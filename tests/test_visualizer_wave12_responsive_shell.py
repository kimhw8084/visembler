from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def test_wave12_theme_has_one_effective_root_target() -> None:
    css = (ASSETS / "integrated_editor.css").read_text()
    editor = (ASSETS / "integrated_editor.mjs").read_text()
    assert '.cui-visualizer-root[data-theme="dark"]' in css
    assert "activeRoot?.setAttribute('data-theme',value)" in editor
    assert "document.documentElement.setAttribute('data-theme',value)" in editor


def test_wave12_responsive_panels_are_drawers_not_display_none() -> None:
    css = (ASSETS / "integrated_editor.css").read_text()
    assert '.cui-visualizer-root .right { display:block; position:absolute;' in css
    assert '.cui-visualizer-root .left { display:block; position:absolute;' in css
    assert '[data-inspector="closed"] .right { visibility:hidden; pointer-events:none; }' in css
    assert '[data-library="closed"] .left { visibility:hidden; pointer-events:none; }' in css


def test_wave12_fit_can_go_below_manual_floor_without_changing_manual_zoom() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text()
    assert "function setZoom(z, renderMini = true, minimum = 0.55)" in editor
    assert "setZoom(z,true,0.1)" in editor


def test_wave12_normal_inspector_exposes_svg_not_powerpoint() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text()
    inspector = editor.split("function renderInspector()", 1)[1].split("function renderCanvasInspector", 1)[0]
    assert "PowerPoint" not in inspector and "PPT" not in inspector
    assert "Visual export ready" in inspector


def test_wave12_narrow_shell_keeps_controls_and_resize_target_available() -> None:
    css = (ASSETS / "integrated_editor.css").read_text()
    assert "#libraryToggle" in css and "#inspectorToggle" in css and "display:inline-flex!important" in css
    assert ".seg button { min-width:76px;" in css
    assert "width:calc(28px * var(--viz-interaction-scale,1))!important" in css
    assert "width:calc(44px * var(--viz-interaction-scale,1))!important" in css
    assert ".resize-h::before { content:\"\"; width:8px; height:8px;" in css
    assert "top:calc(-14px * var(--viz-interaction-scale,1))!important" in css
