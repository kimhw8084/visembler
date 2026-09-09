#!/usr/bin/env python3
"""Validate the repository-local authorities used by a Visembler release.

This is intentionally source-only.  It proves that the current checkout is
internally coherent, but it never turns local evidence into managed-company
certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from source_identity import candidate_sha, source_manifest, working_tree
except ModuleNotFoundError:  # imported from the repository test suite
    from scripts.release_checks.source_identity import candidate_sha, source_manifest, working_tree

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
FROZEN_SHA = 'd8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'


def _manifest_check() -> dict[str, Any]:
    from company_ui.certification.engine import combined_css
    from company_ui.version import FRAMEWORK_VERSION

    path = ROOT / 'company_ui/certification/certification_manifest.json'
    if not path.is_file():
        return {'status': 'FAIL', 'errors': ['manifest missing']}
    payload = json.loads(path.read_text(encoding='utf-8'))
    errors: list[str] = []
    if payload.get('framework_version') != FRAMEWORK_VERSION:
        errors.append('framework_version')
    if payload.get('combined_css_bytes') != len(combined_css().encode('utf-8')):
        errors.append('combined_css_bytes')
    import subprocess
    collected = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only'], cwd=ROOT, text=True, capture_output=True, check=False)
    match = re.search(r'(\d+) tests collected', collected.stdout + collected.stderr)
    expected_tests = int(match.group(1)) if match else None
    if expected_tests is None or payload.get('automated_tests') != expected_tests:
        errors.append('automated_tests')
    if payload.get('phase_35_v2_source_completion', {}).get('single_layout_density_token_authority') is not True:
        errors.append('phase_35_v2_source_completion')
    return {
        'status': 'PASS' if not errors else 'FAIL',
        'errors': errors,
        'automated_tests': payload.get('automated_tests'),
        'collected_tests': expected_tests,
    }


def _launcher_check() -> dict[str, Any]:
    run_path = ROOT / 'run_visembler.sh'
    app_path = ROOT / 'app.py'
    launcher_path = ROOT / 'scripts/launch_visembler.py'
    errors: list[str] = []
    if not run_path.is_file() or 'exec "$PY" "$ROOT/app.py"' not in run_path.read_text(encoding='utf-8'):
        errors.append('run_visembler.sh must exec app.py through its resolved root')
    if not app_path.is_file() or 'company_ui.products.visualizer.cli' not in app_path.read_text(encoding='utf-8'):
        errors.append('app.py must delegate to the Visualizer CLI')
    launcher = launcher_path.read_text(encoding='utf-8') if launcher_path.is_file() else ''
    if 'Path(__file__).resolve().parents[1]' not in launcher or 'company_ui.products.visualizer.cli' not in launcher:
        errors.append('scripts/launch_visembler.py must resolve the package root and CLI')
    return {'status': 'PASS' if not errors else 'FAIL', 'errors': errors}


def run(output: Path) -> int:
    from company_ui.governance import run_governance
    from company_ui.governance.public_api import scan_public_api_contract
    from company_ui.governance.release_contract import scan_release_contract

    checks: dict[str, Any] = {}
    governance = run_governance(ROOT)
    checks['governance'] = {
        'status': 'PASS' if governance.passed else 'FAIL',
        'errors': [item.to_dict() for item in governance.errors],
        'warnings': [item.to_dict() for item in governance.warnings],
    }
    api_findings = scan_public_api_contract(ROOT)
    checks['public_api_contract'] = {
        'status': 'PASS' if not api_findings else 'FAIL',
        'findings': [item.to_dict() for item in api_findings],
    }
    release_findings = scan_release_contract(ROOT)
    checks['release_contract'] = {
        'status': 'PASS' if not release_findings else 'FAIL',
        'findings': [item.to_dict() for item in release_findings],
    }
    checks['certification_manifest'] = _manifest_check()
    checks['canonical_launch'] = _launcher_check()
    frozen_sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest() if FROZEN.is_file() else ''
    checks['frozen_connector'] = {'status': 'PASS' if frozen_sha == FROZEN_SHA else 'FAIL', 'sha256': frozen_sha}

    manifest_hash, manifest = source_manifest(ROOT)
    status = 'PASS' if all(value.get('status') == 'PASS' for value in checks.values()) else 'FAIL'
    result = {
        'schema_version': 1,
        'status': status,
        'candidate_sha': candidate_sha(ROOT),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'working_tree': working_tree(ROOT),
        'source_manifest_hash': manifest_hash,
        'source_file_count': len(manifest),
        'checks': checks,
        'managed_target_status': 'PENDING',
        'note': 'Repository-local coherence only; managed-company target evidence remains external.',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': status, 'output': str(output), 'managed_target_status': 'PENDING'}, sort_keys=True))
    return 0 if status == 'PASS' else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    return run(parser.parse_args().output)


if __name__ == '__main__':
    raise SystemExit(main())
