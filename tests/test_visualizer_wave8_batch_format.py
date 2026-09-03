from __future__ import annotations

import json
import re
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


def test_wave8_batch_state_detects_mixed_values_and_unlocked_count() -> None:
    result = node_json(
        r"""
import {batchSelectionState}
from './company_ui/products/visualizer/assets/authoring_batch.mjs';

console.log(JSON.stringify(batchSelectionState([
  {id:'a',showTitle:true,textAlign:'left',contentDensity:'fit',emphasis:'standard'},
  {id:'b',show_title:false,text_align:'center',contentDensity:'fill',emphasis:'hero',locked:true},
  {id:'c',showTitle:true,textAlign:'left',contentDensity:'fit',emphasis:'standard'},
])));
"""
    )
    assert result["showTitle"]["mixed"] is True
    assert result["textAlign"]["mixed"] is True
    assert result["contentDensity"]["mixed"] is True
    assert result["emphasis"]["mixed"] is True
    assert result["showTitle"]["count"] == 3
    assert result["showTitle"]["unlocked"] == 2


def test_wave8_batch_plan_skips_locked_and_only_patches_requested_field() -> None:
    result = node_json(
        r"""
import {batchPatchPlan}
from './company_ui/products/visualizer/assets/authoring_batch.mjs';

console.log(JSON.stringify(batchPatchPlan([
  {id:'a',title:'A',value:'0',textAlign:'left'},
  {id:'b',title:'B',value:77,textAlign:'left',locked:true},
  {id:'c',title:'C',dataset_id:'ds1',textAlign:'right'},
], 'textAlign', 'center')));
"""
    )
    assert result == [
        {"id": "a", "patch": {"textAlign": "center"}},
        {"id": "c", "patch": {"textAlign": "center"}},
    ]


def test_wave8_batch_boolean_normalization_is_explicit() -> None:
    result = node_json(
        r"""
import {batchPatchPlan}
from './company_ui/products/visualizer/assets/authoring_batch.mjs';
console.log(JSON.stringify({
  show:batchPatchPlan([{id:'a'}],'showTitle','true'),
  hide:batchPatchPlan([{id:'a'}],'showTitle','false'),
}));
"""
    )
    assert result["show"] == [{"id": "a", "patch": {"showTitle": True}}]
    assert result["hide"] == [{"id": "a", "patch": {"showTitle": False}}]


def test_wave8_editor_exposes_mixed_aware_batch_format_controls() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "batchSelectionState(entries)" in editor
    assert "batchSelectionMarkup(selectedEntries)" in editor
    assert "Batch format" in editor
    assert "batchSelectMarkup('showTitle'" in editor
    assert "batchSelectMarkup('textAlign'" in editor
    assert "batchSelectMarkup('contentDensity'" in editor
    assert "batchSelectMarkup('emphasis'" in editor
    assert 'data-batch-field="${field}"' in editor
    assert "Mixed — choose to apply" in editor


def test_wave8_batch_commit_is_single_transaction_and_skips_locked() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "batchPatchPlan(entries,field,event.target.value)" in editor
    assert "commitOps(`Batch ${batchFieldLabel(field)}`" in editor
    assert "Applied ${batchFieldLabel(field)} to ${plan.length} elements" in editor


def test_wave8_batch_format_does_not_offer_semantic_or_data_fields() -> None:
    batch = (ASSETS / "authoring_batch.mjs").read_text(encoding="utf-8")

    # Exact top-level batch-editable field contract.
    fields = re.findall(r"^  ([A-Za-z_][A-Za-z0-9_]*):Object\.freeze\(\{", batch, re.M)
    assert fields == ["showTitle", "textAlign", "contentDensity", "emphasis"]

    # Patch generation is dynamic from the approved field, not from semantic/data keys.
    assert "patch:{[field]:value}" in batch

    forbidden_patch_keys = [
        "title", "value", "unit", "dataset_id", "mapping", "rows",
        "observations", "wafer_id", "tool", "x", "y", "w", "h",
    ]
    for key in forbidden_patch_keys:
        assert f"patch:{{{{{key}:" not in batch
        assert f"patch:{{{key}:" not in batch


def test_wave8_batch_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_batch.mjs'" in page
