from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'company_ui' / 'products' / 'visualizer'
QUALITY_WORKFLOW = ROOT / '.github' / 'workflows' / 'quality.yml'


def test_visualizer_product_has_canonical_in_repo_application_bootstrap():
    text = (PRODUCT / 'cli.py').read_text(encoding='utf-8')
    for token in (
        'def build_application',
        'build_runtime_adapter',
        'ReportRepository',
        'register_visualizer',
    ):
        assert token in text


def test_visualizer_main_runs_through_the_resolved_runtime_adapter():
    text = (PRODUCT / 'cli.py').read_text(encoding='utf-8')
    assert 'adapter, env, _ = build_application(environ)' in text
    assert 'adapter.run(environ=env)' in text
    assert "if __name__ == '__main__':" in text


def test_quality_gate_installs_the_production_package_before_startup_smoke():
    text = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    assert 'python -m pip install --no-cache-dir .' in text
    assert 'Production import smoke' in text
    assert "'company_ui.products.visualizer.cli'," in text


def test_quality_gate_smokes_the_exact_visembler_application():
    text = QUALITY_WORKFLOW.read_text(encoding='utf-8')
    assert 'Visembler startup smoke' in text
    assert 'from company_ui.products.visualizer.cli import build_application' in text
    assert '_, environment, repository = build_application(os.environ)' in text
    assert 'assert repository.list()' in text
    assert "assert environment['COMPANY_UI_ENVIRONMENT'] == 'test'" in text
    assert 'company-ui-runtime-smoke' not in text


def test_intentional_framework_runtime_smoke_shutdown_uses_sigterm():
    text = (ROOT / 'company_ui/certification/runtime_smoke.py').read_text(encoding='utf-8')
    start = text.index('def _stop_process')
    end = text.index('\n\ndef run_runtime_smoke', start)
    block = text[start:end]
    assert 'signal.SIGTERM' in block
    assert 'signal.SIGINT' not in block
