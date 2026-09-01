from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'company_ui' / 'products' / 'visualizer'
ASSETS = PRODUCT / 'assets'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_wave1_shell_defaults_library_and_inspector_open_and_removes_layout_gallery_button() -> None:
    html = _read(ASSETS / 'integrated_editor.html')
    editor = _read(ASSETS / 'integrated_editor.mjs')
    assert 'data-library="open"' in html
    assert 'data-inspector="open"' in html
    assert 'libraryOpen: true' in editor
    assert "setLibrary(storage.get('viz-library-open')!=='0')" in editor
    assert 'id="layoutBtn"' not in html
    assert "openLayoutGallery" not in editor


def test_wave1_runtime_asset_graph_cannot_reuse_the_old_cached_vendor_namespace() -> None:
    page = _read(PRODUCT / 'page.py')
    editor = _read(ASSETS / 'integrated_editor.mjs')
    renderer = _read(ASSETS / 'element_renderer.mjs')
    assert "production_core_v2" not in page
    assert "max_cache_age=3600" not in '\n'.join(
        line for line in page.splitlines() if "add_static_files" in line and "vendor/production_core" in line
    )
    assert "paths.extend(sorted((VENDOR/'core').glob('*.mjs')))" in page
    assert "../vendor/production_core/core/editor_store.mjs?v=v0.4.26" in editor
    assert "../vendor/production_core/core/runtime_registry.mjs?v=v0.4.26" in editor
    assert "../vendor/production_core/core/universal_renderer.mjs?v=v0.4.26" in renderer


def test_wave1_builtin_preset_apply_is_one_transactional_model_replace() -> None:
    editor = _read(ASSETS / 'integrated_editor.mjs')
    assert "commitOps('Apply built-in preset',[{op:'model.replace',value:next}]" in editor
    assert "next.layoutPreset=preset" in editor
    assert "next.mode='smart'" in editor


def test_wave1_export_surface_uses_canonical_json_and_xmlserializer_without_powerpoint_ui() -> None:
    editor = _read(ASSETS / 'integrated_editor.mjs')
    assert "const text=store.exportEnvelope(2)" in editor
    assert "function exportModel(){showPreflight();" not in editor
    assert 'id="exportJsonAction">Download Report JSON</button>' in editor
    assert 'id="exportCopyJsonAction">Copy Report JSON</button>' in editor
    assert 'id="exportPngAction"' not in editor and 'id="exportJpegAction"' not in editor
    assert "new XMLSerializer().serializeToString(svg)" in editor
    assert "document.createElementNS('http://www.w3.org/2000/svg','svg')" in editor
    assert "style.textContent=css" in editor
    assert "exportPptAction" not in editor
    assert "try SVG or PowerPoint" not in editor


def test_wave1_lasso_page_size_and_developer_console_have_visible_production_affordances() -> None:
    html = _read(ASSETS / 'integrated_editor.html')
    editor = _read(ASSETS / 'integrated_editor.mjs')
    css = _read(ASSETS / 'integrated_editor.css')
    assert 'id="debugBtn"' in html and 'id="debugBadge"' in html
    assert "on($('#debugBtn'),'click',openDeveloperConsole)" in editor
    assert "updateDebugBadge()" in editor
    assert "box.classList.add('active')" in editor
    assert ".lasso.active{display:block!important" in css
    assert "&&!hull.contains(event.target)" not in editor
    assert "page-size-modal" in editor and "page-size-presets" in editor
    assert ".modal.page-size-modal .dialog" in css
    assert ".topbar{position:sticky" in css


def test_wave1_normal_import_surface_is_json_only() -> None:
    page = _read(PRODUCT / 'page.py')
    assert "Import a Visembler report from its canonical JSON file." in page
    assert "FileUpload(label='Visembler report JSON'" in page
    assert "FileUpload(label='Visembler report PPTX or export template'" not in page
    assert "ppt_status=ui.label(" not in page
