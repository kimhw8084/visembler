from __future__ import annotations

"""Durable, report-scoped dataset resources for Visembler.

Small datasets remain inline in the report model.  This module owns the
external path for recurring or large data without introducing a second data
engine: revisions are file-backed and queries are executed by the existing
``company_ui.data_engine`` primitives.
"""

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Mapping

from company_ui.data_engine import Aggregation, DataSession, Dataset, Dimension, Metric
from .domain import ReportNotFoundError, VisualizerContractError, stable_json
from .governance import REPORT_EDIT, REPORT_READ, ScopedReportRepository


DATASET_SCHEMA_VERSION = 1
MAX_DATASET_ROWS = 500_000
MAX_DATASET_FIELDS = 256
MAX_DATASET_BYTES = 50_000_000
PREVIEW_ROWS = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dataset_id(value: str) -> str:
    text = str(value or '').strip()
    if not text or len(text) > 96 or any(char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for char in text):
        raise VisualizerContractError('invalid dataset resource id')
    return text


def _fingerprint(fields: list[dict[str, Any]], rows: list[list[Any]]) -> str:
    return hashlib.sha256(stable_json({'fields': fields, 'rows': rows}).encode('utf-8')).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _validate_fields(fields: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, Mapping):
            raise VisualizerContractError('dataset fields must be objects')
        field_id = str(field.get('id') or '').strip()
        name = str(field.get('name') or field_id).strip()
        if not field_id or not name or field_id in seen:
            raise VisualizerContractError('dataset fields require unique id and name')
        seen.add(field_id)
        clean = {str(key): _copy(value) for key, value in field.items() if str(key) in {'id', 'name', 'type', 'nullable', 'semantic_tags', 'unit', 'profile'}}
        clean.update({'id': field_id, 'name': name, 'type': str(field.get('type') or 'unknown')})
        result.append(clean)
        if len(result) > MAX_DATASET_FIELDS:
            raise VisualizerContractError(f'dataset supports at most {MAX_DATASET_FIELDS} fields')
    if not result:
        raise VisualizerContractError('dataset requires at least one field')
    return result


def _validate_rows(rows: Iterable[Iterable[Any]], width: int) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in rows:
        if isinstance(row, (str, bytes, bytearray)):
            raise VisualizerContractError('dataset rows must be arrays')
        values = list(row)
        if len(values) != width:
            raise VisualizerContractError('dataset rows must match the field count')
        result.append(_copy(values))
        if len(result) > MAX_DATASET_ROWS:
            raise VisualizerContractError(f'dataset supports at most {MAX_DATASET_ROWS:,} rows')
    return result


class DatasetResourceStore:
    """Atomic revision store whose catalog is rebuildable from revision files."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.directory = self.root / '_datasets'
        self.catalog_path = self.directory / 'catalog.json'
        self.lock_path = self.directory / '.datasets.lock'
        self._lock = RLock()
        self.directory.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _transaction(self):
        with self._lock:
            handle = self.lock_path.open('a+b')
            try:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except ImportError:  # pragma: no cover - Windows fallback
                    pass
                yield
            finally:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except ImportError:  # pragma: no cover
                    pass
                handle.close()

    def _read_catalog_unlocked(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {'schema_version': DATASET_SCHEMA_VERSION, 'resources': {}}
        try:
            value = json.loads(self.catalog_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise VisualizerContractError('dataset catalog is corrupt') from exc
        if value.get('schema_version') != DATASET_SCHEMA_VERSION or not isinstance(value.get('resources'), Mapping):
            raise VisualizerContractError('unsupported dataset catalog')
        return value

    def _write_atomic_unlocked(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = stable_json(value) + '\n'
        if len(payload.encode('utf-8')) > MAX_DATASET_BYTES + 2_000_000:
            raise VisualizerContractError('dataset resource exceeds the configured storage limit')
        fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            try:
                directory_fd = os.open(path.parent, os.O_DIRECTORY)
                os.fsync(directory_fd)
                os.close(directory_fd)
            except (AttributeError, OSError):  # pragma: no cover - platform fallback
                pass
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _resource_path(self, resource_id: str, revision: int) -> Path:
        return self.directory / _dataset_id(resource_id) / f'r{int(revision)}.json'

    @staticmethod
    def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
        return {key: _copy(record.get(key)) for key in (
            'dataset_id', 'resource_id', 'owner', 'name', 'description', 'schema',
            'row_count', 'provenance', 'source_metadata', 'revision',
            'content_fingerprint', 'created_at', 'modified_at', 'state',
        )}

    def create(self, *, owner: str, name: str, fields: Iterable[Mapping[str, Any]], rows: Iterable[Iterable[Any]],
               description: str = '', provenance: str = '', source_metadata: Mapping[str, Any] | None = None,
               dataset_id: str | None = None) -> dict[str, Any]:
        owner = ' '.join(str(owner or '').split())
        if not owner:
            raise VisualizerContractError('dataset owner is required')
        clean_fields = _validate_fields(fields)
        clean_rows = _validate_rows(rows, len(clean_fields))
        resource_id = _dataset_id(dataset_id or f'dataset-{uuid.uuid4().hex}')
        summary = {
            'dataset_id': resource_id,
            'resource_id': uuid.uuid4().hex,
            'owner': owner,
            'name': ' '.join(str(name or '').replace('\x00', '').split())[:160] or 'Untitled dataset',
            'description': ' '.join(str(description or '').replace('\x00', '').split())[:500],
            'schema': clean_fields,
            'row_count': len(clean_rows),
            'provenance': ' '.join(str(provenance or '').replace('\x00', '').split())[:500],
            'source_metadata': _copy(dict(source_metadata or {})),
            'revision': 1,
            'content_fingerprint': _fingerprint(clean_fields, clean_rows),
            'created_at': _now(),
            'modified_at': _now(),
            'state': 'active',
        }
        revision = {'dataset_id': resource_id, 'revision': 1, 'fields': clean_fields, 'rows': clean_rows,
                    'content_fingerprint': summary['content_fingerprint'], 'created_at': summary['modified_at']}
        with self._transaction():
            catalog = self._read_catalog_unlocked()
            if resource_id in catalog['resources']:
                raise VisualizerContractError(f'dataset resource already exists: {resource_id}')
            self._write_atomic_unlocked(self._resource_path(resource_id, 1), revision)
            catalog['resources'][resource_id] = summary
            self._write_atomic_unlocked(self.catalog_path, catalog)
        return self._summary(summary)

    def summary(self, resource_id: str) -> dict[str, Any]:
        resource_id = _dataset_id(resource_id)
        with self._transaction():
            record = self._read_catalog_unlocked()['resources'].get(resource_id)
            if not isinstance(record, Mapping) or record.get('state') != 'active':
                raise ReportNotFoundError(resource_id)
            return self._summary(record)

    def list_summaries(self) -> list[dict[str, Any]]:
        with self._transaction():
            records = [self._summary(value) for value in self._read_catalog_unlocked()['resources'].values()
                       if isinstance(value, Mapping) and value.get('state') == 'active']
        return sorted(records, key=lambda value: (str(value.get('modified_at') or ''), str(value.get('dataset_id') or '')), reverse=True)

    def get(self, resource_id: str, *, revision: int | None = None) -> dict[str, Any]:
        summary = self.summary(resource_id)
        revision_number = int(revision or summary['revision'])
        path = self._resource_path(summary['dataset_id'], revision_number)
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError as exc:
            raise VisualizerContractError('dataset revision is missing') from exc
        except json.JSONDecodeError as exc:
            raise VisualizerContractError('dataset revision is corrupt') from exc
        if value.get('dataset_id') != summary['dataset_id'] or value.get('revision') != revision_number:
            raise VisualizerContractError('dataset revision identity mismatch')
        fields = _validate_fields(value.get('fields') or [])
        rows = _validate_rows(value.get('rows') or [], len(fields))
        if _fingerprint(fields, rows) != value.get('content_fingerprint'):
            raise VisualizerContractError('dataset revision fingerprint mismatch')
        return {**summary, 'revision': revision_number, 'schema': fields, 'fields': fields, 'row_count': len(rows),
                'content_fingerprint': value['content_fingerprint'], 'rows': rows}

    def preview(self, resource_id: str, *, revision: int | None = None, limit: int = PREVIEW_ROWS) -> dict[str, Any]:
        value = self.get(resource_id, revision=revision)
        value['rows'] = value['rows'][:max(1, min(int(limit), PREVIEW_ROWS))]
        return value

    def replace(self, resource_id: str, *, fields: Iterable[Mapping[str, Any]], rows: Iterable[Iterable[Any]],
                expected_revision: int | None = None, provenance: str | None = None,
                source_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        clean_fields = _validate_fields(fields)
        clean_rows = _validate_rows(rows, len(clean_fields))
        with self._transaction():
            catalog = self._read_catalog_unlocked()
            old = catalog['resources'].get(_dataset_id(resource_id))
            if not isinstance(old, Mapping) or old.get('state') != 'active':
                raise ReportNotFoundError(resource_id)
            current_revision = int(old.get('revision') or 0)
            if expected_revision is not None and current_revision != int(expected_revision):
                raise VisualizerContractError(f'stale dataset revision: expected {current_revision}, received {expected_revision}')
            next_revision = current_revision + 1
            fingerprint = _fingerprint(clean_fields, clean_rows)
            record = dict(old)
            record.update({'schema': clean_fields, 'row_count': len(clean_rows), 'revision': next_revision,
                           'content_fingerprint': fingerprint, 'modified_at': _now()})
            if provenance is not None: record['provenance'] = ' '.join(str(provenance).split())[:500]
            if source_metadata is not None: record['source_metadata'] = _copy(dict(source_metadata))
            revision = {'dataset_id': record['dataset_id'], 'revision': next_revision, 'fields': clean_fields,
                        'rows': clean_rows, 'content_fingerprint': fingerprint, 'created_at': record['modified_at']}
            self._write_atomic_unlocked(self._resource_path(record['dataset_id'], next_revision), revision)
            catalog['resources'][record['dataset_id']] = record
            self._write_atomic_unlocked(self.catalog_path, catalog)
            return self._summary(record)

    def delete(self, resource_id: str) -> None:
        with self._transaction():
            catalog = self._read_catalog_unlocked()
            record = catalog['resources'].get(_dataset_id(resource_id))
            if not isinstance(record, Mapping) or record.get('state') != 'active':
                raise ReportNotFoundError(resource_id)
            updated = dict(record)
            updated.update({'state': 'deleted', 'modified_at': _now()})
            catalog['resources'][updated['dataset_id']] = updated
            self._write_atomic_unlocked(self.catalog_path, catalog)

    def reconcile(self) -> dict[str, Any]:
        """Validate catalog/revision identity without guessing ownership."""
        with self._transaction():
            catalog = self._read_catalog_unlocked()
            blocked: list[str] = []
            for resource_id, record in catalog['resources'].items():
                if not isinstance(record, Mapping) or record.get('state') != 'active':
                    continue
                try:
                    revision = int(record.get('revision') or 0)
                    path = self._resource_path(str(resource_id), revision)
                except (TypeError, ValueError, VisualizerContractError):
                    path = None
                if path is None or not path.is_file():
                    updated = dict(record)
                    updated.update({'state': 'blocked', 'reason': 'active dataset revision is missing'})
                    catalog['resources'][resource_id] = updated
                    blocked.append(str(resource_id))
            if blocked:
                self._write_atomic_unlocked(self.catalog_path, catalog)
            known = set(str(value) for value in catalog['resources'])
            orphans = sorted(child.name for child in self.directory.iterdir()
                             if child.is_dir() and child.name not in known)
            return {'ok': not blocked, 'blocked': blocked, 'orphan_directories': orphans}

    def collect_garbage(self, referenced_ids: Iterable[str] = ()) -> list[str]:
        """Remove only tombstoned, unreferenced revisions.

        Tombstones remain in the catalog so a deleted dataset ID can never be
        reused accidentally. Callers must supply references from active,
        historical, and trash reports; omission is not permission to guess.
        """
        protected = {_dataset_id(value) for value in referenced_ids}
        removed: list[str] = []
        with self._transaction():
            catalog = self._read_catalog_unlocked()
            for resource_id, record in catalog['resources'].items():
                if not isinstance(record, Mapping) or record.get('state') != 'deleted':
                    continue
                if str(resource_id) in protected:
                    continue
                directory = self.directory / _dataset_id(str(resource_id))
                if directory.exists():
                    shutil.rmtree(directory)
                removed.append(str(resource_id))
            return removed

    def health(self) -> bool:
        result = self.reconcile()
        return bool(result['ok'] and not result['orphan_directories'])

    def session(self, resource_id: str, *, revision: int | None = None) -> DataSession:
        value = self.get(resource_id, revision=revision)
        revision_number = int(value.get('revision') or revision or 0)
        row_maps = [dict(zip((field['id'] for field in value['fields']), row)) for row in value['rows']]
        dimensions=tuple(Dimension(field['id'], label=field.get('name'), field=field['id']) for field in value['fields'])
        metrics=tuple(Metric(field['id'], label=field.get('name'), field=field['id'], aggregation=Aggregation.SUM)
                      for field in value['fields'] if field.get('type') in {'integer', 'number'})
        return DataSession(Dataset(value['resource_id'], row_maps, dimensions=dimensions, metrics=metrics, revision=revision_number))


class ScopedDatasetRepository:
    """Report-scoped dataset facade; resource IDs are never an access grant."""

    def __init__(self, store: DatasetResourceStore, reports: ScopedReportRepository):
        self._store = store
        self._reports = reports

    @staticmethod
    def _resource_refs(model: Mapping[str, Any]) -> dict[str, tuple[str, int | None]]:
        result = {}
        for dataset in model.get('datasets', ()) if isinstance(model, Mapping) else ():
            if isinstance(dataset, Mapping) and dataset.get('resource_id'):
                revision = dataset.get('revision')
                result[str(dataset.get('id'))] = (
                    str(dataset.get('resource_id')),
                    int(revision) if isinstance(revision, int) and not isinstance(revision, bool) else None,
                )
        return result

    def _require_reference(self, report_id: str, dataset_id: str, action: str = REPORT_READ) -> tuple[Any, str]:
        self._reports._require(report_id, action)
        report = self._reports.get(report_id)
        refs = self._resource_refs(report.model)
        resource_ref = refs.get(str(dataset_id))
        if resource_ref is None:
            raise ReportNotFoundError(dataset_id)
        return report, resource_ref[0], resource_ref[1]

    def get_for_report(self, report_id: str, dataset_id: str) -> dict[str, Any]:
        _, resource_id, revision = self._require_reference(report_id, dataset_id, REPORT_READ)
        return self._store.get(resource_id, revision=revision)

    def preview_for_report(self, report_id: str, dataset_id: str) -> dict[str, Any]:
        _, resource_id, revision = self._require_reference(report_id, dataset_id, REPORT_READ)
        return self._store.preview(resource_id, revision=revision)

    def session_for_report(self, report_id: str, dataset_id: str, *, revision: int | None = None) -> DataSession:
        _, resource_id, referenced_revision = self._require_reference(report_id, dataset_id, REPORT_READ)
        return self._store.session(resource_id, revision=revision if revision is not None else referenced_revision)

    def replace_for_report(self, report_id: str, dataset_id: str, *, fields: Iterable[Mapping[str, Any]],
                           rows: Iterable[Iterable[Any]], expected_revision: int | None = None,
                           provenance: str | None = None, source_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        _, resource_id, _ = self._require_reference(report_id, dataset_id, REPORT_EDIT)
        return self._store.replace(resource_id, fields=fields, rows=rows, expected_revision=expected_revision,
                                   provenance=provenance, source_metadata=source_metadata)

    def create_for_report(self, report_id: str, *, name: str, fields: Iterable[Mapping[str, Any]], rows: Iterable[Iterable[Any]],
                          description: str = '', provenance: str = '', source_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._reports._require(report_id, REPORT_EDIT)
        return self._store.create(owner=self._reports.principal.subject, name=name, fields=fields, rows=rows,
                                  description=description, provenance=provenance, source_metadata=source_metadata)

    def list_visible(self) -> list[dict[str, Any]]:
        # Ownership is an independent visibility scope.  Referenced resources
        # are visible only through reports the principal can already read.
        owned = [value for value in self._store.list_summaries() if value.get('owner') == self._reports.principal.subject]
        referenced: set[str] = set()
        for summary in self._reports.list_summaries():
            if isinstance(summary.get('dataset_refs'), list):
                referenced.update(str(value) for value in summary['dataset_refs'])
            elif summary.get('report_id'):
                # Older governance summaries predate dataset_refs.  This
                # compatibility path is bounded to those legacy entries and
                # disappears after the next governance summary rebuild.
                try:
                    report=self._reports.get(str(summary['report_id']))
                    referenced.update(resource_id for resource_id, _ in self._resource_refs(report.model).values())
                except (PermissionError, ReportNotFoundError):
                    continue
        visible = {str(value['dataset_id']): value for value in owned}
        for value in self._store.list_summaries():
            if value.get('dataset_id') in referenced:
                visible[str(value['dataset_id'])] = value
        return sorted(visible.values(), key=lambda value: (str(value.get('modified_at') or ''), str(value.get('dataset_id') or '')), reverse=True)

    def delete_for_report(self, report_id: str, dataset_id: str) -> None:
        _, resource_id, _ = self._require_reference(report_id, dataset_id, 'report.delete')
        for other in self._reports._repository.list() + self._reports._repository.list_trash():
            if resource_id in {value[0] for value in self._resource_refs(other.model).values()}:
                raise VisualizerContractError('dataset is still referenced by a report')
        self._store.delete(resource_id)

    def hydrate_model(self, report_id: str, model: Mapping[str, Any]) -> dict[str, Any]:
        self._reports._require(report_id, REPORT_READ)
        hydrated = _copy(model)
        for dataset in hydrated.get('datasets', ()):
            if not isinstance(dataset, dict) or not dataset.get('resource_id'):
                continue
            preview = self.preview_for_report(report_id, str(dataset.get('id')))
            dataset.update({'fields': preview['fields'], 'rows': preview['rows'], 'revision': preview['revision'],
                            'row_count': preview['row_count'], 'content_fingerprint': preview['content_fingerprint'],
                            'external': True})
        return hydrated


__all__ = ['DATASET_SCHEMA_VERSION', 'DatasetResourceStore', 'ScopedDatasetRepository', 'PREVIEW_ROWS']
