from __future__ import annotations

import json
from importlib.resources import files


def _load_release_authority() -> dict[str, object]:
    path = files('company_ui').joinpath('release_authority.json')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise RuntimeError('release_authority.json must contain an object')
    return payload


RELEASE_AUTHORITY = _load_release_authority()
FRAMEWORK_VERSION = str(RELEASE_AUTHORITY['framework_version'])
NICEGUI_VERSION = str(RELEASE_AUTHORITY['nicegui_version'])
RELEASE_STATUS = str(RELEASE_AUTHORITY['release_status'])

__all__ = ['RELEASE_AUTHORITY', 'FRAMEWORK_VERSION', 'NICEGUI_VERSION', 'RELEASE_STATUS']
