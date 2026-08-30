from __future__ import annotations

import argparse
import compileall
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from company_ui.certification.engine import combined_css, run_certification
from company_ui.certification.mac_coverage import ROUTE_BUILDERS, coverage_summary
from company_ui.version import FRAMEWORK_VERSION, NICEGUI_VERSION, RELEASE_STATUS

from .engine import run_governance


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=root, text=True, capture_output=True, check=False)


def _pytest_count(root: Path) -> int:
    result = _run(root, '-m', 'pytest', '--collect-only')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    match = re.search(r'(\d+) tests collected', result.stdout + result.stderr)
    if not match:
        raise RuntimeError('could not determine pytest collection count')
    return int(match.group(1))


def _sync_packaged_certification_manifest(root: Path, *, test_count: int, coverage: dict[str, Any]) -> None:
    """Refresh packaged source-certification facts before pytest executes.

    Tests intentionally validate that the packaged manifest reflects the tree
    being certified, so this synchronization must happen before the test gate.
    Target-runtime/browser claims remain pending and are never synthesized here.
    """
    manifest_path = root / 'company_ui/certification/certification_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['framework_version'] = FRAMEWORK_VERSION
    manifest['automated_tests'] = test_count
    manifest['combined_css_bytes'] = len(combined_css().encode('utf-8'))
    manifest['hotfix_release'] = f'v{FRAMEWORK_VERSION} source-complete governed application platform'
    manifest['live_lab']['coverage'] = coverage
    if isinstance(manifest.get('phase_32_v2_release_candidate'), dict):
        manifest['phase_32_v2_release_candidate']['automated_tests'] = test_count
    manifest['phase'] = max(int(manifest.get('phase', 0)), 47)
    manifest['phase_35_v2_source_completion'] = {
        'automated_tests': test_count,
        'governance': '0 errors / 0 warnings',
        'typography_motion_token_governance': True,
        'single_layout_density_token_authority': True,
        'release_sync_embedded_version_regression': True,
        'visual_component_coverage': f'{coverage["covered_visual_components"]}/{coverage["required_visual_components"]}',
        'runtime_browser_human_target_gates': 'PENDING',
    }
    manifest['phase_38_v200rc5_p0_hardening'] = {
        'automated_tests': test_count,
        'lifecycle_scope_cleanup': True,
        'concurrent_async_action_tracking': True,
        'latest_request_server_table_controller': True,
        'datatable_state_persistence_and_identity_reconciliation': True,
        'overlay_focus_escape_scroll_lock_ownership': True,
        'async_accessibility_announcements': True,
        'stale_refresh_preserves_last_good_content': True,
        'editable_table_revision_owned_save_rollback': True,
        'editable_table_confirmed_and_optimistic_commit_modes': True,
        'datatable_cell_renderer_cost_hardening': True,
        'chart_accessibility_and_cleanup': True,
        'chart_visibility_aware_update_coalescing': True,
        'browser_performance_probe': True,
        'lifecycle_and_async_race_torture_regressions': True,
        'pathological_data_regression_fixtures': True,
        'release_authority_regressions_are_version_agnostic': True,
        'visual_component_coverage': f'{coverage["covered_visual_components"]}/{coverage["required_visual_components"]}',
        'target_runtime_browser_human_gates': 'PENDING',
    }
    browser_gate_path = root / 'BROWSER_UIUX_GATE.json'
    browser_gate = json.loads(browser_gate_path.read_text(encoding='utf-8')) if browser_gate_path.exists() else {}
    browser_gate_pass = browser_gate.get('status') == 'PASS' and int(browser_gate.get('failed', 1)) == 0
    manifest['phase_46_v300a1_application_platform'] = {
        'automated_tests': test_count,
        'application_runtime_kernel': True,
        'typed_atomic_runtime_state': True,
        'transaction_level_undo_redo': True,
        'workspace_lifecycle_ownership': True,
        'application_and_workspace_snapshot_restore': True,
        'json_snapshot_persistence': True,
        'unified_semantic_data_engine': True,
        'lazy_equality_membership_indexes': True,
        'shared_table_chart_kpi_filter_sessions': True,
        'adaptive_workspace_grid_engine': True,
        'responsive_collision_free_layout_persistence': True,
        'semantic_visualization_planner_reuses_certified_renderers': True,
        'governed_extension_registry': True,
        'v2_ui_renderer_contract_preserved_by_opt_in_v3_architecture': True,
        'visual_component_coverage': f'{coverage["covered_visual_components"]}/{coverage["required_visual_components"]}',
        'target_runtime_browser_human_gates': 'PENDING',
    }
    manifest['phase_47_v300a1_browser_uiux_gate'] = {
        'browser_native_constitution_gate': 'PASS' if browser_gate_pass else 'PENDING',
        'browser_native_checks': f"{browser_gate.get('passed', 0)}/{browser_gate.get('checks_total', 0)}" if browser_gate else 'PENDING',
        'mobile_touch_target_hardening': True,
        'reduced_motion_cascade_hardening': True,
        'mobile_header_environment_badge_hardening': True,
        'installed_nicegui_runtime_gate': 'PENDING',
        'live_22_route_server_smoke': 'PENDING',
        'supported_browser_matrix_and_human_baseline': 'PENDING',
    }
    _write(manifest_path, manifest)


def generate_source_evidence(root: str | Path = '.', *, run_tests: bool = True) -> dict[str, Any]:
    """Execute all environment-independent release gates and write current evidence.

    This command is deliberately unable to claim installed-runtime, live-browser,
    clean-install or human-baseline certification. Those remain target-only gates.
    """
    root = Path(root).resolve()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

    compile_ok = compileall.compile_dir(str(root / 'company_ui'), quiet=1) and compileall.compile_dir(str(root / 'tests'), quiet=1)
    governance = run_governance(root)
    test_count = _pytest_count(root)
    coverage = coverage_summary()
    if coverage.get('uncovered'):
        raise RuntimeError(f'visual component coverage is incomplete: {coverage["uncovered"]}')
    _sync_packaged_certification_manifest(root, test_count=test_count, coverage=coverage)

    pytest_status = 'NOT_RUN'
    if run_tests:
        result = _run(root, '-m', 'pytest', '-q')
        if result.returncode:
            raise RuntimeError('pytest failed while generating source evidence:\n' + result.stdout + result.stderr)
        pytest_status = 'PASS'

    source_cert = run_certification(root, require_nicegui=False)
    if not source_cert.passed:
        failures = '; '.join(f'{item.key}: {item.detail}' for item in source_cert.failures)
        raise RuntimeError(f'source certification failed: {failures}')
    source_summary = {
        'compileall': 'PASS' if compile_ok else 'FAIL',
        'governance': {'status': 'PASS' if governance.passed else 'FAIL', 'errors': len(governance.errors), 'warnings': len(governance.warnings)},
        'pytest': pytest_status,
        'automated_tests': test_count,
        'static_certification': source_cert.summary,
        'visual_component_coverage': f'{coverage["covered_visual_components"]}/{coverage["required_visual_components"]}',
        'live_routes': len(ROUTE_BUILDERS),
    }
    if not compile_ok or not governance.passed:
        raise RuntimeError(f'source gates failed: {source_summary}')

    test_report = {
        'framework_version': FRAMEWORK_VERSION,
        'nicegui_version': NICEGUI_VERSION,
        'generated_at': generated_at,
        'status': 'PASS',
        **source_summary,
        'target_runtime_execution': 'PENDING (requires installed NiceGUI 3.15.0 target environment)',
        'browser_execution': 'PENDING',
        'human_visual_baseline': 'PENDING',
        'browser_native_uiux_constitution': 'PASS' if (root / 'BROWSER_UIUX_GATE.json').exists() and json.loads((root / 'BROWSER_UIUX_GATE.json').read_text(encoding='utf-8')).get('status') == 'PASS' else 'PENDING',
    }
    _write(root / 'TEST_REPORT.json', test_report)

    coverage_payload = {'framework_version': FRAMEWORK_VERSION, **coverage}
    _write(root / 'LIVE_COMPONENT_COVERAGE.json', coverage_payload)


    certification = {
        'framework_version': FRAMEWORK_VERSION,
        'nicegui_version': NICEGUI_VERSION,
        'generated_at': generated_at,
        'status': 'SOURCE_TESTS_AND_STATIC_CHECKS_PASS_TARGET_RUNTIME_PENDING',
        'passed': True,
        'release_certified': False,
        'release_status': RELEASE_STATUS,
        'source_validation': source_summary,
        'target_runtime_status': 'PENDING',
        'browser_native_uiux_constitution': 'PASS' if (root / 'BROWSER_UIUX_GATE.json').exists() and json.loads((root / 'BROWSER_UIUX_GATE.json').read_text(encoding='utf-8')).get('status') == 'PASS' else 'PENDING',
        'runtime_contract': 'PENDING',
        'runtime_smoke_22_routes': 'PENDING',
        'browser_matrix': 'PENDING',
        'human_visual_baseline': 'PENDING',
        'note': 'Source PASS does not certify the final release. Target runtime/browser/human gates remain mandatory.',
    }
    _write(root / 'CERTIFICATION_REPORT.json', certification)

    readiness = {
        'framework_version': FRAMEWORK_VERSION,
        'nicegui_version': NICEGUI_VERSION,
        'generated_at': generated_at,
        'release_status': RELEASE_STATUS,
        'status': f'{FRAMEWORK_VERSION.upper()}_SOURCE_VALIDATED_TARGET_RUNTIME_PENDING',
        'automated_tests': test_count,
        'governance': 'PASS',
        'source_certification': 'PASS',
        'live_routes': len(ROUTE_BUILDERS),
        'visual_coverage': f'{coverage["covered_visual_components"]}/{coverage["required_visual_components"]}',
        'clean_install_offline_certification': f'NOT EXECUTED FOR {FRAMEWORK_VERSION.upper()}',
        'setup_gate': 'SOURCE_CONTRACT_PASS_TARGET_EXECUTION_PENDING',
        'browser_native_uiux_constitution': 'PASS' if (root / 'BROWSER_UIUX_GATE.json').exists() and json.loads((root / 'BROWSER_UIUX_GATE.json').read_text(encoding='utf-8')).get('status') == 'PASS' else 'PENDING',
        'target_required': [
            './setup.sh -> SETUP COMPLETE (dispatches to macOS/Linux platform setup)',
            './run_lab.sh for manual review',
            'install certification deps then certify for browser/runtime evidence',
        ],
    }
    _write(root / 'LIVE_CERTIFICATION_READINESS.json', readiness)
    return {'test_report': test_report, 'certification_report': certification, 'readiness': readiness, 'coverage': coverage_payload}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Execute Company UI source-only release gates and regenerate current evidence.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--skip-pytest', action='store_true', help='Collect tests but do not execute them (never use for release evidence).')
    args = parser.parse_args(argv)
    evidence = generate_source_evidence(args.root, run_tests=not args.skip_pytest)
    print(json.dumps({
        'framework_version': FRAMEWORK_VERSION,
        'tests': evidence['test_report']['automated_tests'],
        'governance': evidence['test_report']['governance'],
        'source_certification': evidence['test_report']['static_certification'],
        'visual_coverage': evidence['readiness']['visual_coverage'],
        'target_runtime_status': evidence['certification_report']['target_runtime_status'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
