#!/usr/bin/env python3
"""Template-independent Visualizer PPT insertion.

The existing PPTX is treated as a container. Master/theme/header/footer shapes remain
untouched. Visualizer content is added only inside a selected/named/auto-detected
middle content region. Units accepted by the JSON plan are normalized 0..1 within
that target region.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from typing import Iterable
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import ChartData
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

EMU_PER_INCH=914400

def inches(v): return v/EMU_PER_INCH

def rect(shape): return dict(x=inches(shape.left),y=inches(shape.top),width=inches(shape.width),height=inches(shape.height))
def overlap(a,b,pad=0.0): return a['x'] < b['x']+b['width']+pad and a['x']+a['width'] > b['x']-pad and a['y'] < b['y']+b['height']+pad and a['y']+a['height'] > b['y']-pad

def largest_empty_region(page, obstacles, padding=.08):
    xs=[0,page['width']];ys=[0,page['height']]
    for o in obstacles:
        xs += [max(0,o['x']-padding),min(page['width'],o['x']+o['width']+padding)]
        ys += [max(0,o['y']-padding),min(page['height'],o['y']+o['height']+padding)]
    xs=sorted(set(round(x,6) for x in xs));ys=sorted(set(round(y,6) for y in ys))
    best=None
    for i in range(len(xs)-1):
      for j in range(i+1,len(xs)):
       for k in range(len(ys)-1):
        for l in range(k+1,len(ys)):
          r={'x':xs[i],'y':ys[k],'width':xs[j]-xs[i],'height':ys[l]-ys[k]}
          if r['width']<=0 or r['height']<=0 or any(overlap(r,o,padding) for o in obstacles): continue
          area=r['width']*r['height']; cp=abs(r['x']+r['width']/2-page['width']/2)+abs(r['y']+r['height']/2-page['height']/2)
          if best is None or area>best[0]+1e-9 or (abs(area-best[0])<1e-9 and cp<best[1]): best=(area,cp,r)
    return best[2] if best else {'x':.5,'y':1.2,'width':page['width']-1,'height':page['height']-1.8}

def find_named_region(slide,name):
    target=name.strip().lower()
    for s in slide.shapes:
        if str(getattr(s,'name','')).strip().lower()==target:
            return rect(s)
        if getattr(s,'has_text_frame',False) and s.text.strip().lower()==target:
            return rect(s)
    return None

def target_region(prs,slide,region=None,placeholder=None):
    page={'width':inches(prs.slide_width),'height':inches(prs.slide_height)}
    if region:
        vals=[float(x) for x in region.split(',')]
        if len(vals)!=4: raise ValueError('region must be x,y,width,height inches')
        return dict(zip(['x','y','width','height'],vals))
    if placeholder:
        found=find_named_region(slide,placeholder)
        if found:return found
    # Treat thin top/bottom bands and edge logos as obstacles. Large central placeholders
    # are ignored unless explicitly selected, so an empty content placeholder can be used.
    obs=[]
    for s in slide.shapes:
        r=rect(s);cy=r['y']+r['height']/2
        edge = cy < page['height']*.22 or cy > page['height']*.78 or r['x'] < page['width']*.08 or r['x']+r['width'] > page['width']*.92
        if edge and r['width']*r['height']>.02: obs.append(r)
    return largest_empty_region(page,obs,.06)

def abs_rect(target,item):
    return {k: target[k]+item.get('n'+k[0],0)*target[k.replace('x','width').replace('y','height')] if k in ('x','y') else item.get('n'+k[0],1)*target[k] for k in ()}

def map_norm(target,item):
    return {'x':target['x']+float(item.get('nx',0))*target['width'],'y':target['y']+float(item.get('ny',0))*target['height'],'width':float(item.get('nw',1))*target['width'],'height':float(item.get('nh',1))*target['height']}

def text_style(tf,size=14,bold=False):
    p=tf.paragraphs[0];p.font.name='Arial';p.font.size=Pt(size);p.font.bold=bold

def add_card(slide,r,title,subtitle='Editable Visualizer object'):
    sh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(r['x']),Inches(r['y']),Inches(r['width']),Inches(r['height']))
    sh.name=f'VIZ::{title}';sh.fill.solid();sh.fill.fore_color.rgb=RGBColor(255,255,255);sh.line.color.rgb=RGBColor(220,222,226)
    tf=sh.text_frame;tf.clear();tf.margin_left=Inches(.12);tf.margin_right=Inches(.12);tf.margin_top=Inches(.09);tf.margin_bottom=Inches(.09)
    p=tf.paragraphs[0];p.text=title;p.font.name='Arial';p.font.size=Pt(max(11,min(18,r['height']*10)));p.font.bold=True;p.font.color.rgb=RGBColor(29,29,31)
    p2=tf.add_paragraph();p2.text=subtitle;p2.font.name='Arial';p2.font.size=Pt(10);p2.font.color.rgb=RGBColor(110,110,115)
    return sh

def add_kpi(slide,r,title='Yield',value='98.7%'):
    sh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(r['x']),Inches(r['y']),Inches(r['width']),Inches(r['height']))
    sh.name=f'VIZ::{title} KPI';sh.fill.solid();sh.fill.fore_color.rgb=RGBColor(255,255,255);sh.line.color.rgb=RGBColor(27,102,201);tf=sh.text_frame;tf.clear();p=tf.paragraphs[0];p.text=title;p.font.name='Arial';p.font.size=Pt(10);p.font.bold=True;p.font.color.rgb=RGBColor(110,110,115);p2=tf.add_paragraph();p2.text=value;p2.font.name='Arial';p2.font.size=Pt(max(18,min(36,r['height']*16)));p2.font.bold=True;p2.font.color.rgb=RGBColor(29,29,31);return sh

def add_native_chart(slide,r,title='Trend'):
    data=ChartData();data.categories=['W1','W2','W3','W4','W5'];data.add_series('Yield',[91.4,93.2,92.8,96.1,98.7])
    chart=slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS,Inches(r['x']),Inches(r['y']),Inches(r['width']),Inches(r['height']),data).chart
    chart.has_title=True;chart.chart_title.text_frame.text=title;chart.has_legend=False
    return chart

def add_native_table(slide,r,title='Action tracker'):
    rows,cols=4,3;shape=slide.shapes.add_table(rows,cols,Inches(r['x']),Inches(r['y']),Inches(r['width']),Inches(r['height']));shape.name=f'VIZ::{title}'
    t=shape.table;vals=[['Action','Owner','Status'],['Validate chamber','Kim','Done'],['Run split','Lee','Active'],['Verify yield','Park','Next']]
    for rr in range(rows):
      for cc in range(cols):
        t.cell(rr,cc).text=vals[rr][cc]
        for p in t.cell(rr,cc).text_frame.paragraphs:p.font.name='Arial';p.font.size=Pt(9);p.font.bold=(rr==0)
    return shape

def default_plan():
    return {'items':[
      {'kind':'text','title':'Executive summary','nx':0,'ny':0,'nw':.58,'nh':.27},
      {'kind':'kpi','title':'Hero KPI','nx':.60,'ny':0,'nw':.40,'nh':.27},
      {'kind':'chart','title':'Yield trend','nx':0,'ny':.31,'nw':.64,'nh':.49},
      {'kind':'table','title':'Action tracker','nx':.66,'ny':.31,'nw':.34,'nh':.49},
      {'kind':'text','title':'Source · production evidence · editable output','nx':0,'ny':.84,'nw':1,'nh':.16}
    ]}

def insert(prs,slide_index=0,region=None,placeholder=None,plan=None):
    slide=prs.slides[slide_index];target=target_region(prs,slide,region,placeholder);plan=plan or default_plan();added=[]
    for item in plan['items']:
        r=map_norm(target,item);kind=item.get('kind','text');title=item.get('title',kind)
        if kind=='chart': add_native_chart(slide,r,title)
        elif kind=='table': add_native_table(slide,r,title)
        elif kind=='kpi': add_kpi(slide,r,title)
        else: add_card(slide,r,title,item.get('subtitle','Editable Visualizer content'))
        added.append({'kind':kind,'title':title,**r})
    return target,added

def main():
    ap=argparse.ArgumentParser();ap.add_argument('template');ap.add_argument('output');ap.add_argument('--slide',type=int,default=1);ap.add_argument('--region',help='x,y,width,height inches');ap.add_argument('--placeholder',default='VISUALIZER_CONTENT');ap.add_argument('--plan');args=ap.parse_args()
    prs=Presentation(args.template);plan=json.loads(Path(args.plan).read_text()) if args.plan else None;target,added=insert(prs,args.slide-1,args.region,args.placeholder,plan);prs.save(args.output);print(json.dumps({'pass':True,'target':target,'added':added,'output':str(args.output)},indent=2))
if __name__=='__main__':main()
