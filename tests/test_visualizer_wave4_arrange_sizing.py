from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_wave4_match_size_respects_semantic_minimums_and_canvas_bounds() -> None:
    result = node_json(
        r"""
import {matchSizePatches}
from './company_ui/products/visualizer/assets/authoring_arrange.mjs';
const entries=[
  {id:'ref',r:{x:20,y:20,w:200,h:100},minW:100,minH:80},
  {id:'wide-min',r:{x:850,y:730,w:120,h:60},minW:250,minH:120},
  {id:'normal',r:{x:400,y:300,w:90,h:50},minW:80,minH:70},
];
console.log(JSON.stringify({
  width:matchSizePatches(entries,'width',{canvasWidth:1000,canvasHeight:800,inset:14}),
  size:matchSizePatches(entries,'size',{canvasWidth:1000,canvasHeight:800,inset:14}),
}));
"""
    )

    width = result["width"]
    assert width[0]["id"] == "wide-min"
    assert width[0]["patch"]["w"] == 250
    assert width[0]["patch"]["x"] == 736
    assert "h" not in width[0]["patch"]

    size = result["size"]
    assert size[0]["patch"]["w"] == 250
    assert size[0]["patch"]["h"] == 120
    assert size[0]["patch"]["y"] == 666
    assert size[1]["patch"]["w"] == 200
    assert size[1]["patch"]["h"] == 100


def test_wave4_editor_exposes_full_alignment_surface() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "if (kind === 'right')" in editor
    assert "if (kind === 'bottom')" in editor
    assert "if (kind === 'middle')" in editor

    for action in [
        'data-inspector="align-left"',
        'data-inspector="align-center"',
        'data-inspector="align-right"',
        'data-inspector="align-top"',
        'data-inspector="align-middle"',
        'data-inspector="align-bottom"',
        'data-inspector="distribute-x"',
        'data-inspector="distribute-y"',
    ]:
        assert action in editor


def test_wave4_editor_exposes_match_size_actions_and_reference_semantics() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function matchSize(kind)" in editor
    assert "matchSizePatches" in editor
    assert "First unlocked selected element is the size reference." in editor
    for action in [
        'data-inspector="match-width"',
        'data-inspector="match-height"',
        'data-inspector="match-size"',
    ]:
        assert action in editor
    assert "value==='match-width'" in editor
    assert "value==='match-height'" in editor
    assert "value==='match-size'" in editor


def test_wave4_match_size_reuses_guided_overlap_guard() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "Guided equal sizing would overlap another component" in editor
    assert "manualOpsOverlap(ops)" in editor


def test_wave4_arrange_commands_are_searchable() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "Match selected width" in editor
    assert "Match selected height" in editor
    assert "Match selected size" in editor


def test_wave4_arrange_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_arrange.mjs'" in page
