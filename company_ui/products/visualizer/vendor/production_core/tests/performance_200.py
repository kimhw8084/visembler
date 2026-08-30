#!/usr/bin/env python3
from __future__ import annotations
import json, statistics, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROD=Path(__file__).resolve().parents[1]

def bundle_html():
    html=(PROD/'app/index.html').read_text()
    tokens=(PROD/'app/tokens.css').read_text()
    css=(PROD/'app/editor.css').read_text().replace("@import url('./tokens.css');",'')
    store=(PROD/'core/editor_store.mjs').read_text().replace('export class ','class ').replace('export function ','function ')
    app=(PROD/'app/editor.mjs').read_text()
    start=app.find('import {'); end=app.find("from '../core/editor_store.mjs';")
    app=app[:start]+app[end+len("from '../core/editor_store.mjs';"):]
    return html.replace('<link rel="stylesheet" href="./editor.css">',f'<style>{tokens}\n{css}</style>').replace('<script type="module" src="./editor.mjs"></script>',f'<script type="module">{store}\n{app}</script>')

def pct(values, q):
    values=sorted(values)
    if not values: return 0.0
    idx=min(len(values)-1, max(0, round((len(values)-1)*q)))
    return values[idx]

report={'pass':False,'budget':{'p95_ms':16.7,'max_heap_growth_mb':4.0},'console_errors':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--js-flags=--expose-gc'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.on('console', lambda m: report['console_errors'].append(f'console {m.type}: {m.text}') if m.type=='error' else None)
    page.on('pageerror', lambda e: report['console_errors'].append(f'pageerror: {e}'))
    page.set_content(bundle_html(), wait_until='load')
    page.wait_for_timeout(200)

    model={'schema_version':1,'items':[],'groups':{},'mode':'smart','layoutPreset':'editorial','crossFilter':None,'nextId':201}
    for i in range(200):
        model['items'].append({'id':f'c{i+1}','type':'text','title':f'Component {i+1}','weight':1+(i%7)*0.08,'order':i,'locked':False,'z':i+1})
    page.evaluate("m => { const p=window.__VIZ_PROD__; p.store.replaceModel(m,'200-component performance fixture'); p.ui.selected=new Set(['c1']); p.renderAll(); }", model)
    page.wait_for_timeout(80)
    report['component_count']=page.locator('.component').count()

    cdp=page.context.new_cdp_session(page)
    cdp.send('Performance.enable')
    cdp.send('HeapProfiler.collectGarbage')
    before_metrics={x['name']:x['value'] for x in cdp.send('Performance.getMetrics')['metrics']}
    heap_before=before_metrics.get('JSHeapUsedSize',0)

    perf=page.evaluate("""() => {
      const p=window.__VIZ_PROD__;
      const durations=[];
      const focused=document.querySelector('.component[data-id="c1"]'); focused.focus();
      const beforeFocus=document.activeElement?.dataset?.id || null;
      for(let i=0;i<360;i++){
        p.ui.previewPatches.set('c1',{weight:1.0+((i%41)-20)/100});
        const t0=performance.now();
        p.renderGeometryOnly();
        durations.push(performance.now()-t0);
      }
      const afterFocus=document.activeElement?.dataset?.id || null;
      p.ui.previewPatches.clear(); p.renderGeometryOnly();
      return {durations,beforeFocus,afterFocus,componentCount:document.querySelectorAll('.component').length};
    }""")
    cdp.send('HeapProfiler.collectGarbage')
    after_metrics={x['name']:x['value'] for x in cdp.send('Performance.getMetrics')['metrics']}
    heap_after=after_metrics.get('JSHeapUsedSize',0)
    vals=perf['durations']
    stats={
      'frames':len(vals),
      'mean_ms':statistics.fmean(vals),
      'median_ms':statistics.median(vals),
      'p95_ms':pct(vals,.95),
      'p99_ms':pct(vals,.99),
      'max_ms':max(vals),
      'under_16_7_pct':sum(v<=16.7 for v in vals)/len(vals)*100,
    }
    report['timing']=stats
    report['heap_before_mb']=heap_before/1024/1024
    report['heap_after_mb']=heap_after/1024/1024
    report['heap_growth_mb']=(heap_after-heap_before)/1024/1024
    report['focus_preserved']=perf['beforeFocus']=='c1' and perf['afterFocus']=='c1'
    report['dom_count_stable']=perf['componentCount']==200 and report['component_count']==200
    report['pass']=(not report['console_errors'] and report['dom_count_stable'] and report['focus_preserved'] and stats['p95_ms']<=report['budget']['p95_ms'] and report['heap_growth_mb']<=report['budget']['max_heap_growth_mb'])
    browser.close()

(PROD/'qa/performance_200.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['pass'] else 1)
