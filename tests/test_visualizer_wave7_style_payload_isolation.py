from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui" / "products" / "visualizer" / "assets" / "integrated_editor.mjs"


def _editor() -> str:
    return EDITOR.read_text(encoding="utf-8")


def test_wave7_style_copy_payload_is_strictly_isolated() -> None:
    editor = _editor()
    block = editor.split(
        "function copySemanticSelection(kind='visual_full') {", 1
    )[1].split("function pasteCompositionPayload", 1)[0]
    isolated = "{version:2,kind:'style',style:styleSnapshot(entry)}"
    generic = "const payload={version:1,kind,entry:structuredClone(entry),dataset:"
    assert block.count(isolated) == 1
    assert block.index(isolated) < block.index(generic)
    assert "kind==='style'?{style:styleSnapshot(entry)}" not in block


def test_wave7_isolated_style_paste_precedes_entry_requirement() -> None:
    editor = _editor()
    block = editor.split(
        "function pasteSemanticPayload(payload, mode='auto') {", 1
    )[1].split("\nfunction ", 1)[0]
    style = "if(mode==='style' || payload?.kind==='style')"
    guard = "if(!payload?.entry)return false"
    assert block.index(style) < block.index(guard)
    assert "payload?.style||(source?styleSnapshot(source):null)" in block
