from __future__ import annotations

from pathlib import Path


def test_quality_workflow_runs_product_gates_without_non_blocking_failures() -> None:
    workflow = (Path('.github') / 'workflows' / 'quality.yml').read_text(encoding='utf-8')
    for job in ('production-install-and-startup:', 'tests:', 'authoring-modules:', 'integrity:', 'browser-smoke:'):
        assert job in workflow
    for gate in ('python -m pip install --no-cache-dir .', 'Production import smoke', 'Visembler startup smoke', 'python -m pytest', 'tests/test_visualizer_authoring_p0.py', 'Golden Connector hash', 'Build wheel', 'Verify Visembler package content', 'playwright install --with-deps chromium'):
        assert gate in workflow
    assert 'continue-on-error' not in workflow
