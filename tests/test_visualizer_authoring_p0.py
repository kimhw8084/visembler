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


def test_ppt_projection_uses_the_current_bound_dataset() -> None:
    items = bound_export_items({
        'datasets': [{'id': 'd1', 'fields': [{'id': 'lot', 'name': 'Lot'}, {'id': 'yield', 'name': 'Yield'}], 'rows': [['LOT-24', 0], ['LOT-25', 98.7]]}],
        'items': [{'id': 'c1', 'engine': 'TableEngine', 'dataset_id': 'd1', 'mapping': {'category': 'lot', 'value': 'yield'}}, {'id': 'c2', 'engine': 'CoreChartEngine', 'dataset_id': 'd1', 'mapping': {'category': 'lot', 'value': 'yield'}}],
    })
    assert items[0]['customTable']['rows'][0] == ['LOT-24', 0]
    assert items[1]['data'] == [('LOT-24', 0), ('LOT-25', 98.7)]


def test_authoring_modules_cover_contracts_intake_and_transforms() -> None:
    command = """
import { intakeText } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { applyRecipe } from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
import { contractFor } from './company_ui/products/visualizer/assets/authoring_contracts.mjs';
const intake = intakeText('Source\\tTarget\\tWeight\\nEtch\\tClean\\t0');
if (!intake.recommendations.some(x => x.view === 'diagram')) throw new Error('flow recommendation');
const data = { fields: [{id:'x',name:'X'}, {id:'y',name:'Y'}], rows: [['B', 2], ['A', 0]] };
const transformed = applyRecipe(data, { steps: [{type:'sort', field:'y'}] });
if (transformed.rows[0][1] !== 0) throw new Error('zero was lost');
const pivoted = applyRecipe({ fields: [{id:'tool',name:'Tool'}, {id:'chamber',name:'Chamber'}, {id:'yield',name:'Yield'}], rows: [['ETCH-04', 'A', 98], ['ETCH-04', 'B', 97], ['DEP-02', 'A', 99]] }, { steps: [{type:'pivot', field:'tool', column_field:'chamber', value_field:'yield', aggregation:'mean'}] });
if (pivoted.fields.map(field => field.name).join(',') !== 'Tool,A,B' || pivoted.rows.find(row => row[0] === 'DEP-02')?.[1] !== 99) throw new Error('pivot did not create a deterministic matrix');
const invalid = contractFor('bar').validate({category:'category',value:'category'}, [{id:'category',name:'Category',type:'categorical'}]);
if (!invalid.incompatible.includes('value')) throw new Error('contract did not reject incompatible value mapping');
"""
    subprocess.run(['node', '--input-type=module', '-e', command], cwd=ROOT, check=True, capture_output=True, text=True)


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
