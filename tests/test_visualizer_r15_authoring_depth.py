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
    page = (PRODUCT / 'page.py').read_text(encoding='utf-8')
    assert 'id="debugBtn"' in html and 'id="debugBadge"' in html and 'id="debugModal"' in html
    assert 'on_developer_console=open_developer_console' in page
    for token in ('debugEvent(', 'updateDebugBadge(', 'renderDeveloperConsole', 'copyDeveloperPayload', 'Window error', 'Unhandled rejection', 'data-debug-action'):
        assert token in editor


def test_r19_layouts_and_page_size_are_authored_not_implicitly_resized():
    from company_ui.products.visualizer.domain import canonical_model

    model = canonical_model({'canvas': {'width': 1600, 'height': 900}})
    assert model['canvas'] == {'width': 1600, 'height': 900}
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    html = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')
    css = (PRODUCT / 'assets/integrated_editor.css').read_text(encoding='utf-8')
    assert "const targetH=CANVAS.h" in editor
    assert "id=\"pageSizeBtn\"" in html and "id=\"layoutBtn\"" not in html
    assert 'function setCanvasSize(width, height)' in editor and 'function openLayoutGallery()' not in editor
    assert "commitOps('Apply built-in preset',[{op:'model.replace',value:next}]" in editor
    assert editor.count("{id:'") >= 10 and 'const LAYOUT_ORDER=Object.freeze' in editor
    assert 'component[data-content-density="fit"]' in css
    assert 'width:8px; height:8px' in css and 'component.selected::before { inset:0!important' in css

    script = '''
import { parseCanonical, serializeCanonical } from './company_ui/products/visualizer/vendor/production_core/core/editor_store.mjs';
const model=parseCanonical({canvas:{width:1600,height:900},items:[],groups:{},datasets:[],mode:'guided',layoutPreset:'editorial',crossFilter:null,nextId:1});
if(model.canvas.width!==1600||model.canvas.height!==900)throw new Error('canvas was not retained');
if(parseCanonical(serializeCanonical(model)).canvas.height!==900)throw new Error('canvas did not round trip');
'''
    subprocess.run(['node', '--input-type=module', '--eval', script], cwd=ROOT, text=True, capture_output=True, check=True)


def test_r22_minimap_is_opt_in_at_startup():
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    shell = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')

    assert 'showMini: false' in editor
    assert 'id="miniToggle" aria-pressed="false"' in shell


def test_r23_smart_layout_uses_its_compacted_row_height_and_authoring_panes_are_explicit():
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    shell = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')
    css = (PRODUCT / 'assets/integrated_editor.css').read_text(encoding='utf-8')

    assert 'const h=spec.height' in editor
    assert 'Math.max(policy.minH,spec.height)' not in editor
    assert 'show or hide the element library' in shell.lower()
    assert 'id="historyBtn"' in shell
    assert 'data-library="open"' in shell and 'data-inspector="open"' in shell
    assert '.cui-visualizer-root.preview-mode' in css
    assert "const AUTHORING_VERSION = 'v0.4.26';" in editor and '>v0.4.26</span>' in shell
    assert 'id="libraryToggle"' in shell and 'aria-pressed="true"' in shell and 'id="inspectorToggle"' in shell


def test_r25_smart_layout_fills_the_fixed_page_and_table_preview_is_not_capped_at_five_rows():
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    renderer = (PRODUCT / 'assets/element_renderer.mjs').read_text(encoding='utf-8')
    css = (PRODUCT / 'assets/integrated_editor.css').read_text(encoding='utf-8')
    page = (PRODUCT / 'page.py').read_text(encoding='utf-8')

    assert 'for(const spec of rowSpecs)spec.height+=extra/rowSpecs.length' in editor
    assert "beginPointerSession($('#viewport')" in editor
    assert "box.classList.add('active')" in editor
    assert ".lasso.active{display:block!important" in css
    assert "&&!hull.contains(event.target)" not in editor
    assert "id:'showcase'" in editor
    assert '(bound.rows||[]).slice(0,5)' not in renderer
    assert '.minimap { display:none; }' in css
    assert "ui.button('History',on_click=open_history)" not in page
    assert "function exportCanvasImage(format)" in editor
    assert "maxPixels=64_000_000" in editor


def test_r20_interaction_elements_keep_controls_operable_and_hidden_titles_hidden():
    script = '''
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const tabs=renderIntegratedElement({engine:'InteractionLayer',element:'Tabs',title:'Hidden',showTitle:false,tab:'Evidence'});
if(tabs.includes('>Hidden<') || !tabs.includes('data-tab="Evidence"')) throw new Error('tabs title or controls are wrong');
const expand=renderIntegratedElement({engine:'InteractionLayer',element:'Expandable Detail',expanded:false});
if(!expand.includes('data-action="expand"') || expand.includes('expand-detail-live')) throw new Error('expand state is not bound');
const timeline=renderIntegratedElement({engine:'InteractionLayer',element:'Interactive Timeline',tm:2});
if(!timeline.includes('data-tm="2"') || !timeline.includes('aria-pressed="true"')) throw new Error('timeline controls are not bound');
'''
    subprocess.run(['node', '--input-type=module', '--eval', script], cwd=ROOT, text=True, capture_output=True, check=True)


def test_visembler_branding_is_consistent_while_compatibility_identifiers_remain_stable():
    page = (PRODUCT / 'page.py').read_text(encoding='utf-8')
    editor = (PRODUCT / 'assets/integrated_editor.mjs').read_text(encoding='utf-8')
    toolbar = (PRODUCT / 'assets/integrated_editor.html').read_text(encoding='utf-8')
    css = (PRODUCT / 'assets/integrated_editor.css').read_text(encoding='utf-8')
    assert "AppShell('Visembler'" in page
    assert 'cui-visualizer-workspace' in page
    assert 'cui-visualizer-workspace { height:calc(100dvh - var(--cui-shell-header-height) - 24px)' in css
    assert '.cui-visualizer-host > * { display:block; flex:1 1 0; min-height:0; height:100%; }' in css
    assert "NavItem('visualizer','Visembler','/visualizer'" in page
    assert 'aria-label="Visembler toolbar"' in toolbar
    assert "a.download='visembler_report_model.json'" in editor
    assert "window.CompanyUIVisualizerBridge" in editor
