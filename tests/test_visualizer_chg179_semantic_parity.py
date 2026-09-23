from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
from pptx import Presentation

from company_ui.products.visualizer.domain import VisualizerContractError, canonical_model
from company_ui.products.visualizer.metric_format import format_metric_value, metric_format_issues
from company_ui.products.visualizer.ppt_service import bound_export_items, export_pptx


ROOT = Path(__file__).resolve().parents[1]


def node(source: str) -> dict:
    result = subprocess.run(
        ['node', '--input-type=module', '-e', source], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def test_browser_formatter_preserves_metric_semantics_and_legacy_models() -> None:
    result = node(r'''
import {formatMetricValue,metricFormattingIssues,normalizeMetricFormat} from './company_ui/products/visualizer/assets/authoring_format.mjs';
const cases={
  compactUnit:formatMetricValue(48.2,{unit:'M'}),
  currency:formatMetricValue(48.2,{value_format:'currency',currency_symbol:'$',decimals:1}),
  percentDataWins:formatMetricValue(.276,{value_format:'currency',unit:'M'},{unit:'%',format:{kind:'percent',percent_scale:'ratio'}}),
  count:formatMetricValue(34,{}, {unit:'contacts'}),
  zero:formatMetricValue(0,{value_format:'currency'}),
  negative:formatMetricValue(-2.35,{metric_format:{kind:'currency',prefix:'$',precision:2}}),
  large:formatMetricValue(1234567.8,{metric_format:{kind:'currency',prefix:'$',precision:2}}),
  explicitPrecision:formatMetricValue(3.456,{metric_format:{kind:'number',precision:3}}),
  missing:formatMetricValue(null,{metric_format:{null_display:'N/A'}}),
  noUnit:formatMetricValue(48.2,{value_format:'currency',unit:'M'},{unit:''}),
  compactScale:formatMetricValue(48200000,{metric_format:{kind:'number',precision:1,compact_divisor:1000000,compact_unit:'M'}}),
  legacyUnitPreserved:formatMetricValue(48.2,{value_format:'currency',currency_symbol:'$',unit:'M'}),
};
const contradiction=metricFormattingIssues({value_format:'currency'},{unit:'%',format:{kind:'percent',percent_scale:'ratio'}});
const corrected=metricFormattingIssues({value_format:'currency',metric_format:{kind:'percent',percent_scale:'ratio',prefix:'',suffix:'%'}},{unit:'%',format:{kind:'percent',percent_scale:'ratio'}});
const droppedCompact=metricFormattingIssues({metric_format:{kind:'number',compact_unit:'M',suffix:''}});
const legacy=normalizeMetricFormat({value_format:'percent',decimals:1});
console.log(JSON.stringify({cases,contradiction,corrected,droppedCompact,legacy}));
''')
    assert result['cases'] == {
        'compactUnit': '48.2 M',
        'currency': '$48.2',
        'percentDataWins': '27.6%',
        'count': '34 contacts',
        'zero': '$0',
        'negative': '-$2.35',
        'large': '$1,234,567.80',
        'explicitPrecision': '3.456',
        'missing': 'N/A',
        'noUnit': '48.2',
        'compactScale': '48.2 M',
        'legacyUnitPreserved': '$48.2 M',
    }
    assert any('currency formatting' in issue for issue in result['contradiction'])
    assert result['corrected'] == []
    assert any('Configured compact unit' in issue for issue in result['droppedCompact'])
    assert result['legacy']['kind'] == 'percent' and result['legacy']['precision'] == 1


@pytest.mark.parametrize(
    ('value', 'entry', 'field', 'expected'),
    [
        (48.2, {'unit': 'M'}, None, '48.2 M'),
        (48.2, {'value_format': 'currency', 'currency_symbol': '$', 'decimals': 1}, None, '$48.2'),
        (.276, {'value_format': 'currency', 'unit': 'M'}, {'unit': '%', 'format': {'kind': 'percent', 'percent_scale': 'ratio'}}, '27.6%'),
        (34, {}, {'unit': 'contacts'}, '34 contacts'),
        (0, {'value_format': 'currency'}, None, '$0'),
        (-2.35, {'metric_format': {'kind': 'currency', 'prefix': '$', 'precision': 2}}, None, '-$2.35'),
        (1234567.8, {'metric_format': {'kind': 'currency', 'prefix': '$', 'precision': 2}}, None, '$1,234,567.80'),
        (3.456, {'metric_format': {'kind': 'number', 'precision': 3}}, None, '3.456'),
        (None, {'metric_format': {'null_display': 'N/A'}}, None, 'N/A'),
        (48.2, {'value_format': 'currency', 'unit': 'M'}, {'unit': ''}, '48.2'),
        (48200000, {'metric_format': {'kind': 'number', 'precision': 1, 'compact_divisor': 1000000, 'compact_unit': 'M'}}, None, '48.2 M'),
        (48.2, {'value_format': 'currency', 'currency_symbol': '$', 'unit': 'M'}, None, '$48.2 M'),
    ],
)
def test_python_export_formatter_matches_browser_golden(value, entry, field, expected) -> None:
    assert format_metric_value(value, entry, field) == expected


def test_explicit_percent_override_resolves_legacy_currency_conflict() -> None:
    legacy = {'value_format': 'currency', 'unit': 'M'}
    percent = {'unit': '%', 'format': {'kind': 'percent', 'percent_scale': 'ratio'}}
    corrected = {'value_format': 'currency', 'unit': 'M', 'metric_format': {'kind': 'percent', 'percent_scale': 'ratio', 'prefix': '', 'suffix': '%'}}
    assert format_metric_value(.276, corrected, percent) == '27.6%'
    assert any('currency formatting' in issue for issue in metric_format_issues(legacy, percent))
    assert metric_format_issues(corrected, percent) == []


def test_dropped_explicit_compact_unit_is_a_material_format_issue() -> None:
    entry = {'metric_format': {'kind': 'number', 'compact_unit': 'M', 'suffix': ''}}
    issues = metric_format_issues(entry)
    assert len(issues) == 1
    assert 'Configured compact unit “M” is missing' in issues[0]


def test_data_first_categories_survive_chart_studio_reload_refresh_and_export() -> None:
    result = node(r'''
import {intakeText,planDataFirstCreation} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {chartModelFromEntry,chartToEntry,renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
import {projectDataEntry} from './company_ui/products/visualizer/assets/authoring_projection.mjs';
import {planDatasetRefresh} from './company_ui/products/visualizer/assets/authoring_dataset_refresh.mjs';
const first=intakeText('Month\tValue\nJan\t0\nFeb\t2\nMar\t3');
const inferred=first.candidate_mappings.find(item=>item.view==='line')?.mapping;
const plan=planDataFirstCreation({intake:first,view:'line',mapping:inferred,datasetId:'d1'});
const ds=plan.dataset,created={id:'c1',type:'chart',engine:'CoreChartEngine',element:'Line Chart',title:'Line Chart',dataset_id:'d1',view_type:plan.view,mapping:plan.mapping};
const studio=chartModelFromEntry(created,ds);const saved=chartToEntry(created,studio);
const reloaded=chartModelFromEntry(saved,ds);const svg=renderChartSvg(reloaded);
const refreshed=intakeText('Value\tMonth\n0\tJan\n2.5\tFeb\n3\tMar');
const refresh=planDatasetRefresh({dataset:ds,intake:refreshed,items:[created],selectedId:created.id,viewForEntry:()=> 'line'});
const rebound=refresh.mappings[0].mapping;
const projected=projectDataEntry({...created,mapping:rebound},{...refreshed,id:'d1'},rebound);
console.log(JSON.stringify({mapping:created.mapping,savedMapping:saved.mapping,reloadedMapping:reloaded.mapping,svgHasLabels:['Jan','Feb','Mar'].every(label=>svg.includes(label)),refreshValid:refresh.valid,refreshedMapping:rebound,projected:projected.data}));
''')
    assert result['mapping']['x'] == 'month_1'
    assert result['savedMapping']['x'] == 'month_1'
    assert result['reloadedMapping']['x'] == 'month_1'
    assert result['svgHasLabels'] is True
    assert result['refreshValid'] is True
    assert result['refreshedMapping']['x'] == 'month_2'
    assert result['projected'] == [['Jan', 0], ['Feb', 2.5], ['Mar', 3]]


def test_powerpoint_projection_keeps_category_labels_and_formats_bound_metric() -> None:
    report = canonical_model(
        {
            'datasets': [
                {
                    'id': 'd1',
                    'name': 'Monthly',
                    'revision': 1,
                    'fields': [
                        {'id': 'month', 'name': 'Month', 'type': 'categorical'},
                        {'id': 'value', 'name': 'Yield', 'type': 'number', 'unit': '%', 'format': {'kind': 'percent', 'percent_scale': 'ratio'}},
                    ],
                    'rows': [['Jan', .276], ['Feb', 0], ['Mar', None]],
                }
            ],
            'items': [
                        {'id': 'chart', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': 'Line Chart', 'order': 0, 'dataset_id': 'd1', 'mapping': {'x': 'month', 'y': 'value'}},
                        {'id': 'metric', 'type': 'metric', 'engine': 'MetricEngine', 'element': 'Hero KPI', 'order': 1, 'dataset_id': 'd1', 'mapping': {'value': 'value'}, 'value_format': 'currency', 'unit': 'M'},
            ],
        }
    )
    projected = bound_export_items(report)
    assert projected[0]['data'] == [('Jan', .276), ('Feb', 0), ('Mar', None)]
    assert projected[1]['value'] == 0
    assert format_metric_value(projected[1]['value'], projected[1], projected[1]['_metric_field']) == '0%'
    with pytest.raises(VisualizerContractError, match='Percent data is paired with currency formatting'):
        export_pptx(None, report)


def test_dataset_resource_field_validation_keeps_metric_format_metadata(tmp_path) -> None:
    from company_ui.products.visualizer.dataset_resources import _validate_fields

    fields = _validate_fields(
        [{'id': 'yield', 'name': 'Yield', 'type': 'number', 'unit': '%', 'format': {'kind': 'percent', 'percent_scale': 'ratio'}}]
    )
    assert fields[0]['unit'] == '%'
    assert fields[0]['format'] == {'kind': 'percent', 'percent_scale': 'ratio'}
