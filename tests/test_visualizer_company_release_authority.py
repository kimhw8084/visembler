from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def _module():
    path=ROOT/'scripts/release_checks/run_company_production_readiness.py'
    spec=importlib.util.spec_from_file_location('company_readiness',path)
    module=importlib.util.module_from_spec(spec); assert spec and spec.loader
    spec.loader.exec_module(module); return module


def _aggregator():
    path=ROOT/'scripts/release_checks/run_company_release_aggregator.py'
    spec=importlib.util.spec_from_file_location('company_aggregator',path)
    module=importlib.util.module_from_spec(spec); assert spec and spec.loader
    spec.loader.exec_module(module); return module


def test_target_receipt_requires_every_gate_and_artifact() -> None:
    module=_module(); sha=module.candidate_sha(); manifest,_=module.source_manifest(); deps=module.dependency_fingerprint()
    receipt={
        'schema_version':1,'candidate_sha':sha,'source_manifest_hash':manifest,
        'production_dependency_fingerprint':deps,'configuration_fingerprint':'safe',
        'results':{gate:'PASS' for gate in module.TARGET_GATES},
        'gates':{gate:'PASS' for gate in module.TARGET_GATES},
        'created_at':'2026-09-08T12:00:00+00:00',
        'artifact_manifest':{name: __import__('hashlib').sha256((ROOT/name).read_bytes()).hexdigest() for name in module.TARGET_ARTIFACTS},
    }
    valid,errors=module.validate_target_receipt(receipt,sha=sha,manifest_hash=manifest,dependency_hash=deps)
    assert valid, errors
    receipt['gates'].pop('session')
    valid,errors=module.validate_target_receipt(receipt,sha=sha,manifest_hash=manifest,dependency_hash=deps)
    assert not valid and 'gate_receipt:session' in errors


def test_release_aggregator_rejects_model_only_multi_user_receipt(tmp_path: Path) -> None:
    module=_aggregator(); timestamp='2026-09-08T12:00:00+00:00'; sha=module._head()
    for name in module.REQUIRED:
        value={'status':'PASS','candidate_sha':sha,'created_at':timestamp}
        if name == 'multi_user': value['browser_mode']='model-boundary'
        (tmp_path/f'{name}.json').write_text(json.dumps(value),encoding='utf-8')
    output=tmp_path/'aggregate.json'
    assert module.aggregate(tmp_path,output) == 2
    receipt=json.loads(output.read_text(encoding='utf-8'))
    assert 'browser_mode:multi_user' in receipt['errors']
