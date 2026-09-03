from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


def test_wave2_commit_registers_persistence_before_render_reentry() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    start = js.index("function commitOps(label, ops")
    end = js.index("\nfunction undo()", start)
    block = js[start:end]

    assert "if (sameValue(next, model()))" in block
    assert "syncAccepted(accepted);" in block
    assert "if(render)renderAll();" in block
    assert block.index("syncAccepted(accepted);") < block.index("if(render)renderAll();")


def test_wave2_undo_and_redo_register_persistence_before_render() -> None:
    js = EDITOR.read_text(encoding="utf-8")

    undo_start = js.index("function undo()")
    redo_start = js.index("function redo()", undo_start)
    prune_start = js.index("function pruneSelection()", redo_start)

    undo = js[undo_start:redo_start]
    redo = js[redo_start:prune_start]

    assert undo.index("syncAccepted(") < undo.index("renderAll();")
    assert redo.index("syncAccepted(") < redo.index("renderAll();")


def test_wave2_noop_guard_prevents_duplicate_canonical_revision() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    start = js.index("function commitOps(label, ops")
    end = js.index("\nfunction undo()", start)
    block = js[start:end]

    prospective = block.index("next=prospectiveModel")
    noop = block.index("if (sameValue(next, model()))")
    commit = block.index("const accepted=store.commit")
    assert prospective < noop < commit
