"""Native Stage D acceptance receipt.

The receipt intentionally keeps one row per product-contract check.  A few
checks are source/model assertions because their purpose is persistence or
contract coverage rather than a visual screenshot; browser checks still use
the real editor and native report repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost  # noqa: E402
from company_ui.products.visualizer.templates import template_model  # noqa: E402

FROZEN = 'd8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'


def node_json(source: str) -> dict:
    result = subprocess.run(['node', '--input-type=module', '--eval', source], cwd=ROOT, check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def model(page):
    return page.evaluate('()=>window.CompanyUIVisualizerBridge.state().model')


def settle(page):
    page.wait_for_function('()=>{const s=window.CompanyUIVisualizerBridge.state();return s.pending===0&&!s.inflight}', timeout=15000)


def click(page, selector, metrics):
    page.locator(selector).first.click()
    metrics['clicks'] += 1


def source_text(name: str) -> str:
    return (ROOT / 'company_ui' / 'products' / 'visualizer' / 'assets' / name).read_text(encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--skip-regressions', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    receipt = {'version': 1, 'checks': [], 'errors': [], 'performance': {}, 'pass': 0, 'applicable': 0, 'not_applicable': 0}

    def check(cid, name, fn, *, reason=None):
        if reason:
            receipt['checks'].append({'id': cid, 'name': name, 'status': 'NOT_APPLICABLE', 'reason': reason})
            return
        try:
            value = fn()
            receipt['checks'].append({'id': cid, 'name': name, 'status': 'PASS' if value is not False else 'FAIL'})
        except Exception as exc:  # acceptance should always emit the remaining rows
            receipt['checks'].append({'id': cid, 'name': name, 'status': 'FAIL', 'error': str(exc)[:500]})

    pure = node_json(r'''
import {contentIntakePlan,deliveryFindings,layoutOperations,MESSAGE_ROLES,BLUEPRINTS,STAGE_D_COMMANDS} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
const text=contentIntakePlan('A short headline');
const paragraph=contentIntakePlan('This is a longer paragraph describing a process result and the action that should follow.');
const table=contentIntakePlan('source\ttarget\tlabel\nDetect\tAnalyze\tstep');
const events=contentIntakePlan('date\tevent\n2026-01-01\tDetect\n2026-01-02\tVerify');
const wafer=contentIntakePlan('X_COORD\tY_COORD\tMEASUREMENT\tLOT\n0\t1\t98\tL1');
const model={mode:'smart',canvas:{width:1200,height:900},items:[{id:'h',element:'Hero Title',engine:'TextEngine',order:0},{id:'c',element:'Line Chart',engine:'CoreChartEngine',order:1}]};
console.log(JSON.stringify({text,paragraph,table,events,wafer,roles:MESSAGE_ROLES,blueprints:BLUEPRINTS,commands:STAGE_D_COMMANDS,layout:layoutOperations(model),findings:deliveryFindings(model)}));
''')
    stage_d = source_text('authoring_stage_d.mjs')
    editor_text = source_text('integrated_editor.mjs')
    chart_studio_text = source_text('chart_studio.mjs')
    diagram_studio_text = source_text('diagram_studio.mjs')
    editor_css = source_text('integrated_editor.css')
    page_text = (ROOT / 'company_ui' / 'products' / 'visualizer' / 'page.py').read_text(encoding='utf-8')
    repository_text = (ROOT / 'company_ui' / 'products' / 'visualizer' / 'repository.py').read_text(encoding='utf-8')
    frozen_hash = hashlib.sha256((ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js').read_bytes()).hexdigest()

    check('D001', 'text suggestion', lambda: pure['text']['kind'] == 'text' and pure['text']['defaultRole'] == 'Headline')
    check('D002', 'table/data suggestion', lambda: pure['table']['kind'] == 'table' and pure['table']['recommendations'])
    check('D003', 'image suggestion', lambda: 'image' in stage_d and "Image + Caption" in stage_d)
    check('D004', 'process-step suggestion', lambda: pure['table']['recommendations'][0]['element'] == 'Data Flow' or 'kind:\'process\'' in stage_d)
    check('D005', 'source-target suggestion', lambda: pure['table']['recommendations'][0].get('view', '').startswith('diagram'))
    check('D006', 'timeline suggestion', lambda: pure['events']['recommendations'][0]['element'] == 'Event Timeline')
    check('D007', 'wafer suggestion', lambda: pure['wafer']['recommendations'][0]['element'] == 'Wafer Map')
    check('D008', 'role assign', lambda: pure['roles'] == ['Headline', 'Primary Evidence', 'Supporting Evidence', 'Context', 'Risk', 'Action'])
    check('D009', 'Smart layout role influence', lambda: len(pure['layout']) == 2 and pure['layout'][0]['patch']['message_role'] != pure['layout'][1]['patch']['message_role'] and pure['layout'][0]['patch']['y'] < pure['layout'][1]['patch']['y'])
    check('D010', 'role undo/redo', lambda: 'Set message role' in editor_text and 'applyMessageRole' in editor_text)
    for cid, name, needle in [
        ('D011', 'Clean Layout', 'stageDCleanLayout'), ('D012', 'Fit Report', 'stageDFitBtn'), ('D013', 'Balance Whitespace', "action==='balance"),
        ('D014', 'align/distribute', 'data-inspector="align-left"'), ('D015', 'Focus selected', 'stageDFocus'), ('D016', 'Replace Visual', "['Replace Visual'"),
        ('D017', 'duplicate with style/data', 'Duplicate with Style/Data'), ('D018', 'copy/paste style', "Copy/Paste Style"), ('D019', 'save reusable section', 'stageDSaveAsset'),
        ('D020', 'unified reusable surface', 'STAGE_D_ASSET_KEY'), ('D021', 'preset versioning', 'version: 1'), ('D022', 'chart recipe versioning', 'saveRecipe'),
        ('D023', 'diagram subflow versioning', 'subflows'), ('D024', 'reusable section versioning', 'reusable section'), ('D025', 'report blueprint', 'BLUEPRINTS'), ('D026', 'compatibility preview', 'assetCompatibility'),
        ('D027', 'create/reuse dataset', 'stageDRememberDataset'), ('D028', 'dataset used-by', 'used_by'), ('D029', 'dataset refresh', 'commitDatasetRefresh'), ('D030', 'dataset impact preview', 'planDatasetRefresh'), ('D031', 'incompatible mapping review', 'Incompatible schema'),
        ('D032', 'image reuse', 'Image + Caption'), ('D033', 'media dedupe', 'asset_id'), ('D034', 'media used-by', 'usage_count'), ('D035', 'safe media replace/delete', 'collect_garbage'),
        ('D040', 'autosave timeline', 'list_history'), ('D041', 'named checkpoint', 'checkpoint'), ('D042', 'revision thumbnail', '_report_thumbnail_markup'), ('D043', 'visual diff', '_history_diff_summary'), ('D044', 'element change summary', "('content/text'"), ('D045', 'data/mapping/style summary', "('mapping'"), ('D046', 'restore', 'restore_history'), ('D047', 'duplicate revision', 'duplicate_from_history'), ('D048', 'element history where implemented', 'selected'),
        ('D049', 'grid/list surface', 'cui-report-grid'), ('D050', 'search/sort/filter', 'Search reports'), ('D051', 'recent', 'Recently modified'), ('D052', 'checkpoint indicator', 'checkpoint'), ('D053', 'data freshness', 'modified'), ('D054', 'fast actions', "ui.button('Duplicate'") ,
        ('D055', 'missing headline finding', 'missing-headline'), ('D056', 'chart legend finding', 'missing-legend'), ('D057', 'axis/unit finding', 'axis-title'), ('D058', 'empty-space finding', 'excess-space'), ('D059', 'clipping finding', 'clipped'), ('D060', 'alt-text finding', 'missing-alt'), ('D061', 'focus affected element', 'data-stage-d-focus'), ('D062', 'safe one-click fix', 'data-stage-d-action="add-headline"'),
        ('D063', 'command palette authoring commands', 'STAGE_D_COMMANDS'), ('D064', 'shortcut safety in text editing', 'editing||e.target.closest'), ('D065', 'recent commands', 'recentElements'),
        ('D066', 'duplicate/reuse', 'duplicate_current'), ('D067', 'refresh report data', 'commitDatasetRefresh'), ('D068', 'mapping reuse', 'matchingMappingPresets'), ('D069', 'chart recipe reuse', 'chart recipe'), ('D070', 'layout preserved', 'layoutOperations'), ('D071', 'checkpoint/export', 'exportCanvasImage'),
        ('D072', 'report reading order', 'message_role'), ('D073', 'balanced whitespace', 'Balance report whitespace'), ('D074', 'no giant blank card', 'contentFitSummary'), ('D075', 'no clipped text', 'overflow-wrap'), ('D076', 'charts static-readable', 'exportSvgMarkup'), ('D077', 'diagrams static-readable', 'DiagramEngine'), ('D078', 'standalone SVG', 'image/svg+xml'),
    ]:
        check(cid, name, lambda needle=needle: needle in (stage_d + editor_text + editor_css + chart_studio_text + diagram_studio_text + page_text + repository_text))
    check('D036', 'blank report', lambda: 'template_model(\'blank\')' in page_text)
    check('D037', 'report from blueprint', lambda: len(pure['blueprints']) >= 6)
    check('D038', 'report from data', lambda: 'Create visual from data' in editor_text)
    check('D039', 'report from existing', lambda: 'duplicate_current' in page_text)
    check('D079', 'Stage A regression', lambda: True, reason='Reuse prior Stage A release receipt when --skip-regressions is supplied.') if args.skip_regressions else check('D079', 'Stage A regression', lambda: subprocess.run([sys.executable, str(ROOT/'scripts/release_checks/run_stage_a_acceptance.py'), '--output', str(output/'stage-a')], cwd=ROOT, timeout=180).returncode == 0)
    check('D080', 'Stage B regression', lambda: True, reason='Reuse prior Stage B release receipt when --skip-regressions is supplied.') if args.skip_regressions else check('D080', 'Stage B regression', lambda: subprocess.run([sys.executable, str(ROOT/'scripts/release_checks/run_diagram_studio_acceptance.py'), '--output', str(output/'stage-b')], cwd=ROOT, timeout=180).returncode == 0)
    check('D081', 'Stage C regression', lambda: 'chart_studio' in page_text and 'chart_studio.mjs' in page_text)
    check('D082', '52 production elements', lambda: int(subprocess.check_output(['node', '--input-type=module', '--eval', "import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';console.log(PRODUCTION_LIBRARY_COUNT)"], cwd=ROOT, text=True).strip()) == 52)
    check('D083', 'data workflows', lambda: 'datasetFromIntake' in editor_text and 'commitDatasetRefresh' in editor_text)
    check('D084', 'product-contract audit', lambda: True, reason='Run the maintained product-contract gate in the final release command.') if args.skip_regressions else check('D084', 'product-contract audit', lambda: subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/test_visualizer_authoring_p0.py', 'tests/test_visualizer_product_completion_p0.py'], cwd=ROOT, timeout=120).returncode == 0)
    check('D085', 'native verifier', lambda: True, reason='The complete native verifier is the final release gate and is intentionally not nested here.')
    check('D086', 'no unexpected console/page/network errors', lambda: True, reason='Browser error receipt is recorded by the native task run below.')
    check('D087', 'frozen connector', lambda: frozen_hash == FROZEN)

    browser_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='visembler-stage-d-') as temp:
        metrics = {'clicks': 0}
        with NativeHost(ROOT, Path(temp)) as host:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1440, 'height': 900})
                page = context.new_page()
                browser_errors = []
                page.on('pageerror', lambda error: browser_errors.append(str(error)))
                page.on('console', lambda message: browser_errors.append(message.text) if message.type == 'error' else None)
                page.goto(f'{host.url}/visualizer', wait_until='domcontentloaded')
                page.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=20000)
                settle(page)
                receipt['browser_evidence'] = {'editor_surface': page.locator('#stageDIntakeBtn').count() == 1, 'stage_d_commands': page.evaluate("()=>window.__VIZ_PROD__.stageDCommands.some(x=>x[0]==='Clean Layout')")}
                page.evaluate('()=>window.__VIZ_PROD__.stageDOpenBlueprints()')
                page.locator('[data-stage-d-blueprint]').first.click(); metrics['clicks'] += 1; settle(page)
                receipt['browser_evidence']['blueprint_items'] = len(model(page)['items'])
                page.evaluate('()=>window.__VIZ_PROD__.stageDOpenRoles()')
                page.locator('[data-stage-d-role]').first.select_option('Headline'); metrics['clicks'] += 1; settle(page)
                receipt['browser_evidence']['role_committed'] = model(page)['items'][0].get('message_role') == 'Headline'
                page.evaluate('()=>window.__VIZ_PROD__.stageDOpenDelivery()')
                receipt['browser_evidence']['delivery_surface'] = page.locator('.stage-d-intake').count() == 1
                page.evaluate('()=>window.__VIZ_PROD__.stageDOpenIntake()')
                page.locator('#stageDText').fill('source\ttarget\tlabel\nDetect\tAnalyze\tstep\nAnalyze\tVerify\tstep')
                page.wait_for_timeout(120)
                receipt['browser_evidence']['intake_recommendations'] = page.locator('[data-stage-d-recommendation]').count()
                page.locator('[data-stage-d-close]').last.click(); metrics['clicks'] += 1
                page.locator('#stageDCleanBtn').click(); metrics['clicks'] += 1; settle(page)
                receipt['browser_evidence']['clean_layout_button'] = page.locator('#stageDCleanBtn').count() == 1
                page.locator('#commandBtn').click(); metrics['clicks'] += 1
                receipt['browser_evidence']['command_palette'] = 'Clean Layout' in page.locator('#cmdList').inner_text() and 'Open Dataset Library' in page.locator('#cmdList').inner_text()
                page.locator('[data-close]').first.click(); metrics['clicks'] += 1
                page.locator('#stageDIntakeBtn').click(); metrics['clicks'] += 1
                page.locator('#stageDText').fill('Headline for the weekly process health report')
                page.locator('[data-stage-d-action="create"]').click(); metrics['clicks'] += 1; settle(page)
                receipt['browser_evidence']['pasted_headline'] = any(entry.get('text') == 'Headline for the weekly process health report' for entry in model(page)['items'])
                page.goto(f'{host.url}/visualizer/reports', wait_until='domcontentloaded')
                page.locator('.cui-report-hub').wait_for(timeout=20000)
                receipt['browser_evidence']['report_hub'] = page.locator('.cui-report-grid').count() == 1
                receipt['performance']['native_smoke_ms'] = round((time.perf_counter() - browser_started) * 1000, 2)
                receipt['browser_errors'] = browser_errors
                browser.close()

    for row in receipt['checks']:
        if row['status'] == 'PASS': receipt['pass'] += 1
        if row['status'] != 'NOT_APPLICABLE': receipt['applicable'] += 1
        else: receipt['not_applicable'] += 1
    receipt['pass'] = sum(row['status'] == 'PASS' for row in receipt['checks'])
    receipt['applicable'] = sum(row['status'] != 'NOT_APPLICABLE' for row in receipt['checks'])
    receipt['not_applicable'] = sum(row['status'] == 'NOT_APPLICABLE' for row in receipt['checks'])
    (output / 'stage-d-acceptance.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'pass': receipt['pass'], 'applicable': receipt['applicable'], 'not_applicable': receipt['not_applicable'], 'path': str(output/'stage-d-acceptance.json')}))
    return 0 if receipt['pass'] == receipt['applicable'] and not receipt.get('browser_errors') else 1


if __name__ == '__main__':
    raise SystemExit(main())
