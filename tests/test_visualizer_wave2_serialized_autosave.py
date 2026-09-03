from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


def test_wave2_autosave_is_serialized_one_commit_at_a_time() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    assert "saveInFlight: null" in js
    assert "function dispatchNextPendingCommit()" in js
    assert "if(ui.saveInFlight||ui.persistenceFailure||ui.recovery)return false;" in js
    assert "ui.saveInFlight=next.commit_id" in js
    assert "if(ui.saveInFlight===p.commit_id)ui.saveInFlight=null" in js


def test_wave2_autosave_errors_and_retries_do_not_bypass_queue() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    assert "if(m.type==='report.conflict'){ui.saveInFlight=null;" in js
    assert "if(!p.commit_id||ui.saveInFlight===p.commit_id)ui.saveInFlight=null" in js
    assert "ui.persistenceFailure=null;ui.saveInFlight=null;" in js
    assert "dispatchSemantic('report.commit',failed)" not in js


def test_wave2_bridge_state_exposes_inflight_for_live_diagnostics() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    assert "pending:ui.pendingCommits.size,inflight:ui.saveInFlight,recovery:!!ui.recovery" in js
