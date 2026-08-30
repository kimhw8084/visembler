from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT/'company_ui/products/visualizer'

def test_r13_capability_matrix_is_complete_and_integration_rendered():
    data=json.loads((PRODUCT/'contracts/ELEMENT_CAPABILITY_MATRIX.json').read_text())
    assert data['count']==248
    assert data['engines']==17
    assert len(data['rows'])==248
    assert len({row['element'] for row in data['rows']})==248
    assert len({row['renderer_variant'] for row in data['rows']})==248
    assert {row['renderer_source'] for row in data['rows']}=={'integration'}
    assert all(row['inspector'] and row['direct_edit'] and row['geometry']['min']['w']>0 for row in data['rows'])

def test_r13_normal_authoring_surface_does_not_expose_release_jargon():
    html=(PRODUCT/'assets/integrated_editor.html').read_text()
    js=(PRODUCT/'assets/integrated_editor.mjs').read_text()
    assert '248 production elements' not in html
    assert 'Golden Connector v5 remains the routing authority.' not in js
    assert '248 elements' in html
    assert 'Connections are routed automatically and stay editable.' in js

def test_r13_visual_certification_tools_are_release_assets():
    tools=ROOT.parent/'tools'
    for name in ('r13_visual_layout_matrix.py','r13_catalog_render_audit.py','r13_element_capabilities.py'):
        assert (tools/name).is_file(), name

def test_r13_editor_uses_integration_renderer_and_direct_editing():
    js=(PRODUCT/'assets/integrated_editor.mjs').read_text()
    renderer=(PRODUCT/'assets/element_renderer.mjs').read_text()
    assert "from './element_renderer.mjs'" in js
    assert 'function openInlineEditor' in js
    assert "case 'InteractionLayer': return interaction(entry);" in renderer
    assert "case 'EditorInfrastructure': return infrastructure(entry);" in renderer
