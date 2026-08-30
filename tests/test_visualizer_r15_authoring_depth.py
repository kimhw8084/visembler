from __future__ import annotations

import json
import subprocess
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'company_ui/products/visualizer'


def test_r15_catalog_renderer_has_a_clean_title_free_default_for_all_248_elements():
    """Every library card must insert as usable canvas content, not a labeled gallery tile."""
    script = '''
import { ELEMENTS_BY_ENGINE } from './company_ui/products/visualizer/vendor/production_core/core/runtime_registry.mjs';
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const rows=[];
for (const [engine, elements] of Object.entries(ELEMENTS_BY_ENGINE)) for (const element of elements) {
  const name=typeof element==='string'?element:(element.element||element.name);
  const html=renderIntegratedElement({id:'test',type:'text',engine,element:name,title:name,showTitle:false,textAlign:'left',
    data:[['Baseline',72],['Release',91]],rows:[{label:'Baseline',value:72}],
    customTable:{headers:['Measure','Value'],rows:[['Yield','98.7%']]},
    milestones:[{label:'Discover',date:'Week 1'},{label:'Validate',date:'Week 2'}],
    nodes:['Signal','Analyze','Decision'],edges:[['Signal','Analyze'],['Analyze','Decision']],
    observations:[{label:'1',value:98.2},{label:'2',value:98.8}],statement:'A useful example',detail:'Meaningful context'});
  rows.push([name, html.length, html.includes('<h3>'), html.includes('title-hidden')]);
}
console.log(JSON.stringify(rows));
'''
    run = subprocess.run(['node', '--input-type=module', '--eval', script], cwd=ROOT, text=True, capture_output=True, check=True)
    rows = json.loads(run.stdout)
    assert len(rows) == 248
    assert all(length > 100 and not has_title and title_hidden for _, length, has_title, title_hidden in rows)


def test_r15_title_visibility_alignment_and_starter_data_are_explicit_authoring_contracts():
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    renderer = (PRODUCT / 'assets/element_renderer.mjs').read_text(encoding='utf-8')
    css = (PRODUCT / 'assets/integrated_editor.css').read_text(encoding='utf-8')
    for token in ('showTitle:false', 'iShowTitle', 'iTextAlign', 'chartStarterData', 'timelineStarter', 'diagramStarter', 'data-chart-action', 'data-diagram-action="add-connected"'):
        assert token in editor
    for token in ('title-hidden', 'align-${alignment(', 'entry.fit===\'fit\'', 'entry.focal'):
        assert token in renderer
    assert '.gallery-card.title-hidden>.card-body' in css
    assert '.gallery-card.align-center .card-body' in css and '.gallery-card.align-right .card-body' in css


def test_r15_presentation_fields_survive_the_persisted_model_contract():
    from company_ui.products.visualizer.domain import canonical_model

    model = canonical_model({'items': [{'id':'text-1','type':'text','order':0,'title':'Optional', 'showTitle':False, 'textAlign':'right'}]})
    assert model['items'][0]['showTitle'] is False
    assert model['items'][0]['textAlign'] == 'right'


def test_r15_semantic_bridge_keeps_the_active_report_closure_bound():
    tree = ast.parse((PRODUCT / 'page.py').read_text(encoding='utf-8'))
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'handle_semantic')
    assert any('current' in node.names for node in ast.walk(handler) if isinstance(node, ast.Nonlocal))


def test_r15_developer_console_exposes_live_events_and_safe_copy_actions():
    html = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    assert 'id="debugBtn"' in html and 'id="debugModal"' in html
    for token in ('debugEvent(', 'renderDeveloperConsole', 'copyDeveloperPayload', 'Window error', 'Unhandled rejection', 'data-debug-action'):
        assert token in editor


def test_visembler_branding_is_consistent_while_compatibility_identifiers_remain_stable():
    page = (PRODUCT / 'page.py').read_text(encoding='utf-8')
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    toolbar = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')
    assert "AppShell('Visembler'" in page
    assert "PageHeader('Visembler'" in page
    assert "NavItem('visualizer','Visembler','/visualizer'" in page
    assert 'aria-label="Visembler toolbar"' in toolbar
    assert "a.download='visembler_report_model.json'" in editor
    assert "window.CompanyUIVisualizerBridge" in editor
