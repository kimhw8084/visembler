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


def test_wave7_style_snapshot_is_presentation_only() -> None:
    result = node_json(
        r"""
import {styleSnapshot}
from './company_ui/products/visualizer/assets/authoring_style.mjs';

const entry={
  id:'c1',engine:'MetricEngine',title:'Yield',unit:'%',value:'0',
  dataset_id:'ds1',mapping:{value:'v'},x:10,y:20,w:300,h:180,
  showTitle:true,textAlign:'center',contentDensity:'fill',emphasis:'hero',
  variant:'quiet',value_format:'percent',decimals:2,currency_symbol:'$',
  tool:'ETCH01',wafer_id:'W1',rows:[[0,'0',null,'']],
};
console.log(JSON.stringify(styleSnapshot(entry)));
"""
    )
    assert result["kind"] == "presentation-style"
    assert result["sourceEngine"] == "MetricEngine"
    assert result["common"] == {
        "showTitle": True,
        "textAlign": "center",
        "contentDensity": "fill",
        "emphasis": "hero",
        "variant": "quiet",
    }
    assert result["engine"] == {
        "value_format": "percent",
        "decimals": 2,
        "currency_symbol": "$",
    }
    encoded = json.dumps(result)
    for forbidden in [
        '"title"', '"unit"', '"value"', '"dataset_id"', '"mapping"',
        '"x"', '"y"', '"w"', '"h"', '"tool"', '"wafer_id"', '"rows"',
    ]:
        assert forbidden not in encoded


def test_wave7_same_engine_gets_specific_format_cross_engine_gets_common_only() -> None:
    result = node_json(
        r"""
import {styleSnapshot,stylePatchForTarget}
from './company_ui/products/visualizer/assets/authoring_style.mjs';

const snapshot=styleSnapshot({
  engine:'MetricEngine',showTitle:true,textAlign:'right',
  contentDensity:'fill',emphasis:'prominent',
  value_format:'currency',decimals:3,currency_symbol:'€',
});
console.log(JSON.stringify({
  metric:stylePatchForTarget(snapshot,{id:'m',engine:'MetricEngine'}),
  text:stylePatchForTarget(snapshot,{id:'t',engine:'TextEngine'}),
}));
"""
    )
    assert result["metric"]["value_format"] == "currency"
    assert result["metric"]["decimals"] == 3
    assert result["metric"]["currency_symbol"] == "€"
    assert result["text"] == {
        "showTitle": True,
        "textAlign": "right",
        "contentDensity": "fill",
        "emphasis": "prominent",
    }


def test_wave7_style_plan_skips_locked_targets() -> None:
    result = node_json(
        r"""
import {styleSnapshot,stylePastePlan}
from './company_ui/products/visualizer/assets/authoring_style.mjs';
const snapshot=styleSnapshot({engine:'TextEngine',textAlign:'center',showTitle:false});
console.log(JSON.stringify(stylePastePlan([
  {id:'a',engine:'TextEngine',locked:false},
  {id:'b',engine:'TextEngine',locked:true},
  {id:'c',engine:'MetricEngine',locked:false},
],snapshot)));
"""
    )
    assert [entry["id"] for entry in result] == ["a", "c"]
    assert all(entry["patch"]["textAlign"] == "center" for entry in result)


def test_wave7_editor_builds_explicit_style_payload_and_applies_to_selection() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "styleSnapshot(entry)" in editor
    assert "stylePastePlan(targets,snapshot)" in editor
    assert "payload?.style||(source?styleSnapshot(source):null)" in editor
    assert "Paste style to selection" in editor
    assert "ui.selected.size<1" in editor


def test_wave7_old_unsafe_style_allowlist_is_removed() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "['title','showTitle','textAlign','weight','emphasis','variant','unit']" not in editor


def test_wave7_reuse_capability_allows_style_on_multi_selection() -> None:
    reuse = (ASSETS / "authoring_reuse.mjs").read_text(encoding="utf-8")
    assert "pasteStyle:selectionCount>0" in reuse
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'data-reuse-action="paste-style"' in editor
    assert "Apply copied style" in editor


def test_wave7_command_palette_exposes_format_painter() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "Apply copied style" in editor
    assert "Apply presentation-only style to selected unlocked elements" in editor


def test_wave7_style_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_style.mjs'" in page
