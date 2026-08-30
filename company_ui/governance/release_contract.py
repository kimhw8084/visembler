from __future__ import annotations

import json
import re
from pathlib import Path

from .models import GovernanceFinding


def _load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return payload


def scan_release_contract(root: Path) -> tuple[GovernanceFinding, ...]:
    findings: list[GovernanceFinding] = []
    authority_path = root / 'company_ui/release_authority.json'
    authority = _load(authority_path)
    version = str(authority['framework_version'])
    nicegui = str(authority['nicegui_version'])

    pyproject = (root / 'pyproject.toml').read_text(encoding='utf-8')
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not version_match or version_match.group(1) != version:
        findings.append(GovernanceFinding('release.version', 'pyproject.toml', 'project version does not match release_authority.json'))
    if f'nicegui=={nicegui}' not in pyproject:
        findings.append(GovernanceFinding('release.nicegui-pin', 'pyproject.toml', f'nicegui must be pinned to {nicegui}'))

    json_targets = (
        'COMPATIBILITY.json',
        'FRAMEWORK_CATALOG.json',
        'AI_CONSTRUCTION_MANIFEST.json',
        'BUILD_ENV_RUNTIME_CONTRACT.json',
        'company_ui/runtime/compatibility.json',
        'company_ui/ai/framework_catalog.json',
        'company_ui/ai/construction_manifest.json',
        'company_ui/certification/certification_manifest.json',
    )
    for rel in json_targets:
        path = root / rel
        if not path.exists():
            findings.append(GovernanceFinding('release.missing-authority-copy', rel, 'required generated authority copy is missing'))
            continue
        data = _load(path)
        actual = data.get('framework_version')
        if actual != version:
            findings.append(GovernanceFinding('release.version-drift', rel, f'framework_version={actual!r}; expected {version!r}'))
        actual_nicegui = data.get('nicegui_version')
        if actual_nicegui is not None and actual_nicegui != nicegui:
            findings.append(GovernanceFinding('release.nicegui-drift', rel, f'nicegui_version={actual_nicegui!r}; expected {nicegui!r}'))

    current_text_targets = (
        'docs/RUNTIME_COMPATIBILITY_GUIDE.md',
        'docs/COMPANY_CERTIFICATION_CHECKLIST.md',
        'docs/V2_PUBLIC_API_POLICY.md',
        'docs/PUBLIC_API_INDEX.md',
        'company_ui/ai/guides/AGENTS.md',
        'company_ui/ai/guides/RUNTIME_COMPATIBILITY_GUIDE.md',
        'company_ui/ai/guides/COMPANY_CERTIFICATION_CHECKLIST.md',
        'company_ui/ai/guides/PUBLIC_API_INDEX.md',
        'mac_bundle/README.md', 'mac_bundle/setup_mac.sh',
        'linux_bundle/README.md', 'linux_bundle/setup_linux.sh',
    )
    for rel in current_text_targets:
        path = root / rel
        if not path.exists():
            findings.append(GovernanceFinding('release.missing-current-text', rel, 'current release-facing text is missing'))
            continue
        text = path.read_text(encoding='utf-8')
        if version not in text:
            findings.append(GovernanceFinding('release.current-text-drift', rel, f'current release-facing text does not identify {version}'))

    pairs = (
        ('FRAMEWORK_CATALOG.json', 'company_ui/ai/framework_catalog.json'),
        ('AI_CONSTRUCTION_MANIFEST.json', 'company_ui/ai/construction_manifest.json'),
        ('COMPATIBILITY.json', 'company_ui/runtime/compatibility.json'),
    )
    for left, right in pairs:
        if (root / left).exists() and (root / right).exists() and _load(root / left) != _load(root / right):
            findings.append(GovernanceFinding('release.copy-drift', f'{left} <> {right}', 'root/package authority copies differ'))

    return tuple(findings)
