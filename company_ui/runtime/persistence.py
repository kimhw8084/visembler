from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

from company_ui.data_engine import DataSessionSnapshot, FilterClause, FilterOperation
from company_ui.workspace import GridPlacement, PanelSpec, WorkspaceBreakpoint, WorkspaceLayoutSnapshot

from .kernel import ApplicationSnapshot, StateSnapshot, WorkspaceSnapshot

_SCHEMA_VERSION = 1


def _filter_to_dict(clause: FilterClause) -> dict[str, Any]:
    return {
        'field': clause.field,
        'operation': clause.operation.value,
        'value': deepcopy(clause.value),
        'value2': deepcopy(clause.value2),
        'filter_id': clause.filter_id,
    }


def _filter_from_dict(payload: Mapping[str, Any]) -> FilterClause:
    return FilterClause(
        field=str(payload['field']),
        operation=FilterOperation(str(payload['operation'])),
        value=deepcopy(payload.get('value')),
        value2=deepcopy(payload.get('value2')),
        filter_id=payload.get('filter_id'),
    )


def _panel_to_dict(panel: PanelSpec) -> dict[str, Any]:
    return {
        'panel_id': panel.panel_id,
        'preferred_columns': panel.preferred_columns,
        'preferred_rows': panel.preferred_rows,
        'min_columns': panel.min_columns,
        'max_columns': panel.max_columns,
        'min_rows': panel.min_rows,
        'max_rows': panel.max_rows,
        'phone_full_width': panel.phone_full_width,
        'locked': panel.locked,
        'metadata': deepcopy(dict(panel.metadata)),
    }


def _panel_from_dict(payload: Mapping[str, Any]) -> PanelSpec:
    return PanelSpec(
        panel_id=str(payload['panel_id']),
        preferred_columns=int(payload.get('preferred_columns', 6)),
        preferred_rows=int(payload.get('preferred_rows', 4)),
        min_columns=int(payload.get('min_columns', 2)),
        max_columns=None if payload.get('max_columns') is None else int(payload['max_columns']),
        min_rows=int(payload.get('min_rows', 2)),
        max_rows=None if payload.get('max_rows') is None else int(payload['max_rows']),
        phone_full_width=bool(payload.get('phone_full_width', True)),
        locked=bool(payload.get('locked', False)),
        metadata=deepcopy(dict(payload.get('metadata', {}))),
    )


def _placement_to_dict(item: GridPlacement) -> dict[str, Any]:
    return {
        'panel_id': item.panel_id,
        'breakpoint': item.breakpoint.value,
        'column': item.column,
        'row': item.row,
        'column_span': item.column_span,
        'row_span': item.row_span,
    }


def _placement_from_dict(payload: Mapping[str, Any]) -> GridPlacement:
    return GridPlacement(
        panel_id=str(payload['panel_id']),
        breakpoint=WorkspaceBreakpoint(str(payload['breakpoint'])),
        column=int(payload['column']),
        row=int(payload['row']),
        column_span=int(payload['column_span']),
        row_span=int(payload['row_span']),
    )


def workspace_snapshot_to_dict(snapshot: WorkspaceSnapshot) -> dict[str, Any]:
    return {
        'schema_version': _SCHEMA_VERSION,
        'workspace_id': snapshot.workspace_id,
        'state': {
            'revision': snapshot.state.revision,
            'values': deepcopy(dict(snapshot.state.values)),
        },
        'layout': {
            'schema_version': snapshot.layout.schema_version,
            'revision': snapshot.layout.revision,
            'panels': [_panel_to_dict(item) for item in snapshot.layout.panels],
            'placements': [_placement_to_dict(item) for item in snapshot.layout.placements],
        },
        'data_sessions': {
            session_id: {
                'dataset_key': dataset_key,
                'revision': session.revision,
                'filters': [_filter_to_dict(item) for item in session.filters],
                'search': session.search,
            }
            for session_id, (dataset_key, session) in snapshot.data_sessions.items()
        },
    }


def workspace_snapshot_from_dict(payload: Mapping[str, Any]) -> WorkspaceSnapshot:
    if int(payload.get('schema_version', 0)) != _SCHEMA_VERSION:
        raise ValueError(f'unsupported runtime snapshot schema {payload.get("schema_version")!r}')
    state_payload = payload['state']; layout_payload = payload['layout']
    if not isinstance(state_payload, Mapping) or not isinstance(layout_payload, Mapping):
        raise TypeError('workspace snapshot state/layout must be mappings')
    data_sessions: dict[str, tuple[str, DataSessionSnapshot]] = {}
    raw_sessions = payload.get('data_sessions', {})
    if not isinstance(raw_sessions, Mapping):
        raise TypeError('workspace snapshot data_sessions must be a mapping')
    for session_id, raw in raw_sessions.items():
        if not isinstance(raw, Mapping):
            raise TypeError('data session snapshot must be a mapping')
        data_sessions[str(session_id)] = (
            str(raw['dataset_key']),
            DataSessionSnapshot(
                revision=int(raw.get('revision', 0)),
                filters=tuple(_filter_from_dict(item) for item in raw.get('filters', ())),
                search=str(raw.get('search', '')),
            ),
        )
    return WorkspaceSnapshot(
        workspace_id=str(payload['workspace_id']),
        state=StateSnapshot(
            revision=int(state_payload.get('revision', 0)),
            values=deepcopy(dict(state_payload.get('values', {}))),
        ),
        layout=WorkspaceLayoutSnapshot(
            schema_version=int(layout_payload.get('schema_version', 0)),
            revision=int(layout_payload.get('revision', 0)),
            panels=tuple(_panel_from_dict(item) for item in layout_payload.get('panels', ())),
            placements=tuple(_placement_from_dict(item) for item in layout_payload.get('placements', ())),
        ),
        data_sessions=data_sessions,
    )


def application_snapshot_to_dict(snapshot: ApplicationSnapshot) -> dict[str, Any]:
    return {
        'schema_version': _SCHEMA_VERSION,
        'state': {
            'revision': snapshot.state.revision,
            'values': deepcopy(dict(snapshot.state.values)),
        },
        'workspaces': [workspace_snapshot_to_dict(item) for item in snapshot.workspaces],
    }


def application_snapshot_from_dict(payload: Mapping[str, Any]) -> ApplicationSnapshot:
    if int(payload.get('schema_version', 0)) != _SCHEMA_VERSION:
        raise ValueError(f'unsupported runtime snapshot schema {payload.get("schema_version")!r}')
    state_payload = payload['state']
    if not isinstance(state_payload, Mapping):
        raise TypeError('application snapshot state must be a mapping')
    workspaces = payload.get('workspaces', ())
    if not isinstance(workspaces, (list, tuple)):
        raise TypeError('application snapshot workspaces must be a sequence')
    return ApplicationSnapshot(
        state=StateSnapshot(
            revision=int(state_payload.get('revision', 0)),
            values=deepcopy(dict(state_payload.get('values', {}))),
        ),
        workspaces=tuple(workspace_snapshot_from_dict(item) for item in workspaces),
    )


def serialize_application_snapshot(snapshot: ApplicationSnapshot, *, indent: int | None = None) -> str:
    return json.dumps(application_snapshot_to_dict(snapshot), indent=indent, sort_keys=True, ensure_ascii=False)


def deserialize_application_snapshot(value: str) -> ApplicationSnapshot:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise TypeError('application snapshot JSON must contain an object')
    return application_snapshot_from_dict(payload)


__all__ = [
    'application_snapshot_from_dict', 'application_snapshot_to_dict', 'deserialize_application_snapshot',
    'serialize_application_snapshot', 'workspace_snapshot_from_dict', 'workspace_snapshot_to_dict',
]
