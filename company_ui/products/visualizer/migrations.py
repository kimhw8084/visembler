from __future__ import annotations

"""Canonical report-model migration authority.

The browser may still normalize defensively for compatibility, but persisted
report models pass through this deterministic chain before validation.  Version
zero represents the pre-contract authoring payloads that existed before the
canonical v1 envelope was introduced.
"""

import json
from typing import Any, Mapping


CURRENT_REPORT_MODEL_VERSION = 1
SUPPORTED_REPORT_MODEL_VERSIONS = frozenset({0, 1})


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def migrate_v0_to_v1(value: Mapping[str, Any]) -> dict[str, Any]:
    source = _clone(dict(value))
    source['schema_version'] = 1
    source.setdefault('authoring_schema', 'authoring-p0-v1')
    source.setdefault('datasets', [])
    source.setdefault('items', [])
    source.setdefault('groups', {})
    source.setdefault('mode', 'guided')
    source.setdefault('layoutPreset', 'editorial')
    source.setdefault('crossFilter', None)
    source.setdefault('canvas', {'width': 1600, 'height': 900})
    source.setdefault('nextId', 20)
    return source


def migrate_report_model(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    version = source.get('schema_version', 0)
    if isinstance(version, bool) or not isinstance(version, int) or version not in SUPPORTED_REPORT_MODEL_VERSIONS:
        raise ValueError(f'unsupported report model schema_version {version!r}')
    if version == 0:
        source = migrate_v0_to_v1(source)
    # Keep this explicit even while v1 is current so the next persisted schema
    # change has one obvious insertion point and a testable chain.
    if source.get('schema_version') != CURRENT_REPORT_MODEL_VERSION:
        raise ValueError(f'report migration did not reach version {CURRENT_REPORT_MODEL_VERSION}')
    return source


__all__ = ['CURRENT_REPORT_MODEL_VERSION', 'SUPPORTED_REPORT_MODEL_VERSIONS', 'migrate_report_model', 'migrate_v0_to_v1']
