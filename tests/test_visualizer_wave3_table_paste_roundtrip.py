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


def test_wave3_shared_grid_parser_produces_four_distinct_scalar_states() -> None:
    result = node_json(
        r"""
import {parseAuthoringGrid}
from './company_ui/products/visualizer/assets/authoring_values.mjs';
console.log(JSON.stringify(
  parseAuthoringGrid('Numeric\t0\nText\t"0"\nMissing\t\nBlank\t""').rows
));
"""
    )
    assert result == [
        ["Numeric", 0],
        ["Text", "0"],
        ["Missing", None],
        ["Blank", ""],
    ]


def test_wave3_unbound_table_paste_does_not_double_parse_typed_grid_values() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")

    assert "const parsed=parseAuthoringGrid(text).rows" in editor
    assert "grid.rows[index][startColumn+columnOffset]=value;" in editor

    # Once parseAuthoringGrid has produced canonical typed values, the paste
    # loop must not feed them back through the direct-cell parser.
    assert (
        "grid.rows[index][startColumn+columnOffset]=parseTypedCell(value);"
        not in editor
    )


def test_wave3_direct_cell_edit_still_uses_scalar_parser() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "grid.rows[r][c]=parseTypedCell(e.target.value)" in editor
