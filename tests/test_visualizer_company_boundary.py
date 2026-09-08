from __future__ import annotations

import json
import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from company_ui.diagnostics.correlation import CorrelationIdMiddleware, set_correlation_id, reset_correlation_id
from company_ui.products.visualizer.domain import VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import CAPABILITY_ACTIONS, ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.templates import template_model
from company_ui.security import AuthorizationModel, Principal, RoleDefinition


def _auth() -> AuthorizationModel:
    return AuthorizationModel({'visembler.admin': RoleDefinition('visembler.admin', frozenset({'administration', 'report.create', *CAPABILITY_ACTIONS}))})


def _owner(tmp_path: Path) -> tuple[ReportRepository, ReportAccessCatalog, ScopedReportRepository]:
    repository = ReportRepository(tmp_path)
    access = ReportAccessCatalog(tmp_path)
    principal = Principal('alice', roles=frozenset({'visembler.admin'}))
    return repository, access, ScopedReportRepository(repository, access, principal, _auth())


def test_capability_projection_and_duplicate_is_centralized(tmp_path: Path) -> None:
    repository, access, owner = _owner(tmp_path)
    created = owner.create('owned', model=template_model('blank'))
    assert owner.list_summaries()[0]['report_id'] == 'owned'
    access.update_grant('owned', 'bob', 'viewer')
    viewer = ScopedReportRepository(repository, access, Principal('bob'), _auth())
    assert [item['report_id'] for item in viewer.list_summaries()] == ['owned']
    editor = ScopedReportRepository(repository, access, Principal('bob', permissions=frozenset({'report.create'})), _auth())
    access.update_grant('owned', 'bob', 'editor')
    assert viewer.capabilities('owned').can_duplicate is True
    # Revoke the grant and prove the same facade rejects both clone paths.
    access.update_grant('owned', 'bob', None)
    viewer = ScopedReportRepository(repository, access, Principal('bob'), _auth())
    assert viewer.capabilities('owned').to_dict() == {
        'report_id': 'owned', 'role': None, 'can_read': False, 'can_edit': False,
        'can_rename': False, 'can_duplicate': False, 'can_share': False, 'can_delete': False,
        'can_restore': False, 'can_read_history': False, 'can_restore_history': False,
        'can_export': False, 'read_only': False,
    }
    access.update_grant('owned', 'bob', 'viewer')
    viewer = ScopedReportRepository(repository, access, Principal('bob'), _auth())
    assert viewer.capabilities('owned').can_duplicate is False
    with pytest.raises(PermissionError): viewer.duplicate('owned', 'viewer-copy')
    history = repository.list_history('owned')[0]['history_id']
    with pytest.raises(PermissionError): viewer.duplicate_from_history('owned', history, 'viewer-history-copy')
    access.update_grant('owned', 'bob', 'editor')
    assert editor.duplicate('owned', 'editor-copy').report_id == 'editor-copy'
    assert created.report_id == 'owned'


def test_complete_capability_matrix_and_history_mapping(tmp_path: Path) -> None:
    repository, access, owner = _owner(tmp_path)
    owner.create('matrix', model=template_model('blank'))
    access.update_grant('matrix', 'editor', 'editor')
    access.update_grant('matrix', 'viewer', 'viewer')
    auth = _auth()
    principals = {
        'owner': Principal('alice'),
        'editor': Principal('editor'),
        'viewer': Principal('viewer'),
        'unauthorized': Principal('carol'),
        'admin': Principal('root', roles=frozenset({'visembler.admin'})),
        'support': Principal('support', roles=frozenset({'visembler.support'})),
    }
    expected = {
        'owner': (True, True, True, True, True, True, True, True, True, True),
        'editor': (True, True, True, True, False, False, False, True, True, True),
        'viewer': (True, False, False, False, False, False, False, True, False, True),
        'unauthorized': (False,) * 10,
        'admin': (True,) * 10,
        'support': (False,) * 10,
    }
    for name, principal in principals.items():
        projection = ScopedReportRepository(repository, access, principal, auth).capabilities('matrix')
        actual = tuple(getattr(projection, field) for field in (
            'can_read', 'can_edit', 'can_rename', 'can_duplicate', 'can_share',
            'can_delete', 'can_restore', 'can_read_history', 'can_restore_history', 'can_export',
        ))
        assert actual == expected[name], name

    editor = ScopedReportRepository(repository, access, principals['editor'], auth)
    history_id = repository.list_history('matrix')[0]['history_id']
    restored = editor.restore_history('matrix', history_id=history_id, expected_revision=1)
    assert restored.revision == 2


def test_lifecycle_faults_reconcile_without_stale_ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository, access, owner = _owner(tmp_path)
    original_mark_active = access.mark_active

    def fail_after_report_write(report_id: str) -> None:
        raise OSError('injected create finalization failure')

    monkeypatch.setattr(access, 'mark_active', fail_after_report_write)
    with pytest.raises(OSError):
        owner.create('create-fault', model=template_model('blank'))
    monkeypatch.setattr(access, 'mark_active', original_mark_active)
    assert access.reconcile()['blocked'] == []
    assert access.get('create-fault')['state'] == 'active'
    assert access.get('create-fault')['owner'] == 'alice'

    owner.create('trash-fault', model=template_model('blank'))
    original_mark_trashed = access.mark_trashed
    monkeypatch.setattr(access, 'mark_trashed', lambda report_id: (_ for _ in ()).throw(OSError('injected trash finalization failure')))
    with pytest.raises(OSError):
        owner.trash_report('trash-fault', expected_revision=1)
    monkeypatch.setattr(access, 'mark_trashed', original_mark_trashed)
    assert access.reconcile()['blocked'] == []
    assert access.get('trash-fault')['state'] == 'trashed'

    owner.restore('trash-fault')
    original_mark_deleted = access.mark_deleted
    monkeypatch.setattr(access, 'mark_deleted', lambda report_id: (_ for _ in ()).throw(OSError('injected delete finalization failure')))
    with pytest.raises(OSError):
        owner.delete('trash-fault', expected_revision=1)
    monkeypatch.setattr(access, 'mark_deleted', original_mark_deleted)
    assert access.reconcile()['blocked'] == []
    assert access.get('trash-fault')['state'] == 'deleted'
    with pytest.raises(VisualizerContractError):
        owner.create('trash-fault', model=template_model('blank'))


def test_identity_never_reused_across_trash_delete_or_interrupted_create(tmp_path: Path) -> None:
    repository, access, owner = _owner(tmp_path)
    owner.create('stable', model=template_model('blank'))
    owner.trash_report('stable', expected_revision=1)
    with pytest.raises(VisualizerContractError): owner.create('stable', model=template_model('blank'))
    owner.restore('stable')
    owner.delete('stable', expected_revision=1)
    with pytest.raises(VisualizerContractError): owner.create('stable', model=template_model('blank'))

    access.begin_create('interrupted', 'alice')
    report = access.reconcile()
    assert report['blocked'] == []
    assert access.get('interrupted')['state'] == 'aborted'
    with pytest.raises(VisualizerContractError): access.begin_create('interrupted', 'alice')


def test_orphan_governance_is_blocked_and_not_exposed(tmp_path: Path) -> None:
    repository = ReportRepository(tmp_path)
    repository.create('orphan', model=template_model('blank'))
    access = ReportAccessCatalog(tmp_path)
    result = access.reconcile()
    assert result['blocked'] == ['orphan']
    scoped = ScopedReportRepository(repository, access, Principal('alice'), _auth())
    assert scoped.list() == []
    assert not scoped.capabilities('orphan').can_read


def test_audit_uses_request_correlation_and_does_not_store_report_content(tmp_path: Path) -> None:
    _, access, owner = _owner(tmp_path)
    token = set_correlation_id('req-company-001')
    try:
        owner.create('audited', title='Sensitive title', model=canonical_model({'items': [{'id': 'c1', 'type': 'text', 'order': 0, 'text': 'secret engineering data'}]}))
    finally:
        reset_correlation_id(token)
    event = access.audit.read(report_id='audited')[0]
    assert event['correlation_id'] == 'req-company-001'
    raw = (tmp_path / 'audit.jsonl').read_text(encoding='utf-8')
    assert 'secret engineering data' not in raw and 'Sensitive title' not in raw


def test_unauthorized_asset_history_and_export_are_all_denied(tmp_path: Path) -> None:
    repository, access, owner = _owner(tmp_path)
    out=io.BytesIO(); Image.new('RGB',(12,8),(20,30,40)).save(out, format='PNG')
    image='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
    record=owner.create('protected', model=canonical_model({'items':[{'id':'img','type':'image','engine':'ImageMediaEngine','order':0,'src':image}]}))
    asset_id=record.model['items'][0]['asset_id']
    access.update_grant('protected','bob','viewer')
    carol=ScopedReportRepository(repository, access, Principal('carol'), _auth())
    with pytest.raises(PermissionError): carol.read_asset_for_report('protected',asset_id)
    with pytest.raises(PermissionError): carol.list_history('protected')
    with pytest.raises(PermissionError): carol.export('protected')


def test_readiness_performs_real_atomic_write_and_lock_probe(tmp_path: Path) -> None:
    access = ReportAccessCatalog(tmp_path)
    result = access.write_readiness()
    assert result['ok'] is True
    assert not list(tmp_path.glob('.readiness-*'))


@pytest.mark.asyncio
async def test_http_correlation_header_matches_audit_event(tmp_path: Path) -> None:
    _, access, _ = _owner(tmp_path)
    app=FastAPI()

    @app.post('/audit')
    async def audit_route():
        return access.audit.record('report.test', actor=Principal('alice'), report_id='correlated')

    app.add_middleware(CorrelationIdMiddleware)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response=await client.post('/audit')
    correlation=response.headers['x-correlation-id']
    assert response.json()['correlation_id']==correlation
    assert access.audit.read(report_id='correlated')[-1]['correlation_id']==correlation


def test_role_only_admin_is_global_but_support_is_diagnostics_only(tmp_path: Path) -> None:
    repository, access, owner = _owner(tmp_path)
    owner.create('private', model=template_model('blank'))
    auth = AuthorizationModel({
        'visembler.admin': RoleDefinition('visembler.admin', frozenset({'administration', 'report.create', *CAPABILITY_ACTIONS})),
        'visembler.support': RoleDefinition('visembler.support', frozenset({'diagnostics.read'})),
    })
    admin = ScopedReportRepository(repository, access, Principal('root', roles=frozenset({'visembler.admin'})), auth)
    support = ScopedReportRepository(repository, access, Principal('support', roles=frozenset({'visembler.support'})), auth)
    assert [item.report_id for item in admin.list()] == ['private']
    assert support.list() == []


def test_legacy_report_migration_requires_explicit_owner_in_production(tmp_path: Path) -> None:
    repository=ReportRepository(tmp_path)
    repository.create('legacy', model=template_model('blank'))
    repository.create('legacy-trash', model=template_model('blank'))
    repository.trash_report('legacy-trash', expected_revision=1)
    access=ReportAccessCatalog(tmp_path)
    with pytest.raises(VisualizerContractError):
        access.migrate(['legacy'], owner=None, production=True)
    assert access.migrate(['legacy', 'legacy-trash'], owner='migration-admin', production=True, trashed_ids={'legacy-trash'})==2
    assert access.get('legacy')['owner']=='migration-admin'
    assert access.get('legacy-trash')['state']=='trashed'
    assert access.reconcile()['blocked']==[]
