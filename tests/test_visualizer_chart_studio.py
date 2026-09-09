"""Focused contract tests for the offline Chart Studio adapter."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def node(source: str) -> dict:
    result = subprocess.run(
        ['node', '--input-type=module', '--eval', source],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(result.stdout)


def test_chart_studio_typed_data_and_render_contract() -> None:
    observed = node(r'''
      import * as c from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
      const pasted = 'time\tmeasurement\tseries\n2026-01-01\t0\tRun A\n2026-01-02\t"0"\tRun A\n2026-01-03\t""\tRun B\n2026-01-04\t\tRun B\n2026-01-05\t12\tRun B';
      let model=c.updateChartData(c.normalizeChartModel({chart_type:'Line Chart'}),pasted);
      model=c.mapRole(model,'series','series_3');
      const values=model.dataset.rows.map(row=>row[1]);
      const line=c.renderChartSvg(model);
      const area=c.renderChartSvg(c.switchChartType(model,'Area Chart'));
      const recipe=c.saveRecipe(model,'Trend recipe');
      const applied=c.applyRecipeToModel(c.switchChartType(model,'Line Chart'),recipe.recipe);
      model=c.addReferenceLine(model,10,'Target');
      model=c.addReferenceBand(model,2,8,'Expected');
      console.log(JSON.stringify({
        types:values.map(value=>value===null?'null':typeof value), values,
        recommendations:model.recommendations.length, svg:line.includes('cs-axis-label')&&line.includes('cs-legend'),
        area:area.includes('cs-chart-svg'), recipe:applied.recipe?.name==='Trend recipe',
        references:model.reference_lines.length===1&&model.reference_bands.length===1,
      }));
    ''')
    assert observed == {
        'types': ['number', 'string', 'string', 'null', 'number'],
        'values': [0, '0', '', None, 12],
        'recommendations': 6,
        'svg': True,
        'area': True,
        'recipe': True,
        'references': True,
    }


def test_chart_studio_data_lab_operations_are_bounded_and_typed() -> None:
    observed = node(r'''
      import * as c from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
      let model=c.updateChartData(c.normalizeChartModel({chart_type:'Line Chart'}),'category\tvalue\nA\t1\nB\t2\nC\t3');
      model=c.insertRow(model,1,['Inserted',0]);
      model=c.insertColumn(model,1,'Status','string');
      model=c.renameColumn(model,1,'State');
      model=c.deriveColumn(model,'value_2','Scaled',2,1);
      model=c.sortRows(model,'value_2','desc');
      model=c.topRows(model,'value_2',3);
      model=c.filterRows(model,'category_1','contains','A');
      console.log(JSON.stringify({fields:model.dataset.fields.map(field=>field.name),rows:model.dataset.rows,revision:model.dataset.revision}));
    ''')
    assert observed['fields'] == ['category', 'State', 'value', 'Scaled']
    assert observed['rows'] == [['A', None, 1, 3]]
    assert observed['revision'] >= 8


def test_chart_studio_performance_fixtures_record_timings() -> None:
    observed = node(r'''
      import * as c from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
      const lineRows=Array.from({length:10000},(_,i)=>[`2026-01-${String((i%28)+1).padStart(2,'0')}`,i%97,`S${i%10}`]);
      const dataset={id:'perf',fields:[{id:'time',name:'time',type:'date'},{id:'value',name:'value',type:'number'},{id:'series',name:'series',type:'categorical'}],rows:lineRows};
      const line=c.normalizeChartModel({chart_type:'Line Chart',dataset,mapping:{x:'time',y:'value',series:'series'}});
      const started=performance.now();c.renderChartSvg(line,{width:900,height:480});const lineMs=performance.now()-started;
      const waferRows=Array.from({length:2500},(_,i)=>[i%50,Math.floor(i/50),i%101]);
      const wafer=c.normalizeChartModel({chart_type:'Wafer Map',dataset:{id:'wafer',fields:[{id:'x',name:'die_x',type:'number'},{id:'y',name:'die_y',type:'number'},{id:'v',name:'value',type:'number'}],rows:waferRows},mapping:{die_x:'x',die_y:'y',value:'v'}});
      const waferStart=performance.now();c.renderChartSvg(wafer,{width:900,height:520});const waferMs=performance.now()-waferStart;
      console.log(JSON.stringify({line_rows:line.dataset.rows.length,wafer_rows:wafer.dataset.rows.length,line_ms:Number(lineMs.toFixed(2)),wafer_ms:Number(waferMs.toFixed(2))}));
    ''')
    assert observed['line_rows'] == 10000
    assert observed['wafer_rows'] == 2500
    assert observed['line_ms'] >= 0 and observed['wafer_ms'] >= 0
