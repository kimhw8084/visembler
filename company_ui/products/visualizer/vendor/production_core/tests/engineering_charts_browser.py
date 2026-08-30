#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROD=Path(__file__).resolve().parents[1]
DIMS={'xs':(330,230),'s':(440,280),'m':(600,350),'l':(760,430),'xl':(980,540)}
spc=[10.1,9.9,10.0,10.2,10.1,10.0,10.3,10.2,10.1,10.0,10.8,10.9]
subgroups=[[50+g*.08+i*.03+((g+i)%3)*.02 for i in range(5)] for g in range(9)]
doe=[]
for A in [-1,1]:
  for B in [-1,1]:
    for r in range(3): doe.append({'A':A,'B':B,'y':80+7*A+3*B+5*A*B+r*.4})
surface=[]
for x in [-2,-1,0,1,2]:
  for y in [-2,-1,0,1,2]: surface.append({'x':x,'y':y,'z':70+4*x-2*y+1.2*x*x+.8*y*y+2*x*y})
features=[[i/3,(i%5)-2] for i in range(20)]
response=[8+2*a-1.5*b+((i%3)-1)*.25 for i,(a,b) in enumerate(features)]
FIXTURES={
  'spc':({'values':spc},{'center':10,'sigma':.2,'lsl':9.2,'usl':10.8}),
  'imr':({'values':spc},{}),'xbarr':({'subgroups':subgroups},{}),
  'cusum':({'values':spc},{'target':10,'sigma':.2,'k':.5,'h':4}),
  'ewma':({'values':spc},{'target':10,'sigma':.2,'lambda':.25,'L':3}),
  'doe_main':({'rows':doe,'factors':['A','B'],'response':'y'},{}),
  'doe_interaction':({'rows':doe,'factorA':'A','factorB':'B','response':'y'},{}),
  'surface':({'rows':surface,'x1':'x','x2':'y','response':'z'},{'gridX':14,'gridY':10}),
  'contour':({'rows':surface,'x1':'x','x2':'y','response':'z'},{'gridX':14,'gridY':10}),
  'residual':({'features':features,'response':response},{}),'predicted':({'features':features,'response':response},{}),
  'ci':({'groups':[{'label':'Control','values':[10,11,9,10,10.5,9.5,10.2]},{'label':'Affected','values':[12,13,11.5,12.4,13.1,11.9,12.2]}]},{'confidence':.95}),
  'errorbar':({'groups':[{'label':'A','value':10,'lower':8.5,'upper':11.5},{'label':'B','value':14,'lower':12,'upper':15},{'label':'C','value':9,'lower':8,'upper':10.5}]},{}),
}

def js_bundle():
  stats=(PROD/'core/statistics_engine.mjs').read_text().replace('export class ','class ').replace('export function ','function ')
  eng=(PROD/'core/engineering_chart_engine.mjs').read_text()
  eng=re.sub(r"import\s*\{.*?\}\s*from\s*'\./statistics_engine\.mjs';",'',eng,flags=re.S)
  eng=eng.replace('export const ','const ').replace('export function ','function ')
  return stats+'\n'+eng+'\nwindow.__ENG__={ENGINEERING_CHART_TYPES,prepareEngineeringChart,renderEngineeringChartSvg};'

def html_shell(theme='light'):
  tokens=(PROD/'app/tokens.css').read_text(); css=(PROD/'app/chart_engine.css').read_text().replace("@import url('./tokens.css');",'')
  return f'''<!doctype html><html data-theme="{theme}"><head><meta charset="utf-8"><style>{tokens}\n{css}
  *{{box-sizing:border-box}}body{{margin:0;padding:28px;background:var(--viz-surface-2);color:var(--viz-ink);font-family:var(--viz-font-ui)}}#grid{{display:grid;grid-template-columns:repeat(2,max-content);gap:22px;align-items:start}}
  .card{{background:var(--viz-surface);border:1px solid var(--viz-line);border-radius:var(--viz-r-4);padding:14px;box-shadow:var(--viz-shadow-1)}}.head{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:8px;gap:12px}}.head b{{font-size:var(--viz-type-title)}}.head span{{font-size:var(--viz-type-chrome);color:var(--viz-muted)}}.chartbox{{overflow:hidden;border-radius:var(--viz-r-3);background:var(--viz-surface)}}
  </style></head><body><div id="grid"></div><script>{js_bundle()}</script></body></html>'''

report={'pass':False,'console_errors':[],'sizes':{}}
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
  for size,(w,h) in DIMS.items():
    page=browser.new_page(viewport={'width':max(900,2*w+120),'height':900}); errs=[]
    page.on('console',lambda m,errs=errs: errs.append(f'console {m.type}: {m.text}') if m.type=='error' else None)
    page.on('pageerror',lambda e,errs=errs: errs.append(f'pageerror: {e}'))
    page.set_content(html_shell(),wait_until='load')
    page.evaluate("""({fixtures,w,h,size})=>{const A=window.__ENG__,grid=document.getElementById('grid');for(const type of A.ENGINEERING_CHART_TYPES){const [input,options]=fixtures[type],plan=A.prepareEngineeringChart(type,input,options);const card=document.createElement('section');card.className='card';card.innerHTML=`<div class="head"><b>${type}</b><span>${size.toUpperCase()} · ${w}×${h}</span></div><div class="chartbox" style="width:${w}px;height:${h}px">${A.renderEngineeringChartSvg(plan,{width:w,height:h})}</div>`;grid.appendChild(card);}}""",{'fixtures':FIXTURES,'w':w,'h':h,'size':size})
    page.wait_for_timeout(60)
    metrics=page.evaluate("""({w,h})=>{const charts=[...document.querySelectorAll('.viz-engineering-chart')];return{count:charts.length,bad:charts.filter(s=>/NaN|undefined|Infinity/.test(s.outerHTML)).length,wrong:charts.filter(s=>{const r=s.getBoundingClientRect();return Math.abs(r.width-w)>.5||Math.abs(r.height-h)>.5}).length,titles:charts.filter(s=>!s.querySelector('title')||!s.getAttribute('aria-label')).length};}""",{'w':w,'h':h})
    shot=PROD/'qa'/f'engineering_charts_{size}.png';page.screenshot(path=str(shot),full_page=True)
    report['sizes'][size]={'width':w,'height':h,**metrics,'console_errors':errs,'screenshot':shot.name};report['console_errors'] += [f'{size}: {e}' for e in errs];page.close()
  browser.close()
report['pass']=not report['console_errors'] and all(v['count']==13 and v['bad']==0 and v['wrong']==0 and v['titles']==0 for v in report['sizes'].values())
(PROD/'qa/engineering_charts_browser.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
