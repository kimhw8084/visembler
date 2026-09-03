from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'company_ui' / 'products' / 'visualizer'
ASSETS = PRODUCT / 'assets'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _node(script: str) -> str:
    completed = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, text=True, capture_output=True, check=True)
    return completed.stdout.strip()


def test_wave2_production_library_is_a_curated_subset_of_the_authoritative_registry() -> None:
    output = _node("""
import { PRODUCTION_LIBRARY, PRODUCTION_LIBRARY_COUNT, productionEntries } from './company_ui/products/visualizer/assets/production_library.mjs';
import { ELEMENTS_BY_ENGINE } from './company_ui/products/visualizer/vendor/production_core/core/runtime_registry.mjs';
const entries=productionEntries();
const missing=entries.filter(entry=>!(ELEMENTS_BY_ENGINE[entry.engine]||[]).includes(entry.element));
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,families:Object.keys(PRODUCTION_LIBRARY).length,missing,keys:entries.map(entry=>`${entry.engine}::${entry.element}`),descriptionsOk:entries.every(entry=>typeof entry.description==='string'&&entry.description.trim().length>10)}));
""")
    payload = json.loads(output)
    assert payload['count'] == 39
    assert payload['families'] == 13
    assert payload['missing'] == []
    assert payload['descriptionsOk'] is True
    visible = set(payload['keys'])
    for hidden in ('CoreChartEngine::Bubble Plot','CoreChartEngine::Sankey','TableEngine::Pivot Grid','MatrixEngine::Correlation Matrix','DiagramEngine::Decision Tree','WaferFabEngine::Wafer Difference Map','EngineeringChartEngine::Response Surface'):
        assert hidden not in visible


def test_wave2_library_ui_no_longer_promises_the_full_audit_registry() -> None:
    editor = _read(ASSETS / 'integrated_editor.mjs')
    html = _read(ASSETS / 'integrated_editor.html')
    page = _read(PRODUCT / 'page.py')
    assert "return productionEntries();" in editor
    assert "Object.keys(PRODUCTION_LIBRARY)" in editor
    assert "PRODUCTION_RECOMMENDED.map" in editor
    assert "Production elements" in editor
    assert "Search ${PRODUCTION_LIBRARY_COUNT} production elements" in editor
    assert 'placeholder="Search 248 elements"' not in html
    assert 'placeholder="Search production elements"' in html
    assert "production_library.mjs" in page


def test_wave2_every_quick_add_element_is_in_the_production_library() -> None:
    output = _node("""
import { isProductionElement } from './company_ui/products/visualizer/assets/production_library.mjs';
const quick=[['MetricEngine','Hero KPI'],['CoreChartEngine','Line Chart'],['TextEngine','Key Takeaway'],['TableEngine','Clean Table'],['TimelineEngine','Event Timeline'],['ImageMediaEngine','Image'],['DiagramEngine','Process Flow'],['DecisionCompositeEngine','Risk Callout']];
console.log(JSON.stringify(quick.map(([engine,element])=>[engine,element,isProductionElement(engine,element)])));
""")
    assert all(value is True for _, _, value in json.loads(output))


def test_wave2_curated_diagrams_render_edited_nodes_and_edges() -> None:
    output = _node("""
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const html=renderIntegratedElement({engine:'DiagramEngine',element:'Process Flow',title:'Edited process',nodes:['Detect','Analyze','Verify','Release'],edges:[['Detect','Analyze'],['Analyze','Verify'],['Verify','Release']],showTitle:true});
console.log(JSON.stringify({html}));
""")
    html = json.loads(output)['html']
    assert all(token in html for token in ('Detect','Analyze','Verify','Release','data-graph-plan=','data-direct="diagram-node:0"'))


def test_wave2_curated_composites_render_the_fields_the_inspector_edits() -> None:
    output = _node("""
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const evidence=renderIntegratedElement({engine:'EvidenceCompositeEngine',element:'Evidence Card',statement:'Pressure excursion',detail:'Matched to onset',status:'Supports'});
const risk=renderIntegratedElement({engine:'DecisionCompositeEngine',element:'Risk Callout',statement:'Release risk',detail:'Control lot is still pending',status:'High'});
console.log(JSON.stringify({evidence,risk}));
""")
    payload = json.loads(output)
    assert all(token in payload['evidence'] for token in ('Pressure excursion','Matched to onset','Supports'))
    assert all(token in payload['risk'] for token in ('Release risk','Control lot is still pending','High'))


def test_wave2_authoritative_registry_and_frozen_connector_are_not_reduced_or_replaced() -> None:
    registry = _read(PRODUCT / 'vendor/production_core/core/runtime_registry.mjs')
    frozen = PRODUCT / 'vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
    assert 'generated from authoritative 248-element deep audit' in registry
    assert '"Sankey"' in registry and '"Pivot Grid"' in registry and '"Decision Tree"' in registry
    assert frozen.is_file() and frozen.stat().st_size > 10_000
