from __future__ import annotations

import base64
import binascii
import importlib.util
import io
import json
import math
from pathlib import Path
import textwrap
from typing import Any, Mapping, Sequence

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt
from PIL import Image

from .files import validate_image_bytes, validate_pptx_bytes
from .domain import MODEL_MAX_BYTES, VisualizerContractError, canonical_model, stable_json
from .metric_format import format_metric_value, metric_format_issues

_VENDOR_ADAPTER = Path(__file__).with_name('vendor') / 'production_core' / 'tools' / 'ppt_template_adapter.py'
_MAX_ITEMS_PER_SLIDE = 12


def _adapter():
    spec=importlib.util.spec_from_file_location('company_ui_visualizer_frozen_ppt_adapter', _VENDOR_ADAPTER)
    if spec is None or spec.loader is None: raise RuntimeError('frozen Visualizer PPT adapter is unavailable')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _kind(entry: Mapping[str, Any]) -> str:
    engine=str(entry.get('engine') or '')
    if engine=='ImageMediaEngine': return 'image'
    if engine in {'CoreChartEngine','EngineeringChartEngine'}: return 'chart'
    if engine in {'TableEngine','MatrixEngine'}: return 'table'
    if engine in {'MetricEngine','ComparisonEngine'}: return 'kpi'
    if engine=='DiagramEngine': return 'diagram'
    if engine=='TimelineEngine': return 'timeline'
    if engine=='WaferFabEngine' and str(entry.get('element') or '')=='Wafer Map': return 'wafer_map'
    if engine=='WaferFabEngine' and str(entry.get('element') or '')=='Wafer Difference Map': return 'wafer_difference'
    if engine in {'TextEngine','EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'}: return 'text'
    return 'fallback'


def _statistical_export_projection(entry: dict[str, Any], result: Mapping[str, Any]) -> None:
    """Project the canonical statistical result into editable PPT primitives."""
    explicit_error=str(entry.get('analysis_error') or '').strip()
    semantic=entry.get('analysis_semantics') if isinstance(entry.get('analysis_semantics'),Mapping) else {}
    if explicit_error or semantic.get('ok') is False:
        errors=semantic.get('errors') or []
        message=explicit_error or (errors[0].get('message') if errors and isinstance(errors[0],Mapping) else 'The statistical analysis could not be validated.')
        raise VisualizerContractError(str(message))
    if result.get('ok') is not True or (result.get('population') or {}).get('complete') is not True:
        errors=result.get('errors') or []
        message=errors[0].get('message') if isinstance(errors[0],Mapping) else 'Statistical analysis is not valid for export.' if errors else 'Statistical analysis is not valid for export.'
        raise VisualizerContractError(str(message))
    recipe=str(entry.get('analysis_recipe',{}).get('id') or '') if isinstance(entry.get('analysis_recipe'),Mapping) else ''
    derived=result.get('derived_statistics') or {}
    stats=derived.get('stats') or {}
    if recipe=='process-capability':
        entry['value']=stats.get('cpk')
        entry['metric_label']='Cpk'
        entry['detail']=f"mean {_display(stats.get('mean'))} · sigma {_display(stats.get('sigma'))} · Cp {_display(stats.get('cp'))} · Cpk {_display(stats.get('cpk'))}"
        histogram=stats.get('histogram') or {}
        entry['statistical_chart']={'categories':[str(value) for value in histogram.get('edges') or []][:-1], 'series':[{'name':'Complete population count','values':list(histogram.get('counts') or [])}]}
    elif recipe=='xbar-r-process-review':
        labels=list(derived.get('subgroup_labels') or [])
        entry['statistical_chart']={'categories':[str(value) for value in labels], 'series':[{'name':'Xbar subgroup mean','values':list(stats.get('means') or [])},{'name':'R subgroup range','values':list(stats.get('ranges') or [])}]}
        entry['detail']=f"Xbar center {_display(stats.get('xbarbar'))} · R center {_display(stats.get('rbar'))} · n={_display(stats.get('n'))}"
    elif recipe=='doe-response-review':
        if str(entry.get('element') or '')=='DOE Interaction Plot':
            interaction=derived.get('interaction') or {}
            entry['statistical_chart']={'categories':[str(value) for value in interaction.get('levelsB') or []], 'series':[{'name':str(level),'values':[cell.get('mean') for cell in row]} for level,row in zip(interaction.get('levelsA') or [],interaction.get('cells') or [])]}
        else:
            categories=[]; values=[]
            for effect in derived.get('effects') or []:
                for level in effect.get('levels') or []:
                    categories.append(f"{effect.get('factor')}={level.get('level')}"); values.append(level.get('mean'))
            entry['statistical_chart']={'categories':categories,'series':[{'name':'Observed response mean','values':values}]}
        entry['detail']='Observed descriptive means; no significance claim.'


def bound_export_items(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Resolve canonical dataset bindings into the same export-facing fields as the editor.

    The report model remains untouched; this is an export projection so linked visuals
    always use their current shared source rather than stale item-local preview data.
    """
    datasets={str(dataset.get('id')):dataset for dataset in model.get('datasets') or [] if isinstance(dataset,Mapping)}
    resolved=[]
    for source in model.get('items') or []:
        if not isinstance(source,Mapping): continue
        entry=dict(source); dataset=datasets.get(str(entry.get('dataset_id') or ''))
        recipe_id=str(entry.get('analysis_recipe',{}).get('id') or '') if isinstance(entry.get('analysis_recipe'),Mapping) else ''
        if recipe_id in {'xbar-r-process-review','process-capability','doe-response-review'}:
            authoritative=entry.get('authoritative_analysis')
            if not isinstance(authoritative,Mapping): raise VisualizerContractError('Authoritative statistical result is required for PowerPoint export.')
            _statistical_export_projection(entry,authoritative)
        if not dataset:
            resolved.append(entry); continue
        fields=list(dataset.get('fields') or []); rows=[list(row) for row in dataset.get('rows') or [] if isinstance(row,Sequence) and not isinstance(row,(str,bytes))]
        mapping=entry.get('mapping') if isinstance(entry.get('mapping'),Mapping) else {}
        def index(role: str) -> int:
            field_id=mapping.get(role)
            return next((i for i,field in enumerate(fields) if isinstance(field,Mapping) and field.get('id')==field_id),-1)
        def first(role: str) -> Any:
            column=index(role)
            return next((row[column] for row in rows if column>=0 and column<len(row) and row[column] not in (None,'')),None)
        engine=str(entry.get('engine') or '')
        if engine=='TableEngine':
            entry['customTable']={'headers':[str(field.get('name') or field.get('id') or f'Column {i+1}') if isinstance(field,Mapping) else f'Column {i+1}' for i,field in enumerate(fields)],'rows':rows}
        elif engine=='MatrixEngine':
            entry['matrix']=[[str(field.get('name') or field.get('id') or f'Column {i+1}') if isinstance(field,Mapping) else f'Column {i+1}' for i,field in enumerate(fields)],*rows]
        elif engine=='TimelineEngine':
            label=next((index(role) for role in ('category','label','time','x') if index(role)>=0),-1); date=index('time')
            entry['milestones']=[{'label':str(row[label] if label>=0 and label<len(row) else ''),'date':row[date] if date>=0 and date<len(row) else None} for row in rows]
        elif engine=='DiagramEngine':
            source_index,target_index=index('source'),index('target')
            edges=[(str(row[source_index]),str(row[target_index])) for row in rows if source_index>=0 and target_index>=0 and source_index<len(row) and target_index<len(row) and row[source_index] not in (None,'') and row[target_index] not in (None,'')]
            entry['edges']=edges; entry['nodes']=list(dict.fromkeys(node for edge in edges for node in edge))
        elif engine=='WaferFabEngine':
            x=index('die_x') if index('die_x')>=0 else index('x'); y=index('die_y') if index('die_y')>=0 else index('y'); value=index('value')
            reference=index('reference_value'); affected=index('affected_value'); delta=index('delta')
            observations=[]
            for row in rows:
                observed={'x':row[x] if x>=0 and x<len(row) else None,'y':row[y] if y>=0 and y<len(row) else None,'value':row[value] if value>=0 and value<len(row) else None}
                if reference>=0: observed['reference_value']=row[reference] if reference<len(row) else None
                if affected>=0: observed['affected_value']=row[affected] if affected<len(row) else None
                if delta>=0: observed['delta']=row[delta] if delta<len(row) else None
                elif reference>=0 and affected>=0:
                    reference_value=observed.get('reference_value'); affected_value=observed.get('affected_value')
                    observed['delta']=affected_value-reference_value if isinstance(reference_value,(int,float)) and not isinstance(reference_value,bool) and isinstance(affected_value,(int,float)) and not isinstance(affected_value,bool) else None
                observations.append(observed)
            entry['observations']=observations
            entry.update({key:first(key) for key in ('wafer_id','lot_id','tool','chamber','recipe','process')})
        else:
            label=index('category') if index('category')>=0 else (index('label') if index('label')>=0 else (index('time') if index('time')>=0 else index('x'))); value=index('value') if index('value')>=0 else index('y')
            points=[(str(row[label] if label>=0 and label<len(row) else ''),row[value] if value>=0 and value<len(row) else None) for row in rows]
            if engine in {'CoreChartEngine','EngineeringChartEngine'}: entry['data']=points;entry['rows']=[{'label':label,'value':value} for label,value in points];entry['observations']=[{'label':label,'value':value} for label,value in points]
            elif engine=='MetricEngine':
                entry['value']=next((value for _,value in reversed(points) if value is not None),None)
                value_field=index('value') if index('value')>=0 else index('y')
                entry['_metric_field']=fields[value_field] if value_field>=0 and value_field<len(fields) and isinstance(fields[value_field],Mapping) else {}
            elif engine=='ComparisonEngine':
                values=[value for _,value in points if value is not None];entry['before']=values[0] if values else None;entry['after']=values[-1] if values else None
        resolved.append(entry)
    return resolved


def _plan(model: Mapping[str, Any], layout_geometry: Mapping[str, Any] | None = None, *, target_width: int | None = None, target_height: int | None = None) -> dict[str, Any]:
    report_items=list(model.get('items') or [])
    if not report_items: return _adapter().default_plan()
    positioned=[entry for entry in report_items if all(isinstance(entry.get(key),(int,float)) for key in ('x','y','w','h')) and entry['w']>0 and entry['h']>0]
    if len(positioned)==len(report_items):
        canvas=layout_geometry.get('canvas') if isinstance(layout_geometry,Mapping) and isinstance(layout_geometry.get('canvas'),Mapping) else {}
        if layout_geometry is not None and canvas.get('width') and canvas.get('height'):
            canvas_w=float(canvas['width']);canvas_h=float(canvas['height'])
        else:
            canvas_w=max(1200.0,max(float(entry['x'])+float(entry['w']) for entry in report_items))
            canvas_h=max(675.0,max(float(entry['y'])+float(entry['h']) for entry in report_items))
        scale=min(target_width/canvas_w,target_height/canvas_h) if target_width and target_height else 1.0
        offset_x=(target_width-canvas_w*scale)/2 if target_width and target_height else 0.0
        offset_y=(target_height-canvas_h*scale)/2 if target_width and target_height else 0.0
        return {'items':[{'kind':_kind(entry),'title':str(entry.get('title') or entry.get('element') or _kind(entry))[:100],
                          'nx':max(0.0,min(1.0,(offset_x+float(entry['x'])*scale)/target_width)) if target_width else max(0.0,min(1.0,float(entry['x'])/canvas_w)),
                          'ny':max(0.0,min(1.0,(offset_y+float(entry['y'])*scale)/target_height)) if target_height else max(0.0,min(1.0,float(entry['y'])/canvas_h)),
                          'nw':max(.001,min(1.0,float(entry['w'])*scale/target_width)) if target_width else max(.001,min(1.0,float(entry['w'])/canvas_w)),
                          'nh':max(.001,min(1.0,float(entry['h'])*scale/target_height)) if target_height else max(.001,min(1.0,float(entry['h'])/canvas_h))} for entry in report_items]}
    cols=1 if len(report_items)==1 else 2 if len(report_items)<=8 else 3
    rows=max(1,(len(report_items)+cols-1)//cols)
    gap_x=.025 if cols>1 else 0.0; gap_y=.035 if rows>1 else 0.0
    cell_w=(1-gap_x*(cols-1))/cols; cell_h=(1-gap_y*(rows-1))/rows
    items=[]
    for index,entry in enumerate(report_items):
        col=index%cols; row=index//cols
        items.append({'kind':_kind(entry),'title':str(entry.get('title') or entry.get('element') or _kind(entry))[:100],
                      'nx':col*(cell_w+gap_x),'ny':row*(cell_h+gap_y),'nw':cell_w,'nh':cell_h})
    return {'items':items}


def _validated_layout_geometry(value: Any, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Validate and retain the exact Smart/manual geometry that passed browser preflight."""
    if value is None: return None
    if not isinstance(value,Mapping) or not isinstance(value.get('canvas'),Mapping) or not isinstance(value.get('items'),list):
        raise VisualizerContractError('PowerPoint export requires a complete validated report layout.')
    canvas=value['canvas']
    def dimension(raw: Any, name: str, low: int, high: int) -> int:
        if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) or int(raw)!=raw or not low<=int(raw)<=high:
            raise VisualizerContractError(f'PowerPoint layout {name} is invalid.')
        return int(raw)
    width=dimension(canvas.get('width'),'canvas width',640,3840); height=dimension(canvas.get('height'),'canvas height',360,4800)
    expected={str(entry.get('id') or '') for entry in entries}
    if not all(expected) or len(expected)!=len(entries): raise VisualizerContractError('PowerPoint report elements require unique ids.')
    rects=[]; seen=set()
    for source in value['items']:
        if not isinstance(source,Mapping): raise VisualizerContractError('PowerPoint layout element geometry is malformed.')
        item_id=str(source.get('id') or '')
        if not item_id or item_id in seen: raise VisualizerContractError('PowerPoint layout contains duplicate or missing element ids.')
        seen.add(item_id)
        rect={key:source.get(key) for key in ('x','y','w','h')}
        if any(isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) for raw in rect.values()):
            raise VisualizerContractError(f'PowerPoint layout geometry for {item_id} is invalid.')
        x,y,w,h=(float(rect[key]) for key in ('x','y','w','h'))
        if w<=0 or h<=0 or x<-.1 or y<-.1 or x+w>width+.1 or y+h>height+.1:
            raise VisualizerContractError(f'PowerPoint layout geometry for {item_id} exceeds the report canvas.')
        rects.append({'id':item_id,'x':x,'y':y,'w':w,'h':h})
    if seen!=expected: raise VisualizerContractError('PowerPoint layout elements do not match the saved report.')
    for index,first in enumerate(rects):
        for second in rects[index+1:]:
            intersection_w=min(first['x']+first['w'],second['x']+second['w'])-max(first['x'],second['x'])
            intersection_h=min(first['y']+first['h'],second['y']+second['h'])-max(first['y'],second['y'])
            if intersection_w>1 and intersection_h>1:
                raise VisualizerContractError('PowerPoint layout contains overlapping report elements.')
    return {'canvas':{'width':width,'height':height},'items':rects}


def _export_pages(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split deterministically, honoring optional integer page/page_index and page_break metadata."""
    explicit=any(isinstance(entry.get('page_index',entry.get('page')) ,int) for entry in entries)
    if explicit:
        grouped: dict[int,list[dict[str, Any]]]={}
        for entry in entries: grouped.setdefault(int(entry.get('page_index',entry.get('page',0))),[]).append(entry)
        return [grouped[index] for index in sorted(grouped)]
    ordered=sorted(entries,key=lambda entry:(int(entry.get('order',0)),str(entry.get('id',''))))
    pages: list[list[dict[str, Any]]]=[[]]
    for entry in ordered:
        if pages[-1] and (entry.get('page_break') is True or len(pages[-1])>=_MAX_ITEMS_PER_SLIDE): pages.append([])
        pages[-1].append(entry)
    return [page for page in pages if page]


def _display(value: Any) -> str:
    if value is None: return ''
    if isinstance(value,bool): return 'True' if value else 'False'
    return str(value)


def _semantic_text(entry: Mapping[str, Any]) -> str:
    engine=str(entry.get('engine') or '')
    if engine=='TextEngine': return str(entry.get('text') or entry.get('body') or '')
    if engine=='TimelineEngine':
        lines=[]
        for milestone in entry.get('milestones') or []:
            label=str(milestone.get('label') or '') if isinstance(milestone,Mapping) else str(milestone)
            date=milestone.get('date') if isinstance(milestone,Mapping) else None
            lines.append(f'{label} · {date}' if date not in (None,'') else label)
        return '\n'.join(lines)
    if engine=='DiagramEngine':
        nodes=[str(x) for x in entry.get('nodes') or []]; edges=entry.get('edges') or []
        return '\n'.join(nodes + [f'{edge[0]} → {edge[1]}' for edge in edges if isinstance(edge,Sequence) and not isinstance(edge,(str,bytes)) and len(edge)>=2])
    if engine in {'EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'}:
        return '\n'.join(x for x in [str(entry.get('statement') or ''),str(entry.get('detail') or ''),str(entry.get('status') or '')] if x)
    if engine=='ImageMediaEngine': return '\n'.join(x for x in [str(entry.get('caption') or ''),str(entry.get('alt') or '')] if x)
    if engine in {'WaferFabEngine','SmartLayoutEngine','InteractionLayer','EditorInfrastructure'}:
        return str(entry.get('configuration') or entry.get('behavior') or entry.get('route') or entry.get('element') or '')
    return str(entry.get('detail') or entry.get('element') or '')


def _chart_rows(entry: Mapping[str, Any]) -> list[tuple[str, Any]]:
    rows=entry.get('rows') or entry.get('data') or entry.get('observations') or []
    result=[]
    for i,row in enumerate(rows):
        if isinstance(row,Mapping): result.append((str(row.get('label') or row.get('x') or i+1),row.get('value')))
        elif isinstance(row,Sequence) and not isinstance(row,(str,bytes)) and len(row)>=2: result.append((str(row[0]),row[1]))
    return result or [('Value',None)]


def _table_grid(entry: Mapping[str, Any]) -> tuple[list[str],list[list[Any]]]:
    engine=str(entry.get('engine') or '')
    if engine=='MatrixEngine':
        rows=[list(r) for r in entry.get('matrix') or []]; cols=max((len(r) for r in rows),default=0)
        return [f'C{i+1}' for i in range(cols)],rows
    custom=entry.get('customTable') or {}
    headers=[str(x) for x in custom.get('headers') or []] if isinstance(custom,Mapping) else []
    rows=[list(r) for r in (custom.get('rows') or [])] if isinstance(custom,Mapping) else []
    if not rows: rows=[list(r) for r in entry.get('rows') or [] if isinstance(r,Sequence) and not isinstance(r,(str,bytes))]
    cols=max(len(headers),max((len(r) for r in rows),default=0),1)
    if not headers: headers=[f'Column {i+1}' for i in range(cols)]
    headers=(headers+['']*cols)[:cols]; rows=[(r+[None]*cols)[:cols] for r in rows]
    return headers,rows


def _set_semantic_metadata(shape: Any, entry: Mapping[str, Any]) -> None:
    """Embed the exact canonical element payload so 0, '0', blank and null remain distinguishable."""
    try:
        nodes=shape._element.xpath('.//p:cNvPr')
        if nodes: nodes[0].set('descr','VisualizerSemantic:'+json.dumps(entry,ensure_ascii=False,separators=(',',':')))
    except Exception:
        pass


def _set_report_metadata(slide: Any, model: Mapping[str, Any]) -> None:
    """Store bounded model context without changing the visible slide composition."""
    shape=slide.shapes.add_textbox(0,0,1,1)
    shape.name='VIZ::SemanticReport'
    nodes=shape._element.xpath('.//p:cNvPr')
    if nodes: nodes[0].set('descr','VisualizerSemanticReport:'+stable_json(model))


def _set_blank_report_slide_size(prs: Any, layout_geometry: Mapping[str, Any] | None) -> None:
    """Match a blank PowerPoint page to the validated browser canvas aspect ratio."""
    if not isinstance(layout_geometry,Mapping): return
    canvas=layout_geometry.get('canvas')
    if not isinstance(canvas,Mapping): return
    width,height=float(canvas.get('width') or 0),float(canvas.get('height') or 0)
    if width<=0 or height<=0: return
    longest=Inches(13.333333)
    scale=longest/max(width,height)
    prs.slide_width=round(width*scale)
    prs.slide_height=round(height*scale)


def _replace_image(slide: Any, shape: Any, entry: Mapping[str, Any], title: str, asset_data_url: Any=None) -> Any:
    src=entry.get('src') or (asset_data_url(entry['asset_id']) if asset_data_url and entry.get('asset_id') else None)
    if not isinstance(src,str) or not src.startswith('data:image/') or ';base64,' not in src:
        return shape
    _,encoded=src.split(',',1)
    raw=base64.b64decode(encoded,validate=True)
    image=Image.open(io.BytesIO(raw)); image.load()
    payload=io.BytesIO()
    image.convert('RGBA' if image.mode=='RGBA' else 'RGB').save(payload,format='PNG')
    left,top,width,height=shape.left,shape.top,shape.width,shape.height
    shape._element.getparent().remove(shape._element)
    picture=slide.shapes.add_picture(io.BytesIO(payload.getvalue()),left,top,width,height)
    picture.name=f'VIZ::{title} image'
    return picture


_DIAGRAM_FONT_PT = 10.0
_DIAGRAM_MIN_GAP = Inches(.11)


def _diagram_graph(entry: Mapping[str, Any]) -> tuple[list[str], list[tuple[int, str, str, Any]]]:
    nodes=[str(node) for node in entry.get('nodes') or []]
    if len(nodes)!=len(set(nodes)): raise VisualizerContractError('PowerPoint diagrams require unique node labels.')
    node_indexes={label:index for index,label in enumerate(nodes)}
    edges=[]
    for position,edge in enumerate(entry.get('edges') or []):
        if isinstance(edge,Mapping):
            source,target=edge.get('source',edge.get('from')),edge.get('target',edge.get('to'))
            index=int(edge.get('_diagram_edge_index',position))
        elif isinstance(edge,Sequence) and not isinstance(edge,(str,bytes)) and len(edge)>=2: source,target=edge[0],edge[1];index=position
        else: raise VisualizerContractError('PowerPoint diagram contains a malformed edge.')
        source,target=str(source),str(target)
        if source not in node_indexes or target not in node_indexes: raise VisualizerContractError('PowerPoint diagram edge references a missing node.')
        if node_indexes[source]>=node_indexes[target]: raise VisualizerContractError('PowerPoint diagram edges must preserve the declared causal node order.')
        edges.append((index,source,target,edge))
    return nodes,edges


def _wrap_diagram_label(label: str, width: int, font_size: float) -> list[str]:
    """Insert deterministic word breaks before PowerPoint lays out editable text."""
    usable_points=max(font_size, width/914400*72-14.0)
    capacity=max(1,int(usable_points/(font_size*.55)))
    lines=[]
    for paragraph in str(label).splitlines() or ['']:
        lines.extend(textwrap.wrap(paragraph, width=capacity, break_long_words=True, break_on_hyphens=False, replace_whitespace=True, drop_whitespace=True) or [''])
    return lines


def _diagram_text(slide: Any, name: str, text: str, rect: tuple[int, int, int, int], *, size: float, bold: bool=False) -> Any:
    left,top,width,height=rect
    shape=slide.shapes.add_textbox(left,top,width,height);shape.name=name
    frame=shape.text_frame;frame.clear();frame.word_wrap=False
    frame.margin_left=frame.margin_right=Inches(.05);frame.margin_top=frame.margin_bottom=Inches(.025)
    frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    for index,line in enumerate(text.split('\n') or ['']):
        paragraph=frame.paragraphs[0] if index==0 else frame.add_paragraph()
        paragraph.text=line;paragraph.alignment=PP_ALIGN.CENTER;paragraph.font.name='Arial';paragraph.font.size=Pt(size);paragraph.font.bold=bold;paragraph.font.color.rgb=RGBColor(35,52,73);paragraph.space_after=Pt(0);paragraph.line_spacing=Pt(size*1.12)
    return shape


def _diagram_node_text(shape: Any, text: str) -> None:
    frame=shape.text_frame;frame.clear();frame.word_wrap=False
    frame.margin_left=frame.margin_right=Inches(.10);frame.margin_top=frame.margin_bottom=Inches(.08)
    frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    for index,line in enumerate(text.split('\n') or ['']):
        paragraph=frame.paragraphs[0] if index==0 else frame.add_paragraph()
        paragraph.text=line;paragraph.alignment=PP_ALIGN.CENTER;paragraph.font.name='Arial';paragraph.font.size=Pt(_DIAGRAM_FONT_PT);paragraph.font.color.rgb=RGBColor(35,52,73);paragraph.space_after=Pt(0);paragraph.line_spacing=Pt(_DIAGRAM_FONT_PT*1.12)


def _diagram_layout(nodes: Sequence[str], direction: str, title: str, rect: tuple[int, int, int, int], *, outgoing: bool=False) -> dict[str, Any] | None:
    left,top,width,height=rect
    if width<Inches(1.45) or height<Inches(.85) or not nodes: return None
    direction='down' if direction in {'down','vertical','top-to-bottom'} else 'right'
    side=Inches(.06);heading_lines=_wrap_diagram_label(title,width-2*side,11.5)
    heading_height=max(Inches(.25),round(len(heading_lines)*Inches(.19)+Inches(.04)))
    body_top=top+heading_height+Inches(.08);body_bottom=top+height-Inches(.07)-(Inches(.31) if outgoing else 0)
    body_height=body_bottom-body_top
    if body_height<=0: return None
    if direction=='down':
        node_width=width-2*side
        if node_width<Inches(1.2): return None
        node_left=left+side;wraps=[_wrap_diagram_label(label,node_width, _DIAGRAM_FONT_PT) for label in nodes]
        heights=[max(Inches(.54),round(len(lines)*Inches(_DIAGRAM_FONT_PT*1.18/72)+Inches(.19))) for lines in wraps]
        free=body_height-sum(heights)
        gap=0 if len(nodes)==1 else min(Inches(.30),free//(len(nodes)-1))
        if free<0 or (len(nodes)>1 and gap<_DIAGRAM_MIN_GAP): return None
        placements=[];cursor=body_top
        for label,lines,node_height in zip(nodes,wraps,heights):
            placements.append({'label':label,'text':'\n'.join(lines),'rect':(node_left,cursor,node_width,node_height)})
            cursor+=node_height+gap
    else:
        gap=Inches(.22);usable=width-2*side-gap*(len(nodes)-1)
        node_width=usable//len(nodes) if nodes else 0
        if node_width<Inches(.75): return None
        wraps=[_wrap_diagram_label(label,node_width, _DIAGRAM_FONT_PT) for label in nodes]
        node_height=max(max(Inches(.54),round(len(lines)*Inches(_DIAGRAM_FONT_PT*1.18/72)+Inches(.19))) for lines in wraps)
        if node_height>body_height: return None
        node_top=body_top+(body_height-node_height)//2;placements=[];cursor=left+side
        for label,lines in zip(nodes,wraps):
            placements.append({'label':label,'text':'\n'.join(lines),'rect':(cursor,node_top,node_width,node_height)})
            cursor+=node_width+gap
    return {'direction':direction,'heading':{'text':'\n'.join(heading_lines),'rect':(left+side,top+Inches(.02),width-2*side,heading_height)},'nodes':placements,'body_bottom':body_bottom,'rect':rect}


def _set_diagram_arrow(connector: Any) -> None:
    connector.line.color.rgb=RGBColor(67,91,121);connector.line.width=Pt(1.5)
    line=connector._element.spPr.ln
    for item in list(line):
        if item.tag.endswith('tailEnd'): line.remove(item)
    arrow=OxmlElement('a:tailEnd');arrow.set('type','triangle');arrow.set('w','med');arrow.set('len','med');line.append(arrow)


def _validate_diagram_geometry(slide: Any, rect: tuple[int, int, int, int], shapes: Sequence[Any]) -> None:
    left,top,width,height=rect;right,bottom=left+width,top+height
    slide_size=slide.part.package.presentation_part._element.sldSz
    slide_right,slide_bottom=int(slide_size.cx),int(slide_size.cy)
    for shape in shapes:
        if shape.left<left or shape.top<top or shape.left+shape.width>right or shape.top+shape.height>bottom:
            raise VisualizerContractError(f'PowerPoint diagram primitive {shape.name} exceeds its assigned element region.')
        if shape.left<0 or shape.top<0 or shape.left+shape.width>slide_right or shape.top+shape.height>slide_bottom:
            raise VisualizerContractError(f'PowerPoint diagram primitive {shape.name} exceeds the slide bounds.')
    nodes=[shape for shape in shapes if '::node-' in shape.name and not shape.name.endswith('::label')]
    for index,first in enumerate(nodes):
        for second in nodes[index+1:]:
            overlap_x=min(first.left+first.width,second.left+second.width)-max(first.left,second.left)
            overlap_y=min(first.top+first.height,second.top+second.height)-max(first.top,second.top)
            if overlap_x>1 and overlap_y>1: raise VisualizerContractError('PowerPoint diagram node boxes overlap.')


def _diagram_description(shape: Any, prefix: str, value: Mapping[str, Any]) -> None:
    nodes=shape._element.xpath('.//p:cNvPr')
    if nodes: nodes[0].set('descr',prefix+json.dumps(value,ensure_ascii=False,separators=(',',':')))


def _render_diagram(slide: Any, rect: tuple[int, int, int, int], entry: Mapping[str, Any], title: str, *, page: int=1, page_count: int=1, outgoing: Sequence[tuple[int,str,str,Any]]=(), continued: bool=False) -> Any:
    nodes,edges=_diagram_graph(entry);direction=str(entry.get('direction') or 'right')
    heading=title+(f' · Continued {page}/{page_count}' if continued else '')
    layout=_diagram_layout(nodes,direction,heading,rect,outgoing=bool(outgoing))
    if layout is None: raise VisualizerContractError('PowerPoint diagram cannot fit its assigned region at readable minimum typography.')
    start=len(slide.shapes);heading_shape=_diagram_text(slide,f'VIZ::DiagramTitle::{title}::{page}',layout['heading']['text'],layout['heading']['rect'],size=11.5,bold=True)
    by_label={}
    node_offset=int(entry.get('_diagram_node_offset') or 0)
    for index,node in enumerate(layout['nodes']):
        semantic_index=node_offset+index
        left,top,width,height=node['rect'];shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,left,top,width,height)
        shape.name=f'VIZ::{title}::{node["label"]}::node-{semantic_index+1}';shape.fill.solid();shape.fill.fore_color.rgb=RGBColor(235,242,250);shape.line.color.rgb=RGBColor(102,133,173);shape.line.width=Pt(.9)
        _diagram_node_text(shape,node['text'])
        by_label[node['label']]=shape
        _diagram_description(shape,'VisualizerDiagramNode:',{'item_id':str(entry.get('id') or ''),'node_index':semantic_index,'label':node['label'],'page':page,'page_count':page_count,'direction':layout['direction']})
    for edge_index,source_label,target_label,_raw in edges:
        if source_label not in by_label or target_label not in by_label: continue
        source,target=by_label[source_label],by_label[target_label]
        if layout['direction']=='down':
            x1=source.left+source.width//2;y1=source.top+source.height+Inches(.005);x2=target.left+target.width//2;y2=target.top-Inches(.005)
        else:
            x1=source.left+source.width+Inches(.005);y1=source.top+source.height//2;x2=target.left-Inches(.005);y2=target.top+target.height//2
        connector=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,x1,y1,x2,y2);connector.name=f'VIZ::DiagramEdge::{title}::{edge_index+1}';_set_diagram_arrow(connector)
        _diagram_description(connector,'VisualizerSemanticEdge:',{'item_id':str(entry.get('id') or ''),'edge_index':edge_index,'source':source_label,'target':target_label,'continuation':False})
    if outgoing:
        source_shape=by_label[layout['nodes'][-1]['label']]
        left,top,width,height=rect;footer_y=layout['body_bottom']+Inches(.035);footer_h=top+height-footer_y-Inches(.015)
        footer=_diagram_text(slide,f'VIZ::DiagramContinuation::{title}::{page}','Continues on next slide',(left+Inches(.08),footer_y,width-Inches(.16),footer_h),size=8.5)
        edge_index,source_label,target_label,_raw=outgoing[0]
        if layout['direction']=='down':
            x=source_shape.left+source_shape.width//2;y1=source_shape.top+source_shape.height+Inches(.005);y2=footer_y+Inches(.005)
            connector=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,x,y1,x,y2)
        else:
            x1=source_shape.left+source_shape.width+Inches(.005);x2=left+width-Inches(.06);y=source_shape.top+source_shape.height//2
            connector=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,x1,y,x2,y)
        connector.name=f'VIZ::DiagramEdge::{title}::{edge_index+1}';_set_diagram_arrow(connector)
        _diagram_description(connector,'VisualizerSemanticEdge:',{'item_id':str(entry.get('id') or ''),'edge_index':edge_index,'source':source_label,'target':target_label,'continuation':True})
        for edge_index,source_label,target_label,_raw in outgoing[1:]:
            stub=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,source_shape.left+source_shape.width//2,source_shape.top+source_shape.height+Inches(.005),source_shape.left+source_shape.width//2,footer_y+Inches(.005))
            stub.name=f'VIZ::DiagramEdge::{title}::{edge_index+1}';_set_diagram_arrow(stub)
            _diagram_description(stub,'VisualizerSemanticEdge:',{'item_id':str(entry.get('id') or ''),'edge_index':edge_index,'source':source_label,'target':target_label,'continuation':True})
    all_created=[slide.shapes[index] for index in range(start,len(slide.shapes))]
    _validate_diagram_geometry(slide,rect,all_created)
    _diagram_description(heading_shape,'VisualizerDiagramContinuation:',{'item_id':str(entry.get('id') or ''),'page':page,'page_count':page_count,'direction':layout['direction']})
    return by_label[nodes[0]]


def _replace_diagram(slide: Any, shape: Any, entry: Mapping[str, Any], title: str, continuations: list[dict[str, Any]] | None=None) -> Any:
    nodes,_edges=_diagram_graph(entry)
    if not nodes: return shape
    rect=(shape.left,shape.top,shape.width,shape.height)
    try:
        rendered=_render_diagram(slide,rect,entry,title)
        if getattr(shape,'has_text_frame',False): shape.text_frame.clear()
        return rendered
    except VisualizerContractError as exc:
        if 'cannot fit its assigned region' not in str(exc): raise
    frame=shape.text_frame;frame.clear();frame.word_wrap=True;frame.margin_left=frame.margin_right=Inches(.08);frame.margin_top=frame.margin_bottom=Inches(.05);frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    paragraph=frame.paragraphs[0];paragraph.text=f'{title}\nContinued on following slides';paragraph.alignment=PP_ALIGN.CENTER;paragraph.font.name='Arial';paragraph.font.size=Pt(8.5);paragraph.font.color.rgb=RGBColor(35,52,73)
    shape.name=f'VIZ::{title}::continuation-reference';shape.fill.solid();shape.fill.fore_color.rgb=RGBColor(245,248,252);shape.line.color.rgb=RGBColor(102,133,173)
    if continuations is not None: continuations.append({'entry':dict(entry),'title':title,'reference':shape})
    return shape


def _partition_diagram(entry: Mapping[str, Any], title: str, rect: tuple[int, int, int, int]) -> list[dict[str, Any]]:
    nodes,edges=_diagram_graph(entry);direction=str(entry.get('direction') or 'right');pages=[];start=0
    while start<len(nodes):
        best=None
        for end in range(start+1,len(nodes)+1):
            internal=[edge for edge in edges if start<=nodes.index(edge[1])<end and start<=nodes.index(edge[2])<end]
            outgoing=[edge for edge in edges if start<=nodes.index(edge[1])<end<=nodes.index(edge[2])]
            if any(nodes.index(edge[1])!=end-1 for edge in outgoing): continue
            if _diagram_layout(nodes[start:end],direction,title+' · Continued',rect,outgoing=bool(outgoing)) is None: break
            subset={**entry,'nodes':nodes[start:end],'edges':[{'source':edge[1],'target':edge[2],'_diagram_edge_index':edge[0]} for edge in internal],'_diagram_node_offset':start}
            best={'start':start,'end':end,'entry':subset,'outgoing':outgoing,'internal':internal}
        if best is None: raise VisualizerContractError('PowerPoint diagram contains a label that cannot fit a continuation slide at readable minimum typography.')
        pages.append(best);start=best['end']
    return pages


def _export_diagram_continuations(prs: Any, pending: Sequence[dict[str, Any]]) -> None:
    prepared=[]
    for item in pending:
        rect=(Inches(.5),Inches(.4),prs.slide_width-Inches(1.0),prs.slide_height-Inches(.8))
        pages=_partition_diagram(item['entry'],item['title'],rect);prepared.append((item,rect,pages))
    page_number=len(prs.slides)+1
    for item,rect,pages in prepared:
        last_number=page_number+len(pages)-1
        reference=item['reference'];reference.text_frame.clear();p=reference.text_frame.paragraphs[0];p.text=f'Diagram continues on slides {page_number}–{last_number}';p.alignment=PP_ALIGN.CENTER;p.font.name='Arial';p.font.size=Pt(8.5);p.font.color.rgb=RGBColor(35,52,73)
        nodes,_edges=_diagram_graph(item['entry'])
        for index,page in enumerate(pages,1):
            slide=prs.slides.add_slide(prs.slide_layouts[6]);entry={**page['entry'],'nodes':nodes[page['start']:page['end']], 'edges':[{'source':edge[1],'target':edge[2],'_diagram_edge_index':edge[0]} for edge in page['internal']],'_diagram_node_offset':page['start']}
            _render_diagram(slide,rect,entry,item['title'],page=index,page_count=len(pages),outgoing=page['outgoing'],continued=True)
        page_number=last_number+1


def _numeric(value: Any) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _mix_color(start: tuple[int,int,int], end: tuple[int,int,int], ratio: float) -> RGBColor:
    amount=max(0.0,min(1.0,float(ratio)))
    return RGBColor(*(round(a+(b-a)*amount) for a,b in zip(start,end)))


def _wafer_color(value: Any, low: float | None, high: float | None, *, difference: bool) -> RGBColor:
    if not _numeric(value): return RGBColor(205,211,219)
    if difference:
        extent=max(abs(low or 0.0),abs(high or 0.0),1e-12)
        neutral=(180,188,197)
        if value<0: return _mix_color((54,90,199),neutral,(value+extent)/extent)
        return _mix_color(neutral,(201,79,95),value/extent)
    if low is None or high is None or low==high: return RGBColor(87,112,183)
    return _mix_color((54,90,199),(201,79,95),(value-low)/(high-low))


def _ppt_text(slide: Any, text: str, name: str, left: int, top: int, width: int, height: int, *, size: float=8, bold: bool=False, color: tuple[int,int,int]=(52,65,82)) -> Any:
    shape=slide.shapes.add_textbox(left,top,width,height);shape.name=name
    frame=shape.text_frame;frame.clear();frame.word_wrap=True;frame.margin_left=0;frame.margin_right=0;frame.margin_top=0;frame.margin_bottom=0
    paragraph=frame.paragraphs[0];paragraph.text=text;paragraph.font.size=Pt(size);paragraph.font.bold=bold;paragraph.font.color.rgb=RGBColor(*color)
    return shape


def _replace_wafer_map(slide: Any, shape: Any, entry: Mapping[str, Any], title: str, *, difference: bool) -> Any:
    """Draw an editable wafer panel from canonical die observations."""
    left,top,width,height=shape.left,shape.top,shape.width,shape.height
    shape._element.getparent().remove(shape._element)
    panel=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,left,top,width,height);panel.name=f'VIZ::{title}::spatial-panel'
    panel.fill.solid();panel.fill.fore_color.rgb=RGBColor(255,255,255);panel.line.color.rgb=RGBColor(211,219,229);panel.line.width=Pt(.8)
    observations=[dict(value) for value in entry.get('observations') or [] if isinstance(value,Mapping)]
    def die_value(observation: Mapping[str,Any]) -> Any:
        if not difference: return observation.get('value')
        delta=observation.get('delta')
        if _numeric(delta): return delta
        reference,affected=observation.get('reference_value'),observation.get('affected_value')
        if _numeric(reference) and _numeric(affected): return affected-reference
        return observation.get('value')
    numeric_values=[float(die_value(observation)) for observation in observations if _numeric(die_value(observation))]
    low=min(numeric_values) if numeric_values else None;high=max(numeric_values) if numeric_values else None
    title_y=top+max(Inches(.09),height*.035);title_h=max(Inches(.24),height*.09)
    _ppt_text(slide,title,f'VIZ::{title}::title',left+width*.04,title_y,width*.92,title_h,size=12,bold=True,color=(28,43,62))
    identity=[]
    for label,keys in [('Wafer',('wafer_id','wafer')),('Lot',('lot_id','lot')),('Tool',('tool',)),('Chamber',('chamber',)),('Recipe',('recipe',)),('Process',('process',))]:
        value=next((entry.get(key) for key in keys if entry.get(key) not in (None,'')),None)
        if value is not None: identity.append(f'{label} {value}')
    extent_text=(f'Delta {low:+g} to {high:+g}' if difference and low is not None and high is not None else f'Value {low:g} to {high:g}' if low is not None and high is not None else 'No numeric die values')
    missing=sum(not _numeric(die_value(observation)) for observation in observations)
    scope=f'{len(observations)} observations · {missing} missing · {extent_text}'
    metadata=' · '.join(identity)
    details='\n'.join(value for value in (metadata,scope) if value)
    meta_top=title_y+title_h+Inches(.04);meta_h=min(Inches(.52),max(Inches(.25),height*.16))
    _ppt_text(slide,details,f'VIZ::{title}::metadata',left+width*.04,meta_top,width*.92,meta_h,size=7.5,color=(79,94,113))

    pad=max(Inches(.12),width*.035);body_top=meta_top+meta_h+Inches(.04);body_bottom=top+height-pad
    body_h=max(Inches(.45),body_bottom-body_top);side_layout=width>=Inches(5.8) and body_h>=Inches(1.6)
    if side_layout:
        diameter=min(width*.46,body_h*.94);map_left=left+pad;map_top=body_top+(body_h-diameter)/2
        legend_left=map_left+diameter+pad;legend_top=body_top+body_h*.29;legend_width=max(Inches(.8),left+width-pad-legend_left)
    else:
        diameter=min(width*.72,body_h*.68);map_left=left+(width-diameter)/2;map_top=body_top+max(0,(body_h-diameter-Inches(.3))/2)
        legend_left=left+pad;legend_top=min(body_bottom-Inches(.27),map_top+diameter+Inches(.04));legend_width=width-2*pad
    diameter=max(Inches(.65),diameter)
    outline=slide.shapes.add_shape(MSO_SHAPE.OVAL,map_left,map_top,diameter,diameter);outline.name=f'VIZ::{title}::wafer-outline'
    outline.fill.solid();outline.fill.fore_color.rgb=RGBColor(247,249,252);outline.line.color.rgb=RGBColor(39,54,74);outline.line.width=Pt(1.2)
    notch_w=max(Inches(.10),diameter*.065);notch_h=max(Inches(.035),diameter*.024)
    notch=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,map_left+diameter/2-notch_w/2,map_top-Inches(.004),notch_w,notch_h);notch.name=f'VIZ::{title}::orientation-notch'
    notch.fill.solid();notch.fill.fore_color.rgb=RGBColor(255,255,255);notch.line.fill.background()
    _ppt_text(slide,'N · NOTCH',f'VIZ::{title}::orientation',map_left+diameter*.37,map_top-Inches(.16),diameter*.7,Inches(.13),size=6,bold=True,color=(79,94,113))

    points=[(index,observation) for index,observation in enumerate(observations) if _numeric(observation.get('x')) and _numeric(observation.get('y'))]
    if points:
        center_x=map_left+diameter/2;center_y=map_top+diameter/2;radius=diameter/2
        center_data_x=sum(float(observation['x']) for _,observation in points)/len(points);center_data_y=sum(float(observation['y']) for _,observation in points)/len(points)
        max_radius=max((math.hypot(float(observation['x'])-center_data_x,float(observation['y'])-center_data_y) for _,observation in points),default=0.0)
        cell=max(Inches(.035),min(Inches(.16),diameter*.075));scale=max(0.0,(radius-cell*.72)/max_radius) if max_radius else 0.0
        for index,observation in points:
            value=die_value(observation);die=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,center_x+(float(observation['x'])-center_data_x)*scale-cell/2,center_y-(float(observation['y'])-center_data_y)*scale-cell/2,cell,cell)
            die.name=f'VIZ::{title}::die-{index+1}';die.fill.solid();die.fill.fore_color.rgb=_wafer_color(value,low,high,difference=difference);die.line.color.rgb=RGBColor(255,255,255);die.line.width=Pt(.45)
            detail={'index':index,'x':observation.get('x'),'y':observation.get('y'),'value':observation.get('value'),'delta':value if difference else None,'reference_value':observation.get('reference_value'),'affected_value':observation.get('affected_value')}
            try: die._element.xpath('.//p:cNvPr')[0].set('descr','VisualizerSemanticDie:'+json.dumps(detail,ensure_ascii=False,separators=(',',':')))
            except Exception: pass
    else:
        _ppt_text(slide,'No die coordinates',f'VIZ::{title}::empty',map_left+diameter*.15,map_top+diameter*.47,diameter*.7,Inches(.22),size=8,color=(100,112,128))

    if difference:
        legend_title='SIGNED DELTA · AFFECTED − REFERENCE'; colors=[_wafer_color(-max(abs(low or 0),abs(high or 0)),low,high,difference=True),_wafer_color(0,low,high,difference=True),_wafer_color(max(abs(low or 0),abs(high or 0)),low,high,difference=True)]
        labels=[f'{-max(abs(low or 0),abs(high or 0)):g}','0',f'+{max(abs(low or 0),abs(high or 0)):g}']
    else:
        legend_title='MEASURED VALUE';colors=[_wafer_color(low,low,high,difference=False),_wafer_color((low+high)/2 if low is not None and high is not None else low,low,high,difference=False),_wafer_color(high,low,high,difference=False)];labels=[f'{low:g}' if low is not None else 'Missing',f'{(low+high)/2:g}' if low is not None and high is not None else '—',f'{high:g}' if high is not None else '—']
    title_height=Inches(.19);_ppt_text(slide,legend_title,f'VIZ::{title}::legend-title',legend_left,legend_top,legend_width,title_height,size=6.5,bold=True,color=(58,72,91))
    band_top=legend_top+title_height+Inches(.04);band_h=max(Inches(.10),min(Inches(.16),height*.04));gap=Inches(.025);band_w=max(Inches(.04),(legend_width-gap*8)/9)
    for index in range(9):
        value=low+(high-low)*index/8 if low is not None and high is not None else low
        if difference:
            extent=max(abs(low or 0),abs(high or 0));value=-extent+2*extent*index/8
        swatch=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,legend_left+index*(band_w+gap),band_top,band_w,band_h);swatch.name=f'VIZ::{title}::legend-{index+1}'
        swatch.fill.solid();swatch.fill.fore_color.rgb=_wafer_color(value,low,high,difference=difference);swatch.line.fill.background()
    _ppt_text(slide,labels[0],f'VIZ::{title}::legend-low',legend_left,band_top+band_h+Inches(.025),legend_width*.3,Inches(.17),size=7,color=(80,94,113))
    _ppt_text(slide,labels[-1],f'VIZ::{title}::legend-high',legend_left+legend_width*.7,band_top+band_h+Inches(.025),legend_width*.3,Inches(.17),size=7,color=(80,94,113))
    return panel


def _fill_text_shape(shape: Any, entry: Mapping[str, Any], title: str) -> None:
    if not getattr(shape,'has_text_frame',False): return
    tf=shape.text_frame; tf.clear(); p=tf.paragraphs[0]; p.text=title; p.font.bold=True; p.font.size=Pt(13)
    body=_semantic_text(entry)
    if body:
        p2=tf.add_paragraph(); p2.text=body; p2.font.size=Pt(10)


def _fill_kpi(shape: Any, entry: Mapping[str, Any], title: str) -> None:
    if not getattr(shape,'has_text_frame',False): return
    value=entry.get('value')
    if value is None and str(entry.get('engine') or '')=='ComparisonEngine':
        value=f"{_display(entry.get('before'))} → {_display(entry.get('after'))}".strip()
    tf=shape.text_frame; tf.clear();p=tf.paragraphs[0];p.text=f"{title} · {entry.get('metric_label')}" if entry.get('metric_label') else title;p.font.bold=True;p.font.size=Pt(10)
    p2=tf.add_paragraph();p2.text=format_metric_value(value,entry,entry.get('_metric_field')) if str(entry.get('engine') or '')=='MetricEngine' else _display(value);p2.font.bold=True;p2.font.size=Pt(24)
    unit=str(entry.get('unit') or '')
    if unit and str(entry.get('engine') or '')!='MetricEngine':
        p3=tf.add_paragraph();p3.text=unit;p3.font.size=Pt(9)
    if entry.get('detail'):
        p3=tf.add_paragraph();p3.text=str(entry['detail']);p3.font.size=Pt(8)


def _fill_chart(shape: Any, entry: Mapping[str, Any], title: str) -> None:
    if not getattr(shape,'has_chart',False): return
    statistical=entry.get('statistical_chart') if isinstance(entry.get('statistical_chart'),Mapping) else None
    if statistical:
        data=ChartData();data.categories=[str(value) for value in statistical.get('categories') or []]
        for series in statistical.get('series') or []:
            if isinstance(series,Mapping): data.add_series(str(series.get('name') or title),list(series.get('values') or []))
        shape.chart.replace_data(data)
    else:
        rows=_chart_rows(entry);data=ChartData();data.categories=[r[0] for r in rows];data.add_series(title,[r[1] for r in rows]);shape.chart.replace_data(data)
    shape.chart.has_title=True;shape.chart.chart_title.text_frame.text=title;shape.chart.has_legend=False


def _replace_table(slide: Any, shape: Any, entry: Mapping[str, Any], title: str) -> Any:
    headers,rows=_table_grid(entry);cols=max(1,len(headers));nrows=max(2,1+len(rows))
    left,top,width,height=shape.left,shape.top,shape.width,shape.height
    shape._element.getparent().remove(shape._element)
    new_shape=slide.shapes.add_table(nrows,cols,left,top,width,height);new_shape.name=f'VIZ::{title}'
    table=new_shape.table
    for c,h in enumerate(headers): table.cell(0,c).text=_display(h)
    for r,row in enumerate(rows,1):
        for c in range(cols): table.cell(r,c).text=_display(row[c] if c<len(row) else None)
    for r in range(nrows):
        for c in range(cols):
            for p in table.cell(r,c).text_frame.paragraphs:p.font.size=Pt(9);p.font.bold=(r==0)
    return new_shape


def _apply_semantics(slide: Any, before_count: int, entries: list[Mapping[str, Any]], plan: Mapping[str, Any], asset_data_url: Any=None, continuations: list[dict[str, Any]] | None=None) -> None:
    created=[slide.shapes[i] for i in range(before_count,len(slide.shapes))]
    # adapter emits one top-level shape per plan item; replacement tables are processed from the correlated originals.
    if len(created)<len(entries): raise RuntimeError('frozen PowerPoint adapter created fewer shapes than planned')
    for index,(entry,item) in enumerate(zip(entries,plan['items'])):
        shape=created[index];kind=item['kind'];title=item['title']
        if kind=='image': shape=_replace_image(slide,shape,entry,title,asset_data_url)
        elif kind=='diagram': shape=_replace_diagram(slide,shape,entry,title,continuations)
        elif kind=='wafer_map': shape=_replace_wafer_map(slide,shape,entry,title,difference=False)
        elif kind=='wafer_difference': shape=_replace_wafer_map(slide,shape,entry,title,difference=True)
        elif kind=='timeline': _fill_text_shape(shape,entry,title)
        elif kind=='kpi': _fill_kpi(shape,entry,title)
        elif kind=='chart': _fill_chart(shape,entry,title)
        elif kind=='table': shape=_replace_table(slide,shape,entry,title)
        elif kind=='fallback': _fill_text_shape(shape,{**entry,'detail':f'Controlled fallback · {entry.get("element") or "specialized visual"} remains semantic metadata; recreate this visual natively in Visembler.'},title)
        else: _fill_text_shape(shape,entry,title)
        _set_semantic_metadata(shape,entry)


def export_pptx(template_bytes: bytes | None, model: Mapping[str, Any], *, slide_index: int = 0, placeholder: str = 'VISUALIZER_CONTENT', asset_data_url: Any=None, layout_geometry: Mapping[str, Any] | None=None) -> bytes:
    """Export the authored report into an optional template or a clean blank deck."""
    if template_bytes is None:
        prs=Presentation()
        prs.slides.add_slide(prs.slide_layouts[6])
    else:
        validate_pptx_bytes(template_bytes)
        prs=Presentation(io.BytesIO(template_bytes))
    if slide_index < 0 or slide_index >= len(prs.slides): raise ValueError('PPT slide index is out of range')
    try: semantic_model=canonical_model(model)
    except VisualizerContractError: semantic_model=None
    if semantic_model is not None and asset_data_url:
        semantic_model=json.loads(stable_json(semantic_model))
        for entry in semantic_model['items']:
            if entry.get('engine')=='ImageMediaEngine' and entry.get('asset_id'):
                entry['src']=asset_data_url(entry['asset_id']); entry.pop('asset_id',None)
    entries=bound_export_items(semantic_model or model)
    layout_geometry=_validated_layout_geometry(layout_geometry,entries)
    if layout_geometry is not None:
        geometry={rect['id']:rect for rect in layout_geometry['items']}
        entries=[{**entry,**geometry[str(entry['id'])]} for entry in entries]
    if template_bytes is None: _set_blank_report_slide_size(prs,layout_geometry)
    for entry in entries:
        if str(entry.get('engine') or '')!='MetricEngine':
            continue
        issues=metric_format_issues(entry,entry.get('_metric_field'))
        if issues:
            raise VisualizerContractError('; '.join(issues))
    adapter=_adapter()
    continuations=[]
    pages=_export_pages(entries)
    for page_index,page_entries in enumerate(pages):
        slide=prs.slides[slide_index] if page_index==0 else prs.slides.add_slide(prs.slide_layouts[6]); target_slide_index=slide_index if page_index==0 else len(prs.slides)-1
        selected_placeholder=placeholder if page_index==0 else None
        target=adapter.target_region(prs,slide,placeholder=selected_placeholder)
        plan=_plan({**(semantic_model or model),'items':page_entries},layout_geometry,target_width=Inches(target['width']),target_height=Inches(target['height'])); before_count=len(slide.shapes)
        adapter.insert(prs,slide_index=target_slide_index,placeholder=selected_placeholder,plan=plan)
        _apply_semantics(slide,before_count,page_entries,plan,asset_data_url,continuations)
        if page_index==0 and semantic_model is not None: _set_report_metadata(slide,semantic_model)
    _export_diagram_continuations(prs,continuations)
    output=io.BytesIO(); prs.save(output); payload=output.getvalue(); validate_pptx_bytes(payload); return payload


def import_visembler_pptx(payload: bytes) -> dict[str, Any] | None:
    """Rebuild a report only from exact exported metadata; never infer from ordinary shapes."""
    validate_pptx_bytes(payload)
    prs=Presentation(io.BytesIO(payload)); items=[]; seen=set(); report_context=None
    for slide in prs.slides:
        for shape in slide.shapes:
            descriptions=[]
            try: descriptions=[node.get('descr') for node in shape._element.xpath('.//p:cNvPr')]
            except Exception: descriptions=[]
            for description in descriptions:
                if isinstance(description,str) and description.startswith('VisualizerSemanticReport:'):
                    if report_context is not None: raise VisualizerContractError('semantic PowerPoint contains multiple report payloads')
                    encoded=description.removeprefix('VisualizerSemanticReport:')
                    if len(encoded.encode('utf-8'))>MODEL_MAX_BYTES: raise VisualizerContractError('semantic PowerPoint payload exceeds model limit')
                    try: report_context=json.loads(encoded,parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('non-finite value')))
                    except (json.JSONDecodeError,ValueError) as exc: raise VisualizerContractError('malformed Visembler report payload') from exc
                    if not isinstance(report_context,Mapping): raise VisualizerContractError('semantic Visembler report payload must be an object')
                    continue
                if not isinstance(description,str) or not description.startswith('VisualizerSemantic:'): continue
                encoded=description.removeprefix('VisualizerSemantic:')
                if len(encoded.encode('utf-8'))>MODEL_MAX_BYTES: raise VisualizerContractError('semantic PowerPoint payload exceeds model limit')
                try: entry=json.loads(encoded,parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('non-finite value')))
                except (json.JSONDecodeError,ValueError) as exc: raise VisualizerContractError('malformed VisualizerSemantic payload') from exc
                if not isinstance(entry,Mapping): raise VisualizerContractError('semantic PowerPoint payload must be an object')
                entry=dict(entry); entry_id=str(entry.get('id') or '')
                if not entry_id or entry_id in seen: raise VisualizerContractError('semantic PowerPoint contains duplicate or missing element ids')
                # Older geometry-less exports can still recover a deterministic canvas position.
                if not all(isinstance(entry.get(key),(int,float)) for key in ('x','y','w','h')):
                    entry.update({'x':shape.left/prs.slide_width*1200,'y':shape.top/prs.slide_height*675,'w':shape.width/prs.slide_width*1200,'h':shape.height/prs.slide_height*675})
                seen.add(entry_id);items.append(entry)
    if not items:
        if report_context is not None: raise VisualizerContractError('semantic Visembler report is missing element payloads')
        return None
    for entry in items:
        if entry.get('engine')!='ImageMediaEngine' or not entry.get('src'): continue
        src=entry.get('src')
        if not isinstance(src,str) or ';base64,' not in src: raise VisualizerContractError('semantic PowerPoint image must be an embedded PNG, JPEG, or WebP')
        prefix,encoded=src.split(',',1)
        if prefix not in {'data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'}: raise VisualizerContractError('semantic PowerPoint image format is unsupported')
        try: validate_image_bytes(base64.b64decode(encoded,validate=True))
        except (ValueError,binascii.Error,VisualizerContractError) as exc: raise VisualizerContractError('semantic PowerPoint image is invalid') from exc
    # Element metadata preserves the bound export projection, not its source dataset.
    # Drop dangling links so imported elements stay canonical and immediately editable.
    for entry in items:
        if entry.pop('dataset_id',None) is not None: entry.pop('mapping',None)
    next_ids=[int(str(item['id'])[1:])+1 for item in items if str(item['id']).startswith('c') and str(item['id'])[1:].isdigit()]
    model=canonical_model({'items':items,'nextId':max([1,*next_ids])}) if report_context is None else canonical_model(report_context)
    if report_context is not None and {str(item.get('id')) for item in model['items']} != seen:
        raise VisualizerContractError('semantic Visembler report element payloads do not match report context')
    if len(stable_json(model).encode('utf-8'))>MODEL_MAX_BYTES: raise VisualizerContractError('semantic PowerPoint report exceeds model limit')
    return model
