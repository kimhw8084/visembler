from __future__ import annotations

import json
import subprocess
from pathlib import Path

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


def test_wave10_structural_state_blocks_grouping_mixed_locked_or_grouped_selection() -> None:
    result = node_json(
        r"""
import {structuralSelectionState}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

const model={
  items:[
    {id:'a',locked:false,groupId:null},
    {id:'b',locked:true,groupId:'g1'},
    {id:'c',locked:false,groupId:'g1'},
    {id:'d',locked:false,groupId:null},
  ],
  groups:{g1:{id:'g1',items:['b','c']}},
};
console.log(JSON.stringify({
  mixed:structuralSelectionState(model,['a','b','c']),
  fresh:structuralSelectionState(model,['a','d']),
}));
"""
    )
    assert result["mixed"] == {
        "selectedCount": 3,
        "lockedCount": 1,
        "unlockedCount": 2,
        "groupedCount": 2,
        "groupable": False,
        "groupIds": ["g1"],
        "blockedGroupIds": ["g1"],
        "ungroupableGroupIds": [],
    }
    assert result["fresh"] == {
        "selectedCount": 2,
        "lockedCount": 0,
        "unlockedCount": 2,
        "groupedCount": 0,
        "groupable": True,
        "groupIds": [],
        "blockedGroupIds": [],
        "ungroupableGroupIds": [],
    }


def test_wave10_ungroup_is_allowed_only_when_whole_group_is_unlocked() -> None:
    result = node_json(
        r"""
import {structuralSelectionState}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

const unlocked={
  items:[
    {id:'a',locked:false,groupId:'g1'},
    {id:'b',locked:false,groupId:'g1'},
  ],
  groups:{g1:{id:'g1',items:['a','b']}},
};
const locked={
  items:[
    {id:'a',locked:false,groupId:'g1'},
    {id:'b',locked:true,groupId:'g1'},
  ],
  groups:{g1:{id:'g1',items:['a','b']}},
};
console.log(JSON.stringify({
  unlocked:structuralSelectionState(unlocked,['a']),
  locked:structuralSelectionState(locked,['a']),
}));
"""
    )
    assert result["unlocked"]["ungroupableGroupIds"] == ["g1"]
    assert result["unlocked"]["blockedGroupIds"] == []
    assert result["locked"]["ungroupableGroupIds"] == []
    assert result["locked"]["blockedGroupIds"] == ["g1"]


def test_wave10_layer_plan_skips_locked_entries_and_only_changes_z() -> None:
    result = node_json(
        r"""
import {layerSelectionPlan}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

console.log(JSON.stringify(layerSelectionPlan([
  {id:'a',locked:false,z:2,title:'A',value:'0'},
  {id:'b',locked:true,z:7,title:'B',dataset_id:'ds1'},
  {id:'c',locked:false,z:99,title:'C'},
],1)));
"""
    )
    assert result == [
        {"id": "a", "patch": {"z": 3}},
        {"id": "c", "patch": {"z": 99}},
    ]


def test_wave10_editor_grouping_respects_structural_protection() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "structuralSelectionState(model(),ids)" in editor
    assert "Unlock selected components before grouping" in editor
    assert "Ungroup selected components before creating a new group" in editor


def test_wave10_editor_ungroup_blocks_groups_with_locked_members() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "state.blockedGroupIds.length" in editor
    assert "Unlock group members before ungrouping" in editor
    assert "for (const gid of state.ungroupableGroupIds)" in editor


def test_wave10_layering_uses_locked_safe_plan() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "layerSelectionPlan(entries,delta)" in editor
    assert "Selected components are locked" in editor
    assert "plan.map(({id,patch})=>({op:'item.patch',id,patch}))" in editor


def test_wave10_command_eligibility_matches_structural_state() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "structuralSelectionState(model(),[...ui.selected])" in editor
    assert "group:structure.groupable" in editor
    assert "ungroup:structure.groupIds.length>0&&structure.blockedGroupIds.length===0" in editor
    assert "front:structure.unlockedCount>0" in editor
    assert "back:structure.unlockedCount>0" in editor


def test_wave10_structural_plans_do_not_mutate_semantic_or_geometry_fields() -> None:
    selection = (ASSETS / "authoring_selection.mjs").read_text(encoding="utf-8")
    layer_fn = selection.split("export function layerSelectionPlan", 1)[1].split(
        "export function duplicateSelectionPlan", 1
    )[0]
    assert "patch:{z:" in layer_fn
    for forbidden in [
        "patch:{title:",
        "patch:{value:",
        "patch:{dataset_id:",
        "patch:{mapping:",
        "patch:{x:",
        "patch:{y:",
        "patch:{w:",
        "patch:{h:",
    ]:
        assert forbidden not in layer_fn
