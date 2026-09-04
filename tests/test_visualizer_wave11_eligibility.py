from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(["node", "--input-type=module", "-e", source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_wave11_summary_and_eligibility_describe_mixed_selection() -> None:
    result = node_json(r"""
import {selectionActionEligibility} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const model={mode:'guided',items:[{id:'a',locked:false,groupId:null,z:1},{id:'b',locked:true,groupId:'g1',z:2},{id:'c',locked:false,groupId:'g1',z:3}],groups:{g1:{id:'g1',items:['b','c']}}};
console.log(JSON.stringify(selectionActionEligibility(model,['a','b','c'])));
""")
    assert result["summary"] == {"count": 3, "unlocked": 2, "locked": 1, "grouped": 2}
    assert result["group"] == {"enabled": False, "reason": "Locked members prevent an atomic structural action", "atomic": True}
    assert result["ungroup"] == {"enabled": False, "reason": "Locked members prevent an atomic structural action", "atomic": True}
    assert result["front"]["enabled"] is True and result["front"]["partial"] is True
    assert result["delete"]["enabled"] is True and result["batch"]["partial"] is True


def test_wave11_reasons_cover_count_group_and_no_unlocked_cases() -> None:
    result = node_json(r"""
import {selectionActionEligibility} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const base={mode:'guided',groups:{},items:[{id:'a',locked:true,groupId:null},{id:'b',locked:false,groupId:'g1'},{id:'c',locked:false,groupId:null}]};
console.log(JSON.stringify({one:selectionActionEligibility(base,['c']),locked:selectionActionEligibility(base,['a']),grouped:selectionActionEligibility(base,['b','c'])}));
""")
    assert result["one"]["group"]["reason"] == "Selection count insufficient"
    assert result["locked"]["delete"]["reason"] == "No eligible unlocked members"
    assert result["grouped"]["group"]["reason"] == "Existing group membership conflicts with Group"


def test_wave11_editor_uses_shared_eligibility_for_toolbar_inspector_keyboard_and_palette() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "selectionActionEligibility(model(),ids" in editor
    assert "selectionActionEligibility(model(),[...ui.selected]" in editor
    assert "eligibilityButton('Group','group',eligibility.group)" in editor
    assert "node.title=state[key].enabled" in editor
    assert "if(!eligibility.group.enabled)return toast(" in editor
    assert "if(!eligibility.delete.enabled)return toast(eligibility.delete.reason)" in editor


def test_wave11_partial_and_atomic_plans_remain_single_patch_only() -> None:
    result = node_json(r"""
import {layerSelectionPlan} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
import {batchPatchPlan} from './company_ui/products/visualizer/assets/authoring_batch.mjs';
const entries=[{id:'a',locked:false,z:3,value:'0',title:'A'},{id:'b',locked:true,z:4,value:null,title:'B'}];
console.log(JSON.stringify({layer:layerSelectionPlan(entries,1),batch:batchPatchPlan(entries,'textAlign','center')}));
""")
    assert result == {"layer": [{"id": "a", "patch": {"z": 4}}], "batch": [{"id": "a", "patch": {"textAlign": "center"}}]}


def test_wave11_inspector_makes_partial_skip_explicit() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "Locked members will be skipped." in editor
    assert "Delete skips locked members." in editor
    assert "each change applies in one step" in editor
