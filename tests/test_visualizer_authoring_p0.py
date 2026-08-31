from __future__ import annotations

import subprocess
from pathlib import Path

from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.ppt_service import bound_export_items


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'company_ui' / 'products' / 'visualizer' / 'assets'


def test_dataset_binding_persists_without_copying_rows_into_item() -> None:
    model = canonical_model({
        'datasets': [{'id': 'd1', 'name': 'Yield', 'revision': 1, 'fields': [{'id': 'yield', 'name': 'Yield'}], 'rows': [[0]], 'source': {'kind': 'clipboard'}}],
        'items': [{'id': 'c1', 'type': 'chart', 'order': 0, 'dataset_id': 'd1', 'mapping': {'value': 'yield'}}],
    })
    assert model['datasets'][0]['rows'] == [[0]]
    assert 'rows' not in model['items'][0]


def test_editor_replaces_shared_datasets_through_the_dependency_commit_path() -> None:
    editor = (ASSETS / 'integrated_editor.mjs').read_text()
    assert "return commitDataset(entry,label,nextDataset,nextMapping);" in editor
    assert "replaceDataset(entry,'Paste data into visual',dataset,mapping)" in editor


def test_editor_persistence_uses_one_pending_pipeline_and_retains_conflict_recovery() -> None:
    editor = (ASSETS / 'integrated_editor.mjs').read_text(encoding='utf-8')
    assert 'function syncAccepted(accepted)' in editor
    assert 'function persistPendingState()' in editor
    assert 'function reapplyLocalRecovery()' in editor
    assert "if(!dispatchSemantic('report.commit',payload))" in editor
    assert "dispatchSemantic('report.commit',{report_id:" not in editor
    assert "syncAccepted({id:localCommitId('undo'" in editor
    assert "syncAccepted({id:localCommitId('redo'" in editor
    assert "commitOps('Load preset',[{op:'model.replace',value:next}]" in editor
    assert "button.textContent='Autosaved'" in editor
    assert "button.textContent='Recover edits'" in editor
    page = (ROOT / 'company_ui' / 'products' / 'visualizer' / 'page.py').read_text(encoding='utf-8')
    assert "'authoring_geometry.mjs'" in page


def test_personal_preset_list_exposes_every_server_supported_preset() -> None:
    editor = (ASSETS / 'integrated_editor.mjs').read_text(encoding='utf-8')
    html = (ASSETS / 'integrated_editor.html').read_text(encoding='utf-8')
    assert 'personalPresets.slice(0,20)' not in editor
    assert "id=\"presetSearch\"" in html
    assert "result.sort((a,b)=>a.name.localeCompare" in editor
    assert "p.model.items.length" in editor


def test_data_dock_and_unbound_tables_preserve_large_range_editing_contracts() -> None:
    editor = (ASSETS / 'integrated_editor.mjs').read_text(encoding='utf-8')
    assert 'function parseCellForField(raw, field)' in editor
    assert 'function renderVirtualCustomTable(entry)' in editor
    assert 'id="tableEditorGrid"' in editor
    assert "Paste table range" in editor
    assert "Clear table range" in editor
    assert "while(next.fields.length<startColumn+width)" in editor
    assert "Clear dataset range" in editor
    assert "Delete dataset column" in editor
    assert "record.index}:${column}" in editor


def test_element_maturity_audit_covers_the_registered_catalog_and_renderer_uses_semantic_payloads() -> None:
    command = """
import { ELEMENT_MATURITY_AUDIT, MATURITY_COUNTS } from './company_ui/products/visualizer/assets/element_maturity_audit.mjs';
import { REGISTRY_COUNTS } from './company_ui/products/visualizer/vendor/production_core/core/runtime_registry.mjs';
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
if (ELEMENT_MATURITY_AUDIT.length !== REGISTRY_COUNTS.elements || ELEMENT_MATURITY_AUDIT.length !== 248) throw new Error('catalog audit is incomplete');
if (Object.values(MATURITY_COUNTS).reduce((a,b)=>a+b,0)!==248) throw new Error('maturity totals are inconsistent');
const strip=renderIntegratedElement({engine:'MetricEngine',element:'Metric Strip',metrics:[{label:'Custom yield',value:0},{label:'Lot',value:'0012'}]});
if (!strip.includes('Custom yield') || !strip.includes('0012') || !strip.includes('>0<')) throw new Error('metric strip ignores semantic values');
const ranked=renderIntegratedElement({engine:'TableEngine',element:'Ranked Table',customTable:{headers:['Lot','Yield'],rows:[['LOT-99',0]]}});
if (!ranked.includes('LOT-99') || !ranked.includes('>0<') || ranked.includes('Chamber A')) throw new Error('specialized table ignores bound rows');
const quality=renderIntegratedElement({engine:'ComparisonEngine',element:'Quality Improvement',before:0,after:100});
if (!quality.includes('>0<') || !quality.includes('>100<')) throw new Error('comparison visual ignores before/after values');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_container_layout_metadata_persists_with_group_membership() -> None:
    model = canonical_model({
        'groups': {'g1': {'id': 'g1', 'items': ['c1', 'c2'], 'layout': {'kind': 'grid', 'gap': 14}}},
        'items': [{'id': 'c1', 'type': 'text', 'order': 0, 'groupId': 'g1'}, {'id': 'c2', 'type': 'text', 'order': 1, 'groupId': 'g1'}],
    })
    assert model['groups']['g1']['layout']['kind'] == 'grid'


def test_ppt_projection_uses_the_current_bound_dataset() -> None:
    items = bound_export_items({
        'datasets': [{'id': 'd1', 'fields': [{'id': 'lot', 'name': 'Lot'}, {'id': 'yield', 'name': 'Yield'}], 'rows': [['LOT-24', 0], ['LOT-25', 98.7]]}],
        'items': [{'id': 'c1', 'engine': 'TableEngine', 'dataset_id': 'd1', 'mapping': {'category': 'lot', 'value': 'yield'}}, {'id': 'c2', 'engine': 'CoreChartEngine', 'dataset_id': 'd1', 'mapping': {'category': 'lot', 'value': 'yield'}}],
    })
    assert items[0]['customTable']['rows'][0] == ['LOT-24', 0]
    assert items[1]['data'] == [('LOT-24', 0), ('LOT-25', 98.7)]


def test_authoring_modules_cover_contracts_intake_and_transforms() -> None:
    command = """
import { intakeText, appendCompatibleDataset } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { applyRecipe } from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
import { contractFor } from './company_ui/products/visualizer/assets/authoring_contracts.mjs';
const intake = intakeText('Source\\tTarget\\tWeight\\nEtch\\tClean\\t0');
if (!intake.recommendations.some(x => x.view === 'diagram')) throw new Error('flow recommendation');
if (!intakeText('Name\\tValue\\n"broken\\t1').warnings.some(x => x.code === 'unclosed_quote')) throw new Error('intake warning was not retained');
const mixed = intakeText('Date\\tReading\\n2026-08-01\\t1\\nnot-a-date\\tA');
if (!mixed.warnings.some(x => x.code === 'invalid_date') || !mixed.warnings.some(x => x.code === 'mixed_type')) throw new Error('mixed intake was not made actionable');
if (mixed.rows[1][0] !== 'not-a-date' || mixed.rows[0][1] !== '1') throw new Error('ambiguous values were coerced');
const data = { fields: [{id:'x',name:'X'}, {id:'y',name:'Y'}], rows: [['B', 2], ['A', 0]] };
const transformed = applyRecipe(data, { steps: [{type:'sort', field:'y'}] });
if (transformed.rows[0][1] !== 0) throw new Error('zero was lost');
const pivoted = applyRecipe({ fields: [{id:'tool',name:'Tool'}, {id:'chamber',name:'Chamber'}, {id:'yield',name:'Yield'}], rows: [['ETCH-04', 'A', 98], ['ETCH-04', 'B', 97], ['DEP-02', 'A', 99]] }, { steps: [{type:'pivot', field:'tool', column_field:'chamber', value_field:'yield', aggregation:'mean'}] });
if (pivoted.fields.map(field => field.name).join(',') !== 'Tool,A,B' || pivoted.rows.find(row => row[0] === 'DEP-02')?.[1] !== 99) throw new Error('pivot did not create a deterministic matrix');
const invalid = contractFor('bar').validate({category:'category',value:'category'}, [{id:'category',name:'Category',type:'categorical'}]);
if (!invalid.incompatible.includes('value')) throw new Error('contract did not reject incompatible value mapping');
const appended = appendCompatibleDataset({fields:[{id:'lot',name:'Lot'},{id:'yield',name:'Yield'}],rows:[['LOT-24',0]],revision:2}, {fields:[{id:'new_lot',name:'Lot'},{id:'new_yield',name:'Yield'}],rows:[['LOT-25',98.7]]});
if (!appended.ok || appended.dataset.rows.length !== 2 || appended.dataset.rows[1][1] !== 98.7 || appended.dataset.revision !== 3) throw new Error('matching rows did not append');
if (appendCompatibleDataset({fields:[{name:'Lot'}],rows:[]}, {fields:[{name:'Wafer'}],rows:[]}).ok) throw new Error('mismatched headings were appended');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_authoring_data_preserves_engineering_numeric_and_typed_dimensions() -> None:
    command = """
import { intakeText } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { applyRecipe } from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const percent = intakeText('Yield\\tLot Code\\tZero\\tBlank\\n98.7%\\t0012\\t0%\\t\\n-2.5%\\t0007\\t-0.5%\\t');
if (percent.rows[0][0] !== .987 || percent.rows[1][0] !== -.025 || percent.rows[0][2] !== 0 || percent.rows[1][2] !== -.005) throw new Error('percent values were not converted to fractions');
if (percent.rows[0][1] !== '0012' || percent.rows[1][1] !== '0007' || percent.rows[0][3] !== null) throw new Error('identifiers or blanks were coerced');
const temporal = intakeText('Timestamp\\tYield\\n2026-08-01T00:00:00Z\\t98.7%\\n2026-08-02T00:00:00Z\\t99.1%');
const line = temporal.candidate_mappings.find(candidate => candidate.view === 'line');
if (!line || line.mapping.x !== temporal.fields[0].id || line.incompatible.length) throw new Error('temporal line mapping does not satisfy its contract');
const base = {fields:[{id:'value',name:'Value',type:'number'}],rows:[[.1],[.3],[null]]};
const derived = applyRecipe(base,{steps:[{type:'derive',source_field:'value',multiplier:0,offset:0}]});
if (derived.rows.map(row=>row[1]).join(',') !== '0,0,') throw new Error('explicit zero derive parameters were lost');
const normalized = applyRecipe(base,{steps:[{type:'normalize',field:'value'}]});
if (normalized.rows[0][1] !== 0 || normalized.rows[1][1] !== 1 || normalized.rows[2][1] !== null) throw new Error('small numeric range was not normalized');
const constant = applyRecipe({fields:[{id:'value',name:'Value',type:'number'}],rows:[[.2],[.2],[null]]},{steps:[{type:'normalize',field:'value'}]});
if (constant.rows.map(row=>row[1]).join(',') !== '0,0,') throw new Error('constant normalization is not deterministic');
const grouped = applyRecipe({fields:[{id:'key',name:'Key'},{id:'value',name:'Value'}],rows:[[1,2],['1',3],[null,4]]},{steps:[{type:'group',field:'key',value_field:'value',aggregation:'sum'}]});
if (grouped.rows.length !== 3 || grouped.rows[0][0] !== 1 || grouped.rows[1][0] !== '1') throw new Error('grouping merged distinct typed values');
const pivoted = applyRecipe({fields:[{id:'index',name:'Index'},{id:'column',name:'Column'},{id:'value',name:'Value'}],rows:[[1,1,2],['1','1',3]]},{steps:[{type:'pivot',field:'index',column_field:'column',value_field:'value',aggregation:'sum'}]});
if (pivoted.rows.length !== 2 || pivoted.fields.map(field=>field.name).join(',') !== 'Index,1 (number),1 (string)') throw new Error('pivot merged typed dimensions');
const wafer = renderIntegratedElement({engine:'WaferFabEngine',element:'Wafer Map',dataset_id:'wafer',observations:[{x:0,y:0,value:.1},{x:1,y:0,value:.2}]});
if (!wafer.includes('heat-4')) throw new Error('wafer renderer compressed a sub-unit range');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_paste_recommendations_bind_the_matching_validated_view_contract() -> None:
    command = """
import { intakeText, candidateForView } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { contractFor } from './company_ui/products/visualizer/assets/authoring_contracts.mjs';
const cases = [
  ['bar', 'Lot\\tYield\\nL1\\t0\\nL2\\t98.7'],
  ['line', 'Timestamp\\tYield\\n2026-08-01T00:00:00Z\\t98.7\\n2026-08-02T00:00:00Z\\t99.1'],
  ['scatter', 'Temperature\\tPressure\\n20\\t1.1\\n21\\t1.3'],
  ['table', 'Lot\\tStatus\\nL1\\tOpen\\nL2\\tClosed'],
  ['engineering', 'Subgroup\\tReading\\nA\\t0\\nB\\t0.2'],
  ['diagram', 'Source\\tTarget\\tWeight\\nEtch\\tClean\\t0\\nClean\\tInspect\\t2'],
  ['wafer', 'Die X\\tDie Y\\tYield\\n0\\t0\\t98.7\\n1\\t0\\t99.1'],
];
for (const [view, text] of cases) {
  const intake = intakeText(text);
  const recommendation = intake.recommendations.find(item => item.view === view);
  if (!recommendation) throw new Error(`missing ${view} recommendation`);
  const candidate = candidateForView(intake, view);
  if (!candidate || JSON.stringify(recommendation.mapping) !== JSON.stringify(candidate.mapping)) throw new Error(`${view} recommendation used another view mapping`);
  const validation = contractFor(recommendation.contract_view).validate(recommendation.mapping, intake.fields);
  if (!validation.valid || recommendation.unresolved.length || recommendation.incompatible.length) throw new Error(`${view} recommendation is not immediately bindable`);
}
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)
    editor = (ASSETS / 'integrated_editor.mjs').read_text()
    assert 'mapping=result.candidate_mappings[0]?.mapping' not in editor
    assert 'function resolvedEntry(entry)' in editor
    assert 'title:String(labels.at(-1)||entry.title)' not in editor
    assert 'candidate.id===entry.id?nextMapping:candidate.mapping||{}' not in editor


def test_guided_and_free_canvas_geometry_contracts() -> None:
    command = """
import { chooseSnap, clampMovementDelta, distributeRects, resizeRect } from './company_ui/products/visualizer/assets/authoring_geometry.mjs';
const canvas={w:120,h:100};
const moved=clampMovementDelta([{x:10,y:10,w:40,h:20},{x:80,y:20,w:10,h:30}],100,-50,canvas,0);
if (moved.dx !== 30 || moved.dy !== -10) throw new Error('selection did not receive one shared boundary delta');
const northwest=resizeRect({x:20,y:20,w:40,h:20},'nw',{x:10,y:5},{minW:10,minH:10,canvas});
if (JSON.stringify(northwest)!==JSON.stringify({x:30,y:25,w:30,h:15})) throw new Error('northwest resize lost the opposite edge anchor');
const center=resizeRect({x:30,y:30,w:20,h:10},'e',{x:8,y:0},{minW:10,minH:10,canvas,alt:true});
if (center.x!==22 || center.w!==36) throw new Error('center resize did not preserve the center');
const ratio=resizeRect({x:20,y:20,w:40,h:20},'se',{x:20,y:1},{minW:10,minH:10,canvas,shift:true});
if (ratio.w/ratio.h!==2) throw new Error('shift resize did not preserve aspect ratio');
const bounded=resizeRect({x:2,y:2,w:20,h:20},'nw',{x:-50,y:-50},{minW:10,minH:10,canvas,inset:14});
if (bounded.x<14 || bounded.y<14 || bounded.x+bounded.w>106 || bounded.y+bounded.h>86) throw new Error('guided resize escaped its canvas frame');
const priority=chooseSnap(101,[{value:100,priority:3},{value:102,priority:1}],8);
if (priority?.value!==102) throw new Error('snap priority was not deterministic for equally close targets');
const safe=chooseSnap(15,[{value:14,priority:0},{value:16,priority:4}],8);
if (safe?.value!==14) throw new Error('safe margin did not win the deterministic snap priority');
const distributed=distributeRects([{id:'a',x:14,y:10,w:20,h:10},{id:'b',x:50,y:10,w:20,h:10},{id:'c',x:100,y:10,w:20,h:10}],'x',14);
if (!distributed || distributed[1].x!==57 || distributed[2].x!==100) throw new Error('guided distribution did not preserve equal grid-safe gaps');
if (distributeRects([{id:'a',x:0,y:0,w:40,h:10},{id:'b',x:45,y:0,w:40,h:10},{id:'c',x:90,y:0,w:40,h:10}],'x',14)!==null) throw new Error('guided distribution accepted an overlapping result');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)
    editor = (ASSETS / 'integrated_editor.mjs').read_text(encoding='utf-8')
    css = (ASSETS / 'integrated_editor.css').read_text(encoding='utf-8')
    assert "['n','ne','e','se','s','sw','w','nw']" in editor
    assert 'clampMovementDelta(orig,sx,sy,CANVAS,inset)' in editor
    assert 'if(!ui.selected.has(id)){ui.selected.clear();ui.selected.add(id);reconcileCanvas({content:false});renderInspector();}' in editor
    assert 'clearTransientInteractionVisuals' in editor and 'cancelPointerSession(\'mode-switch\')' in editor
    assert 'function guidedTargets(axis, moving, others, excludedIds=new Set())' in editor
    assert 'function manualOpsOverlap(ops)' in editor
    assert 'distributeRects(rects,axis,model().mode===\'guided\'?CANVAS.gap:0)' in editor
    assert "hideGuides(reason);" in editor
    for handle in ('n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'):
        assert f'.resize-h--{handle}' in css


def test_dataset_bound_engineering_variants_use_the_production_analysis_renderer() -> None:
    command = """
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const fields = [
  {id:'factor',name:'Factor',type:'categorical'},
  {id:'batch',name:'Batch',type:'categorical'},
  {id:'temperature',name:'Temperature',type:'number'},
  {id:'response',name:'Response',type:'number'},
];
const rows = [
  {Factor:'Low',Batch:'A',Temperature:10,Response:80},
  {Factor:'Low',Batch:'B',Temperature:12,Response:82},
  {Factor:'High',Batch:'A',Temperature:14,Response:91},
  {Factor:'High',Batch:'B',Temperature:16,Response:94},
];
const entry = {engine:'EngineeringChartEngine',element:'DOE Main Effects',title:'DOE',analysis_fields:fields,analysis_rows:rows,analysis_mapping:{value:'response'}};
const rendered = renderIntegratedElement(entry);
if (!rendered.includes('data-engineering-chart=\"doe_main\"')) throw new Error('dataset DOE was not rendered by the analysis engine');
const confidence = renderIntegratedElement({...entry,element:'Confidence Interval Plot'});
if (!confidence.includes('data-engineering-chart=\"ci\"')) throw new Error('dataset confidence interval was not rendered by the analysis engine');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_engineering_factor_mapping_overrides_unmapped_numeric_columns() -> None:
    command = """
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const fields = [
  {id:'x',name:'Temperature',type:'number'}, {id:'y',name:'Pressure',type:'number'},
  {id:'noise',name:'Unmapped sensor',type:'number'}, {id:'response',name:'Yield',type:'number'},
];
const rows = [];
for (const temperature of [10, 20, 30]) for (const pressure of [1, 2, 3]) rows.push({Temperature:temperature,Pressure:pressure,'Unmapped sensor':null,Yield:70 + temperature / 3 + pressure});
const rendered = renderIntegratedElement({engine:'EngineeringChartEngine',element:'Response Surface',title:'Surface',analysis_fields:fields,analysis_rows:rows,analysis_mapping:{x:'x',y:'y',value:'response'}});
if (!rendered.includes('data-engineering-chart=\"surface\"')) throw new Error('explicit x/y mapping was not used for response surface');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_dataset_bound_wafer_renderer_keeps_semiconductor_identity_context() -> None:
    command = """
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const rendered = renderIntegratedElement({
  engine:'WaferFabEngine', element:'Wafer Map', dataset_id:'wafer-1',
  observations:[{x:0,y:0,value:98.5},{x:1,y:0,value:97.9}],
  wafer_id:'W12', lot:'LOT-24-118', tool:'ETCH-04', chamber:'B', recipe:'RCP-7', process:'Etch',
});
for (const value of ['W12','LOT-24-118','ETCH-04']) if (!rendered.includes(value)) throw new Error(`missing mapped wafer identity ${value}`);
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_specialty_dataset_views_use_matrix_timeline_and_graph_semantics() -> None:
    command = """
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const matrix = renderIntegratedElement({engine:'MatrixEngine',element:'Heatmap',dataset_id:'d1',title:'Yield',matrix_long:[{row:'Etch',column:'A',value:97.2},{row:'Etch',column:'B',value:98.1},{row:'Dep',column:'A',value:96.8},{row:'Dep',column:'B',value:99.0}]});
if (!matrix.includes('matrix-bound') || !matrix.includes('99')) throw new Error('mapped matrix was not rendered');
const timeline = renderIntegratedElement({engine:'TimelineEngine',element:'Event Timeline',dataset_id:'d1',milestones:[{label:'Collect',date:'2026-08-01'},{label:'Verify',date:'2026-08-04'}]});
if (!timeline.includes('data-timeline-plan') || !timeline.includes('2026-08-04')) throw new Error('semantic timeline was not rendered');
const diagram = renderIntegratedElement({engine:'DiagramEngine',element:'Data Flow',dataset_id:'d1',nodes:['Source','Analyze','Decide'],edges:[['Source','Analyze'],['Analyze','Decide']]});
if (!diagram.includes('data-graph-plan') || !diagram.includes('Decide')) throw new Error('validated graph was not rendered');
if (!diagram.includes('data-direct="diagram-node:0"')) throw new Error('diagram nodes are not inline editable');
const titled = renderIntegratedElement({engine:'TextEngine',element:'Key Takeaway',title:'Editable title',showTitle:true});
if (!titled.includes('data-direct=\"title\"')) throw new Error('visible title is not inline editable');
const table = renderIntegratedElement({engine:'TableEngine',element:'Clean Table',dataset_id:'d1',customTable:{headers:['Lot','Yield'],rows:[['LOT-24',98.7]]}});
if (!table.includes('data-direct=\"dataset-cell:0:1\"')) throw new Error('dataset table cells are not inline editable');
const chart = renderIntegratedElement({engine:'CoreChartEngine',element:'Line Chart',data:[['A',1],['B',2]]});
if (!chart.includes('data-behavior-point=\"0\"')) throw new Error('core chart does not expose attachable behavior hooks');
const fabFields = [{id:'tool',name:'Tool',type:'categorical'},{id:'chamber',name:'Chamber',type:'categorical'},{id:'value',name:'Yield',type:'number'},{id:'process',name:'Process',type:'categorical'}];
const fabRows = [{Tool:'ETCH-04',Chamber:'A',Yield:98.1,Process:'Etch'},{Tool:'ETCH-04',Chamber:'B',Yield:97.4,Process:'Clean'},{Tool:'DEP-02',Chamber:'A',Yield:99.0,Process:'Deposit'}];
const fab = renderIntegratedElement({engine:'WaferFabEngine',element:'Tool × Recipe Heatmap',dataset_id:'fab',fab_fields:fabFields,fab_rows:fabRows,fab_mapping:{tool:'tool',chamber:'chamber',value:'value',process:'process'}});
if (!fab.includes('ETCH-04') || !fab.includes('97.4')) throw new Error('mapped fab heatmap was not rendered');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)
