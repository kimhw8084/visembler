#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROD=Path(__file__).resolve().parents[1]
DIMS={'xs':(330,230),'s':(440,280),'m':(600,350),'l':(760,430),'xl':(980,540)}
FIXTURES={
'histogram':{'values':[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
'box':{'values':[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
'violin':{'values':[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
'ecdf':{'values':[4,2,3,5,5,7,8,8,9,10,12]},
'regression':{'x':[1,2,3,4,5,6,7,8],'y':[2.3,4.2,5.8,8.1,9.7,12.4,13.8,16.1]},
'bubble':{'x':[1,2,3,4,5],'y':[8,5,9,4,7],'size':[10,45,22,70,35],'labels':['Etch','CVD','CMP','Litho','Diffusion']},
'stacked100':{'categories':['Q1','Q2','Q3','Q4'],'series':[{'name':'Pass','values':[72,80,76,84]},{'name':'Review','values':[18,12,16,10]},{'name':'Fail','values':[10,8,8,6]}]},
'stackedArea':{'categories':['Jan','Feb','Mar','Apr','May'],'series':[{'name':'A','values':[20,24,22,30,34]},{'name':'B','values':[12,15,19,18,22]},{'name':'C','values':[8,10,13,15,17]}]},
'step':{'x':[1,2,3,4,5],'y':[10,14,13,18,21]},
'treemap':{'nodes':[{'id':'a','label':'Etch','value':42},{'id':'b','label':'CVD','value':35},{'id':'c','label':'CMP','value':27},{'id':'d','label':'Litho','value':21},{'id':'e','label':'Diffusion','value':15}]},
'funnel':{'stages':['Cases','Qualified','Rooted','Verified','Closed'],'values':[120,88,61,42,37]},
'sankey':{'nodes':[{'id':'fdc','label':'FDC'},{'id':'spc','label':'SPC'},{'id':'norm','label':'Normalize'},{'id':'reason','label':'Reason'},{'id':'close','label':'Close'}],'links':[{'source':'fdc','target':'norm','value':50},{'source':'spc','target':'norm','value':35},{'source':'norm','target':'reason','value':70},{'source':'reason','target':'close','value':62}]},
}

def js_bundle():
    stats=(PROD/'core/statistics_engine.mjs').read_text()
    stats=stats.replace('export class ','class ').replace('export function ','function ')
    graph=(PROD/'core/graph_semantics_engine.mjs').read_text()
    graph=graph.replace('export class ','class ').replace('export const ','const ').replace('export function ','function ')
    graph='const __GRAPH__=(()=>{'+graph+';return {GraphContractError,validateGraph};})();\nconst {GraphContractError,validateGraph}=__GRAPH__;'
    advanced=(PROD/'core/advanced_chart_engine.mjs').read_text()
    advanced=re.sub(r"import\s*\{.*?\}\s*from\s*'\./(?:statistics_engine|graph_semantics_engine)\.mjs';",'',advanced,flags=re.S)
    advanced=advanced.replace('export const ','const ').replace('export function ','function ')
    return stats+'\n'+graph+'\n'+advanced+'\nwindow.__ADV_CHART__={ADVANCED_CHART_TYPES,prepareAdvancedChart,renderAdvancedChartSvg};'

def html_shell():
    tokens=(PROD/'app/tokens.css').read_text()
    css=(PROD/'app/chart_engine.css').read_text().replace("@import url('./tokens.css');",'')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{tokens}\n{css}
    *{{box-sizing:border-box}}body{{margin:0;padding:28px;background:var(--viz-surface-2);color:var(--viz-ink);font-family:var(--viz-font-ui)}}
    #grid{{display:grid;grid-template-columns:repeat(2,max-content);gap:22px;align-items:start}}
    .card{{background:var(--viz-surface);border:1px solid var(--viz-line);border-radius:var(--viz-r-4);padding:14px;box-shadow:var(--viz-shadow-1)}}
    .head{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:8px;gap:12px}}.head b{{font-size:var(--viz-type-title)}}.head span{{font-size:var(--viz-type-chrome);color:var(--viz-muted)}}
    .chartbox{{overflow:hidden;border-radius:var(--viz-r-3);background:var(--viz-surface)}}
    </style></head><body><div id="grid"></div><script>{js_bundle()}</script></body></html>'''

report={'pass':False,'console_errors':[],'sizes':{}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
    for size,(w,h) in DIMS.items():
        page=browser.new_page(viewport={'width':max(900,2*w+120),'height':900})
        errs=[]
        page.on('console',lambda m,errs=errs: errs.append(f'console {m.type}: {m.text}') if m.type=='error' else None)
        page.on('pageerror',lambda e,errs=errs: errs.append(f'pageerror: {e}'))
        page.set_content(html_shell(),wait_until='load')
        page.evaluate("""({fixtures,w,h,size})=>{
          const A=window.__ADV_CHART__,grid=document.getElementById('grid');
          for(const type of A.ADVANCED_CHART_TYPES){
            const plan=A.prepareAdvancedChart(type,fixtures[type]);
            const card=document.createElement('section');card.className='card';
            card.innerHTML=`<div class="head"><b>${type}</b><span>${size.toUpperCase()} · ${w}×${h}</span></div><div class="chartbox" style="width:${w}px;height:${h}px">${A.renderAdvancedChartSvg(plan,{width:w,height:h,title:type})}</div>`;
            grid.appendChild(card);
          }
        }""",{'fixtures':FIXTURES,'w':w,'h':h,'size':size})
        page.wait_for_timeout(80)
        metrics=page.evaluate("""({w,h})=>{
          const charts=[...document.querySelectorAll('.viz-advanced-chart')];
          return {count:charts.length,bad:charts.filter(s=>/NaN|undefined|Infinity/.test(s.outerHTML)).length,
            wrong:charts.filter(s=>{const r=s.getBoundingClientRect();return Math.abs(r.width-w)>.5||Math.abs(r.height-h)>.5}).length,
            titles:charts.filter(s=>!s.querySelector('title')||!s.getAttribute('aria-label')).length};
        }""",{'w':w,'h':h})
        shot=PROD/'qa'/f'advanced_charts_{size}.png'
        page.screenshot(path=str(shot),full_page=True)
        report['sizes'][size]={'width':w,'height':h,**metrics,'console_errors':errs,'screenshot':shot.name}
        report['console_errors'].extend([f'{size}: {x}' for x in errs])
        page.close()
    browser.close()

report['pass']=not report['console_errors'] and all(v['count']==12 and v['bad']==0 and v['wrong']==0 and v['titles']==0 for v in report['sizes'].values())
(PROD/'qa/advanced_charts_browser.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['pass'] else 1)
