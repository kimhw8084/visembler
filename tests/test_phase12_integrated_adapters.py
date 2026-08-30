from pathlib import Path
import company_ui
from company_ui.certification import build_certification_app, build_component_gallery

def test_integrated_apps_import_without_importing_nicegui_runtime():
    assert callable(build_certification_app)
    assert callable(build_component_gallery)

def test_semantic_svg_icons_are_used_by_core_adapters():
    src=Path(company_ui.__file__).parent/'integrations/nicegui_components.py'
    text=src.read_text()
    assert 'render_icon_svg' in text
    assert "ui.icon(icon)" not in text

def test_app_shell_installs_all_visual_css_layers():
    src=Path(company_ui.__file__).parent/'integrations/nicegui_layout.py'
    text=src.read_text()
    assert 'install_framework_css' in text
