from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


def test_wave3_select_all_handlers_are_in_correct_grid_regions() -> None:
    editor = EDITOR.read_text(encoding="utf-8")

    dock_start = editor.index("$('#dataDockGrid')?.addEventListener('keydown'")
    dock_end = editor.index("$('#dataDockGrid')?.addEventListener('paste'", dock_start)
    table_start = editor.index("$('#tableEditorGrid')?.addEventListener('keydown'")
    table_end = editor.index("$('#tableEditorGrid')?.addEventListener('paste'", table_start)

    dock = editor[dock_start:dock_end]
    table = editor[table_start:table_end]

    assert "Select all dataset cells" in dock
    assert "Select all table cells" not in dock
    assert "ui.dataDockRange={anchor:'0:0',focus:" in dock
    assert "host.__dockPaint()" in dock
    assert '[data-dataset-cell="${target.dataset.datasetCell}"]' in dock

    assert "Select all table cells" in table
    assert "Select all dataset cells" not in table
    assert "ui.tableRange={anchor:'0:0',focus:" in table
    assert "host.__tablePaint()" in table
    assert '[data-table-cell="${target.dataset.tableCell}"]' in table


def test_wave3_select_all_is_immediately_available_before_copy() -> None:
    editor = EDITOR.read_text(encoding="utf-8")

    dock_start = editor.index("$('#dataDockGrid')?.addEventListener('keydown'")
    dock_end = editor.index("$('#dataDockGrid')?.addEventListener('paste'", dock_start)
    table_start = editor.index("$('#tableEditorGrid')?.addEventListener('keydown'")
    table_end = editor.index("$('#tableEditorGrid')?.addEventListener('paste'", table_start)

    dock = editor[dock_start:dock_end]
    table = editor[table_start:table_end]

    assert dock.index("Select all dataset cells") < dock.index("event.key.toLowerCase()==='c'")
    assert table.index("Select all table cells") < table.index("event.key.toLowerCase()==='c'")


def test_wave3_typed_range_copy_remains_active_on_both_grids() -> None:
    editor = EDITOR.read_text(encoding="utf-8")
    token = "formatAuthoringRow(record.slice(loColumn,hiColumn+1))"
    assert editor.count(token) >= 2
