#!/usr/bin/env python3
"""Execute maintained checks; never turn missing coverage into a release PASS.

Default browser mode uses the real NiceGUI host. Embedded mode deliberately
substitutes a test transport while retaining the production editor and file
repository; it is useful on restricted machines, not a native-host receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = 'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
FROZEN_HASH = 'd8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'


def source_manifest() -> dict[str, str]:
    paths = []
    for directory in ('company_ui', 'scripts', 'tests'):
        paths.extend(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and not path.is_symlink()
                     and '__pycache__' not in path.parts
                     and path.suffix in {'.py', '.mjs', '.js', '.css', '.html', '.json', '.md'})
    paths.extend(ROOT / name for name in ('pyproject.toml', 'requirements.txt') if (ROOT / name).is_file())
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New empty evidence directory outside the checkout')
    parser.add_argument('--host-mode', choices=('native', 'embedded'), default='native')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('--output must be outside the checkout')
    if output.exists() and any(output.iterdir()):
        parser.error('--output must be new or empty; stale receipts must not be reused')
    output.mkdir(parents=True, exist_ok=True)
    logs = output / 'logs'; logs.mkdir()
    before = source_manifest()
    (output / 'source-manifest.json').write_text(json.dumps(before, indent=2) + '\n')
    if ROOT.joinpath('.git').exists():
        try: git_status_start=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip().splitlines()
        except Exception: git_status_start=[]
    else: git_status_start=[]
    results: list[dict] = []

    def run(name: str, command: list[str], timeout: int = 180) -> None:
        started = time.monotonic()
        row = {'name': name, 'command': command, 'log': f'logs/{name}.log'}
        with (logs / f'{name}.log').open('w', encoding='utf-8') as log:
            try:
                process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                         text=True, timeout=timeout)
                row.update(returncode=process.returncode, status='PASS' if process.returncode == 0 else 'FAIL')
            except (OSError, subprocess.TimeoutExpired) as error:
                log.write('\n' + str(error) + '\n')
                row.update(status='BLOCKED_ENV' if isinstance(error, OSError) else 'FAIL', error=str(error))
        row['elapsed_seconds'] = round(time.monotonic() - started, 3)
        results.append(row)
        (output / 'progress.json').write_text(json.dumps(results, indent=2) + '\n')
        print(f'{name}: {row["status"]}', flush=True)

    run('repository-contracts', [sys.executable, 'scripts/release_checks/run_repository_contracts.py',
                                '--output', str(output / 'repository-contracts.json')], 180)
    run('company-boundary-model', [sys.executable, 'scripts/release_checks/run_company_user_acceptance.py',
                                   '--output', str(output / 'company-boundary-model.json')], 180)
    run('company-boundary-browser', [sys.executable, 'scripts/release_checks/run_company_boundary_browser_gate.py',
                                    '--output', str(output / 'company-boundary-browser.json')], 360)
    run('company-readiness-local', [sys.executable, 'scripts/release_checks/run_company_production_readiness.py',
                                   '--data-dir', str(output / 'company-readiness-data'),
                                   '--output', str(output / 'company-readiness-local.json')], 180)
    run('company-capacity', [sys.executable, 'scripts/release_checks/run_company_capacity.py',
                             '--output', str(output / 'company-capacity.json')], 300)

    run('delivery-tests', [sys.executable, '-m', 'pytest', 'tests/test_visualizer_completion_delivery.py',
                          'tests/test_visualizer_production_closeout.py', '--tb=short',
                          '--junitxml=' + str(output / 'delivery-tests.xml')])
    run('full-tests', [sys.executable, '-m', 'pytest', '--tb=short',
                       '--junitxml=' + str(output / 'full-tests.xml')], 600)
    assets = ROOT / 'company_ui/products/visualizer/assets'
    for name in ('integrated_editor.mjs', 'element_renderer.mjs', 'authoring_dataset_refresh.mjs',
                 'authoring_portability.mjs', 'authoring_intake_client.mjs'):
        run('syntax-' + name, ['node', '--check', str(assets / name)])
    run('persistence-source-probe', ['node', 'scripts/release_checks/probe_persistence.mjs', '--repo', str(ROOT),
                                    '--output', str(output / 'persistence-source.json')])
    if (ROOT / '.git').exists():
        run('git-diff-check', ['git', 'diff', '--check'])
    else:
        results.append({'name': 'git-diff-check', 'status': 'NOT_RUN', 'reason': 'Source archive has no .git directory.'})

    browser_available = True
    if args.host_mode == 'native':
        try:
            if importlib.metadata.version('nicegui') != '3.15.0':
                raise RuntimeError('Native checks require the declared NiceGUI 3.15.0 runtime.')
        except (importlib.metadata.PackageNotFoundError, RuntimeError) as error:
            browser_available = False
            results.append({'name': 'native-host-dependency', 'status': 'BLOCKED_ENV', 'reason': str(error)})

    browser_checks = [
        ('elements', 'run_editor_workflows.py', 1200),
        ('data', 'run_data_workflows.py', 900),
        ('performance', 'measure_editor.py', 600),
    ]
    if args.host_mode == 'native':
        browser_checks.extend([
            ('report-hub-browser-errors', 'run_report_hub_browser_error_gate.py', 600),
            ('native-recovery', 'run_native_recovery.py', 600),
            ('worker-lifecycle', 'run_worker_lifecycle.py', 600),
            ('operations-drill', 'run_operations_drill.py', 600),
            ('native-acceptance', 'run_native_acceptance.py', 900),
        ])
    for name, script, timeout in browser_checks:
        if browser_available:
            command = [sys.executable, 'scripts/release_checks/' + script, '--output', str(output / name)]
            if args.host_mode == 'native' and script in {'run_editor_workflows.py','run_data_workflows.py','measure_editor.py'}:
                command.append('--native')
            run(name, command, timeout)
        else:
            results.append({'name': name, 'status': 'NOT_RUN', 'reason': 'Native host dependency unavailable.'})

    after = source_manifest()
    results.append({'name': 'source-stability', 'status': 'PASS' if after == before else 'FAIL'})
    results.append({'name': 'frozen-connector', 'status': 'PASS' if before.get(FROZEN) == FROZEN_HASH else 'FAIL'})
    required_names={
        'delivery-tests','full-tests','syntax-integrated_editor.mjs','syntax-element_renderer.mjs',
        'syntax-authoring_dataset_refresh.mjs','syntax-authoring_portability.mjs','syntax-authoring_intake_client.mjs',
        'repository-contracts','company-boundary-model','company-boundary-browser','company-readiness-local','company-capacity',
        'persistence-source-probe','elements','data','performance','source-stability','frozen-connector',
    }
    if ROOT.joinpath('.git').exists(): required_names.add('git-diff-check')
    if args.host_mode=='native':
        required_names.update({'report-hub-browser-errors','native-recovery','worker-lifecycle','operations-drill','native-acceptance'})
    by_name={row['name']:row for row in results}
    missing=sorted(required_names-set(by_name))
    failing=sorted(name for name in required_names if by_name.get(name,{}).get('status')!='PASS')
    all_pass=not missing and not failing
    release_status='PASS_LOCAL_INTERNAL_PILOT' if all_pass and args.host_mode=='native' else ('PASS_EMBEDDED_ONLY' if all_pass else 'BLOCKED')
    remaining=[] if release_status=='PASS_LOCAL_INTERNAL_PILOT' else [
        {'name':name,'status':by_name.get(name,{}).get('status','NOT_RUN')} for name in failing or missing
    ]
    report = {
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'platform': platform.platform(), 'python': sys.version, 'host_mode': args.host_mode,
        'source_editor_sha256': before['company_ui/products/visualizer/assets/integrated_editor.mjs'],
        'source_page_sha256': before.get('company_ui/products/visualizer/page.py'),
        'checks': results,
        'required_gates': sorted(required_names),
        'remaining_release_validation': remaining,
        'checks_status': 'PASS' if all_pass else 'INCOMPLETE_OR_FAILED',
        'release_status': release_status,
        'company_boundary_status': 'READY_FOR_COMPANY_TARGET_CERTIFICATION' if by_name.get('company-readiness-local', {}).get('status') == 'PASS' else 'BLOCKED',
        'managed_target_status': 'PENDING',
        'supported_scope': 'single local/internal-pilot instance; shared-network identity/authorization/hosting remain organization-managed',
        'git_status_at_start': git_status_start,
        'reason': 'All bounded local/internal-pilot gates passed on this exact source.' if release_status=='PASS_LOCAL_INTERNAL_PILOT' else 'One or more required bounded-release gates are incomplete or failed.',
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    release_manifest={
        'release_status':release_status,
        'company_boundary_status':report['company_boundary_status'],
        'managed_target_status':'PENDING',
        'source_editor_sha256':report['source_editor_sha256'],
        'source_page_sha256':report['source_page_sha256'],
        'frozen_connector_sha256':before.get(FROZEN),
        'launch_command':'python scripts/launch_visembler.py --data-dir /absolute/path/to/visembler-data --port 8080',
        'verification_command':f'{sys.executable} scripts/verify_release.py --host-mode native --output <new-empty-directory>',
        'backup_contract':'Stop Visembler, copy the complete configured data directory, restore to a separate directory, and verify report/history/image before rollback use.',
        'limitations':['User preferences live in NiceGUI user storage and are not canonical Report JSON.','Shared-network production requires organization-managed authentication, authorization, durable backup and hosting/session controls.'],
    }
    (output/'release-manifest.json').write_text(json.dumps(release_manifest,indent=2)+'\n')
    artifacts = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(output.rglob('*')) if path.is_file()}
    (output / 'artifact-sha256.json').write_text(json.dumps(artifacts, indent=2) + '\n')
    archive = output.parent / (output.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if path.is_file(): bundle.write(path, Path(output.name) / path.relative_to(output))
    print(json.dumps({'release_status': report['release_status'], 'checks_status': report['checks_status'],
                      'evidence_zip': str(archive), 'remaining': remaining}, indent=2))
    return 0 if release_status in {'PASS_LOCAL_INTERNAL_PILOT','PASS_EMBEDDED_ONLY'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
