from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'company_ui/products/visualizer/assets'
FROZEN=ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'


def test_data_first_surfaces_worker_failure_instead_of_silent_idle_state():
    source=(ASSETS/'integrated_editor.mjs').read_text()
    assert "state.error||'Paste data to see production-ready visual choices.'" in source
    assert 'data-first-status error' in source
    assert 'intakeClient.cancel()' in source


def test_final_native_verifier_executes_all_remaining_native_gates():
    source=(ROOT/'scripts/verify_release.py').read_text()
    for name in ('native-recovery','worker-lifecycle','operations-drill','native-acceptance'):
        assert name in source
    assert "release_status='PASS_LOCAL_INTERNAL_PILOT'" in source
    assert "'release_status': 'BLOCKED'" not in source
    for script in ('run_native_recovery.py','run_worker_lifecycle.py','run_operations_drill.py','run_native_acceptance.py'):
        path=ROOT/'scripts/release_checks'/script
        assert path.is_file()
        compile(path.read_text(),str(path),'exec')


def test_native_host_supports_same_origin_restart_for_recovery_drill():
    source=(ROOT/'scripts/release_checks/editor_host.py').read_text()
    assert 'def stop(self):' in source and 'def restart(self):' in source
    assert 'return self._start(reuse_port=True)' in source


def test_intake_client_failure_cancel_and_retry_contract():
    script=r'''
import {createIntakeClient} from './company_ui/products/visualizer/assets/authoring_intake_client.mjs';
let mode='fail',terminated=0;
const makeWorker=()=>({
  onmessage:null,onerror:null,onmessageerror:null,
  postMessage(payload){queueMicrotask(()=>{if(mode==='fail')this.onerror?.({preventDefault(){}});else this.onmessage?.({data:{id:payload.id,result:{rows:[[1]],fields:[]}}});});},
  terminate(){terminated++;}
});
const client=createIntakeClient({makeWorker,parseInline:()=>({rows:[[0]]}),threshold:1,timeoutMs:1000});
let failed=false;try{await client.parse('large')}catch{failed=true}
mode='pass';const result=await client.parse('large2');
console.log(JSON.stringify({failed,rows:result.rows.length,pending:client.pendingCount,terminated}));
'''
    out=subprocess.check_output(['node','--input-type=module','-e',script],cwd=ROOT,text=True)
    result=json.loads(out)
    assert result['failed'] and result['rows']==1 and result['pending']==0 and result['terminated']==2


def test_final_closeout_invariants():
    out=subprocess.check_output(['node','--input-type=module','-e',"import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';console.log(PRODUCTION_LIBRARY_COUNT)"],cwd=ROOT,text=True).strip()
    assert out=='49'
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
