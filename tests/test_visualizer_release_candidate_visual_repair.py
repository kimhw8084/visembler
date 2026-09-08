from __future__ import annotations

import json
import subprocess
import hashlib
from pathlib import Path

from company_ui.products.visualizer import page as visualizer_page


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(["node", "--input-type=module", "-e", source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_rc_canvas_inspector_keeps_one_compact_page_size_action_without_layout_gallery() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    start = editor.index("function renderCanvasInspector")
    body = editor[start:editor.index("function renderAll", start)]
    assert "Smart layouts" not in body
    assert "data-suggestion" not in body
    assert 'id="inspectorPageSize"' in body
    assert "page-size-row" in body and "full-width" not in body
    assert "addEventListener('click',openPageSize)" in body


def test_rc_has_one_icon_only_developer_console_trigger_and_keeps_modal_name() -> None:
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    page_source = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert html.count('id="debugBtn"') == 1
    trigger = html[html.index('id="debugBtn"') - 100:html.index('id="debugBtn"') + 260]
    assert 'debug-glyph' in trigger and 'debugBadge' in trigger and 'debug-label' not in trigger
    assert 'id="debugTitle">Developer console<' in html
    assert "on_developer_console=" not in page_source


def test_rc_bootstrap_is_fire_and_forget_and_preserves_import_failure_signal() -> None:
    calls: list[str] = []
    class FakeUi:
        @staticmethod
        def run_javascript(script: str) -> None:
            calls.append(script)
    visualizer_page._bootstrap_editor(FakeUi(), {"report_id": "r", "model": {}}, "build", "/module.mjs?v=build")
    assert len(calls) == 1
    assert "__CUI_VISUALIZER_BOOTSTRAP__" in calls[0]
    assert "import(" in calls[0] and "editorReady='failed'" in calls[0]


def test_rc_production_and_renderer_regressions_remain_intact() -> None:
    output = node_json(r"""
import {PRODUCTION_LIBRARY_COUNT,productionEntries} from './company_ui/products/visualizer/assets/production_library.mjs';
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const engineering=element=>renderIntegratedElement({id:element,engine:'EngineeringChartEngine',element,title:element,showTitle:false,observations:[{label:'1',value:0},{label:'2',value:1}]});
const image=element=>renderIntegratedElement({id:element,engine:'ImageMediaEngine',element,title:element,showTitle:false,src:'',caption:'',alt:''});
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().length,cusum:engineering('CUSUM Chart'),ewma:engineering('EWMA Chart'),caption:image('Image + Caption'),shot:image('Screenshot Frame')}));
""")
    assert output["count"] == output["entries"] == 39
    assert all("<svg" in output[name] and "<polygon" not in output[name] for name in ("cusum", "ewma"))
    assert "Caption: describe the image" in output["caption"]
    assert "Add screenshot or mockup" in output["shot"]


def test_rc_normal_editor_markup_has_no_ppt_surface() -> None:
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    assert "PowerPoint" not in html and "PPT" not in html


def test_rc_frozen_connector_checksum_is_unchanged() -> None:
    connector = ROOT / "company_ui" / "products" / "visualizer" / "vendor" / "production_core" / "core" / "GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"
    assert hashlib.sha256(connector.read_bytes()).hexdigest() == "d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e"


def test_rc_mobile_shell_overrides_library_closed_grid_state() -> None:
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    mobile = css[css.index("@media (max-width: 800px)"):css.index("@media (max-width:400px)")]
    assert '.cui-visualizer-root[data-library="closed"] .shell' in mobile
    assert "grid-template-columns:minmax(0,1fr)!important" in mobile
