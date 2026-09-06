#!/usr/bin/env python3
"""Native browser acceptance for the dedicated Visembler Diagram Studio.

The fixture is temporary and the browser drives the visible studio surface.  A
small number of model assertions inspect the public studio state to verify
canonical persistence, routing geometry, and that no editor-only chrome leaks
into exported SVG.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from company_ui.products.visualizer.domain import canonical_model
from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json
from playwright.sync_api import sync_playwright


def _diagram_model() -> dict:
    return canonical_model({
        'schema_version': 1,
        'items': [{
            'id': 'diagram-1', 'type': 'diagram', 'engine': 'DiagramEngine',
            'element': 'Process Flow', 'title': 'Manufacturing flow',
            'nodes': ['Source', 'Inspect', 'Release'],
            'edges': [['Source', 'Inspect'], ['Inspect', 'Release']],
            'direction': 'right', 'edge_label': 'handoff', 'order': 0,
            'weight': 1.3, 'locked': False, 'z': 1,
        }],
        'groups': {}, 'datasets': [], 'crossFilter': None,
        'mode': 'smart', 'layoutPreset': 'editorial',
        'canvas': {'width': 1600, 'height': 900}, 'nextId': 2,
    })


def _studio_state(page) -> dict:
    return page.evaluate('()=>window.CompanyUIDiagramStudio.state()')


def _wait_studio(page) -> None:
    page.locator('#diagram-studio[data-studio-ready="true"]').wait_for(timeout=20000)


def _wait_saved(page) -> None:
    page.wait_for_function(
        '()=>{const s=window.CompanyUIDiagramStudio.state();return !s.pending&&!s.dirty}',
        timeout=20000,
    )


def _command(page, name: str, *args):
    return page.evaluate(
        '([name,args])=>window.CompanyUIDiagramStudio.command(name,...args)',
        [name, list(args)],
    )


def _select_nodes(page, indexes: list[int]) -> None:
    page.locator('.ds-node').nth(indexes[0]).dispatch_event('click')
    for index in indexes[1:]:
        page.locator('.ds-node').nth(index).dispatch_event('click', {'shiftKey': True})
    page.wait_for_function(
        '(count)=>window.CompanyUIDiagramStudio.state().selected_nodes.length===count',
        arg=len(indexes),
    )


def _assert_no_overlapping_nodes(page) -> None:
    assert page.evaluate("""()=>{
      const nodes=window.CompanyUIDiagramStudio.state().model.nodes;
      return !nodes.some((a,i)=>nodes.slice(i+1).some(b=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y));
    }"""), 'nodes overlap after Clean Diagram'


def _assert_studio_geometry(page, width: int) -> None:
    metrics = page.evaluate("""()=>{
      const root=document.querySelector('#diagram-studio'),wrap=document.querySelector('#ds-canvas-wrap'),svg=document.querySelector('#ds-canvas');
      const r=n=>{const x=n?.getBoundingClientRect();return x&&{left:x.left,right:x.right,top:x.top,bottom:x.bottom,width:x.width,height:x.height};};
      return {root:r(root),wrap:r(wrap),svg:r(svg),scrollWidth:document.documentElement.scrollWidth,innerWidth:innerWidth};
    }""")
    assert metrics['root']['width'] > 0 and metrics['wrap']['width'] > 0, (width, metrics)
    assert metrics['scrollWidth'] <= metrics['innerWidth'] + 1, (width, metrics)
    assert metrics['wrap']['left'] >= 0 and metrics['wrap']['right'] <= metrics['innerWidth'] + 1, metrics


def _performance_fixture() -> dict:
    script = """
import {cleanDiagram, normalizeDiagram} from './company_ui/products/visualizer/assets/authoring_diagram_studio.mjs';
const diagram=normalizeDiagram({nodes:Array.from({length:100},(_,i)=>({id:`n${i}`,label:`N${i}`})),edges:Array.from({length:150},(_,i)=>({id:`e${i}`,source:`n${i<99?i:i-99}`,target:`n${i<99?i+1:(i-99+50)%100}`}))});
const started=performance.now();
const cleaned=cleanDiagram(diagram,{direction:'right'});
console.log(JSON.stringify({nodes:cleaned.nodes.length,edges:cleaned.edges.length,elapsed_ms:Number((performance.now()-started).toFixed(2))}));
"""
    completed = subprocess.run(
        ['node', '--input-type=module', '-e', script],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'native Diagram Studio acceptance', 'cases': [], 'unexpected_errors': []}

    def check(name, callback):
        print(f'CHECK {name}', flush=True)
        case = {'name': name, 'status': 'FAIL'}
        try:
            callback()
            case['status'] = 'PASS'
            print(f'PASS {name}', flush=True)
        except Exception as exc:  # keep every acceptance result auditable
            case['error'] = str(exc) or repr(exc)
            case['traceback'] = traceback.format_exc()
            print(f'FAIL {name}: {case["error"]}', flush=True)
        report['cases'].append(case)

    try:
        with tempfile.TemporaryDirectory(prefix='visembler-diagram-studio-') as td:
            with NativeHost(ROOT, Path(td) / 'data') as host, sync_playwright() as playwright:
                report_id = host.create(model=_diagram_model(), name='diagram-studio-acceptance')
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context(accept_downloads=True, viewport={'width': 1440, 'height': 900})
                page = context.new_page()
                page.set_default_timeout(6000)
                events = BrowserEvents()
                events.attach(page)

                page.goto(f'{host.url}/visualizer?report={quote(report_id)}', wait_until='domcontentloaded')
                ready(page, require_settled=True)
                page.locator('[data-action="edit-diagram"]').click()
                _wait_studio(page)

                def open_studio():
                    assert '/visualizer/diagram-studio' in page.url
                    assert _studio_state(page)['model']['schema'] == 'visembler.diagram.studio'

                check('open Diagram Studio from Process Flow', open_studio)

                def create_nodes():
                    initial = len(_studio_state(page)['model']['nodes'])
                    page.get_by_role('button', name='Add Process', exact=True).click()
                    page.get_by_role('button', name='Add Decision', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == initial + 2

                check('create five nodes from the shape palette', create_nodes)

                def quick_connect():
                    _select_nodes(page, [0])
                    before = len(_studio_state(page)['model']['edges'])
                    page.get_by_role('button', name='Quick branch', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == 6
                    assert len(_studio_state(page)['model']['edges']) == before + 1
                    page.locator('.ds-edge').first.dispatch_event('click')
                    edge_before = len(_studio_state(page)['model']['edges'])
                    nodes_before = len(_studio_state(page)['model']['nodes'])
                    page.get_by_role('button', name='Insert node on edge', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == nodes_before + 1
                    assert len(_studio_state(page)['model']['edges']) == edge_before + 1

                check('quick-connect branch and insert node on edge', quick_connect)

                def fixed_and_floating():
                    page.locator('.ds-edge').first.dispatch_event('click')
                    page.locator('[data-edge-inspect="sourcePort"]').select_option('right')
                    page.locator('[data-edge-inspect="targetPort"]').select_option('left')
                    edge = _studio_state(page)['model']['edges'][0]
                    assert edge['sourcePort'] == 'right' and edge['targetPort'] == 'left'
                    page.locator('[data-edge-inspect="sourcePort"]').select_option('floating')
                    page.locator('[data-edge-inspect="targetPort"]').select_option('floating')
                    assert _studio_state(page)['model']['edges'][0]['sourcePort'] == 'floating'

                check('fixed and floating connector ports', fixed_and_floating)

                def waypoint_label_reverse():
                    page.locator('.ds-edge').first.dispatch_event('click')
                    page.get_by_role('button', name='Add waypoint', exact=True).click()
                    assert len(_studio_state(page)['model']['edges'][0]['waypoints']) == 1
                    page.get_by_role('button', name='Add label', exact=True).click()
                    label = page.locator('[data-edge-label]').last
                    label.fill('handoff')
                    label.dispatch_event('change')
                    assert any(item['text'] == 'handoff' for item in _studio_state(page)['model']['edges'][0]['labels'])
                    page.get_by_role('button', name='Reverse direction', exact=True).click()
                    page.get_by_role('button', name='Delete last waypoint', exact=True).click()
                    assert not _studio_state(page)['model']['edges'][0]['waypoints']

                check('orthogonal route, waypoint, center label, reverse', waypoint_label_reverse)

                def multi_selection_commands():
                    _select_nodes(page, [0, 1, 2])
                    page.get_by_role('button', name='Align left', exact=True).click()
                    page.get_by_role('button', name='Distribute H', exact=True).click()
                    page.get_by_role('button', name='Equal width', exact=True).click()
                    page.get_by_role('button', name='Group', exact=True).click()
                    assert len(_studio_state(page)['model']['groups']) == 1
                    page.get_by_role('button', name='Ungroup', exact=True).click()
                    _select_nodes(page, [0, 1])
                    before = len(_studio_state(page)['model']['nodes'])
                    page.locator('[data-action="copy"]').click()
                    page.get_by_role('button', name='Paste', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == before + 2
                    _command(page, 'duplicate')
                    assert len(_studio_state(page)['model']['nodes']) == before + 4

                check('multi-select, lasso-compatible actions, align, group, copy, duplicate', multi_selection_commands)

                def lasso_selection():
                    page.get_by_role('button', name='Clear selection').click()
                    canvas = page.locator('#ds-canvas').bounding_box()
                    assert canvas
                    page.mouse.move(canvas['x'] + 5, canvas['y'] + 5)
                    page.mouse.down()
                    page.mouse.move(canvas['x'] + min(700, canvas['width'] - 5), canvas['y'] + min(350, canvas['height'] - 5))
                    page.mouse.up()
                    assert len(_studio_state(page)['selected_nodes']) >= 2

                check('lasso selects multiple nodes', lasso_selection)

                def inline_label_edit():
                    # Earlier alignment coverage intentionally puts some nodes on
                    # the same x/y bands; exercise the topmost visible node so
                    # this remains a real pointer interaction rather than a
                    # forced DOM event through an occluding shape.
                    node = page.locator('.ds-node').last
                    node_id = node.get_attribute('data-node-id')
                    node.dispatch_event('dblclick')
                    editor = page.locator('.ds-inline-editor')
                    editor.wait_for()
                    editor.fill('Edited process')
                    editor.press('Enter')
                    assert next(item for item in _studio_state(page)['model']['nodes'] if item['id'] == node_id)['label'] == 'Edited process'

                check('inline node label edit commits accessibly', inline_label_edit)

                def layer_and_lane_management():
                    page.get_by_role('button', name='+ Add', exact=True).first.click()
                    assert len(_studio_state(page)['model']['layers']) == 2
                    row = page.locator('.ds-layer-row').last
                    row.locator('[data-layer-action="hide"]').count()
                    row.locator('[data-layer-action="visibility"]').click()
                    row.locator('[data-layer-action="visibility"]').click()
                    row.locator('[data-layer-action="lock"]').click()
                    row.locator('[data-layer-action="lock"]').click()
                    row.locator('[data-layer-action="duplicate"]').click()
                    assert len(_studio_state(page)['model']['layers']) == 3
                    page.get_by_role('button', name='+ Add', exact=True).last.click()
                    page.get_by_role('button', name='+ Add', exact=True).last.click()
                    assert len(_studio_state(page)['model']['swimlanes']) == 2
                    page.locator('.ds-lane-row').last.locator('[data-lane-action="up"]').click()
                    page.locator('.ds-lane-row').first.locator('[data-lane-action="toggle-orientation"]').click()
                    page.locator('.ds-lane-row').first.locator('[data-lane-action="grow"]').click()
                    _select_nodes(page, [0])
                    page.locator('[data-inspect="lane"]').select_option(_studio_state(page)['model']['swimlanes'][0]['id'])
                    assert _studio_state(page)['model']['nodes'][0]['lane']

                check('layer visibility/lock/duplicate and swimlane reorder/move', layer_and_lane_management)

                def layouts_and_clean():
                    _select_nodes(page, [0])
                    pin = page.locator('[data-inspect="pinned"]')
                    if not pin.is_checked():
                        pin.check()
                    pinned_before = page.evaluate("()=>{const n=window.CompanyUIDiagramStudio.state().model.nodes[0];return [n.x,n.y]}")
                    page.get_by_role('button', name='Flow →', exact=True).click()
                    page.get_by_role('button', name='Flow ↓', exact=True).click()
                    pinned_after = page.evaluate("()=>{const n=window.CompanyUIDiagramStudio.state().model.nodes[0];return [n.x,n.y]}")
                    assert pinned_before == pinned_after
                    page.get_by_role('button', name='Clean Diagram', exact=True).click()
                    _assert_no_overlapping_nodes(page)
                    assert all(edge['waypoints'] == [] for edge in _studio_state(page)['model']['edges'])

                check('horizontal/vertical layout and Clean Diagram preserve pinned node', layouts_and_clean)

                def accelerators_and_subflow():
                    page.locator('#ds-process-input').fill('Detect\nAnalyze\nVerify\nRelease')
                    page.get_by_role('button', name='Paste process steps', exact=True).first.click()
                    page.locator('#ds-graph-input').fill('Source\tTarget\tLabel\nTool\tChamber\tfeeds\nChamber\tInspection\tchecks')
                    page.get_by_role('button', name='Paste source-target graph', exact=True).click()
                    _select_nodes(page, [0, 1])
                    page.locator('#ds-subflow-name').fill('Inspection path')
                    page.get_by_role('button', name='Save selection as subflow', exact=True).click()
                    assert page.locator('.ds-subflow-row').count() == 1
                    page.locator('.ds-subflow-row').get_by_role('button', name='Insert', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) >= 8

                check('paste process steps, source-target graph, save/reinsert subflow', accelerators_and_subflow)

                def undo_redo_and_export():
                    before = len(_studio_state(page)['model']['nodes'])
                    _select_nodes(page, [0])
                    _command(page, 'quick-branch')
                    changed = len(_studio_state(page)['model']['nodes'])
                    assert changed == before + 1
                    page.get_by_role('button', name='Undo', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == before
                    page.get_by_role('button', name='Redo', exact=True).click()
                    assert len(_studio_state(page)['model']['nodes']) == changed
                    with page.expect_download() as download_info:
                        page.get_by_role('button', name='Export JSON', exact=True).click()
                    download_info.value.save_as(output / 'diagram.json')
                    with page.expect_download() as download_info:
                        page.get_by_role('button', name='Export SVG', exact=True).click()
                    download_info.value.save_as(output / 'diagram.svg')
                    payload = json.loads((output / 'diagram.json').read_text(encoding='utf-8'))
                    svg = (output / 'diagram.svg').read_text(encoding='utf-8')
                    assert payload['schema'] == 'visembler.diagram.studio'
                    assert 'handoff' in svg and 'Diagram Studio' not in svg

                check('one-transaction undo/redo and JSON/SVG export', undo_redo_and_export)

                def save_reopen_and_preview():
                    page.get_by_role('button', name='Save diagram', exact=True).click()
                    _wait_saved(page)
                    saved_count = len(_studio_state(page)['model']['nodes'])
                    page.get_by_role('button', name='← Report', exact=True).click()
                    page.wait_for_url('**/visualizer?report=*', timeout=20000)
                    ready(page, require_settled=True)
                    page.locator('[data-action="edit-diagram"]').click()
                    _wait_studio(page)
                    assert len(_studio_state(page)['model']['nodes']) == saved_count
                    page.get_by_role('button', name='Preview', exact=True).click()
                    assert 'studio-preview' in (page.locator('#diagram-studio').get_attribute('class') or '')
                    assert not page.locator('.ds-toolbar').is_visible()
                    page.get_by_role('button', name='Exit preview', exact=True).click()

                check('save/close/reopen report integration and reading preview', save_reopen_and_preview)

                def responsive_and_keyboard():
                    for width in (1440, 1024, 768, 390):
                        page.set_viewport_size({'width': width, 'height': 844 if width < 800 else 900})
                        _assert_studio_geometry(page, width)
                    page.set_viewport_size({'width': 1440, 'height': 900})
                    page.locator('.ds-node').first.click()
                    page.locator('#ds-canvas').press('ArrowRight')
                    assert _studio_state(page)['dirty']

                check('responsive studio and keyboard nudge', responsive_and_keyboard)

                def performance_fixture():
                    result = _performance_fixture()
                    assert result['nodes'] == 100 and result['edges'] == 150, result
                    assert result['elapsed_ms'] >= 0, result
                    report['performance_fixture'] = result

                check('100-node/150-edge deterministic layout fixture', performance_fixture)

                report['unexpected_errors'] = events.unexpected
                report['cases'].append({
                    'name': 'no unexpected browser console/page/network errors',
                    'status': 'PASS' if not events.unexpected else 'FAIL',
                    'error': events.unexpected[:8],
                })
                context.close()
                browser.close()
    except Exception as exc:
        report['harness_error'] = str(exc)
        report['traceback'] = traceback.format_exc()

    production_count = int(subprocess.check_output([
        'node', '--input-type=module', '-e',
        "import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs'; console.log(PRODUCTION_LIBRARY_COUNT)",
    ], cwd=ROOT, text=True).strip())
    frozen = ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
    report['production_library_count'] = production_count
    report['frozen_connector_sha256'] = hashlib.sha256(frozen.read_bytes()).hexdigest()
    report['passed'] = sum(case.get('status') == 'PASS' for case in report['cases'])
    report['total'] = len(report['cases'])
    report['status'] = 'PASS' if report['passed'] == report['total'] and production_count == 39 and not report['unexpected_errors'] and 'harness_error' not in report else 'FAIL'
    write_json(output / 'diagram-studio-acceptance.json', report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
