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


def test_wave5_reuse_capabilities_hide_unsupported_data_actions() -> None:
    result = node_json(
        r"""
import {reuseCapabilities}
from './company_ui/products/visualizer/assets/authoring_reuse.mjs';

const visualOnly=reuseCapabilities({
  selectionCount:1,
  hasDataset:false,
  hasMapping:false,
  clipboard:{kind:'style',entry:{title:'Source'}},
});
const dataBound=reuseCapabilities({
  selectionCount:1,
  hasDataset:true,
  hasMapping:true,
  clipboard:{
    kind:'dataset_data',
    entry:{mapping:{value:'v'}},
    dataset:{id:'ds',rows:[[0,'0',null,'']]},
  },
});
console.log(JSON.stringify({visualOnly,dataBound}));
"""
    )
    visual = result["visualOnly"]
    assert visual["copyVisual"] is True
    assert visual["copyStyle"] is True
    assert visual["copyData"] is False
    assert visual["copyMapping"] is False
    assert visual["pasteData"] is False
    assert visual["appendData"] is False

    data = result["dataBound"]
    assert data["copyData"] is True
    assert data["copyMapping"] is True
    assert data["pasteData"] is True
    assert data["pasteMapping"] is True
    assert data["appendData"] is True


def test_wave5_reuse_capabilities_support_multi_selection_compositions() -> None:
    result = node_json(
        r"""
import {reuseCapabilities,reuseClipboardLabel}
from './company_ui/products/visualizer/assets/authoring_reuse.mjs';

const clipboard={kind:'composition',items:[{id:'a'},{id:'b'}]};
console.log(JSON.stringify({
  unlocked:reuseCapabilities({selectionCount:3,selectionLocked:false,clipboard}),
  locked:reuseCapabilities({selectionCount:3,selectionLocked:true,clipboard}),
  label:reuseClipboardLabel(clipboard),
}));
"""
    )
    assert result["unlocked"]["copySelection"] is True
    assert result["unlocked"]["cut"] is True
    assert result["unlocked"]["pasteNew"] is True
    assert result["locked"]["cut"] is False
    assert result["label"] == "2 elements copied"


def test_wave5_single_element_inspector_has_contextual_reuse_surface() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function reuseInspectorMarkup(entry)" in editor
    assert "inspectorSection('Reuse'" in editor
    assert 'data-reuse-action="${action}"' in editor
    assert "button('Visual','copy-visual',caps.copyVisual)" in editor
    assert "button('Style','copy-style',caps.copyStyle)" in editor
    assert "button('Data','copy-data',caps.copyData)" in editor
    assert "button('Mapping','copy-mapping',caps.copyMapping)" in editor
    assert "button('Paste as new','paste-new',caps.pasteNew)" in editor
    assert "button('Paste data','paste-data',caps.pasteData)" in editor
    assert "button('Paste mapping','paste-mapping',caps.pasteMapping)" in editor
    assert "button('Paste style','paste-style',caps.pasteStyle)" in editor
    assert "button('Append data','append-data',caps.appendData)" in editor


def test_wave5_reuse_ui_uses_capability_gates_instead_of_dead_controls() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "${enabled?'':'disabled'}" in editor
    assert "button('Mapping','copy-mapping',caps.copyMapping)" in editor
    assert "button('Paste data','paste-data',caps.pasteData)" in editor
    assert "button('Paste mapping','paste-mapping',caps.pasteMapping)" in editor
    assert "button('Append data','append-data',caps.appendData)" in editor


def test_wave5_multi_selection_inspector_exposes_composition_reuse() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'data-reuse-action="copy-selection"' in editor
    assert 'data-reuse-action="cut-selection"' in editor
    assert 'data-reuse-action="paste-new"' in editor
    assert "reuseCapabilities({selectionCount:ids.length" in editor


def test_wave5_reuse_actions_bind_to_existing_semantic_clipboard_contract() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "copySemanticSelection('dataset_data')" in editor
    assert "copySemanticSelection('mapping')" in editor
    assert "copySemanticSelection('style')" in editor
    assert "pasteSemanticPayload(ui.semanticClipboard,'data')" in editor
    assert "pasteSemanticPayload(ui.semanticClipboard,'mapping')" in editor
    assert "pasteSemanticPayload(ui.semanticClipboard,'style')" in editor
    assert "pasteSemanticPayload(ui.semanticClipboard,'append-data')" in editor
    assert "pasteSemanticClipboard()" in editor


def test_wave5_reuse_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_reuse.mjs'" in page
