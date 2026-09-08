from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def test_wave6_presets_view_separates_report_and_section_save_actions() -> None:
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    assert 'id="presetSave"' in html
    assert "Save report preset…" in html
    assert 'id="presetSaveSelection"' in html
    assert "Save selected section…" in html
    assert 'id="presetKindFilter"' in html
    assert '<option value="section">Sections</option>' in html
    assert '<option value="report">Reports</option>' in html


def test_wave6_personal_preset_list_filters_by_kind_and_search() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "const kind=String($('#presetKindFilter')?.value||'all');" in editor
    assert "(kind==='all'||p.kind===kind)" in editor
    assert "built.innerHTML=kind==='section'" in editor
    assert "Built-in presets are full-report layouts" in editor


def test_wave6_save_selection_action_tracks_current_selection() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function syncPresetSelectionAction()" in editor
    assert "button.disabled=count<2" in editor
    assert "Save selected section · ${count}…" in editor
    assert "syncPresetSelectionAction();" in editor


def test_wave6_preset_filters_and_save_selection_are_live_wired() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "on($('#presetSaveSelection'),'click',saveSelectionPreset)" in editor
    assert "on($('#presetKindFilter'),'change',renderPresetList)" in editor
    assert "on($('#presetSearch'),'input'" in editor


def test_wave6_section_filter_keeps_report_and_section_actions_distinct() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "applyLabel=p.kind==='section'?'Insert':'Apply'" in editor
    assert "personalPresetSummary(p)" in editor
    assert 'data-preset-kind="${p.kind||\'report\'}"' in editor
