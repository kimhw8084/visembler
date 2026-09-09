from __future__ import annotations

from pathlib import Path

import pytest

from company_ui.data_engine import DataQuery, FilterClause, FilterOperation, SortClause
from company_ui.products.visualizer.dataset_resources import DatasetResourceStore, ScopedDatasetRepository
from company_ui.products.visualizer.domain import ReportNotFoundError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import ReportAccessCatalog, ReportRole, ScopedReportRepository
from company_ui.products.visualizer.migrations import migrate_report_model
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.templates import template_model
from company_ui.security import AuthorizationModel, Principal


def _scoped(repository: ReportRepository, access: ReportAccessCatalog, subject: str, *permissions: str) -> ScopedReportRepository:
    return ScopedReportRepository(repository, access, Principal(subject, permissions=frozenset(permissions)), AuthorizationModel())


def _fields() -> list[dict[str, object]]:
    return [
        {'id': 'tool', 'name': 'Tool', 'type': 'categorical', 'semantic_tags': ['tool']},
        {'id': 'yield', 'name': 'Yield', 'type': 'number', 'semantic_tags': ['value']},
    ]


def _rows() -> list[list[object]]:
    return [['T01', 0], ['T02', 0.91], ['T03', None]]


def test_report_model_migration_is_explicit_idempotent_and_rejects_future_versions() -> None:
    migrated = migrate_report_model({'items': [], 'groups': {}})
    assert migrated['schema_version'] == 1
    assert migrate_report_model(migrated) == migrated
    with pytest.raises(ValueError, match='unsupported report model schema_version'):
        migrate_report_model({'schema_version': 99})
    with pytest.raises(VisualizerContractError, match='unsupported report model schema_version'):
        canonical_model({'schema_version': 99})


def test_external_dataset_resource_is_revisioned_and_queried_by_existing_data_engine(tmp_path: Path) -> None:
    store = DatasetResourceStore(tmp_path)
    created = store.create(owner='alice', name='Weekly yield', fields=_fields(), rows=_rows(), provenance='fixture')
    assert created['row_count'] == 3 and created['revision'] == 1
    session = store.session(created['dataset_id'])
    result = session.query(DataQuery(filters=(FilterClause('tool', FilterOperation.EQUALS, 'T01'),), sorts=(SortClause('tool'),)))
    assert result.rows == ({'tool': 'T01', 'yield': 0},)
    grouped = session.aggregate(dimensions=('tool',), metrics=('yield',))
    assert grouped.rows[0]['yield'] == 0
    replaced = store.replace(created['dataset_id'], fields=_fields(), rows=_rows() + [['T04', 0.87]], expected_revision=1)
    assert replaced['revision'] == 2 and store.get(created['dataset_id'])['row_count'] == 4
    assert store.get(created['dataset_id'], revision=1)['row_count'] == 3
    with pytest.raises(VisualizerContractError, match='stale dataset revision'):
        store.replace(created['dataset_id'], fields=_fields(), rows=_rows(), expected_revision=1)


def test_dataset_access_is_report_scoped_and_referenced_resources_cannot_be_deleted(tmp_path: Path) -> None:
    repository = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repository)
    owner = _scoped(repository, access, 'alice', 'report.create')
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='Protected data', fields=_fields(), rows=_rows())
    model = canonical_model({'datasets': [{'id': 'inline-dataset', 'resource_id': resource['dataset_id'], 'external': True,
                                           'fields': resource['schema'], 'rows': [], 'row_count': resource['row_count']}],
                             'items': [{'id': 'table-1', 'type': 'table', 'engine': 'TableEngine', 'order': 0,
                                        'dataset_id': 'inline-dataset', 'mapping': {'category': 'tool', 'value': 'yield'}}]})
    owner.create('protected-data', model=model)
    access.grant('protected-data', owner.principal, 'bob', ReportRole.VIEWER)
    viewer = _scoped(repository, access, 'bob')
    viewer_data = ScopedDatasetRepository(store, viewer)
    assert viewer_data.get_for_report('protected-data', 'inline-dataset')['row_count'] == 3
    assert viewer_data.session_for_report('protected-data', 'inline-dataset').query().total == 3
    with pytest.raises(PermissionError):
        ScopedDatasetRepository(store, _scoped(repository, access, 'mallory'),).get_for_report('protected-data', 'inline-dataset')
    with pytest.raises(PermissionError):
        viewer_data.replace_for_report('protected-data', 'inline-dataset', fields=_fields(), rows=_rows())
    with pytest.raises(VisualizerContractError, match='still referenced'):
        owner_data = ScopedDatasetRepository(store, owner)
        owner_data.delete_for_report('protected-data', 'inline-dataset')


def test_external_dataset_hydration_keeps_report_json_compact_and_preserves_typed_zero(tmp_path: Path) -> None:
    repository = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repository)
    owner = _scoped(repository, access, 'alice', 'report.create')
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='Compact source', fields=_fields(), rows=_rows())
    model = canonical_model({'datasets': [{'id': 'd1', 'resource_id': resource['dataset_id'], 'external': True,
                                           'fields': resource['schema'], 'rows': [], 'row_count': resource['row_count']}],
                             'items': []})
    record = owner.create('compact', model=model)
    hydrated = ScopedDatasetRepository(store, owner).hydrate_model(record.report_id, record.model)
    dataset = hydrated['datasets'][0]
    assert dataset['rows'][0][1] == 0
    assert dataset['row_count'] == 3
    assert record.model['datasets'][0]['rows'] == []


def test_dataset_reconciliation_blocks_missing_revision_and_gc_preserves_tombstone(tmp_path: Path) -> None:
    store = DatasetResourceStore(tmp_path)
    resource = store.create(owner='alice', name='Lifecycle', fields=_fields(), rows=_rows())
    store._resource_path(resource['dataset_id'], 1).unlink()
    result = store.reconcile()
    assert result['ok'] is False
    assert resource['dataset_id'] in result['blocked']
    with pytest.raises(ReportNotFoundError):
        store.get(resource['dataset_id'])

    fresh = store.create(owner='alice', name='Garbage', fields=_fields(), rows=_rows())
    store.delete(fresh['dataset_id'])
    assert store.collect_garbage([fresh['dataset_id']]) == []
    assert store.collect_garbage() == [fresh['dataset_id']]
    with pytest.raises(VisualizerContractError, match='already exists'):
        store.create(owner='alice', name='Reuse', fields=_fields(), rows=_rows(), dataset_id=fresh['dataset_id'])


def test_governance_migration_populates_summary_for_new_report(tmp_path: Path) -> None:
    repository = ReportRepository(tmp_path)
    access = ReportAccessCatalog(repository)
    record = repository.create('new-report', title='Newest report', model=template_model('blank'))
    access.migrate([record], owner_subject='alice', require_explicit_owner=True)
    principal = _scoped(repository, access, 'alice')
    assert principal.list_summaries()[0]['report_id'] == record.report_id
    assert principal.list_summaries()[0]['title'] == 'Newest report'
