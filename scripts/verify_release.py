#!/usr/bin/env python3
"""Run Visembler's maintained bounded-release checks and package their evidence."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], logs: Path) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    name = '-'.join(Path(part).name for part in command[:3]).replace('/', '_')
    (logs / f'{name}.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
    return {'command': command, 'returncode': completed.returncode, 'status': 'PASS' if completed.returncode == 0 else 'FAIL'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve(); logs = output / 'logs'; logs.mkdir(parents=True, exist_ok=True)
    checks = [
        [sys.executable, '-m', 'pytest', 'tests/test_visualizer_production_closeout.py', 'tests/test_visualizer_product_evolution_01_data_first.py', 'tests/test_visualizer_product_evolution_02_mapping_presets.py', 'tests/test_visualizer_product_evolution_03_dataset_refresh.py', 'tests/test_visualizer_v4_1_final_repair.py'],
        ['node', '--check', 'company_ui/products/visualizer/assets/integrated_editor.mjs'],
        ['node', '--check', 'company_ui/products/visualizer/assets/authoring_dataset_refresh.mjs'],
        ['git', 'diff', '--check'],
    ]
    results = [run(command, logs) for command in checks]
    report = {'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'checks': results, 'status': 'PASS' if all(row['status'] == 'PASS' for row in results) else 'FAIL'}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in output.rglob('*'):
            if path.is_file(): bundle.write(path, path.relative_to(output.parent))
    print(json.dumps({'status': report['status'], 'evidence_zip': str(archive)}, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
