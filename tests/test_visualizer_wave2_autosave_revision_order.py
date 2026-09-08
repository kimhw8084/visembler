from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


def test_wave2_pending_autosave_dispatches_lowest_base_revision_first() -> None:
    js = EDITOR.read_text(encoding="utf-8")
    assert "const queued=[...ui.pendingCommits.values()].sort((a,b)=>" in js
    assert "(Number(a.base_revision)||0)-(Number(b.base_revision)||0)" in js
    assert "const next=queued[0]" in js
    assert "const next=[...ui.pendingCommits.values()][0]" not in js


def test_wave2_revision_ordering_rule_handles_reverse_insertion_order() -> None:
    source = '''
const pending = new Map();
pending.set("cmd-12", {commit_id:"cmd-12", base_revision:11});
pending.set("cmd-11", {commit_id:"cmd-11", base_revision:10});
const queued=[...pending.values()].sort((a,b)=>
  (Number(a.base_revision)||0)-(Number(b.base_revision)||0)
  || String(a.commit_id||"").localeCompare(String(b.commit_id||""))
);
console.log(JSON.stringify(queued.map(x=>[x.commit_id,x.base_revision])));
'''
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout) == [["cmd-11", 10], ["cmd-12", 11]]
