from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
AUTHORING_SCHEMA = 'authoring-p0-v1'
MODEL_MAX_BYTES = 1_500_000
BRIDGE_MAX_BYTES = 2_000_000
IMAGE_EMBED_MAX_BYTES = 750_000
ALLOWED_MODES = {'smart', 'guided', 'free'}

class VisualizerError(RuntimeError): pass
class VisualizerContractError(VisualizerError): pass
class RevisionConflictError(VisualizerError):
    def __init__(self, expected: int, received: int):
        super().__init__(f'stale revision: expected {expected}, received {received}')
        self.expected=expected; self.received=received
class ReportNotFoundError(VisualizerError): pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable(value: Any) -> Any:
    if isinstance(value, list): return [_stable(v) for v in value]
    if isinstance(value, Mapping): return {str(k): _stable(value[k]) for k in sorted(value)}
    return value


def stable_json(value: Any) -> str:
    return json.dumps(_stable(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode('utf-8')).hexdigest()


def canonical_model(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    src=dict(value or {})
    items=src.get('items') if isinstance(src.get('items'), list) else []
    groups=src.get('groups') if isinstance(src.get('groups'), Mapping) else {}
    mode=src.get('mode') if src.get('mode') in ALLOWED_MODES else 'guided'
    next_id=src.get('nextId') if isinstance(src.get('nextId'), int) and src.get('nextId') > 0 else _infer_next_id(items)
    datasets=src.get('datasets') if isinstance(src.get('datasets'), list) else []
    model={'schema_version':SCHEMA_VERSION,'authoring_schema':AUTHORING_SCHEMA,'datasets':json.loads(json.dumps(datasets)),'items':json.loads(json.dumps(items)),'groups':json.loads(json.dumps(groups)),'mode':mode,'layoutPreset':str(src.get('layoutPreset') or 'editorial'),'crossFilter':src.get('crossFilter'),'nextId':next_id}
    validate_model(model)
    encoded=stable_json(model).encode('utf-8')
    if len(encoded) > MODEL_MAX_BYTES: raise VisualizerContractError(f'report model exceeds {MODEL_MAX_BYTES} bytes')
    return model


def _infer_next_id(items: list[Any]) -> int:
    found=[]
    for row in items:
        if isinstance(row, Mapping):
            raw=str(row.get('id') or '')
            if raw.startswith('c') and raw[1:].isdigit(): found.append(int(raw[1:]))
    return max(20, max(found, default=19)+1)


def validate_model(model: Mapping[str, Any]) -> None:
    required=('schema_version','authoring_schema','datasets','items','groups','mode','layoutPreset','crossFilter','nextId')
    for key in required:
        if key not in model: raise VisualizerContractError(f'missing model field: {key}')
    if model['schema_version'] != SCHEMA_VERSION: raise VisualizerContractError(f'unsupported schema_version {model["schema_version"]!r}')
    if model['mode'] not in ALLOWED_MODES: raise VisualizerContractError(f'unsupported mode {model["mode"]!r}')
    if model['authoring_schema'] != AUTHORING_SCHEMA: raise VisualizerContractError(f'unsupported authoring_schema {model["authoring_schema"]!r}')
    if not isinstance(model['items'], list) or not isinstance(model['groups'], Mapping) or not isinstance(model['datasets'], list): raise VisualizerContractError('invalid items/groups/datasets')
    if not isinstance(model['nextId'], int) or model['nextId'] < 1: raise VisualizerContractError('nextId must be positive integer')
    dataset_ids=set()
    for dataset in model['datasets']:
        if not isinstance(dataset, Mapping): raise VisualizerContractError('every dataset must be object')
        dataset_id=dataset.get('id')
        if not isinstance(dataset_id, str) or not dataset_id or dataset_id in dataset_ids: raise VisualizerContractError('dataset requires unique id')
        if not isinstance(dataset.get('fields'), list) or not isinstance(dataset.get('rows'), list): raise VisualizerContractError(f'dataset {dataset_id} requires fields/rows')
        dataset_ids.add(dataset_id)
    ids=set()
    for item in model['items']:
        if not isinstance(item, Mapping): raise VisualizerContractError('every item must be object')
        id_=item.get('id'); type_=item.get('type')
        if not isinstance(id_, str) or not id_: raise VisualizerContractError('item requires id')
        if id_ in ids: raise VisualizerContractError(f'duplicate item id: {id_}')
        ids.add(id_)
        if not isinstance(type_, str) or not type_: raise VisualizerContractError(f'item {id_} requires type')
        if item.get('dataset_id') is not None and (item.get('dataset_id') not in dataset_ids or not isinstance(item.get('mapping'), Mapping)): raise VisualizerContractError(f'item {id_} has invalid dataset binding')
        if not isinstance(item.get('order'), (int,float)): raise VisualizerContractError(f'item {id_} requires numeric order')
        for key in ('x','y','w','h','weight','z'):
            if key in item and item[key] is not None and not isinstance(item[key], (int,float)): raise VisualizerContractError(f'item {id_}.{key} must be numeric')


def validate_report_id(report_id: str) -> str:
    text=str(report_id).strip()
    if not text or len(text) > 96 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in text):
        raise VisualizerContractError('invalid report id')
    return text


@dataclass(frozen=True)
class ReportRecord:
    report_id: str
    revision: int
    title: str
    model: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    commit_ids: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {'report_id':self.report_id,'revision':self.revision,'title':self.title,'model':dict(self.model),'metadata':dict(self.metadata),'commit_ids':list(self.commit_ids),'created_at':self.created_at,'updated_at':self.updated_at,'fingerprint':fingerprint(self.model)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> 'ReportRecord':
        return cls(report_id=validate_report_id(str(value['report_id'])),revision=int(value.get('revision',1)),title=str(value.get('title') or 'Untitled report'),model=canonical_model(value.get('model') if isinstance(value.get('model'),Mapping) else {}),metadata=dict(value.get('metadata') or {}),commit_ids=tuple(str(x) for x in value.get('commit_ids',[]) if isinstance(x,str))[-256:],created_at=str(value.get('created_at') or utc_now()),updated_at=str(value.get('updated_at') or utc_now()))
