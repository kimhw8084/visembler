#!/usr/bin/env python3
"""Supported loopback launcher; it never kills an existing process."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return probe.connect_ex((host, port)) != 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / '.visembler-data')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    if importlib.metadata.version('nicegui') != '3.15.0':
        raise SystemExit('NiceGUI 3.15.0 is required; install requirements.txt into this Python environment.')
    if not free(args.host, args.port):
        raise SystemExit(f'{args.host}:{args.port} is already in use; choose another --port. No process was stopped.')
    env = os.environ | {'COMPANY_UI_HOST': args.host, 'COMPANY_UI_PORT': str(args.port), 'COMPANY_UI_VISUALIZER_DATA_DIR': str(args.data_dir.resolve())}
    return subprocess.run([sys.executable, '-m', 'company_ui.products.visualizer.cli'], cwd=ROOT, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
