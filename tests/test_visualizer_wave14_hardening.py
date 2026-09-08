from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(["node", "--input-type=module", "-e", source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_wave14_pointer_targets_and_narrow_shell_have_one_contract() -> None:
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    assert "min-height:44px!important;" in css
    assert ".cui-visualizer-root .tb.icon, .cui-visualizer-root .pane-close { min-width:44px!important; min-height:44px!important; }" in css
    assert "width:calc(28px * var(--viz-interaction-scale,1))!important" in css
    assert "width:calc(44px * var(--viz-interaction-scale,1))!important" in css
    assert css.count('@media (max-width:800px)') == 0
    assert css.count('.cui-visualizer-root[data-library="closed"][data-inspector="closed"] .shell') == 1


def test_wave14_accessibility_semantics_and_listener_lifecycle_remain_explicit() -> None:
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'id="undo" aria-label="Undo"' in html
    assert 'id="zoomOut" aria-label="Zoom out"' in html
    assert 'role="dialog" aria-modal="true"' in html
    assert 'role="combobox"' in html and 'role="listbox"' in html
    assert "eventAbort?.abort()" in editor
    assert "window.__VIZ_RESIZE_OBSERVER__?.disconnect?.()" in editor
    assert "on(document,'keydown',trapModalFocus)" in editor
    assert "if(e.key==='Escape')" in editor and "closeModals()" in editor


def test_wave14_image_empty_states_are_distinct_and_escaped() -> None:
    output = node_json(r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const render=element=>renderIntegratedElement({id:element,engine:'ImageMediaEngine',element,title:element,src:'',caption:'',showTitle:false});
console.log(JSON.stringify({image:render('Image'),caption:render('Image + Caption'),screenshot:render('Screenshot Frame')}));
""")
    assert "Add image" in output["image"]
    assert "Caption: describe the image" in output["caption"]
    assert "Add screenshot or mockup" in output["screenshot"]
    assert len({output["image"], output["caption"], output["screenshot"]}) == 3
    for markup in output.values():
        assert '<article' in markup and 'undefined' not in markup and 'NaN' not in markup


def test_wave14_scalar_and_small_renderer_inputs_remain_safe() -> None:
    output = node_json(r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const metric=value=>renderIntegratedElement({id:'m',engine:'MetricEngine',element:'Hero KPI',title:'Metric',value,showTitle:false});
const engineering=observations=>renderIntegratedElement({id:'e',engine:'EngineeringChartEngine',element:'EWMA Chart',title:'EWMA',observations,showTitle:false});
console.log(JSON.stringify({zero:metric(0),stringZero:metric('0'),blank:metric(''),nullValue:metric(null),missing:metric(undefined),engineering:engineering([{label:'1',value:0},{label:'2',value:0}])}));
""")
    assert ">0<" in output["zero"] and ">0<" in output["stringZero"]
    assert "NaN" not in "".join(output.values()) and "Infinity" not in "".join(output.values())
    assert '<path' in output["engineering"] and 'accent-line' in output["engineering"]


def test_wave14_production_library_and_lock_eligibility_are_unchanged() -> None:
    output = node_json(r"""
import {PRODUCTION_LIBRARY_COUNT,productionEntries} from './company_ui/products/visualizer/assets/production_library.mjs';
import {selectionActionEligibility} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const model={mode:'guided',groups:{g:{items:['a','b']}},items:[{id:'a',locked:true,groupId:'g'},{id:'b',locked:false,groupId:'g'}]};
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().length,state:selectionActionEligibility(model,['a','b'])}));
""")
    assert output["count"] == output["entries"] == 39
    assert output["state"]["group"]["reason"] == "Locked members prevent an atomic structural action"
    assert output["state"]["delete"] == {"enabled": True, "reason": "", "partial": True}
