from __future__ import annotations
import json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def node(src):return json.loads(subprocess.run(['node','--input-type=module','-e',src],cwd=ROOT,capture_output=True,text=True,check=True).stdout)
def test_refresh_planner_handles_exact_reordered_changed_and_shared_data():
 out=node(r'''
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';import {refreshCompatibility,planDatasetRefresh} from './company_ui/products/visualizer/assets/authoring_dataset_refresh.mjs';
const old=intakeText('lot\tx\ty\tvalue\nL\t1\t1\t0'),reordered=intakeText('value\ty\tlot\tx\n"0"\t1\tL\t1'),changed=intakeText('lot\tx\ty\tvalue\ttool\nL\t1\t1\t0\tE');
const map={die_x:old.fields[1].id,die_y:old.fields[2].id,value:old.fields[3].id,lot_id:old.fields[0].id};const ds={id:'d',name:'D',revision:2,fields:old.fields,rows:old.rows},items=[{id:'a',dataset_id:'d',mapping:map,view_type:'wafer',x:1,y:2,w:3,h:4},{id:'b',dataset_id:'d',mapping:map,view_type:'wafer'}];
console.log(JSON.stringify({exact:refreshCompatibility(old.fields,old.fields),reordered:refreshCompatibility(old.fields,reordered.fields),changed:refreshCompatibility(old.fields,changed.fields),plan:planDatasetRefresh({dataset:ds,intake:reordered,items,selectedId:'a',viewForEntry:e=>e.view_type}),one:planDatasetRefresh({dataset:ds,intake:reordered,items,selectedId:'a',selectedOnly:true,viewForEntry:e=>e.view_type})}));
''')
 assert out['exact']['kind']=='exact' and out['reordered']['kind']=='reordered' and out['changed']['kind']=='changed'
 assert out['plan']['valid'] and len(out['plan']['mappings'])==2 and out['one']['valid'] and len(out['one']['mappings'])==1
def test_refresh_connector_unchanged_and_editor_has_shared_replace_guard():
 js=(ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_text();assert 'function commitDatasetRefresh' in js and 'datasetConsumers(existing.id).length>1' in js and 'source_dataset_id:detached.id' in js and 'Schema changed · ${detail}' in js and "linked===1?'Refresh data'" in js
 p=ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js';assert hashlib.sha256(p.read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
