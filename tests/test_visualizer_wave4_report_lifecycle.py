from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "company_ui" / "products" / "visualizer" / "page.py"


def page_text() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_wave4_main_report_strip_is_reduced_to_primary_actions() -> None:
    page = page_text()
    marker = "with ui.element('section').classes('cui-visualizer-reportbar w-full')"
    start = page.index(marker)
    end = page.index("host=ui.element('div').classes('cui-visualizer-host", start)
    strip = page[start:end]

    assert "label='Reports'" in strip
    assert "use-input input-debounce=0" in strip
    assert "ui.button('New report'" in strip
    assert "ui.button('Duplicate'" in strip
    assert "ui.button('Manage'" in strip

    # Secondary / destructive actions belong in the manager, not the persistent
    # authoring strip.
    assert "Clean up empty reports" not in strip
    assert "ui.button('Trash'" not in strip
    assert "ui.button('Restore…'" not in strip
    assert "ui.button('Import…'" not in strip
    assert "report_filter=" not in strip


def test_wave4_report_manager_contains_secondary_lifecycle_actions() -> None:
    page = page_text()
    assert "manage_dialog=ui.dialog()" in page
    assert "ui.label('Manage reports')" in page
    assert "Duplicate current report" in page
    assert "Report history" in page
    assert "Import…" in page
    assert "Move current to trash…" in page
    assert "Restore trashed report…" in page
    assert "Clean up empty reports" in page


def test_wave4_report_manager_refreshes_current_context_on_open() -> None:
    page = page_text()
    assert "async def open_manage_reports()" in page
    assert "manage_current.set_text" in page
    assert "manage_counts.set_text" in page
    assert "len(repository.list())" in page
    assert "len(repository.list_trash())" in page


def test_wave4_report_options_still_disambiguate_blank_and_duplicate_titles() -> None:
    page = page_text()
    assert "label='New blank report' if record.title=='Untitled report' and blank else record.title" in page
    assert "counts[label]>1" in page
    assert "record.report_id[-6:]" in page


def test_wave4_report_manager_uses_existing_repository_lifecycle_methods() -> None:
    page = page_text()
    # Ensure this slice rearranges existing trusted lifecycle operations rather
    # than introducing a parallel report store.
    assert "repository.trash_report" in page
    assert "repository.restore(" in page
    assert "repository.delete_if_blank" in page
    assert "repository.list_history" in page
    assert "repository.create(" in page
