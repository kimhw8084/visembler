from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


def editor_text() -> str:
    return EDITOR.read_text(encoding="utf-8")


def test_wave3_clipboard_uses_typed_roundtrip_formatter() -> None:
    editor = editor_text()
    assert "parseDelimitedText" in editor
    assert "formatAuthoringRow(record.slice(loColumn,hiColumn+1))" in editor
    assert editor.count("formatAuthoringRow(record.slice(loColumn,hiColumn+1))") >= 2
    assert "const parsed=parseAuthoringGrid(text).rows" in editor


def test_wave3_dataset_paste_preserves_quoted_cell_intent_with_field_types() -> None:
    editor = editor_text()
    assert "function parseCellForField(raw, field)" in editor
    assert "const quoted=arguments[2]===true;" in editor
    assert "if(quoted)return text;" in editor
    assert "const parsed=parseDelimitedText(text)" in editor
    assert "parsed.quoted_rows[rowOffset]?.[columnOffset]" in editor
    assert "parseCellForField(value,next.fields[columnIndex],Boolean(" in editor


def test_wave3_table_and_data_dock_support_select_all_ranges() -> None:
    editor = editor_text()
    assert "Select all table cells" in editor
    assert "Select all dataset cells" in editor
    assert "event.key.toLowerCase()==='a'" in editor
    assert "ui.tableRange={anchor:'0:0',focus:" in editor
    assert "ui.dataDockRange={anchor:'0:0',focus:" in editor


def test_wave3_clipboard_help_mentions_select_all() -> None:
    editor = editor_text()
    assert "Ctrl/Cmd+A selects all" in editor
