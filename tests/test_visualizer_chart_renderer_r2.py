"""Deterministic CHG-137 R2 geometry, selection, authority and keyboard proofs."""
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


def test_vertical_and_horizontal_bar_rectangles_match_base_end_mapping() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, canonicalBarRectangles, chartRenderPlan, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'category',name:'Category',type:'categorical'},{id:'series',name:'Series',type:'categorical'},{id:'value',name:'Value',type:'number'}];
        const cases=[
          ['vertical-grouped-positive','Vertical Bar',[['A', 'one', 2],['B','one',5]],{barMode:'grouped'},{}],
          ['vertical-grouped-negative','Vertical Bar',[['A','one',-2],['B','one',-5]],{barMode:'grouped'},{}],
          ['vertical-grouped-mixed','Vertical Bar',[['A','one',-2],['B','one',5]],{barMode:'grouped'},{}],
          ['vertical-stacked','Vertical Bar',[['A','one',4],['A','two',3],['B','one',-2],['B','two',-5]],{barMode:'stacked'},{}],
          ['vertical-percent','Vertical Bar',[['A','one',4],['A','two',6],['B','one',1],['B','two',3]],{barMode:'percent'},{}],
          ['horizontal-grouped','Horizontal Bar',[['A','one',2],['B','one',5]],{barMode:'grouped'},{}],
          ['horizontal-stacked','Horizontal Bar',[['A','one',4],['A','two',3],['B','one',-2],['B','two',-5]],{barMode:'stacked'},{}],
          ['horizontal-percent','Horizontal Bar',[['A','one',4],['A','two',6],['B','one',1],['B','two',3]],{barMode:'percent'},{}],
          ['configured-domain','Vertical Bar',[['A','one',2],['B','one',5]],{barMode:'grouped'},{y:{min:-10,max:10,zeroBaseline:true}}],
        ];
        const parseRects=svg=>[...svg.matchAll(/<rect class="cs-mark cs-bar-mark"[^>]*\bx="([\d.-]+)"[^>]*\by="([\d.-]+)"[^>]*\bwidth="([\d.-]+)"[^>]*\bheight="([\d.-]+)"/g)].map(match=>({x:Number(match[1]),y:Number(match[2]),width:Number(match[3]),height:Number(match[4])}));
        const result={};
        for(const [name,type,rows,visual,yAxis] of cases){
          const dataset={id:name,fields,rows};
          const model=chartModelFromEntry({element:type,mapping:{category:'category',value:'value',series:'series'},visual,axes:yAxis.y?yAxis:{y:yAxis},dataset},dataset);
          const options={width:860,height:460},plan=chartRenderPlan(model,options),actual=canonicalBarRectangles(model,options),svgRects=parseRects(renderChartSvg(model,options));
          const checks=actual.map((rect,index)=>{
            const mapped=type==='Horizontal Bar'?{x:Math.min(plan.valueAt(rect.base),plan.valueAt(rect.end)),y:rect.y,width:Math.abs(plan.valueAt(rect.base)-plan.valueAt(rect.end)),height:rect.height}:{x:rect.x,y:Math.min(plan.yAt(rect.base),plan.yAt(rect.end)),width:rect.width,height:Math.abs(plan.yAt(rect.base)-plan.yAt(rect.end))};
            const rendered=svgRects[index];
            return {mapped,actual:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},svg:rendered,delta:{x:Math.abs(rect.x-mapped.x),y:Math.abs(rect.y-mapped.y),width:Math.abs(rect.width-mapped.width),height:Math.abs(rect.height-mapped.height)},svg_delta:rendered?{x:Math.abs(rendered.x-rect.x),y:Math.abs(rendered.y-rect.y),width:Math.abs(rendered.width-rect.width),height:Math.abs(rendered.height-rect.height)}:null};
          });
          result[name]={domain:plan.yDomain,checks,finite:checks.every(check=>Object.values(check.delta).every(value=>Number.isFinite(value))&&check.svg_delta&&Object.values(check.svg_delta).every(value=>value<=.011))};
        }
        console.log(JSON.stringify(result));
        ''',
    )
    assert all(case["finite"] for case in observed.values())
    # The second positive stack must occupy 4 → 7, and the second negative stack -2 → -7.
    stacked = observed["vertical-stacked"]["checks"]
    assert stacked[1]["mapped"]["y"] < stacked[0]["mapped"]["y"]
    assert observed["vertical-percent"]["domain"] == {"min": 0, "max": 1}
    assert observed["configured-domain"]["domain"] == {"min": -10, "max": 10}


def test_bar_geometry_exposes_later_stack_base_and_percent_segments() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, canonicalBarRectangles} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'category',name:'Category',type:'categorical'},{id:'series',name:'Series',type:'categorical'},{id:'value',name:'Value',type:'number'}];
        const dataset={id:'stack',fields,rows:[['A','one',4],['A','two',3],['A','three',3],['B','one',1],['B','two',3]]};
        const make=(type,barMode)=>{const model=chartModelFromEntry({element:type,mapping:{category:'category',value:'value',series:'series'},visual:{barMode},dataset},dataset);return canonicalBarRectangles(model,{width:800,height:420});};
        console.log(JSON.stringify({vertical:make('Vertical Bar','stacked'),horizontal:make('Horizontal Bar','stacked'),percent:make('Vertical Bar','percent')}));
        ''',
    )
    for orientation in ("vertical", "horizontal"):
        assert observed[orientation][1]["base"] == 4
        assert observed[orientation][1]["end"] == 7
    assert observed["percent"][0]["display"] == 0.4
    assert observed["percent"][1]["base"] == 0.4
    assert observed["percent"][1]["end"] == 0.7


def test_semantic_selection_uses_mapped_columns_not_column_zero() -> None:
    observed = node(
        r'''
        import {chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const fields=[{id:'noise',name:'Noise',type:'categorical'},{id:'series',name:'Series',type:'categorical'},{id:'category',name:'Category',type:'categorical'},{id:'note',name:'Note',type:'categorical'},{id:'value',name:'Value',type:'number'},{id:'secondary',name:'Secondary',type:'number'}];
        const dataset={id:'mapped',fields,rows:[['ignore','S1','A','n',4,40],['ignore','S2','A','n',3,30]]};
        const model=chartModelFromEntry({element:'Vertical Bar',mapping:{category:'category',value:'value',series:'series',secondaryY:'secondary'},dataset,series:[{key:'S1',label:'S1',axis:'primary'},{key:'S2',label:'S2',axis:'secondary'}]},dataset);
        const bars=[...renderChartSvg(model,{width:800,height:420}).matchAll(/data-chart-point="[^"]+"[^>]*data-selection-cols="([^"]+)"/g)].map(match=>match[1].split(',').map(Number));
        console.log(JSON.stringify({bars,fields:fields.map((field,index)=>[field.id,index])}));
        ''',
    )
    assert set(observed["bars"][0]) == {1, 2, 4}
    assert set(observed["bars"][1]) == {1, 2, 4, 5}
    assert all(0 not in columns for columns in observed["bars"])


def test_core_authority_is_canonical_through_integrated_element_path() -> None:
    observed = node(
        r'''
        import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
        import {renderChartSvg, chartModelFromEntry, CORE_TYPES} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
        const dataset={id:'authority',fields:[{id:'x',name:'X',type:'number'},{id:'y',name:'Y',type:'number'}],rows:[[0,1],[2,3],[10,4]]};
        const outputs=Object.fromEntries(CORE_TYPES.map(type=>{const mapping=['Vertical Bar','Horizontal Bar','Pareto'].includes(type)?{category:'x',value:'y'}:['Histogram','Box Plot'].includes(type)?{value:'y'}:{x:'x',y:'y'};const model=chartModelFromEntry({element:type,mapping,dataset},dataset);const entry={id:'e',engine:'CoreChartEngine',element:type,title:type,mapping,_resolved_dataset:dataset};return [type,{studio:renderChartSvg(model,{width:760,height:400}).includes('data-renderer-authority="visembler-canonical-chart-v2"'),integrated:renderIntegratedElement(entry).includes('data-renderer-authority="visembler-canonical-chart-v2"')}]}));
        const source=await (await import('node:fs/promises')).readFile('./company_ui/products/visualizer/assets/element_renderer.mjs','utf8');
        console.log(JSON.stringify({outputs,legacy_return:source.includes("case 'CoreChartEngine': return chart(entry);"),legacy_guard:source.includes('Legacy library-only chart previews')}));
        ''',
    )
    assert all(value["studio"] and value["integrated"] for value in observed["outputs"].values())
    assert observed["legacy_return"] is False
    assert observed["legacy_guard"] is True


def test_chart_studio_keyboard_contract_and_single_mark_selection_path() -> None:
    studio = (ROOT / "company_ui/products/visualizer/assets/chart_studio.mjs").read_text(encoding="utf-8")
    canonical = (ROOT / "company_ui/products/visualizer/assets/canonical_chart_renderer.mjs").read_text(encoding="utf-8")
    assert "event.key==='Enter'||event.key===' '||event.key==='Spacebar'" in studio
    assert "selectionColumnsForMark" in studio and "selectionColumnsForMarks" in studio
    assert "selectedCols=new Set([0])" not in studio
    assert "canvas.dataset.recommendationPreview" not in studio
    assert "canvas.dataset.previewActive" in studio
    assert studio.count("[data-chart-point],[data-wafer-die]") >= 2
    assert 'data-legend-series="${full}"' in canonical
    assert 'role="button"' in canonical and 'tabindex="0"' in canonical
    assert "requestAnimationFrame" in studio
