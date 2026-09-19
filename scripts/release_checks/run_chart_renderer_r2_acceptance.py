#!/usr/bin/env python3
"""Native CHG-137 R2 browser proof and screenshot matrix.

This is deliberately a probe, not a certification replacement.  It records
the live browser state for the repaired bar geometry, semantic selection,
keyboard controls, transient interaction state, and constrained layouts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]


def dataset(kind: str) -> dict:
    fields = [
        {'id': 'category', 'name': 'Category with a long engineering label', 'type': 'categorical'},
        {'id': 'value', 'name': 'Measured value', 'type': 'number'},
        {'id': 'series', 'name': 'Series with a deliberately long label', 'type': 'categorical'},
        {'id': 'time', 'name': 'Observation time', 'type': 'date'},
        {'id': 'x', 'name': 'Numeric X', 'type': 'number'},
        {'id': 'y', 'name': 'Numeric Y', 'type': 'number'},
        {'id': 'secondary', 'name': 'Secondary measurement', 'type': 'number'},
        {'id': 'note', 'name': 'Operator note', 'type': 'categorical'},
    ]
    rows = []
    categories = ['Category Alpha with an extended label', 'Category Beta with an extended label', 'Category Gamma with an extended label', 'Category Delta with an extended label']
    series = [f'Run {index:02d} — long configured series label' for index in range(1, 13)]
    if kind == 'bar':
        values = [4, -2, 7, 3, -5, 6, 2, -1, 8, -3, 5, 4]
        for index, category in enumerate(categories):
            for series_index in range(3):
                rows.append([category, values[(index * 3 + series_index) % len(values)], series[index * 3 + series_index], f'2026-01-{index + 1:02d}', index + .25, values[(index * 3 + series_index) % len(values)], (index + 1) * 10 + series_index, 'bar evidence'])
    elif kind == 'time':
        dates = ['2026-01-01', '2026-01-02', '2026-01-05', '2026-01-12', '2026-02-01', '2026-03-18']
        for index, date in enumerate(dates):
            for series_index in range(3):
                value = [2, 5, 3, 9, 4, 12][index] + series_index
                rows.append([categories[index % len(categories)], value, series[series_index], date, index, value, value * 10, 'time evidence'])
    else:
        for index, value in enumerate([4, -3, 8, -6, 2, 11, -1, 5]):
            rows.append([categories[index % len(categories)], value, series[index % 4], f'2026-01-{index + 1:02d}', index * 1.7, value, index + 20, 'scatter evidence'])
    return {'id': f'chart-r2-{kind}', 'name': f'R2 {kind} observations', 'revision': 1, 'fields': fields, 'rows': rows, 'warnings': [], 'metadata': {}}


def report_model(canonical_model, kind: str) -> dict:
    source = dataset(kind)
    if kind == 'bar':
        element, mapping = 'Vertical Bar', {'category': 'category', 'value': 'value', 'series': 'series', 'x': 'category', 'y': 'value', 'secondaryY': 'secondary'}
    elif kind == 'time':
        element, mapping = 'Line Chart', {'x': 'time', 'y': 'value', 'series': 'series', 'secondaryY': 'secondary'}
    else:
        element, mapping = 'Scatter Plot', {'x': 'x', 'y': 'y', 'series': 'series', 'secondaryY': 'secondary'}
    item = {'id': 'chart-r2', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': element, 'title': f'R2 {kind} evidence', 'dataset_id': source['id'], 'mapping': mapping, 'data': [], 'weight': 2.4, 'order': 0, 'locked': False, 'z': 1}
    return canonical_model({'items': [item], 'datasets': [source], 'groups': {}, 'mode': 'smart', 'layoutPreset': 'editorial', 'canvas': {'width': 1600, 'height': 900}, 'nextId': 2})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True, choices=('base', 'candidate'))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(HERE))
    from company_ui.products.visualizer.domain import canonical_model
    from editor_host import NativeHost
    from native_common import BrowserEvents, browser_kwargs, ready
    from playwright.sync_api import sync_playwright

    receipt = {'label': args.label, 'root': str(root), 'checks': [], 'screenshots': [], 'viewports': [], 'errors': [], 'source': {}}
    shots = output / 'screenshots'
    shots.mkdir(parents=True, exist_ok=True)

    def check(name: str, fn) -> None:
        row = {'name': name, 'status': 'FAIL'}
        try:
            value = fn()
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], bool):
                passed, details = value
                if not passed:
                    raise AssertionError(f'probe returned false: {details}')
                value = details
            if value is False:
                raise AssertionError('probe returned false')
            row['status'] = 'PASS'
            if value is not None:
                row['details'] = value
        except Exception as exc:
            row['error'] = str(exc) or repr(exc)
            row['traceback'] = traceback.format_exc()
        receipt['checks'].append(row)
        print(f"{row['status']} {name}", flush=True)

    def holdout(name: str, reason: str) -> None:
        receipt['checks'].append({'name': name, 'status': 'NOT_APPLICABLE', 'reason': reason})
        print(f'NOT_APPLICABLE {name}', flush=True)

    def state(page):
        return page.evaluate('()=>JSON.parse(JSON.stringify(window.CompanyUIChartStudio.state))')

    def model_hash(page):
        return page.evaluate('()=>window.CompanyUIChartStudio.hash()')

    def screenshot(page, name: str):
        path = shots / name
        page.screenshot(path=str(path), animations='disabled')
        receipt['screenshots'].append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size, 'dimensions': page.evaluate('()=>({width:innerWidth,height:innerHeight,devicePixelRatio})')})

    def bounds(page):
        return page.evaluate('''()=>{const svg=document.querySelector('#cs-canvas svg');if(!svg)return {svg:false};const s=svg.getBoundingClientRect();const box=n=>{const b=n.getBoundingClientRect();return {left:b.left,top:b.top,right:b.right,bottom:b.bottom,width:b.width,height:b.height}};const inside=b=>b.left>=s.left-1&&b.top>=s.top-1&&b.right<=s.right+1&&b.bottom<=s.bottom+1;const legends=[...svg.querySelectorAll('.cs-legend-item,[data-legend-series]')].map(box);const axes=[...svg.querySelectorAll('.cs-axis-label,.cs-axis-title,[data-secondary-axis]')].map(box);const plot=svg.querySelector('.cs-plot-area');return {svg:true,viewBox:svg.getAttribute('viewBox'),svgBox:box(svg),plot:plot?box(plot):null,plotUseful:!!plot&&plot.getBoundingClientRect().width>=64&&plot.getBoundingClientRect().height>=64,legends,axes,legendBoundsInside:legends.every(inside),axisBoundsInside:axes.every(inside),overflow:svg.scrollWidth>svg.clientWidth+1||svg.scrollHeight>svg.clientHeight+1}}''')

    def semantic_mark_selection(page):
        snapshot = state(page)
        model = snapshot['model']
        fields = model.get('dataset', {}).get('fields', [])
        mapping = model.get('mapping', {})
        mapped_roles = ('category', 'x', 'time', 'value', 'y', 'series', 'color')
        expected = {index for role in mapped_roles for index, field in enumerate(fields) if field.get('id') == mapping.get(role)}
        selected = set(snapshot.get('selectedCols', []))
        return snapshot.get('selectedRows') == [0] and expected.issubset(selected) and selected != {0}

    try:
        with tempfile.TemporaryDirectory(prefix=f'visembler-r2-{args.label}-') as td:
            with NativeHost(root, Path(td) / 'data') as host, sync_playwright() as playwright:
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context(accept_downloads=True, viewport={'width': 1440, 'height': 900})
                page = context.new_page()
                page.set_default_timeout(12000)
                events = BrowserEvents()
                events.attach(page)
                report_ids = {kind: host.create(model=report_model(canonical_model, kind), name=f'r2-{kind}-{args.label}') for kind in ('bar', 'time', 'scatter')}

                def open_main(kind='bar'):
                    page.goto(f'{host.url}/visualizer?report={quote(report_ids[kind])}', wait_until='domcontentloaded')
                    ready(page, require_settled=True)
                    page.locator('.cui-visualizer-root').first.wait_for(timeout=20000)
                    page.wait_for_timeout(160)

                def open_studio(kind='bar'):
                    open_main(kind)
                    page.locator('[data-action="edit-chart"]').first.click()
                    page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000)
                    page.wait_for_timeout(160)

                open_main('bar')
                check('main editor canonical authority', lambda: page.locator('[data-renderer-authority="visembler-canonical-chart-v2"]').count() > 0)
                screenshot(page, f'{args.label}-embedded-main-editor-bar-1440.png')

                open_studio('bar')
                check('Chart Studio canonical authority', lambda: page.locator('[data-renderer-authority="visembler-canonical-chart-v2"]').count() > 0)
                check('vertical grouped bar screenshot', lambda: (page.locator('[data-cs-tab="visual"]').click(), page.locator('[data-path="visual.barMode"]').select_option('grouped'), screenshot(page, f'{args.label}-vertical-grouped-bars-1440.png'), True)[-1])
                check('vertical stacked bar screenshot', lambda: (page.locator('[data-path="visual.barMode"]').select_option('stacked'), screenshot(page, f'{args.label}-vertical-stacked-bars-1440.png'), True)[-1])
                check('vertical percent bar screenshot', lambda: (page.locator('[data-path="visual.barMode"]').select_option('percent'), screenshot(page, f'{args.label}-vertical-percent-bars-1440.png'), True)[-1])
                page.locator('#cs-chart-type').select_option('Horizontal Bar')
                check('horizontal grouped bar screenshot', lambda: (page.locator('[data-path="visual.barMode"]').select_option('grouped'), screenshot(page, f'{args.label}-horizontal-grouped-bars-1440.png'), True)[-1])
                check('horizontal stacked bar screenshot', lambda: (page.locator('[data-path="visual.barMode"]').select_option('stacked'), screenshot(page, f'{args.label}-horizontal-stacked-bars-1440.png'), True)[-1])
                check('horizontal percent bar screenshot', lambda: (page.locator('[data-path="visual.barMode"]').select_option('percent'), screenshot(page, f'{args.label}-horizontal-percent-bars-1440.png'), True)[-1])
                bar_layout = bounds(page)
                check('bar bounds at desktop', lambda: (bar_layout.get('svg') and bar_layout.get('plotUseful') and bar_layout.get('legendBoundsInside') and bar_layout.get('axisBoundsInside') and not bar_layout.get('overflow'), bar_layout))

                page.locator('#cs-chart-type').select_option('Line Chart')
                page.locator('[data-cs-tab="visual"]').click()
                page.locator('[data-path="legend.position"]').select_option('right')
                page.locator('[data-path="axes.y.title"]').fill('Secondary engineering units')
                page.locator('[data-path="axes.y.title"]').press('Tab')
                page.locator('#cs-reference-value').fill('4')
                page.locator('#cs-reference-label').fill('Target')
                page.locator('[data-action="add-reference"]').click()
                page.locator('#cs-band-low').fill('1')
                page.locator('#cs-band-high').fill('6')
                page.locator('[data-action="add-band"]').click()
                page.locator('#cs-annotation-text').fill('Observed shift')
                page.locator('[data-action="add-annotation"]').click()
                screenshot(page, f'{args.label}-annotations-secondary-axis-1440.png')
                check('annotations and references rendered', lambda: page.locator('[data-reference-id]').count() >= 2 and page.locator('[data-annotation-id]').count() >= 1)

                base_hash = model_hash(page)
                preview_button = page.locator('button[data-recommendation-preview]').first
                if preview_button.count():
                    check('recommendation preview is transient', lambda: (preview_button.click(), page.wait_for_timeout(80), model_hash(page) == base_hash and state(page).get('recommendationPreview') is not None)[-1])
                else:
                    holdout('recommendation preview is transient', 'base runtime has no product-owned preview control')
                page.locator('[data-action="preview-close"]').count()
                page.locator('[data-recommendation]').first.click()
                page.wait_for_timeout(80)
                check('recommendation apply changes model', lambda: model_hash(page) != base_hash)

                page.locator('[data-cs-tab="interaction"]').click()
                for key in ('tooltip', 'crosshair', 'zoom', 'pan', 'brush', 'rangeSelector', 'legendFilter'):
                    node = page.locator(f'[data-path="interaction.{key}"]')
                    if not node.is_checked():
                        node.click()
                check('transient controls enabled', lambda: all(state(page)['model']['interaction'][key] for key in ('tooltip', 'crosshair', 'zoom', 'pan', 'brush', 'rangeSelector', 'legendFilter')))
                transient_hash = model_hash(page)
                fit_before = state(page).get('previewWidth')
                fit_button = page.locator('[data-action="fit"]')
                if fit_button.count() and fit_before is not None:
                    fit_button.click()
                    page.wait_for_timeout(80)
                    fit_after = state(page)['previewWidth']
                    check('Fit changes live preview layout', lambda: fit_after != fit_before and page.locator('#cs-canvas svg').count() > 0)
                else:
                    holdout('Fit changes live preview layout', 'base runtime has no product-owned Fit control')
                plot = page.locator('#cs-canvas .cs-plot-area')
                plot_box = plot.bounding_box() if plot.count() else None
                if plot_box:
                    page.mouse.move(plot_box['x'] + plot_box['width'] / 2, plot_box['y'] + plot_box['height'] / 2)
                    page.mouse.wheel(0, -120)
                    page.wait_for_timeout(60)
                zoom_changed = state(page).get('view', {}).get('x') is not None or state(page).get('view', {}).get('y') is not None
                check('zoom changes live view only', lambda: zoom_changed and model_hash(page) == transient_hash)
                if plot_box:
                    zoom_view = state(page).get('view', {})
                    page.keyboard.down('Shift')
                    page.mouse.move(plot_box['x'] + plot_box['width'] / 2, plot_box['y'] + plot_box['height'] / 2)
                    page.mouse.down()
                    page.mouse.move(plot_box['x'] + plot_box['width'] / 2 + 32, plot_box['y'] + plot_box['height'] / 2 + 18)
                    page.mouse.up()
                    page.keyboard.up('Shift')
                    page.wait_for_timeout(60)
                    check('pan changes live view only', lambda: state(page).get('view') != zoom_view and model_hash(page) == transient_hash)
                first_point = page.locator('[data-chart-point]').first
                if first_point.count():
                    first_point.hover(); page.wait_for_timeout(40)
                    check('tooltip is observable', lambda: not page.locator('#cs-chart-tooltip').get_attribute('hidden'))
                    check('crosshair is observable', lambda: page.locator('[data-crosshair-layer]').get_attribute('visibility') == 'visible')
                range_button = page.locator('[data-range-value="recent"]')
                if range_button.count():
                    range_before = state(page).get('view', {}).copy()
                    range_button.click(); page.wait_for_timeout(60)
                    check('range selector changes live view only', lambda: state(page).get('view') != range_before and model_hash(page) == transient_hash)
                else:
                    holdout('range selector changes live view only', 'current chart has no numeric/time X range selector')
                if plot_box:
                    page.mouse.move(plot_box['x'] + 6, plot_box['y'] + 6)
                    page.mouse.down()
                    page.mouse.move(plot_box['x'] + plot_box['width'] - 6, plot_box['y'] + plot_box['height'] - 6)
                    page.mouse.up()
                    page.wait_for_timeout(60)
                    check('brush selects semantic rows and columns', lambda: bool(state(page).get('selectedRows')) and semantic_mark_selection(page))
                reset = page.locator('[data-action="reset-selection"]')
                reset.click()
                page.wait_for_timeout(60)
                check('reset restores deterministic view', lambda: state(page).get('view', {'x': None, 'y': None}) == {'x': None, 'y': None} and model_hash(page) == transient_hash)

                page.locator('[data-cs-tab="visual"]').click()
                first_legend = page.locator('[data-legend-series]').first
                first_point = page.locator('[data-chart-point]').first
                check('legend has keyboard button semantics', lambda: first_legend.get_attribute('role') == 'button' and first_legend.get_attribute('tabindex') == '0')
                if first_legend.count():
                    before_visible = state(page)['model']['series'][0]['visible']
                    first_legend.focus();page.keyboard.press('Enter');page.wait_for_timeout(80)
                    check('Enter activates legend filter', lambda: state(page)['model']['series'][0]['visible'] != before_visible)
                    first_legend = page.locator('[data-legend-series]').first
                    first_legend.focus();page.keyboard.press(' ');page.wait_for_timeout(80)
                    check('Space restores legend filter', lambda: state(page)['model']['series'][0]['visible'] == before_visible)
                if first_point.count():
                    first_point.focus();page.keyboard.press('Enter');page.wait_for_timeout(80)
                    check('Enter selects mark semantically', lambda: semantic_mark_selection(page))
                    first_point.focus();page.keyboard.press(' ');page.wait_for_timeout(80)
                    check('Space preserves mark selection', lambda: semantic_mark_selection(page))
                screenshot(page, f'{args.label}-chart-studio-keyboard-interaction-1440.png')

                page.locator('[data-cs-tab="data"]').click()
                cell = page.locator('[data-cell="0:1"]')
                cell.focus();cell.fill('99')
                check('cell draft preserves focus', lambda: page.evaluate('()=>document.activeElement?.getAttribute("data-cell")==="0:1"'))
                recipe_button = page.locator('[data-action="save-recipe"]')
                if recipe_button.count() and page.locator('#cs-name-dialog').count():
                    recipe_button.click()
                    page.locator('#cs-name-dialog').wait_for(state='visible')
                    page.locator('#cs-name-input').fill('R2 evidence recipe')
                    page.locator('#cs-name-confirm').click()
                    page.wait_for_timeout(80)
                    check('recipe naming dialog commits', lambda: (any(recipe.get('name') == 'R2 evidence recipe' for recipe in state(page).get('recipes', [])), {'recipe_names': [recipe.get('name') for recipe in state(page).get('recipes', [])]}))
                else:
                    holdout('recipe naming dialog commits', 'base runtime has no product-owned naming dialog')

                export_button = page.locator('[data-action="export-svg"]')
                if export_button.count():
                    export_hash = model_hash(page)
                    with page.expect_download() as download_info:
                        export_button.click()
                    download = download_info.value
                    svg_bytes = Path(download.path()).read_bytes()
                    check('SVG export canonical parity', lambda: model_hash(page) == export_hash and b'visembler-canonical-chart-v2' in svg_bytes and svg_bytes.count(b'data-chart-point') > 0)
                else:
                    holdout('SVG export canonical parity', 'base runtime has no product-owned SVG export control')

                for name, width, height, dpr in (('desktop-1440', 1440, 900, 1), ('narrow-1024', 1024, 900, 1), ('mobile-390', 390, 844, 1)):
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(120)
                    layout = bounds(page)
                    receipt['viewports'].append({'name': name, 'width': width, 'height': height, 'device_scale_factor': dpr, 'layout': layout})
                    check(f'layout bounds {name}', lambda layout=layout: layout.get('svg') and layout.get('plotUseful') and layout.get('legendBoundsInside') and layout.get('axisBoundsInside') and not layout.get('overflow'))
                    screenshot(page, f'{args.label}-dense-legend-{name}.png')

                coarse = browser.new_context(accept_downloads=True, viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                coarse_page = coarse.new_page();coarse_page.set_default_timeout(12000)
                coarse_page.goto(f'{host.url}/visualizer/chart-studio?report={quote(report_ids["time"])}&element=chart-r2', wait_until='domcontentloaded')
                coarse_page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000);coarse_page.wait_for_timeout(160)
                coarse_layout = coarse_page.evaluate('()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1})')
                receipt['viewports'].append({'name': 'reflow-200-percent', 'width': 390, 'height': 844, 'device_scale_factor': 2, 'layout': coarse_layout})
                check('layout reflow 200 percent', lambda: not coarse_layout['overflow'])
                screenshot(coarse_page, f'{args.label}-irregular-time-line-reflow-200-percent.png')
                coarse.close()

                page.set_viewport_size({'width': 1440, 'height': 900})
                page.wait_for_timeout(120)
                open_studio('time');screenshot(page, f'{args.label}-irregular-time-line-1440.png')
                open_studio('scatter');screenshot(page, f'{args.label}-mixed-sign-scatter-1440.png')
                receipt['errors'] = events.unexpected
                check('no unexpected browser errors', lambda: not receipt['errors'])
                context.close();browser.close()
    except Exception as exc:
        receipt['harness_error'] = str(exc)
        receipt['traceback'] = traceback.format_exc()
    receipt['pass'] = sum(row['status'] == 'PASS' for row in receipt['checks'])
    receipt['applicable'] = len(receipt['checks'])
    receipt['source']['candidate_root'] = str(root)
    (output / f'{args.label}-r2-browser-acceptance.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'pass': receipt['pass'], 'applicable': receipt['applicable'], 'screenshots': len(receipt['screenshots']), 'path': str(output / f'{args.label}-r2-browser-acceptance.json')}))
    return 0 if receipt['pass'] == receipt['applicable'] and not receipt.get('harness_error') and not receipt['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
