#!/usr/bin/env python3
"""Exercise the company report boundary with real browser contexts.

The model-boundary receipt remains useful for fast CI.  This gate covers the
browser-specific contract: protected navigation, the owner sharing surface,
and the Viewer read-only projection.  The fixture IDs are unique to this run
and are removed only after ownership is verified.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import sys
import uuid
from time import monotonic
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from source_identity import candidate_sha
except ModuleNotFoundError:
    from scripts.release_checks.source_identity import candidate_sha

from company_ui.products.visualizer.governance import CAPABILITY_ACTIONS, ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.page import template_model
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.security import AuthorizationModel, Principal, RoleDefinition


_MAX_DIAGNOSTIC_EVENTS = 40
_BROWSER_STRUCTURE_SCRIPT = r'''(reportId) => {
    const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' &&
            style.visibility !== 'hidden' && Number(style.opacity) !== 0;
    };
    const safeRole = (element) => {
        const role = element?.getAttribute('role');
        return role && role.length <= 32 ? role : null;
    };
    const cards = [...document.querySelectorAll('[data-testid="report-card"]')]
        .filter((element) => element.getAttribute('data-report-id') === reportId);
    const triggers = cards.flatMap((card) =>
        [...card.querySelectorAll('[data-report-action="more"]')]);
    const menus = [...document.querySelectorAll('.q-menu')].filter(visible).slice(0, 3);
    const active = document.activeElement;
    const activeInTarget = cards.some((card) => card.contains(active));
    const activeInMenu = menus.some((menu) => menu.contains(active));
    const expanded = triggers[0]?.getAttribute('aria-expanded');
    const hasPopup = triggers[0]?.getAttribute('aria-haspopup');
    return {
        document_ready_state: document.readyState,
        socket_connected: typeof window.socket?.connected === 'boolean' ? window.socket.connected : null,
        handshake_complete: typeof window.did_handshake === 'boolean' ? window.did_handshake : null,
        target_card_count: cards.length,
        target_card_visible_count: cards.filter(visible).length,
        target_trigger_count: triggers.length,
        target_trigger_visible_count: triggers.filter(visible).length,
        target_trigger_focused_count: triggers.filter((element) => element === active || element.contains(active)).length,
        target_trigger_aria_expanded: expanded === 'true' ? true : expanded === 'false' ? false : null,
        target_trigger_aria_haspopup: ['menu', 'dialog', 'listbox', 'tree', 'grid', 'true', 'false'].includes(hasPopup) ? hasPopup : null,
        visible_menu_count: [...document.querySelectorAll('.q-menu')].filter(visible).length,
        visible_menus: menus.map((menu) => ({
            role: safeRole(menu),
            button_count: menu.querySelectorAll('button').length,
            focused_inside: menu.contains(active),
        })),
        active_element: {
            tag: active?.tagName?.toLowerCase() ?? null,
            role: safeRole(active),
            report_action: active?.getAttribute('data-report-action') === 'more' ? 'more' : null,
            inside_target_card: activeInTarget,
            inside_visible_menu: activeInMenu,
        },
    };
}'''


class _BrowserDiagnosticObserver:
    """Bounded, non-authoritative state observed by the browser acceptance harness."""

    def __init__(self) -> None:
        self.started = monotonic()
        self.events: list[dict] = []
        self.context: dict = {}
        self.page = None
        self.failure_diagnostics: dict | None = None

    def event(self, name: str, page_name: str | None = None) -> None:
        self.events.append({
            'elapsed_ms': round((monotonic() - self.started) * 1000),
            'event': name,
            'page': page_name or self.context.get('page'),
        })
        del self.events[:-_MAX_DIAGNOSTIC_EVENTS]

    def stage(
        self,
        check_id: str,
        subject: str,
        role: str,
        stage: str,
        page,
        page_name: str,
        report_id: str | None = None,
        trigger_click_state: str | None = None,
    ) -> None:
        self.context = {
            'check_id': check_id,
            'principal': {'subject': subject, 'role': role},
            'stage': stage,
            'page': page_name,
        }
        if report_id is not None:
            self.context['fixture'] = {
                'report_id': report_id,
                'card_test_id': 'report-card',
                'trigger_action': 'more',
            }
        if trigger_click_state is not None:
            self.context['interaction'] = {
                'kind': 'report-action-menu',
                'trigger_click_state': trigger_click_state,
            }
        self.page = page
        self.event(f'stage:{stage}', page_name)

    def snapshot(self) -> dict:
        return {
            **self.context,
            'event_order': list(self.events),
        }


def _safe_stage(observer: _BrowserDiagnosticObserver, *args, **kwargs) -> None:
    try:
        observer.stage(*args, **kwargs)
    except Exception:
        # Diagnostics must never change a browser assertion's behavior.
        pass


def _safe_event(observer: _BrowserDiagnosticObserver, name: str, page_name: str | None = None) -> None:
    try:
        observer.event(name, page_name)
    except Exception:
        pass


def _capture_failure_diagnostics(observer: _BrowserDiagnosticObserver) -> dict:
    """Capture bounded structural browser metadata without affecting the primary failure."""
    diagnostic = {'observer_only': True, **observer.snapshot()}
    if observer.page is None:
        diagnostic['browser_state'] = {'status': 'unavailable'}
        return diagnostic
    report_id = observer.context.get('fixture', {}).get('report_id')
    if report_id is None:
        diagnostic['browser_state'] = {'status': 'not_applicable'}
        return diagnostic
    try:
        state = observer.page.evaluate(_BROWSER_STRUCTURE_SCRIPT, report_id)
    except Exception as exc:
        diagnostic['browser_state'] = {
            'status': 'capture_failed',
            'error_type': type(exc).__name__,
        }
    else:
        diagnostic['browser_state'] = {'status': 'captured', 'state': state}
    return diagnostic


def _fallback_failure_diagnostics(observer: _BrowserDiagnosticObserver, exc: Exception) -> dict:
    """Keep the original assertion reportable even if the diagnostic provider fails."""
    try:
        snapshot = observer.snapshot()
    except Exception:
        snapshot = {}
    return {
        'observer_only': True,
        'capture_status': 'failed',
        'capture_error_type': type(exc).__name__,
        **snapshot,
    }


@contextmanager
def _capture_before_browser_close(observer: _BrowserDiagnosticObserver):
    try:
        yield
    except Exception as exc:
        try:
            observer.failure_diagnostics = _capture_failure_diagnostics(observer)
        except Exception as diagnostic_exc:
            observer.failure_diagnostics = _fallback_failure_diagnostics(observer, diagnostic_exc)
        raise


def _auth() -> AuthorizationModel:
    return AuthorizationModel({'visembler.admin': RoleDefinition('visembler.admin', frozenset({'administration', 'report.create', *CAPABILITY_ACTIONS}))})


def _record(checks: list[dict], identifier: str, status: str, detail: str = '') -> None:
    item = {'id': identifier, 'status': status}
    if detail:
        item['detail'] = detail
    checks.append(item)


def _wait_for_nicegui_interactive(page) -> None:
    """Wait for NiceGUI 3.15's live Socket.IO connection and handshake."""
    page.wait_for_function(
        '() => window.socket?.connected === true && window.did_handshake === true',
        timeout=15000,
    )


def _open_report_menu(
    page,
    report_id: str,
    *,
    diagnostics: _BrowserDiagnosticObserver | None = None,
    check_id: str = 'browser-interaction',
    subject: str = 'unknown',
    role: str = 'unknown',
    page_name: str = 'unknown',
):
    def mark(stage: str, click_state: str = 'not_started') -> None:
        if diagnostics is not None:
            _safe_stage(
                diagnostics,
                check_id,
                subject,
                role,
                f'report_menu.{stage}',
                page,
                page_name,
                report_id,
                click_state,
            )

    mark('locate_card')
    card = page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]')
    mark('wait_for_card_visible')
    card.wait_for(state='visible', timeout=15000)
    mark('count_card')
    if card.count() != 1:
        raise AssertionError(f'expected one visible report card for {report_id!r}, found {card.count()}')
    mark('locate_trigger')
    trigger = card.locator('[data-report-action="more"]:visible')
    mark('wait_for_trigger_visible')
    trigger.wait_for(state='visible', timeout=5000)
    mark('count_trigger')
    if trigger.count() != 1:
        raise AssertionError(f'expected one visible More trigger for {report_id!r}, found {trigger.count()}')
    mark('wait_for_existing_menu_hidden')
    page.locator('.q-menu:visible').wait_for(state='hidden', timeout=5000)
    mark('click_trigger', 'attempting')
    trigger.click()
    mark('wait_for_action_menu_visible', 'completed')
    menu = page.locator('.q-menu:visible')
    menu.wait_for(state='visible', timeout=5000)
    mark('count_action_menu', 'completed')
    if menu.count() != 1:
        raise AssertionError(f'expected one visible action menu for {report_id!r}, found {menu.count()}')
    return menu


def _close_report_menu(
    page,
    menu,
    *,
    diagnostics: _BrowserDiagnosticObserver | None = None,
    check_id: str = 'browser-interaction',
    subject: str = 'unknown',
    role: str = 'unknown',
    page_name: str = 'unknown',
    report_id: str | None = None,
) -> None:
    if diagnostics is not None:
        _safe_stage(diagnostics, check_id, subject, role, 'report_menu.press_escape', page, page_name, report_id, 'completed')
    page.keyboard.press('Escape')
    if diagnostics is not None:
        _safe_stage(diagnostics, check_id, subject, role, 'report_menu.wait_hidden_after_escape', page, page_name, report_id, 'completed')
    menu.wait_for(state='hidden', timeout=5000)


def run(base_url: str, data_dir: Path, output: Path, headed: bool = False) -> int:
    checks: list[dict] = []
    diagnostics = _BrowserDiagnosticObserver()
    failure_diagnostics: dict | None = None
    run_id = uuid.uuid4().hex[:12]
    reports_dir = data_dir.expanduser().resolve() / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    repository = ReportRepository(reports_dir)
    access = ReportAccessCatalog(reports_dir)
    admin = ScopedReportRepository(repository, access, Principal('alice', roles=frozenset({'visembler.admin'})), _auth())
    shared_id = f'company-browser-shared-{run_id}'
    private_id = f'company-browser-private-{run_id}'
    created = [shared_id, private_id]
    for report_id, title in ((shared_id, 'Browser shared report'), (private_id, 'Browser private report')):
        admin.create(report_id, title=title, model=template_model('blank'), metadata={'crawler_owner': run_id})

    errors: list[str] = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright, _capture_before_browser_close(diagnostics):
            browser = playwright.chromium.launch(headless=not headed)

            def context(subject: str):
                return browser.new_context(viewport={'width': 1440, 'height': 900}, extra_http_headers={'x-auth-user': subject})

            def visit(page, url: str, expected: int, check_id: str, subject: str, role: str, page_name: str, report_id: str):
                # A deliberate 404 is part of the protected-resource contract.
                # Do not convert the browser's expected failed-resource console
                # event into an application error; positive pages still capture
                # console and uncaught page errors exhaustively.
                if expected == 200:
                    page.on('console', lambda message: errors.append(f'{message.type}: {message.text}') if message.type == 'error' else None)
                    page.on('pageerror', lambda error: errors.append(f'pageerror: {error}'))
                    page.on('requestfailed', lambda request: errors.append(f'requestfailed: {request.url} · {request.failure}'))
                    page.on('response', lambda response: errors.append(f'http-{response.status}: {response.url}') if response.status >= 500 else None)

                    def observe_websocket(websocket):
                        _safe_event(diagnostics, 'websocket_opened', page_name)
                        for event_name, event_label in (
                            ('framesent', 'websocket_frame_sent'),
                            ('framereceived', 'websocket_frame_received'),
                            ('close', 'websocket_closed'),
                        ):
                            try:
                                websocket.on(event_name, lambda _payload=None, label=event_label: _safe_event(diagnostics, label, page_name))
                            except Exception:
                                pass

                    try:
                        page.on('websocket', observe_websocket)
                    except Exception:
                        pass
                _safe_stage(diagnostics, check_id, subject, role, 'navigation.goto', page, page_name, report_id)
                response = page.goto(url, wait_until='domcontentloaded', timeout=15000)
                _safe_event(diagnostics, 'navigation.domcontentloaded', page_name)
                actual = response.status if response else 0
                if actual != expected:
                    raise AssertionError(f'{url} returned {actual}, expected {expected}')
                if expected == 200:
                    _safe_stage(diagnostics, check_id, subject, role, 'navigation.wait_for_socket_handshake', page, page_name, report_id)
                    _wait_for_nicegui_interactive(page)
                    _safe_event(diagnostics, 'nicegui.socket_handshake_ready', page_name)
                return response

            alice_context = context('alice')
            alice = alice_context.new_page()
            anonymous_context = browser.new_context(viewport={'width': 1440, 'height': 900})
            anonymous = anonymous_context.new_page()
            visit(anonymous, f'{base_url}/visualizer?report={shared_id}', 404, 'CB000', 'anonymous', 'anonymous', 'anonymous_report', shared_id)
            _record(checks, 'CB000', 'PASS')
            alice_response = visit(alice, f'{base_url}/visualizer?report={shared_id}', 200, 'CB001', 'alice', 'owner', 'alice_report', shared_id)
            _record(checks, 'CB001', 'PASS')
            _safe_stage(diagnostics, 'CB013', 'alice', 'owner', 'security_headers', alice, 'alice_report', shared_id)
            if alice_response.headers.get('x-content-type-options') != 'nosniff' or alice_response.headers.get('x-frame-options') != 'DENY':
                raise AssertionError('required security headers missing')
            _record(checks, 'CB013', 'PASS')
            alice_hub = alice_context.new_page()
            visit(alice_hub, f'{base_url}/visualizer/reports?report={shared_id}', 200, 'CB002', 'alice', 'owner', 'alice_report_hub', shared_id)
            _safe_stage(diagnostics, 'CB002', 'alice', 'owner', 'report_hub.ready', alice_hub, 'alice_report_hub', shared_id)
            alice_hub.locator('[data-testid="report-hub"]').wait_for(timeout=15000)
            owner_menu = _open_report_menu(alice_hub, shared_id, diagnostics=diagnostics, check_id='CB002', subject='alice', role='owner', page_name='alice_report_hub')
            _safe_stage(diagnostics, 'CB002', 'alice', 'owner', 'assert_manage_access_visible', alice_hub, 'alice_report_hub', shared_id)
            owner_menu.get_by_role('button', name='Manage access', exact=True).wait_for(state='visible', timeout=5000)
            _close_report_menu(alice_hub, owner_menu, diagnostics=diagnostics, check_id='CB002', subject='alice', role='owner', page_name='alice_report_hub', report_id=shared_id)
            _record(checks, 'CB002', 'PASS')

            bob_before_context = context('bob')
            bob_before = bob_before_context.new_page()
            visit(bob_before, f'{base_url}/visualizer?report={shared_id}', 404, 'CB003', 'bob', 'ungranted', 'bob_before_grant', shared_id)
            _record(checks, 'CB003', 'PASS')
            carol_context = context('carol')
            carol = carol_context.new_page()
            visit(carol, f'{base_url}/visualizer?report={shared_id}', 404, 'CB004', 'carol', 'ungranted', 'carol_report', shared_id)
            _record(checks, 'CB004', 'PASS')
            _safe_stage(diagnostics, 'CB005', 'carol', 'ungranted', 'request_private_asset', carol, 'carol_report', private_id)
            asset_response = carol_context.request.get(f'{base_url}/_cui_visualizer/report-assets/{private_id}/missing', timeout=10000)
            if asset_response.status != 404:
                raise AssertionError(f'unauthorized asset status {asset_response.status}')
            _record(checks, 'CB005', 'PASS')

            owner_menu = _open_report_menu(alice_hub, shared_id, diagnostics=diagnostics, check_id='CB006', subject='alice', role='owner', page_name='alice_report_hub')
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'open_share_dialog', alice_hub, 'alice_report_hub', shared_id, 'completed')
            owner_menu.get_by_role('button', name='Manage access', exact=True).click()
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'wait_for_menu_hidden_after_manage_access', alice_hub, 'alice_report_hub', shared_id, 'completed')
            owner_menu.wait_for(state='hidden', timeout=5000)
            share_dialog = alice_hub.locator('[data-cui-overlay="dialog"]:visible')
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'wait_for_share_dialog_visible', alice_hub, 'alice_report_hub', shared_id, 'completed')
            share_dialog.wait_for(state='visible', timeout=5000)
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'fill_grantee', alice_hub, 'alice_report_hub', shared_id, 'completed')
            alice_hub.get_by_label('Person or group').fill('bob')
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'submit_viewer_grant', alice_hub, 'alice_report_hub', shared_id, 'completed')
            alice_hub.get_by_role('button', name='Grant access', exact=True).click()
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'wait_for_share_dialog_hidden', alice_hub, 'alice_report_hub', shared_id, 'completed')
            share_dialog.wait_for(state='hidden', timeout=5000)
            _safe_stage(diagnostics, 'CB006', 'alice', 'owner', 'verify_viewer_grant_persisted', alice, 'alice_report', shared_id)
            page_wait = 0
            while page_wait < 10 and access.get(shared_id).get('grants', {}).get('bob') != 'viewer':
                alice.wait_for_timeout(100)
                page_wait += 1
            if access.get(shared_id).get('grants', {}).get('bob') != 'viewer':
                raise AssertionError('owner Share command did not persist the viewer grant')
            _record(checks, 'CB006', 'PASS')

            bob_context = context('bob')
            bob = bob_context.new_page()
            visit(bob, f'{base_url}/visualizer?report={shared_id}', 200, 'CB007', 'bob', 'viewer', 'bob_viewer_report', shared_id)
            _safe_stage(diagnostics, 'CB007', 'bob', 'viewer', 'assert_read_only_marker', bob, 'bob_viewer_report', shared_id)
            if bob.locator('[data-report-read-only="true"]').count() != 1:
                raise AssertionError('Viewer read-only marker missing')
            _safe_stage(diagnostics, 'CB007', 'bob', 'viewer', 'assert_title_not_editable', bob, 'bob_viewer_report', shared_id)
            if bob.locator('.cui-visualizer-report-title input').count() != 0:
                raise AssertionError('Viewer title is editable')
            _record(checks, 'CB007', 'PASS')
            _safe_stage(diagnostics, 'CB008', 'bob', 'viewer', 'assert_mutation_commands_hidden', bob, 'bob_viewer_report', shared_id)
            for name in ('Duplicate', 'Share', 'Trash'):
                if bob.get_by_role('button', name=name, exact=True).count():
                    raise AssertionError(f'Viewer mutation command visible: {name}')
            _record(checks, 'CB008', 'PASS')
            _safe_stage(diagnostics, 'CB009', 'bob', 'viewer', 'assert_read_only_indicator', bob, 'bob_viewer_report', shared_id)
            if bob.get_by_text('Read-only', exact=True).count() != 1:
                raise AssertionError('Viewer indicator missing')
            _record(checks, 'CB009', 'PASS')

            bob_hub = bob_context.new_page()
            visit(bob_hub, f'{base_url}/visualizer/reports?report={shared_id}', 200, 'CB015', 'bob', 'viewer', 'bob_viewer_report_hub', shared_id)
            viewer_menu = _open_report_menu(bob_hub, shared_id, diagnostics=diagnostics, check_id='CB015', subject='bob', role='viewer', page_name='bob_viewer_report_hub')
            _safe_stage(diagnostics, 'CB015', 'bob', 'viewer', 'assert_viewer_menu_permissions', bob_hub, 'bob_viewer_report_hub', shared_id, 'completed')
            for label in ('Review history', 'Download JSON'):
                viewer_menu.get_by_role('button', name=label, exact=True).wait_for(state='visible', timeout=5000)
            for label in ('Edit details', 'Manage access', 'Move to trash'):
                if viewer_menu.get_by_role('button', name=label, exact=True).count():
                    raise AssertionError(f'Viewer unauthorized Report Hub action visible: {label}')
            _close_report_menu(bob_hub, viewer_menu, diagnostics=diagnostics, check_id='CB015', subject='bob', role='viewer', page_name='bob_viewer_report_hub', report_id=shared_id)
            _record(checks, 'CB015', 'PASS')

            # The server-side projection is the source of truth for role
            # promotion; reload proves the browser consumes the new projection.
            access.update_grant(shared_id, 'bob', 'editor')
            bob_editor = bob_context.new_page()
            visit(bob_editor, f'{base_url}/visualizer?report={shared_id}', 200, 'CB010', 'bob', 'editor', 'bob_editor_report', shared_id)
            _safe_stage(diagnostics, 'CB010', 'bob', 'editor', 'assert_editor_not_read_only', bob_editor, 'bob_editor_report', shared_id)
            if bob_editor.locator('[data-report-read-only="true"]').count():
                raise AssertionError('Editor remained read-only after promotion')
            _safe_stage(diagnostics, 'CB010', 'bob', 'editor', 'assert_title_editable', bob_editor, 'bob_editor_report', shared_id)
            if bob_editor.locator('.cui-visualizer-report-title input').count() != 1:
                raise AssertionError('Editor title input missing after promotion')
            _record(checks, 'CB010', 'PASS')

            bob_editor_hub = bob_context.new_page()
            visit(bob_editor_hub, f'{base_url}/visualizer/reports?report={shared_id}', 200, 'CB016', 'bob', 'editor', 'bob_editor_report_hub', shared_id)
            editor_menu = _open_report_menu(bob_editor_hub, shared_id, diagnostics=diagnostics, check_id='CB016', subject='bob', role='editor', page_name='bob_editor_report_hub')
            _safe_stage(diagnostics, 'CB016', 'bob', 'editor', 'assert_editor_menu_permissions', bob_editor_hub, 'bob_editor_report_hub', shared_id, 'completed')
            for label in ('Edit details', 'Duplicate report', 'Review history', 'Download JSON'):
                editor_menu.get_by_role('button', name=label, exact=True).wait_for(state='visible', timeout=5000)
            for label in ('Manage access', 'Move to trash'):
                if editor_menu.get_by_role('button', name=label, exact=True).count():
                    raise AssertionError(f'Editor unauthorized Report Hub action visible: {label}')
            _close_report_menu(bob_editor_hub, editor_menu, diagnostics=diagnostics, check_id='CB016', subject='bob', role='editor', page_name='bob_editor_report_hub', report_id=shared_id)
            _record(checks, 'CB016', 'PASS')

            access.update_grant(shared_id, 'bob', None)
            revoked = bob_context.new_page()
            visit(revoked, f'{base_url}/visualizer?report={shared_id}', 404, 'CB011', 'bob', 'revoked', 'bob_revoked_report', shared_id)
            _record(checks, 'CB011', 'PASS')
            for width in (1440, 768, 390):
                responsive_context = browser.new_context(viewport={'width': width, 'height': 900}, extra_http_headers={'x-auth-user': 'alice'})
                responsive = responsive_context.new_page()
                visit(responsive, f'{base_url}/visualizer?report={shared_id}', 200, 'CB014', 'alice', 'owner', f'alice_responsive_{width}', shared_id)
                _safe_stage(diagnostics, 'CB014', 'alice', 'owner', f'assert_no_overflow_{width}', responsive, f'alice_responsive_{width}', shared_id)
                if responsive.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth + 1') is not True:
                    raise AssertionError(f'page overflow at {width}px')
                responsive.close(); responsive_context.close()
            _record(checks, 'CB014', 'PASS')
            anonymous.close(); alice.close(); alice_hub.close(); bob.close(); bob_hub.close(); bob_editor.close(); bob_editor_hub.close(); revoked.close(); bob_before.close(); carol.close()
            anonymous_context.close(); alice_context.close(); bob_context.close(); bob_before_context.close(); carol_context.close(); browser.close()
    except Exception as exc:
        _record(checks, 'CB999', 'FAIL', f'{type(exc).__name__}: {exc}')
        failure_diagnostics = diagnostics.failure_diagnostics
        if failure_diagnostics is None:
            try:
                failure_diagnostics = _capture_failure_diagnostics(diagnostics)
            except Exception as diagnostic_exc:
                failure_diagnostics = _fallback_failure_diagnostics(diagnostics, diagnostic_exc)
    finally:
        for report_id in created:
            try:
                record = admin.get(report_id)
                admin.delete(report_id, expected_revision=record.revision)
            except Exception:
                # Cleanup is intentionally ownership-scoped; the receipt reports
                # any remaining fixture through the final count below.
                pass
    remaining = [report_id for report_id in created if (reports_dir / f'{report_id}.json').exists() or (reports_dir / '_trash' / f'{report_id}.json').exists()]
    if errors:
        _record(checks, 'CB012', 'FAIL', '; '.join(errors[:10]))
    else:
        _record(checks, 'CB012', 'PASS')
    result = {
        'schema_version': 1,
        'status': 'PASS' if all(item['status'] == 'PASS' for item in checks) and not remaining else 'FAIL',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'base_url': base_url,
        'candidate_sha': candidate_sha(ROOT),
        'browser_mode': 'playwright',
        'checks': checks,
        'browser_console_errors': errors,
        'created': len(created),
        'cleaned': len(created) - len(remaining),
        'remaining': remaining,
    }
    if failure_diagnostics is not None:
        result['failure_diagnostics'] = failure_diagnostics
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'passed': sum(item['status'] == 'PASS' for item in checks), 'failed': sum(item['status'] == 'FAIL' for item in checks), 'remaining': remaining, 'output': str(output)}, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--headed', action='store_true')
    args = parser.parse_args()
    return run(args.base_url.rstrip('/'), args.data_dir, args.output, args.headed)


if __name__ == '__main__':
    raise SystemExit(main())
