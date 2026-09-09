#!/usr/bin/env python3
from __future__ import annotations

"""Aggregate fresh company-release receipts without treating missing evidence as green."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from source_identity import candidate_sha
except ModuleNotFoundError:
    from scripts.release_checks.source_identity import candidate_sha

REQUIRED = ('full_tests', 'integrity', 'native', 'company_boundary', 'multi_user', 'migration_recovery', 'fault_lifecycle', 'capacity', 'source_stability')


def _head() -> str:
    return candidate_sha(ROOT)


def aggregate(receipt_dir: Path, output: Path) -> int:
    candidate = _head(); checks: dict[str, Any] = {}; errors: list[str] = []
    for name in REQUIRED:
        path = receipt_dir / f'{name}.json'
        if not path.is_file():
            checks[name] = {'status': 'MISSING', 'path': str(path)}; errors.append(f'missing:{name}'); continue
        try: value=json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            checks[name] = {'status': 'INVALID', 'error': type(exc).__name__}; errors.append(f'invalid:{name}'); continue
        source = value.get('candidate_sha') or value.get('source', {}).get('head') or value.get('source_sha')
        status = value.get('status') or value.get('result') or value.get('release_status')
        checks[name] = {'status': status, 'candidate_sha': source, 'path': str(path)}
        if source != candidate: errors.append(f'sha:{name}')
        if status not in {'PASS', 'PASS_LOCAL_INTERNAL_PILOT', 'READY_FOR_COMPANY_TARGET_CERTIFICATION', 'PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE'}:
            errors.append(f'gate:{name}')
        if name == 'multi_user' and value.get('browser_mode') != 'playwright':
            errors.append('browser_mode:multi_user')
        timestamp = value.get('created_at') or value.get('generated_at')
        if not timestamp:
            errors.append(f'timestamp:{name}')
        else:
            try:
                created=datetime.fromisoformat(str(timestamp).replace('Z','+00:00'))
                if created.tzinfo is None or (datetime.now(timezone.utc)-created).total_seconds()>30*86400: errors.append(f'stale:{name}')
            except ValueError: errors.append(f'timestamp:{name}')
    status='READY_FOR_COMPANY_TARGET_CERTIFICATION' if not errors else 'BLOCKED'
    receipt={'schema_version':1,'status':status,'candidate_sha':candidate,'created_at':datetime.now(timezone.utc).isoformat(),'checks':checks,'errors':sorted(set(errors))}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'errors':sorted(set(errors)),'output':str(output)},sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--receipts',required=True,type=Path); parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); return aggregate(args.receipts,args.output)


if __name__=='__main__': raise SystemExit(main())
