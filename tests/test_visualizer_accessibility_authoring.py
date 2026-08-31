from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'company_ui' / 'products' / 'visualizer' / 'assets'


def test_keyboard_resize_uses_the_same_bounded_geometry_contract_as_pointer_resize() -> None:
    script = """
import { resizeRectByKeyboard } from './company_ui/products/visualizer/assets/authoring_geometry.mjs';
const canvas={w:120,h:100};
const start={x:20,y:20,w:40,h:20};
const west=resizeRectByKeyboard(start,'ArrowLeft',5,{minW:10,minH:10,canvas});
if (JSON.stringify(west)!==JSON.stringify({x:15,y:20,w:45,h:20})) throw new Error('left keyboard resize lost its opposite edge');
const east=resizeRectByKeyboard(start,'ArrowRight',10,{minW:10,minH:10,canvas});
if (east.x!==20 || east.w!==50) throw new Error('modified keyboard resize did not use the requested step');
const bounded=resizeRectByKeyboard({x:100,y:10,w:10,h:20},'ArrowRight',50,{minW:10,minH:10,canvas,inset:5});
if (bounded.x+bounded.w!==115) throw new Error('keyboard resize escaped the canvas');
const minimum=resizeRectByKeyboard({x:20,y:20,w:10,h:20},'ArrowRight',-50,{minW:10,minH:10,canvas});
if (minimum.w!==10 || minimum.x!==20) throw new Error('keyboard resize ignored the minimum size');
"""
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_accessibility_contracts_cover_canvas_palette_grid_summary_focus_and_motion() -> None:
    editor = (ASSETS / 'integrated_editor.mjs').read_text(encoding='utf-8')
    html = (ASSETS / 'integrated_editor.html').read_text(encoding='utf-8')
    css = (ASSETS / 'integrated_editor.css').read_text(encoding='utf-8')

    for token in (
        "resizeRectByKeyboard",
        "function keyboardResizeSelected(event)",
        "event.shiftKey?10:1",
        "aria-roledescription', 'report component'",
        "aria-disabled', entry.locked ? 'true' : 'false'",
        "grouped' : ''",
        'focusedComponentId',
        "aria-rowcount",
        "aria-colcount",
        'chart-summary-',
        'aria-describedby="${summaryId}"',
        "aria-activedescendant",
        'function trapModalFocus(e)',
    ):
        assert token in editor
    for token in ('role="combobox"', 'aria-autocomplete="list"', 'id="selStatus" aria-live="polite"'):
        assert token in html
    for token in ('@media (pointer: coarse)', 'min-width:44px!important', 'prefers-reduced-motion: reduce'):
        assert token in css
