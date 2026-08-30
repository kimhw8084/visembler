#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time, os
from pathlib import Path

PROD=Path(__file__).resolve().parents[1]
QA=PROD/'qa'; QA.mkdir(exist_ok=True)
ROOT=PROD
COMMANDS=[
 ('advanced_chart_engine',['node','tests/advanced_chart_engine.test.mjs']),
 ('core_chart_engine',['node','tests/core_chart_engine.test.mjs']),
 ('editor_store',['node','tests/editor_store.test.mjs']),
 ('engineering_chart_engine',['node','tests/engineering_chart_engine.test.mjs']),
 ('graph_semantics_engine',['node','tests/graph_semantics_engine.test.mjs']),
 ('grid_layout_engine',['node','tests/grid_layout_engine.test.mjs']),
 ('data_grid_engine',['node','tests/data_grid_engine.test.mjs']),
 ('image_media_engine',['node','tests/image_media_engine.test.mjs']),
 ('wafer_fab_engine',['node','tests/wafer_fab_engine.test.mjs']),
 ('statistics_engine',['node','tests/statistics_engine.test.mjs']),
 ('table_pivot_engine',['node','tests/table_pivot_engine.test.mjs']),
 ('table_pivot_reference',['node','tests/table_pivot_reference.test.mjs']),
 ('timeline_semantics_engine',['node','tests/timeline_semantics_engine.test.mjs']),
 ('universal_renderer',['node','tests/universal_renderer.test.mjs']),
 ('ppt_mapping_catalog',['node','tests/ppt_mapping_catalog.test.mjs']),
 ('property_fuzz',['node','tests/property_fuzz.test.mjs']),
 ('static_p0_lint',['python','tools/static_p0_lint.py']),
 ('component_contracts',['python','tools/validate_component_contracts.py']),
 ('offline_runtime',['python','tests/offline_runtime.test.py']),
 ('ppt_template_adapter',['python','tests/ppt_template_adapter_test.py']),
 ('browser_smoke',['python','tests/browser_smoke.py']),
 ('performance_200',['python','tests/performance_200.py']),
 ('advanced_charts_browser',['python','tests/advanced_charts_browser.py']),
 ('engineering_charts_browser',['python','tests/engineering_charts_browser.py']),
 ('approval_preview_browser',['python','tests/approval_preview_browser.py']),
 ('release_248_browser',['python','tests/release_248_browser.py']),
 ('diagram_connector_benchmark',['python','tests/diagram_connector_benchmark.py']),
]

def extract_json(text):
    text=text.strip(); start=text.find('{')
    if start<0:return None
    depth=0;ins=False;esc=False
    for i,ch in enumerate(text[start:],start):
        if ins:
            if esc:esc=False
            elif ch=='\\':esc=True
            elif ch=='"':ins=False
            continue
        if ch=='"':ins=True
        elif ch=='{':depth+=1
        elif ch=='}':
            depth-=1
            if depth==0:
                try:return json.loads(text[start:i+1])
                except: return None
    return None

results=[];t0=time.perf_counter()
env=os.environ.copy();env.setdefault('TERM','xterm')
for idx,(name,cmd) in enumerate(COMMANDS,1):
    s=time.perf_counter();cp=subprocess.run(cmd,cwd=PROD,text=True,capture_output=True,env=env);elapsed=(time.perf_counter()-s)*1000
    payload=extract_json(cp.stdout);passed=cp.returncode==0 and (payload is None or payload.get('pass',True) is True)
    results.append({'index':idx,'name':name,'pass':passed,'returncode':cp.returncode,'elapsed_ms':round(elapsed,2),'payload':payload,'stdout_tail':cp.stdout.strip().splitlines()[-12:],'stderr_tail':cp.stderr.strip().splitlines()[-8:]})
    print(f'[{idx:02d}/{len(COMMANDS)}] {"PASS" if passed else "FAIL"} {name} ({elapsed:.0f} ms)',flush=True)
    if not passed:
        break
report={'pass':len(results)==len(COMMANDS) and all(r['pass'] for r in results),'suite':'Visualizer 95+ Production Release','commands_planned':len(COMMANDS),'commands_ran':len(results),'elapsed_ms':round((time.perf_counter()-t0)*1000,2),'results':results}
(QA/'release_suite.json').write_text(json.dumps(report,indent=2)+'\n')
# Keep historical filename aligned to current release evidence.
(QA/'full_suite.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'commands':report['commands_ran'],'planned':report['commands_planned'],'elapsed_ms':report['elapsed_ms']},indent=2))
raise SystemExit(0 if report['pass'] else 1)
