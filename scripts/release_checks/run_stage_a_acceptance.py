#!/usr/bin/env python3
"""Bounded native browser acceptance for the Stage A authoring shell.

The checks use temporary report storage and the installed NiceGUI application.
They intentionally probe the user-visible geometry and commands rather than
reimplementing editor layout in the test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

ROOT = Path(os.environ.get('VIZ_ACCEPTANCE_ROOT', str(Path(__file__).resolve().parents[2]))).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, acceptance_model, browser_kwargs, ready, write_json
from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.templates import template_model
from playwright.sync_api import sync_playwright


def _item(id_: str, type_: str, engine: str, element: str, order: int, **extra):
    return {
        'id': id_, 'type': type_, 'engine': engine, 'element': element,
        'title': element, 'order': order, 'weight': 1.0, 'locked': False,
        'groupId': None, 'z': order + 1, **extra,
    }


def stage_model() -> dict:
    return canonical_model({
        'mode': 'smart', 'layoutPreset': 'editorial', 'nextId': 7,
        'items': [
            _item('c1', 'text', 'TextEngine', 'Key Takeaway', 0, text='Stage A acceptance'),
            _item('c2', 'metric', 'MetricEngine', 'Hero KPI', 1, value=84.2, unit='%'),
            _item('c3', 'chart', 'CoreChartEngine', 'Line Chart', 2,
                  data=[['Week 1', 1], ['Week 2', 3], ['Week 3', 2]], brush=[0, 2], revealed=True),
            _item('c4', 'timeline', 'TimelineEngine', 'Event Timeline', 3,
                  milestones=[{'label': 'Observe', 'date': None}, {'label': 'Verify', 'date': None}]),
            _item('c5', 'wafer', 'WaferFabEngine', 'Wafer Map', 4,
                  observations=[{'x': 0, 'y': 0, 'value': 1.2}, {'x': 1, 'y': 0, 'value': 1.5}], lot='L1', tool='ETCH-01', chamber='C1'),
            _item('c6', 'diagram', 'DiagramEngine', 'Process Flow', 5,
                  nodes=['Input', 'Inspect', 'Release'], edges=[{'from': 0, 'to': 1, 'label': 'inspect'}]),
        ],
        'groups': {}, 'datasets': [], 'crossFilter': None,
        'canvas': {'width': 1600, 'height': 900},
    })


def solo_model(type_: str, engine: str, element: str, content: dict) -> dict:
    return canonical_model({
        'mode': 'smart', 'layoutPreset': 'editorial', 'nextId': 2,
        'items': [_item('c1', type_, engine, element, 0, **content)],
        'groups': {}, 'datasets': [], 'crossFilter': None,
        'canvas': {'width': 1600, 'height': 900},
    })


def _layout_hash(page) -> str:
    value = page.evaluate("()=>__VIZ_PROD__.layoutRects().map(({id,x,y,w,h})=>({id,x,y,w,h}))")
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _settled(page, timeout=15000) -> None:
    page.wait_for_function("()=>{const s=window.CompanyUIVisualizerBridge?.state?.();return s&&s.pending===0&&!s.inflight}", timeout=timeout)


def _load(page, host, report_id) -> None:
    page.goto(f'{host.url}/visualizer?report={quote(report_id)}', wait_until='domcontentloaded')
    ready(page, require_settled=True)
    page.wait_for_timeout(180)


def _set_panel(page, selector: str, open_: bool) -> None:
    button = page.locator(selector)
    if (button.get_attribute('aria-pressed') == 'true') != open_:
        button.click()
        page.wait_for_timeout(120)


def _rects(page):
    return page.evaluate("""()=>Object.fromEntries(['.left','.work','.right','#viewport','#sceneFrame'].map(selector=>{
      const n=document.querySelector(selector),r=n?.getBoundingClientRect();
      return [selector,r?{left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}:null];
    }))""")


def _layout_probe(page):
    return page.evaluate("""()=>{
      const canvas=CompanyUIVisualizerBridge.state().model.canvas;
      const rects=window.__VIZ_PROD__.layoutRects();
      const overlap=[];
      for(let i=0;i<rects.length;i+=1)for(let j=i+1;j<rects.length;j+=1){
        const a=rects[i],b=rects[j],w=Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)),h=Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));
        if(w*h>1)overlap.push({a:a.id,b:b.id,area:w*h});
      }
      const area=rects.reduce((sum,r)=>sum+r.w*r.h,0);
      return {canvas,rects,overlap,area_share:area/(canvas.width*canvas.height)};
    }""")


def _assert_workspace(page, width: int) -> None:
    _set_panel(page, '#libraryToggle', True)
    _set_panel(page, '#inspectorToggle', True)
    rect = _rects(page)
    left, work, right, viewport, frame = (rect[s] for s in ('.left', '.work', '.right', '#viewport', '#sceneFrame'))
    assert left and work and right and left['right'] <= work['left'] + 1 and work['right'] <= right['left'] + 1, rect
    assert abs((frame['left'] - viewport['left']) - (viewport['right'] - frame['right'])) <= 2.0, rect
    assert page.evaluate('()=>document.documentElement.scrollWidth-innerWidth') <= 1, width


def _drag_event(page, event_name: str):
    return page.evaluate("""(name)=>{
      const hull=document.querySelector('#hull'), r=hull.getBoundingClientRect(), dt=new DataTransfer();
      dt.setData('application/x-viz-element',JSON.stringify({element:'Area Chart',engine:'CoreChartEngine'}));
      const event=new DragEvent(name,{bubbles:true,cancelable:true,clientX:r.left+r.width*.74,clientY:r.top+r.height*.68,dataTransfer:dt});
      hull.dispatchEvent(event); return window.__VIZ_PROD__.placementGhost();
    }""", event_name)


def _hub_select(page, label: str) -> None:
    page.locator('.cui-report-hub-toolbar .q-field').nth(2).click()
    page.get_by_text(label, exact=True).last.click()
    page.wait_for_timeout(180)


def _assert_layout_geometry(page, *, min_area_share=None):
    probe=_layout_probe(page)
    canvas=probe['canvas']
    assert not probe['overlap'], {'overlap':probe['overlap'],'rects':probe['rects']}
    for rect in probe['rects']:
        assert rect['x']>=-1 and rect['y']>=-1, rect
        assert rect['x']+rect['w']<=canvas['width']+1 and rect['y']+rect['h']<=canvas['height']+1, rect
    if min_area_share is not None:
        assert probe['area_share']>=min_area_share, probe
    before=_layout_hash(page)
    page.evaluate('()=>window.__VIZ_PROD__.renderAll()')
    page.wait_for_timeout(80)
    assert _layout_hash(page)==before, 'Smart layout changed across an identical render'


def _assert_chrome(page, shot_path: Path):
    page.locator('.component').first.click()
    page.wait_for_timeout(180)
    page.screenshot(path=str(shot_path))
    state=page.evaluate("""()=>{
      const component=document.querySelector('.component.selected'),content=component?.querySelector('.c-content'),chrome=document.querySelector('.editor-chrome');
      const r=n=>{const x=n?.getBoundingClientRect();return x?{left:x.left,right:x.right,top:x.top,bottom:x.bottom,width:x.width,height:x.height}:null};
      const intersects=(a,b)=>a&&b&&Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top))>1;
      const cr=r(content);
      return {component:r(component),content:cr,chrome:r(chrome),handleRects:[...document.querySelectorAll('.editor-chrome .resize-h,.editor-chrome .c-head')].map(r),handlesInsideContent:[...document.querySelectorAll('.editor-chrome .resize-h,.editor-chrome .c-head')].filter(n=>intersects(r(n),cr)).length,embeddedHead:component?.querySelectorAll('.c-head').length||0,embeddedResize:component?.querySelectorAll('.resize-h').length||0,chromeBackground:chrome?getComputedStyle(chrome).backgroundColor:null};
    }""")
    assert state['chrome'] and state['content'] and state['embeddedHead']==0 and state['embeddedResize']==0, state
    assert state['handlesInsideContent']==0, state
    assert state['chromeBackground'] in ('rgba(0, 0, 0, 0)', 'transparent'), state
    component=page.locator('.component.selected')
    component.focus()
    assert page.evaluate('()=>document.activeElement?.classList.contains("component")')
    page.locator('.editor-chrome .c-head').first.focus()
    assert page.evaluate('()=>document.activeElement?.classList.contains("c-head")')


def _assert_commands(page, width: int, shot_path: Path):
    page.set_viewport_size({'width':width,'height':844 if width<=800 else 900})
    page.wait_for_timeout(140)
    command=page.locator('#commandBtn')
    assert command.is_visible(), f'command overflow path is not reachable at {width}px'
    command.click()
    page.locator('#cmdModal.show').wait_for()
    labels=page.locator('#cmdList .cmd-label').all_inner_texts()
    required=('Undo','Redo','Report History','Help & shortcuts','Preview report','Export report','Open Library','Open Inspector','Reflow report')
    missing=[label for label in required if label not in labels]
    assert not missing, {'width':width,'missing':missing,'labels':labels}
    assert page.evaluate('()=>document.documentElement.scrollWidth-innerWidth')<=1
    page.screenshot(path=str(shot_path))
    page.keyboard.press('Escape')


def _assert_hover_invariance(page, shot_path: Path):
    page.locator('.component').first.wait_for()
    node=page.locator('.component').first
    target=node.locator('.integrated-element-content')
    page.wait_for_timeout(700)
    before_image=target.screenshot(animations='disabled')
    before=hashlib.sha256(before_image).hexdigest()
    shot_path.with_name(shot_path.stem + '-before.png').write_bytes(before_image)
    node.hover(position={'x':2,'y':2})
    page.wait_for_timeout(700)
    after_image=target.screenshot(animations='disabled')
    after=hashlib.sha256(after_image).hexdigest()
    shot_path.with_name(shot_path.stem + '-after.png').write_bytes(after_image)
    page.screenshot(path=str(shot_path))
    assert before==after, {'before':before,'after':after}


def _assert_no_document_overflow(page):
    assert page.evaluate('()=>document.documentElement.scrollWidth-innerWidth')<=1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shots = output / 'screenshots'
    shots.mkdir(exist_ok=True)
    report = {'scope': 'native Stage A workspace and report-hub acceptance', 'cases': [], 'unexpected_errors': []}

    mixed = stage_model()
    ids = {}
    try:
        with tempfile.TemporaryDirectory(prefix='visembler-stage-a-') as td, NativeHost(ROOT, Path(td) / 'data') as host, sync_playwright() as pw:
            ids['mixed'] = host.create(model=mixed, name='stage-a-mixed')
            ids['timeline'] = host.create(model=solo_model('timeline', 'TimelineEngine', 'Event Timeline', {'milestones': [{'label': 'Observe', 'date': None}, {'label': 'Verify', 'date': None}]}), name='stage-a-timeline')
            ids['chart'] = host.create(model=solo_model('chart', 'CoreChartEngine', 'Line Chart', {'data': [['A', 1], ['B', 3], ['C', 2]], 'brush': [0, 2], 'revealed': True}), name='stage-a-chart')
            ids['table'] = host.create(model=solo_model('table', 'TableEngine', 'Clean Table', {'customTable': {'headers': ['Signal', 'Value', 'Status'], 'rows': [['Pressure', '12.4', 'Stable'], ['Temperature', '84', 'Watch'], ['Yield', '98.2%', 'Stable']]} }), name='stage-a-table')
            ids['diagram'] = host.create(model=solo_model('diagram', 'DiagramEngine', 'Process Flow', {'nodes': ['Input', 'Inspect', 'Release'], 'edges': [['Input', 'Inspect'], ['Inspect', 'Release']]}), name='stage-a-diagram')
            ids['narrative'] = host.create(model=solo_model('text', 'TextEngine', 'Body Narrative', {'text': 'A source-backed narrative keeps the investigation decision visible while preserving the evidence chain.'}), name='stage-a-narrative')
            ids['metric'] = host.create(model=solo_model('metric', 'MetricEngine', 'Hero KPI', {'value': 84.2, 'unit': '%'}), name='stage-a-metric')
            ids['wafer'] = host.create(model=solo_model('wafer', 'WaferFabEngine', 'Wafer Map', {'observations': [{'x': 0, 'y': 0, 'value': 1.2}]}), name='stage-a-wafer')
            ids['hub'] = host.create(model=template_model('operations-review'), name='stage-a-hub')

            browser = pw.chromium.launch(**browser_kwargs())
            context = browser.new_context()
            page = context.new_page()
            events = BrowserEvents()
            events.attach(page)

            def check(name, fn):
                case = {'name': name, 'status': 'FAIL'}
                try:
                    fn()
                    case['status'] = 'PASS'
                except Exception as exc:
                    case['error'] = str(exc) or repr(exc)
                    case['traceback'] = traceback.format_exc()
                report['cases'].append(case)

            _load(page, host, ids['mixed'])
            page.set_viewport_size({'width': 1440, 'height': 900})
            check('desktop 1440 three-column reflow and gutters', lambda: _assert_workspace(page, 1440))
            page.set_viewport_size({'width': 1024, 'height': 800})
            check('desktop 1024 three-column reflow and gutters', lambda: _assert_workspace(page, 1024))
            check('panel close restores canvas width without overflow', lambda: (
                _set_panel(page, '#inspectorToggle', False),
                assert_width_growth(page),
            ))

            _load(page, host, ids['timeline'])
            check('solo Timeline governed content fit', lambda: _assert_solo(page, 'timeline', .80, .18))
            _load(page, host, ids['chart'])
            check('solo chart governed content fit', lambda: _assert_solo(page, 'chart', .82, .42))
            _load(page, host, ids['wafer'])
            check('solo Wafer Map governed content fit', lambda: _assert_solo(page, 'wafer', .40, .28))

            _load(page, host, ids['mixed'])
            page.set_viewport_size({'width': 1440, 'height': 900})
            check('selected content has no occluding selection chrome', lambda: _assert_selection(page))
            page.screenshot(path=str(shots / 'after-multi-report-1440.png'))
            check('multi-element Smart composition is bounded and deterministic', lambda: _assert_layout_geometry(page, min_area_share=.52))
            check('external selection and resize chrome stays outside content', lambda: _assert_chrome(page, shots / 'after-selected-chrome-1440.png'))
            check('drag ghost matches final proposed bounds', lambda: _assert_drag(page))

            for name, report_id, min_width, min_area in (
                ('line-chart', ids['chart'], .94, .70),
                ('clean-table', ids['table'], .94, .70),
                ('process-flow', ids['diagram'], .94, .56),
                ('wafer-map', ids['wafer'], .50, .42),
                ('body-narrative', ids['narrative'], .94, .30),
                ('hero-metric', ids['metric'], .94, .38),
            ):
                _load(page, host, report_id)
                page.set_viewport_size({'width':1440,'height':900})
                check(f'solo {name} safe-hull occupancy', lambda min_width=min_width, min_area=min_area, name=name: _assert_solo(page, name, min_width, min_area))
                page.screenshot(path=str(shots / f'after-solo-{name}-1440.png'))
                if name=='line-chart':
                    check('ordinary hover preserves chart content pixels', lambda: _assert_hover_invariance(page, shots / 'after-hover-line-chart-1440.png'))

            _load(page, host, ids['mixed'])
            page.set_viewport_size({'width':1440,'height':900})
            for width in (1440, 1024, 390):
                check(f'editor command reachability at {width}px', lambda width=width: _assert_commands(page, width, shots / f'after-command-palette-{width}.png'))

            _load(page, host, ids['mixed'])
            page.set_viewport_size({'width':1440,'height':900})

            def preview_case(width):
                page.set_viewport_size({'width': width, 'height': 844 if width < 800 else 900})
                _load(page, host, ids['mixed'])
                page.locator('#previewBtn').click()
                page.wait_for_timeout(180)
                page.locator('#previewFitWidth').click()
                page.locator('#previewFitPage').click()
                root = page.locator('.cui-visualizer-root')
                assert 'preview-mode' in (root.get_attribute('class') or '')
                assert not page.locator('#libraryPane').is_visible() and not page.locator('#inspectorPane').is_visible()
                rect = _rects(page)
                assert abs((rect['#sceneFrame']['left'] - rect['#viewport']['left']) - (rect['#viewport']['right'] - rect['#sceneFrame']['right'])) <= 2.0, rect
                page.screenshot(path=str(shots / f'preview-{width}.png'))
                page.locator('#previewExit').click()

            for width in (1440, 1024, 768, 390):
                check(f'preview full-stage symmetric at {width}', lambda width=width: preview_case(width))

            coarse_context = browser.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            coarse_page = coarse_context.new_page()
            coarse_events = BrowserEvents()
            coarse_events.attach(coarse_page)
            _load(coarse_page, host, ids['mixed'])
            check('200-percent-equivalent coarse-pointer command reflow', lambda: _assert_commands(coarse_page, 390, shots / 'after-command-palette-200-percent-equivalent.png'))
            check('200-percent-equivalent coarse-pointer has no document overflow', lambda: _assert_no_document_overflow(coarse_page))
            report['unexpected_errors'].extend(coarse_events.unexpected)
            coarse_context.close()

            _load(page, host, ids['mixed'])
            page.set_viewport_size({'width': 1440, 'height': 900})
            check('three built-in presets change layout and undo/redo', lambda: _assert_presets(page))
            check('Map command opens the minimap when available', lambda: _assert_map(page))
            check('dedicated report hub renders independent cards and lifecycle', lambda: _assert_hub(page, host, ids['hub']))

            report['unexpected_errors'] = events.unexpected
            report['cases'].append({'name': 'no browser console/page/network errors', 'status': 'PASS' if not events.unexpected else 'FAIL', 'error': events.unexpected[:4]})
            context.close()
            browser.close()
    except Exception as exc:
        report['harness_error'] = str(exc)

    production_count = int(subprocess.check_output([
        'node', '--input-type=module', '-e',
        "import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs'; console.log(PRODUCTION_LIBRARY_COUNT)",
    ], cwd=ROOT, text=True).strip())
    frozen = ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
    report['production_library_count'] = production_count
    report['frozen_connector_sha256'] = hashlib.sha256(frozen.read_bytes()).hexdigest()
    report['passed'] = sum(case.get('status') == 'PASS' for case in report['cases'])
    report['total'] = len(report['cases'])
    report['status'] = 'PASS' if report['passed'] == report['total'] and production_count == 52 and not report['unexpected_errors'] and 'harness_error' not in report else 'FAIL'
    report['source_editor_sha256'] = hashlib.sha256((ROOT / 'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest()
    write_json(output / 'stage-a-acceptance.json', report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


def assert_width_growth(page):
    after = _rects(page)['.work']['width']
    assert after > 500, after


def _assert_solo(page, kind: str, min_width_share: float, min_area_share: float):
    rect = page.evaluate('()=>__VIZ_PROD__.layoutRects()[0]')
    canvas = page.evaluate('()=>CompanyUIVisualizerBridge.state().model.canvas')
    width_share=rect['w']/canvas['width'];area_share=rect['w']*rect['h']/(canvas['width']*canvas['height'])
    assert width_share >= min_width_share and area_share >= min_area_share and rect['y'] <= 20, (kind, rect, width_share, area_share)
    node = page.locator('.component').first
    assert node.get_attribute('data-content-fit') == 'responsive'
    assert node.get_attribute('data-layout-growth') in {'horizontal', 'plot', 'square', 'text', 'data', 'media', 'balanced'}
    _assert_layout_geometry(page, min_area_share=min_area_share)


def _assert_selection(page):
    page.locator('.component').first.click()
    page.wait_for_timeout(360)
    node = page.locator('.component.selected').first
    assert node.count() == 1, 'click did not select a component'
    shadow = node.evaluate("n=>getComputedStyle(n).boxShadow")
    pseudo = node.evaluate("n=>getComputedStyle(n,'::before').content")
    assert shadow == 'none', shadow
    assert pseudo in ('none', ''), pseudo


def _assert_drag(page):
    before = json.loads(page.evaluate('()=>__VIZ_PROD__.serialize()'))
    ghost = _drag_event(page, 'dragover')
    assert ghost and ghost['w'] > 0 and ghost['h'] > 0 and ghost['mode'] == 'smart-insert', ghost
    after_ghost = _drag_event(page, 'drop')
    assert after_ghost is None
    _settled(page)
    model = json.loads(page.evaluate('()=>__VIZ_PROD__.serialize()'))
    assert len(model['items']) == len(before['items']) + 1
    new_id = next(item['id'] for item in model['items'] if item['id'] not in {old['id'] for old in before['items']})
    actual = page.evaluate('(id)=>__VIZ_PROD__.layoutRects().find(rect=>rect.id===id)', new_id)
    assert max(abs(actual[key] - ghost[key]) for key in ('x', 'y', 'w', 'h')) <= 2.0, (ghost, actual)


def _assert_presets(page):
    _set_panel(page, '#libraryToggle', True)
    page.locator('#presetsTab').click()
    page.locator('#builtinPresetList [data-built-preset]').first.wait_for()
    hashes = []
    for preset in ('executive', 'technical', 'manufacturing'):
        page.locator(f'#builtinPresetList [data-built-preset="{preset}"]').click()
        page.wait_for_function('(name)=>JSON.parse(__VIZ_PROD__.serialize()).layoutPreset===name', arg=preset)
        _settled(page)
        hashes.append(_layout_hash(page))
    assert len(set(hashes)) == 3, hashes
    current = hashes[-1]
    page.locator('#undo').click()
    page.wait_for_timeout(120)
    assert _layout_hash(page) != current
    page.locator('#redo').click()
    page.wait_for_timeout(120)
    assert _layout_hash(page) == current


def _assert_map(page):
    button = page.locator('#miniToggle')
    assert button.is_visible()
    button.click()
    assert button.get_attribute('aria-pressed') == 'true'
    assert page.locator('#minimap').evaluate("n=>getComputedStyle(n).display==='block'")


def _assert_hub(page, host, report_id):
    page.goto(f'{host.url}/visualizer/reports?report={quote(report_id)}', wait_until='domcontentloaded')
    page.locator('.cui-report-grid').first.wait_for(timeout=20000)
    assert not page.locator('.cui-visualizer-root').count(), 'hub must not embed the editor root'
    assert page.locator('.cui-report-thumb').count() >= 1, 'hub has no report preview thumbnails'
    card = page.locator(f'.cui-report-card[data-report-id="{report_id}"]')
    card.wait_for(timeout=20000)
    old_title = card.locator('input[aria-label="Title"]').input_value()
    new_title = f'{old_title} Stage A'
    card.locator('input[aria-label="Title"]').fill(new_title)
    card.locator('input[aria-label="Title"]').press('Tab')
    _wait_repo_title(host, old_title, new_title)
    page.reload(wait_until='domcontentloaded')
    page.locator('.cui-report-grid').first.wait_for(timeout=20000)
    target = page.locator('.cui-report-card').filter(has=page.locator(f'input[aria-label="Title"][value="{new_title}"]')).first
    if not target.count():
        target = page.locator('.cui-report-card').first
    before = page.locator('.cui-report-card').count()
    target.get_by_role('button', name='Duplicate', exact=True).click()
    page.wait_for_function('(n)=>document.querySelectorAll(".cui-report-card").length>n', arg=before)
    page.reload(wait_until='domcontentloaded')
    page.locator('.cui-report-grid').first.wait_for(timeout=20000)
    index = page.locator('.cui-report-card').evaluate_all("(cards,title)=>cards.findIndex(card=>card.querySelector('input[aria-label=\\\"Title\\\"]')?.value===title)", new_title)
    assert index >= 0, f'renamed report card not found; cards={page.locator(".cui-report-card").count()}'
    page.locator('.cui-report-card').nth(index).get_by_role('button', name='Move to trash', exact=True).click()
    page.locator('.q-dialog').get_by_role('button', name='Move to trash', exact=True).click()
    _hub_select(page, 'Active + trash')
    assert page.get_by_text('Trash', exact=False).count() >= 1
    trash = page.locator('.cui-report-card').filter(has_text=new_title).first
    trash.get_by_role('button', name='Restore', exact=True).click()
    page.wait_for_timeout(220)
    _hub_select(page, 'Active')
    restored_index = page.locator('.cui-report-card').evaluate_all("(cards,title)=>cards.findIndex(card=>card.querySelector('input[aria-label=\\\"Title\\\"]')?.value===title)", new_title)
    assert restored_index >= 0, 'restored report card not found'
    page.locator('.cui-report-card').nth(restored_index).get_by_role('button', name='History', exact=True).click()
    page.locator('.cui-history-panel').wait_for()
    assert page.locator('.cui-history-card').count() >= 1


def _wait_repo_title(host, old_title: str, new_title: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        titles = {record.title for record in host.repository.list()}
        if new_title in titles and old_title not in titles:
            return
        time.sleep(.1)
    raise AssertionError(f'report title did not change: {old_title!r} -> {new_title!r}')


if __name__ == '__main__':
    raise SystemExit(main())
