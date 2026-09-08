from __future__ import annotations

import json
import subprocess
from pathlib import Path

from company_ui.products.visualizer.templates import REPORT_TEMPLATES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_p0_builtin_templates_contain_only_production_elements() -> None:
    payload = {
        template_id: [
            {"engine": item.get("engine"), "element": item.get("element")}
            for item in template["model"]["items"]
        ]
        for template_id, template in REPORT_TEMPLATES.items()
    }
    result = node_json(
        f"""
import {{isProductionElement}} from './company_ui/products/visualizer/assets/production_library.mjs';
const templates={json.dumps(payload)};
const invalid=[];
for (const [templateId, items] of Object.entries(templates)) {{
  for (const item of items) if (!isProductionElement(item.engine, item.element)) invalid.push({{templateId, ...item}});
}}
console.log(JSON.stringify(invalid));
"""
    )
    assert result == []


def test_p0_renderer_semantics_are_variant_specific_and_strict_numeric() -> None:
    result = node_json(
        r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const render=(element, extra={}) => renderIntegratedElement({engine:'MetricEngine',element,title:element,showTitle:false,...extra});
const values={
  hero:render('Hero KPI',{value:0,unit:'%',delta:2,target:10}),
  delta:render('Metric + Delta',{value:'0',unit:'ms',delta:2,period:'week over week',target:999}),
  target:render('Target vs Actual',{actual:0,target:10,variance:-10,unit:'%'}),
  progress:render('Progress Metric',{current:'0',max:100,unit:'%'}),
  status:render('Status Metric',{status:'Watch',detail:'Needs review',value:'0',unit:'ppm',delta:7,target:8}),
  capacity:render('Capacity Metric',{current:'0',capacity:100,unit:'lots'}),
  rate:render('Rate Metric',{numerator:0,denominator:10,value:0,unit:'%',period:'per lot'}),
  threshold:render('Threshold Metric',{value:'0',warning:5,critical:10,unit:'ppm'}),
  sparkline:render('Metric with Sparkline',{value:0,unit:'%',series:[['A',0],['B','0'],['C',null]]}),
  ring:render('Metric Ring',{value:'0',max:100,unit:'%',center_label:'Complete'}),
};
console.log(JSON.stringify(values));
"""
    )
    assert "meter" not in result["hero"]
    assert "999" not in result["delta"]
    assert "Target" in result["target"] and "Variance" in result["target"]
    assert "0" in result["progress"] and "NaN" not in result["progress"]
    assert all(token in result["status"] for token in ("Watch", "Needs review", "ppm"))
    assert "target" not in result["status"].lower()
    assert "0 / 10" in result["rate"]
    assert "Complete" in result["ring"] and "stroke-dasharray=\"0 100\"" not in result["ring"]


def test_p0_core_chart_diagram_and_media_semantics_are_visible() -> None:
    result = node_json(
        r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const chart=(element)=>renderIntegratedElement({engine:'CoreChartEngine',element,title:element,showTitle:false,data:[['Week 1',10],['Week 2',20],['Week 3',15]]});
const diagram=(direction)=>renderIntegratedElement({engine:'DiagramEngine',element:'Process Flow',title:'Flow',showTitle:false,nodes:['A','B','C'],edges:[['A','B'],['B','C']],direction,edge_label:'handoff'});
const image=renderIntegratedElement({engine:'ImageMediaEngine',element:'Image + Caption',title:'Photo',showTitle:false,src:'data:image/png;base64,AA==',alt:'Chamber surface',caption:'Observed surface'});
const project=renderIntegratedElement({engine:'ProjectCompositeEngine',element:'Project Card',title:'Work',showTitle:false,statement:'Modeled statement',detail:'Modeled detail',status:'Paused'});
console.log(JSON.stringify({line:chart('Line Chart'),area:chart('Area Chart'),bar:chart('Vertical Bar'),right:diagram('right'),down:diagram('down'),image,project}));
"""
    )
    for chart in (result["line"], result["area"], result["bar"]):
        assert "Week 1" in chart and "10" in chart
    assert result["right"] != result["down"]
    assert "handoff" in result["right"] and "handoff" in result["down"]
    assert 'aria-label="Chamber surface"' in result["image"]
    assert all(token in result["project"] for token in ("Modeled statement", "Modeled detail", "Paused"))
    assert "On track" not in result["project"] and "68%" not in result["project"] and "Owner" not in result["project"]


def test_p0_engineering_parameters_reach_variant_algorithms() -> None:
    result = node_json(
        r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const observations=[{label:'1',value:10},{label:'2',value:11},{label:'3',value:12},{label:'4',value:13}];
const render=(element, extra={})=>renderIntegratedElement({engine:'EngineeringChartEngine',element,title:element,showTitle:false,observations,...extra});
console.log(JSON.stringify({
  spc:render('SPC Control Chart',{specification_low:8,specification_high:16,lower_limit:999,upper_limit:1000}),
  imr:render('I-MR Chart',{lower_limit:999,upper_limit:1000}),
  cusumA:render('CUSUM Chart',{target:10,sigma:1,k:0.5,h:5}),
  cusumB:render('CUSUM Chart',{target:12,sigma:1,k:0.5,h:5}),
  ewmaA:render('EWMA Chart',{target:10,sigma:1,lambda:0.2,L:3}),
  ewmaB:render('EWMA Chart',{target:12,sigma:1,lambda:0.8,L:2}),
  liveCusumA:render('CUSUM Chart',{target:10,sigma:1,k:0.5,decision_h:4,x:14,y:14,w:480,h:225}),
  liveCusumB:render('CUSUM Chart',{target:10,sigma:1,k:0.5,decision_h:6,x:14,y:14,w:480,h:225}),
}));
"""
    )
    assert "999" not in result["spc"] and "1000" not in result["spc"]
    assert result["cusumA"] != result["cusumB"]
    assert result["ewmaA"] != result["ewmaB"]
    assert result["liveCusumA"] != result["liveCusumB"]


def test_p0_spc_specification_limits_are_rendered_separately_and_strictly_numeric() -> None:
    result = node_json(
        r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
import {prepareEngineeringChart} from './company_ui/products/visualizer/vendor/production_core/core/engineering_chart_engine.mjs';
const observations=[{label:'1',value:10},{label:'2',value:11},{label:'3',value:12},{label:'4',value:13}];
const render=(extra={})=>renderIntegratedElement({engine:'EngineeringChartEngine',element:'SPC Control Chart',title:'SPC',showTitle:false,observations,...extra});
const specLines=(markup)=>markup.match(/<line class="viz-eng-spec"[^>]+>/g)||[];
const values=observations.map(({value})=>value);
const baselinePlan=prepareEngineeringChart('spc',{values},{lsl:8,usl:16});
const changedPlan=prepareEngineeringChart('spc',{values},{lsl:9,usl:15});
const noLower=render({specification_high:15});
const stringZero=render({specification_low:'0',specification_high:15});
console.log(JSON.stringify({
  baseline:specLines(render({specification_low:8,specification_high:16})),
  changed:specLines(render({specification_low:9,specification_high:15})),
  stringZero:specLines(stringZero),
  stringZeroIgnored:stringZero===noLower,
  computedLimitsStable:baselinePlan.center===changedPlan.center&&baselinePlan.lcl===changedPlan.lcl&&baselinePlan.ucl===changedPlan.ucl,
}));
"""
    )
    assert len(result["baseline"]) == 2
    assert result["baseline"] != result["changed"]
    assert len(result["stringZero"]) == 1
    assert result["stringZeroIgnored"] is True
    assert result["computedLimitsStable"] is True


def test_p0_editor_exposes_compatible_switcher_onboarding_and_grid_actions() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'id="iVisualType"' in editor
    assert "Change visual type" in editor
    assert 'id="iDecisionH"' in editor and "decision_h" in editor
    assert "blankStartSurface" in editor
    for action in (
        "insert-row-above",
        "insert-row-below",
        "delete-rows",
        "insert-column-left",
        "insert-column-right",
        "delete-columns",
    ):
        assert action in editor
    assert "data-table-action=\"delete-rows\"" in editor


def test_p0_grid_operations_are_selection_aware_and_preserve_scalars() -> None:
    result = node_json(
        r"""
import {applyGridAction} from './company_ui/products/visualizer/assets/authoring_grid.mjs';
const source={headers:['A','B','C'],rows:[[0,'0',null],[1,'one',''],[2,'two',false]]};
const selected={anchor:'1:1',focus:'1:1'};
const inserted=applyGridAction(source,'insert-row-above',selected);
const removed=applyGridAction(source,'delete-rows',selected);
const left=applyGridAction(source,'insert-column-left',selected);
const columns=applyGridAction(source,'delete-columns',selected);
console.log(JSON.stringify({inserted,removed,left,columns}));
"""
    )
    assert result["inserted"]["rows"][0] == [0, "0", None]
    assert result["inserted"]["rows"][1] == [None, None, None]
    assert result["removed"]["rows"] == [[0, "0", None], [2, "two", False]]
    assert result["left"]["headers"] == ["A", "Column 2", "B", "C"]
    assert result["columns"]["headers"] == ["A", "C"]
    assert result["columns"]["rows"][0] == [0, None]
