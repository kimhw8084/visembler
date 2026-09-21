from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui/products/visualizer/assets"


def read(name: str) -> str:
    return (ASSETS / name).read_text()


def test_chg139_negative_control_rejects_positional_command_hiding() -> None:
    chart_css = read("chart_studio.css")
    diagram_css = read("diagram_studio.css")
    assert "nth-child" not in chart_css
    assert "nth-child" not in diagram_css
    assert ".cs-actions .cs-btn:nth-child(-n+3)" not in chart_css
    assert ".ds-toolbar-group button:nth-child(n+5)" not in diagram_css


def test_chg139_negative_control_rejects_fixed_mobile_canvas_minimum() -> None:
    diagram_css = read("diagram_studio.css")
    diagram_js = read("diagram_studio.mjs")
    authoring_js = read("authoring_diagram_studio.mjs")
    assert "min-width:720px" not in diagram_css.replace(" ", "")
    assert "Math.max(900" not in diagram_js
    assert "w:900,h:560" not in authoring_js
    assert "Math.max(900" not in authoring_js
    assert "min-width:0" in diagram_css


def test_chg139_overflow_duplicates_secondary_commands_and_keeps_primaries() -> None:
    chart = read("chart_studio.html")
    diagram = read("diagram_studio.html")
    editor = read("integrated_editor.html")
    for source in (chart, diagram):
        secondary = re.findall(r'data-action="([^"]+)" data-responsive-priority="secondary"', source)
        assert secondary
        assert 'data-responsive-overflow' in source
        for action in secondary:
            assert f'data-overflow-action="{action}"' in source, action
    for control in ("undo", "redo", "commandBtn", "previewBtn"):
        assert re.search(rf'id="{control}"[^>]*data-responsive-priority="primary"', editor)
    assert 'id="saveBtn">Autosaved' in editor
    assert '#saveBtn' in read("integrated_editor.css")


def test_chg139_shared_token_authority_and_focus_contract() -> None:
    tokens = read("tokens.css")
    editor_css = read("integrated_editor.css")
    chart_css = read("chart_studio.css")
    diagram_css = read("diagram_studio.css")
    assert all(token in tokens for token in ("--viz-r-control", "--viz-r-surface", "--viz-r-overlay", "--viz-control-height"))
    assert "--viz-accent:" not in editor_css
    assert "--viz-surface:" not in editor_css
    assert "--viz-accent" in chart_css and "--viz-accent" in diagram_css
    assert "closeResponsiveOverflow" in read("chart_studio.mjs")
    assert "closeResponsiveOverflow" in read("diagram_studio.mjs")
    assert "focus({preventScroll:true})" in read("chart_studio.mjs")
    assert "focusVisible(details.querySelector('summary'))" in read("diagram_studio.mjs")
