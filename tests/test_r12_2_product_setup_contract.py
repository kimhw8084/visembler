from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
ROOT = SOURCE.parent


def test_root_setup_dispatches_to_visualizer_product_installers():
    text = (ROOT / 'setup.sh').read_text(encoding='utf-8')
    assert 'Darwin) exec "$ROOT/setup_mac.sh"' in text
    assert 'Linux) exec "$ROOT/setup_linux.sh"' in text
    assert 'Visembler' in text
    assert 'production setup' in text


def test_macos_product_setup_uses_exact_app_smoke_not_framework_lab_smoke():
    text = (ROOT / 'setup_mac.sh').read_text(encoding='utf-8')
    assert 'live_app_http_smoke.py' in text
    assert 'verify_nicegui315_runtime.py' in text
    assert 'company-ui" runtime-smoke' not in text
    assert 'run_lab.sh' not in text


def test_linux_product_setup_uses_exact_app_smoke():
    text = (ROOT / 'setup_linux.sh').read_text(encoding='utf-8')
    assert 'live_app_http_smoke.py' in text
    assert 'verify_nicegui315_runtime.py' in text


def test_intentional_framework_runtime_smoke_shutdown_uses_sigterm():
    text = (SOURCE / 'company_ui/certification/runtime_smoke.py').read_text(encoding='utf-8')
    start = text.index('def _stop_process')
    end = text.index('\n\ndef run_runtime_smoke', start)
    block = text[start:end]
    assert 'signal.SIGTERM' in block
    assert 'signal.SIGINT' not in block


def test_run_script_points_to_canonical_setup():
    text = (ROOT / 'run_visualizer.sh').read_text(encoding='utf-8')
    assert 'Run ./setup.sh first.' in text
