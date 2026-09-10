from __future__ import annotations

"""Governed statistical-result boundary.

The browser remains the renderer for inline data.  Resource-backed analyses
are executed by the repository's existing JavaScript numerical authority over
the complete server-side population, then reduced to a bounded canonical
result for every consumer (Editor, preview, export, and refresh preflight).
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from .domain import VisualizerContractError, stable_json


STATISTICAL_RECIPE_IDS = frozenset({'xbar-r-process-review', 'process-capability', 'doe-response-review'})
_CLI = Path(__file__).with_name('assets') / 'statistical_analysis_cli.mjs'


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _filter_fingerprint(filters: Iterable[Any] = ()) -> str:
    normalized = []
    for clause in filters:
        normalized.append({
            'field': str(getattr(clause, 'field', '') or ''),
            'operation': str(getattr(getattr(clause, 'operation', None), 'value', getattr(clause, 'operation', '')) or ''),
            'value': getattr(clause, 'value', None),
            'value2': getattr(clause, 'value2', None),
            'filter_id': getattr(clause, 'filter_id', None),
        })
    encoded = stable_json(normalized).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _error_result(recipe_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        'ok': False,
        'analysis_type': recipe_id,
        'statistical_semantic_version': 'statistical-v1',
        'derived_mapping': {},
        'analysis_rows': [],
        'summary': {},
        'derived_statistics': {},
        'renderer_ready': {'dataset': {'fields': [], 'rows': []}},
        'warnings': [],
        'errors': [{'code': code, 'message': message}],
        'provenance_text': '',
    }


def _run_authority(dataset: Mapping[str, Any], requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node = shutil.which('node')
    if not node:
        return [_error_result(str(request.get('recipe_id') or ''), 'ANALYSIS_RUNTIME', 'Authoritative statistical runtime is unavailable.') for request in requests]
    payload = {'dataset': {'fields': _clone(dataset.get('fields') or []), 'rows': _clone(dataset.get('rows') or [])}, 'analyses': requests}
    try:
        completed = subprocess.run(
            [node, str(_CLI)],
            input=stable_json(payload),
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        )
        value = json.loads(completed.stdout)
        if not isinstance(value, list) or len(value) != len(requests):
            raise ValueError('statistical runtime returned an invalid result set')
        return [dict(item) if isinstance(item, Mapping) else _error_result(str(request.get('recipe_id') or ''), 'ANALYSIS_RUNTIME', 'Authoritative statistical runtime returned an invalid result.') for request, item in zip(requests, value)]
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        message = f'Authoritative statistical analysis failed: {exc}'
        return [_error_result(str(request.get('recipe_id') or ''), 'ANALYSIS_RUNTIME', message) for request in requests]


def _decorate(result: Mapping[str, Any], request: Mapping[str, Any], *, report_id: str, dataset_id: str,
              resource_id: str, revision: int, session_id: str, filters: Iterable[Any], source_total: int,
              filtered_total: int, analyzed_rows: int, complete: bool) -> dict[str, Any]:
    value = _clone(dict(result))
    recipe_id = str(request.get('recipe_id') or '')
    provenance = {
        'analysis_id': str(request.get('analysis_id') or recipe_id),
        'analysis_type': recipe_id,
        'statistical_semantic_version': value.get('statistical_semantic_version') or 'statistical-v1',
        'report_id': report_id,
        'dataset_id': dataset_id,
        'resource_id': resource_id,
        'dataset_revision': int(revision),
        'session_id': session_id,
        'filter_fingerprint': _filter_fingerprint(filters),
        'source_total': int(source_total),
        'filtered_total': int(filtered_total),
        'analyzed_rows': int(analyzed_rows),
        'complete': bool(complete),
        'mapping': _clone(request.get('mapping') or {}),
        'options': _clone(request.get('options') or {}),
        'semantic_provenance': str(value.pop('provenance_text') or ''),
    }
    value.update({
        'analysis_id': provenance['analysis_id'],
        'analysis_type': recipe_id,
        'statistical_semantic_version': provenance['statistical_semantic_version'],
        'mapping': _clone(request.get('mapping') or {}),
        'source_mapping': _clone(request.get('mapping') or {}),
        'provenance': provenance,
        'population': {key: provenance[key] for key in ('source_total', 'filtered_total', 'analyzed_rows', 'complete')},
        'source': {key: provenance[key] for key in ('report_id', 'dataset_id', 'resource_id', 'dataset_revision')},
        'session': {key: provenance[key] for key in ('session_id', 'filter_fingerprint')},
        'assumptions': {'mapping': _clone(request.get('mapping') or {}), 'options': _clone(request.get('options') or {})},
    })
    if not complete:
        value['ok'] = False
        value['derived_statistics'] = {}
        value['renderer_ready'] = {'dataset': {'fields': [], 'rows': []}}
        value.setdefault('errors', []).insert(0, {'code': 'INCOMPLETE_POPULATION', 'message': 'Authoritative statistical analysis requires the complete filtered population.'})
    return value


def analyze_statistical_items(*, report_id: str, dataset_id: str, resource_id: str, revision: int,
                              fields: list[Mapping[str, Any]], rows: list[list[Any]], items: Iterable[Mapping[str, Any]],
                              session_id: str, filters: Iterable[Any] = (), source_total: int | None = None,
                              filtered_total: int | None = None, complete: bool = True) -> dict[str, dict[str, Any]]:
    requests = []
    for item in items:
        recipe = item.get('analysis_recipe') if isinstance(item, Mapping) else None
        recipe_id = str(recipe.get('id') or '') if isinstance(recipe, Mapping) else ''
        if recipe_id not in STATISTICAL_RECIPE_IDS:
            continue
        requests.append({
            'analysis_id': str(item.get('analysis_id') or item.get('id') or recipe_id),
            'recipe_id': recipe_id,
            'mapping': _clone(recipe.get('mapping') or item.get('mapping') or {}),
            'options': _clone(item.get('capability_overrides') or {}),
            'item_id': str(item.get('id') or ''),
        })
    if not requests:
        return {}
    source_count = len(rows) if source_total is None else int(source_total)
    filtered_count = len(rows) if filtered_total is None else int(filtered_total)
    raw_results = _run_authority({'fields': fields, 'rows': rows}, requests)
    output = {}
    for request, result in zip(requests, raw_results):
        decorated = _decorate(result, request, report_id=report_id, dataset_id=dataset_id, resource_id=resource_id,
                              revision=revision, session_id=session_id, filters=filters, source_total=source_count,
                              filtered_total=filtered_count, analyzed_rows=len(rows), complete=complete and len(rows) == filtered_count)
        output[request['item_id']] = decorated
    return output


def first_analysis_error(results: Mapping[str, Mapping[str, Any]]) -> str | None:
    for result in results.values():
        if result.get('ok') is not True:
            errors = result.get('errors') or []
            if errors and isinstance(errors[0], Mapping):
                return str(errors[0].get('message') or 'Analysis needs attention.')
            return 'Analysis needs attention: the statistical contract is not satisfied.'
    return None


def require_valid_statistical_results(results: Mapping[str, Mapping[str, Any]]) -> None:
    message = first_analysis_error(results)
    if message:
        raise VisualizerContractError(message)


__all__ = ['STATISTICAL_RECIPE_IDS', 'analyze_statistical_items', 'first_analysis_error', 'require_valid_statistical_results']
