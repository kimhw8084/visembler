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


def test_wave6_preset_helpers_distinguish_report_and_section_and_preserve_typed_values() -> None:
    result = node_json(
        r"""
import {personalPresetKind,personalPresetSummary,clonePersonalPreset}
from './company_ui/products/visualizer/assets/authoring_presets.mjs';

const section={
  id:'s1',name:'Fab evidence',kind:'section',
  payload:{kind:'composition',items:[
    {id:'a',value:0},
    {id:'b',value:'0',blank:'',missing:null},
  ],groups:[],datasets:[]},
};
const report={id:'r1',name:'Review',model:{mode:'guided',items:[{id:'a'}]}};
console.log(JSON.stringify({
  sectionKind:personalPresetKind(section),
  reportKind:personalPresetKind(report),
  sectionSummary:personalPresetSummary(section),
  reportSummary:personalPresetSummary(report),
  clone:clonePersonalPreset(section,{id:'s2',name:'Fab evidence copy'}),
}));
"""
    )
    assert result["sectionKind"] == "section"
    assert result["reportKind"] == "report"
    assert result["sectionSummary"] == "Section · 2 elements"
    assert result["reportSummary"] == "Report · 1 element · guided"
    clone = result["clone"]
    assert clone["id"] == "s2"
    assert clone["kind"] == "section"
    assert clone["payload"]["items"][0]["value"] == 0
    assert clone["payload"]["items"][1]["value"] == "0"
    assert clone["payload"]["items"][1]["blank"] == ""
    assert clone["payload"]["items"][1]["missing"] is None


def test_wave6_normalization_is_backward_compatible_and_accepts_section_payloads() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "value.kind==='section'" in editor
    assert "payload.kind!=='composition'" in editor
    assert "kind:'report'" in editor
    assert "kind:'section'" in editor


def test_wave6_selection_can_be_saved_as_section_preset() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function saveSelectionPresetNamed(name)" in editor
    assert "function saveSelectionPreset()" in editor
    assert "buildCompositionClipboard(model(),[...ui.selected],{rects:clipboardRects()})" in editor
    assert "Select 2+ elements to save a section preset" in editor
    assert "Section preset saved" in editor


def test_wave6_section_apply_inserts_instead_of_replacing_report() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "if(saved.kind==='section')" in editor
    assert "pasteCompositionPayload(structuredClone(saved.payload))" in editor
    assert "Load preset" in editor
    assert "{op:'model.replace',value:next}" in editor


def test_wave6_section_update_uses_current_selection_while_report_update_uses_report() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "if(personalPresets[index].kind==='section')" in editor
    assert "Select 2+ elements to update this section preset" in editor
    assert "payload=buildCompositionClipboard" in editor
    assert "model:parseCanonical(store.serialize())" in editor


def test_wave6_preset_library_labels_insert_vs_apply_and_summaries() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "personalPresetSummary(p)" in editor
    assert "p.kind==='section'?'Insert':'Apply'" in editor
    assert "Section preset" in editor


def test_wave6_multi_selection_inspector_and_command_surface_save_section() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'data-reuse-action="save-section"' in editor
    assert "if(action==='save-section'){saveSelectionPreset();return;}" in editor
    assert "Save selection preset" in editor


def test_wave6_preset_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_presets.mjs'" in page
