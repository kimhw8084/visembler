from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def test_wave3_wafer_uses_observations_without_dataset_binding() -> None:
    renderer = (ASSETS / "element_renderer.mjs").read_text(encoding="utf-8")
    assert "if(Array.isArray(entry.observations)&&entry.observations.length)" in renderer
    assert "if(entry.dataset_id&&Array.isArray(entry.observations)" not in renderer


def test_wave3_wafer_rendering_does_not_coerce_text_zero_to_numeric() -> None:
    renderer = (ASSETS / "element_renderer.mjs").read_text(encoding="utf-8")
    assert "entry.observations.map(row=>row.value).filter(value=>typeof value==='number'&&Number.isFinite(value))" in renderer
    assert "typeof value==='number'&&Number.isFinite(value)" in renderer


def test_wave3_engineering_and_wafer_have_practical_observation_actions() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    for action in [
        'data-engineering-action="add"',
        'data-engineering-action="sample"',
        'data-engineering-action="clear"',
        'data-wafer-action="add"',
        'data-wafer-action="sample"',
        'data-wafer-action="clear"',
    ]:
        assert action in editor
    assert "Add engineering observation" in editor
    assert "Restore engineering sample" in editor
    assert "Clear engineering observations" in editor
    assert "Add wafer observation" in editor
    assert "Restore wafer sample" in editor
    assert "Clear wafer observations" in editor


def test_wave3_wafer_identity_covers_semiconductor_context() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    for field_id in ["iWaferId", "iLot", "iTool", "iChamber", "iRecipe", "iProcess", "iBin", "iRoute"]:
        assert f'id="{field_id}"' in editor
    for key in ["wafer_id", "lot", "tool", "chamber", "recipe", "process", "bin", "route"]:
        assert f"['i" in editor
        assert f"'{key}']" in editor


def test_wave3_engineering_limit_actions_keep_control_and_spec_limits_distinct() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'data-engineering-action="clear-limits"' in editor
    assert "Clear engineering limits" in editor
    assert "lower_limit:null" in editor
    assert "upper_limit:null" in editor
    assert "specification_low:null" in editor
    assert "specification_high:null" in editor
