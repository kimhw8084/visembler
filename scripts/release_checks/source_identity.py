"""Source identity helpers shared by checkout and archive release checks.

Archives intentionally do not contain ``.git``.  They may still run local
verification when the handoff supplies the immutable candidate SHA through
``VISSEMBLER_CANDIDATE_SHA``.  The fallback is explicit and fail-closed; it
never invents a source identity.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def _git_root(root: Path) -> bool:
    return (root / '.git').exists()


def candidate_sha(root: Path) -> str:
    if _git_root(root):
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    value = str(os.environ.get('VISSEMBLER_CANDIDATE_SHA') or '').strip()
    if not value:
        raise RuntimeError('VISSEMBLER_CANDIDATE_SHA is required when verifying a source archive without .git')
    return value


def working_tree(root: Path) -> list[str]:
    if not _git_root(root):
        return []
    return subprocess.check_output(['git', 'status', '--short'], cwd=root, text=True).splitlines()


def source_paths(root: Path) -> list[Path]:
    if _git_root(root):
        output = subprocess.check_output(
            ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            cwd=root,
        ).decode('utf-8')
        return [Path(item) for item in output.split('\0') if item]
    return [
        path.relative_to(root)
        for path in root.rglob('*')
        if path.is_file()
        and '.git' not in path.parts
        and '__pycache__' not in path.parts
        and path.suffix != '.pyc'
    ]


def source_manifest(root: Path) -> tuple[str, dict[str, str]]:
    artifacts: dict[str, str] = {}
    digest = hashlib.sha256()
    for relative in sorted(set(source_paths(root))):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        name = relative.as_posix()
        artifacts[name] = hashlib.sha256(content).hexdigest()
        digest.update(name.encode('utf-8'))
        digest.update(b'\0')
        digest.update(content)
    return digest.hexdigest(), artifacts
