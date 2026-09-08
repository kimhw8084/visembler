#!/usr/bin/env python3
"""Emit the clean-source gate consumed by the company release aggregator."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
FROZEN_SHA = 'd8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'


def _git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def run(output: Path) -> int:
    status = _git('status', '--short')
    diff_check = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
    frozen_sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    checks = {
        'working_tree_clean': not status,
        'diff_check': diff_check.returncode == 0,
        'frozen_connector': frozen_sha == FROZEN_SHA,
    }
    result = {
        'schema_version': 1,
        'status': 'PASS' if all(checks.values()) else 'FAIL',
        'candidate_sha': _git('rev-parse', 'HEAD'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
        'working_tree': status.splitlines(),
        'frozen_connector_sha': frozen_sha,
        'diff_check_output': diff_check.stdout + diff_check.stderr,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(output), 'checks': checks}, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    return run(parser.parse_args().output)


if __name__ == '__main__':
    raise SystemExit(main())
