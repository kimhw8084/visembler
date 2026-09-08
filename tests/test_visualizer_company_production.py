from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from company_ui.products.visualizer.domain import RevisionConflictError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import (
    HISTORY_READ,
    REPORT_EDIT,
    REPORT_EXPORT,
    REPORT_READ,
    REPORT_SHARE,
    ReportAccessCatalog,
    ReportRole,
    ScopedReportRepository,
)
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.runtime import build_runtime_adapter
from company_ui.products.visualizer.templates import template_model
from company_ui.security import Principal


def principal(subject: str, *permissions: str, groups: tuple[str, ...] = ()) -> Principal:
    return Principal(subject, permissions=frozenset(permissions), metadata={"groups": groups})


def scoped(repo: ReportRepository, access: ReportAccessCatalog, subject: str, *permissions: str, groups: tuple[str, ...] = ()) -> ScopedReportRepository:
    from company_ui.security import AuthorizationModel

    return ScopedReportRepository(repo, access, principal(subject, *permissions, groups=groups), AuthorizationModel())


def test_access_migration_is_explicit_idempotent_and_audited(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    record = repo.create("legacy", model=template_model("blank"))
    access = ReportAccessCatalog(repo)

    result = access.migrate([record], owner_subject="alice", require_explicit_owner=True)
    assert result == {"examined": 1, "existing": 0, "migrated": 1}
    assert access.migrate([record], owner_subject=None, require_explicit_owner=True) == {"examined": 1, "existing": 1, "migrated": 0}
    assert access.get("legacy").owner_subject == "alice"

    events = access.audit.read()
    assert events == []  # migration is structural, not a user action
    with pytest.raises(Exception, match="COMPANY_UI_MIGRATION_OWNER_SUBJECT"):
        access.migrate([repo.create("legacy-2", model=template_model("blank"))], owner_subject=None, require_explicit_owner=True)


def test_owner_editor_viewer_and_unauthorized_paths_are_server_enforced(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repo)
    owner = scoped(repo, access, "alice", "report.create")
    record = owner.create("shared", model=template_model("blank"))
    access.grant("shared", owner.principal, "bob", ReportRole.EDITOR)
    access.grant("shared", owner.principal, "carol", ReportRole.VIEWER)

    editor = scoped(repo, access, "bob")
    viewer = scoped(repo, access, "carol")
    stranger = scoped(repo, access, "mallory")
    assert editor.get("shared").report_id == record.report_id
    assert viewer.get("shared").report_id == record.report_id
    assert [item.report_id for item in stranger.list()] == []
    with pytest.raises(PermissionError): stranger.get("shared")
    with pytest.raises(PermissionError): viewer.commit("shared", base_revision=1, model=canonical_model({}), commit_id="viewer")

    edited = editor.commit(
        "shared",
        base_revision=1,
        model=canonical_model({"items": [{"id": "c1", "type": "text", "engine": "TextEngine", "order": 0, "text": "edited"}]}),
        commit_id="editor-1",
    )
    assert edited.revision == 2
    assert editor.list_history("shared")
    assert access.can("shared", viewer.principal, REPORT_READ)
    assert not access.can("shared", viewer.principal, REPORT_EDIT)
    assert access.can("shared", owner.principal, REPORT_SHARE)


def test_history_and_export_are_resource_scoped_and_collision_does_not_reassign_owner(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repo)
    owner = scoped(repo, access, "alice", "report.create")
    record = owner.create("shared", model=template_model("blank"))
    access.grant(record.report_id, owner.principal, "bob", ReportRole.VIEWER)
    viewer = scoped(repo, access, "bob")
    stranger = scoped(repo, access, "mallory")

    viewer.require_export(record.report_id)
    assert viewer.list_history(record.report_id)[0]["revision"] == 1
    with pytest.raises(PermissionError): stranger.list_history(record.report_id)
    with pytest.raises(PermissionError): stranger.require_export(record.report_id)

    with pytest.raises(VisualizerContractError, match="already exists"):
        owner.create(record.report_id, model=template_model("blank"))
    assert access.get(record.report_id).owner_subject == "alice"
    assert access.can(record.report_id, viewer.principal, REPORT_EXPORT)


def test_share_revoke_group_access_and_stale_commit_preserve_data(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repo)
    owner = scoped(repo, access, "alice", "report.create")
    owner.create("shared", model=template_model("blank"))
    access.grant("shared", owner.principal, "manufacturing", ReportRole.VIEWER, group=True)
    group_member = scoped(repo, access, "dave", groups=("manufacturing",))
    assert group_member.get("shared").report_id == "shared"
    access.revoke("shared", owner.principal, "manufacturing", group=True)
    with pytest.raises(PermissionError): group_member.get("shared")

    stale = repo.get("shared")
    repo.commit("shared", base_revision=stale.revision, model=canonical_model({"items": [{"id": "remote", "type": "text", "engine": "TextEngine", "order": 0, "text": "remote"}]}), commit_id="remote")
    with pytest.raises(RevisionConflictError):
        owner.commit("shared", base_revision=stale.revision, model=canonical_model({"items": []}), commit_id="stale")
    assert repo.get("shared").model["items"][0]["text"] == "remote"


def test_asset_access_is_scoped_without_leaking_asset_existence(tmp_path: Path):
    out = io.BytesIO()
    Image.new("RGB", (12, 12), (10, 20, 30)).save(out, format="PNG")
    image = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
    repo = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repo)
    owner = scoped(repo, access, "alice", "report.create")
    record = owner.create("image", model=canonical_model({"items": [{"id": "c1", "type": "image", "engine": "ImageMediaEngine", "order": 0, "src": image}]}))
    asset_id = record.model["items"][0]["asset_id"]
    assert access.can_read_asset(asset_id, owner.principal)
    assert not access.can_read_asset(asset_id, principal("mallory"))
    access.grant("image", owner.principal, "bob", ReportRole.VIEWER)
    assert access.can_read_asset(asset_id, principal("bob"))


def test_production_authentication_fails_closed_and_trusted_header_is_accepted(tmp_path: Path):
    base = {
        "COMPANY_UI_ENVIRONMENT": "prod",
        "COMPANY_UI_STORAGE_SECRET": "storage-secret-that-is-longer-than-32-characters",
        "COMPANY_UI_VISUALIZER_DATA_DIR": str(tmp_path),
        "COMPANY_UI_PROXY_ENABLED": "true",
        "COMPANY_UI_TRUSTED_PROXIES": "10.0.0.0/8",
        "COMPANY_UI_HOST": "0.0.0.0",
    }
    with pytest.raises(RuntimeError, match="AUTH_MODE=header"):
        build_runtime_adapter(base)
    adapter, _ = build_runtime_adapter({**base, "COMPANY_UI_AUTH_MODE": "header"})
    accepted = asyncio.run(adapter.auth_adapter.authenticate({"x-auth-user": "alice", "x-auth-roles": "visembler.user"}, "10.1.2.3"))
    spoofed = asyncio.run(adapter.auth_adapter.authenticate({"x-auth-user": "mallory"}, "192.0.2.1"))
    assert accepted.authenticated and accepted.subject == "alice"
    assert not spoofed.authenticated


def test_audit_events_contain_safe_metadata_only(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repo)
    owner = scoped(repo, access, "alice", "report.create")
    owner.create("audited", model=template_model("blank"))
    access.grant("audited", owner.principal, "bob", ReportRole.VIEWER)
    events = access.audit.read()
    assert {event["action"] for event in events} >= {"report.create", "report.share.grant"}
    assert all("model" not in event and "clipboard" not in event for event in events)
