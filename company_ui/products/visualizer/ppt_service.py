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
from pptx.chart.data import ChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from PIL import Image

from .files import validate_image_bytes, validate_pptx_bytes
from .domain import MODEL_MAX_BYTES, VisualizerContractError, canonical_model, stable_json
from .metric_format import format_metric_value, metric_format_issues

_VENDOR_ADAPTER = Path(__file__).with_name('vendor') / 'production_core' / 'tools' / 'ppt_template_adapter.py'
_MAX_ITEMS_PER_SLIDE = 12
_CHART_PALETTE = ('1769D1', '2E8B72', 'B7791F', '9B4DCA', 'C94F5F', '3B82A0', '6F7C38', 'D36C2E')


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


def _chart_export_spec(entry: Mapping[str, Any], dataset: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Project canonical chart data and Chart Studio intent before export flattening."""
    studio = entry.get('chart_studio') if isinstance(entry.get('chart_studio'), Mapping) else {}
    source = dataset if isinstance(dataset, Mapping) and isinstance(dataset.get('fields'), list) else None
    if source is None and isinstance(studio.get('dataset'), Mapping): source = studio['dataset']
    fields = [field for field in (source.get('fields') or []) if isinstance(field, Mapping)] if source else []
    rows = [list(row) for row in (source.get('rows') or []) if isinstance(row, Sequence) and not isinstance(row, (str, bytes))] if source else []
    mapping = {**(studio.get('mapping') if isinstance(studio.get('mapping'), Mapping) else {}),
               **(entry.get('mapping') if isinstance(entry.get('mapping'), Mapping) else {})}
    chart_type = str(studio.get('chart_type') or entry.get('chart_type') or entry.get('element') or '')
    if chart_type == 'Bar Chart': chart_type = 'Vertical Bar'
    axis_set = studio.get('axes') if isinstance(studio.get('axes'), Mapping) else {}
    axis_set = {**(entry.get('axes') if isinstance(entry.get('axes'), Mapping) else {}), **axis_set}
    y_axis = axis_set.get('y') if isinstance(axis_set.get('y'), Mapping) else {}
    default_zero = 'Bar' in chart_type or chart_type == 'Pareto'
    axis = {
        'role': 'y', 'min': y_axis.get('min'), 'max': y_axis.get('max'),
        'auto': y_axis.get('auto', True) is not False,
        'zeroBaseline': y_axis.get('zeroBaseline', default_zero) is True,
        'scale': str(y_axis.get('scale') or 'linear'), 'format': y_axis.get('format'),
        'unit': y_axis.get('unit'), 'prefix': y_axis.get('prefix'), 'suffix': y_axis.get('suffix'),
        'precision': y_axis.get('precision'), 'title': y_axis.get('title'), 'grid': y_axis.get('grid'),
    }
    legend_src = studio.get('legend') if isinstance(studio.get('legend'), Mapping) else {}
    legend_src = {**(entry.get('legend') if isinstance(entry.get('legend'), Mapping) else {}), **legend_src}
    visual_src = studio.get('visual') if isinstance(studio.get('visual'), Mapping) else {}
    visual_src = {**(entry.get('visual') if isinstance(entry.get('visual'), Mapping) else {}), **visual_src}
    declared_series = entry.get('series') if isinstance(entry.get('series'), list) else studio.get('series')
    declared_series = declared_series if isinstance(declared_series, list) else []
    statistical = entry.get('statistical_chart') if isinstance(entry.get('statistical_chart'), Mapping) else None

    def field_index(role: str) -> int:
        field_id = mapping.get(role)
        return next((i for i, field in enumerate(fields) if field.get('id') == field_id), -1)

    def finite(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

    def typed(value: Any) -> str:
        return str(value if value is not None else '')

    if statistical:
        categories = [str(value) for value in statistical.get('categories') or []]
        series = []
        for item in statistical.get('series') or []:
            if not isinstance(item, Mapping): continue
            values = list(item.get('values') or [])
            series.append({'key': str(item.get('name') or entry.get('title') or 'Series'),
                           'name': str(item.get('name') or entry.get('title') or 'Series'),
                           'field': None, 'axis': 'primary', 'visible': True, 'legend': True,
                           'values': (values + [None] * len(categories))[:len(categories)]})
        return {'type': chart_type, 'categories': categories, 'series': series, 'axis': axis,
                'legend': {'show': legend_src.get('show', len(series) > 1), 'position': legend_src.get('position', 'bottom')},
                'x_field': None, 'x_role': None, 'y_field': None, 'axis_source': y_axis,
                'visual': visual_src,
                'source': 'statistical_chart'}

    if source and rows:
        if chart_type == 'Box Plot':
            category = next((field_index(role) for role in ('category', 'cohort', 'status', 'series') if field_index(role) >= 0), -1)
            value = next((field_index(role) for role in ('value', 'y') if field_index(role) >= 0), -1)
            groups: dict[str, list[float]] = {}
            for row in rows:
                observed = row[value] if 0 <= value < len(row) else None
                if not finite(observed): continue
                key = typed(row[category] if 0 <= category < len(row) else 'All')
                groups.setdefault(key, []).append(float(observed))
            categories = list(groups)
            value_field=fields[value] if 0 <= value < len(fields) else None
            return {'type': chart_type, 'categories': categories,
                    'groups': [{'key': key, 'name': key, 'values': groups[key], 'axis': 'primary', 'visible': True}
                               for key in categories], 'axis': axis,
                    'legend': {'show': False, 'position': 'bottom'}, 'x_field': None,
                    'x_role': 'category', 'y_field': value_field, 'axis_source': y_axis,
                    'visual': visual_src,
                    'source': 'bound_dataset'}

        if chart_type == 'Histogram':
            value_index=field_index('value') if field_index('value') >= 0 else field_index('y')
            observed=[float(row[value_index]) for row in rows if 0 <= value_index < len(row) and finite(row[value_index])]
            if not observed:
                low,high,bins=0.0,1.0,1
            else:
                configured=visual_src.get('bins')
                bins=max(3,min(40,int(configured))) if isinstance(configured,int) and not isinstance(configured,bool) else min(16,max(6,math.ceil(math.sqrt(len(observed)))))
                low,high=min(observed),max(observed)
                if low==high:
                    padding=max(1.0,abs(low)*.05);low-=padding;high+=padding
            step=(high-low)/bins;counts=[0]*bins
            for value in observed:
                bucket=min(bins-1,max(0,math.floor((value-low)/max(1e-12,step))))
                counts[bucket]+=1
            edges=[low+step*index for index in range(bins+1)]
            labels=[f'{edges[index]:.12g}–{edges[index+1]:.12g}' for index in range(bins)]
            value_field=fields[value_index] if 0 <= value_index < len(fields) else None
            return {'type': chart_type, 'categories': labels,
                    'series': [{'key': 'Count', 'name': 'Count', 'field': None, 'axis': 'primary',
                                'visible': True, 'legend': False, 'values': counts, 'points': []}],
                    'axis': axis, 'legend': {'show': False, 'position': 'bottom'}, 'x_field': value_field,
                    'x_role': 'value', 'y_field': None, 'axis_source': y_axis, 'visual': visual_src,
                    'source': 'bound_dataset_histogram'}

        if chart_type in {'Scatter Plot', 'Regression Scatter'}:
            x_role = 'x'; x_index = field_index('x')
        elif chart_type in {'Vertical Bar', 'Horizontal Bar', 'Pareto', 'DOE Main Effects'}:
            x_role = 'category' if field_index('category') >= 0 else 'x'; x_index = field_index(x_role)
        else:
            x_role = next((role for role in ('x', 'category', 'time', 'label') if field_index(role) >= 0), 'x')
            x_index = field_index(x_role)
        value_roles = [role for role in ('y', 'value', 'secondaryY') if field_index(role) >= 0]
        group_index = field_index('series') if field_index('series') >= 0 else field_index('color')
        x_values = [row[x_index] if 0 <= x_index < len(row) else None for row in rows]
        categories = list(dict.fromkeys(typed(value) for value in x_values))
        x_field = next((field for field in fields if x_index >= 0 and field.get('id') == fields[x_index].get('id')), None)
        if x_field and (x_field.get('type') in {'number', 'integer'} or 'time' in (x_field.get('semantic_tags') or [])):
            categories.sort(key=lambda value: (0, float(value)) if value not in ('', 'None') and _is_finite_number(value) else (1, value))

        series_meta: list[dict[str, Any]] = []
        point_y_index = field_index('y') if field_index('y') >= 0 else field_index('value')
        if group_index >= 0:
            keys = list(dict.fromkeys(typed(row[group_index] if group_index < len(row) else None) for row in rows))
            by_key = {str(spec.get('key', spec.get('name', spec.get('label', '')))): spec
                      for spec in declared_series if isinstance(spec, Mapping)}
            ordered = [key for spec in declared_series if isinstance(spec, Mapping)
                       for key in [str(spec.get('key', spec.get('name', spec.get('label', ''))))] if key in keys]
            ordered.extend(key for key in keys if key not in ordered)
            for key in ordered:
                spec = by_key.get(key, {})
                series_meta.append({'key': key, 'name': str(spec.get('label') or spec.get('name') or key),
                                    'field': mapping.get('y') or mapping.get('value'),
                                    'axis': 'secondary' if spec.get('axis') == 'secondary' else 'primary',
                                    'visible': spec.get('visible') is not False, 'legend': spec.get('legend') is not False,
                                    'color': spec.get('color') or _CHART_PALETTE[len(series_meta)%len(_CHART_PALETTE)],
                                    '_group_index': group_index})
            order = str(legend_src.get('order') or 'input')
            if order == 'label-asc': series_meta.sort(key=lambda item: item['name'].casefold())
            elif order == 'label-desc': series_meta.sort(key=lambda item: item['name'].casefold(), reverse=True)
            elif order == 'value-desc':
                value_index = field_index('y') if field_index('y') >= 0 else field_index('value')
                totals = {}
                for item in series_meta:
                    totals[item['key']] = sum(float(row[value_index]) for row in rows
                                               if value_index >= 0 and value_index < len(row)
                                               and item['_group_index'] < len(row)
                                               and typed(row[item['_group_index']]) == item['key']
                                               and finite(row[value_index]))
                series_meta.sort(key=lambda item: totals.get(item['key'], 0), reverse=True)
        else:
            field_roles = []
            for spec in declared_series:
                if not isinstance(spec, Mapping): continue
                field_id = spec.get('field')
                if field_id and any(field.get('id') == field_id for field in fields): field_roles.append((str(field_id), spec))
            if not field_roles:
                for role in value_roles:
                    field_id = mapping.get(role)
                    if field_id and not any(existing[0] == str(field_id) for existing in field_roles): field_roles.append((str(field_id), {}))
            for field_id, spec in field_roles:
                field_at = next((i for i, field in enumerate(fields) if field.get('id') == field_id), -1)
                field_name = str(next((field.get('name') for field in fields if field.get('id') == field_id), field_id))
                series_meta.append({'key': str(spec.get('key') or field_id), 'name': str(spec.get('label') or spec.get('name') or field_name),
                                    'field': field_id, 'axis': 'secondary' if spec.get('axis') == 'secondary' or field_id == mapping.get('secondaryY') else 'primary',
                                    'visible': spec.get('visible') is not False, 'legend': spec.get('legend') is not False,
                                    'color': spec.get('color') or _CHART_PALETTE[len(series_meta)%len(_CHART_PALETTE)],
                                    '_value_index': field_at})
        for series in series_meta:
            values = [None] * len(categories)
            category_at = {category: i for i, category in enumerate(categories)}
            scatter_points=[]
            for row_index, row in enumerate(rows):
                category_key = typed(row[x_index] if 0 <= x_index < len(row) else None)
                if series.get('_group_index') is not None:
                    if series['key'] != typed(row[series['_group_index']] if series['_group_index'] < len(row) else None): continue
                    value_index = point_y_index
                else: value_index = int(series.get('_value_index', -1))
                value = row[value_index] if 0 <= value_index < len(row) else None
                x_value=row[x_index] if 0 <= x_index < len(row) else None
                if chart_type in {'Scatter Plot','Regression Scatter'} and finite(x_value) and finite(value):
                    scatter_points.append({'x':float(x_value),'y':float(value)})
                if category_key in category_at: values[category_at[category_key]] = float(value) if finite(value) else None
            series['values'] = values
            series['points'] = scatter_points if chart_type in {'Scatter Plot','Regression Scatter'} else []
        y_field=fields[point_y_index] if 0 <= point_y_index < len(fields) else None
        return {'type': chart_type, 'categories': categories, 'series': series_meta, 'axis': axis,
                'legend': {'show': legend_src.get('show', len(series_meta) > 1), 'position': legend_src.get('position', 'bottom')},
                'x_field': x_field, 'x_role': x_role, 'y_field': y_field, 'axis_source': y_axis,
                'visual': visual_src,
                'source': 'bound_dataset'}

    chart_rows = _chart_rows(entry)
    categories = list(dict.fromkeys(label for label, _ in chart_rows))
    value_by_category = {label: value for label, value in chart_rows}
    series = [{'key': 'Value', 'name': str(entry.get('title') or 'Value'), 'field': None, 'axis': 'primary',
               'visible': True, 'legend': True, 'values': [value_by_category.get(label) for label in categories],
               'points': [{'x': label, 'y': value_by_category.get(label)} for label in categories]}]
    return {'type': chart_type, 'categories': categories, 'series': series, 'axis': axis,
            'legend': {'show': legend_src.get('show', False), 'position': legend_src.get('position', 'bottom')},
            'x_field': None, 'x_role': None, 'y_field': None, 'axis_source': y_axis,
            'visual': visual_src,
            'source': 'legacy_rows'}


def _is_finite_number(value: Any) -> bool:
    try: return not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError): return False


def bound_export_items(model: Mapping[str, Any], *, _include_chart_specs: bool = False) -> list[dict[str, Any]]:
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
        if _include_chart_specs and _kind(entry) == 'chart':
            entry['_pptx_chart_spec'] = _chart_export_spec(entry, dataset)
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
            label=index('category') if index('category')>=0 else (index('label') if index('label')>=0 else (index('time') if index('time')>=0 else index('x')))
            trend_visual=engine=='CoreChartEngine' and str(entry.get('element') or '') in {'Line Chart','Multi-Line','Area Chart','Scatter Plot','Regression Scatter'}
            value=index('y') if trend_visual and index('y')>=0 else (index('value') if index('value')>=0 else index('y'))
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
        def normalized_size(value: float, target: int | None, canvas_scale: float, canvas_size: float) -> float:
            if not target:
                return max(.001, min(1.0, value / canvas_size))
            # The frozen adapter converts normalized inches to EMU by truncating.
            # Center the fraction in the intended EMU so fractional CSS pixels
            # export to the same nearest-EMU geometry as the report canvas.
            emu = min(target, max(1, round(value * canvas_scale)))
            return max(.001, min(1.0, (emu + .5) / target))

        return {'items':[{'kind':_kind(entry),'title':str(entry.get('title') or entry.get('element') or _kind(entry))[:100],
                          'nx':max(0.0,min(1.0,(offset_x+float(entry['x'])*scale)/target_width)) if target_width else max(0.0,min(1.0,float(entry['x'])/canvas_w)),
                          'ny':max(0.0,min(1.0,(offset_y+float(entry['y'])*scale)/target_height)) if target_height else max(0.0,min(1.0,float(entry['y'])/canvas_h)),
                          'nw':normalized_size(float(entry['w']), target_width, scale, canvas_w),
                          'nh':normalized_size(float(entry['h']), target_height, scale, canvas_h)} for entry in report_items]}
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


_REPORT_TEXT_BACKGROUND = (255,255,255)
_REPORT_TEXT_STYLES = {
    'text_heading': {'size':10.5,'minimum':9.5,'bold':True,'color':(28,43,62),'alignment':PP_ALIGN.CENTER,'line_spacing':1.0,'space_after':0.0},
    'report_headline': {'size':17.5,'minimum':13.0,'bold':True,'color':(23,43,67),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.5},
    'context_subhead': {'size':10.5,'minimum':8.0,'family':'Arial Narrow','bold':False,'color':(55,74,96),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.0},
    'metric_title': {'size':10.5,'minimum':9.5,'bold':True,'color':(55,74,96),'alignment':PP_ALIGN.CENTER,'line_spacing':1.0,'space_after':0.5},
    'metric_value': {'size':24.0,'minimum':15.0,'bold':True,'color':(23,50,78),'alignment':PP_ALIGN.CENTER,'line_spacing':1.0,'space_after':0.5},
    'comparison_value': {'size':20.0,'minimum':14.0,'bold':True,'color':(23,50,78),'alignment':PP_ALIGN.CENTER,'line_spacing':1.0,'space_after':0.5},
    'narrative_interpretation': {'size':11.5,'minimum':9.5,'bold':False,'color':(37,54,73),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.5},
    'evidence_detail': {'size':10.5,'minimum':9.5,'bold':False,'color':(55,72,92),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.5},
    'risk_decision': {'size':11.0,'minimum':9.5,'bold':True,'color':(104,43,49),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.5},
    'action_status': {'size':10.5,'minimum':9.5,'bold':True,'color':(43,79,67),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.0},
    'conclusion_next_step': {'size':12.5,'minimum':10.0,'bold':True,'color':(23,50,78),'alignment':PP_ALIGN.LEFT,'line_spacing':1.0,'space_after':0.5},
}
_REPORT_TEXT_MARGIN_LEFT = Inches(.03)
_REPORT_TEXT_MARGIN_RIGHT = Inches(.03)
_REPORT_TEXT_MARGIN_TOP = Inches(0)
_REPORT_TEXT_MARGIN_BOTTOM = Inches(0)
# PowerPoint and LibreOffice shape text with font-specific glyph widths and
# natural leading that can exceed a character-count estimate. Reserve room for
# both so editable text does not rely on renderer-specific clipping behavior.
_REPORT_TEXT_WIDTH_SAFETY_FACTOR = 1.15
_REPORT_TEXT_LINE_HEIGHT_FACTOR = 1.2


def _report_text_role(entry: Mapping[str, Any]) -> str:
    description=' '.join(str(entry.get(key) or '') for key in ('element','title','type')).casefold().replace('_',' ').replace('-',' ')
    if any(token in description for token in ('executive statement','hero title','report headline','headline')): return 'report_headline'
    if any(token in description for token in ('key takeaway','next step','conclusion','recommendation')): return 'conclusion_next_step'
    if any(token in description for token in ('risk','decision','release gate')): return 'risk_decision'
    if any(token in description for token in ('evidence','detail','finding','supporting data')): return 'evidence_detail'
    if any(token in description for token in ('context','subhead','objective','scope')): return 'context_subhead'
    if any(token in description for token in ('action','status','containment','owner','corrective action')): return 'action_status'
    body=str(entry.get('text') or entry.get('body') or '')
    if 'body narrative' in description and body.count(' · ')>=2: return 'context_subhead'
    return 'narrative_interpretation'


def _report_text_segments(entry: Mapping[str, Any], title: str) -> list[tuple[str,str]]:
    engine=str(entry.get('engine') or '')
    segments=[(title,'text_heading')]
    if engine in {'EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'}:
        entry_role=_report_text_role(entry)
        statement=str(entry.get('statement') or '')
        statement_lower=statement.casefold().strip()
        decision_language=('contain','hold ','release ','do not','stop ','reserve ','block ')
        next_step_language=('complete ','verify ','run ','confirm ','review ','update ','schedule ','implement ','document ','prepare ')
        if engine=='ProjectCompositeEngine':
            if any(statement_lower.startswith(token) for token in decision_language): entry_role='risk_decision'
            elif any(statement_lower.startswith(token) for token in next_step_language): entry_role='conclusion_next_step'
        statement_role=entry_role if engine in {'DecisionCompositeEngine','ProjectCompositeEngine'} else 'narrative_interpretation'
        if engine=='DecisionCompositeEngine' and statement_role=='conclusion_next_step': detail_role='risk_decision'
        elif engine=='ProjectCompositeEngine' and statement_role=='risk_decision': detail_role='conclusion_next_step'
        else: detail_role='evidence_detail'
        segments.extend((str(entry[key]),role) for key,role in (
            ('statement',statement_role),('detail',detail_role),('status','action_status')
        ) if entry.get(key) not in (None,''))
        return segments
    if engine=='ImageMediaEngine':
        body='\n'.join(str(entry[key]) for key in ('caption','alt') if entry.get(key) not in (None,''))
    else:
        body=_semantic_text(entry)
    if body:
        role=_report_text_role(entry)
        if engine=='TimelineEngine': role='action_status'
        segments.append((body,role))
    return segments


def _estimated_character_width(character: str, size: float, font_family: str='Arial') -> float:
    if character in ' il.,:;!|\'`': factor=.28
    elif character in 'MW@%&': factor=.88
    elif character.isspace(): factor=.29
    elif character in 'frt()[]{}-_/': factor=.36
    elif character.isupper(): factor=.62
    elif character.isdigit(): factor=.55
    else: factor=.51
    condensed=.8 if font_family=='Arial Narrow' else 1.0
    return size*factor*condensed


def _estimated_lines(text: str, size: float, available_width: float, font_family: str='Arial') -> int:
    lines=0
    for hard_line in text.split('\n') or ['']:
        current=0.0; line_count=1
        for word in hard_line.split(' '):
            word_width=sum(_estimated_character_width(character,size,font_family) for character in word)
            if current and current+size*.29+word_width>available_width:
                line_count+=1;current=word_width
            elif word_width>available_width:
                line_count+=max(0,math.ceil(word_width/available_width)-1);current=word_width%available_width
            else:
                current+=(size*.29 if current else 0)+word_width
        lines+=line_count
    return max(1,lines)


def _apply_report_text_authority(shape: Any, segments: Sequence[tuple[str,str]]) -> None:
    """Give every exported report text frame deterministic, high-contrast formatting."""
    frame=shape.text_frame
    frame.clear()
    frame.word_wrap=True
    frame.auto_size=MSO_AUTO_SIZE.NONE
    frame.margin_left=_REPORT_TEXT_MARGIN_LEFT
    frame.margin_right=_REPORT_TEXT_MARGIN_RIGHT
    frame.margin_top=_REPORT_TEXT_MARGIN_TOP
    frame.margin_bottom=_REPORT_TEXT_MARGIN_BOTTOM
    frame.vertical_anchor=MSO_ANCHOR.TOP
    shape.fill.solid()
    shape.fill.fore_color.rgb=RGBColor(*_REPORT_TEXT_BACKGROUND)

    specs=[(str(text),role,_REPORT_TEXT_STYLES[role]) for text,role in segments]
    usable_width=max(1.0,(shape.width/12700-(_REPORT_TEXT_MARGIN_LEFT+_REPORT_TEXT_MARGIN_RIGHT)/12700)/_REPORT_TEXT_WIDTH_SAFETY_FACTOR)
    usable_height=max(1.0,shape.height/12700-(_REPORT_TEXT_MARGIN_TOP+_REPORT_TEXT_MARGIN_BOTTOM)/12700)
    groupings=[[(index,) for index in range(len(specs))]]
    if len(specs)>1 and specs[0][1]=='text_heading':
        compact=[(0,1)]
        remaining=list(range(2,len(specs)))
        if len(remaining)>1 and specs[remaining[-1]][1]=='action_status':
            remaining[-2:]=[(remaining[-2],remaining[-1])]
        compact.extend((index,) if isinstance(index,int) else index for index in remaining)
        groupings.append(compact)

    selected_scale=None;selected_families=[];selected_groups=[]
    for groups in groupings:
        for step in range(21):
            scale=1.0-step*.025
            for use_condensed in (False,True):
                families=[];total_height=0.0
                for group in groups:
                    texts=[];group_sizes=[];group_spacing=[];group_after=[];group_roles=[];group_family='Arial'
                    for position,index in enumerate(group):
                        text,role,style=specs[index]
                        if position: texts.append(' · ')
                        texts.append(text);group_roles.append(role)
                        group_sizes.append(max(style['minimum'],round(style['size']*scale*2)/2))
                        group_spacing.append(style['line_spacing']);group_after.append(style['space_after'])
                        family=style.get('family','Arial')
                        if use_condensed and role in {'report_headline','narrative_interpretation','evidence_detail'} and family=='Arial': family='Arial Narrow'
                        families.append((index,family))
                        if family=='Arial Narrow': group_family='Arial Narrow'
                    content_sizes=[group_sizes[position] for position,index in enumerate(group) if specs[index][1]!='text_heading']
                    measure_size=max(content_sizes or group_sizes)
                    text=''.join(texts)
                    total_height+=_estimated_lines(text,measure_size,usable_width,group_family)*measure_size*max(group_spacing)*_REPORT_TEXT_LINE_HEIGHT_FACTOR+max(group_after)
                if total_height<=usable_height:
                    selected_scale=scale;selected_families=[family for _,family in sorted(families)];selected_groups=groups;break
            if selected_scale is not None: break
        if selected_scale is not None: break
    if selected_scale is None:
        raise VisualizerContractError(f'PowerPoint report text for {shape.name} exceeds its assigned element rectangle at minimum readable font sizes.')

    roles=[]
    for group_index,group in enumerate(selected_groups):
        first_style=specs[group[0]][2]
        paragraph_style=next((specs[index][2] for index in group if specs[index][1]!='text_heading'),first_style)
        paragraph=frame.paragraphs[0] if group_index==0 else frame.add_paragraph()
        paragraph.alignment=paragraph_style['alignment']
        paragraph.line_spacing=max(specs[index][2]['line_spacing'] for index in group)
        paragraph.space_before=Pt(0)
        paragraph.space_after=Pt(max(specs[index][2]['space_after'] for index in group))
        for position,index in enumerate(group):
            text,role,style=specs[index]
            if len(group)==1:
                paragraph.text=text
                runs=paragraph.runs
            else:
                run=paragraph.add_run()
                run.text=(' · ' if position else '')+text
                runs=[run]
            size=max(style['minimum'],round(style['size']*selected_scale*2)/2)
            for run in runs:
                run.font.name=selected_families[index]
                run.font.size=Pt(size)
                run.font.bold=style['bold']
                run.font.italic=False
                run.font.color.rgb=RGBColor(*style['color'])
            roles.append(role)
    nodes=shape._element.xpath('.//p:cNvPr')
    if nodes:
        labels=', '.join(dict.fromkeys(role.replace('_',' ') for role in roles))
        nodes[0].set('title',f'Visembler report text roles: {labels}')


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
    _apply_report_text_authority(shape,_report_text_segments(entry,title))


def _fill_kpi(shape: Any, entry: Mapping[str, Any], title: str) -> None:
    if not getattr(shape,'has_text_frame',False): return
    value=entry.get('value')
    if value is None and str(entry.get('engine') or '')=='ComparisonEngine':
        before=format_metric_value(entry.get('before'),entry,entry.get('_metric_field'))
        after=format_metric_value(entry.get('after'),entry,entry.get('_metric_field'))
        value=f'{before} → {after}'
    label=f"{title} · {entry.get('metric_label')}" if entry.get('metric_label') else title
    rendered=format_metric_value(value,entry,entry.get('_metric_field')) if str(entry.get('engine') or '')=='MetricEngine' else _display(value)
    segments=[(label,'metric_title'),(rendered,'comparison_value' if str(entry.get('engine') or '')=='ComparisonEngine' else 'metric_value')]
    unit=str(entry.get('unit') or '')
    if unit and str(entry.get('engine') or '') not in {'MetricEngine','ComparisonEngine'}:
        segments.append((unit,'comparison_value' if str(entry.get('engine') or '')=='ComparisonEngine' else 'metric_value'))
    if entry.get('detail'):
        segments.append((str(entry['detail']),'evidence_detail'))
    _apply_report_text_authority(shape,segments)


def _chart_domain(axis: Mapping[str, Any], values: Sequence[Any]) -> tuple[float, float] | None:
    numbers=[float(value) for value in values if _is_finite_number(value)]
    if not numbers: return None
    data_min,data_max=min(numbers),max(numbers)
    span=data_max-data_min
    padding=span*.05 if span else max(abs(data_min)*.05,1.0)
    auto_min,auto_max=data_min-padding,data_max+padding
    if axis.get('zeroBaseline') is True:
        if data_min>=0: auto_min=0.0
        if data_max<=0: auto_max=0.0
        auto_min=min(0.0,auto_min); auto_max=max(0.0,auto_max)
    if axis.get('auto') is False:
        source_min,source_max=axis.get('min'),axis.get('max')
        lower=float(source_min) if _is_finite_number(source_min) else auto_min
        upper=float(source_max) if _is_finite_number(source_max) else auto_max
        valid=lower<upper and lower<=data_min and upper>=data_max
        if valid: return lower,upper
    return auto_min,auto_max


def _chart_number_format(spec: Mapping[str, Any]) -> str | None:
    axis=spec.get('axis') if isinstance(spec.get('axis'),Mapping) else {}
    source_format=axis.get('format')
    if isinstance(source_format,str) and source_format not in {'', 'auto', 'number', 'currency', 'percent'}:
        return source_format
    field=spec.get('y_field') if isinstance(spec.get('y_field'),Mapping) else {}
    field_format=field.get('format') if isinstance(field.get('format'),Mapping) else {}
    unit=str(axis.get('unit') or field.get('unit') or '')
    precision=axis.get('precision')
    decimals=max(0,min(8,int(precision))) if isinstance(precision,int) and not isinstance(precision,bool) else 1
    pattern='#,##0'+('.'+'0'*decimals if decimals else '')
    if source_format=='percent' or field_format.get('kind')=='percent':
        return pattern+'%' if field_format.get('percent_scale')=='ratio' or source_format=='percent' else pattern+'"%"'
    if source_format=='currency': pattern='$'+pattern
    elif axis.get('prefix'): pattern=f'"{str(axis["prefix"]).replace(chr(34), chr(34)*2)}"'+pattern
    suffix=str(axis.get('suffix') or '')
    if unit: suffix=f' {unit}'+suffix
    if suffix: pattern+=f'"{suffix.replace(chr(34), chr(34)*2)}"'
    return pattern if (precision is not None or source_format=='currency' or unit or axis.get('prefix') or axis.get('suffix')) else None


def _native_chart_type(spec: Mapping[str, Any]) -> Any:
    chart_type=str(spec.get('type') or '')
    if chart_type in {'Line Chart','Multi-Line','SPC Control Chart'}:
        visual=spec.get('visual') if isinstance(spec.get('visual'),Mapping) else {}
        markers=visual.get('markers',True)
        return XL_CHART_TYPE.LINE_MARKERS if markers is not False else XL_CHART_TYPE.LINE
    if chart_type=='Xbar-R Chart' and spec.get('source')=='statistical_chart':
        return XL_CHART_TYPE.LINE_MARKERS
    if chart_type=='DOE Interaction Plot' and spec.get('source')=='statistical_chart':
        return XL_CHART_TYPE.LINE_MARKERS
    if chart_type=='DOE Main Effects' and spec.get('source')=='statistical_chart':
        return XL_CHART_TYPE.COLUMN_CLUSTERED
    if chart_type in {'Vertical Bar','Histogram'}: return XL_CHART_TYPE.COLUMN_CLUSTERED
    if chart_type=='Horizontal Bar': return XL_CHART_TYPE.BAR_CLUSTERED
    if chart_type=='Area Chart': return XL_CHART_TYPE.AREA
    if chart_type in {'Scatter Plot','Regression Scatter'}: return XL_CHART_TYPE.XY_SCATTER
    return None


def _reorder_replacement_shapes(slide: Any, placeholder: Any, replacements: Sequence[Any]) -> Any:
    parent=placeholder._element.getparent();position=parent.index(placeholder._element)
    nodes=[replacement._element for replacement in replacements]
    for chart_node in placeholder._element.xpath('.//c:chart'):
        relationship_id=chart_node.get(qn('r:id'))
        if relationship_id and relationship_id in slide.part.rels:
            slide.part.drop_rel(relationship_id)
    parent.remove(placeholder._element)
    for node in nodes: parent.remove(node)
    for offset,node in enumerate(nodes): parent.insert(position+offset,node)
    return replacements[0]


def _replace_native_chart(slide: Any, placeholder: Any, spec: Mapping[str, Any], title: str) -> Any:
    visible=[series for series in spec.get('series') or [] if isinstance(series,Mapping) and series.get('visible') is not False]
    if not visible: raise VisualizerContractError('PowerPoint chart export requires at least one visible series.')
    if any(series.get('axis')=='secondary' for series in visible):
        raise VisualizerContractError(f"PowerPoint export does not support a secondary value axis for {spec.get('type') or 'chart'}.")
    chart_type=_native_chart_type(spec)
    if chart_type is None:
        raise VisualizerContractError(f"PowerPoint export does not support chart family {spec.get('type') or '(unspecified)'}.")
    left,top,width,height=placeholder.left,placeholder.top,placeholder.width,placeholder.height
    categories=[str(value) for value in spec.get('categories') or []]
    if chart_type==XL_CHART_TYPE.XY_SCATTER:
        data=XyChartData()
        for series in visible:
            exported=data.add_series(str(series.get('name') or series.get('key') or title))
            for point in series.get('points') or []:
                if isinstance(point,Mapping) and _is_finite_number(point.get('x')) and _is_finite_number(point.get('y')):
                    exported.add_data_point(float(point['x']),float(point['y']))
    else:
        data=ChartData();data.categories=categories or ['Value']
        for series in visible:
            values=list(series.get('values') or [])
            values=(values+[None]*len(data.categories))[:len(data.categories)]
            data.add_series(str(series.get('name') or series.get('key') or title),
                            [float(value) if _is_finite_number(value) else None for value in values])
    chart_shape=slide.shapes.add_chart(chart_type,left,top,width,height,data)
    chart_shape.name=f'VIZ::{title}'
    chart=chart_shape.chart;chart.has_title=True;chart.chart_title.text_frame.text=title
    if chart_type==XL_CHART_TYPE.XY_SCATTER:
        scatter_style=chart.plots[0]._element.xpath('./c:scatterStyle')
        if scatter_style: scatter_style[0].set('val','marker')
    legend=spec.get('legend') if isinstance(spec.get('legend'),Mapping) else {}
    chart.has_legend=legend.get('show') is not False and any(series.get('legend') is not False for series in visible)
    if chart.has_legend:
        positions={'top':XL_LEGEND_POSITION.TOP,'bottom':XL_LEGEND_POSITION.BOTTOM,
                   'left':XL_LEGEND_POSITION.LEFT,'right':XL_LEGEND_POSITION.RIGHT}
        chart.legend.position=positions.get(str(legend.get('position') or 'bottom'),XL_LEGEND_POSITION.BOTTOM)
        legend_element=chart.legend._element
        insertion=1 if legend_element.find(qn('c:legendPos')) is not None else 0
        for index,series_spec in enumerate(visible):
            if series_spec.get('legend') is False:
                legend_entry=OxmlElement('c:legendEntry');series_index=OxmlElement('c:idx');series_index.set('val',str(index))
                delete=OxmlElement('c:delete');delete.set('val','1');legend_entry.append(series_index);legend_entry.append(delete)
                legend_element.insert(insertion,legend_entry);insertion+=1
    for index,(series,series_spec) in enumerate(zip(chart.series,visible)):
        color=str(series_spec.get('color') or _CHART_PALETTE[index%len(_CHART_PALETTE)]).lstrip('#')
        if len(color)!=6 or any(char not in '0123456789abcdefABCDEF' for char in color): continue
        rgb=RGBColor.from_string(color)
        if chart_type==XL_CHART_TYPE.XY_SCATTER:
            series.marker.style=XL_MARKER_STYLE.CIRCLE;series.marker.size=5
            series.marker.format.fill.solid();series.marker.format.fill.fore_color.rgb=rgb
        elif chart_type in {XL_CHART_TYPE.BAR_CLUSTERED,XL_CHART_TYPE.COLUMN_CLUSTERED}:
            series.format.fill.solid();series.format.fill.fore_color.rgb=rgb
        else:
            series.format.line.color.rgb=rgb
    axis=spec.get('axis') if isinstance(spec.get('axis'),Mapping) else {}
    values=[value for series in visible
            for value in (series.get('values') or [])]
    if chart_type==XL_CHART_TYPE.XY_SCATTER:
        values=[point.get('y') for series in visible for point in series.get('points') or [] if isinstance(point,Mapping)]
    domain=_chart_domain(axis,values)
    if domain is not None:
        chart.value_axis.minimum_scale,chart.value_axis.maximum_scale=domain
    number_format=_chart_number_format(spec)
    if number_format: chart.value_axis.tick_labels.number_format=number_format
    if axis.get('title'):
        chart.value_axis.has_title=True;chart.value_axis.axis_title.text_frame.text=str(axis['title'])
    y_axis=spec.get('axis_source') if isinstance(spec.get('axis_source'),Mapping) else {}
    if y_axis.get('grid') is False: chart.value_axis.has_major_gridlines=False
    return _reorder_replacement_shapes(slide,placeholder,[chart_shape])


def _box_plot_stats(values: Sequence[float]) -> dict[str, float | int]:
    ordered=sorted(float(value) for value in values)
    def quantile(fraction: float) -> float:
        position=(len(ordered)-1)*fraction;low=math.floor(position);high=math.ceil(position)
        return ordered[low]+(ordered[high]-ordered[low])*(position-low)
    return {'n':len(ordered),'min':ordered[0],'q1':quantile(.25),'median':quantile(.5),
            'q3':quantile(.75),'max':ordered[-1]}


def _box_plot_label(value: float, spec: Mapping[str, Any]) -> str:
    axis=spec.get('axis') if isinstance(spec.get('axis'),Mapping) else {}
    precision=axis.get('precision')
    if isinstance(precision,int) and not isinstance(precision,bool): result=f'{value:.{max(0,min(8,precision))}f}'
    else: result=str(int(value)) if value.is_integer() else f'{value:.4f}'.rstrip('0').rstrip('.')
    unit=str(axis.get('unit') or '')
    suffix=str(axis.get('suffix') or '')
    return f"{axis.get('prefix') or ''}{result}{(' '+unit) if unit else ''}{suffix}"


def _draw_box_plot(slide: Any, placeholder: Any, entry: Mapping[str, Any], spec: Mapping[str, Any], title: str) -> Any:
    groups=[group for group in spec.get('groups') or [] if isinstance(group,Mapping) and group.get('values')]
    if not groups: raise VisualizerContractError('PowerPoint Box Plot export requires numeric values in at least one cohort.')
    all_values=[value for group in groups for value in group['values'] if _is_finite_number(value)]
    domain=_chart_domain(spec.get('axis') or {},all_values)
    if domain is None: raise VisualizerContractError('PowerPoint Box Plot export requires a finite value-axis domain.')
    left,top,width,height=placeholder.left,placeholder.top,placeholder.width,placeholder.height
    plot_left=left+int(width*.19);plot_right=left+int(width*.97)
    plot_top=top+int(height*.20);plot_bottom=top+int(height*.75)
    low,high=domain
    y_at=lambda value: plot_bottom-round((float(value)-low)/(high-low)*(plot_bottom-plot_top))
    created=[]
    title_shape=slide.shapes.add_textbox(left+int(width*.04),top+int(height*.015),int(width*.92),int(height*.15))
    title_shape.name=f"VIZ::{entry.get('id','chart')}::box-plot-title";title_shape.text_frame.text=title
    title_shape.text_frame.word_wrap=False
    for paragraph in title_shape.text_frame.paragraphs:
        paragraph.font.size=Pt(12);paragraph.font.bold=True
    created.append(title_shape)
    for tick in range(5):
        value=low+(high-low)*tick/4;y=y_at(value)
        line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,plot_left,y,plot_right,y)
        line.name=f"VIZ::{entry.get('id','chart')}::box-plot-grid-{tick}";line.line.color.rgb=RGBColor(220,226,234);line.line.width=Pt(.6);created.append(line)
        label=slide.shapes.add_textbox(left, y-int(Pt(5)), plot_left-left-int(width*.025), Pt(12))
        label.name=f"VIZ::{entry.get('id','chart')}::box-plot-axis-{tick}";label.text_frame.text=_box_plot_label(value,spec)
        label.text_frame.word_wrap=False;label.text_frame.paragraphs[0].alignment=PP_ALIGN.RIGHT;label.text_frame.paragraphs[0].font.size=Pt(7)
        created.append(label)
    for index,group in enumerate(groups):
        color=RGBColor.from_string(_CHART_PALETTE[index%len(_CHART_PALETTE)])
        stats=_box_plot_stats(group['values']);center=plot_left+(index+.5)*(plot_right-plot_left)/len(groups)
        half=min(int((plot_right-plot_left)/max(1,len(groups))*.20),int(Inches(.28)))
        whisker=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,center,y_at(stats['max']),center,y_at(stats['min']))
        whisker.name=f"VIZ::{entry.get('id','chart')}::box-plot-{index}-whisker";whisker.line.color.rgb=color;whisker.line.width=Pt(1.4);created.append(whisker)
        for cap,value_key in enumerate(('min','max')):
            y=y_at(stats[value_key]);line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,center-half,y,center+half,y)
            line.name=f"VIZ::{entry.get('id','chart')}::box-plot-{index}-whisker-cap-{cap}";line.line.color.rgb=color;line.line.width=Pt(1.4);created.append(line)
        box_top,box_bottom=y_at(stats['q3']),y_at(stats['q1'])
        box=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,center-half,box_top,half*2,max(Pt(1),box_bottom-box_top))
        box.name=f"VIZ::{entry.get('id','chart')}::box-plot-{index}-quartiles";box.fill.solid();box.fill.fore_color.rgb=color;box.fill.transparency=68;box.line.color.rgb=color;box.line.width=Pt(1.2);created.append(box)
        median_y=y_at(stats['median']);median=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,center-half,median_y,center+half,median_y)
        median.name=f"VIZ::{entry.get('id','chart')}::box-plot-{index}-median";median.line.color.rgb=RGBColor(35,45,60);median.line.width=Pt(2);created.append(median)
        category=slide.shapes.add_textbox(center-int(Inches(.6)),plot_bottom+int(height*.045),int(Inches(1.2)),int(height*.13))
        category.name=f"VIZ::{entry.get('id','chart')}::box-plot-{index}-category";category.text_frame.text=str(group.get('name') or group.get('key') or 'All')
        category.text_frame.word_wrap=True;category.text_frame.paragraphs[0].alignment=PP_ALIGN.CENTER;category.text_frame.paragraphs[0].font.size=Pt(8)
        nodes=category._element.xpath('.//p:cNvPr')
        if nodes: nodes[0].set('title',json.dumps({'category':group.get('key'),'quartiles':stats},ensure_ascii=False,separators=(',',':')))
        created.append(category)
    anchor=_reorder_replacement_shapes(slide,placeholder,created)
    return anchor


def _fill_chart(slide: Any, shape: Any, entry: Mapping[str, Any], title: str) -> Any:
    spec=entry.get('_pptx_chart_spec') if isinstance(entry.get('_pptx_chart_spec'),Mapping) else _chart_export_spec(entry)
    if spec.get('type')=='Box Plot': return _draw_box_plot(slide,shape,entry,spec,title)
    return _replace_native_chart(slide,shape,spec,title)


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
        elif kind=='chart': shape=_fill_chart(slide,shape,entry,title)
        elif kind=='table': shape=_replace_table(slide,shape,entry,title)
        elif kind=='fallback': _fill_text_shape(shape,{**entry,'detail':f'Controlled fallback · {entry.get("element") or "specialized visual"} remains semantic metadata; recreate this visual natively in Visembler.'},title)
        else: _fill_text_shape(shape,entry,title)
        _set_semantic_metadata(shape,{key:value for key,value in entry.items() if key!='_pptx_chart_spec'})


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
    entries=bound_export_items(semantic_model or model,_include_chart_specs=True)
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
