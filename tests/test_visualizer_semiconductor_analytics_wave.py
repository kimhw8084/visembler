from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from company_ui.products.visualizer.page import _dataset_export_bytes, _safe_download_stem


ROOT = Path(__file__).resolve().parents[1]


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_promoted_analytics_keep_the_legacy_library_and_have_real_renderer_contracts():
    payload = node_json(r'''
import {PRODUCTION_LIBRARY_COUNT, productionEntries, isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
import {CHART_TYPES, chartModelFromEntry, chartToEntry, renderChartSvg, switchChartType} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const dataset={id:'fab',revision:4,fields:[
  {id:'x',name:'Position',type:'number',semantic_tags:[]},
  {id:'y',name:'Measurement',type:'number',semantic_tags:['value']},
  {id:'cause',name:'Defect Cause',type:'categorical',semantic_tags:['category']},
  {id:'count',name:'Count',type:'number',semantic_tags:['weight']},
  {id:'run',name:'Run',type:'categorical',semantic_tags:['identifier']}
],rows:[[1,5,'Particle',10,'A'],[2,8,'Scratch',7,'A'],[3,13,'Particle',3,'B'],[4,11,'Void',1,'B']]};
const promoted=['Multi-Line','Scatter Plot','Regression Scatter','Histogram','Box Plot','Pareto'];
const rendered=promoted.map(type=>{const model=chartModelFromEntry({engine:'CoreChartEngine',element:type,title:type},dataset);const svg=renderChartSvg(model);return {type,svg:svg.slice(0,30),hasSvg:svg.includes('<svg'),safe:!/[Nn]aN|Infinity/.test(svg)};});
const base=chartModelFromEntry({engine:'CoreChartEngine',element:'Line Chart',title:'Yield trend',mapping:{x:'x',y:'y'}},dataset);
const switched=switchChartType(base,'Regression Scatter'),switchedEntry=chartToEntry({engine:'CoreChartEngine',element:'Line Chart',title:'Yield trend'},switched);
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().length,promoted,promotedProduction:promoted.map(element=>isProductionElement('CoreChartEngine',element)),chartTypes:promoted.map(element=>CHART_TYPES.includes(element)),rendered,switch:{type:switched.chart_type,dataset:switched.dataset.id,revision:switched.dataset.revision,title:switchedEntry.title,mapping:switched.mapping}}));
''')
    assert payload["count"] == payload["entries"] == 45
    assert all(payload["promotedProduction"])
    assert all(payload["chartTypes"])
    assert all(item["hasSvg"] and item["safe"] for item in payload["rendered"])
    assert payload["switch"] == {
        "type": "Regression Scatter",
        "dataset": "fab",
        "revision": 4,
        "title": "Yield trend",
        "mapping": {"x": "x", "y": "y"},
    }


def test_data_first_recommendations_are_explainable_and_resolve_to_promoted_targets():
    payload = node_json(r'''
import {intakeText, productionRecommendations} from './company_ui/products/visualizer/assets/authoring_data.mjs';
const cases={
  scatter:'x\ty\n1\t5\n2\t8\n3\t13',
  distribution:'measurement\n10\n12\n11\n13',
  pareto:'defect_cause\tcount\nParticle\t42\nScratch\t18\nVoid\t7',
  spc:'timestamp\tmeasurement\n2026-01-01\t10\n2026-01-02\t11\n2026-01-03\t9',
};
const output=Object.fromEntries(Object.entries(cases).map(([name,text])=>{const result=intakeText(text);return [name,productionRecommendations(result).slice(0,3).map(item=>({view:item.view,target:item.production_target,reason:item.reason}))]}));
console.log(JSON.stringify(output));
''')
    assert payload["scatter"][0]["target"]["element"] == "Scatter Plot"
    assert payload["distribution"][0]["target"]["element"] == "Histogram"
    assert payload["pareto"][0]["target"]["element"] == "Pareto"
    assert payload["spc"][0]["target"]["element"] == "Line Chart"
    assert all(item["reason"] for values in payload.values() for item in values)


def test_governed_engineering_transforms_are_deterministic_and_typed():
    payload = node_json(r'''
import {applyRecipe} from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
const dataset={fields:[{id:'time',name:'Time',type:'integer'},{id:'a',name:'A',type:'number'},{id:'b',name:'B',type:'number'}],rows:[[1,10,2],[2,14,4],[3,13,5],[4,19,7]]};
const recipe={steps:[
  {type:'calculated',source_fields:['a','b'],operation:'subtract',name:'Delta'},
  {type:'difference',source_field:'a',name:'A change'},
  {type:'percent_change',source_field:'a',name:'A % change'},
  {type:'rolling_mean',source_field:'a',window:2,name:'A rolling mean'},
  {type:'z_score',source_field:'a',name:'A z'},
  {type:'cumulative_percent',source_field:'b',name:'B cumulative %'}
]};
const first=applyRecipe(dataset,recipe),second=applyRecipe(dataset,recipe);
console.log(JSON.stringify({fields:first.fields.map(field=>field.name),rows:first.rows,stable:JSON.stringify(first)===JSON.stringify(second),sourceUnchanged:dataset.fields.length===3&&dataset.rows.length===4}));
''')
    assert payload["stable"] is True
    assert payload["sourceUnchanged"] is True
    assert payload["fields"][-6:] == ["Delta", "A change", "A % change", "A rolling mean", "A z", "B cumulative %"]
    assert payload["rows"][0][-5:] == [None, None, 10, -1.0690449676496976, 11.11111111111111]
    assert payload["rows"][3][-1] == 100


def test_engineering_recipe_catalog_is_bounded_to_supported_production_visuals():
    payload = node_json(r'''
import {recommendEngineeringRecipes} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const fields=[
  {id:'tool',name:'Tool',type:'categorical',semantic_tags:['tool']},
  {id:'chamber',name:'Chamber',type:'categorical',semantic_tags:['chamber']},
  {id:'measurement',name:'Measurement',type:'number',semantic_tags:['value']},
  {id:'time',name:'Timestamp',type:'datetime',semantic_tags:['time']},
];
const recipes=recommendEngineeringRecipes(fields);
console.log(JSON.stringify({ids:recipes.map(recipe=>recipe.id),ready:recipes.every(recipe=>recipe.ready),visuals:recipes.flatMap(recipe=>recipe.visuals)}));
''')
    assert "tool-chamber-matching" in payload["ids"]
    assert "spc-excursion" in payload["ids"]
    assert all(item in {"Hero KPI", "Key Takeaway", "Line Chart", "Clean Table", "SPC Control Chart", "Horizontal Bar", "Executive Statement", "Before/After KPI", "Box Plot", "Histogram", "Wafer Map"} for item in payload["visuals"])


def test_recipe_execution_is_an_atomic_multi_visual_production_plan():
    payload = node_json(r'''
import {recipeExecutionPlan} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
import {isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
const fields=[
  {id:'cause',name:'Defect Cause',type:'categorical',semantic_tags:['category']},
  {id:'loss',name:'Yield Loss',type:'number',semantic_tags:['weight']},
  {id:'lot',name:'Lot',type:'identifier',semantic_tags:['lot_id']},
];
const plan=recipeExecutionPlan('yield-pareto',fields);
console.log(JSON.stringify({valid:plan.valid,status:plan.status,visuals:plan.visuals.map(item=>({element:item.element,role:item.role,mapping:item.mapping,production:item.production})),steps:plan.transform_plan.steps,provenance:plan.provenance,allProduction:plan.visuals.every(item=>isProductionElement(item.engine,item.element)),sameSource:plan.visuals.every(item=>item.mapping&&plan.mappings.value==='loss')}));
''')
    assert payload["valid"] is True
    assert payload["status"] == "ready"
    assert [item["element"] for item in payload["visuals"]] == ["Pareto", "Clean Table", "Hero KPI"]
    assert all(item["production"] for item in payload["visuals"])
    assert payload["allProduction"] is True
    assert payload["sameSource"] is True
    assert [step["type"] for step in payload["steps"]] == ["group", "sort", "cumulative_percent"]
    assert payload["provenance"]["recipe_id"] == "yield-pareto"


def test_recipe_mapping_review_is_fail_closed_for_unresolved_roles():
    payload = node_json(r'''
import {recipeExecutionPlan} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const fields=[
  {id:'tool',name:'Tool',type:'categorical',semantic_tags:['tool']},
  {id:'value',name:'Measurement',type:'number',semantic_tags:['value']},
];
const blocked=recipeExecutionPlan('tool-chamber-matching',fields);
const ready=recipeExecutionPlan('tool-chamber-matching',[...fields,{id:'chamber',name:'Chamber',type:'categorical',semantic_tags:['chamber']}]);
console.log(JSON.stringify({blocked:{valid:blocked.valid,status:blocked.status,unresolved:blocked.unresolved},ready:{valid:ready.valid,status:ready.status}}));
''')
    assert payload["blocked"] == {"valid": False, "status": "needs-mapping", "unresolved": ["chamber"]}
    assert payload["ready"] == {"valid": True, "status": "ready"}


def test_dataset_profile_preserves_missing_distinct_and_numeric_range_metadata():
    payload = node_json(r'''
import {profileDataset} from './company_ui/products/visualizer/assets/authoring_data.mjs';
const profile=profileDataset({revision:4,fields:[
  {id:'tool',name:'Tool',type:'categorical',semantic_tags:['tool']},
  {id:'value',name:'Measurement',type:'number',semantic_tags:['value']},
],rows:[['ETCH-01',10],['ETCH-01',null],['ETCH-02',14],['ETCH-03',10]]});
console.log(JSON.stringify(profile));
''')
    assert payload["rows"] == 4
    assert payload["columns"] == 2
    assert payload["source_revision"] == 4
    assert payload["fields"][0]["missing"] == 0
    assert payload["fields"][0]["distinct"] == 3
    assert payload["fields"][1]["missing"] == 1
    assert payload["fields"][1]["distinct"] == 2
    assert payload["fields"][1]["min"] == 10
    assert payload["fields"][1]["max"] == 14


def test_server_dataset_export_is_deterministic_and_filename_safe():
    fields = [
        {"id": "tool", "name": "Tool"},
        {"id": "note", "name": "Engineering note"},
    ]
    rows = [{"tool": "ETCH-01", "note": 'line 1, "review"'}]
    assert _safe_download_stem('../../Weekly yield/2026') == 'Weekly-yield-2026'
    assert _dataset_export_bytes(fields, rows, delimiter=',') == b'Tool,Engineering note\nETCH-01,"line 1, ""review"""\n'
    assert _dataset_export_bytes(fields, rows, delimiter='\t') == b'Tool\tEngineering note\nETCH-01\t"line 1, ""review"""\n'


@pytest.fixture(scope='module')
def recipe_browser():
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as instance:
        executable = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
        options = {'headless': True}
        if executable:
            options.update(executable_path=executable, args=['--no-sandbox'])
        try:
            browser = instance.chromium.launch(**options)
        except playwright.Error as exc:
            pytest.skip(f'Chromium unavailable: {exc}')
        yield browser
        browser.close()


def test_native_recipe_workflow_creates_linked_analysis_with_atomic_undo(recipe_browser, tmp_path):
    scripts = str(ROOT / 'scripts' / 'release_checks')
    sys.path.insert(0, scripts)
    try:
        from editor_host import EditorHost, load_editor
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    with EditorHost(ROOT, tmp_path / 'recipe-data') as host:
        report_id = host.create()
        context = recipe_browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
        page_errors = []
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('console', lambda message: page_errors.append(message.text) if message.type == 'error' else None)
        try:
            load_editor(page, host, report_id)
            ready(page)
            panels(page)
            page.locator('#pasteDataBtn').click()
            page.locator('#dataFirstText').fill('Defect Cause\tYield Loss\tLot\nParticle\t42\tL001\nParticle\t5\tL002\nScratch\t18\tL003\nVoid\t7\tL004')
            page.locator('[data-data-first-recipe="yield-pareto"]').click()
            page.locator('#dataFirstApplyRecipe').click()
            settled(page)
            applied = model(page)
            assert [item['element'] for item in applied['items']] == ['Pareto', 'Clean Table', 'Hero KPI']
            assert len({item['analysis_id'] for item in applied['items']}) == 1
            assert len({item['dataset_id'] for item in applied['items']}) == 1
            assert all(item['analysis_recipe']['id'] == 'yield-pareto' for item in applied['items'])
            rendered = page.locator('.cs-static-chart').evaluate_all('(nodes) => nodes.map(node => node.innerHTML).join("\\n")')
            assert 'Particle: 47' in rendered
            assert 'Scratch: 18' in rendered
            assert 'Void: 7' in rendered
            assert 'Top contributor' in page.locator('body').inner_text()
            analysis_id = applied['items'][0]['analysis_id']
            page.locator('#undo').click()
            settled(page)
            assert model(page)['items'] == []
            page.locator('#redo').click()
            settled(page)
            assert model(page)['items'][0]['analysis_id'] == analysis_id
            primary_id = model(page)['items'][0]['id']
            page.locator(f'.component[data-id="{primary_id}"] [data-chart-point]').first.click()
            page.locator('#activeFilters').wait_for(state='visible')
            assert 'Active filter' in page.locator('#activeFilters').inner_text()
            page.locator('[data-clear-all-filters]').click()
            page.locator('#activeFilters').wait_for(state='hidden')
            page.locator('#exportBtn').click()
            assert page.locator('#exportPptAction').is_visible()
            assert page.locator('#exportPngAction').is_visible()
            assert page.locator('#exportJpegAction').is_visible()
            with page.expect_download() as csv_download:
                page.locator('[data-export-dataset="current-csv"]').click()
            assert csv_download.value.suggested_filename.endswith('.csv')
            page.locator('#exportBtn').click()
            with page.expect_download() as report_download:
                page.locator('#exportJsonAction').click()
            assert report_download.value.suggested_filename.endswith('.json')
            page.locator('#exportBtn').click()
            page.locator('#exportPptAction').click()
            page.wait_for_timeout(100)
            assert any(request.get('type') == 'ppt.export_requested' for request in page.evaluate('window.__HOST_TEST__.requests')), page.locator('#modalBody').inner_text()
            assert not page_errors, page_errors
        finally:
            context.close()


@pytest.mark.parametrize(
    ('recipe_id', 'source_text', 'expected_elements'),
    [
        (
            'spc-excursion',
            'Timestamp\tMeasurement\n2026-01-01\t10\n2026-01-02\t11\n2026-01-03\t9',
            ['SPC Control Chart', 'Clean Table'],
        ),
        (
            'tool-chamber-matching',
            'Tool\tChamber\tMeasurement\nETCH-01\tA\t10\nETCH-01\tB\t12\nETCH-02\tA\t8',
            ['Horizontal Bar', 'Clean Table'],
        ),
        (
            'golden-affected',
            'Cohort\tProcess Position\tReference Value\tAffected Value\nGolden\t1\t10\t11\nAffected\t2\t10\t13\nGolden\t3\t12\t12',
            ['Line Chart', 'Box Plot', 'Clean Table'],
        ),
        (
            'wafer-difference',
            'Die X\tDie Y\tReference Value\tAffected Value\n1\t1\t10\t11\n2\t1\t10\t9\n1\t2\t10\t15',
            ['Wafer Map', 'Clean Table'],
        ),
        (
            'pre-post-change',
            'Status\tMeasurement\nPre\t10\nPost\t12\nPre\t14\nPost\t16\nPost\t20',
            ['Before/After KPI', 'Line Chart', 'Clean Table'],
        ),
        (
            'distribution-review',
            'Measurement\n10\n12\n11\n13',
            ['Box Plot', 'Histogram', 'Clean Table'],
        ),
    ],
)
def test_native_supported_recipe_workflows_create_linked_production_analysis(
    recipe_browser, tmp_path, recipe_id, source_text, expected_elements
):
    scripts = str(ROOT / 'scripts' / 'release_checks')
    sys.path.insert(0, scripts)
    try:
        from editor_host import EditorHost, load_editor
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)

    with EditorHost(ROOT, tmp_path / recipe_id) as host:
        report_id = host.create()
        context = recipe_browser.new_context(viewport={'width': 1440, 'height': 1000})
        page_errors = []
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('console', lambda message: page_errors.append(message.text) if message.type == 'error' else None)
        try:
            load_editor(page, host, report_id)
            ready(page)
            panels(page)
            page.locator('#pasteDataBtn').click()
            page.locator('#dataFirstText').fill(source_text)
            page.locator(f'[data-data-first-recipe="{recipe_id}"]').click()
            page.locator('#dataFirstApplyRecipe').click()
            settled(page)
            applied = model(page)
            assert [item['element'] for item in applied['items']] == expected_elements
            assert len({item['analysis_id'] for item in applied['items']}) == 1
            assert len({item['dataset_id'] for item in applied['items']}) == 1
            assert all(item['analysis_recipe']['id'] == recipe_id for item in applied['items'])
            rendered = page.locator('.cs-static-chart').evaluate_all('(nodes) => nodes.map(node => node.innerHTML).join("\\n")')
            if recipe_id == 'spc-excursion':
                assert '2026-01-01' in rendered
                assert rendered.index('2026-01-01') < rendered.index('2026-01-03')
            elif recipe_id == 'tool-chamber-matching':
                assert 'ETCH-01 · A' in rendered and 'ETCH-01 · B' in rendered
            elif recipe_id == 'golden-affected':
                assert 'Golden' in rendered and 'Affected' in rendered
                assert '10' in rendered and '15' in rendered and '9' in rendered
            elif recipe_id == 'wafer-difference':
                assert 'Delta' in rendered and 'Reference' in rendered and 'Affected' in rendered
                assert '+5' in rendered and '-1' in rendered
            elif recipe_id == 'pre-post-change':
                assert 'Pre' in rendered and 'Post' in rendered
                assert '12' in rendered and '16' in rendered
            elif recipe_id == 'distribution-review':
                assert '10.00' in rendered and '13.00' in rendered
            assert not page_errors, page_errors
        finally:
            context.close()


@pytest.mark.parametrize('viewport_width', [768, 390])
def test_native_recipe_workflow_is_responsive_without_browser_errors(recipe_browser, tmp_path, viewport_width):
    scripts = str(ROOT / 'scripts' / 'release_checks')
    sys.path.insert(0, scripts)
    try:
        from editor_host import EditorHost, load_editor
        from run_editor_workflows import model, ready, settled
    finally:
        sys.path.remove(scripts)

    with EditorHost(ROOT, tmp_path / f'responsive-{viewport_width}') as host:
        report_id = host.create()
        context = recipe_browser.new_context(viewport={'width': viewport_width, 'height': 900})
        page_errors = []
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('console', lambda message: page_errors.append(message.text) if message.type == 'error' else None)
        try:
            load_editor(page, host, report_id)
            ready(page)
            if page.locator('#libraryToggle').get_attribute('aria-pressed') != 'true':
                page.locator('#libraryToggle').click()
            page.locator('#pasteDataBtn').scroll_into_view_if_needed()
            page.locator('#pasteDataBtn').click()
            page.locator('#dataFirstText').fill('Defect Cause\tYield Loss\nParticle\t42\nScratch\t18')
            page.locator('[data-data-first-recipe="yield-pareto"]').click()
            page.locator('#dataFirstApplyRecipe').click()
            settled(page)
            assert [item['element'] for item in model(page)['items']] == ['Pareto', 'Clean Table', 'Hero KPI']
            assert page.locator('body').evaluate('(node) => node.scrollWidth <= window.innerWidth + 1')
            assert not page_errors, page_errors
        finally:
            context.close()
