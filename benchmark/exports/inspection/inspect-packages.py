from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','rel':'http://schemas.openxmlformats.org/package/2006/relationships'}
FILES={
 'A-executive':'/tmp/visembler-chg173-r4-benchmark-set-with-image-v3/executive-business-review.pptx',
 'B-rca':'/tmp/visembler-chg173-r4-benchmark-set-with-image-v3/semiconductor-rca.pptx',
 'C-experiment':'/tmp/visembler-chg173-r4-benchmark-set-with-image-v3/experiment-decision.pptx',
 'D-technical':'/tmp/visembler-chg173-r4-benchmark-set-with-image-v3/technical-status-review.pptx',
 'E-fresh-mixed':'/tmp/visembler-chg173-r4-fresh-mixed-v10/E-fresh-mixed-grid-reserve.pptx',
 'F-fresh-sparse':'/tmp/visembler-chg173-r4-fresh-sparse-v7/F-sparse-batch14.pptx',
}
def text_points(parent):
 if parent is None:return []
 out=[]
 for pt in parent.findall('.//c:pt',NS):
  v=pt.find('./c:v',NS)
  if v is not None:out.append((int(pt.get('idx','0')),v.text or ''))
 return [v for _,v in sorted(out)]
def series_name(s):
 tx=s.find('./c:tx',NS)
 if tx is None:return None
 v=tx.find('.//c:v',NS)
 if v is not None:return v.text
 return None
def axis(ax):
 scaling=ax.find('./c:scaling',NS)
 return {'min':scaling.find('c:min',NS).get('val') if scaling is not None and scaling.find('c:min',NS) is not None else None,'max':scaling.find('c:max',NS).get('val') if scaling is not None and scaling.find('c:max',NS) is not None else None,'crosses':ax.find('c:crosses',NS).get('val') if ax.find('c:crosses',NS) is not None else None}
def inspect(path):
 out={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'slides':[],'chart_parts':[],'semantic':[],'box_plot_primitives':[]}
 with ZipFile(path) as z:
  names=set(z.namelist()); slides=sorted([n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda x:int(re.search(r'(\d+)',x).group(1)))
  for sn in slides:
   sroot=ET.fromstring(z.read(sn)); relpath=sn.rsplit('/',1)[0]+'/_rels/'+sn.rsplit('/',1)[1]+'.rels'; relmap={}
   if relpath in names:
    rr=ET.fromstring(z.read(relpath)); relmap={n.get('Id'):n.get('Target') for n in rr.findall('rel:Relationship',NS)}
   slide={'part':sn,'shapes':[],'charts':[]}
   for nv in sroot.findall('.//p:cNvPr',NS):
    name=nv.get('name',''); descr=nv.get('descr',''); title=nv.get('title','')
    if name or descr or title:
     shape={'name':name,'descr':descr,'title':title}
     if descr.startswith('VisualizerSemanticReport:'):
      try:out['semantic'].append({'kind':'report','slide':sn,'payload':json.loads(descr.split(':',1)[1])})
      except:out['semantic'].append({'kind':'report','slide':sn,'parse_error':True})
     elif descr.startswith('VisualizerSemantic:'):
      try:out['semantic'].append({'kind':'item','slide':sn,'payload':json.loads(descr.split(':',1)[1])})
      except:out['semantic'].append({'kind':'item','slide':sn,'parse_error':True})
     if name.startswith('VIZ::') and 'box-plot-' in name:
      itemid=name.split('::')[1]
      payload=None
      if title:
       try:payload=json.loads(title)
       except:pass
      out['box_plot_primitives'].append({'slide':sn,'name':name,'item_id':itemid,'title_json':payload,'descr':descr})
     slide['shapes'].append(shape)
   for gf in sroot.findall('.//p:graphicFrame',NS):
    nv=gf.find('./p:nvGraphicFramePr/p:cNvPr',NS); chart=gf.find('.//c:chart',NS)
    if chart is None:continue
    rid=chart.get('{%s}id'%NS['r']);target=relmap.get(rid,'');part=str(Path(sn).parent/target)
    # Normalize OOXML relative reference such as ppt/slides/../charts/chart1.xml.
    from posixpath import normpath
    part=normpath(part)
    slide['charts'].append({'shape_name':nv.get('name') if nv is not None else None,'shape_descr':nv.get('descr') if nv is not None else None,'rel_id':rid,'chart_part':part})
    if part not in names:continue
    cr=ET.fromstring(z.read(part)); plots=[]
    pa=cr.find('.//c:plotArea',NS)
    if pa is not None:
     for child in list(pa):
      ln=child.tag.split('}')[-1]
      if ln.endswith('Chart'):
       series=[]
       for se in child.findall('./c:ser',NS):
        cat=se.find('./c:cat',NS); val=se.find('./c:val',NS)
        cats=text_points(cat)
        values=text_points(val)
        series.append({'name':series_name(se),'categories':cats,'values':values})
       plots.append({'family':ln,'series':series})
    chartrec={'slide':sn,'shape_name':nv.get('name') if nv is not None else None,'shape_descr':nv.get('descr') if nv is not None else None,'part':part,'plots':plots,'val_axes':[axis(a) for a in cr.findall('.//c:valAx',NS)],'cat_axes':len(cr.findall('.//c:catAx',NS)),'legend':cr.find('.//c:legend',NS) is not None,'title_text':[n.text for n in cr.findall('.//c:title//a:t',NS) if n.text]}
    out['chart_parts'].append(chartrec)
   out['slides'].append(slide)
 out['report_contexts']=[x['payload'] for x in out['semantic'] if x['kind']=='report']
 # Keep raw semantics elsewhere; report to tabulation via metrics.
 return out
reports={k:inspect(Path(v)) for k,v in FILES.items()}
out=Path('/tmp/visembler-chg173-r4-pptx-inspection-final/package-inspection.json');out.write_text(json.dumps(reports,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:{'sha256':v['sha256'],'slides':len(v['slides']),'chart_parts':len(v['chart_parts']),'charts':[{'part':c['part'],'name':c['shape_name'],'plot':[(p['family'],[(s['name'],s['categories'],s['values']) for s in p['series']]) for p in c['plots']],'axes':c['val_axes'],'legend':c['legend']} for c in v['chart_parts']],'box_primitives':len(v['box_plot_primitives']),'semantic_items':sum(x['kind']=='item' for x in v['semantic']),'report_contexts':len(v['report_contexts'])} for k,v in reports.items()},indent=2,ensure_ascii=False))
