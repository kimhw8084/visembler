from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(["node", "--input-type=module", "-e", source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_wave13_locked_affordances_and_inspector_actions_follow_eligibility() -> None:
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert ".component:not(.selected) .resize-h, .component.locked .resize-h" in css
    assert ".cui-visualizer-root .component.locked .resize-h { display:none!important; pointer-events:none; }" in css
    assert "display: none !important; pointer-events: none;" in css
    assert "eligibilityButton(entry.locked?'Unlock':'Lock','lock',lockAction)" in editor
    assert 'aria-disabled="${state.enabled?\'false\':\'true\'}"' in editor
    assert "Lock / unlock" not in editor


def test_wave13_selection_summary_and_smart_guidance_have_one_authoritative_source() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "selection-lock-summary" not in editor
    assert "Smart mode owns arrangement and placement." in editor
    assert "Locked members will be skipped." in editor
    state = node_json(r"""
import {selectionActionEligibility} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const model={mode:'smart',groups:{},items:[{id:'a',locked:false},{id:'b',locked:true}]};
console.log(JSON.stringify(selectionActionEligibility(model,['a','b'])));
""")
    assert state["arrange"] == {"enabled": False, "reason": "Arrange is automatic in Smart mode", "partial": True}
    assert state["delete"] == {"enabled": True, "reason": "", "partial": True}


def test_wave13_command_rows_and_report_templates_have_semantic_hierarchy() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert 'class="cmd-copy"' in editor and 'class="cmd-label"' in editor and 'class="cmd-description"' in editor
    assert ".cmd-copy" in css and ".cmd-shortcut" in css
    assert "cui-report-template-title" in page and "cui-report-template-description" in page
    assert ".cui-report-template" in css


def test_wave13_context_toolbar_keeps_only_immediate_actions() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    context = editor.split("function renderContext(rm)", 1)[1].split("function renderMinimap", 1)[0]
    assert "actionButton('lock'" in context and "actionButton('delete'" in context
    assert "actionButton('group'" not in context and "actionButton('front'" not in context
    assert "['Group selection'" in editor and "['Bring selection forward'" in editor
    assert ".context { max-width:min(520px,calc(100vw - 24px)); flex-wrap:nowrap; }" in css


def test_wave13_engineering_traces_are_unfilled_and_stable() -> None:
    output = node_json(r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const render=(element,observations)=>renderIntegratedElement({id:element,engine:'EngineeringChartEngine',element,title:element,showTitle:true,observations});
const points=[{label:'1',value:0},{label:'2',value:0},{label:'3',value:1},{label:'4',value:0}];
console.log(JSON.stringify({
  cusum:render('CUSUM Chart',points), ewma:render('EWMA Chart',points),
  empty:render('CUSUM Chart',[]), single:render('EWMA Chart',[{label:'1',value:0}]),
  spc:render('SPC Control Chart',points), imr:render('I-MR Chart',points),
}));
""")
    for key in ("cusum", "ewma"):
        assert '<svg' in output[key] and '<path' in output[key]
        assert f'data-engineering-chart="{key}"' in output[key]
        assert "<polygon" not in output[key]
    assert "Insufficient data" in output["empty"] and "Insufficient data" in output["single"]
    assert 'data-engineering-chart="spc"' in output["spc"]
    assert 'data-engineering-chart="imr"' in output["imr"]
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    assert ".viz-engineering-chart .viz-line { fill: none;" in css
    assert ".viz-engineering-chart .viz-line.viz-series-0" in css
