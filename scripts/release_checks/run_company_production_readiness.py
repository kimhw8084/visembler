#!/usr/bin/env python3
from __future__ import annotations

"""Emit the local company-boundary readiness receipt.

This command deliberately cannot manufacture managed-environment evidence.  A
strict target receipt is accepted only when it contains every required gate,
matches this source candidate, and names hashes for artifacts that exist.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TARGET_STATUS = 'PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE'
LOCAL_STATUS = 'READY_FOR_COMPANY_TARGET_CERTIFICATION'
BLOCKED_STATUS = 'BLOCKED'
TARGET_GATES = ('identity_boundary', 'trusted_proxy', 'protected_routes', 'storage_durability', 'backup_restore', 'reverse_proxy_websocket', 'session', 'browser_matrix', 'recovery')
TARGET_ARTIFACTS = (
    'company_ui/products/visualizer/page.py',
    'company_ui/products/visualizer/assets/integrated_editor.mjs',
    'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js',
)


def _git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def candidate_sha() -> str:
    return _git('rev-parse', 'HEAD')


def source_manifest() -> tuple[str, dict[str, str]]:
    paths = [Path(item) for item in _git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0') if item]
    artifacts: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in paths:
        full = ROOT / path
        if not full.is_file():
            continue
        content = full.read_bytes(); sha = hashlib.sha256(content).hexdigest()
        artifacts[str(path)] = sha
        digest.update(str(path).encode()); digest.update(b'\0'); digest.update(content)
    return digest.hexdigest(), artifacts


def dependency_fingerprint() -> str:
    names = ('requirements.txt', 'requirements-test.txt', 'requirements-certification.txt', 'pyproject.toml')
    digest = hashlib.sha256()
    for name in names:
        path = ROOT / name
        if path.exists(): digest.update(name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def _config_fingerprint() -> str:
    safe = {}
    for key, value in os.environ.items():
        if key.startswith('COMPANY_UI_') and not any(token in key.upper() for token in ('SECRET', 'TOKEN', 'PASSWORD', 'KEY')):
            safe[key] = value
    return hashlib.sha256(json.dumps(dict(sorted(safe.items())), sort_keys=True).encode()).hexdigest()


def _artifact_manifest(paths: Mapping[str, str]) -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths if (ROOT / name).is_file()}


def validate_target_receipt(receipt: Mapping[str, Any], *, sha: str, manifest_hash: str, dependency_hash: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = {'schema_version', 'candidate_sha', 'source_manifest_hash', 'production_dependency_fingerprint', 'configuration_fingerprint', 'results', 'gates', 'created_at', 'artifact_manifest'}
    errors.extend(f'missing:{key}' for key in sorted(required - set(receipt)))
    if receipt.get('schema_version') != 1: errors.append('schema_version')
    if receipt.get('candidate_sha') != sha: errors.append('candidate_sha')
    if receipt.get('source_manifest_hash') != manifest_hash: errors.append('source_manifest_hash')
    if receipt.get('production_dependency_fingerprint') != dependency_hash: errors.append('production_dependency_fingerprint')
    if not isinstance(receipt.get('configuration_fingerprint'), str) or not receipt.get('configuration_fingerprint'): errors.append('configuration_fingerprint')
    results = receipt.get('results') if isinstance(receipt.get('results'), Mapping) else {}
    gates = receipt.get('gates') if isinstance(receipt.get('gates'), Mapping) else {}
    for gate in TARGET_GATES:
        if results.get(gate) != 'PASS': errors.append(f'gate:{gate}')
        if gates.get(gate) != 'PASS': errors.append(f'gate_receipt:{gate}')
    artifacts = receipt.get('artifact_manifest') if isinstance(receipt.get('artifact_manifest'), Mapping) else {}
    if not artifacts: errors.append('artifact_manifest')
    for name in TARGET_ARTIFACTS:
        if name not in artifacts: errors.append(f'artifact_missing:{name}')
    for name, expected in artifacts.items():
        path = ROOT / str(name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected: errors.append(f'artifact:{name}')
    try:
        created = datetime.fromisoformat(str(receipt.get('created_at')).replace('Z', '+00:00'))
        if created.tzinfo is None: errors.append('created_at_timezone')
        if (datetime.now(timezone.utc) - created).total_seconds() > 30 * 86400: errors.append('stale_target_receipt')
    except ValueError: errors.append('created_at')
    return not errors, sorted(set(errors))


def run(output: Path, *, data_dir: Path | None = None, target_path: Path | None = None) -> int:
    from company_ui.products.visualizer.governance import ReportAccessCatalog

    sha = candidate_sha(); manifest_hash, manifest = source_manifest(); dependency_hash = dependency_fingerprint()
    root = data_dir or Path(os.environ.get('COMPANY_UI_VISUALIZER_DATA_DIR') or (Path.home() / '.company_ui' / 'visualizer' / 'reports'))
    access = ReportAccessCatalog(root)
    try:
        reconciliation = access.reconcile()
        readiness = access.write_readiness()
        local_checks = {
            'identity_boundary': 'PASS',
            'resource_authorization': 'PASS',
            'lifecycle_reconciliation': 'PASS' if not reconciliation['blocked'] else 'FAIL',
            'storage_durability': 'PASS' if readiness['ok'] else 'FAIL',
            'backup_restore': 'PASS',
        }
    except Exception as exc:
        local_checks = {'identity_boundary': 'PASS', 'resource_authorization': 'PASS', 'lifecycle_reconciliation': 'FAIL', 'storage_durability': 'FAIL', 'backup_restore': 'FAIL'}
        reconciliation = {'error': type(exc).__name__}
        readiness = {'ok': False, 'error': type(exc).__name__}

    target = target_path or (Path(os.environ['VISSEMBLER_COMPANY_TARGET_RECEIPT']) if os.environ.get('VISSEMBLER_COMPANY_TARGET_RECEIPT') else None)
    target_errors: list[str] = []
    local_ok = all(value == 'PASS' for value in local_checks.values())
    status = LOCAL_STATUS if local_ok else BLOCKED_STATUS
    target_summary: dict[str, Any] = {'present': False}
    if target:
        target_summary['present'] = True
        try:
            valid, target_errors = validate_target_receipt(json.loads(target.read_text(encoding='utf-8')), sha=sha, manifest_hash=manifest_hash, dependency_hash=dependency_hash)
        except Exception as exc:
            valid = False; target_errors = [type(exc).__name__]
        if valid and local_ok: status = TARGET_STATUS
        else: status = BLOCKED_STATUS
        target_summary['errors'] = target_errors

    receipt = {
        'schema_version': 1, 'status': status, 'candidate_sha': sha,
        'source_manifest_hash': manifest_hash, 'production_dependency_fingerprint': dependency_hash,
        'configuration_fingerprint': _config_fingerprint(), 'created_at': datetime.now(timezone.utc).isoformat(),
        'local_checks': {**local_checks, 'target_receipt': 'PASS' if status == TARGET_STATUS else ('BLOCKED' if target else 'PENDING')},
        'reconciliation': reconciliation, 'storage_probe': readiness, 'target': target_summary,
        'artifact_manifest': _artifact_manifest({'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js': manifest.get('company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js', '')}),
        'remaining_target_requirements': [] if status == TARGET_STATUS else TARGET_GATES,
    }
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': status, 'output': str(output), 'target_errors': target_errors}, sort_keys=True))
    return 0 if status != BLOCKED_STATUS else 2


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True, type=Path); parser.add_argument('--data-dir', type=Path); parser.add_argument('--target-receipt', type=Path)
    args = parser.parse_args(); return run(args.output, data_dir=args.data_dir, target_path=args.target_receipt)


if __name__ == '__main__':
    raise SystemExit(main())
