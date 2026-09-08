#!/usr/bin/env python3
"""Exercise the company report boundary with real browser contexts.

The model-boundary receipt remains useful for fast CI.  This gate covers the
browser-specific contract: protected navigation, the owner sharing surface,
and the Viewer read-only projection.  The fixture IDs are unique to this run
and are removed only after ownership is verified.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from company_ui.products.visualizer.governance import CAPABILITY_ACTIONS, ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.page import template_model
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.security import AuthorizationModel, Principal, RoleDefinition


def _auth() -> AuthorizationModel:
    return AuthorizationModel({'visembler.admin': RoleDefinition('visembler.admin', frozenset({'administration', 'report.create', *CAPABILITY_ACTIONS}))})


def _record(checks: list[dict], identifier: str, status: str, detail: str = '') -> None:
    item = {'id': identifier, 'status': status}
    if detail:
        item['detail'] = detail
    checks.append(item)


def run(base_url: str, data_dir: Path, output: Path, headed: bool = False) -> int:
    checks: list[dict] = []
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not headed)

            def context(subject: str):
                return browser.new_context(viewport={'width': 1440, 'height': 900}, extra_http_headers={'x-auth-user': subject})

            def visit(page, url: str, expected: int):
                # A deliberate 404 is part of the protected-resource contract.
                # Do not convert the browser's expected failed-resource console
                # event into an application error; positive pages still capture
                # console and uncaught page errors exhaustively.
                if expected == 200:
                    page.on('console', lambda message: errors.append(f'{message.type}: {message.text}') if message.type == 'error' else None)
                    page.on('pageerror', lambda error: errors.append(f'pageerror: {error}'))
                    page.on('requestfailed', lambda request: errors.append(f'requestfailed: {request.url} · {request.failure}'))
                    page.on('response', lambda response: errors.append(f'http-{response.status}: {response.url}') if response.status >= 500 else None)
                response = page.goto(url, wait_until='domcontentloaded', timeout=15000)
                actual = response.status if response else 0
                if actual != expected:
                    raise AssertionError(f'{url} returned {actual}, expected {expected}')
                return response

            alice_context = context('alice')
            alice = alice_context.new_page()
            anonymous_context = browser.new_context(viewport={'width': 1440, 'height': 900})
            anonymous = anonymous_context.new_page()
            visit(anonymous, f'{base_url}/visualizer?report={shared_id}', 404)
            _record(checks, 'CB000', 'PASS')
            alice_response = visit(alice, f'{base_url}/visualizer?report={shared_id}', 200)
            _record(checks, 'CB001', 'PASS')
            if alice_response.headers.get('x-content-type-options') != 'nosniff' or alice_response.headers.get('x-frame-options') != 'DENY':
                raise AssertionError('required security headers missing')
            _record(checks, 'CB013', 'PASS')
            if not alice.get_by_role('button', name='Share', exact=True).is_visible():
                raise AssertionError('owner Share command is not visible')
            _record(checks, 'CB002', 'PASS')

            bob_before_context = context('bob')
            bob_before = bob_before_context.new_page()
            visit(bob_before, f'{base_url}/visualizer?report={shared_id}', 404)
            _record(checks, 'CB003', 'PASS')
            carol_context = context('carol')
            carol = carol_context.new_page()
            visit(carol, f'{base_url}/visualizer?report={shared_id}', 404)
            _record(checks, 'CB004', 'PASS')
            asset_response = carol_context.request.get(f'{base_url}/_cui_visualizer/report-assets/{private_id}/missing', timeout=10000)
            if asset_response.status != 404:
                raise AssertionError(f'unauthorized asset status {asset_response.status}')
            _record(checks, 'CB005', 'PASS')

            alice.get_by_role('button', name='Share', exact=True).click()
            alice.get_by_label('Company subject').fill('bob')
            alice.get_by_role('button', name='Grant / update', exact=True).click()
            page_wait = 0
            while page_wait < 10 and access.get(shared_id).get('grants', {}).get('bob') != 'viewer':
                alice.wait_for_timeout(100)
                page_wait += 1
            if access.get(shared_id).get('grants', {}).get('bob') != 'viewer':
                raise AssertionError('owner Share command did not persist the viewer grant')
            _record(checks, 'CB006', 'PASS')

            bob_context = context('bob')
            bob = bob_context.new_page()
            visit(bob, f'{base_url}/visualizer?report={shared_id}', 200)
            if bob.locator('[data-report-read-only="true"]').count() != 1:
                raise AssertionError('Viewer read-only marker missing')
            if bob.locator('.cui-visualizer-report-title input').count() != 0:
                raise AssertionError('Viewer title is editable')
            _record(checks, 'CB007', 'PASS')
            for name in ('Duplicate', 'Share', 'Trash'):
                if bob.get_by_role('button', name=name, exact=True).count():
                    raise AssertionError(f'Viewer mutation command visible: {name}')
            _record(checks, 'CB008', 'PASS')
            if bob.get_by_text('Read-only', exact=True).count() != 1:
                raise AssertionError('Viewer indicator missing')
            _record(checks, 'CB009', 'PASS')

            # The server-side projection is the source of truth for role
            # promotion; reload proves the browser consumes the new projection.
            access.update_grant(shared_id, 'bob', 'editor')
            bob_editor = bob_context.new_page()
            visit(bob_editor, f'{base_url}/visualizer?report={shared_id}', 200)
            if bob_editor.locator('[data-report-read-only="true"]').count():
                raise AssertionError('Editor remained read-only after promotion')
            if bob_editor.locator('.cui-visualizer-report-title input').count() != 1:
                raise AssertionError('Editor title input missing after promotion')
            _record(checks, 'CB010', 'PASS')

            access.update_grant(shared_id, 'bob', None)
            revoked = bob_context.new_page()
            visit(revoked, f'{base_url}/visualizer?report={shared_id}', 404)
            _record(checks, 'CB011', 'PASS')
            for width in (1440, 768, 390):
                responsive_context = browser.new_context(viewport={'width': width, 'height': 900}, extra_http_headers={'x-auth-user': 'alice'})
                responsive = responsive_context.new_page()
                visit(responsive, f'{base_url}/visualizer?report={shared_id}', 200)
                if responsive.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth + 1') is not True:
                    raise AssertionError(f'page overflow at {width}px')
                responsive.close(); responsive_context.close()
            _record(checks, 'CB014', 'PASS')
            anonymous.close(); alice.close(); bob.close(); bob_editor.close(); revoked.close(); bob_before.close(); carol.close()
            anonymous_context.close(); alice_context.close(); bob_context.close(); bob_before_context.close(); carol_context.close(); browser.close()
    except Exception as exc:
        _record(checks, 'CB999', 'FAIL', f'{type(exc).__name__}: {exc}')
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
        'candidate_sha': __import__('subprocess').check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'browser_mode': 'playwright',
        'checks': checks,
        'browser_console_errors': errors,
        'created': len(created),
        'cleaned': len(created) - len(remaining),
        'remaining': remaining,
    }
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
