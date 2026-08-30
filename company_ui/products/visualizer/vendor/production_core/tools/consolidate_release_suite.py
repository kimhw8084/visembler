#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time, os, sys
from pathlib import Path
PROD=Path(__file__).resolve().parents[1]; QA=PROD/'qa'
CHEAP=[
 ('advanced_chart_engine',['node','tests/advanced_chart_engine.test.mjs']),('core_chart_engine',['node','tests/core_chart_engine.test.mjs']),
 ('editor_store',['node','tests/editor_store.test.mjs']),('engineering_chart_engine',['node','tests/engineering_chart_engine.test.mjs']),
 ('graph_semantics_engine',['node','tests/graph_semantics_engine.test.mjs']),('grid_layout_engine',['node','tests/grid_layout_engine.test.mjs']),
 ('data_grid_engine',['node','tests/data_grid_engine.test.mjs']),('image_media_engine',['node','tests/image_media_engine.test.mjs']),
 ('wafer_fab_engine',['node','tests/wafer_fab_engine.test.mjs']),('statistics_engine',['node','tests/statistics_engine.test.mjs']),
 ('table_pivot_engine',['node','tests/table_pivot_engine.test.mjs']),('table_pivot_reference',['node','tests/table_pivot_reference.test.mjs']),
 ('timeline_semantics_engine',['node','tests/timeline_semantics_engine.test.mjs']),('universal_renderer',['node','tests/universal_renderer.test.mjs']),
 ('ppt_mapping_catalog',['node','tests/ppt_mapping_catalog.test.mjs']),('property_fuzz',['node','tests/property_fuzz.test.mjs']),
]
FILES=[
 ('static_p0_lint','static_p0_lint.json'),('component_contracts','component_contract_validation.json'),('offline_runtime','offline_runtime.json'),
 ('ppt_template_adapter','ppt_template_adapter.json'),('browser_smoke','browser_smoke.json'),('performance_200','performance_200.json'),
 ('advanced_charts_browser','advanced_charts_browser.json'),('engineering_charts_browser','engineering_charts_browser.json'),
 ('approval_preview_browser','approval_preview_browser.json'),('release_248_browser','release_248_browser.json'),('diagram_connector_benchmark','diagram_connector_benchmark.json'),
]
def extract(text):
    st=text.find('{')
    if st<0:return None
    dec=json.JSONDecoder()
    try:return dec.raw_decode(text[st:])[0]
    except:return None
results=[];env=os.environ.copy();env.setdefault('TERM','xterm');start=time.perf_counter()
for name,cmd in CHEAP:
    t=time.perf_counter();cp=subprocess.run(cmd,cwd=PROD,text=True,capture_output=True,env=env);payload=extract(cp.stdout);ok=cp.returncode==0 and payload is not None and payload.get('pass') is True
    results.append({'name':name,'pass':ok,'source':'executed','elapsed_ms':round((time.perf_counter()-t)*1000,2),'payload':payload})
    if not ok: break
if all(r['pass'] for r in results) and len(results)==len(CHEAP):
    for name,file in FILES:
        p=QA/file
        payload=json.loads(p.read_text()) if p.exists() else None;ok=bool(payload and payload.get('pass') is True)
        results.append({'name':name,'pass':ok,'source':file,'payload':payload})
        if not ok: break
report={'pass':len(results)==27 and all(r['pass'] for r in results),'suite':'Visualizer 95+ Production Release','commands_planned':27,'commands_ran':len(results),'elapsed_ms':round((time.perf_counter()-start)*1000,2),'results':results}
(QA/'release_suite.json').write_text(json.dumps(report,indent=2)+'\n');(QA/'full_suite.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'commands':len(results),'failed':[r['name'] for r in results if not r['pass']],'elapsed_ms':report['elapsed_ms']},indent=2));sys.exit(0 if report['pass'] else 1)
