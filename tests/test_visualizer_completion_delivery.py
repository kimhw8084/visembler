from __future__ import annotations
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def node(code):
 p=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,text=True,capture_output=True,timeout=15,check=True)
 return json.loads(p.stdout)

def test_portable_envelope_removes_asset_id_without_coercing_rows_or_mutating_source():
 r=node('''
import {portableEnvelope} from './company_ui/products/visualizer/assets/authoring_portability.mjs';
const m={items:[{id:'i',engine:'ImageMediaEngine',src:'/asset/local',asset_id:'local'}],datasets:[{rows:[[0,'0','',null,true,'00123']]}]};
const result=await portableEnvelope(m,4,async()=> 'data:image/png;base64,AAAA');
console.log(JSON.stringify({source:m,result:result.envelope}));
''')
 assert r['source']['items'][0]['asset_id']=='local'
 assert 'asset_id' not in r['result']['model']['items'][0]
 assert r['result']['model']['datasets'][0]['rows']==[[0,'0','',None,True,'00123']]
 assert r['result']['revision']==4

def test_portable_envelope_does_not_silently_export_missing_or_external_assets():
 r=node('''
import {portableEnvelope} from './company_ui/products/visualizer/assets/authoring_portability.mjs';
const m={items:[{engine:'ImageMediaEngine',asset_id:'broken'}]};
let failures=0;for(const resolve of [async()=>{throw Error('unavailable')},async()=> 'https://external/image']){try{await portableEnvelope(m,1,resolve)}catch{failures++}}
console.log(JSON.stringify({failures}));
''')
 assert r['failures']==2

def test_worker_lifecycle_success_error_timeout_supersession_and_retry():
 r=node('''
import {createIntakeClient} from './company_ui/products/visualizer/assets/authoring_intake_client.mjs';
const workers=[],timers=new Map();let seq=0;
const client=createIntakeClient({threshold:1,parseInline:s=>s,makeWorker:()=>{const w={postMessage(m){this.message=m},terminate(){this.terminated=true}};workers.push(w);return w;},setTimer:fn=>{timers.set(++seq,fn);return seq},clearTimer:id=>timers.delete(id)});
const first=client.parse('A').catch(e=>e.message);const second=client.parse('B');
workers[1].onmessage({data:{id:workers[1].message.id,result:{rows:[[2]]}}});
const a=await first,b=await second;
const error=client.parse('C').catch(e=>e.message);workers[2].onerror({preventDefault(){}});await error;
const timeout=client.parse('D').catch(e=>e.message);[...timers.values()][0]();await timeout;
const retry=client.parse('E');workers[4].onmessage({data:{id:workers[4].message.id,result:{rows:[[5]]}}});await retry;
const cancel=client.parse('F').catch(e=>e.message);client.cancel();await cancel;
console.log(JSON.stringify({a,b,pending:client.pendingCount,timers:timers.size,terminated:workers.every(w=>w.terminated),handlers:workers.every(w=>w.onmessage===null&&w.onerror===null)}));
''')
 assert r['a']=='Parsing superseded' and r['b']['rows']==[[2]]
 assert r['pending']==r['timers']==0 and r['terminated'] and r['handlers']

def test_worker_creation_failure_rejects_and_next_inline_parse_recovers():
 r=node('''
import {createIntakeClient} from './company_ui/products/visualizer/assets/authoring_intake_client.mjs';
const client=createIntakeClient({threshold:4,makeWorker:()=>{throw Error('worker unavailable')},parseInline:()=>({rows:[[1]]})});
const error=await client.parse('long data').catch(e=>e.message);const next=await client.parse('x');console.log(JSON.stringify({error,next,pending:client.pendingCount}));
''')
 assert r['error']=='worker unavailable' and r['next']['rows']==[[1]] and r['pending']==0

def test_target_and_sparkline_geometry_depends_on_actual_values_not_fixed_artwork():
 r=node('''
import {renderIntegratedElement as render} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const target={engine:'MetricEngine',element:'Target vs Actual',actual:20,target:100};
const a=render(target),b=render({...target,actual:80});
const spark={engine:'MetricEngine',element:'Metric with Sparkline',value:8,series:[['A',1],['B',4],['C',9]]};
const c=render(spark),d=render({...spark,series:[['A',9],['B',4],['C',1]]});
console.log(JSON.stringify({a,b,c,d}));
''')
 assert 'width:20%' in r['a'] and 'width:80%' in r['b']
 assert r['c']!=r['d'] and 'M3.00 43.00' in r['c'] and 'M3.00 5.00' in r['d']
