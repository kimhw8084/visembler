from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'company_ui/products/visualizer/assets'
FROZEN = ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'


def node(source: str):
    result = subprocess.run(['node', '--input-type=module', '-e', source], cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def test_refresh_rebinds_mappings_and_transforms_without_changing_scalar_values():
    result = node(r'''
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {planDatasetRefresh} from './company_ui/products/visualizer/assets/authoring_dataset_refresh.mjs';
const before=intakeText('time\tvalue\tgroup\n2026-01-01\t0\tA\n2026-01-02\t"0"\tB\n2026-01-03\t""\tC');
const after=intakeText('group\tvalue\ttime\nA\t0\t2026-01-01\nB\t"0"\t2026-01-02\nC\t""\t2026-01-03');
const byName=(fields,name)=>fields.find(field=>field.name===name).id;
const entry={id:'line',dataset_id:'D',view_type:'line',mapping:{x:byName(before.fields,'time'),y:byName(before.fields,'value')},transform_recipe:{source_dataset_id:'D',steps:[{type:'filter',field:byName(before.fields,'group'),operator:'contains',value:'A'},{type:'pivot',index_fields:[byName(before.fields,'time')],column_field:byName(before.fields,'group'),value_field:byName(before.fields,'value'),aggregation:'sum'}]}};
const plan=planDatasetRefresh({dataset:{id:'D',fields:before.fields,rows:before.rows},intake:after,items:[entry],selectedId:'line',viewForEntry:value=>value.view_type});
console.log(JSON.stringify({valid:plan.valid,mapping:plan.mappings[0]?.mapping,recipe:plan.mappings[0]?.transform_recipe,rows:after.rows}));
''')
    assert result['valid']
    assert result['mapping']['x'].endswith('_3')
    assert result['mapping']['y'].endswith('_2')
    step = result['recipe']['steps'][1]
    assert step['index_fields'] == [result['mapping']['x']]
    assert step['value_field'] == result['mapping']['y']
    assert result['rows'][0][1] == 0 and result['rows'][1][1] == '0' and result['rows'][2][1] == ''


def test_refresh_blocks_locks_missing_targets_ambiguous_and_unsupported_transform_references():
    result = node(r'''
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {planDatasetRefresh} from './company_ui/products/visualizer/assets/authoring_dataset_refresh.mjs';
const source=intakeText('category\tvalue\nA\t1'), next=intakeText('value\tcategory\n2\tA'), duplicate=intakeText('value\tvalue\n2\t3');
const entry={id:'a',dataset_id:'D',view_type:'bar',mapping:{category:source.fields[0].id,value:source.fields[1].id}};
const dataset={id:'D',fields:source.fields,rows:source.rows};
const run=(items,selectedId,intake=next,selectedOnly=false)=>planDatasetRefresh({dataset,intake,items,selectedId,selectedOnly,viewForEntry:value=>value.view_type});
const unsupported={...entry,transform_recipe:{steps:[{type:'filter',unknown_field:source.fields[0].id}]}};
console.log(JSON.stringify({locked:run([entry,{...entry,id:'b',locked:true}],'a'),missing:run([entry],'missing',next,true),duplicate:run([entry],'a',duplicate),transform:run([unsupported],'a')}));
''')
    assert not result['locked']['valid'] and 'Unlock every linked' in result['locked']['reason']
    assert not result['missing']['valid'] and 'no longer linked' in result['missing']['reason']
    assert result['duplicate']['compatibility']['kind'] == 'ambiguous'
    assert not result['transform']['valid'] and 'Unsupported transform field reference' in result['transform']['reason']


def test_editor_uses_dataset_identity_epoch_and_canonical_data_dock_path():
    source = (ASSETS / 'integrated_editor.mjs').read_text()
    assert 'function invalidateResolvedData()' in source
    assert "${bootstrap.report_id||'default'}:${ui.projectionEpoch}" in source
    assert 'dataset:dataset?{id:dataset.id,revision:dataset.revision||0,epoch:ui.projectionEpoch}:null' in source
    assert 'Values come from the Data Dock below.' in source
    assert "const views=['bar','line','multi_line','scatter','regression_scatter','histogram','box','pareto','table','timeline','engineering','wafer','diagram'];" in source
    assert "const view=event.target.value,target=productionTargetForView(view);" in source


def test_closeout_invariants_remain_intact():
    result = node("import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT}));")
    assert result['count'] == 49
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == 'd8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
