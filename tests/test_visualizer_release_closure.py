from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _contracts_module():
    path = ROOT / 'scripts/release_checks/run_repository_contracts.py'
    spec = importlib.util.spec_from_file_location('visualizer_repository_contracts', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_repository_contract_receipt_proves_current_checkout(tmp_path: Path):
    module = _contracts_module()
    output = tmp_path / 'repository-contracts.json'
    assert module.run(output) == 0
    receipt = json.loads(output.read_text(encoding='utf-8'))
    assert receipt['status'] == 'PASS'
    assert receipt['managed_target_status'] == 'PENDING'
    assert all(check['status'] == 'PASS' for check in receipt['checks'].values())


def test_native_verifier_requires_repository_and_company_local_gates():
    source = (ROOT / 'scripts/verify_release.py').read_text(encoding='utf-8')
    for gate in ('repository-contracts', 'company-boundary-model', 'company-boundary-browser', 'company-readiness-local', 'company-capacity'):
        assert gate in source
    assert (ROOT / 'scripts/release_checks/run_company_boundary_browser_gate.py').is_file()
    assert "'managed_target_status': 'PENDING'" in source


def test_archive_source_identity_requires_explicit_candidate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from scripts.release_checks.source_identity import candidate_sha

    monkeypatch.delenv('VISSEMBLER_CANDIDATE_SHA', raising=False)
    with pytest.raises(RuntimeError, match='VISSEMBLER_CANDIDATE_SHA'):
        candidate_sha(tmp_path)
    expected = 'candidate-test-sha'
    monkeypatch.setenv('VISSEMBLER_CANDIDATE_SHA', expected)
    assert candidate_sha(tmp_path) == expected
