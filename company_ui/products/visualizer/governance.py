"""Resource governance for the Visembler report repository.

The report JSON remains the canonical editable document.  Ownership and grants
live beside it in a small rebuildable governance directory so old report files,
history, and assets remain readable without an in-place schema rewrite.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from threading import RLock
from collections.abc import Iterable
from typing import Any, Mapping

from company_ui.security import AccessPolicy, AuthorizationModel, Principal

from .domain import ReportNotFoundError, RevisionConflictError, VisualizerContractError, stable_json, validate_report_id
from .repository import ReportRecord, ReportRepository


class ReportRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


REPORT_READ = "report.read"
REPORT_CREATE = "report.create"
REPORT_EDIT = "report.edit"
REPORT_RENAME = "report.rename"
REPORT_DUPLICATE = "report.duplicate"
REPORT_SHARE = "report.share"
REPORT_DELETE = "report.delete"
REPORT_RESTORE = "report.restore"
HISTORY_READ = "report.history.read"
HISTORY_RESTORE = "report.history.restore"
REPORT_EXPORT = "report.export"
ADMINISTRATION = "administration"

OWNER_ACTIONS = frozenset({
    REPORT_READ, REPORT_EDIT, REPORT_RENAME, REPORT_DUPLICATE, REPORT_SHARE,
    REPORT_DELETE, REPORT_RESTORE, HISTORY_READ, HISTORY_RESTORE, REPORT_EXPORT,
})
EDITOR_ACTIONS = frozenset({
    REPORT_READ, REPORT_EDIT, REPORT_RENAME, REPORT_DUPLICATE,
    HISTORY_READ, HISTORY_RESTORE, REPORT_EXPORT,
})
VIEWER_ACTIONS = frozenset({REPORT_READ, HISTORY_READ, REPORT_EXPORT})


@dataclass(frozen=True, slots=True)
class AccessRecord:
    report_id: str
    owner_subject: str
    grants: Mapping[str, ReportRole]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "owner_subject": self.owner_subject,
            "grants": {key: value.value for key, value in sorted(self.grants.items())},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AccessRecord":
        report_id = validate_report_id(str(value.get("report_id") or ""))
        owner = str(value.get("owner_subject") or "").strip()
        if not owner or len(owner) > 256:
            raise VisualizerContractError("access record requires a stable owner subject")
        raw_grants = value.get("grants", {})
        if not isinstance(raw_grants, Mapping):
            raise VisualizerContractError("access grants must be an object")
        grants: dict[str, ReportRole] = {}
        for raw_key, raw_role in raw_grants.items():
            key = str(raw_key).strip()
            if not key or len(key) > 320 or key in {owner, f"subject:{owner}"}:
                continue
            try:
                role = ReportRole(str(raw_role))
            except ValueError as exc:
                raise VisualizerContractError("access grant has an invalid role") from exc
            if role is ReportRole.OWNER:
                raise VisualizerContractError("owner must be represented by owner_subject")
            grants[key] = role
        return cls(report_id, owner, grants, int(value.get("schema_version", 1)))


class AuditTrail:
    """Small append-only, redacted audit stream stored with report data."""

    def __init__(self, root: Path):
        self.path = root / "_governance" / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._lock_path = self.path.parent / ".audit.lock"

    @contextmanager
    def _transaction(self):
        with self._lock:
            handle = self._lock_path.open("a+b")
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

    def record(
        self,
        *,
        actor: Principal,
        action: str,
        resource_id: str | None,
        outcome: str = "success",
        revision: int | None = None,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_subject": actor.subject if actor.authenticated else "anonymous",
            "action": action,
            "resource_id": resource_id,
            "outcome": outcome,
            "correlation_id": correlation_id or str(actor.metadata.get("correlation_id") or "")[:128] or None,
        }
        if revision is not None:
            event["revision"] = int(revision)
        if reason:
            event["reason"] = " ".join(str(reason).split())[:240]
        line = stable_json(event) + "\n"
        with self._transaction():
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    def read(self, *, limit: int = 200) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        except FileNotFoundError:
            return []
        output: list[dict[str, Any]] = []
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                output.append(dict(value))
        return output


class ReportAccessCatalog:
    """Durable owner/grant catalog with atomic, idempotent migration."""

    def __init__(self, repository: ReportRepository):
        self.repository = repository
        self.root = repository.root / "_governance"
        self.access_root = self.root / "access"
        self.access_root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._lock_path = self.root / ".access.lock"
        self.audit = AuditTrail(repository.root)

    @contextmanager
    def _transaction(self):
        with self._lock:
            handle = self._lock_path.open("a+b")
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

    def _path(self, report_id: str) -> Path:
        return self.access_root / f"{validate_report_id(report_id)}.json"

    @staticmethod
    def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(stable_json(value) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                temp.chmod(0o600)
            except OSError:
                pass
            os.replace(temp, path)
            try:
                directory_fd = os.open(path.parent, os.O_DIRECTORY)
                os.fsync(directory_fd)
                os.close(directory_fd)
            except (AttributeError, OSError):
                pass
        finally:
            temp.unlink(missing_ok=True)

    def get(self, report_id: str) -> AccessRecord:
        path = self._path(report_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ReportNotFoundError(report_id) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise VisualizerContractError(f"corrupt access record: {report_id}") from exc
        if not isinstance(value, Mapping):
            raise VisualizerContractError(f"corrupt access record: {report_id}")
        record = AccessRecord.from_dict(value)
        if record.report_id != validate_report_id(report_id):
            raise VisualizerContractError("access filename and identity differ")
        return record

    def has(self, report_id: str) -> bool:
        """Return whether a validated access record exists without exposing it."""
        try:
            self.get(report_id)
        except ReportNotFoundError:
            return False
        return True

    def ensure_owner(self, report_id: str, owner_subject: str) -> AccessRecord:
        owner = str(owner_subject or "").strip()
        if not owner or len(owner) > 256:
            raise VisualizerContractError("an explicit stable migration owner is required")
        with self._transaction():
            path = self._path(report_id)
            if path.exists():
                return self.get(report_id)
            record = AccessRecord(validate_report_id(report_id), owner, {})
            self._atomic_write(path, record.to_dict())
            return record

    def migrate(self, records: Iterable[ReportRecord], *, owner_subject: str | None, require_explicit_owner: bool) -> dict[str, int]:
        records = tuple(records)
        migrated = 0
        existing = 0
        for record in records:
            try:
                self.get(record.report_id)
                existing += 1
                continue
            except ReportNotFoundError:
                pass
            if not owner_subject:
                if require_explicit_owner:
                    raise VisualizerContractError(
                        f"report {record.report_id} has no owner; set COMPANY_UI_MIGRATION_OWNER_SUBJECT before production startup"
                    )
                continue
            self.ensure_owner(record.report_id, owner_subject)
            migrated += 1
        return {"examined": len(records), "existing": existing, "migrated": migrated}

    def create(self, report_id: str, owner_subject: str) -> AccessRecord:
        record = self.ensure_owner(report_id, owner_subject)
        self.audit.record(actor=Principal(owner_subject), action="report.create", resource_id=report_id)
        return record

    def _role(self, record: AccessRecord, principal: Principal) -> ReportRole | None:
        if not principal.authenticated:
            return None
        if principal.subject == record.owner_subject:
            return ReportRole.OWNER
        direct = record.grants.get(f"subject:{principal.subject}") or record.grants.get(principal.subject)
        if direct:
            return direct
        groups = principal.metadata.get("groups", ())
        if isinstance(groups, str):
            groups = (groups,)
        for group in groups if isinstance(groups, Iterable) else ():
            role = record.grants.get(f"group:{str(group).strip()}")
            if role and (direct is None or role is ReportRole.EDITOR):
                direct = role
        return direct

    def role_for(self, report_id: str, principal: Principal) -> ReportRole | None:
        return self._role(self.get(report_id), principal)

    def can(self, report_id: str, principal: Principal, action: str) -> bool:
        if principal.has_permission(ADMINISTRATION) or principal.has_permission("report.admin"):
            return True
        try:
            role = self.role_for(report_id, principal)
        except (ReportNotFoundError, VisualizerContractError):
            return False
        if role is ReportRole.OWNER:
            return action in OWNER_ACTIONS
        if role is ReportRole.EDITOR:
            return action in EDITOR_ACTIONS
        if role is ReportRole.VIEWER:
            return action in VIEWER_ACTIONS
        return False

    def require(self, report_id: str, principal: Principal, action: str) -> None:
        if self.can(report_id, principal, action):
            return
        self.audit.record(actor=principal, action=action, resource_id=report_id, outcome="denied", reason="resource access denied")
        if not principal.authenticated:
            raise PermissionError("authentication required")
        raise PermissionError("resource access denied")

    def require_global(self, principal: Principal, action: str, authorization: AuthorizationModel) -> None:
        if principal.has_permission(ADMINISTRATION) or principal.has_permission(action):
            return
        decision = authorization.check(principal, AccessPolicy(required_permissions=frozenset({action})))
        if not decision.allowed:
            self.audit.record(actor=principal, action=action, resource_id=None, outcome="denied", reason=decision.reason)
            raise PermissionError("access denied")

    def grant(self, report_id: str, actor: Principal, subject: str, role: ReportRole, *, group: bool = False) -> AccessRecord:
        self.require(report_id, actor, REPORT_SHARE)
        cleaned = str(subject or "").strip()
        if not cleaned or len(cleaned) > 256 or role is ReportRole.OWNER:
            raise VisualizerContractError("a valid non-owner share target and role are required")
        key = f"group:{cleaned}" if group else f"subject:{cleaned}"
        with self._transaction():
            current = self.get(report_id)
            grants = dict(current.grants)
            grants[key] = role
            updated = AccessRecord(current.report_id, current.owner_subject, grants)
            self._atomic_write(self._path(report_id), updated.to_dict())
        self.audit.record(actor=actor, action="report.share.grant", resource_id=report_id, reason=f"{key}={role.value}")
        return updated

    def revoke(self, report_id: str, actor: Principal, subject: str, *, group: bool = False) -> AccessRecord:
        self.require(report_id, actor, REPORT_SHARE)
        key = f"group:{str(subject or '').strip()}" if group else f"subject:{str(subject or '').strip()}"
        with self._transaction():
            current = self.get(report_id)
            grants = dict(current.grants)
            grants.pop(key, None)
            updated = AccessRecord(current.report_id, current.owner_subject, grants)
            self._atomic_write(self._path(report_id), updated.to_dict())
        self.audit.record(actor=actor, action="report.share.revoke", resource_id=report_id, reason=key)
        return updated

    def accessible(self, records: Iterable[ReportRecord], principal: Principal, action: str = REPORT_READ) -> list[ReportRecord]:
        return [record for record in records if self.can(record.report_id, principal, action)]

    def can_read_asset(self, asset_id: str, principal: Principal) -> bool:
        if not isinstance(asset_id, str) or not asset_id.startswith("sha256-"):
            return False
        for record in self.accessible(self.repository.list(), principal, REPORT_READ):
            if any(isinstance(item, Mapping) and item.get("asset_id") == asset_id for item in record.model.get("items", ())):
                return True
        return False

    def access_summary(self, report_id: str, principal: Principal) -> dict[str, Any]:
        record = self.get(report_id)
        role = self._role(record, principal)
        return {"owner": record.owner_subject, "role": role.value if role else None, "grants": {key: value.value for key, value in record.grants.items()}}

    def health(self) -> bool:
        """Cheap readiness check; it does not deserialize the report catalog."""
        return self.access_root.is_dir() and os.access(self.access_root, os.R_OK | os.W_OK) and self.audit.path.parent.is_dir()

    def delete(self, report_id: str) -> None:
        self._path(report_id).unlink(missing_ok=True)


class ScopedReportRepository:
    """The only repository surface a request-bound Visembler page receives."""

    def __init__(self, repository: ReportRepository, access: ReportAccessCatalog, principal: Principal, authorization: AuthorizationModel):
        self._repository = repository
        self._access = access
        self._principal = principal
        self._authorization = authorization
        self.assets = repository.assets

    @property
    def principal(self) -> Principal:
        return self._principal

    def get(self, report_id: str) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_READ)
        return self._repository.get(report_id)

    def list(self) -> list[ReportRecord]:
        return self._access.accessible(self._repository.list(), self._principal)

    def list_trash(self) -> list[ReportRecord]:
        return self._access.accessible(self._repository.list_trash(), self._principal)

    def create(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require_global(self._principal, REPORT_CREATE, self._authorization)
        # Publish the owner record before the report file so a storage failure
        # cannot leave a newly-created report without an unambiguous owner.
        access_was_missing = not self._access.has(report_id)
        self._access.ensure_owner(report_id, self._principal.subject)
        try:
            record = self._repository.create(report_id, **kwargs)
        except Exception:
            if access_was_missing:
                self._access.delete(report_id)
            raise
        self._access.audit.record(actor=self._principal, action="report.create", resource_id=record.report_id)
        return record

    def require_export(self, report_id: str) -> None:
        """Enforce the report.export capability at the server boundary."""
        self._access.require(report_id, self._principal, REPORT_EXPORT)

    def commit(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_EDIT)
        record = self._repository.commit(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.commit", resource_id=report_id, revision=record.revision)
        return record

    def rename(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_RENAME)
        record = self._repository.rename(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.rename", resource_id=report_id, revision=record.revision)
        return record

    def update_description(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_EDIT)
        record = self._repository.update_description(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.description", resource_id=report_id, revision=record.revision)
        return record

    def trash_report(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_DELETE)
        record = self._repository.trash_report(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.trash", resource_id=report_id, revision=record.revision)
        return record

    def restore(self, report_id: str) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_RESTORE)
        record = self._repository.restore(report_id)
        self._access.audit.record(actor=self._principal, action="report.restore", resource_id=report_id, revision=record.revision)
        return record

    def delete(self, report_id: str, **kwargs: Any) -> bool:
        self._access.require(report_id, self._principal, REPORT_DELETE)
        result = self._repository.delete(report_id, **kwargs)
        self._access.delete(report_id)
        self._access.audit.record(actor=self._principal, action="report.delete", resource_id=report_id)
        return result

    def delete_if_blank(self, report_id: str, **kwargs: Any) -> bool:
        self._access.require(report_id, self._principal, REPORT_DELETE)
        result = self._repository.delete_if_blank(report_id, **kwargs)
        if result:
            self._access.delete(report_id)
            self._access.audit.record(actor=self._principal, action="report.delete", resource_id=report_id, reason="blank report cleanup")
        return result

    def list_history(self, report_id: str) -> list[dict[str, Any]]:
        self._access.require(report_id, self._principal, HISTORY_READ)
        return self._repository.list_history(report_id)

    def get_history(self, report_id: str, history_id: str) -> dict[str, Any]:
        self._access.require(report_id, self._principal, HISTORY_READ)
        return self._repository.get_history(report_id, history_id)

    def checkpoint(self, report_id: str, **kwargs: Any) -> dict[str, Any]:
        self._access.require(report_id, self._principal, HISTORY_RESTORE)
        value = self._repository.checkpoint(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.checkpoint", resource_id=report_id)
        return value

    def restore_history(self, report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, HISTORY_RESTORE)
        record = self._repository.restore_history(report_id, **kwargs)
        self._access.audit.record(actor=self._principal, action="report.history.restore", resource_id=report_id, revision=record.revision)
        return record

    def duplicate_from_history(self, report_id: str, history_id: str, new_report_id: str, **kwargs: Any) -> ReportRecord:
        self._access.require(report_id, self._principal, REPORT_DUPLICATE)
        self._access.require_global(self._principal, REPORT_CREATE, self._authorization)
        access_was_missing = not self._access.has(new_report_id)
        self._access.ensure_owner(new_report_id, self._principal.subject)
        try:
            record = self._repository.duplicate_from_history(report_id, history_id, new_report_id, **kwargs)
        except Exception:
            if access_was_missing:
                self._access.delete(new_report_id)
            raise
        self._access.audit.record(actor=self._principal, action="report.create", resource_id=record.report_id)
        self._access.audit.record(actor=self._principal, action="report.duplicate", resource_id=record.report_id, reason=f"from:{report_id}:{history_id}")
        return record
