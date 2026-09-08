from __future__ import annotations

"""Visembler's small, durable resource-governance boundary.

The report JSON remains the canonical document.  This module owns the security
metadata which cannot safely be reconstructed from a report (owner, grants,
resource identity, lifecycle state, and audit records).  Request handlers use
``ScopedReportRepository`` rather than the raw repository so authorization is
centralized and duplicate/asset/history paths cannot accidentally bypass it.
"""

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from enum import StrEnum
from typing import Any, Iterable, Iterator, Mapping, Protocol

from company_ui.diagnostics import get_correlation_id
from company_ui.security import AuthorizationModel, Principal

from .domain import ReportNotFoundError, RevisionConflictError, VisualizerContractError, canonical_model, stable_json, utc_now, validate_report_id
from .repository import ReportRepository


CAPABILITY_ACTIONS = (
    'report.read', 'report.edit', 'report.rename', 'report.duplicate',
    'report.share', 'report.delete', 'report.restore', 'report.history.read',
    'report.history.restore', 'report.export',
)
GLOBAL_CREATE = 'report.create'
GLOBAL_ADMIN = 'administration'
REPORT_READ, REPORT_CREATE, REPORT_EDIT, REPORT_RENAME, REPORT_DUPLICATE, REPORT_SHARE, REPORT_DELETE, REPORT_RESTORE, HISTORY_READ, HISTORY_RESTORE, REPORT_EXPORT = (
    'report.read', 'report.create', 'report.edit', 'report.rename', 'report.duplicate',
    'report.share', 'report.delete', 'report.restore', 'report.history.read',
    'report.history.restore', 'report.export',
)
ADMINISTRATION = GLOBAL_ADMIN


class ReportRole(StrEnum):
    OWNER = 'owner'
    EDITOR = 'editor'
    VIEWER = 'viewer'


_ROLES = {'owner', 'editor', 'viewer'}
_ROLE_ACTIONS = {
    'owner': frozenset(CAPABILITY_ACTIONS),
    'editor': frozenset({'report.read', 'report.edit', 'report.rename', 'report.duplicate', 'report.history.read', 'report.history.restore', 'report.export'}),
    'viewer': frozenset({'report.read', 'report.history.read', 'report.export'}),
}
OWNER_ACTIONS = frozenset(CAPABILITY_ACTIONS)
EDITOR_ACTIONS = _ROLE_ACTIONS['editor']
VIEWER_ACTIONS = _ROLE_ACTIONS['viewer']


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CapabilityProjection:
    report_id: str
    role: str | None
    can_read: bool
    can_edit: bool
    can_rename: bool
    can_duplicate: bool
    can_share: bool
    can_delete: bool
    can_restore: bool
    can_read_history: bool
    can_restore_history: bool
    can_export: bool

    @property
    def read_only(self) -> bool:
        return self.can_read and not self.can_edit

    def to_dict(self) -> dict[str, Any]:
        return {
            'report_id': self.report_id, 'role': self.role,
            'can_read': self.can_read, 'can_edit': self.can_edit,
            'can_rename': self.can_rename, 'can_duplicate': self.can_duplicate,
            'can_share': self.can_share, 'can_delete': self.can_delete,
            'can_restore': self.can_restore, 'can_read_history': self.can_read_history,
            'can_restore_history': self.can_restore_history, 'can_export': self.can_export,
            'read_only': self.read_only,
        }


class IdentityDirectoryResolver(Protocol):
    def resolve(self, value: str) -> 'IdentityReference | None': ...


@dataclass(frozen=True, slots=True)
class IdentityReference:
    subject: str
    display_name: str | None = None
    email: str | None = None


class GovernanceRecord(dict[str, Any]):
    """Mapping-compatible record with the legacy owner_subject view."""

    def __getattr__(self, name: str) -> Any:
        if name == 'owner_subject':
            return self.get('owner')
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class ExactSubjectIdentityResolver:
    """Deterministic dev/test resolver; production may provide a directory adapter."""

    def resolve(self, value: str) -> IdentityReference | None:
        subject = ' '.join(str(value).split())
        return IdentityReference(subject) if subject else None


class AuditTrail:
    def __init__(self, path: str | Path, *, max_bytes: int | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(1024, int(max_bytes or os.environ.get('COMPANY_UI_AUDIT_MAX_BYTES', 10_000_000)))
        self._lock = RLock()

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size <= self.max_bytes:
            return
        rotated = self.path.with_name(self.path.name + '.1')
        try:
            rotated.unlink()
        except FileNotFoundError:
            pass
        os.replace(self.path, rotated)

    def record(self, action: str, *, actor: Principal | None, report_id: str | None = None,
               outcome: str = 'success', reason: str | None = None,
               revision: int | None = None) -> dict[str, Any]:
        event = {
            'timestamp': _now(), 'actor_subject': actor.subject if actor and actor.authenticated else 'anonymous',
            'action': action, 'report_id': report_id, 'revision': revision,
            'correlation_id': get_correlation_id(), 'outcome': outcome,
        }
        if reason:
            event['reason'] = ' '.join(str(reason).split())[:240]
        with self._lock:
            self._rotate_if_needed()
            with self.path.open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(stable_json(event) + '\n')
                handle.flush(); os.fsync(handle.fileno())
        return event

    def read(self, *, report_id: str | None = None) -> list[dict[str, Any]]:
        paths = [self.path.with_name(self.path.name + '.1'), self.path]
        result: list[dict[str, Any]] = []
        for path in paths:
            if not path.is_file():
                continue
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if report_id is None or event.get('report_id') == report_id:
                    result.append(event)
        return result


class ReportAccessCatalog:
    VERSION = 1

    def __init__(self, root: str | Path | ReportRepository):
        self.repository = root if isinstance(root, ReportRepository) else None
        self.root = (root.root if isinstance(root, ReportRepository) else Path(root)).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / '_governance.json'
        self.lock_path = self.root / '.governance.lock'
        self.audit = AuditTrail(self.root / 'audit.jsonl')
        self._lock = RLock()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            handle = self.lock_path.open('a+b')
            try:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                except ImportError:  # pragma: no cover
                    pass
                yield
            finally:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except ImportError:  # pragma: no cover
                    pass
                handle.close()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {'schema_version': 1, 'resources': {}}

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise VisualizerContractError('governance catalog is corrupt') from exc
        if value.get('schema_version') != self.VERSION or not isinstance(value.get('resources'), Mapping):
            raise VisualizerContractError('unsupported governance catalog')
        return value

    def _write_unlocked(self, value: Mapping[str, Any]) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix='.governance.', suffix='.tmp', dir=self.root)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(stable_json(value) + '\n'); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            try:
                fd = os.open(self.root, os.O_DIRECTORY); os.fsync(fd); os.close(fd)
            except (AttributeError, OSError):
                pass
        finally:
            try: os.unlink(tmp_name)
            except FileNotFoundError: pass

    def _record_unlocked(self, value: dict[str, Any], report_id: str) -> dict[str, Any]:
        return value['resources'].setdefault(report_id, {})

    def _state(self, record: Mapping[str, Any], state: str) -> None:
        record['state'] = state
        record['state_changed_at'] = _now()

    def _new_record(self, report_id: str, owner: str) -> dict[str, Any]:
        if not owner or not owner.strip():
            raise VisualizerContractError('resource owner is required')
        return {
            'report_id': validate_report_id(report_id), 'resource_id': uuid.uuid4().hex,
            'generation': 1, 'owner': owner.strip(), 'grants': {}, 'state': 'creating',
            'created_at': _now(), 'state_changed_at': _now(),
        }

    def assert_new_identity(self, report_id: str) -> None:
        report_id = validate_report_id(report_id)
        with self._transaction():
            value = self._read_unlocked()
            if report_id in value['resources'] or (self.root / f'{report_id}.json').exists() or (self.root / '_trash' / f'{report_id}.json').exists():
                raise VisualizerContractError(f'report already exists or is reserved: {report_id}')

    def begin_create(self, report_id: str, owner: str) -> None:
        with self._transaction():
            value = self._read_unlocked()
            if report_id in value['resources'] or (self.root / f'{report_id}.json').exists() or (self.root / '_trash' / f'{report_id}.json').exists():
                raise VisualizerContractError(f'report already exists or is reserved: {report_id}')
            value['resources'][validate_report_id(report_id)] = self._new_record(report_id, owner)
            self._write_unlocked(value)

    def mark_active(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record or not record.get('owner'): raise VisualizerContractError('governance record is unavailable')
            self._state(record, 'active'); self._write_unlocked(value)

    def begin_trash(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record or record.get('state') != 'active': raise VisualizerContractError('report is not active')
            self._state(record, 'trashing'); self._write_unlocked(value)

    def mark_trashed(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record: raise VisualizerContractError('governance record is unavailable')
            self._state(record, 'trashed'); self._write_unlocked(value)

    def begin_delete(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record or record.get('state') not in {'active', 'trashed'}: raise VisualizerContractError('report is not deletable')
            self._state(record, 'deleting'); self._write_unlocked(value)

    def mark_deleted(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record: raise VisualizerContractError('governance record is unavailable')
            record['owner'] = record.get('owner') or 'deleted-resource'; record['grants'] = {}
            self._state(record, 'deleted'); self._write_unlocked(value)

    def migrate(self, report_ids: list[str] | Iterable[Any], *, owner: str | None = None, production: bool = False,
                trashed_ids: set[str] | None = None, owner_subject: str | None = None,
                require_explicit_owner: bool | None = None) -> int | dict[str, int]:
        legacy_contract = owner_subject is not None or require_explicit_owner is not None
        if owner is None: owner = owner_subject
        if require_explicit_owner is not None: production = require_explicit_owner
        ids = [str(getattr(record, 'report_id', record)) for record in report_ids]
        selected = owner or 'local-dev'; trashed_ids = trashed_ids or set()
        created = 0
        with self._transaction():
            value = self._read_unlocked()
            for report_id in ids:
                report_id = validate_report_id(report_id)
                if report_id in value['resources']:
                    continue
                if production and not owner:
                    raise VisualizerContractError('COMPANY_UI_MIGRATION_OWNER_SUBJECT is required for production governance migration')
                state = 'trashed' if report_id in trashed_ids else 'active'
                value['resources'][report_id] = {**self._new_record(report_id, selected), 'state': state}
                created += 1
            if created: self._write_unlocked(value)
        return {'examined': len(ids), 'existing': len(ids) - created, 'migrated': created} if legacy_contract else created

    def reconcile(self) -> dict[str, Any]:
        """Reconcile files and governance without guessing ownership.

        Missing governance never becomes an implicitly owned resource.  It is
        recorded as blocked, which prevents exposure until an operator repairs
        the catalog explicitly.
        """
        with self._transaction():
            value = self._read_unlocked(); resources = value['resources']; blocked = []; changed = False
            active_ids = {path.stem for path in self.root.glob('*.json') if path.name != self.path.name}
            trash_dir = self.root / '_trash'
            trash_ids = {path.stem for path in trash_dir.glob('*.json')} if trash_dir.exists() else set()
            for report_id in sorted(active_ids | trash_ids | set(resources)):
                record = resources.get(report_id)
                if record is None:
                    resources[report_id] = {'report_id': report_id, 'resource_id': uuid.uuid4().hex, 'generation': 1, 'owner': '', 'grants': {}, 'state': 'blocked', 'created_at': _now(), 'state_changed_at': _now(), 'reason': 'orphan report without governance'}
                    blocked.append(report_id); changed = True; continue
                state = record.get('state')
                if report_id in active_ids and report_id in trash_ids:
                    self._state(record, 'blocked'); record['reason'] = 'active and trash copies coexist'; blocked.append(report_id); changed = True
                elif state == 'creating' and report_id in active_ids:
                    self._state(record, 'active'); changed = True
                elif state == 'creating':
                    self._state(record, 'aborted'); record['reason'] = 'interrupted create'; changed = True
                elif state == 'trashing':
                    if report_id in active_ids:
                        self._state(record, 'active'); changed = True
                    elif report_id in trash_ids:
                        self._state(record, 'trashed'); changed = True
                    else:
                        self._state(record, 'blocked'); record['reason'] = 'interrupted trash with no durable report'; blocked.append(report_id); changed = True
                elif state == 'trashed' and report_id in active_ids and report_id not in trash_ids:
                    # Restore's file move is atomic; a crash before governance
                    # finalization leaves a valid active file and a trashed
                    # governance state.  Complete that deterministic transition.
                    self._state(record, 'active'); changed = True
                elif state == 'deleting' and (report_id in active_ids or report_id in trash_ids):
                    self._state(record, 'blocked'); record['reason'] = 'interrupted delete'; blocked.append(report_id); changed = True
                elif state == 'deleting':
                    record['grants'] = {}; self._state(record, 'deleted'); changed = True
                elif state in {'deleted', 'aborted', 'blocked'} and (report_id in active_ids or report_id in trash_ids):
                    self._state(record, 'blocked'); record['reason'] = 'terminal governance state has a report file'; blocked.append(report_id); changed = True
                elif state == 'active' and report_id not in active_ids:
                    self._state(record, 'blocked'); record['reason'] = 'active governance without report'; blocked.append(report_id); changed = True
                if not record.get('owner') and record.get('state') not in {'deleted', 'aborted'}:
                    self._state(record, 'blocked'); record['reason'] = 'missing owner'; blocked.append(report_id); changed = True
            if changed or active_ids or trash_ids:
                self._write_unlocked(value)
            return {'blocked': sorted(set(blocked)), 'active': len(active_ids), 'trash': len(trash_ids)}

    def get(self, report_id: str) -> dict[str, Any]:
        with self._transaction():
            record = self._read_unlocked()['resources'].get(validate_report_id(report_id))
            if not record: raise ReportNotFoundError(report_id)
            return GovernanceRecord(json.loads(json.dumps(record)))

    def has(self, report_id: str) -> bool:
        try:
            self.get(report_id)
            return True
        except ReportNotFoundError:
            return False

    def ensure_owner(self, report_id: str, owner_subject: str) -> dict[str, Any]:
        if self.has(report_id): return self.get(report_id)
        self.begin_create(report_id, owner_subject)
        self.mark_active(report_id)
        return self.get(report_id)

    def create(self, report_id: str, owner_subject: str) -> dict[str, Any]:
        record = self.ensure_owner(report_id, owner_subject)
        self.audit.record('report.create', actor=Principal(owner_subject), report_id=report_id)
        return record

    def delete(self, report_id: str) -> None:
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if record:
                record['owner'] = record.get('owner') or 'deleted-resource'; record['grants'] = {}
                self._state(record, 'deleted'); self._write_unlocked(value)

    def health(self) -> bool:
        return self.root.is_dir() and os.access(self.root, os.R_OK | os.W_OK) and self.audit.path.parent.is_dir()

    def _role_name(self, record: Mapping[str, Any], principal: Principal) -> str | None:
        projection = self._capabilities_for_record(record, principal, AuthorizationModel())
        return projection.role

    def can(self, report_id: str, principal: Principal, action: str) -> bool:
        try:
            record = self.get(report_id)
        except ReportNotFoundError:
            return False
        if action == REPORT_CREATE: return False
        projection = self._capabilities_for_record(record, principal, AuthorizationModel())
        return bool(getattr(projection, {
            REPORT_READ: 'can_read', REPORT_EDIT: 'can_edit', REPORT_RENAME: 'can_rename',
            REPORT_DUPLICATE: 'can_duplicate', REPORT_SHARE: 'can_share', REPORT_DELETE: 'can_delete',
            REPORT_RESTORE: 'can_restore', HISTORY_READ: 'can_read_history',
            HISTORY_RESTORE: 'can_restore_history', REPORT_EXPORT: 'can_export',
        }.get(action, 'never'), False))

    def require(self, report_id: str, principal: Principal, action: str) -> None:
        if self.can(report_id, principal, action): return
        self.audit.record(action, actor=principal, report_id=report_id, outcome='denied', reason='resource access denied')
        raise PermissionError('resource access denied')

    def require_global(self, principal: Principal, action: str, authorization: AuthorizationModel) -> None:
        effective = authorization.effective_permissions(principal)
        if principal.authenticated and (action in effective or GLOBAL_ADMIN in effective or 'visembler.admin' in principal.roles): return
        self.audit.record(action, actor=principal, outcome='denied', reason='global permission denied')
        raise PermissionError('access denied')

    def grant(self, report_id: str, actor: Principal, subject: str, role: ReportRole, *, group: bool = False) -> dict[str, Any]:
        self.require(report_id, actor, REPORT_SHARE)
        value = str(subject or '').strip()
        if not value or role is ReportRole.OWNER: raise VisualizerContractError('a valid non-owner share target and role are required')
        result = self.update_grant(report_id, f'group:{value}' if group else value, str(role.value))
        self.audit.record('report.share.grant', actor=actor, report_id=report_id, reason=str(role.value))
        return result

    def revoke(self, report_id: str, actor: Principal, subject: str, *, group: bool = False) -> dict[str, Any]:
        self.require(report_id, actor, REPORT_SHARE)
        result = self.update_grant(report_id, f'group:{str(subject or "").strip()}' if group else str(subject or '').strip(), None)
        self.audit.record('report.share.revoke', actor=actor, report_id=report_id, reason='revoked')
        return result

    def accessible(self, records: Iterable[Any], principal: Principal, action: str = REPORT_READ) -> list[Any]:
        return [record for record in records if self.can(str(record.report_id), principal, action)]

    def can_read_asset(self, asset_id: str, principal: Principal) -> bool:
        if self.repository is None: return False
        for record in self.accessible(self.repository.list(), principal, REPORT_READ):
            if any(isinstance(item, Mapping) and item.get('asset_id') == asset_id for item in record.model.get('items', ())): return True
        return False

    def access_summary(self, report_id: str, principal: Principal) -> dict[str, Any]:
        record = self.get(report_id)
        role = self._capabilities_for_record(record, principal, AuthorizationModel()).role
        return {'owner': record.get('owner'), 'role': role, 'grants': dict(record.get('grants', {}))}

    def update_grant(self, report_id: str, subject: str, role: str | None) -> dict[str, Any]:
        if role not in _ROLES - {'owner'} and role is not None:
            raise VisualizerContractError('grant role must be editor, viewer, or removed')
        subject = ' '.join(str(subject).split())
        if not subject: raise VisualizerContractError('grant subject is required')
        with self._transaction():
            value = self._read_unlocked(); record = value['resources'].get(validate_report_id(report_id))
            if not record or record.get('state') != 'active': raise ReportNotFoundError(report_id)
            if role is None: record.setdefault('grants', {}).pop(subject, None)
            else: record.setdefault('grants', {})[subject] = role
            self._write_unlocked(value); return json.loads(json.dumps(record))

    @staticmethod
    def _summary(record: Any) -> dict[str, Any]:
        model=getattr(record, 'model', {}) if not isinstance(record, Mapping) else record.get('model', {})
        return {
            'report_id': str(getattr(record, 'report_id', '') if not isinstance(record, Mapping) else record.get('report_id', '')),
            'title': str(getattr(record, 'title', 'Untitled report') if not isinstance(record, Mapping) else record.get('title') or 'Untitled report'),
            'revision': int(getattr(record, 'revision', 0) if not isinstance(record, Mapping) else record.get('revision') or 0),
            'updated_at': str(getattr(record, 'updated_at', '') if not isinstance(record, Mapping) else record.get('updated_at') or ''),
            'item_count': len(model.get('items', ())) if isinstance(model, Mapping) else 0,
            'group_count': len(model.get('groups', ())) if isinstance(model, Mapping) else 0,
        }

    def update_summary(self, record: Any) -> None:
        summary=self._summary(record); report_id=validate_report_id(summary['report_id'])
        with self._transaction():
            value=self._read_unlocked(); resource=value['resources'].get(report_id)
            if not resource: raise ReportNotFoundError(report_id)
            resource['summary']=summary; self._write_unlocked(value)

    def rebuild_summaries(self, records: Any) -> None:
        summaries={}
        for record in records:
            summary=self._summary(record); summaries[summary['report_id']]=summary
        with self._transaction():
            value=self._read_unlocked()
            for report_id, resource in value['resources'].items():
                if report_id in summaries: resource['summary']=summaries[report_id]
                elif resource.get('state') in {'deleted', 'aborted'}: resource.pop('summary', None)
            self._write_unlocked(value)

    def visible_summaries(self, principal: Principal, authorization: AuthorizationModel) -> list[dict[str, Any]]:
        with self._transaction():
            value=self._read_unlocked(); result=[]
            for report_id, resource in value.get('resources', {}).items():
                if not self._capabilities_for_record(resource, principal, authorization).can_read: continue
                summary=resource.get('summary')
                if isinstance(summary, Mapping): result.append(dict(summary))
            return sorted(result,key=lambda item:(str(item.get('updated_at') or ''),str(item.get('report_id') or '')),reverse=True)

    def capabilities(self, report_id: str, principal: Principal, authorization: AuthorizationModel) -> CapabilityProjection:
        try: record = self.get(report_id)
        except ReportNotFoundError:
            return CapabilityProjection(report_id, None, False, False, False, False, False, False, False, False, False, False)
        return self._capabilities_for_record(record, principal, authorization)

    @staticmethod
    def _capabilities_for_record(record: Mapping[str, Any], principal: Principal, authorization: AuthorizationModel) -> CapabilityProjection:
        effective = authorization.effective_permissions(principal)
        admin = principal.authenticated and (GLOBAL_ADMIN in effective or 'visembler.admin' in principal.roles)
        role = 'owner' if principal.authenticated and principal.subject == record.get('owner') else record.get('grants', {}).get(principal.subject) if principal.authenticated else None
        if role is None and principal.authenticated:
            groups = principal.metadata.get('groups', ()) if isinstance(principal.metadata, Mapping) else ()
            for group in groups if isinstance(groups, (list, tuple, set, frozenset)) else ():
                role = record.get('grants', {}).get(f'group:{group}')
                if role in _ROLE_ACTIONS:
                    break
        allowed = set(CAPABILITY_ACTIONS) if admin else set(_ROLE_ACTIONS.get(role or '', ()))
        if record.get('state') == 'trashed':
            allowed = {'report.restore'} if admin or role == 'owner' else set()
        elif record.get('state') != 'active':
            allowed = set()
        return CapabilityProjection(str(record.get('report_id') or ''), role or ('admin' if admin else None), *(action in allowed for action in CAPABILITY_ACTIONS))

    def visible_report_ids(self, principal: Principal, authorization: AuthorizationModel) -> set[str]:
        with self._transaction():
            value=self._read_unlocked()
            return {report_id for report_id, record in value.get('resources', {}).items() if self._capabilities_for_record(record, principal, authorization).can_read}

    def write_readiness(self) -> dict[str, Any]:
        probe = self.root / f'.readiness-{uuid.uuid4().hex}.tmp'; renamed = self.root / f'.readiness-{uuid.uuid4().hex}.done'
        try:
            with probe.open('w', encoding='utf-8') as handle:
                handle.write('visembler-readiness'); handle.flush(); os.fsync(handle.fileno())
            os.replace(probe, renamed)
            with renamed.open('r', encoding='utf-8') as handle:
                if handle.read() != 'visembler-readiness': raise OSError('readback mismatch')
            with self.lock_path.open('a+b') as handle:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX); fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except ImportError: pass
            return {'ok': True, 'path': str(self.root)}
        except OSError as exc:
            return {'ok': False, 'error': type(exc).__name__}
        finally:
            probe.unlink(missing_ok=True); renamed.unlink(missing_ok=True)


class ScopedReportRepository:
    """Capability-aware facade; the raw report/asset repository stays private."""

    def __init__(self, repository: ReportRepository, access: ReportAccessCatalog, principal: Principal, authorization: AuthorizationModel):
        self._repository = repository; self._access = access; self.principal = principal; self.authorization = authorization

    def capabilities(self, report_id: str) -> CapabilityProjection:
        return self._access.capabilities(report_id, self.principal, self.authorization)

    def _require(self, report_id: str, action: str) -> CapabilityProjection:
        if action not in CAPABILITY_ACTIONS: raise ValueError(action)
        projection = self.capabilities(report_id)
        capability_name = {
            'report.read': 'can_read',
            'report.edit': 'can_edit',
            'report.rename': 'can_rename',
            'report.duplicate': 'can_duplicate',
            'report.share': 'can_share',
            'report.delete': 'can_delete',
            'report.restore': 'can_restore',
            'report.history.read': 'can_read_history',
            'report.history.restore': 'can_restore_history',
            'report.export': 'can_export',
        }[action]
        if not getattr(projection, capability_name):
            self._access.audit.record(action, actor=self.principal, report_id=report_id, outcome='denied', reason='permission denied')
            raise PermissionError('report access denied')
        return projection

    def _require_global(self, permission: str) -> None:
        effective = self.authorization.effective_permissions(self.principal)
        if not self.principal.authenticated or (permission not in effective and GLOBAL_ADMIN not in effective):
            self._access.audit.record(permission, actor=self.principal, outcome='denied', reason='global permission denied')
            raise PermissionError('access denied')

    def list(self) -> list[Any]:
        return [record for record in self._repository.list() if self.capabilities(record.report_id).can_read]

    def list_summaries(self) -> list[dict[str, Any]]:
        return self._access.visible_summaries(self.principal, self.authorization)

    def get(self, report_id: str) -> Any:
        self._require(report_id, 'report.read'); return self._repository.get(report_id)

    def create(self, report_id: str, **kwargs: Any) -> Any:
        self._require_global(GLOBAL_CREATE); owner = self.principal.subject
        self._access.begin_create(report_id, owner)
        try:
            record = self._repository.create(report_id, **kwargs); self._access.mark_active(report_id); self._access.update_summary(record)
        except Exception:
            try: self._access.reconcile()
            finally: raise
        self._access.audit.record('report.create', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def commit(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, 'report.edit')
        record = self._repository.commit(report_id, **kwargs); self._access.update_summary(record)
        self._access.audit.record('report.commit', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def rename(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, 'report.rename'); record = self._repository.rename(report_id, **kwargs); self._access.update_summary(record)
        self._access.audit.record('report.rename', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def duplicate(self, source_report_id: str, new_report_id: str, **kwargs: Any) -> Any:
        self._require(source_report_id, 'report.duplicate'); self._require_global(GLOBAL_CREATE)
        self._access.begin_create(new_report_id, self.principal.subject)
        try:
            record = self._repository.create(new_report_id, model=self._repository.get(source_report_id).model, **kwargs); self._access.mark_active(new_report_id); self._access.update_summary(record)
        except Exception:
            self._access.reconcile(); raise
        self._access.audit.record('report.duplicate', actor=self.principal, report_id=new_report_id, revision=record.revision); return record

    def duplicate_from_history(self, source_report_id: str, history_id: str, new_report_id: str, **kwargs: Any) -> Any:
        self._require(source_report_id, 'report.duplicate'); self._require_global(GLOBAL_CREATE)
        self._access.begin_create(new_report_id, self.principal.subject)
        try:
            record = self._repository.duplicate_from_history(source_report_id, history_id, new_report_id, **kwargs); self._access.mark_active(new_report_id); self._access.update_summary(record)
        except Exception:
            self._access.reconcile(); raise
        self._access.audit.record('report.duplicate_history', actor=self.principal, report_id=new_report_id, revision=record.revision); return record

    def list_history(self, report_id: str) -> list[dict[str, Any]]:
        self._require(report_id, 'report.history.read')
        entries = self._repository.list_history(report_id)
        events = self._access.audit.read(report_id=report_id)
        actor_by_revision = {event.get('revision'): event.get('actor_subject') for event in events if event.get('revision') is not None}
        for entry in entries: entry['actor_subject'] = actor_by_revision.get(entry.get('revision'), 'actor unavailable')
        return entries

    def checkpoint(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, 'report.history.restore'); result = self._repository.checkpoint(report_id, **kwargs)
        self._access.audit.record('report.checkpoint', actor=self.principal, report_id=report_id); return result

    def restore_history(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, 'report.history.restore'); record = self._repository.restore_history(report_id, **kwargs)
        self._access.update_summary(record); self._access.audit.record('report.history.restore', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def trash_report(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, 'report.delete'); self._access.begin_trash(report_id)
        try: record = self._repository.trash_report(report_id, **kwargs); self._access.mark_trashed(report_id); self._access.update_summary(record)
        except Exception: self._access.reconcile(); raise
        self._access.audit.record('report.trash', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def restore(self, report_id: str) -> Any:
        projection = self.capabilities(report_id)
        if not projection.can_restore: raise PermissionError('report restore denied')
        record = self._repository.restore(report_id); self._access.mark_active(report_id); self._access.update_summary(record)
        self._access.audit.record('report.restore', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def delete(self, report_id: str, **kwargs: Any) -> bool:
        self._require(report_id, 'report.delete'); self._access.begin_delete(report_id)
        try: result = self._repository.delete(report_id, **kwargs); self._access.mark_deleted(report_id)
        except Exception: self._access.reconcile(); raise
        self._access.audit.record('report.delete', actor=self.principal, report_id=report_id); return result

    def delete_if_blank(self, report_id: str, **kwargs: Any) -> bool:
        self._require(report_id, 'report.delete'); self._access.begin_delete(report_id)
        try:
            result = self._repository.delete_if_blank(report_id, **kwargs)
            if result:
                self._access.mark_deleted(report_id)
                self._access.audit.record('report.delete', actor=self.principal, report_id=report_id)
            else:
                # The repository intentionally left the report in place.
                self._access.mark_active(report_id)
            return result
        except Exception:
            self._access.reconcile(); raise

    def list_trash(self) -> list[Any]:
        return [record for record in self._repository.list_trash() if self.capabilities(record.report_id).can_restore]

    def share(self, report_id: str, subject: str, role: str | None) -> dict[str, Any]:
        self._require(report_id, 'report.share'); record = self._access.update_grant(report_id, subject, role)
        self._access.audit.record('report.share' if role else 'report.share_revoke', actor=self.principal, report_id=report_id, reason=role or 'revoked')
        return record

    def read_asset_for_report(self, report_id: str, asset_id: str) -> bytes:
        self._require(report_id, 'report.read')
        record = self._repository.get(report_id)
        if asset_id not in {str(item.get('asset_id')) for item in record.model.get('items', []) if isinstance(item, Mapping)}:
            raise ReportNotFoundError(asset_id)
        return self._repository.assets.read_image(asset_id)

    def asset_data_url(self, report_id: str, asset_id: str) -> str:
        self.read_asset_for_report(report_id, asset_id)
        return self._repository.assets.data_url(asset_id)

    def export(self, report_id: str) -> Any:
        self._require(report_id, 'report.export'); record = self._repository.get(report_id)
        self._access.audit.record('report.export', actor=self.principal, report_id=report_id, revision=record.revision); return record

    def writable_readiness(self) -> dict[str, Any]:
        return self._access.write_readiness()

    def require_export(self, report_id: str) -> None:
        self._require(report_id, REPORT_EXPORT)

    def update_description(self, report_id: str, **kwargs: Any) -> Any:
        self._require(report_id, REPORT_EDIT)
        record = self._repository.update_description(report_id, **kwargs)
        self._access.update_summary(record)
        self._access.audit.record('report.description', actor=self.principal, report_id=report_id, revision=record.revision)
        return record

    def get_history(self, report_id: str) -> list[dict[str, Any]]:
        return self.list_history(report_id)

    def read_asset_by_id(self, asset_id: str) -> bytes:
        if not self._access.can_read_asset(asset_id, self.principal):
            self._access.audit.record('asset.read', actor=self.principal, outcome='denied', reason='asset access denied')
            raise PermissionError('asset access denied')
        return self._repository.assets.read_image(asset_id)

    def asset_data_url_by_id(self, asset_id: str) -> str:
        self.read_asset_by_id(asset_id)
        return self._repository.assets.data_url(asset_id)

    @property
    def access(self) -> ReportAccessCatalog:
        return self._access
