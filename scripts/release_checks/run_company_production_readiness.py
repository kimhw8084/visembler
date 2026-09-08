#!/usr/bin/env python3
"""Local/company-boundary readiness gate for Visembler.

This gate proves application-level guarantees in an isolated temporary
repository.  It deliberately never promotes a laptop simulation to the
company-managed production-candidate status; that status requires an external
target evidence document for the exact candidate and topology.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from company_ui.products.visualizer.domain import RevisionConflictError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import ReportAccessCatalog, ReportRole, ScopedReportRepository
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.runtime import build_runtime_adapter
from company_ui.products.visualizer.templates import template_model
from company_ui.security import AuthorizationModel, Principal


def _principal(subject: str, *permissions: str, groups: tuple[str, ...] = ()) -> Principal:
    return Principal(subject, permissions=frozenset(permissions), metadata={"groups": groups})


def _model(text: str = "seed") -> dict[str, Any]:
    return canonical_model({"items": [{"id": "c1", "type": "text", "engine": "TextEngine", "element": "Body Narrative", "order": 0, "text": text, "body": text}]})


def _scoped(repo: ReportRepository, access: ReportAccessCatalog, principal: Principal) -> ScopedReportRepository:
    return ScopedReportRepository(repo, access, principal, AuthorizationModel())


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _fingerprint(values: dict[str, str]) -> str:
    safe = {key: value for key, value in values.items() if "SECRET" not in key.upper() and "TOKEN" not in key.upper() and "PASSWORD" not in key.upper()}
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()


def _run_check(checks: list[dict[str, Any]], check_id: str, name: str, fn: Callable[[], Any]) -> Any:
    started = time.perf_counter()
    try:
        value = fn()
        checks.append({"id": check_id, "name": name, "status": "PASS", "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
        return value
    except Exception as exc:  # the receipt must show the first concrete failure
        checks.append({"id": check_id, "name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {str(exc)[:300]}", "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
        return None


def _check_auth_contract() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="visembler-company-auth-") as td:
        base = {
            "COMPANY_UI_ENVIRONMENT": "prod",
            "COMPANY_UI_STORAGE_SECRET": "company-readiness-storage-secret-0123456789",
            "COMPANY_UI_VISUALIZER_DATA_DIR": td,
            "COMPANY_UI_PROXY_ENABLED": "true",
            "COMPANY_UI_TRUSTED_PROXIES": "10.0.0.0/8",
            "COMPANY_UI_HOST": "0.0.0.0",
        }
        try:
            build_runtime_adapter(base)
        except RuntimeError:
            pass
        else:
            raise AssertionError("production accepted missing header auth mode")
        adapter, _ = build_runtime_adapter({**base, "COMPANY_UI_AUTH_MODE": "header"})
        good = asyncio.run(adapter.auth_adapter.authenticate({"x-auth-user": "alice", "x-auth-roles": "visembler.user"}, "10.1.2.3"))
        bad = asyncio.run(adapter.auth_adapter.authenticate({"x-auth-user": "mallory"}, "192.0.2.1"))
        assert good.authenticated and good.subject == "alice"
        assert not bad.authenticated
        return {"trusted_subject": good.subject, "untrusted_headers_anonymous": not bad.authenticated}


def _check_acl_and_conflict() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="visembler-company-acl-") as td:
        repo = ReportRepository(Path(td) / "reports")
        access = ReportAccessCatalog(repo)
        owner = _scoped(repo, access, _principal("alice", "report.create"))
        record = owner.create("shared", title="Shared", model=template_model("blank"))
        access.grant("shared", owner.principal, "bob", ReportRole.EDITOR)
        access.grant("shared", owner.principal, "carol", ReportRole.VIEWER)
        editor = _scoped(repo, access, _principal("bob"))
        viewer = _scoped(repo, access, _principal("carol"))
        stranger = _scoped(repo, access, _principal("mallory"))
        assert editor.get(record.report_id).report_id == record.report_id
        assert viewer.get(record.report_id).report_id == record.report_id
        with __import__("contextlib").suppress(PermissionError):
            stranger.get(record.report_id)
            raise AssertionError("unauthorized report read succeeded")
        with __import__("contextlib").suppress(PermissionError):
            viewer.commit(record.report_id, base_revision=1, model=_model("viewer"), commit_id="viewer")
            raise AssertionError("viewer write succeeded")
        editor.commit(record.report_id, base_revision=1, model=_model("editor"), commit_id="editor")
        with __import__("contextlib").suppress(RevisionConflictError):
            owner.commit(record.report_id, base_revision=1, model=_model("stale"), commit_id="stale")
            raise AssertionError("stale write succeeded")
        assert repo.get(record.report_id).model["items"][0]["text"] == "editor"
        access.revoke(record.report_id, owner.principal, "bob")
        with __import__("contextlib").suppress(PermissionError):
            editor.get(record.report_id)
            raise AssertionError("revoked editor retained access")
        return {"owner": "alice", "editor": "bob", "viewer": "carol", "unauthorized": "mallory", "stale_write": "rejected", "revocation": "enforced"}


def _check_migration_backup_fault() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="visembler-company-backup-") as td:
        source = Path(td) / "source"
        repo = ReportRepository(source / "reports")
        access = ReportAccessCatalog(repo)
        record = repo.create("legacy", model=_model("legacy"))
        migration = access.migrate([record], owner_subject="migration-owner", require_explicit_owner=True)
        repo.commit("legacy", base_revision=1, model=_model("history"), commit_id="history")
        backup = Path(td) / "backup"
        started = time.perf_counter()
        shutil.copytree(source, backup)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        restored = ReportRepository(backup / "reports")
        restored_access = ReportAccessCatalog(restored)
        assert restored.get("legacy").model["items"][0]["text"] == "history"
        assert restored_access.get("legacy").owner_subject == "migration-owner"
        broken = restored.root / "broken.json"
        broken.write_text("{broken", encoding="utf-8")
        restored.list()
        assert not broken.exists()
        assert any((restored.root / "_quarantine").glob("broken.*.corrupt.json"))
        return {"migration": migration, "backup_duration_ms": duration_ms, "restored_owner": restored_access.get("legacy").owner_subject, "corrupt_report_quarantined": True}


def _capacity() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for count in (10, 100, 1000):
        with tempfile.TemporaryDirectory(prefix=f"visembler-company-capacity-{count}-") as td:
            repo = ReportRepository(Path(td) / "reports")
            for index in range(count):
                repo.create(f"r{index:04d}", model=template_model("blank"))
            started = time.perf_counter()
            listed = len(repo.list())
            elapsed = (time.perf_counter() - started) * 1000
            assert listed == count
            result[str(count)] = {"reports": listed, "list_ms": round(elapsed, 3)}
    return result


def _write_evidence(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    details["auth"] = _run_check(checks, "CP001", "production authentication fails closed", _check_auth_contract)
    details["acl"] = _run_check(checks, "CP002", "resource ACL, viewer enforcement, revoke, and stale conflict", _check_acl_and_conflict)
    details["migration_backup"] = _run_check(checks, "CP003", "migration, backup/restore, and corruption quarantine", _check_migration_backup_fault)
    details["capacity"] = _run_check(checks, "CP004", "filesystem catalog characterization", _capacity)
    hashes = {
        "integrated_editor.mjs": _hash(ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"),
        "page.py": _hash(ROOT / "company_ui/products/visualizer/page.py"),
        "frozen_connector": _hash(ROOT / "company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"),
    }
    environment = {key: value for key, value in os.environ.items() if key.startswith("COMPANY_UI_") or key.startswith("VISSEMBLER_")}
    target_path = os.environ.get("VISSEMBLER_COMPANY_TARGET_EVIDENCE", "")
    target = None
    if target_path:
        try:
            target = json.loads(Path(target_path).read_text(encoding="utf-8"))
        except Exception as exc:
            target = {"status": "invalid", "detail": str(exc)[:240]}
    local_pass = all(item["status"] == "PASS" for item in checks)
    head = _git("rev-parse", "HEAD")
    target_pass = isinstance(target, dict) and target.get("status") == "PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE" and target.get("candidate_sha") == head
    status = "PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE" if local_pass and target_pass else "READY_FOR_COMPANY_TARGET_CERTIFICATION" if local_pass else "BLOCKED"
    receipt = {
        "schema_version": 1,
        "application": "Visembler",
        "release_status": status,
        "checks_status": "PASS" if local_pass else "FAIL",
        "source": {"head": head, "branch": _git("branch", "--show-current"), "hashes": hashes},
        "dependencies": {"python": sys.version.split()[0], "nicegui": importlib.metadata.version("nicegui"), "node": subprocess.run(["node", "--version"], check=True, capture_output=True, text=True).stdout.strip()},
        "configuration_fingerprint": _fingerprint(environment),
        "checks": checks,
        "details": details,
        "target_evidence": target_path or None,
        "remaining_target_requirements": [] if target_pass else [
            "company-managed identity assertion boundary",
            "company durable storage and backup ownership",
            "reverse-proxy/WebSocket/session topology evidence",
            "required company browser and recovery evidence",
        ],
    }
    receipt_path = output / "company_production_readiness.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(output / "company_production_evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(receipt_path, receipt_path.name)
    print(json.dumps({"release_status": status, "checks_status": receipt["checks_status"], "receipt": str(receipt_path), "evidence_zip": str(output / "company_production_evidence.zip")}, indent=2))
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    _write_evidence(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
