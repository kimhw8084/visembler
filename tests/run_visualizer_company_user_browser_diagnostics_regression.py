from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.release_checks import run_company_user_browser_acceptance as acceptance


class ReplayResponse:
    def __init__(self, status: int):
        self.status = status
        self.headers = {'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY'}


class ReplayRequest:
    def get(self, _url: str, timeout: int):
        assert timeout == 10000
        return ReplayResponse(404)


class ReplayLocator:
    def __init__(self, page, selector: str, kind: str = 'selector', name: str | None = None):
        self.page = page
        self.selector = selector
        self.kind = kind
        self.name = name

    def locator(self, selector: str):
        return ReplayLocator(self.page, selector)

    def get_by_role(self, role: str, name: str, exact: bool):
        return self.page.get_by_role(role, name, exact)

    def wait_for(self, state: str | None = None, timeout: int | None = None):
        if self.selector == '.q-menu:visible':
            self.page.menu_waits.append((state, timeout))
            if state == 'visible' and self.page.fail_menu_open:
                raise TimeoutError('intentional menu failure')
            if state == 'visible' and not self.page.menu_open:
                raise AssertionError('menu was expected to be open')
            if state == 'hidden':
                self.page.menu_open = False
            return
        if self.kind == 'role' and state == 'visible':
            assert self.count() == 1
        if self.selector == '[data-cui-overlay="dialog"]:visible' and state == 'visible':
            assert self.page.dialog_open
        if self.selector == '[data-cui-overlay="dialog"]:visible' and state == 'hidden':
            assert not self.page.dialog_open

    def count(self) -> int:
        if self.kind == 'text':
            return int(self.page.principal_role == 'viewer')
        if self.kind == 'role':
            assert self.name is not None
            self.page.role_counts.append((self.page.subject, self.page.current_path, self.name))
            if self.name == 'Grant access':
                return 1
            if self.page.current_path == '/visualizer/reports' and self.page.menu_open:
                role = self.page.principal_role
                visible = {
                    'owner': {'Manage access'},
                    'viewer': {'Review history', 'Download JSON'},
                    'editor': {'Edit details', 'Duplicate report', 'Review history', 'Download JSON'},
                }.get(role, set())
                return int(self.name in visible)
            if self.page.current_path == '/visualizer' and self.page.principal_role == 'viewer':
                return 0
            return 1
        if self.selector.startswith('[data-testid="report-card"]'):
            return 1
        if self.selector == '[data-report-action="more"]:visible':
            return 1
        if self.selector == '.q-menu:visible':
            return int(self.page.menu_open)
        if self.selector == '[data-testid="report-hub"]':
            return int(self.page.current_path == '/visualizer/reports')
        if self.selector == '[data-cui-overlay="dialog"]:visible':
            return int(self.page.dialog_open)
        if self.selector == '[data-report-read-only="true"]':
            return int(self.page.principal_role == 'viewer')
        if self.selector == '.cui-visualizer-report-title input':
            return int(self.page.principal_role != 'viewer')
        return 0

    def click(self, *args, **kwargs):
        if self.selector == '[data-report-action="more"]:visible':
            self.page.trigger_clicks.append((args, kwargs))
            self.page.menu_open = not self.page.fail_menu_open
            self.page.trigger_focused = True
            return
        if self.kind == 'role' and self.name == 'Manage access':
            self.page.dialog_open = True
            self.page.menu_open = False
            return
        if self.kind == 'role' and self.name == 'Grant access':
            report_id = parse_qs(urlparse(self.page.url).query).get('report', [''])[0]
            self.page.catalog.update_grant(report_id, 'bob', 'viewer')
            self.page.dialog_open = False

    def fill(self, value: str):
        assert self.kind == 'role' and self.name == 'Person or group'
        assert value == 'bob'


class ReplayPage:
    def __init__(self, subject: str, catalog, fail_menu_open: bool = False):
        self.subject = subject
        self.catalog = catalog
        self.fail_menu_open = fail_menu_open
        self.request = ReplayRequest()
        self.keyboard = types.SimpleNamespace(press=self._press)
        self.url = ''
        self.current_path = ''
        self.menu_open = False
        self.dialog_open = False
        self.trigger_focused = False
        self.listeners = {}
        self.menu_waits = []
        self.trigger_clicks = []
        self.role_counts = []
        self.socket_waits = []

    @property
    def principal_role(self) -> str:
        if self.subject == 'alice':
            return 'owner'
        report_id = parse_qs(urlparse(self.url).query).get('report', [''])[0]
        return self.catalog.get(report_id).get('grants', {}).get('bob', 'ungranted') if self.subject == 'bob' else 'ungranted'

    def on(self, event: str, callback):
        self.listeners.setdefault(event, []).append(callback)

    def goto(self, url: str, wait_until: str, timeout: int):
        assert wait_until == 'domcontentloaded'
        assert timeout == 15000
        self.url = url
        self.current_path = urlparse(url).path
        report_id = parse_qs(urlparse(url).query).get('report', [''])[0]
        status = 200 if self.principal_role in {'owner', 'viewer', 'editor'} else 404
        if self.subject == 'anonymous':
            status = 404
        return ReplayResponse(status)

    def wait_for_function(self, expression: str, timeout: int):
        assert expression == '() => window.socket?.connected === true && window.did_handshake === true'
        self.socket_waits.append(timeout)

    def locator(self, selector: str):
        return ReplayLocator(self, selector)

    def get_by_role(self, role: str, name: str, exact: bool):
        assert exact is True
        assert role == 'button' or (role == 'textbox' and name == 'Person or group')
        return ReplayLocator(self, 'role', kind='role', name=name)

    def get_by_label(self, label: str):
        return ReplayLocator(self, 'label', kind='label', name=label)

    def get_by_text(self, text: str, exact: bool):
        assert exact is True
        if text == 'Read-only':
            return ReplayLocator(self, 'read-only-text', kind='text', name=text)
        raise AssertionError(f'unexpected text query: {text}')

    def evaluate(self, expression: str, *args):
        if 'scrollWidth' in expression:
            return True
        assert expression == acceptance._BROWSER_STRUCTURE_SCRIPT
        assert not getattr(self.catalog, '_playwright_closed', False)
        assert len(args) == 1
        return {
            'document_ready_state': 'interactive',
            'socket_connected': True,
            'handshake_complete': True,
            'target_card_count': 1,
            'target_card_visible_count': 1,
            'target_trigger_count': 1,
            'target_trigger_visible_count': 1,
            'target_trigger_focused_count': int(self.trigger_focused),
            'target_trigger_aria_expanded': False,
            'target_trigger_aria_haspopup': 'menu',
            'visible_menu_count': int(self.menu_open),
            'visible_menus': [],
            'active_element': {
                'tag': 'button' if self.trigger_focused else 'body',
                'role': 'button' if self.trigger_focused else None,
                'report_action': 'more' if self.trigger_focused else None,
                'inside_target_card': self.trigger_focused,
                'inside_visible_menu': False,
            },
        }

    def wait_for_timeout(self, timeout: int):
        assert timeout == 100

    def _press(self, key: str):
        assert key == 'Escape'
        self.menu_open = False

    def close(self):
        pass


class ReplayContext:
    def __init__(self, subject: str, catalog, fail_menu_at: tuple[str, int] | None = None):
        self.subject = subject
        self.catalog = catalog
        self.fail_menu_at = fail_menu_at
        self.request = ReplayRequest()
        self.pages = []

    def new_page(self):
        fail_here = self.fail_menu_at == (self.subject, len(self.pages))
        page = ReplayPage(self.subject, self.catalog, fail_menu_open=fail_here)
        self.pages.append(page)
        return page

    def close(self):
        pass


class ReplayBrowser:
    def __init__(self, catalog, fail_menu_at: tuple[str, int] | None = None):
        self.catalog = catalog
        self.fail_menu_at = fail_menu_at
        self.contexts = []

    def new_context(self, viewport, extra_http_headers=None):
        subject = (extra_http_headers or {}).get('x-auth-user', 'anonymous')
        context = ReplayContext(subject, self.catalog, self.fail_menu_at)
        context.viewport = viewport
        self.contexts.append(context)
        return context

    def close(self):
        pass


class ReplayChromium:
    def __init__(self, browser: ReplayBrowser):
        self.browser = browser

    def launch(self, headless: bool):
        assert headless is True
        return self.browser


class ReplayPlaywright:
    def __init__(self, browser: ReplayBrowser):
        self.chromium = ReplayChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.chromium.browser.catalog._playwright_closed = True
        return False


def install_replay(monkeypatch, catalog, *, fail_menu_at: tuple[str, int] | None = None):
    browser = ReplayBrowser(catalog, fail_menu_at=fail_menu_at)
    manager = ReplayPlaywright(browser)
    package = types.ModuleType('playwright')
    package.__path__ = []
    sync_api = types.ModuleType('playwright.sync_api')
    sync_api.sync_playwright = lambda: manager
    monkeypatch.setitem(sys.modules, 'playwright', package)
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', sync_api)
    return browser


def run_replay(tmp_path: Path, monkeypatch, *, fail_menu_at: tuple[str, int] | None = None):
    catalog = acceptance.ReportAccessCatalog(tmp_path / 'replay-data' / 'reports')
    browser = install_replay(monkeypatch, catalog, fail_menu_at=fail_menu_at)
    output = tmp_path / 'receipt.json'
    status = acceptance.run('http://replay.invalid', tmp_path / 'replay-data', output)
    return status, json.loads(output.read_text()), browser


def test_menu_failure_receipt_has_bounded_observer_diagnostics_and_keeps_primary_failure(tmp_path, monkeypatch):
    status, receipt, browser = run_replay(tmp_path, monkeypatch, fail_menu_at=('bob', 1))

    assert status == 2
    assert receipt['status'] == 'FAIL'
    failure_index = next(index for index, check in enumerate(receipt['checks']) if check['id'] == 'CB999')
    assert receipt['checks'][failure_index]['detail'] == 'TimeoutError: intentional menu failure'
    assert next(check['status'] for check in receipt['checks'] if check['id'] == 'CB009') == 'PASS'
    assert 'CB015' not in [check['id'] for check in receipt['checks']]
    assert receipt['created'] == receipt['cleaned'] == 2
    assert receipt['remaining'] == []

    diagnostic = receipt['failure_diagnostics']
    assert diagnostic['observer_only'] is True
    assert diagnostic['check_id'] == 'CB015'
    assert diagnostic['principal'] == {'subject': 'bob', 'role': 'viewer'}
    assert diagnostic['stage'] == 'report_menu.wait_for_action_menu_visible'
    assert diagnostic['page'] == 'bob_viewer_report_hub'
    assert diagnostic['fixture']['report_id'].startswith('company-browser-shared-')
    assert diagnostic['fixture']['card_test_id'] == 'report-card'
    assert diagnostic['fixture']['trigger_action'] == 'more'
    assert diagnostic['interaction']['trigger_click_state'] == 'completed'
    assert diagnostic['browser_state']['status'] == 'captured'
    state = diagnostic['browser_state']['state']
    assert state['socket_connected'] is True
    assert state['handshake_complete'] is True
    assert state['target_card_count'] == state['target_trigger_visible_count'] == 1
    assert state['target_trigger_focused_count'] == 1
    assert state['visible_menu_count'] == 0
    event_names = [event['event'] for event in diagnostic['event_order']]
    assert event_names.index('stage:report_menu.click_trigger') < event_names.index('stage:report_menu.wait_for_action_menu_visible')
    assert len(diagnostic['event_order']) <= acceptance._MAX_DIAGNOSTIC_EVENTS
    viewer_context = next(context for context in browser.contexts if context.subject == 'bob' and len(context.pages) > 1)
    assert viewer_context.pages[1].trigger_clicks == [((), {})]
    assert viewer_context.pages[1].menu_waits[-2:] == [('hidden', 5000), ('visible', 5000)]
    assert not list((tmp_path / 'replay-data' / 'reports').glob('company-browser-*.json'))


def test_diagnostic_provider_failure_does_not_mask_menu_timeout_or_skip_cleanup(tmp_path, monkeypatch):
    def broken_provider(_observer):
        raise RuntimeError('diagnostic provider failure')

    monkeypatch.setattr(acceptance, '_capture_failure_diagnostics', broken_provider)
    status, receipt, browser = run_replay(tmp_path, monkeypatch, fail_menu_at=('bob', 3))

    assert status == 2
    failure = next(check for check in receipt['checks'] if check['id'] == 'CB999')
    assert failure == {'id': 'CB999', 'status': 'FAIL', 'detail': 'TimeoutError: intentional menu failure'}
    assert receipt['failure_diagnostics']['capture_status'] == 'failed'
    assert receipt['failure_diagnostics']['capture_error_type'] == 'RuntimeError'
    assert receipt['failure_diagnostics']['check_id'] == 'CB016'
    assert receipt['failure_diagnostics']['principal'] == {'subject': 'bob', 'role': 'editor'}
    assert next(check['status'] for check in receipt['checks'] if check['id'] == 'CB010') == 'PASS'
    assert next(check['status'] for check in receipt['checks'] if check['id'] == 'CB015') == 'PASS'
    assert receipt['created'] == receipt['cleaned'] == 2
    assert receipt['remaining'] == []
    editor_context = next(context for context in browser.contexts if context.subject == 'bob' and len(context.pages) > 3)
    assert editor_context.pages[3].trigger_clicks == [((), {})]


def test_positive_replay_preserves_all_checks_roles_clicks_and_timeout_budgets(tmp_path, monkeypatch):
    status, receipt, browser = run_replay(tmp_path, monkeypatch)

    expected_ids = [
        'CB000', 'CB001', 'CB013', 'CB002', 'CB003', 'CB004', 'CB005', 'CB006',
        'CB007', 'CB008', 'CB009', 'CB015', 'CB010', 'CB016', 'CB011', 'CB014', 'CB012',
    ]
    assert status == 0
    assert receipt['status'] == 'PASS'
    assert [check['id'] for check in receipt['checks']] == expected_ids
    assert all(check['status'] == 'PASS' for check in receipt['checks'])
    assert 'failure_diagnostics' not in receipt
    assert receipt['created'] == receipt['cleaned'] == 2
    assert receipt['remaining'] == []
    assert receipt['browser_console_errors'] == []

    pages = [page for context in browser.contexts for page in context.pages]
    trigger_clicks = [click for page in pages for click in page.trigger_clicks]
    assert trigger_clicks == [((), {})] * 4
    menu_waits = [wait for page in pages for wait in page.menu_waits]
    assert menu_waits == [
        ('hidden', 5000), ('visible', 5000), ('hidden', 5000),
        ('hidden', 5000), ('visible', 5000), ('hidden', 5000),
        ('hidden', 5000), ('visible', 5000), ('hidden', 5000),
        ('hidden', 5000), ('visible', 5000), ('hidden', 5000),
    ]
    assert all(timeout == 15000 for page in pages for timeout in page.socket_waits)
    assert ('bob', '/visualizer/reports', 'Edit details') in [item for page in pages for item in page.role_counts]
    assert ('bob', '/visualizer/reports', 'Manage access') in [item for page in pages for item in page.role_counts]
    assert ('bob', '/visualizer/reports', 'Move to trash') in [item for page in pages for item in page.role_counts]


def main() -> int:
    from tempfile import TemporaryDirectory

    controls = (
        test_menu_failure_receipt_has_bounded_observer_diagnostics_and_keeps_primary_failure,
        test_diagnostic_provider_failure_does_not_mask_menu_timeout_or_skip_cleanup,
        test_positive_replay_preserves_all_checks_roles_clicks_and_timeout_budgets,
    )
    for control in controls:
        with TemporaryDirectory(prefix='visembler-browser-diagnostic-') as root:
            monkeypatch = pytest.MonkeyPatch()
            try:
                control(Path(root), monkeypatch)
            finally:
                monkeypatch.undo()
        print(f'{control.__name__}: PASS')
    print(f'{len(controls)} browser diagnostic execution controls passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
