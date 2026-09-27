from __future__ import annotations
import hashlib, json, posixpath, re, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path('/Users/haewonkim/.codex-fabric/evidence/visembler/CHG-173-r5-run10')
REPORTS=ROOT/'reports'
OUT=REPORTS/'pptx-inspection.json'
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','rel':'http://schemas.openxmlformats.org/package/2006/relationships'}

def text_nodes(node,selector):
    return [x.text or '' for x in node.findall(selector,NS)]

def local_name(tag):
    return tag.split('}',1)[-1]

def cache_values(parent):
    if parent is None:return {'formula':None,'kind':None,'values':[]}
    refs=parent.find('c:strRef',NS) or parent.find('c:numRef',NS)
    lit=parent.find('c:strLit',NS) or parent.find('c:numLit',NS)
    holder=refs or lit
    if holder is None:return {'formula':None,'kind':None,'values':[]}
    cache=holder.find('c:strCache',NS) or holder.find('c:numCache',NS) or holder.find('c:multiLvlStrCache',NS) or holder
    values=[]
    for point in cache.findall('.//c:pt',NS):
        val=point.find('c:v',NS)
        if val is not None:values.append({'idx':point.get('idx'),'v':val.text})
    formula=holder.find('c:f',NS)
    return {'formula':formula.text if formula is not None else None,'kind':local_name(cache.tag),'ptCount':len(values),'values':values}

def series_info(ser):
    tx=ser.find('c:tx',NS)
    name=cache_values(tx) if tx is not None else None
    if name and name['values']:
        name_value=' '.join(x['v'] for x in name['values'])
    else:
        name_value=None
    order=ser.find('c:order',NS)
    cat=ser.find('c:cat',NS)
    val=ser.find('c:val',NS)
    xval=ser.find('c:xVal',NS)
    yval=ser.find('c:yVal',NS)
    return {'order':order.get('val') if order is not None else None,'name':name_value,'name_cache':name,'category_cache':cache_values(cat),'value_cache':cache_values(val or yval),'x_cache':cache_values(xval),'y_cache':cache_values(yval),'series_color':(ser.find('c:spPr/a:solidFill/a:srgbClr',NS).get('val') if ser.find('c:spPr/a:solidFill/a:srgbClr',NS) is not None else None)}

def axis_info(ax):
    scaling=ax.find('c:scaling',NS)
    axis_title=ax.find('c:title',NS)
    tick_skip=ax.find('c:tickLblSkip',NS);mark_skip=ax.find('c:tickMarkSkip',NS)
    txpr=ax.find('c:txPr',NS)
    body=txpr.find('.//a:bodyPr',NS) if txpr is not None else None
    sizes=[]
    if txpr is not None:
        for n in txpr.findall('.//a:defRPr',NS)+txpr.findall('.//a:rPr',NS):
            if n.get('sz'):sizes.append(int(n.get('sz'))/100)
    return {'kind':local_name(ax.tag),'id':(ax.find('c:axId',NS).get('val') if ax.find('c:axId',NS) is not None else None),'title':' '.join(text_nodes(axis_title,'.//a:t')) if axis_title is not None else None,'min':scaling.find('c:min',NS).get('val') if scaling is not None and scaling.find('c:min',NS) is not None else None,'max':scaling.find('c:max',NS).get('val') if scaling is not None and scaling.find('c:max',NS) is not None else None,'tick_label_interval':tick_skip.get('val') if tick_skip is not None else None,'tick_mark_interval':mark_skip.get('val') if mark_skip is not None else None,'tick_label_rotation_degrees':(int(body.get('rot'))/60000 if body is not None and body.get('rot') else None),'tick_font_points':sizes,'num_fmt':(ax.find('c:numFmt',NS).get('formatCode') if ax.find('c:numFmt',NS) is not None else None)}

def shape_info(slide):
    out=[]
    tree=slide.find('.//p:spTree',NS)
    if tree is None:return out
    for kind in ('sp','graphicFrame','grpSp','cxnSp'):
        for shape in tree.findall(f'p:{kind}',NS):
            nv=shape.find(f'p:nv{kind[0].upper()+kind[1:]}/p:cNvPr',NS)
            if nv is None:
                nv=shape.find('.//p:cNvPr',NS)
            xfrm=shape.find('p:spPr/a:xfrm',NS) or shape.find('p:xfrm',NS)
            off=xfrm.find('a:off',NS) if xfrm is not None else None
            ext=xfrm.find('a:ext',NS) if xfrm is not None else None
            paras=[''.join((t.text or '') for t in para.findall('.//a:t',NS)) for para in shape.findall('p:txBody/a:p',NS)]
            rpr=[]
            for node in shape.findall('.//a:rPr',NS)+shape.findall('.//a:defRPr',NS):
                if node.get('sz'):rpr.append(int(node.get('sz'))/100)
            out.append({'kind':kind,'name':nv.get('name') if nv is not None else None,'descr':nv.get('descr') if nv is not None else None,'text':'\n'.join(x for x in paras if x),'font_points':sorted(set(rpr)),'geometry_emu':{'x':float(off.get('x')) if off is not None else None,'y':float(off.get('y')) if off is not None else None,'cx':float(ext.get('cx')) if ext is not None else None,'cy':float(ext.get('cy')) if ext is not None else None}})
    return out

def inspect(path,row):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); slides=sorted((n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml$',n).group(1)))
        charts=sorted((n for n in names if re.fullmatch(r'ppt/charts/chart\d+\.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml$',n).group(1)))
        charts_out=[];slide_out=[]
        for spath in slides:
            sx=ET.fromstring(z.read(spath));rels_path=posixpath.join(posixpath.dirname(spath),'_rels',posixpath.basename(spath)+'.rels');relmap={}
            if rels_path in names:
                rx=ET.fromstring(z.read(rels_path))
                relmap={r.get('Id'):posixpath.normpath(posixpath.join(posixpath.dirname(spath),r.get('Target'))) for r in rx}
            sshape=shape_info(sx); chart_refs=[]
            for gf in sx.findall('.//p:graphicFrame',NS):
                rid=gf.find('.//c:chart',NS)
                if rid is not None:chart_refs.append({'shape':next((s for s in sshape if s['kind']=='graphicFrame' and s['name']==(gf.find('.//p:cNvPr',NS).get('name') if gf.find('.//p:cNvPr',NS) is not None else None)),None),'part':relmap.get(rid.get('{%s}id'%NS['r']))})
            slide_out.append({'slide':spath,'texts':[s['text'] for s in sshape if s['text']],'shapes':sshape,'chart_refs':chart_refs})
        for cpath in charts:
            cx=ET.fromstring(z.read(cpath));pa=cx.find('.//c:plotArea',NS)
            plot=[local_name(x.tag) for x in list(pa)] if pa is not None else []
            all_ser=[]
            if pa is not None:
                for family in list(pa):
                    all_ser.extend(series_info(s) for s in family.findall('c:ser',NS))
            legend=cx.find('.//c:legend',NS);legend_tx=legend.find('c:txPr',NS) if legend is not None else None
            lfonts=[]
            if legend_tx is not None:
                for n in legend_tx.findall('.//a:defRPr',NS)+legend_tx.findall('.//a:rPr',NS):
                    if n.get('sz'):lfonts.append(int(n.get('sz'))/100)
            title=cx.find('.//c:title',NS)
            axes=[]
            if pa is not None:
                for ax in list(pa):
                    if local_name(ax.tag) in ('catAx','dateAx','valAx','serAx'):
                        axes.append(axis_info(ax))
            charts_out.append({'part':cpath,'plot_families':plot,'chart_title':' '.join(text_nodes(title,'.//a:t')) if title is not None else None,'series_count':len(all_ser),'series':all_ser,'axes':axes,'legend':{'present':legend is not None,'position':(legend.find('c:legendPos',NS).get('val') if legend is not None and legend.find('c:legendPos',NS) is not None else None),'overlay':(legend.find('c:overlay',NS).get('val') if legend is not None and legend.find('c:overlay',NS) is not None else None),'font_points':sorted(set(lfonts))},'ext_uris':[e.get('uri') for e in cx.findall('.//c:ext',NS)]})
        core={}
        if 'docProps/core.xml' in names:
            corexml=ET.fromstring(z.read('docProps/core.xml'))
            core={local_name(x.tag):(x.text or '') for x in list(corexml)}
        model_path=ROOT/'run-owned-data'/'reports'/f"{row['report_id']}.json"
        source=json.loads(model_path.read_text())['model'] if model_path.exists() else None
        chart_items=[];box_items=[]
        if source:
            for item in source.get('items',[]):
                if item.get('engine')=='CoreChartEngine':
                    ds=next((d for d in source.get('datasets',[]) if d.get('id')==item.get('dataset_id')),None)
                    cs=item.get('chart_studio') or {}
                    chart_items.append({'id':item.get('id'),'element':item.get('element'),'title':item.get('title'),'view_type':item.get('view_type'),'dataset_id':item.get('dataset_id'),'mapping':item.get('mapping'),'dataset_revision':ds.get('revision') if ds else None,'fields':ds.get('fields') if ds else None,'row_count':len(ds.get('rows',[])) if ds else None,'series':cs.get('series'),'axes':cs.get('axes'),'legend':cs.get('legend'),'semantic_stats':cs.get('statistical_result')})
                    if item.get('element')=='Box Plot' or item.get('view_type')=='box':box_items.append(item)
        shape_matches=[]
        for item in box_items:
            title=item.get('title') or '';id_=str(item.get('id'))
            matches=[]
            for slide in slide_out:
                for shape in slide['shapes']:
                    if id_ in str(shape.get('name') or '') or (title and title.lower() in str(shape.get('text') or '').lower()):matches.append({'slide':slide['slide'],'shape':shape})
            shape_matches.append({'item_id':id_,'title':title,'box_chart_parts_by_title_or_id':[c['part'] for c in charts_out if c.get('chart_title')==title or id_ in c['part']],'editable_shape_matches':matches})
        return {'report_key':row['key'],'title':row['title'],'report_id':row['report_id'],'pptx':row['pptx_path'],'bytes':path.stat().st_size,'sha256':digest,'slide_count':len(slides),'chart_parts':charts_out,'slide_parts':slide_out,'report_source_charts':chart_items,'box_plot_primitives':shape_matches,'package_metadata':core,'has_custom_xml':any(n.startswith('customXml/') for n in names),'custom_xml_parts':[n for n in names if n.startswith('customXml/')],'embedded_workbooks':[{'part':n,'bytes':len(z.read(n)),'sha256':hashlib.sha256(z.read(n)).hexdigest()} for n in names if n.startswith('ppt/embeddings/')],'package_files':sorted(names)}

run=json.loads((ROOT/'benchmark-run.json').read_text());results=[inspect(ROOT/row['pptx_path'],row) for row in run['reports'].values()]
OUT.write_text(json.dumps({'request':'CHG-173-r5','source_sha':run['source_sha'],'reports':results},indent=2,ensure_ascii=False)+'\n')
print(json.dumps([{'key':r['report_key'],'title':r['title'],'slides':r['slide_count'],'charts':[(c['part'],c['plot_families'],c['series_count'],[ax for ax in c['axes'] if ax['kind']=='valAx']) for c in r['chart_parts']],'box':[(x['title'],len(x['editable_shape_matches']),x['box_chart_parts_by_title_or_id']) for x in r['box_plot_primitives']]} for r in results],indent=2,ensure_ascii=False))
