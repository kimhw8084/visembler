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


def test_wave3_metric_display_formatting_is_presentation_only() -> None:
    result = node_json(
        r"""
import {formatMetricDisplay,metricDisplayUnit}
from './company_ui/products/visualizer/assets/authoring_format.mjs';
console.log(JSON.stringify({
  number:formatMetricDisplay(1234.5,{style:'number',decimals:2}),
  percent:formatMetricDisplay(98.7,{style:'percent',decimals:1}),
  currency:formatMetricDisplay(1234.5,{style:'currency',decimals:2,currency:'$'}),
  compact:formatMetricDisplay(1420000,{style:'compact',decimals:2}),
  text:formatMetricDisplay('0',{style:'number',decimals:2}),
  unitPercent:metricDisplayUnit({value_format:'percent',unit:'units'}),
  unitCurrency:metricDisplayUnit({value_format:'currency',unit:'USD'}),
}));
"""
    )
    assert result["number"] == "1,234.50"
    assert result["percent"] == "98.7"
    assert result["currency"] == "$1,234.50"
    assert result["compact"] == "1.42M"
    assert result["text"] == "0"
    assert result["unitPercent"] == "%"
    assert result["unitCurrency"] == ""


def test_wave3_chart_sort_and_missing_policy_do_not_coerce_text_zero() -> None:
    result = node_json(
        r"""
import {prepareChartRows}
from './company_ui/products/visualizer/assets/authoring_format.mjs';
const rows=[
  {label:'B',value:0},
  {label:'A',value:'0'},
  {label:'C',value:null},
  {label:'D',value:5},
];
console.log(JSON.stringify({
  input:prepareChartRows(rows),
  zero:prepareChartRows(rows,{missingPolicy:'zero'}),
  drop:prepareChartRows(rows,{missingPolicy:'drop'}),
  desc:prepareChartRows(rows,{sortMode:'value-desc'}),
}));
"""
    )
    assert result["input"] == [
        {"label": "B", "value": 0},
        {"label": "A", "value": "0"},
        {"label": "C", "value": None},
        {"label": "D", "value": 5},
    ]
    assert result["zero"][1]["value"] == "0"
    assert result["zero"][2]["value"] == 0
    assert [row["label"] for row in result["drop"]] == ["B", "A", "D"]
    assert [row["label"] for row in result["desc"]][:2] == ["D", "B"]


def test_wave3_metric_and_chart_controls_are_exposed_in_inspector() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function metricFormatMarkup(entry)" in editor
    assert 'id="iValueFormat"' in editor
    assert 'id="iDecimals"' in editor
    assert 'id="iCurrencySymbol"' in editor
    assert 'id="iChartSort"' in editor
    assert 'id="iChartMissing"' in editor
    assert "Edit metric value format" in editor
    assert "Edit chart sort" in editor
    assert "Edit chart missing-value policy" in editor


def test_wave3_renderer_uses_presentation_helpers() -> None:
    renderer = (ASSETS / "element_renderer.mjs").read_text(encoding="utf-8")
    assert "formatMetricDisplay" in renderer
    assert "metricDisplayUnit" in renderer
    assert "prepareChartRows" in renderer
    assert "sortMode:entry.sort_mode||'input'" in renderer
    assert "missingPolicy:entry.missing_policy||'gap'" in renderer


def test_wave3_format_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_format.mjs'" in page
