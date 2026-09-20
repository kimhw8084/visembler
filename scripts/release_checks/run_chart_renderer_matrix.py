#!/usr/bin/env python3
"""Capture native before/after evidence for the bounded chart renderer change.

The script intentionally uses the real NiceGUI product process and Chromium.
It creates only a temporary local report fixture and writes evidence beneath
the caller-provided artifact directory.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]


def dataset() -> dict:
    fields = [
        {'id': 'time', 'name': 'Observation time', 'type': 'date', 'semantic_tags': ['time']},
        {'id': 'measurement', 'name': 'Measurement', 'type': 'number', 'semantic_tags': ['value']},
        {'id': 'series', 'name': 'Run', 'type': 'categorical', 'semantic_tags': ['category']},
        {'id': 'category', 'name': 'Category', 'type': 'categorical', 'semantic_tags': ['category']},
    ]
    rows = []
    values = {
        'Run A': [12.0, 15.5, 11.0, 19.0],
        'Run B': [8.0, 13.0, 17.5, 21.0],
        'Run C': [5.0, 10.0, 16.0, 24.0],
    }
    dates = ['2026-01-01', '2026-01-02', '2026-01-05', '2026-01-12']
    for index, date in enumerate(dates):
        for name, series_values in values.items():
            rows.append([date, series_values[index], name, f'Category {index + 1} with a deliberately long label'])
    return {'id': 'chart-r1-data', 'name': 'R1 renderer evidence observations', 'revision': 1, 'fields': fields, 'rows': rows, 'warnings': [], 'metadata': {}}


def report_model(canonical_model):
    source = dataset()
    item = {
        'id': 'chart-r1', 'type': 'chart', 'engine': 'CoreChartEngine', 'element': 'Multi-Line',
        'title': 'Production chart renderer evidence', 'dataset_id': source['id'],
        'mapping': {'x': 'time', 'y': 'measurement', 'series': 'series'},
        'chart_studio': {
            'chart_type': 'Multi-Line', 'dataset_id': source['id'], 'dataset': source,
            'mapping': {'x': 'time', 'y': 'measurement', 'series': 'series'},
            'axes': {
                'x': {'title': 'Observation time', 'format': 'date', 'tickCount': 4},
                'y': {'title': 'Measurement units', 'tickCount': 6, 'zeroBaseline': False},
            },
            'legend': {'show': True, 'position': 'bottom', 'orientation': 'horizontal', 'order': 'input'},
            'visual': {'palette': 'colorblind', 'markers': True, 'missingPolicy': 'gap'},
            'interaction': {'tooltip': True, 'crosshair': True, 'zoom': True, 'pan': True, 'brush': True, 'rangeSelector': True, 'crossFilter': True, 'resetZoom': True},
            'series': [
                {'key': 'Run A', 'label': 'Run A · baseline', 'color': '#0072B2', 'lineDash': 'solid'},
                {'key': 'Run B', 'label': 'Run B · changed', 'color': '#E69F00', 'lineDash': 'dashed'},
                {'key': 'Run C', 'label': 'Run C · holdout', 'color': '#009E73', 'lineDash': 'dotted'},
            ],
        },
        'data': [[row[0], row[1]] for row in source['rows']],
        'weight': 2.4, 'order': 0, 'locked': False, 'z': 1,
    }
    return canonical_model({'items': [item], 'datasets': [source], 'groups': {}, 'mode': 'smart', 'layoutPreset': 'editorial', 'canvas': {'width': 1600, 'height': 900}, 'nextId': 2})


def capture(page, path: Path, selector: str | None = None) -> dict:
    target = page.locator(selector) if selector else page
    target.screenshot(path=str(path), animations='disabled')
    box = target.bounding_box() if selector else page.evaluate('()=>({x:0,y:0,width:innerWidth,height:innerHeight})')
    return {'path': path.name, 'selector': selector, 'box': box}


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

    receipt = {'label': args.label, 'root': str(root), 'viewports': [], 'screenshots': [], 'interactions': {}, 'errors': []}
    with tempfile.TemporaryDirectory(prefix=f'visembler-chart-matrix-{args.label}-') as td:
        with NativeHost(root, Path(td) / 'data') as host, sync_playwright() as playwright:
            report_id = host.create(model=report_model(canonical_model), name=f'chart-renderer-{args.label}')
            browser = playwright.chromium.launch(**browser_kwargs())
            context = browser.new_context(accept_downloads=True, viewport={'width': 1440, 'height': 900})
            page = context.new_page()
            page.set_default_timeout(12000)
            events = BrowserEvents()
            events.attach(page)

            page.goto(f'{host.url}/visualizer?report={quote(report_id)}', wait_until='domcontentloaded')
            ready(page, require_settled=True)
            page.locator('.cui-visualizer-root').first.wait_for(timeout=20000)
            page.wait_for_timeout(250)
            receipt['interactions']['main_editor_authority'] = page.locator('[data-renderer-authority="visembler-canonical-chart-v2"]').count() > 0
            receipt['screenshots'].append(capture(page, output / f'{args.label}-main-editor-1440-light.png'))

            page.locator('#previewBtn').click()
            page.locator('#previewExit').wait_for(state='visible')
            page.wait_for_timeout(150)
            receipt['interactions']['reading_preview'] = True
            receipt['screenshots'].append(capture(page, output / f'{args.label}-reading-preview-1440-light.png'))
            page.locator('#previewExit').click()
            page.wait_for_timeout(120)

            page.locator('[data-action="edit-chart"]').first.click()
            page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000)
            page.wait_for_timeout(200)
            receipt['interactions']['chart_studio_authoring'] = page.locator('#cs-chart-svg').count() > 0 or page.locator('#cs-canvas svg').count() > 0
            receipt['chart_geometry'] = page.evaluate('''()=>{
                const svg=document.querySelector('#cs-canvas svg');
                if(!svg)return {svg:false};
                const canvas=document.querySelector('#cs-canvas').getBoundingClientRect();
                const marks=[...svg.querySelectorAll('[data-chart-point],[data-wafer-die]')].map(node=>node.getBoundingClientRect());
                const legends=[...svg.querySelectorAll('.cs-legend-item')].map(node=>node.getBoundingClientRect());
                const inside=box=>box.left>=canvas.left-1&&box.top>=canvas.top-1&&box.right<=canvas.right+1&&box.bottom<=canvas.bottom+1;
                return {svg:true,marks:marks.length,accessible_marks:[...svg.querySelectorAll('[data-chart-point],[data-wafer-die]')].filter(node=>node.getAttribute('aria-label')).length,mark_bounds_inside:marks.every(inside),legend_bounds_inside:legends.every(inside),viewBox:svg.getAttribute('viewBox'),svg_overflow:svg.scrollWidth>svg.clientWidth+1||svg.scrollHeight>svg.clientHeight+1};
            }''')
            receipt['chart_geometry']['bounds_pass'] = bool(receipt['chart_geometry'].get('svg') and receipt['chart_geometry'].get('mark_bounds_inside') and receipt['chart_geometry'].get('legend_bounds_inside') and not receipt['chart_geometry'].get('svg_overflow'))
            receipt['screenshots'].append(capture(page, output / f'{args.label}-chart-studio-1440-light.png'))

            point = page.locator('#cs-canvas [data-chart-point]').first
            if point.count():
                point.focus()
                page.wait_for_timeout(120)
                receipt['interactions']['keyboard_focus'] = page.evaluate('()=>!!document.activeElement?.matches("[data-chart-point]")')
                page.evaluate('()=>document.querySelector("#cs-canvas [data-chart-point]")?.dispatchEvent(new PointerEvent("pointermove", {bubbles:true, clientX:120, clientY:120}))')
                receipt['interactions']['tooltip'] = page.evaluate('()=>{const node=document.querySelector("#cs-chart-tooltip");return !!node&&!node.hidden&&!!node.textContent}')
                receipt['screenshots'].append(capture(page, output / f'{args.label}-chart-studio-hover-focus-1440.png'))

            theme_button = page.locator('[data-action="toggle-theme"]')
            if theme_button.count():
                theme_button.click()
                page.wait_for_timeout(120)
                receipt['interactions']['dark_theme'] = page.evaluate('()=>document.documentElement.getAttribute("data-theme")==="dark"')
                receipt['screenshots'].append(capture(page, output / f'{args.label}-chart-studio-1440-dark.png'))

            recommendation = page.locator('[data-action="recommendation-preview"]').first
            if recommendation.count():
                recommendation.click()
                page.wait_for_timeout(120)
                receipt['interactions']['recommendation_preview'] = 'Recommendation preview' in page.locator('#cs-status').inner_text()
                receipt['screenshots'].append(capture(page, output / f'{args.label}-recommendation-preview-1440.png'))

            page.locator('[data-cs-tab="interaction"]').click()
            range_button = page.locator('[data-range-value="recent"]')
            if range_button.count():
                before_view = page.evaluate('()=>JSON.stringify(window.CompanyUIChartStudio.state.view)')
                range_button.click()
                page.wait_for_timeout(80)
                receipt['interactions']['range_selector'] = page.evaluate('(before)=>before!==JSON.stringify(window.CompanyUIChartStudio.state.view)', before_view)
            plot = page.locator('#cs-canvas .cs-plot-area')
            if plot.count() and page.evaluate('()=>window.CompanyUIChartStudio.state.model.interaction.zoom'):
                box = plot.bounding_box()
                if box:
                    before_zoom = page.evaluate('()=>JSON.stringify(window.CompanyUIChartStudio.state.view)')
                    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.mouse.wheel(0, -120)
                    page.wait_for_timeout(80)
                    receipt['interactions']['zoom'] = page.evaluate('(before)=>before!==JSON.stringify(window.CompanyUIChartStudio.state.view)', before_zoom)
            if plot.count() and page.evaluate('()=>window.CompanyUIChartStudio.state.model.interaction.pan'):
                box = plot.bounding_box()
                if box:
                    before_pan = page.evaluate('()=>JSON.stringify(window.CompanyUIChartStudio.state.view)')
                    page.keyboard.down('Shift')
                    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.mouse.down()
                    page.mouse.move(box['x'] + box['width'] / 2 + 40, box['y'] + box['height'] / 2 + 10)
                    page.mouse.up()
                    page.keyboard.up('Shift')
                    page.wait_for_timeout(80)
                    receipt['interactions']['pan'] = page.evaluate('(before)=>before!==JSON.stringify(window.CompanyUIChartStudio.state.view)', before_pan)
            if plot.count() and page.evaluate('()=>window.CompanyUIChartStudio.state.model.interaction.brush'):
                box = plot.bounding_box()
                if box:
                    page.mouse.move(box['x'] + 10, box['y'] + 10)
                    page.mouse.down()
                    page.mouse.move(box['x'] + box['width'] - 10, box['y'] + box['height'] - 10)
                    page.mouse.up()
                    page.wait_for_timeout(80)
                    receipt['interactions']['brush'] = page.evaluate('()=>window.CompanyUIChartStudio.state.selectedRows.length>0')
            reset_button = page.locator('[data-action="reset-selection"]')
            if reset_button.count():
                reset_button.click()
                page.wait_for_timeout(80)
                receipt['interactions']['reset_zoom'] = page.evaluate('()=>{const state=window.CompanyUIChartStudio.state,view=state.view||{};return (view.x??null)===null&&(view.y??null)===null&&state.selectedRows.length===0}')
            receipt['screenshots'].append(capture(page, output / f'{args.label}-chart-studio-interactions-1440.png'))

            for name, width, height, dpr in (
                ('narrow-1024', 1024, 900, 1),
                ('mobile-390', 390, 844, 1),
            ):
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_timeout(140)
                overflow = page.evaluate('()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1})')
                receipt['viewports'].append({'name': name, 'width': width, 'height': height, 'device_scale_factor': dpr, 'overflow': overflow})
                receipt['screenshots'].append(capture(page, output / f'{args.label}-chart-studio-{name}.png'))

            # The supported coarse-pointer contract models a 200%-equivalent
            # path with a 390 CSS-pixel viewport and DPR 2.
            coarse_context = browser.new_context(accept_downloads=True, viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            coarse_page = coarse_context.new_page()
            coarse_page.set_default_timeout(12000)
            coarse_events = BrowserEvents()
            coarse_events.attach(coarse_page)
            coarse_page.goto(f'{host.url}/visualizer/chart-studio?report={quote(report_id)}&element=chart-r1', wait_until='domcontentloaded')
            coarse_page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000)
            coarse_page.wait_for_timeout(160)
            coarse_overflow = coarse_page.evaluate('()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1})')
            receipt['viewports'].append({'name': 'reflow-200-percent', 'width': 390, 'height': 844, 'device_scale_factor': 2, 'overflow': coarse_overflow})
            receipt['screenshots'].append(capture(coarse_page, output / f'{args.label}-chart-studio-reflow-200-percent.png'))
            receipt['errors'].extend(coarse_events.unexpected)
            coarse_context.close()

            try:
                forced_context = browser.new_context(accept_downloads=True, viewport={'width': 1440, 'height': 900}, forced_colors='active')
                forced_page = forced_context.new_page()
                forced_page.set_default_timeout(12000)
                forced_events = BrowserEvents()
                forced_events.attach(forced_page)
                forced_page.goto(f'{host.url}/visualizer/chart-studio?report={quote(report_id)}&element=chart-r1', wait_until='domcontentloaded')
                forced_page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000)
                forced_page.wait_for_timeout(120)
                receipt['interactions']['forced_colors'] = forced_page.evaluate('()=>matchMedia("(forced-colors: active)").matches')
                receipt['screenshots'].append(capture(forced_page, output / f'{args.label}-chart-studio-forced-colors-1440.png'))
                receipt['errors'].extend(forced_events.unexpected)
                forced_context.close()
            except Exception as exc:
                receipt['interactions']['forced_colors'] = False
                receipt['forced_colors_note'] = f'Browser did not expose forced-colors context: {exc}'

            # Exercise the product-owned naming dialog and export surface.
            page.set_viewport_size({'width': 1440, 'height': 900})
            name_button = page.locator('[data-action="save-recipe"]')
            if name_button.count() and page.locator('#cs-name-dialog').count():
                name_button.click()
                dialog = page.locator('#cs-name-dialog')
                dialog.wait_for(state='visible')
                dialog.locator('#cs-name-input').fill(f'{args.label} evidence recipe')
                dialog.locator('button[value="cancel"]').click()
                receipt['interactions']['recipe_naming_dialog'] = True
            export_button = page.locator('[data-action="export-svg"]')
            if export_button.count():
                receipt['interactions']['svg_export_control'] = True

            receipt['errors'] = events.unexpected
            context.close()
            browser.close()
    (output / f'{args.label}-browser-matrix.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if not receipt['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

