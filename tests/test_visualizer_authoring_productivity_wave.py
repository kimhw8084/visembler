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


def test_productivity_matrix_covers_exactly_the_production_library() -> None:
    result = node_json(
        r"""
import {productionEntries,PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().map(item=>item.element)}));
"""
    )
    matrix = (ROOT / "docs" / "VISSEMBLER_AUTHORING_PRODUCTIVITY_MATRIX.md").read_text()
    assert result["count"] == len(result["entries"]) == 39
    assert len(set(result["entries"])) == 39
    assert all(f"| {element} |" in matrix for element in result["entries"])


def test_content_first_clipboard_contract_uses_one_shared_path() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "on($('#pasteDataBtn'),'click',()=>openDataFirstDialog())" in editor
    assert "if(action==='paste')openDataFirstDialog()" in editor
    assert "async function handleClipboardText(text)" in editor
    assert "on(window,'paste',async(e)=>{if(ui.preview||hasAuthoringTextFocus())return;" in editor
    assert "active?.isContentEditable" in editor


def test_dataset_inline_edit_is_field_aware() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    values = (ASSETS / "authoring_values.mjs").read_text(encoding="utf-8")
    assert "export function parseAuthoringFieldValue" in values
    assert "parseAuthoringFieldValue(raw,field||{},{quoted})" in editor
    assert "parseCellForField(value,directDataset.fields?.[directColumn])" in editor

    result = node_json(
        r"""
import {parseAuthoringFieldValue} from './company_ui/products/visualizer/assets/authoring_values.mjs';
console.log(JSON.stringify([
  parseAuthoringFieldValue('0',{type:'identifier'}),
  parseAuthoringFieldValue('0',{type:'categorical'}),
  parseAuthoringFieldValue('0',{type:'number'}),
  parseAuthoringFieldValue('',{type:'number'}),
  parseAuthoringFieldValue('""',{type:'string'}),
]));
"""
    )
    assert result == ["0", "0", 0, None, ""]


def test_focused_browser_controls_are_not_intercepted_by_canvas_paste() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "hasAuthoringTextFocus()" in editor
    assert "input,textarea,select,[role=\"textbox\"],[contenteditable=\"true\"]" in editor
    assert "if(ui.preview||hasAuthoringTextFocus())return" in editor
