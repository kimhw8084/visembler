#!/usr/bin/env python3
"""Run the company-user browser contract against an isolated native host.

The multi-principal browser receipt is a release input, not a manual side
check.  This wrapper owns a fresh temporary repository and a free local port,
starts the real production-mode Visembler entrypoint, delegates assertions to
the maintained browser suite, and removes the isolated fixture directory in a
finally block.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, process: subprocess.Popen[str], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = 'server did not become ready'
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Visembler exited before readiness with code {process.returncode}')
        try:
            with urlopen(f'{base_url}/healthz', timeout=1.0) as response:
                if response.status == 200:
                    return
                last_error = f'health status {response.status}'
        except Exception as exc:  # bounded polling of a local process
            last_error = str(exc)
        time.sleep(0.1)
    raise TimeoutError(last_error)


def run(output: Path) -> int:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix='visembler-company-boundary-browser-'))
    port = _free_port()
    base_url = f'http://127.0.0.1:{port}'
    server_log = output.with_suffix('.server.log')
    process: subprocess.Popen[str] | None = None
    result: dict[str, object] = {
        'schema_version': 1,
        'status': 'FAIL',
        'base_url': base_url,
        'data_dir': str(temp_dir),
        'cleanup': {'attempted': False, 'remaining': None},
    }
    try:
        environment = os.environ.copy()
        environment.update({
            'COMPANY_UI_ENVIRONMENT': 'prod',
            'COMPANY_UI_AUTH_MODE': 'header',
            'COMPANY_UI_PROXY_ENABLED': 'true',
            'COMPANY_UI_TRUSTED_PROXIES': '127.0.0.1',
            'COMPANY_UI_STORAGE_SECRET': secrets.token_urlsafe(48),
            'COMPANY_UI_MIGRATION_OWNER_SUBJECT': 'alice',
            'COMPANY_UI_DIAGNOSTICS_ENABLED': 'true',
            'COMPANY_UI_HOST': '0.0.0.0',
            'COMPANY_UI_PORT': str(port),
            'COMPANY_UI_VISUALIZER_DATA_DIR': str(temp_dir),
        })
        with server_log.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(
                [sys.executable, 'scripts/launch_visembler.py', '--host', '0.0.0.0', '--port', str(port), '--data-dir', str(temp_dir)],
                cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, text=True,
            )
        _wait_for_health(base_url, process)
        child = subprocess.run(
            [sys.executable, 'scripts/release_checks/run_company_user_browser_acceptance.py',
             '--base-url', base_url, '--data-dir', str(temp_dir), '--output', str(output)],
            cwd=ROOT, text=True, capture_output=True, timeout=240,
        )
        result['child_returncode'] = child.returncode
        result['child_stdout'] = child.stdout[-4000:]
        result['child_stderr'] = child.stderr[-4000:]
        if output.exists():
            child_receipt = json.loads(output.read_text(encoding='utf-8'))
            result.update(child_receipt)
        result['status'] = 'PASS' if child.returncode == 0 else 'FAIL'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        result['cleanup'] = {'attempted': True, 'remaining': int(any(temp_dir.iterdir())) if temp_dir.exists() else 0}
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        result['cleanup']['remaining'] = 0 if not temp_dir.exists() else 1
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(output), 'server_log': str(server_log)}, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    return run(parser.parse_args().output)


if __name__ == '__main__':
    raise SystemExit(main())
