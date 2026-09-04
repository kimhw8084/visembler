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


def test_wave9_additive_selection_supports_standard_modifiers() -> None:
    result = node_json(
        r"""
import {isAdditiveSelectionGesture}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

console.log(JSON.stringify({
  plain:isAdditiveSelectionGesture({}),
  shift:isAdditiveSelectionGesture({shiftKey:true}),
  meta:isAdditiveSelectionGesture({metaKey:true}),
  ctrl:isAdditiveSelectionGesture({ctrlKey:true}),
}));
"""
    )
    assert result == {"plain": False, "shift": True, "meta": True, "ctrl": True}


def test_wave9_selection_lock_state_is_explicit_for_mixed_selection() -> None:
    result = node_json(
        r"""
import {selectionLockState}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

console.log(JSON.stringify(selectionLockState([
  {id:'a',locked:false},
  {id:'b',locked:true},
  {id:'c',locked:false},
])));
"""
    )
    assert result == {
        "count": 3,
        "locked": 1,
        "unlocked": 2,
        "mixed": True,
        "allLocked": False,
        "allUnlocked": False,
    }


def test_wave9_lock_plan_only_patches_items_that_need_change() -> None:
    result = node_json(
        r"""
import {selectionLockPlan}
from './company_ui/products/visualizer/assets/authoring_selection.mjs';

const entries=[
  {id:'a',locked:false,title:'A',value:'0'},
  {id:'b',locked:true,title:'B',dataset_id:'ds1'},
  {id:'c',locked:false,title:'C'},
];
console.log(JSON.stringify({
  lock:selectionLockPlan(entries,true),
  unlock:selectionLockPlan(entries,false),
}));
"""
    )
    assert result["lock"] == [
        {"id": "a", "patch": {"locked": True}},
        {"id": "c", "patch": {"locked": True}},
    ]
    assert result["unlock"] == [
        {"id": "b", "patch": {"locked": False}},
    ]


def test_wave9_editor_uses_cmd_ctrl_shift_additive_selection() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "isAdditiveSelectionGesture(e)" in editor
    assert "if (e.shiftKey) ui.selected.has(id)" not in editor


def test_wave9_multi_selection_exposes_explicit_lock_all_unlock_all() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'data-selection-lock="true">Lock all</button>' in editor
    assert 'data-selection-lock="false">Unlock all</button>' in editor
    assert "bindSelectionLockControls(selectedEntries)" in editor
    assert "selectionLockState(entries)" in editor
    assert "selectionLockPlan(entries,locked)" in editor


def test_wave9_lock_actions_are_single_transactions() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "commitOps(locked?'Lock selection':'Unlock selection'" in editor
    assert "plan.map(({id,patch})=>({op:'item.patch',id,patch}))" in editor


def test_wave9_toolbar_lock_label_reflects_selection_state() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "lockButton.textContent=willLock?'Lock':'Unlock'" in editor
    assert "lockButton.title=willLock?'Lock every selected element':'Unlock every selected element'" in editor


def test_wave9_locking_does_not_touch_semantic_fields() -> None:
    selection = (ASSETS / "authoring_selection.mjs").read_text(encoding="utf-8")
    lock_function = selection.split("export function selectionLockPlan", 1)[1].split(
        "export function duplicateSelectionPlan", 1
    )[0]

    # The planner must emit exactly the lock-state patch.
    assert ".map(entry=>({id:entry.id,patch:{locked:target}}));" in lock_function

    forbidden_exact_fragments = [
        "patch:{title:",
        "patch:{value:",
        "patch:{unit:",
        "patch:{dataset_id:",
        "patch:{mapping:",
        "patch:{rows:",
        "patch:{x:",
        "patch:{y:",
        "patch:{w:",
        "patch:{h:",
    ]
    for forbidden in forbidden_exact_fragments:
        assert forbidden not in lock_function
