from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui/products/visualizer/assets"


def _node(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_wave2_diagram_node_rename_remaps_edges_atomically() -> None:
    payload = _node(
        "import {reconcileDiagramEdges} from "
        "'./company_ui/products/visualizer/assets/authoring_diagram.mjs';"
        "const edges=reconcileDiagramEdges("
        "['Signal','Analyze','Validate','Decision'],"
        "['Detect','Analyze','Verify','Release'],"
        "[['Signal','Analyze'],['Analyze','Validate'],['Validate','Decision']]);"
        "console.log(JSON.stringify({edges}));"
    )
    assert payload["edges"] == [
        ["Detect", "Analyze"],
        ["Analyze", "Verify"],
        ["Verify", "Release"],
    ]


def test_wave2_diagram_reorder_preserves_and_delete_prunes_edges() -> None:
    payload = _node(
        "import {reconcileDiagramEdges} from "
        "'./company_ui/products/visualizer/assets/authoring_diagram.mjs';"
        "const reorder=reconcileDiagramEdges("
        "['A','B','C'],['B','A','C'],[['A','B'],['B','C']]);"
        "const deleted=reconcileDiagramEdges("
        "['A','B','C'],['A','B'],[['A','B'],['B','C']]);"
        "console.log(JSON.stringify({reorder,deleted}));"
    )
    assert payload["reorder"] == [["A", "B"], ["B", "C"]]
    assert payload["deleted"] == [["A", "B"]]


def test_wave2_diagram_edge_validation_rejects_unknown_endpoints() -> None:
    payload = _node(
        "import {parseDiagramEdges,validateDiagramEdges} from "
        "'./company_ui/products/visualizer/assets/authoring_diagram.mjs';"
        "const edges=parseDiagramEdges('A -> B\\nB -> C');"
        "console.log(JSON.stringify({"
        "edges,"
        "ok:validateDiagramEdges(['A','B','C'],edges),"
        "bad:validateDiagramEdges(['A','B'],edges)"
        "}));"
    )
    assert payload["edges"] == [["A", "B"], ["B", "C"]]
    assert payload["ok"] == {"valid": True, "unknown": []}
    assert payload["bad"] == {"valid": False, "unknown": ["C"]}


def test_wave2_editor_uses_atomic_diagram_handlers() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "from './authoring_diagram.mjs'" in editor
    assert "reconcileDiagramEdges(entry.nodes||[],nodes,entry.edges||[])" in editor
    assert "patch('Edit diagram nodes',{nodes,edges})" in editor
    assert "validateDiagramEdges(entry.nodes||[],edges)" in editor
    assert "Unknown diagram node:" in editor
