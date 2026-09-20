from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from company_ui.products.visualizer import page as page_module

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


def test_wave3_scalar_contract_preserves_zero_text_zero_null_and_blank() -> None:
    result = node_json(
        r"""
import {
  parseAuthoringScalar,
  formatAuthoringScalar,
  parseAuthoringGrid,
  formatAuthoringRow,
} from './company_ui/products/visualizer/assets/authoring_values.mjs';

const grid=parseAuthoringGrid('n\tt\tmissing\tblank\n0\t"0"\t\t""');
console.log(JSON.stringify({
  values:grid.rows[1],
  scalar:[
    parseAuthoringScalar('0'),
    parseAuthoringScalar('"0"'),
    parseAuthoringScalar(''),
    parseAuthoringScalar('""'),
  ],
  formatted:[
    formatAuthoringScalar(0),
    formatAuthoringScalar('0'),
    formatAuthoringScalar(null),
    formatAuthoringScalar(''),
  ],
  row:formatAuthoringRow([0,'0',null,'']),
}));
"""
    )
    assert result["values"] == [0, "0", None, ""]
    assert result["scalar"] == [0, "0", None, ""]
    assert result["formatted"] == ["0", '"0"', "", '""']
    assert result["row"] == '0\t"0"\t\t""'


def test_wave3_unknown_direct_edit_keeps_percent_and_currency_as_text() -> None:
    result = node_json(
        r"""
import {parseAuthoringScalar} from './company_ui/products/visualizer/assets/authoring_values.mjs';
console.log(JSON.stringify([
  parseAuthoringScalar('98.7%'),
  parseAuthoringScalar('$42.80'),
  parseAuthoringScalar('42.8'),
]));
"""
    )
    assert result == ["98.7%", "$42.80", 42.8]


def test_wave3_dataset_intake_preserves_explicit_quoted_string_intent() -> None:
    result = node_json(
        r"""
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
const data=intakeText('Measure\tValue\nNumeric zero\t0\nText zero\t"0"\nMissing\t\nBlank text\t""');
console.log(JSON.stringify(data.rows));
"""
    )
    assert result == [
        ["Numeric zero", 0],
        ["Text zero", "0"],
        ["Missing", None],
        ["Blank text", ""],
    ]


def test_field_aware_direct_edit_preserves_profiled_string_zero() -> None:
    result = node_json(
        r"""
import {parseAuthoringFieldValue} from './company_ui/products/visualizer/assets/authoring_values.mjs';
console.log(JSON.stringify({
  identifier: parseAuthoringFieldValue('0',{type:'identifier'}),
  category: parseAuthoringFieldValue('0',{type:'categorical'}),
  numeric: parseAuthoringFieldValue('0',{type:'number'}),
  missing: parseAuthoringFieldValue('',{type:'number'}),
  blank: parseAuthoringFieldValue('""',{type:'string'}),
}));
"""
    )
    assert result == {
        "identifier": "0",
        "category": "0",
        "numeric": 0,
        "missing": None,
        "blank": "",
    }


def test_wave3_editor_uses_shared_typed_grid_contract() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function parseCellForField(raw, field, quoted=false)" in editor
    assert "parseAuthoringFieldValue" in editor
    assert "parseCellForField(value,directDataset.fields?.[directColumn])" in editor
    assert "parseAuthoringFieldValue(raw,field||{},{quoted})" in editor
    assert "from './authoring_values.mjs'" in editor
    assert "function parseTypedCell(raw) { return parseAuthoringScalar(raw); }" in editor
    assert "function parseTable(text) { return parseAuthoringGrid(text).rows; }" in editor
    assert "formatAuthoringRow" in editor
    assert "formatAuthoringScalar(record.row[column])" in editor


def test_wave3_asset_fingerprint_includes_authoring_values() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_values.mjs'" in page


def test_chg138_runtime_assets_are_fingerprinted_and_byte_sensitive(tmp_path, monkeypatch) -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    runtime_assets = (
        "authoring_human.mjs",
        "authoring_preview.mjs",
        "authoring_projection.mjs",
        "authoring_values.mjs",
    )
    assert all(f"'{name}'" in page for name in runtime_assets)

    copied_product = tmp_path / "product"
    copied_assets = copied_product / "assets"
    shutil.copytree(ASSETS, copied_assets)
    copied_vendor = copied_product / "vendor" / "production_core"
    shutil.copytree(page_module.VENDOR / "core", copied_vendor / "core")
    monkeypatch.setattr(page_module, "PRODUCT", copied_product)
    monkeypatch.setattr(page_module, "ASSETS", copied_assets)
    monkeypatch.setattr(page_module, "VENDOR", copied_vendor)
    baseline = page_module._asset_build()

    for name in ("authoring_preview.mjs", "authoring_projection.mjs"):
        asset = copied_assets / name
        original = asset.read_bytes()
        mutated = original[:1] + bytes((original[0] ^ 1,)) + original[1:]
        asset.write_bytes(mutated)
        assert page_module._asset_build() != baseline, name
        asset.write_bytes(original)
        assert page_module._asset_build() == baseline, name
