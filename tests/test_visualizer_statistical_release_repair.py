from __future__ import annotations

import io
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from pptx import Presentation

from company_ui.data_engine import DataQuery, FilterClause, FilterOperation
from company_ui.products.visualizer.dataset_resources import DatasetResourceStore, ScopedDatasetRepository
from company_ui.products.visualizer.domain import ReportNotFoundError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.ppt_service import export_pptx
from company_ui.products.visualizer.page import _apply_data_session_filters, _candidate_session, _report_thumbnail_markup
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.statistical_analysis import analyze_statistical_items, require_valid_statistical_results
from company_ui.security import AuthorizationModel, Principal


ROOT = Path(__file__).resolve().parents[1]


def node_json(source: str):
    result = subprocess.run(['node', '--input-type=module', '-e', source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def _cap_fields():
    return [
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number'},
        {'id': 'lsl', 'name': 'LSL', 'type': 'number'},
        {'id': 'usl', 'name': 'USL', 'type': 'number'},
    ]


def _cap_item(item_id='capability'):
    mapping = {'value': 'measurement', 'specification_low': 'lsl', 'specification_high': 'usl'}
    return {'id': item_id, 'engine': 'MetricEngine', 'type': 'metric', 'mapping': mapping, 'analysis_recipe': {'id': 'process-capability', 'mapping': mapping}}


def _analyze(fields, rows, item, *, source_total=None, filtered_total=None, revision=1, dataset_id='d1', filters=()):
    return analyze_statistical_items(
        report_id='report-1', dataset_id=dataset_id, resource_id='resource-1', revision=revision,
        fields=fields, rows=rows, items=[item], session_id='session-1',
        filters=filters, source_total=len(rows) if source_total is None else source_total,
        filtered_total=len(rows) if filtered_total is None else filtered_total,
    )[item['id']]


def test_resource_capability_uses_full_population_and_records_provenance(tmp_path: Path):
    fields = _cap_fields()
    rows = [[1, 0, 10] for _ in range(250)] + [[10, 0, 10] for _ in range(250)]
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='full capability', fields=fields, rows=rows)
    result = _analyze(fields, [[row[field['id']] for field in fields] for row in store.session(resource['dataset_id']).query(DataQuery(limit=None)).rows], _cap_item(), source_total=500, filtered_total=500)
    assert result['ok'] is True
    stats = result['derived_statistics']['stats']
    sigma = math.sqrt(10125 / 499)
    assert stats['n'] == 500
    assert stats['mean'] == pytest.approx(5.5)
    assert stats['cpk'] == pytest.approx(4.5 / (3 * sigma))
    assert result['population'] == {'source_total': 500, 'filtered_total': 500, 'analyzed_rows': 500, 'complete': True}
    assert result['source']['dataset_revision'] == resource['revision']
    assert len(result['renderer_ready']['dataset']['rows']) == 1
    assert 250 != stats['n']


def test_filtered_resource_over_10000_is_not_silently_truncated(tmp_path: Path):
    fields = _cap_fields() + [{'id': 'population', 'name': 'Population', 'type': 'categorical'}]
    rows = [[9.8 + (index % 3) * 0.2, 9, 11, 'target'] for index in range(12000)] + [[10.2, 9, 11, 'other'] for _ in range(50)]
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='large filtered capability', fields=fields, rows=rows)
    session = store.session(resource['dataset_id'])
    with session.transaction():
        session.set_filter(FilterClause('population', FilterOperation.EQUALS, 'target'))
    preview = session.query(DataQuery(limit=10000))
    complete = session.query(DataQuery(limit=None))
    assert preview.filtered_total == 12000 and len(preview.rows) == 10000
    assert complete.filtered_total == 12000 and len(complete.rows) == 12000
    result = _analyze(fields, [[row['measurement'], row['lsl'], row['usl'], row['population']] for row in complete.rows], _cap_item('filtered-capability'), source_total=12050, filtered_total=complete.filtered_total)
    assert result['ok'] is True
    assert result['population']['filtered_total'] == 12000
    assert result['population']['analyzed_rows'] == 12000
    assert result['population']['complete'] is True
    assert result['derived_statistics']['stats']['n'] == 12000


def test_resource_xbar_and_doe_use_exact_complete_rows():
    x_fields = [{'id': 'subgroup', 'name': 'Subgroup', 'type': 'categorical'}, {'id': 'measurement', 'name': 'Measurement', 'type': 'number'}]
    x_rows = [[f'G{i}', i + offset] for i in range(1, 61) for offset in range(5)]
    x_item = {'id': 'xbar', 'engine': 'EngineeringChartEngine', 'type': 'chart', 'element': 'Xbar-R Chart', 'analysis_recipe': {'id': 'xbar-r-process-review', 'mapping': {'subgroup': 'subgroup', 'value': 'measurement'}}}
    x_result = _analyze(x_fields, x_rows, x_item, source_total=300, filtered_total=300)
    assert x_result['ok'] is True
    assert x_result['population'] == {'source_total': 300, 'filtered_total': 300, 'analyzed_rows': 300, 'complete': True}
    assert x_result['derived_statistics']['stats']['n'] == 5
    assert x_result['derived_statistics']['stats']['means'][:3] == [3, 4, 5]
    assert x_result['derived_statistics']['stats']['ranges'] == [4] * 60

    d_fields = [{'id': 'factor_a', 'name': 'Factor A', 'type': 'categorical'}, {'id': 'factor_b', 'name': 'Factor B', 'type': 'categorical'}, {'id': 'response', 'name': 'Response', 'type': 'number'}]
    d_rows = [[a, b, base + index * 0.1] for a, base in [('A', 10), ('B', 30)] for b in ('L', 'H') for index in range(100)]
    d_item = {'id': 'doe', 'engine': 'EngineeringChartEngine', 'type': 'chart', 'element': 'DOE Interaction Plot', 'analysis_recipe': {'id': 'doe-response-review', 'mapping': {'factor_a': 'factor_a', 'factor_b': 'factor_b', 'response': 'response'}}}
    d_result = _analyze(d_fields, d_rows, d_item, source_total=400, filtered_total=400)
    assert d_result['ok'] is True
    assert d_result['population'] == {'source_total': 400, 'filtered_total': 400, 'analyzed_rows': 400, 'complete': True}
    interaction = d_result['derived_statistics']['interaction']
    assert len(interaction['cells']) == 2 and all(len(row) == 2 for row in interaction['cells'])
    assert interaction['cells'][0][0]['mean'] == pytest.approx(14.95)
    assert interaction['cells'][1][1]['mean'] == pytest.approx(34.95)


@pytest.mark.parametrize('size', [1000, 10000, 100000])
def test_supported_resource_envelope_is_bounded_and_characterized(size: int):
    fields = _cap_fields()
    rows = [[9.8 + (index % 3) * 0.2, 9, 11] for index in range(size)]
    started = time.perf_counter()
    result = _analyze(fields, rows, _cap_item(f'cap-{size}'), source_total=size, filtered_total=size)
    elapsed = time.perf_counter() - started
    assert result['ok'] is True
    assert result['population']['analyzed_rows'] == size
    assert result['population']['complete'] is True
    # The response is a governed summary, not a raw-row transport.
    assert len(json.dumps(result, separators=(',', ':'))) < 25000
    assert elapsed < 60


def test_invalid_refresh_preflight_is_atomic_for_xbar_capability_and_doe(tmp_path: Path):
    store = DatasetResourceStore(tmp_path)

    cap = store.create(owner='alice', name='cap', fields=_cap_fields(), rows=[[9.8, 9, 11], [10.2, 9, 11]])
    bad_cap_rows = [[9.8, 9, 11], [10.2, 9.5, 11]]
    bad_cap = _analyze(_cap_fields(), bad_cap_rows, _cap_item(), revision=2, dataset_id=cap['dataset_id'])
    with pytest.raises(VisualizerContractError, match='conflicting values'):
        require_valid_statistical_results({'cap': bad_cap})
    assert store.get(cap['dataset_id'])['revision'] == 1

    x_fields = [{'id': 'subgroup', 'name': 'Subgroup', 'type': 'categorical'}, {'id': 'measurement', 'name': 'Measurement', 'type': 'number'}]
    x = store.create(owner='alice', name='xbar', fields=x_fields, rows=[['A', 1], ['A', 2], ['B', 3], ['B', 4]])
    bad_x = _analyze(x_fields, [['A', 1], ['A', 2], ['B', 3], ['B', 4], ['B', 5]], {'id': 'x', 'analysis_recipe': {'id': 'xbar-r-process-review', 'mapping': {'subgroup': 'subgroup', 'value': 'measurement'}}}, revision=2, dataset_id=x['dataset_id'])
    with pytest.raises(VisualizerContractError, match='constant subgroup size'):
        require_valid_statistical_results({'x': bad_x})
    assert store.get(x['dataset_id'])['revision'] == 1

    d_fields = [{'id': 'factor_a', 'name': 'Factor A', 'type': 'categorical'}, {'id': 'factor_b', 'name': 'Factor B', 'type': 'categorical'}, {'id': 'response', 'name': 'Response', 'type': 'number'}]
    d = store.create(owner='alice', name='doe', fields=d_fields, rows=[['A', 'L', 1], ['A', 'H', 2], ['B', 'L', 3], ['B', 'H', 4]])
    bad_d = _analyze(d_fields, [['A', 'L', 1], ['A', 'H', 2], ['B', 'L', 3]], {'id': 'd', 'analysis_recipe': {'id': 'doe-response-review', 'mapping': {'factor_a': 'factor_a', 'factor_b': 'factor_b', 'response': 'response'}}}, revision=2, dataset_id=d['dataset_id'])
    with pytest.raises(VisualizerContractError, match='missing|Interaction cell'):
        require_valid_statistical_results({'d': bad_d})
    assert store.get(d['dataset_id'])['revision'] == 1


def test_invalid_persisted_analysis_is_explicitly_failed_closed_and_svg_is_finite():
    payload = node_json(r'''
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
import {renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const viewBox = value => { const match=value.match(/viewBox="([^"]+)"/); if(!match) throw new Error('missing viewBox'); const nums=match[1].trim().split(/\s+/).map(Number); return {nums,finite:nums.length===4&&nums.every(Number.isFinite)&&nums.every(value=>value>=0)}; };
const xbar={engine:'EngineeringChartEngine',element:'Xbar-R Chart',chart_type:'Xbar-R Chart',dataset:{fields:[],rows:[]},mapping:{},statistical_result:null};
const invalidEntry={engine:'EngineeringChartEngine',element:'Xbar-R Chart',title:'Quality review',analysis_error:'Xbar-R requires constant subgroup size. Found subgroup sizes 4 and 5.',analysis_semantics:{ok:false},_resolved_dataset:{fields:[],rows:[]}};
const populated=renderChartSvg({...xbar,statistical_result:{n:2,means:[1,2],ranges:[1,1],xbarLimits:{lcl:0,center:1.5,ucl:3},rLimits:{lcl:0,center:1,ucl:2},rules:{signals:[]}}},{width:760,height:500});
const empty=renderChartSvg(xbar,{width:760,height:500});
const error=renderChartSvg({...xbar,analysis_error:'bad'}, {width:760,height:500});
const card=renderIntegratedElement({...invalidEntry,value:84.2,statistical_result:{means:[84.2]}});
const invalidCapability=renderIntegratedElement({engine:'MetricEngine',element:'Hero KPI',title:'Capability',analysis_recipe:{id:'process-capability'},authoritative_analysis:{ok:false,population:{complete:false},errors:[{message:'Conflicting LSL values'}]},value:84.2,capability_summary:{cpk:1.7},statistical_result:{cpk:1.7}});
const invalidDoe=renderIntegratedElement({engine:'EngineeringChartEngine',element:'DOE Interaction Plot',title:'DOE',analysis_recipe:{id:'doe-response-review'},authoritative_analysis:{ok:false,population:{complete:false},errors:[{message:'Missing interaction cell'}]},statistical_result:{interaction:{cells:[[99]]}}});
const invalidChart=renderChartSvg({...xbar,authoritative_analysis:{ok:false,population:{complete:false},errors:[{message:'bad Xbar'}]},statistical_result:{means:[84.2]}},{width:760,height:500});
console.log(JSON.stringify({populated:viewBox(populated),empty:viewBox(empty),error:viewBox(error),card,invalidCapability,invalidDoe,invalidChart,hasDemo:/(84\.2|Baseline|Pilot|Validation|1\.7|99)/.test(card+invalidCapability+invalidDoe+invalidChart)}));
''')
    for key in ('populated', 'empty', 'error'):
        assert payload[key]['finite'] is True
    assert 'Analysis needs attention' in payload['card']
    assert 'Analysis needs attention' in payload['invalidCapability']
    assert 'Analysis needs attention' in payload['invalidDoe']
    assert 'Analysis needs attention' in payload['invalidChart']
    assert payload['hasDemo'] is False

    thumb=_report_thumbnail_markup(
        {'items':[{'id':'cap','engine':'MetricEngine','element':'Hero KPI','value':84.2,'analysis_recipe':{'id':'process-capability'}}]},
        'Invalid capability',
        {'cap':{'ok':False,'population':{'complete':False},'errors':[{'message':'Conflicting LSL values'}]}},
    )
    assert 'Analysis needs attention' in thumb
    assert '84.2' not in thumb
    assert 'Baseline' not in thumb and 'Pilot' not in thumb


def test_ppt_statistical_primitives_match_authoritative_editor_result():
    cap_fields = _cap_fields()
    cap_rows = [[9.8, 9.5, 10.5], [10, 9.5, 10.5], [10.2, 9.5, 10.5], [10.1, 9.5, 10.5], [9.9, 9.5, 10.5]]
    cap_item = _cap_item('cap')
    cap_result = _analyze(cap_fields, cap_rows, cap_item)
    x_fields = [{'id': 'subgroup', 'name': 'Subgroup', 'type': 'categorical'}, {'id': 'measurement', 'name': 'Measurement', 'type': 'number'}]
    x_rows = [['A', 1], ['A', 3], ['B', 2], ['B', 6]]
    x_mapping = {'subgroup': 'subgroup', 'value': 'measurement'}
    x_item = {'id': 'xbar', 'engine': 'EngineeringChartEngine', 'type': 'chart', 'element': 'Xbar-R Chart', 'mapping': x_mapping, 'analysis_recipe': {'id': 'xbar-r-process-review', 'mapping': x_mapping}}
    x_result = _analyze(x_fields, x_rows, x_item)
    d_fields = [{'id': 'factor_a', 'name': 'Factor A', 'type': 'categorical'}, {'id': 'factor_b', 'name': 'Factor B', 'type': 'categorical'}, {'id': 'response', 'name': 'Response', 'type': 'number'}]
    d_rows = [['A', 'L', 10], ['A', 'H', 14], ['B', 'L', 20], ['B', 'H', 28]]
    d_mapping = {'factor_a': 'factor_a', 'factor_b': 'factor_b', 'response': 'response'}
    d_item = {'id': 'doe', 'engine': 'EngineeringChartEngine', 'type': 'chart', 'element': 'DOE Interaction Plot', 'mapping': d_mapping, 'analysis_recipe': {'id': 'doe-response-review', 'mapping': d_mapping}}
    d_result = _analyze(d_fields, d_rows, d_item)
    model = canonical_model({'datasets': [
        {'id': 'cap-dataset', 'fields': cap_fields, 'rows': cap_rows},
        {'id': 'x-dataset', 'fields': x_fields, 'rows': x_rows},
        {'id': 'd-dataset', 'fields': d_fields, 'rows': d_rows},
    ], 'items': [
        {**cap_item, 'dataset_id': 'cap-dataset', 'title': 'Capability KPI', 'order': 0, 'x': 0, 'y': 0, 'w': 300, 'h': 150},
        {**x_item, 'dataset_id': 'x-dataset', 'title': 'Xbar-R', 'order': 1, 'x': 0, 'y': 180, 'w': 600, 'h': 250},
        {**d_item, 'dataset_id': 'd-dataset', 'title': 'DOE Interaction', 'order': 2, 'x': 620, 'y': 180, 'w': 600, 'h': 250},
    ], 'nextId': 4})
    model['items'][0]['authoritative_analysis'] = cap_result
    model['items'][1]['authoritative_analysis'] = x_result
    model['items'][2]['authoritative_analysis'] = d_result
    deck = Presentation(io.BytesIO(export_pptx(None, model)))
    texts = '\n'.join(shape.text for shape in deck.slides[0].shapes if getattr(shape, 'has_text_frame', False))
    assert str(cap_result['derived_statistics']['stats']['cpk']) in texts
    assert '84.2' not in texts and 'Complete population count' not in texts
    charts = [shape.chart for shape in deck.slides[0].shapes if getattr(shape, 'has_chart', False)]
    assert len(charts) == 2
    x_values = [list(series.values) for series in charts[0].plots[0].series]
    doe_values = [list(series.values) for series in charts[1].plots[0].series]
    assert x_values == [x_result['derived_statistics']['stats']['means'], x_result['derived_statistics']['stats']['ranges']]
    expected_doe = [[cell['mean'] for cell in row] for row in d_result['derived_statistics']['interaction']['cells']]
    assert doe_values == expected_doe
    invalid_model = canonical_model({'items': [{**cap_item, 'order': 0, 'x': 0, 'y': 0, 'w': 300, 'h': 150, 'value': 84.2, 'authoritative_analysis': {'ok': False, 'population': {'complete': False}, 'errors': [{'message': 'Conflicting LSL values'}]}}], 'datasets': []})
    with pytest.raises(VisualizerContractError, match='Conflicting LSL values'):
        export_pptx(None, invalid_model)
    stale_model = canonical_model({'items': [{**cap_item, 'order': 0, 'x': 0, 'y': 0, 'w': 300, 'h': 150, 'analysis_error': 'Historical analysis needs attention', 'authoritative_analysis': cap_result}], 'datasets': []})
    with pytest.raises(VisualizerContractError, match='Historical analysis needs attention'):
        export_pptx(None, stale_model)


def test_recommendation_validation_is_conservative_and_shared_with_execution():
    payload = node_json(r'''
import {recommendEngineeringRecipes} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const fields=[{id:'g',name:'Subgroup',type:'categorical',semantic_tags:['subgroup']},{id:'m',name:'Measurement',type:'number',semantic_tags:['value']}];
const bad=value=>recommendEngineeringRecipes(fields,[['A',value],['A',2],['B',3],['B',4]]).some(item=>item.id==='xbar-r-process-review');
const doeFields=[{id:'tool',name:'Tool',type:'categorical'},{id:'chamber',name:'Chamber',type:'categorical'},{id:'yield',name:'Yield',type:'number'}];
const doe=items=>recommendEngineeringRecipes(doeFields,items).some(item=>item.id==='doe-response-review');
const tagged=[{id:'a',name:'Factor A',type:'categorical',semantic_tags:['factor_a']},{id:'b',name:'Factor B',type:'categorical',semantic_tags:['factor_b']},{id:'r',name:'Response',type:'number',semantic_tags:['response']}];
const capFields=[{id:'m',name:'Measurement',type:'number',semantic_tags:['value']},{id:'low',name:'LSL',type:'number',semantic_tags:['specification_low']},{id:'high',name:'USL',type:'number',semantic_tags:['specification_high']}];
const capRecipe=rows=>recommendEngineeringRecipes(capFields,rows).some(item=>item.id==='process-capability');
console.log(JSON.stringify({null:bad(null),blank:bad(''),whitespace:bad('   '),boolean:bad(true),malformed:bad('abc'),ordinary:doe([['T1','A',90],['T1','B',91],['T2','A',92],['T2','B',93]]),incomplete:recommendEngineeringRecipes(tagged,[['A','L',1],['A','H',2],['B','L',3]]).some(item=>item.id==='doe-response-review'),conflictingCapability:capRecipe([[10,9,11],[10,9.5,11]]),zeroVariationCapability:capRecipe([[10,9,11],[10,9,11]])}));
''')
    assert payload == {'null': False, 'blank': False, 'whitespace': False, 'boolean': False, 'malformed': False, 'ordinary': False, 'incomplete': False, 'conflictingCapability': False, 'zeroVariationCapability': False}


def test_cross_report_resource_access_is_denied_and_stale_revision_is_ignored(tmp_path: Path):
    repository = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repository)
    scoped = ScopedReportRepository(repository, access, Principal('alice', permissions=frozenset({'report.create'})), AuthorizationModel())
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='scoped', fields=_cap_fields(), rows=[[9.8, 9, 11], [10.2, 9, 11]])
    report_model = canonical_model({'datasets': [{'id': 'd1', 'resource_id': resource['dataset_id'], 'external': True, 'fields': resource['schema'], 'rows': [], 'row_count': 2}], 'items': []})
    scoped.create('report-a', model=report_model)
    scoped.create('report-b', model=canonical_model({'datasets': [], 'items': []}))
    with pytest.raises((PermissionError, ReportNotFoundError)):
        ScopedDatasetRepository(store, scoped).session_for_report('report-b', 'd1')
    assert node_json(r'''
import {acceptsStatisticalResult,nextRequestId,resultKey} from './company_ui/products/visualizer/assets/statistical_result_guard.mjs';
const key=resultKey('report-a','d1','session-a'),requests={[key]:{current:9}};
const request10=nextRequestId(requests,key),request11=nextRequestId(requests,key);
let state={visibleFilter:'none',population:0};
const apply=(requestId,filter,population)=>{const expectedFilters=[['product','equals',filter,null,null]],resultFilters=[['product','equals',filter,null,null]];if(acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',expectedSessionId:'session-a',resultSessionId:'session-a',expectedFilters,resultFilters,expectedRevision:4,resultRevision:4,activeRequestId:requests[key].current,resultRequestId:requestId})){state={visibleFilter:filter,population};}};
apply(request11,'B',2); apply(request10,'A',1);
const bootstrap20=20,bootstrap21=21;requests[key].current=bootstrap21;let disposable={};
const bootstrap=(requestId)=>{const accepted=!!requests[key]&&acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',activeRequestId:requests[key].current,resultRequestId:requestId});if(accepted){disposable={};state.bootstrap=requestId;}return accepted;};
const bootstrap21Accepted=bootstrap(bootstrap21),bootstrap20Rejected=!bootstrap(bootstrap20);
const generationAfterBootstrap=nextRequestId(requests,key),numericCollisionRejected=!acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',activeRequestId:generationAfterBootstrap,resultRequestId:1});
requests[key].current=31;const currentErrorAccepted=acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',activeRequestId:31,resultRequestId:31}),staleErrorRejected=!acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',activeRequestId:31,resultRequestId:30});
const emptyGeneration={};const unknownTaggedRejected=!emptyGeneration[key] || !acceptsStatisticalResult({expectedReportId:'report-a',resultReportId:'report-a',expectedDatasetId:'d1',resultDatasetId:'d1',activeRequestId:emptyGeneration[key]?.current,resultRequestId:20});
console.log(JSON.stringify({same:acceptsStatisticalResult({expectedRevision:2,resultRevision:2}),revision_stale:acceptsStatisticalResult({expectedRevision:2,resultRevision:1}),request_stale:acceptsStatisticalResult({activeRequestId:'new',resultRequestId:'old'}),request10,request11,state,bootstrap21Accepted,bootstrap20Rejected,generationAfterBootstrap,numericCollisionRejected,currentErrorAccepted,staleErrorRejected,unknownTaggedRejected,report_switch:acceptsStatisticalResult({expectedReportId:'report-b',resultReportId:'report-a',activeRequestId:1,resultRequestId:1})}));
    ''') == {'same': True, 'revision_stale': False, 'request_stale': False, 'request10': 10, 'request11': 11, 'state': {'visibleFilter': 'B', 'population': 2, 'bootstrap': 21}, 'bootstrap21Accepted': True, 'bootstrap20Rejected': True, 'generationAfterBootstrap': 22, 'numericCollisionRejected': True, 'currentErrorAccepted': True, 'staleErrorRejected': True, 'unknownTaggedRejected': True, 'report_switch': False}


def test_filter_intent_converges_with_datasession_and_statistical_population(tmp_path: Path):
    fields=[
        {'id':'tool','name':'Tool','type':'categorical'},
        {'id':'product','name':'Product','type':'categorical'},
        {'id':'chamber','name':'Chamber','type':'categorical'},
        {'id':'measurement','name':'Measurement','type':'number'},
        {'id':'lsl','name':'LSL','type':'number'},
        {'id':'usl','name':'USL','type':'number'},
    ]
    rows=[
        ['ETCH-01','P1','B',1,0,40],['ETCH-01','P1','B',2,0,40],['ETCH-01','P2','B',10,0,40],['ETCH-01','P2','B',11,0,40],
        ['DEP-02','P2','A',20,0,40],['DEP-02','P2','A',21,0,40],['DEP-02','P1','A',30,0,40],['DEP-02','P1','A',31,0,40],
    ]
    item={'id':'capability','analysis_recipe':{'id':'process-capability','mapping':{'value':'measurement','specification_low':'lsl','specification_high':'usl'}}}
    store=DatasetResourceStore(tmp_path)
    resource=store.create(owner='alice',name='filter-intent',fields=fields,rows=rows)
    session=store.session(resource['dataset_id'])

    def apply(values, replace=True):
        clauses=[FilterClause(field,FilterOperation.EQUALS,value) for field,value in values]
        _apply_data_session_filters(session,clauses,replace=replace)
        result=session.query(DataQuery(limit=None))
        analyzed=_analyze(fields,[[row[field['id']] for field in fields] for row in result.rows],item,source_total=8,filtered_total=result.filtered_total,revision=resource['revision'],dataset_id=resource['dataset_id'],filters=session.filters)
        return result,analyzed

    result,unfiltered=apply([])
    assert session.filters==() and result.filtered_total==8 and unfiltered['population']=={'source_total':8,'filtered_total':8,'analyzed_rows':8,'complete':True}
    assert unfiltered['derived_statistics']['stats']['mean'] == 15.75
    result,tool=apply([('tool','ETCH-01')])
    assert [(clause.field,clause.value) for clause in session.filters]==[('tool','ETCH-01')]
    assert result.filtered_total==4 and tool['population']['analyzed_rows']==4
    assert tool['derived_statistics']['stats']['mean'] == 6
    result,product=apply([('product','P2')])
    assert [(clause.field,clause.value) for clause in session.filters]==[('product','P2')]
    assert result.filtered_total==4 and product['population']['filtered_total']==4
    assert product['derived_statistics']['stats']['mean'] == 15.5
    result,compound=apply([('tool','ETCH-01'),('chamber','B')])
    assert [(clause.field,clause.value) for clause in session.filters]==[('tool','ETCH-01'),('chamber','B')]
    assert result.filtered_total==4 and compound['population']['analyzed_rows']==4
    assert compound['derived_statistics']['stats']['mean'] == 6
    result,removed=apply([('tool','ETCH-01')])
    assert [(clause.field,clause.value) for clause in session.filters]==[('tool','ETCH-01')]
    assert result.filtered_total==4 and removed['session']['filter_fingerprint']!=compound['session']['filter_fingerprint']
    assert removed['derived_statistics']['stats']['mean'] == 6
    result,cleared=apply([])
    assert session.filters==() and result.filtered_total==8 and cleared['population']['analyzed_rows']==8
    assert cleared['derived_statistics']['stats']['mean'] == 15.75

    candidate=_candidate_session(resource['dataset_id'],fields,rows,resource['revision']+1,[FilterClause('tool',FilterOperation.EQUALS,'ETCH-01'),FilterClause('chamber',FilterOperation.EQUALS,'B')])
    candidate_result=candidate.query(DataQuery(limit=None))
    candidate_rows=[[row[field['id']] for field in fields] for row in candidate_result.rows]
    candidate_analysis=_analyze(fields,candidate_rows,item,source_total=len(rows),filtered_total=candidate_result.filtered_total,revision=resource['revision']+1,dataset_id=resource['dataset_id'],filters=candidate.filters)
    assert candidate_result.filtered_total==4 and len(candidate_result.rows)==4
    assert candidate_analysis['population']=={'source_total':8,'filtered_total':4,'analyzed_rows':4,'complete':True}
    assert [(clause.field,clause.value) for clause in candidate.filters]==[('tool','ETCH-01'),('chamber','B')]
    assert candidate_analysis['session']['filter_fingerprint']!=cleared['session']['filter_fingerprint']
    assert candidate_analysis['derived_statistics']['stats']['mean']==6


@pytest.mark.parametrize('viewport_width', [1440, 768, 390])
def test_native_editor_statistical_paths_are_browser_safe(viewport_width: int, tmp_path: Path):
    """Exercise the shipped NiceGUI route, not only the embedded editor host."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost, load_editor
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    def apply_recipe(page, recipe_id: str, source: str):
        panels(page, library=viewport_width > 800, inspector=False)
        before_count = len(model(page)['items'])
        paste = page.locator('#pasteDataBtn')
        if not paste.is_visible():
            paste = page.locator('#blankStartSurface [data-blank-action="paste"]')
        paste.click()
        page.locator('#dataFirstText').fill(source)
        page.locator('.data-first-summary').wait_for(state='visible', timeout=20000)
        recipe = page.locator(f'[data-data-first-recipe="{recipe_id}"]')
        recipe.wait_for(state='visible', timeout=20000)
        recipe.click()
        recipe.wait_for(state='attached')
        page.locator('#dataFirstApplyRecipe').click()
        page.wait_for_function(
            '(count) => window.CompanyUIVisualizerBridge.state().model.items.length > count',
            arg=before_count,
            timeout=30000,
        )
        settled(page)

    def selected(page, item_id: str):
        component = page.locator(f'.component[data-id="{item_id}"]')
        component.focus()
        component.press('Enter')
        panels(page, library=False, inspector=True)
        return component

    xbar_source = 'Subgroup\tOrder\tMeasurement\n' + '\n'.join(
        f'G{group}\t{group}\t{group + offset}'
        for group in range(1, 4)
        for offset in range(5)
    )

    with tempfile.TemporaryDirectory(prefix='visembler-native-statistical-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(
                    viewport={'width': viewport_width, 'height': 1000},
                    accept_downloads=True,
                )
                errors = []
                failed_requests = []
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    load_editor(page, host, 'native-statistical-report')
                    ready(page)

                    # Inline Xbar-R, then the same real report is bound to the
                    # governed resource path.  The bound model retains only a
                    # 250-row preview; the rendered semantics must be complete.
                    apply_recipe(page, 'xbar-r-process-review', xbar_source)
                    xbar_id = next(item['id'] for item in model(page)['items'] if item['element'] == 'Xbar-R Chart')
                    xbar = selected(page, xbar_id)
                    assert all(token in xbar.inner_text() for token in ('X̄', 'R', 'UCL', 'LCL'))
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function(
                        '() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)',
                        timeout=20000,
                    )
                    settled(page)
                    bound_dataset = next(dataset for dataset in model(page)['datasets'] if dataset.get('resource_id'))
                    assert bound_dataset['row_count'] == 15
                    assert len(bound_dataset['rows']) == 15

                    # A real chart interaction must reach the active-filter
                    # surface without producing a browser error or overflow.
                    xbar = selected(page, xbar_id)
                    points = xbar.locator('[data-chart-point], [data-point], [data-behavior-point]')
                    if points.count():
                        points.first.click()
                        page.locator('#activeFilters').wait_for(state='visible')
                        assert 'Active filters' in page.locator('#activeFilters').inner_text()
                        page.locator('[data-clear-all-filters]').click()
                        page.locator('#activeFilters').wait_for(state='hidden')

                    # Export Center must expose every semantic surface.  The
                    # server PPT request is exercised through the native route;
                    # PPT semantic equality is asserted in the value-level test.
                    page.locator('#exportBtn').click()
                    assert page.locator('#exportPptAction').is_visible()
                    assert page.locator('#exportSvgAction').is_visible()
                    assert page.locator('#exportPngAction').is_visible()
                    assert page.locator('#exportJpegAction').is_visible()
                    page.locator('#exportPptAction').click()
                    page.wait_for_timeout(1000)
                    export_text = page.locator('body').inner_text()
                    assert (
                        'Editable PowerPoint export generated' in export_text
                        or 'Resolve export-blocking validation issues first' in export_text
                    )
                    if page.locator('#genericModal.show').count():
                        page.locator('#genericModal.show [data-close]').first.click()

                    # Refresh the bound Xbar-R into mixed subgroup sizes.  The
                    # authoritative refresh boundary rejects it and leaves the
                    # prior revision/analysis visible.
                    selected(page, xbar_id)
                    page.locator('[data-refresh-dataset]').click()
                    page.locator('#refreshDataText').fill('Subgroup\tOrder\tMeasurement\nA\t1\t1\nA\t1\t2\nB\t2\t3\nB\t2\t4\nB\t2\t5')
                    refresh_linked = page.locator('#refreshLinked')
                    if refresh_linked.is_enabled():
                        refresh_linked.click()
                        page.get_by_text('constant subgroup size').wait_for(timeout=20000)
                    else:
                        assert page.locator('#modalBody').inner_text().strip()
                        page.locator('#modalBody [data-close]').click()
                    assert next(dataset for dataset in model(page)['datasets'] if dataset.get('resource_id'))['revision'] == 1
                    assert all(token in page.locator(f'.component[data-id="{xbar_id}"]').inner_text() for token in ('X̄', 'R', 'UCL', 'LCL'))

                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    browser_text = page.locator('body').inner_text()
                    assert 'NaN' not in browser_text
                    assert 'Infinity' not in browser_text
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_bound_capability_uses_full_population_after_reopen(tmp_path: Path):
    """The actual NiceGUI resource path must not regress to the preview."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost, load_editor
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    rows = [[1 if index < 250 else 10, 0, 10] for index in range(500)]
    cap_item = {
        **_cap_item('cap'),
        'type': 'chart',
        'engine': 'CoreChartEngine',
        'element': 'Histogram',
        'title': 'Capability Histogram',
        'dataset_id': 'd1',
        'order': 0,
        'x': 20,
        'y': 20,
        'w': 720,
        'h': 360,
    }
    report_model = canonical_model({
        'datasets': [{'id': 'd1', 'name': 'Capability source', 'fields': _cap_fields(), 'rows': rows}],
        'items': [cap_item],
        'nextId': 2,
    })
    with tempfile.TemporaryDirectory(prefix='visembler-native-capability-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                errors = []
                failed_requests = []
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge?.state', timeout=20000)
                    page.wait_for_timeout(500)
                    cap_id = 'cap'
                    cap = page.locator(f'.component[data-id="{cap_id}"]')
                    assert 'n=500' in cap.inner_text()
                    assert 'Cpk 0.333' in cap.inner_text()

                    cap.focus()
                    cap.press('Enter')
                    panels(page, library=False, inspector=True)
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function(
                        '() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)',
                        timeout=20000,
                    )
                    settled(page)
                    dataset = next(dataset for dataset in model(page)['datasets'] if dataset.get('resource_id'))
                    assert dataset['row_count'] == 500
                    assert len(dataset['rows']) == 250
                    assert 'n=500' in cap.inner_text()
                    assert 'Cpk 0.333' in cap.inner_text()

                    # Reopen through the real route and prove the persisted
                    # binding resolves the same complete result.
                    report_id = page.evaluate('() => window.CompanyUIVisualizerBridge.state().report_id')
                    page.close()
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                    page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    cap = page.locator(f'.component[data-id="{cap_id}"]')
                    assert 'n=500' in cap.inner_text()
                    assert 'Cpk 0.333' in cap.inner_text()

                    page.locator('#exportBtn').click()
                    assert page.locator('#exportPptAction').is_visible()
                    assert page.locator('#exportSvgAction').is_visible()
                    page.locator('#exportPptAction').click()
                    page.wait_for_timeout(1000)
                    assert 'Editable PowerPoint export generated' in page.locator('body').inner_text() or 'Resolve export-blocking validation issues first' in page.locator('body').inner_text()

                    cap.focus()
                    cap.press('Enter')
                    panels(page, library=False, inspector=True)
                    page.locator('[data-refresh-dataset]').click()
                    page.locator('#refreshDataText').fill('Measurement\tLSL\tUSL\n1\t0\t10\n10\t0\t9')
                    refresh_linked = page.locator('#refreshLinked')
                    if refresh_linked.is_enabled():
                        refresh_linked.click()
                        page.wait_for_timeout(1000)
                        assert 'specification' in page.locator('body').inner_text().lower()
                    else:
                        assert page.locator('#modalBody').inner_text().strip()
                        page.locator('#modalBody [data-close]').click()
                    assert next(dataset for dataset in model(page)['datasets'] if dataset.get('resource_id'))['revision'] == 1
                    assert 'Cpk 0.333' in cap.inner_text()
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    browser_text = page.locator('body').inner_text()
                    assert 'NaN' not in browser_text and 'Infinity' not in browser_text
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_bound_doe_uses_complete_cells_and_exports(tmp_path: Path):
    """The shipped Editor must use governed complete-cell DOE results after binding."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    fields = [
        {'id': 'factor_a', 'name': 'Factor A', 'type': 'categorical'},
        {'id': 'factor_b', 'name': 'Factor B', 'type': 'categorical'},
        {'id': 'response', 'name': 'Response', 'type': 'number'},
    ]
    rows = [
        ['A', 'L', 10], ['A', 'L', 12], ['A', 'H', 14], ['A', 'H', 16],
        ['B', 'L', 20], ['B', 'L', 22], ['B', 'H', 28], ['B', 'H', 30],
    ]
    mapping = {'factor_a': 'factor_a', 'factor_b': 'factor_b', 'response': 'response'}
    item = {
        'id': 'doe', 'type': 'chart', 'engine': 'EngineeringChartEngine',
        'element': 'DOE Interaction Plot', 'title': 'DOE Interaction',
        'dataset_id': 'd1', 'mapping': mapping,
        'analysis_recipe': {'id': 'doe-response-review', 'mapping': mapping},
        'order': 0, 'x': 20, 'y': 20, 'w': 720, 'h': 360,
    }
    report_model = canonical_model({'datasets': [{'id': 'd1', 'name': 'DOE source', 'fields': fields, 'rows': rows}], 'items': [item], 'nextId': 2})

    with tempfile.TemporaryDirectory(prefix='visembler-native-doe-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                page = context.new_page()
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    settled(page)
                    doe = page.locator('.component[data-id="doe"]')
                    assert 'Analysis needs attention' not in doe.inner_text()
                    assert doe.locator('svg').count() > 0
                    doe.focus()
                    doe.press('Enter')
                    panels(page, library=False, inspector=True)
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function(
                        '() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)',
                        timeout=20000,
                    )
                    settled(page)
                    dataset = next(dataset for dataset in model(page)['datasets'] if dataset.get('resource_id'))
                    assert dataset['row_count'] == 8
                    assert len(dataset['rows']) == 8
                    assert 'Analysis needs attention' not in doe.inner_text()
                    preflight = page.evaluate('() => window.__VIZ_PROD__.preflight()')
                    assert not preflight['dataIssues'], preflight
                    page.locator('#exportBtn').click()
                    if preflight['layoutIssues']:
                        page.locator('#exportPptAction').click()
                        assert page.locator('#genericModal.show').count() == 1
                    else:
                        with page.expect_download(timeout=20000) as download_info:
                            page.locator('#exportPptAction').click()
                        ppt_bytes = Path(download_info.value.path()).read_bytes()
                        assert len(ppt_bytes) > 1000
                        deck = Presentation(io.BytesIO(ppt_bytes))
                        assert any(getattr(shape, 'has_chart', False) for slide in deck.slides for shape in slide.shapes)
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    assert 'NaN' not in page.locator('body').inner_text()
                    assert 'Infinity' not in page.locator('body').inner_text()
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_filtered_resource_refresh_bootstrap_preserves_session_population(tmp_path: Path):
    """A successful refresh must bootstrap the preserved filtered session."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    fields = [
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number'},
        {'id': 'lsl', 'name': 'LSL', 'type': 'number'},
        {'id': 'usl', 'name': 'USL', 'type': 'number'},
        {'id': 'product', 'name': 'Product', 'type': 'categorical'},
    ]
    rows = [[20, 0, 40, 'P2'], [21, 0, 40, 'P2'], [20, 0, 40, 'P2'], [21, 0, 40, 'P2'],
            [1, 0, 40, 'P1'], [2, 0, 40, 'P1'], [1, 0, 40, 'P1'], [2, 0, 40, 'P1']]
    cap_mapping = {'value': 'measurement', 'specification_low': 'lsl', 'specification_high': 'usl'}
    cap = {
        **_cap_item('cap'), 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI',
        'title': 'Capability', 'dataset_id': 'd1', 'order': 0, 'x': 20, 'y': 20, 'w': 360, 'h': 180,
        'mapping': cap_mapping,
    }
    persisted_filter = {'field': 'product', 'label': 'Product', 'value': 'P2', 'source': 'Capability', 'source_entry': 'cap'}
    report_model = canonical_model({'datasets': [{'id': 'd1', 'name': 'Refresh source', 'fields': fields, 'rows': rows}], 'items': [cap], 'crossFilter': persisted_filter, 'crossFilters': [persisted_filter], 'nextId': 2})

    with tempfile.TemporaryDirectory(prefix='visembler-native-filtered-refresh-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                page = context.new_page()
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    cap_node = page.locator('.component[data-id="cap"]')
                    cap_node.focus(); cap_node.press('Enter'); panels(page, library=False, inspector=True)
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)', timeout=20000)
                    settled(page)

                    page.evaluate('''() => {
                      const reportId=window.CompanyUIVisualizerBridge.state().report_id;
                      const message={bridge_version:1,type:'dataset.filters_requested',payload:{report_id:reportId,dataset_id:'d1',session_id:`report:${reportId}`,filters:[{field:'product',operation:'equals',value:'P2'}]}};
                      document.querySelector('.cui-visualizer-root').dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:JSON.stringify(message)}));
                    }''')
                    page.locator('#activeFilters').wait_for(state='visible', timeout=20000)
                    assert 'P2' in page.locator('#activeFilters').inner_text()
                    settled(page)
                    filtered_before = page.evaluate('''() => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      return {revision:state.revision, filters:state.model.crossFilters||((state.model.crossFilter&&[state.model.crossFilter])||[]), text:document.querySelector('.component[data-id="cap"]')?.innerText||''};
                    }''')
                    assert filtered_before['filters'] and filtered_before['filters'][0]['value'] == 'P2'
                    assert 'n=4' in filtered_before['text']

                    refreshed = 'Measurement\tLSL\tUSL\tProduct\n30\t0\t40\tP2\n31\t0\t40\tP2\n30\t0\t40\tP2\n31\t0\t40\tP2\n1\t0\t40\tP1\n2\t0\t40\tP1\n1\t0\t40\tP1\n2\t0\t40\tP1'
                    page.evaluate('''(rowsText) => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      const reportId=state.report_id;
                      const rows=rowsText.split('\\n').slice(1).map(row=>row.split('\\t').map(value=>/^[-+]?\\d+(\\.\\d+)?$/.test(value)?Number(value):value));
                      const fields=[{id:'measurement',name:'Measurement',type:'number'},{id:'lsl',name:'LSL',type:'number'},{id:'usl',name:'USL',type:'number'},{id:'product',name:'Product',type:'categorical'}];
                      const message={bridge_version:1,type:'dataset.resource_refresh_requested',payload:{report_id:reportId,dataset_id:'d1',session_id:`report:${reportId}`,dataset:{id:'d1',name:'Refresh source',fields,rows},expected_revision:1,base_revision:state.revision,commit_id:'native-filtered-refresh',selected_only:false}};
                      document.querySelector('.cui-visualizer-root').dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:JSON.stringify(message)}));
                    }''', refreshed)
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge.state().model.datasets.find(dataset => dataset.resource_id)?.revision === 2', timeout=20000)
                    settled(page)
                    result = page.evaluate('''() => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      const analysis=window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap;
                      return {revision:state.model.datasets.find(dataset=>dataset.resource_id)?.revision, filters:state.model.crossFilters||((state.model.crossFilter&&[state.model.crossFilter])||[]), analysis, text:document.querySelector('.component[data-id="cap"]')?.innerText||''};
                    }''')
                    assert result['revision'] == 2
                    assert [(value['field'], value['value']) for value in result['filters']] == [('product', 'P2')]
                    assert result['analysis']['population'] == {'source_total': 8, 'filtered_total': 4, 'analyzed_rows': 4, 'complete': True}
                    assert result['analysis']['session']['filter_fingerprint']
                    assert result['analysis']['derived_statistics']['stats']['mean'] == 30.5
                    assert result['analysis']['derived_statistics']['stats']['cpk'] == pytest.approx(5.484827557301445)
                    assert 'n=4' in result['text'] and 'Cpu 5.485' in result['text']
                    assert 'mean 15.5' not in result['text']

                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    assert 'NaN' not in page.locator('body').inner_text()
                    assert 'Infinity' not in page.locator('body').inner_text()
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_compound_filtered_resource_refresh_and_post_refresh_convergence(tmp_path: Path):
    """Compound refresh, remove-one, and clear-all keep the same population."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    fields = [
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number'},
        {'id': 'lsl', 'name': 'LSL', 'type': 'number'},
        {'id': 'usl', 'name': 'USL', 'type': 'number'},
        {'id': 'tool', 'name': 'Tool', 'type': 'categorical'},
        {'id': 'chamber', 'name': 'Chamber', 'type': 'categorical'},
    ]
    rows = [[10, 0, 100, 'ETCH-01', 'B'], [11, 0, 100, 'ETCH-01', 'B'],
            [12, 0, 100, 'ETCH-01', 'A'], [13, 0, 100, 'ETCH-01', 'A'],
            [1, 0, 100, 'DEP-02', 'B'], [2, 0, 100, 'DEP-02', 'B'],
            [3, 0, 100, 'DEP-02', 'A'], [4, 0, 100, 'DEP-02', 'A']]
    cap = {
        **_cap_item('cap'), 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI',
        'title': 'Capability', 'dataset_id': 'd1', 'order': 0, 'x': 20, 'y': 20, 'w': 360, 'h': 180,
        'mapping': {'value': 'measurement', 'specification_low': 'lsl', 'specification_high': 'usl'},
    }
    compound = [
        {'field': 'tool', 'label': 'Tool', 'value': 'ETCH-01', 'source': 'Capability', 'source_entry': 'cap'},
        {'field': 'chamber', 'label': 'Chamber', 'value': 'B', 'source': 'Capability', 'source_entry': 'cap'},
    ]
    report_model = canonical_model({
        'datasets': [{'id': 'd1', 'name': 'Compound refresh source', 'fields': fields, 'rows': rows}],
        'items': [cap], 'crossFilter': compound[0], 'crossFilters': compound, 'nextId': 2,
    })

    with tempfile.TemporaryDirectory(prefix='visembler-native-compound-refresh-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    assert page.locator('#activeFilters').inner_text().count('=') == 2
                    cap_node = page.locator('.component[data-id="cap"]')
                    cap_node.focus(); cap_node.press('Enter'); panels(page, library=False, inspector=True)
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)', timeout=20000)
                    settled(page)

                    # Establish the compound session through the real resource
                    # request boundary before refreshing the resource.
                    page.evaluate('''() => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      const message={bridge_version:1,type:'dataset.filters_requested',payload:{report_id:state.report_id,dataset_id:'d1',session_id:`report:${state.report_id}`,filters:[{field:'tool',operation:'equals',value:'ETCH-01'},{field:'chamber',operation:'equals',value:'B'}]}};
                      document.querySelector('.cui-visualizer-root').dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:JSON.stringify(message)}));
                    }''')
                    page.wait_for_function('''() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap?.population?.filtered_total === 2''', timeout=20000)
                    settled(page)

                    refreshed = 'Measurement\tLSL\tUSL\tTool\tChamber\n40\t0\t100\tETCH-01\tB\n41\t0\t100\tETCH-01\tB\n42\t0\t100\tETCH-01\tA\n43\t0\t100\tETCH-01\tA\n1\t0\t100\tDEP-02\tB\n2\t0\t100\tDEP-02\tB\n3\t0\t100\tDEP-02\tA\n4\t0\t100\tDEP-02\tA'
                    page.evaluate('''(rowsText) => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      const rows=rowsText.split('\\n').slice(1).map(row=>row.split('\\t').map(value=>/^[-+]?\\d+(\\.\\d+)?$/.test(value)?Number(value):value));
                      const fields=[{id:'measurement',name:'Measurement',type:'number'},{id:'lsl',name:'LSL',type:'number'},{id:'usl',name:'USL',type:'number'},{id:'tool',name:'Tool',type:'categorical'},{id:'chamber',name:'Chamber',type:'categorical'}];
                      const message={bridge_version:1,type:'dataset.resource_refresh_requested',payload:{report_id:state.report_id,dataset_id:'d1',session_id:`report:${state.report_id}`,dataset:{id:'d1',name:'Compound refresh source',fields,rows},expected_revision:1,base_revision:state.revision,commit_id:'native-compound-refresh',selected_only:false}};
                      document.querySelector('.cui-visualizer-root').dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:JSON.stringify(message)}));
                    }''', refreshed)
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge.state().model.datasets.find(dataset => dataset.resource_id)?.revision === 2', timeout=20000)
                    settled(page)
                    result = page.evaluate('''() => ({
                      filters:window.CompanyUIVisualizerBridge.state().model.crossFilters||[],
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap,
                    })''')
                    assert [(value['field'], value['value']) for value in result['filters']] == [('tool', 'ETCH-01'), ('chamber', 'B')]
                    assert result['analysis']['population'] == {'source_total': 8, 'filtered_total': 2, 'analyzed_rows': 2, 'complete': True}
                    assert result['analysis']['derived_statistics']['stats']['mean'] == 40.5

                    page.evaluate("document.querySelector('#activeFilters [data-clear-active-filter=\\\"1\\\"]')?.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))")
                    page.wait_for_timeout(500)
                    after_remove_state = page.evaluate('''() => ({
                      filters:window.CompanyUIVisualizerBridge.state().model.crossFilters||[],
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap,
                      buttons:[...document.querySelectorAll('#activeFilters [data-clear-active-filter]')].map(node=>node.getAttribute('data-clear-active-filter')),
                    })''')
                    assert [(value['field'], value['value']) for value in after_remove_state['filters']] == [('tool', 'ETCH-01')], after_remove_state
                    settled(page)
                    removed = page.evaluate('''() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap''')
                    assert removed['population'] == {'source_total': 8, 'filtered_total': 4, 'analyzed_rows': 4, 'complete': True}
                    assert removed['derived_statistics']['stats']['mean'] == 41.5

                    page.locator('[data-clear-all-filters]').click()
                    page.wait_for_function('''() => {
                      const filters=window.CompanyUIVisualizerBridge.state().model.crossFilters||[];
                      return !filters.length && window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap?.population?.filtered_total === 8;
                    }''', timeout=20000)
                    settled(page)
                    cleared = page.evaluate('''() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap''')
                    assert cleared['population'] == {'source_total': 8, 'filtered_total': 8, 'analyzed_rows': 8, 'complete': True}
                    assert cleared['derived_statistics']['stats']['mean'] == 22
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    assert 'NaN' not in page.locator('body').inner_text()
                    assert 'Infinity' not in page.locator('body').inner_text()
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_compound_to_single_reset_and_reopen_keep_canonical_filter_state(tmp_path: Path):
    """Real chart selection replaces a compound session and reset clears both projections."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import panels, ready, settled
    finally:
        sys.path.remove(scripts)

    fields = [
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number'},
        {'id': 'lsl', 'name': 'LSL', 'type': 'number'},
        {'id': 'usl', 'name': 'USL', 'type': 'number'},
        {'id': 'tool', 'name': 'Tool', 'type': 'categorical'},
        {'id': 'chamber', 'name': 'Chamber', 'type': 'categorical'},
        {'id': 'product', 'name': 'Product', 'type': 'categorical'},
    ]
    rows = [
        [10, 0, 100, 'ETCH-01', 'B', 'P1'], [11, 0, 100, 'ETCH-01', 'B', 'P1'],
        [30, 0, 100, 'ETCH-01', 'B', 'P2'], [31, 0, 100, 'ETCH-01', 'B', 'P2'],
        [40, 0, 100, 'ETCH-01', 'A', 'P2'], [41, 0, 100, 'ETCH-01', 'A', 'P1'],
        [50, 0, 100, 'DEP-02', 'B', 'P1'], [51, 0, 100, 'DEP-02', 'A', 'P2'],
    ]
    cap_mapping = {'value': 'measurement', 'specification_low': 'lsl', 'specification_high': 'usl'}
    cap = {
        **_cap_item('cap'), 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI',
        'title': 'Capability', 'dataset_id': 'd1', 'mapping': cap_mapping,
        'order': 0, 'x': 20, 'y': 20, 'w': 360, 'h': 180,
    }
    chart = {
        'id': 'chart', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': 'Line Chart',
        'title': 'Product chart', 'dataset_id': 'd1',
        'mapping': {'category': 'product', 'value': 'measurement', 'x': 'product', 'y': 'measurement'},
        'visual': {'markers': True},
        'order': 1, 'x': 420, 'y': 20, 'w': 720, 'h': 360,
        'data': [['P1', 10], ['P2', 30]], 'rows': [{'label': 'P1', 'value': 10}, {'label': 'P2', 'value': 30}],
    }
    compound = [
        {'field': 'tool', 'label': 'Tool', 'value': 'ETCH-01', 'source': 'Product chart', 'source_entry': 'chart'},
        {'field': 'chamber', 'label': 'Chamber', 'value': 'B', 'source': 'Product chart', 'source_entry': 'chart'},
    ]
    report_model = canonical_model({
        'datasets': [{'id': 'd1', 'name': 'Filter transition source', 'fields': fields, 'rows': rows}],
        'items': [cap, chart], 'crossFilter': compound[0], 'crossFilters': compound, 'mode': 'free', 'nextId': 3,
    })

    with tempfile.TemporaryDirectory(prefix='visembler-native-filter-transition-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                page = context.new_page()
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    assert page.locator('#activeFilters').inner_text().count('=') == 2
                    cap_node = page.locator('.component[data-id="cap"]')
                    cap_node.focus(); cap_node.press('Enter'); panels(page, library=False, inspector=True)
                    page.locator('[data-dataset-action="bind-resource"]').click()
                    page.wait_for_function('() => window.CompanyUIVisualizerBridge.state().model.datasets.some(dataset => dataset.resource_id)', timeout=20000)
                    page.wait_for_function('() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap?.population?.filtered_total === 4', timeout=20000)
                    settled(page)

                    assert page.locator('.component[data-id="chart"] [data-behavior-point]').count() >= 3
                    p2_index = 2
                    page.locator('.component[data-id="chart"] [data-behavior-point]').nth(p2_index).dispatch_event('click')
                    page.wait_for_function('() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap?.derived_statistics?.stats?.mean === 38', timeout=20000)
                    settled(page)
                    single = page.evaluate('''() => {
                      const state=window.CompanyUIVisualizerBridge.state();
                      const analysis=window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap;
                      return {model:state.model,analysis};
                    }''')
                    assert [(value['field'], value['value']) for value in single['model']['crossFilters']] == [('product', 'P2')]
                    assert (single['model']['crossFilter']['field'], single['model']['crossFilter']['value']) == ('product', 'P2')
                    assert [(value['field'], value['value']) for value in single['analysis']['session_filters']] == [('product', 'P2')]
                    assert single['analysis']['population'] == {'source_total': 8, 'filtered_total': 4, 'analyzed_rows': 4, 'complete': True}
                    assert single['analysis']['derived_statistics']['stats']['mean'] == 38
                    assert single['analysis']['session']['filter_fingerprint']

                    export_model = json.loads(json.dumps(single['model']))
                    export_item = next(item for item in export_model['items'] if item['id'] == 'cap')
                    export_item['authoritative_analysis'] = single['analysis']
                    deck = Presentation(io.BytesIO(export_pptx(None, canonical_model(export_model))))
                    texts = '\n'.join(shape.text for slide in deck.slides for shape in slide.shapes if getattr(shape, 'has_text_frame', False))
                    assert str(single['analysis']['derived_statistics']['stats']['cpk']) in texts

                    page.reload(wait_until='domcontentloaded'); ready(page)
                    reopened = page.evaluate('''() => ({
                      model:window.CompanyUIVisualizerBridge.state().model,
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap,
                    })''')
                    assert [(value['field'], value['value']) for value in reopened['model']['crossFilters']] == [('product', 'P2')]
                    assert (reopened['model']['crossFilter']['field'], reopened['model']['crossFilter']['value']) == ('product', 'P2')
                    assert reopened['analysis']['population']['filtered_total'] == 4
                    assert reopened['analysis']['derived_statistics']['stats']['mean'] == 38

                    reopened_p2_index = 2
                    page.locator('.component[data-id="chart"] [data-behavior-point]').nth(reopened_p2_index).dispatch_event('click')
                    page.wait_for_function('() => !window.CompanyUIVisualizerBridge.state().model.crossFilters.length && window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap?.population?.filtered_total === 8', timeout=20000)
                    settled(page)
                    cleared = page.evaluate('''() => ({
                      model:window.CompanyUIVisualizerBridge.state().model,
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap,
                    })''')
                    assert cleared['model']['crossFilter'] is None
                    assert cleared['model']['crossFilters'] == []
                    assert cleared['analysis']['session_filters'] == []
                    assert cleared['analysis']['population'] == {'source_total': 8, 'filtered_total': 8, 'analyzed_rows': 8, 'complete': True}
                    assert cleared['analysis']['derived_statistics']['stats']['mean'] == 33

                    page.reload(wait_until='domcontentloaded'); ready(page)
                    reopened_clear = page.evaluate('''() => ({
                      model:window.CompanyUIVisualizerBridge.state().model,
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.cap,
                    })''')
                    assert reopened_clear['model']['crossFilter'] is None
                    assert reopened_clear['model']['crossFilters'] == []
                    assert reopened_clear['analysis']['population']['filtered_total'] == 8
                    assert reopened_clear['analysis']['derived_statistics']['stats']['mean'] == 33
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    assert 'NaN' not in page.locator('body').inner_text()
                    assert 'Infinity' not in page.locator('body').inner_text()
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    page.close()
                    browser.close()


def test_native_persisted_filter_scoping_is_dataset_safe_and_ambiguous_state_fails_closed(tmp_path: Path):
    """Reopen never assigns an inline predicate to an unrelated resource."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import ready
    finally:
        sys.path.remove(scripts)

    inline_fields = [
        {'id': 'category', 'name': 'Category', 'type': 'categorical'},
        {'id': 'value', 'name': 'Value', 'type': 'number'},
    ]
    capability_fields = [
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number'},
        {'id': 'lsl', 'name': 'LSL', 'type': 'number'},
        {'id': 'usl', 'name': 'USL', 'type': 'number'},
        {'id': 'product', 'name': 'Product', 'type': 'categorical'},
    ]
    inline_dataset = {'id': 'd-inline', 'fields': inline_fields, 'rows': [['A', 1], ['B', 2]]}
    inline_item = {
        'id': 'inline', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': 'Vertical Bar',
        'title': 'Inline source', 'dataset_id': 'd-inline', 'mapping': {'category': 'category', 'value': 'value'},
        'data': [['A', 1], ['B', 2]], 'rows': [{'label': 'A', 'value': 1}, {'label': 'B', 'value': 2}],
        'order': 0, 'x': 20, 'y': 20, 'w': 360, 'h': 180,
    }
    cap_mapping = {'value': 'measurement', 'specification_low': 'lsl', 'specification_high': 'usl'}

    with tempfile.TemporaryDirectory(prefix='visembler-native-filter-scope-') as data_dir:
        data_root = Path(data_dir) / 'native-data'
        store = DatasetResourceStore(data_root)
        resource_rows = [[10, 0, 100, 'P1'], [11, 0, 100, 'P1'], [30, 0, 100, 'P2'], [31, 0, 100, 'P2']]
        resource_a = store.create(owner='local-dev', dataset_id='resource-a', name='Resource A', fields=capability_fields, rows=resource_rows)
        resource_b = store.create(owner='local-dev', dataset_id='resource-b', name='Resource B', fields=capability_fields, rows=resource_rows)

        def resource_dataset(resource, dataset_id):
            preview = store.preview(resource['dataset_id'])
            return {'id': dataset_id, 'resource_id': resource['dataset_id'], 'revision': 1, 'external': True,
                    'fields': preview['fields'], 'rows': preview['rows'], 'row_count': preview['row_count']}

        def cap_item(item_id, dataset_id, title='Capability'):
            return {
                **_cap_item(item_id), 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI',
                'title': title, 'dataset_id': dataset_id, 'mapping': cap_mapping,
                'order': 1, 'x': 420, 'y': 20, 'w': 360, 'h': 180,
            }

        inline_filter = {'field': 'category', 'label': 'Category', 'value': 'A', 'source': 'Inline source', 'source_entry': 'inline'}
        mixed_cap = cap_item('cap-mixed', 'd-resource')
        mixed_model = canonical_model({
            'datasets': [inline_dataset, resource_dataset(resource_a, 'd-resource')],
            'items': [inline_item, mixed_cap], 'crossFilter': inline_filter, 'crossFilters': [inline_filter], 'nextId': 3,
        })
        exact_filter = {'field': 'product', 'label': 'Product', 'value': 'P2', 'source': 'Capability', 'source_entry': 'cap-exact'}
        exact_cap = cap_item('cap-exact', 'd-exact')
        exact_model = canonical_model({
            'datasets': [resource_dataset(resource_a, 'd-exact')], 'items': [exact_cap],
            'crossFilter': exact_filter, 'crossFilters': [exact_filter], 'nextId': 2,
        })
        legacy_filter = {'field': 'product', 'label': 'Product', 'value': 'P2', 'source': 'Capability'}
        legacy_cap = cap_item('cap-legacy', 'd-legacy')
        legacy_model = canonical_model({
            'datasets': [resource_dataset(resource_a, 'd-legacy')], 'items': [legacy_cap],
            'crossFilter': legacy_filter, 'nextId': 2,
        })
        ambiguous_filter = {'field': 'product', 'label': 'Product', 'value': 'P2', 'source': 'Capability'}
        ambiguous_a = cap_item('cap-a', 'd-a')
        ambiguous_b = cap_item('cap-b', 'd-b')
        ambiguous_model = canonical_model({
            'datasets': [resource_dataset(resource_a, 'd-a'), resource_dataset(resource_b, 'd-b')],
            'items': [ambiguous_a, ambiguous_b], 'crossFilter': ambiguous_filter, 'nextId': 3,
        })

        with NativeHost(ROOT, data_root) as host:
            report_ids = [
                host.create(model=mixed_model), host.create(model=exact_model),
                host.create(model=legacy_model), host.create(model=ambiguous_model),
            ]
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_ids[0]}', wait_until='domcontentloaded')
                    ready(page)
                    mixed = page.evaluate('''() => ({
                      model:window.CompanyUIVisualizerBridge.state().model,
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.['cap-mixed'],
                    })''')
                    assert [(value['field'], value['value']) for value in mixed['model']['crossFilters']] == [('category', 'A')]
                    assert mixed['analysis']['session_filters'] == []
                    assert mixed['analysis']['population'] == {'source_total': 4, 'filtered_total': 4, 'analyzed_rows': 4, 'complete': True}

                    page.goto(f'{host.url}/visualizer?report={report_ids[1]}', wait_until='domcontentloaded'); ready(page)
                    exact = page.evaluate('''() => window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.['cap-exact']''')
                    assert [(value['field'], value['value']) for value in exact['session_filters']] == [('product', 'P2')]
                    assert exact['population']['filtered_total'] == 2

                    page.goto(f'{host.url}/visualizer?report={report_ids[2]}', wait_until='domcontentloaded'); ready(page)
                    legacy = page.evaluate('''() => ({
                      model:window.CompanyUIVisualizerBridge.state().model,
                      analysis:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.['cap-legacy'],
                    })''')
                    assert [(value['field'], value['value']) for value in legacy['model']['crossFilters']] == [('product', 'P2')]
                    assert [(value['field'], value['value']) for value in legacy['analysis']['session_filters']] == [('product', 'P2')]
                    assert legacy['analysis']['population']['filtered_total'] == 2

                    page.goto(f'{host.url}/visualizer?report={report_ids[3]}', wait_until='domcontentloaded'); ready(page)
                    ambiguous = page.evaluate('''() => ({
                      a:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.['cap-a'],
                      b:window.__VIZ_PROD__?.ui?.authoritativeAnalyses?.['cap-b'],
                    })''')
                    for result in (ambiguous['a'], ambiguous['b']):
                        assert result['ok'] is False
                        assert result['errors'][0]['code'] == 'SESSION_CONVERGENCE'
                        assert result['derived_statistics'] == {}
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    page.close()
                    browser.close()


def test_native_request_generations_guard_bootstrap_error_and_report_switch(tmp_path: Path):
    """The real Editor receiver keeps one logical generation across projections."""
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost
        from run_editor_workflows import ready
    finally:
        sys.path.remove(scripts)

    fields = [{'id': 'value', 'name': 'Value', 'type': 'number'}]
    report_model = canonical_model({
        'datasets': [{'id': 'd1', 'name': 'Generation source', 'fields': fields, 'rows': [[1], [2]], 'revision': 1}],
        'items': [], 'nextId': 1,
    })
    with tempfile.TemporaryDirectory(prefix='visembler-native-generations-') as data_dir:
        with NativeHost(ROOT, Path(data_dir) / 'native-data') as host:
            report_id = host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options = {'headless': True}
                if executable:
                    options.update(executable_path=executable, args=['--no-sandbox'])
                browser = instance.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                errors, failed_requests = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.on('requestfailed', lambda request: failed_requests.append((request.url, request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}', wait_until='domcontentloaded')
                    ready(page)
                    evidence = page.evaluate('''() => {
                      const bridge=window.CompanyUIVisualizerBridge, prod=window.__VIZ_PROD__;
                      const initial=bridge.state(), reportA=initial.report_id, session=`report:${reportA}`;
                      const key=JSON.stringify([reportA,'d1',session]);
                      prod.ui.requestGenerations[key]={current:21,report_id:reportA,dataset_id:'d1',session_id:session,filters:[],checkVisible:false};
                      const bootstrap=(requestId,reportId=reportA,revision=2,filterValue='B')=>{
                        const model=structuredClone(initial.model); model.datasets[0].revision=revision;
                        model.crossFilter={field:'value',label:'Value',value:filterValue,source_entry:'none'};
                        model.crossFilters=[model.crossFilter];
                        return {bridge_version:1,type:'report.bootstrap',payload:{report_id:reportId,revision,model,analysis_results:{},request_id:requestId,request_dataset_id:'d1',request_session_id:session}};
                      };
                      bridge.receive(bootstrap(21));
                      const accepted={revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value,disposableRequests:Object.keys(prod.ui.datasetRequests).length};
                      bridge.receive(bootstrap(20,reportA,2,'A'));
                      const afterOldBootstrap={revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value};
                      bridge.receive({bridge_version:1,type:'dataset.binding_result',payload:{report_id:reportA,dataset_id:'d1',session_id:session,request_id:1,result:{rows:[[9]],revision:2,source_revision:2},analysis_results:{}}});
                      const collision={revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value};
                      bridge.receive({bridge_version:1,type:'report.error',payload:{report_id:reportA,dataset_id:'d1',session_id:session,request_dataset_id:'d1',request_session_id:session,request_id:20,message:'stale diagnostic'}});
                      const staleError={revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value,persistence:prod.ui.persistenceFailure?.message||null};
                      bridge.receive({bridge_version:1,type:'report.error',payload:{report_id:reportA,dataset_id:'d1',session_id:session,request_dataset_id:'d1',request_session_id:session,request_id:21,message:'current diagnostic'}});
                      const currentError={revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value,persistence:prod.ui.persistenceFailure?.message||null};
                      const reportBModel=structuredClone(initial.model);
                      bridge.receive({bridge_version:1,type:'report.bootstrap',payload:{report_id:'report-b',revision:3,model:reportBModel,analysis_results:{}}});
                      const switched={report:bridge.state().report_id,revision:bridge.state().revision};
                      bridge.receive(bootstrap(21,reportA,2,'A'));
                      const lateAfterSwitch={report:bridge.state().report_id,revision:bridge.state().revision,filter:bridge.state().model.crossFilter?.value??null};
                      return {accepted,afterOldBootstrap,collision,staleError,currentError,switched,lateAfterSwitch};
                    }''')
                    assert evidence == {
                        'accepted': {'revision': 2, 'filter': 'B', 'disposableRequests': 0},
                        'afterOldBootstrap': {'revision': 2, 'filter': 'B'},
                        'collision': {'revision': 2, 'filter': 'B'},
                        'staleError': {'revision': 2, 'filter': 'B', 'persistence': None},
                        'currentError': {'revision': 2, 'filter': 'B', 'persistence': 'current diagnostic'},
                        'switched': {'report': 'report-b', 'revision': 3},
                        'lateAfterSwitch': {'report': 'report-b', 'revision': 3, 'filter': None},
                    }
                    assert not errors, errors
                    assert not failed_requests, failed_requests
                finally:
                    context.close()
                    browser.close()


def test_native_invalid_statistical_reports_fail_closed_in_editor_preview_hub_and_export(tmp_path: Path):
    playwright = pytest.importorskip('playwright.sync_api')
    scripts = str(ROOT / 'scripts' / 'release_checks')
    import sys
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost, load_editor
        from run_editor_workflows import ready
    finally:
        sys.path.remove(scripts)

    cap_fields=_cap_fields()
    x_fields=[{'id':'subgroup','name':'Subgroup','type':'categorical'},{'id':'measurement','name':'Measurement','type':'number'}]
    d_fields=[{'id':'factor_a','name':'Factor A','type':'categorical'},{'id':'factor_b','name':'Factor B','type':'categorical'},{'id':'response','name':'Response','type':'number'}]
    cap_item={**_cap_item('cap'),'type':'metric','engine':'MetricEngine','element':'Hero KPI','title':'Capability','dataset_id':'cap-dataset','order':0,'x':20,'y':20,'w':360,'h':180,'value':84.2}
    x_mapping={'subgroup':'subgroup','value':'measurement'}
    x_item={'id':'xbar','type':'chart','engine':'EngineeringChartEngine','element':'Xbar-R Chart','title':'Xbar-R','dataset_id':'x-dataset','mapping':x_mapping,'analysis_recipe':{'id':'xbar-r-process-review','mapping':x_mapping},'order':1,'x':420,'y':20,'w':520,'h':300}
    d_mapping={'factor_a':'factor_a','factor_b':'factor_b','response':'response'}
    d_item={'id':'doe','type':'chart','engine':'EngineeringChartEngine','element':'DOE Interaction Plot','title':'DOE Interaction','dataset_id':'d-dataset','mapping':d_mapping,'analysis_recipe':{'id':'doe-response-review','mapping':d_mapping},'order':2,'x':20,'y':340,'w':920,'h':300}
    report_model=canonical_model({'datasets':[
        {'id':'cap-dataset','name':'Capability','fields':cap_fields,'rows':[[1,0,10],[1,0,10]]},
        {'id':'x-dataset','name':'Xbar','fields':x_fields,'rows':[['A',1],['A',2],['B',3],['B',4],['B',5]]},
        {'id':'d-dataset','name':'DOE','fields':d_fields,'rows':[['A','L',1],['A','H',2],['B','L',3]]},
    ],'items':[cap_item,x_item,d_item],'nextId':4})

    with tempfile.TemporaryDirectory(prefix='visembler-native-invalid-statistical-') as data_dir:
        with NativeHost(ROOT,Path(data_dir)/'native-data') as host:
            report_id=host.create(model=report_model)
            with playwright.sync_playwright() as instance:
                executable=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
                options={'headless':True}
                if executable: options.update(executable_path=executable,args=['--no-sandbox'])
                browser=instance.chromium.launch(**options); context=browser.new_context(viewport={'width':1440,'height':1000})
                page=context.new_page(); errors=[]; failed=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
                page.on('requestfailed',lambda request:failed.append((request.url,request.failure)))
                try:
                    page.goto(f'{host.url}/visualizer?report={report_id}',wait_until='domcontentloaded'); ready(page); page.wait_for_timeout(700)
                    body='\n'.join(page.locator('.component').all_inner_texts())
                    assert body.count('Analysis needs attention')>=3
                    for forbidden in ('84.2','Baseline','Pilot','Validation','1.7','99'):
                        assert forbidden not in body
                    page.locator('#previewBtn').click(); page.wait_for_timeout(300)
                    preview='\n'.join(page.locator('.component').all_inner_texts())
                    assert preview.count('Analysis needs attention')>=3
                    assert '84.2' not in preview and 'Baseline' not in preview and 'Pilot' not in preview
                    page.locator('#previewExit').click()
                    page.locator('#exportBtn').click()
                    page.locator('#exportPptAction').click(); page.wait_for_timeout(300)
                    assert 'Resolve export-blocking validation issues first' in page.locator('body').inner_text()
                    page.goto(f'{host.url}/visualizer/reports',wait_until='domcontentloaded'); page.wait_for_timeout(1000)
                    hub=page.locator('[data-testid="report-card"]').filter(has_text='Analysis needs attention')
                    assert hub.count()==1, page.locator('body').inner_text()
                    thumb=hub.locator('.cui-report-thumb').inner_text()
                    assert 'Analysis needs attention' in thumb
                    assert '84.2' not in thumb and 'Baseline' not in thumb and 'Pilot' not in thumb
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    assert not errors, errors
                    assert not failed, failed
                finally:
                    context.close(); browser.close()
