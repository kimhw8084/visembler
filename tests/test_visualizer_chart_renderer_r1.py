"""Deterministic CHG-137 R1 chart geometry and authority fixtures."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def node(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_irregular_numeric_and_time_domains_are_proportional() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, chartRenderPlan} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const numericDataset={id:'numeric',fields:[{id:'x',name:'X',type:'number'},{id:'y',name:'Y',type:'number'}],rows:[[0,10],[2,12],[10,14]]};
        const timeDataset={id:'time',fields:[{id:'t',name:'Timestamp',type:'datetime'},{id:'y',name:'Y',type:'number'}],rows:[['2026-01-01T00:00:00Z',10],['2026-01-02T00:00:00Z',12],['2026-01-10T00:00:00Z',14]]};
        const numeric=chartRenderPlan(chartModelFromEntry({element:'Scatter Plot',mapping:{x:'x',y:'y'},dataset:numericDataset},numericDataset),{width:900,height:480});
        const time=chartRenderPlan(chartModelFromEntry({element:'Line Chart',mapping:{x:'t',y:'y'},dataset:timeDataset},timeDataset),{width:900,height:480});
        const nx=numeric.data.rows.map(row=>numeric.xAt(row.xValue,'numeric'));
        const tx=time.data.rows.map(row=>time.xAt(row.xValue,'numeric'));
        console.log(JSON.stringify({numeric_domain:numeric.xDomain,time_domain:time.xDomain,numeric_gap:[nx[1]-nx[0],nx[2]-nx[1]],time_gap:[tx[1]-tx[0],tx[2]-tx[1]],x_ticks:numeric.xTicks.length}));
        ''',
    )
    assert observed["numeric_domain"] == {"min": 0, "max": 10}
    assert observed["time_gap"][1] > observed["time_gap"][0] * 5
    assert observed["numeric_gap"][1] > observed["numeric_gap"][0] * 3
    assert 2 <= observed["x_ticks"] <= 7


def test_bar_domains_baselines_stacks_and_percent_normalization_are_truthful() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, chartRenderPlan} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'cat',name:'Category',type:'categorical'},{id:'value',name:'Value',type:'number'},{id:'series',name:'Series',type:'categorical'}];
        const make=(rows,visual={},axes={})=>{const dataset={id:'bars',fields,rows};return chartRenderPlan(chartModelFromEntry({element:'Vertical Bar',mapping:{category:'cat',value:'value',series:'series'},visual,axes,dataset},dataset),{width:860,height:460});};
        const positive=make([['A',2,'A'],['B',5,'A']]);
        const negative=make([['A',-2,'A'],['B',-5,'A']]);
        const mixed=make([['A',-2,'A'],['B',5,'A']]);
        const stacked=make([['A',4,'one'],['A',3,'two'],['B',-2,'one'],['B',-5,'two']],{barMode:'stacked'});
        const percent=make([['A',4,'one'],['A',6,'two'],['B',1,'one'],['B',3,'two']],{barMode:'percent'});
        const bounded=make([['A',2,'A'],['B',5,'A']],{}, {y:{min:-10,max:10,zeroBaseline:true}});
        console.log(JSON.stringify({positive:positive.yDomain,negative:negative.yDomain,mixed:mixed.yDomain,stacked:stacked.yDomain,totals:stacked.stack.totals,percent:percent.yDomain,percent_display:percent.stack.stacks.map(stack=>stack.map(point=>point.display)),bounded:bounded.yDomain}));
        ''',
    )
    assert observed["positive"]["min"] == 0
    assert observed["negative"]["max"] == 0
    assert observed["mixed"]["min"] < 0 < observed["mixed"]["max"]
    assert observed["totals"] == [{"positive": 7, "negative": 0}, {"positive": 0, "negative": 7}]
    assert observed["stacked"]["min"] == -7 and observed["stacked"]["max"] == 7
    assert observed["percent"] == {"min": 0, "max": 1}
    assert observed["percent_display"][0][0] == 0.4 and observed["percent_display"][1][0] == 0.6
    assert observed["bounded"] == {"min": -10, "max": 10}


def test_missing_policy_keeps_zero_distinct_and_area_uses_governed_baseline() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, chartRenderPlan, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const dataset={id:'missing',fields:[{id:'cat',name:'Category',type:'categorical'},{id:'value',name:'Value',type:'number'}],rows:[['A',0],['B',null],['C',4]]};
        const plan=(policy)=>chartRenderPlan(chartModelFromEntry({element:'Line Chart',mapping:{x:'cat',y:'value'},visual:{missingPolicy:policy},dataset},dataset),{width:800,height:420});
        const gap=plan('gap'),zero=plan('zero'),drop=plan('drop');
        const area=chartModelFromEntry({element:'Area Chart',mapping:{x:'cat',y:'value'},axes:{y:{zeroBaseline:false},x:{}},dataset},dataset);
        const svg=renderChartSvg(area,{width:800,height:420});
        console.log(JSON.stringify({gap:gap.data.rows.map(row=>row.y),zero:zero.data.rows.map(row=>row.y),drop:drop.data.rows.map(row=>row.y),area_has_baseline:svg.includes('cs-area')&&svg.includes('M'),area_has_infinity:/NaN|Infinity/.test(svg)}));
        ''',
    )
    assert observed["gap"] == [0, None, 4]
    assert observed["zero"] == [0, 0, 4]
    assert observed["drop"] == [0, 4]
    assert observed["area_has_baseline"] is True
    assert observed["area_has_infinity"] is False


def test_adaptive_layout_colors_legend_secondary_axis_formatting_and_annotations() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, chartRenderPlan, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'cat',name:'Very long category label',type:'categorical'},{id:'value',name:'Primary measurement',type:'number'},{id:'secondary',name:'Secondary measurement',type:'number'},{id:'series',name:'Series',type:'categorical'}];
        const rows=Array.from({length:12},(_,i)=>[`Category ${i+1} with deliberately long name`,i+1,(i+1)*100,`Series ${String(i+1).padStart(2,'0')}`]);
        const dataset={id:'dense',fields,rows};
            const model=chartModelFromEntry({element:'Line Chart',mapping:{x:'cat',y:'value',series:'series'},axes:{x:{rotation:45,tickCount:4,title:'Long category axis title'},y:{tickCount:7,title:'Primary units',prefix:'$',precision:2},secondaryY:{tickCount:4,title:'Secondary units',unit:'ms'}},legend:{position:'right',orientation:'vertical',order:'label-desc'},series:rows.map((row,index)=>({key:row[3],label:row[3],axis:index===11?'secondary':'primary',color:`#${(index+1).toString(16).padStart(6,'0')}`})),annotations:[{id:'a1',text:'Boundary annotation',x:.98,y:.05}],reference_lines:[{id:'r1',value:6,label:'Target'}],reference_bands:[{id:'b1',low:3,high:8,label:'Expected'}],dataset},dataset);
        const plan=chartRenderPlan(model,{width:390,height:844}),svg=renderChartSvg(model,{width:390,height:844,dark:true}),seriesColors=[...new Set([...svg.matchAll(/data-series-key="([^"]+)"[^>]*fill="([^"]+)"/g)].map(match=>match[2]))];
        console.log(JSON.stringify({left:plan.layout.left,right:plan.layout.right,plot:plan.layout.plotWidth,rotation:plan.layout.rotation,x_ticks:plan.xTicks.length,y_ticks:plan.yTicks.length,secondary_ticks:plan.secondaryTicks.length,legend:svg.includes('data-legend-position="right"')&&svg.includes('data-legend-orientation="vertical"'),title:svg.includes('Long category axis title')&&svg.includes('Primary units')&&svg.includes('Secondary units'),references:svg.includes('data-reference-id="r1"')&&svg.includes('data-reference-id="b1"'),annotation:svg.includes('data-annotation-id="a1"'),dark:svg.includes('#172234'),colors:seriesColors}));
        ''',
    )
    assert observed["plot"] >= 120
    assert observed["rotation"] == 45
    assert observed["x_ticks"] <= 4 and observed["y_ticks"] <= 8
    assert observed["secondary_ticks"] >= 2
    assert observed["legend"] and observed["title"] and observed["references"] and observed["annotation"] and observed["dark"]
    assert len(observed["colors"]) >= 8


def test_core_family_authority_and_specialized_truth_boundaries() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const coreDataset={id:'core',fields:[{id:'x',name:'X',type:'number'},{id:'y',name:'Y',type:'number'}],rows:[[0,1],[2,3],[10,4]]};
        const core=renderChartSvg(chartModelFromEntry({element:'Regression Scatter',mapping:{x:'x',y:'y'},dataset:coreDataset},coreDataset),{width:760,height:400});
        const capDataset={id:'cap',fields:[{id:'value',name:'Measurement',type:'number'}],rows:[[9.8],[10],[10.2],[10.1],[9.9]]};
        const cap=renderChartSvg(chartModelFromEntry({element:'Histogram',analysis_recipe:{id:'process-capability'},specification_low:9.5,specification_high:10.5,target:10,mapping:{value:'value'},dataset:capDataset},capDataset),{width:760,height:400});
        const waferDataset={id:'wafer',fields:[{id:'x',name:'Die X',type:'number'},{id:'y',name:'Die Y',type:'number'},{id:'v',name:'Value',type:'number'}],rows:[[1,1,2],[2,1,3]]};
        const wafer=renderChartSvg(chartModelFromEntry({element:'Wafer Map',mapping:{die_x:'x',die_y:'y',value:'v'},dataset:waferDataset},waferDataset),{width:520,height:520});
        console.log(JSON.stringify({core:core.includes('data-renderer-authority="visembler-canonical-chart-v2"')&&core.includes('cs-regression-line'),cap:cap.includes('LSL')&&cap.includes('USL')&&cap.includes('Target')&&cap.includes('not control limits'),wafer:wafer.includes('cs-wafer-svg'),unsafe:/NaN|Infinity|preserveAspectRatio="none"/.test(core+cap+wafer)}));
        ''',
    )
    assert observed == {"core": True, "cap": True, "wafer": True, "unsafe": False}


def test_every_core_chart_type_renders_through_the_canonical_authority() -> None:
    observed = node(
        r'''
        import {CORE_TYPES, chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'cat',name:'Category',type:'categorical'},{id:'x',name:'X',type:'number'},{id:'value',name:'Value',type:'number'},{id:'series',name:'Series',type:'categorical'}];
        const dataset={id:'all-core',fields,rows:[['A',0,1,'S1'],['A',2,3,'S2'],['B',10,5,'S1'],['B',12,4,'S2'],['C',20,8,'S1']]};
        const outputs=Object.fromEntries(CORE_TYPES.map(type=>{const mapping=['Vertical Bar','Horizontal Bar','Pareto'].includes(type)?{category:'cat',value:'value',series:'series'}:['Histogram','Box Plot'].includes(type)?{category:'cat',value:'value'}:['Scatter Plot','Regression Scatter'].includes(type)?{x:'x',y:'value'}:{x:'x',y:'value',series:'series'};const svg=renderChartSvg(chartModelFromEntry({element:type,mapping,dataset},dataset),{width:760,height:420});return [type,{authority:svg.includes('visembler-canonical-chart-v2'),unsafe:/NaN|Infinity|preserveAspectRatio="none"/.test(svg),has_mark:svg.includes('data-chart-point')}]}));
        console.log(JSON.stringify(outputs));
        ''',
    )
    assert set(observed) == {'Vertical Bar','Horizontal Bar','Line Chart','Multi-Line','Area Chart','Scatter Plot','Regression Scatter','Histogram','Box Plot','Pareto'}
    assert all(value['authority'] and not value['unsafe'] and value['has_mark'] for value in observed.values())


def test_chart_studio_source_controls_are_not_phantom() -> None:
    chart_studio = (ROOT / "company_ui/products/visualizer/assets/chart_studio.mjs").read_text()
    integrated = (ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs").read_text()
    assert "window.prompt" not in chart_studio
    assert "recommendationPreview" in chart_studio
    assert "data-interaction-crosshair" in (ROOT / "company_ui/products/visualizer/assets/canonical_chart_renderer.mjs").read_text()
    assert "renderChartSvg(model" in integrated
    assert 'preserveAspectRatio="none"' not in integrated
    assert 'aria-label="${esc(p.l)} ${p.v} minutes"' not in integrated
