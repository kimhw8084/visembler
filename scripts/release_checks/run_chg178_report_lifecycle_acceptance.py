#!/usr/bin/env python3
"""Native browser regressions for CHG-178 report lifecycle and stale edits."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.governance import ReportAccessCatalog
from editor_host import NativeHost
from native_common import BrowserEvents, acceptance_model, browser_kwargs, ready, select, write_json
from source_identity import candidate_sha


def _model(text: str) -> dict:
    value = acceptance_model()
    value['items'][0]['text'] = text
    value['items'][0]['body'] = text
    return canonical_model(value)


def _record(repo, report_id: str, predicate, *, timeout: float = 15):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = repo.get(report_id)
        if predicate(latest):
            return latest
        time.sleep(.1)
    raise AssertionError(f'report state did not settle; latest={latest.to_dict() if latest else None}')


def _editor(page, host: NativeHost, report_id: str) -> None:
    response = page.goto(f'{host.url}/visualizer?report={quote(report_id)}', wait_until='domcontentloaded')
    assert response and response.status == 200, response.status if response else None
    ready(page, require_settled=True)
    page.wait_for_function('()=>window.socket?.connected===true&&window.did_handshake===true', timeout=15_000)


def _hub(page, host: NativeHost, report_id: str) -> None:
    response = page.goto(f'{host.url}/visualizer/reports?report={quote(report_id)}', wait_until='domcontentloaded')
    assert response and response.status == 200, response.status if response else None
    page.locator('[data-testid="report-hub"]').wait_for(timeout=20_000)
    page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]').wait_for(timeout=20_000)


def _edit_details(page, report_id: str):
    card = page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]')
    card.locator('[data-report-action="more"]:visible').click()
    menu = page.locator('.q-menu:visible')
    menu.get_by_role('button', name='Edit details', exact=True).click()
    dialog = page.locator('[data-cui-overlay="dialog"]:visible').filter(has_text='Edit report details')
    dialog.wait_for(timeout=8_000)
    return dialog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    screenshots = output / 'screenshots'
    screenshots.mkdir(exist_ok=True)
    receipt = {
        'schema': 'visembler-chg178-report-lifecycle.v1',
        'candidate_sha': candidate_sha(ROOT),
        'cases': [],
        'unexpected_browser_events': [],
    }

    def case(name: str, details: dict) -> None:
        receipt['cases'].append({'name': name, 'status': 'PASS', 'details': details})

    try:
        with tempfile.TemporaryDirectory(prefix='visembler-chg178-lifecycle-') as temporary:
            with NativeHost(ROOT, Path(temporary) / 'data') as host:
                report_id = f'chg178-{int(time.time())}'
                initial = host.repository.create(
                    report_id,
                    title='CHG-178 original title',
                    model=_model('Historical report content'),
                    metadata={'description': 'Original report purpose'},
                )
                ReportAccessCatalog(host.repository).migrate(
                    [initial], owner_subject='local-dev', require_explicit_owner=True,
                )
                current = host.repository.commit(
                    report_id,
                    base_revision=initial.revision,
                    model=_model('Current report content'),
                    commit_id='chg178-browser-current-r2',
                )
                receipt['fixture'] = {
                    'report_id': report_id,
                    'starting_revision': current.revision,
                    'historical_revision': 1,
                    'historical_title': initial.title,
                    'historical_description': initial.metadata['description'],
                }

                events = BrowserEvents()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(**browser_kwargs())
                    context_a = browser.new_context(viewport={'width': 1440, 'height': 900})
                    context_b = browser.new_context(viewport={'width': 1440, 'height': 900})
                    editor_a = context_a.new_page()
                    editor_b = context_b.new_page()
                    for page in (editor_a, editor_b):
                        events.attach(page)
                        _editor(page, host, report_id)
                    initial_a = editor_a.evaluate('()=>CompanyUIVisualizerBridge.state().revision')
                    initial_b = editor_b.evaluate('()=>CompanyUIVisualizerBridge.state().revision')
                    assert initial_a == initial_b == current.revision

                    attempted_a = 'CHG-178 title from session A'
                    attempted_b = 'CHG-178 retained title from session B'
                    editor_a.get_by_label('Report title').fill(attempted_a)
                    editor_a.get_by_label('Report title').press('Tab')
                    saved_a = _record(host.repository, report_id, lambda value: value.title == attempted_a)
                    editor_b.get_by_label('Report title').fill(attempted_b)
                    editor_b.get_by_label('Report title').press('Tab')
                    conflict_b = editor_b.locator('[data-testid="report-edit-conflict"]:visible')
                    conflict_b.wait_for(timeout=10_000)
                    assert 'changed after revision' in conflict_b.inner_text().casefold()
                    assert editor_b.get_by_label('Report title').input_value() == attempted_b
                    assert host.repository.get(report_id).title == attempted_a
                    editor_b.screenshot(path=str(screenshots / 'stale-editor-title-conflict.png'), full_page=True)
                    case('isolated sessions reject stale title and preserve draft', {
                        'revision_loaded_by_both': initial_a,
                        'revision_after_a': saved_a.revision,
                        'canonical_before_resolution': attempted_a,
                        'stale_draft_retained': attempted_b,
                        'conflict_visible': True,
                    })
                    editor_b.get_by_role('button', name='Save retained draft as new revision', exact=True).click()
                    resolved_title = _record(host.repository, report_id, lambda value: value.title == attempted_b)
                    assert resolved_title.revision == saved_a.revision + 1

                    editor_a.reload(wait_until='domcontentloaded')
                    editor_b.reload(wait_until='domcontentloaded')
                    for page in (editor_a, editor_b):
                        ready(page, require_settled=True)
                    same_revision = editor_a.evaluate('()=>CompanyUIVisualizerBridge.state().revision')
                    assert editor_b.evaluate('()=>CompanyUIVisualizerBridge.state().revision') == same_revision == resolved_title.revision
                    attempted_purpose_a = 'Purpose saved by session A'
                    attempted_purpose_b = 'Purpose retained from stale session B'
                    editor_a.get_by_label('Description').fill(attempted_purpose_a)
                    editor_a.get_by_label('Description').press('Tab')
                    saved_purpose_a = _record(host.repository, report_id, lambda value: value.metadata.get('description') == attempted_purpose_a)
                    editor_b.get_by_label('Description').fill(attempted_purpose_b)
                    editor_b.get_by_label('Description').press('Tab')
                    purpose_conflict = editor_b.locator('[data-testid="report-edit-conflict"]:visible')
                    purpose_conflict.wait_for(timeout=10_000)
                    assert editor_b.get_by_label('Description').input_value() == attempted_purpose_b
                    assert host.repository.get(report_id).metadata['description'] == attempted_purpose_a
                    editor_b.screenshot(path=str(screenshots / 'stale-editor-purpose-conflict.png'), full_page=True)
                    editor_b.get_by_role('button', name='Save retained draft as new revision', exact=True).click()
                    resolved_purpose = _record(host.repository, report_id, lambda value: value.metadata.get('description') == attempted_purpose_b)
                    assert resolved_purpose.title == attempted_b
                    case('isolated sessions reject stale purpose and preserve draft', {
                        'revision_loaded_by_both': same_revision,
                        'revision_after_a': saved_purpose_a.revision,
                        'canonical_before_resolution': attempted_purpose_a,
                        'stale_draft_retained': attempted_purpose_b,
                        'revision_after_explicit_resolution': resolved_purpose.revision,
                    })

                    hub_a = context_a.new_page()
                    hub_b = context_b.new_page()
                    for page in (hub_a, hub_b):
                        events.attach(page)
                        _hub(page, host, report_id)
                    detail_revision_a = host.repository.get(report_id).revision
                    details_b = _edit_details(hub_b, report_id)
                    details_b.get_by_label('Report name').fill('CHG-178 Hub draft from session B')
                    details_b.get_by_label('Purpose').fill('Hub purpose draft from session B')
                    details_a = _edit_details(hub_a, report_id)
                    details_a.get_by_label('Report name').fill('CHG-178 Hub title from session A')
                    details_a.get_by_label('Purpose').fill('Hub purpose from session A')
                    details_a.get_by_role('button', name='Save details', exact=True).click()
                    saved_details_a = _record(
                        host.repository, report_id,
                        lambda value: value.title == 'CHG-178 Hub title from session A'
                        and value.metadata.get('description') == 'Hub purpose from session A',
                    )
                    details_b.get_by_role('button', name='Save details', exact=True).click()
                    details_b.get_by_text('Your entered details are still here.', exact=False).wait_for(timeout=10_000)
                    assert details_b.get_by_label('Report name').input_value() == 'CHG-178 Hub draft from session B'
                    assert details_b.get_by_label('Purpose').input_value() == 'Hub purpose draft from session B'
                    canonical_before_details_resolution = host.repository.get(report_id)
                    assert canonical_before_details_resolution.title == 'CHG-178 Hub title from session A'
                    assert canonical_before_details_resolution.metadata['description'] == 'Hub purpose from session A'
                    hub_b.screenshot(path=str(screenshots / 'stale-hub-details-conflict.png'), full_page=True)
                    details_b.get_by_role('button', name='Save retained draft as new revision', exact=True).click()
                    final_details = _record(
                        host.repository, report_id,
                        lambda value: value.title == 'CHG-178 Hub draft from session B'
                        and value.metadata.get('description') == 'Hub purpose draft from session B',
                    )
                    assert final_details.revision > saved_details_a.revision
                    hub_b.reload(wait_until='domcontentloaded')
                    _hub(hub_b, host, report_id)
                    card_b = hub_b.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]')
                    assert card_b.locator('.cui-report-card-title').inner_text() == 'CHG-178 Hub draft from session B'
                    assert card_b.locator('.cui-report-card-description').inner_text() == 'Hub purpose draft from session B'
                    editor_b.reload(wait_until='domcontentloaded')
                    ready(editor_b, require_settled=True)
                    assert editor_b.get_by_label('Report title').input_value() == 'CHG-178 Hub draft from session B'
                    assert editor_b.get_by_label('Description').input_value() == 'Hub purpose draft from session B'
                    case('Report Hub details conflict resolution and reload persistence', {
                        'starting_revision': detail_revision_a,
                        'revision_after_session_a': saved_details_a.revision,
                        'canonical_before_resolution': saved_details_a.title,
                        'draft_title_and_purpose_preserved': True,
                        'revision_after_explicit_resolution': final_details.revision,
                        'hub_reload_title': card_b.locator('.cui-report-card-title').inner_text(),
                        'hub_reload_purpose': card_b.locator('.cui-report-card-description').inner_text(),
                        'editor_reload_purpose': editor_b.get_by_label('Description').input_value(),
                    })

                    _editor(editor_a, host, report_id)
                    _editor(editor_b, host, report_id)
                    normal_base = editor_a.evaluate('()=>CompanyUIVisualizerBridge.state().revision')
                    assert editor_b.evaluate('()=>CompanyUIVisualizerBridge.state().revision') == normal_base
                    select(editor_a, 'c1')
                    editor_a.locator('#iText').fill('Normal report edit saved by session A')
                    editor_a.locator('#iText').press('Tab')
                    saved_model_a = _record(host.repository, report_id, lambda value: value.model['items'][0].get('text') == 'Normal report edit saved by session A')
                    select(editor_b, 'c1')
                    draft_component_title = 'Retained component title from session B'
                    editor_b.locator('#iTitle').fill(draft_component_title)
                    editor_b.locator('#iTitle').press('Tab')
                    editor_b.wait_for_function('()=>CompanyUIVisualizerBridge.state().recovery===true', timeout=15_000)
                    normal_conflict_status = editor_b.locator('#saveStatus').inner_text()
                    assert normal_conflict_status == 'Local edits need recovery'
                    assert editor_b.locator('#saveBtn').inner_text() == 'Recover edits'
                    recovery_key = f'viz-pending-report:{report_id}'
                    retained = editor_b.evaluate('key=>JSON.parse(localStorage.getItem(key)||"null")', recovery_key)
                    retained_item = next(item for item in retained['recovery']['model']['items'] if item['id'] == 'c1')
                    assert retained_item['title'] == draft_component_title
                    assert host.repository.get(report_id).model['items'][0].get('text') == 'Normal report edit saved by session A'
                    editor_b.screenshot(path=str(screenshots / 'stale-report-edit-recovery.png'), full_page=True)
                    editor_b.locator('#saveBtn').click()
                    resolved_model = _record(
                        host.repository, report_id,
                        lambda value: value.model['items'][0].get('title') == draft_component_title
                        and value.model['items'][0].get('text') == 'Normal report edit saved by session A',
                    )
                    editor_b.wait_for_function('()=>CompanyUIVisualizerBridge.state().recovery===false', timeout=15_000)
                    case('normal report edit conflict retains and safely reapplies non-overlapping draft', {
                        'revision_loaded_by_both': normal_base,
                        'revision_after_session_a': saved_model_a.revision,
                        'canonical_before_resolution': saved_model_a.model['items'][0].get('text'),
                        'retained_draft': retained_item['title'],
                        'visible_conflict_state': normal_conflict_status,
                        'revision_after_explicit_resolution': resolved_model.revision,
                        'session_a_edit_preserved': resolved_model.model['items'][0].get('text'),
                    })

                    history_page = hub_b
                    _hub(history_page, host, report_id)
                    card = history_page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]')
                    card.locator('[data-report-action="more"]:visible').click()
                    history_page.locator('.q-menu:visible').get_by_role('button', name='Review history', exact=True).click()
                    history = history_page.locator('[data-testid="report-history"]:visible')
                    history.wait_for(timeout=10_000)
                    history_page.get_by_label('Name a checkpoint').fill('CHG-178 pre-restore checkpoint')
                    history.get_by_role('button', name='Save checkpoint', exact=True).click()
                    _record(
                        host.repository, report_id,
                        lambda value: any(entry.get('checkpoint') and entry.get('label') == 'CHG-178 pre-restore checkpoint' for entry in host.repository.list_history(report_id)),
                    )
                    checkpoint_entry = next(entry for entry in host.repository.list_history(report_id) if entry.get('checkpoint') and entry.get('label') == 'CHG-178 pre-restore checkpoint')
                    checkpoint_card = history.locator(f'[data-history-id="{checkpoint_entry["history_id"]}"]')
                    checkpoint_card.wait_for(state='visible', timeout=10_000)
                    old_revision = resolved_model.revision
                    historical = history.locator('[data-history-id="r1"]')
                    historical.wait_for(timeout=10_000)
                    historical.get_by_role('button', name='View this revision', exact=True).click()
                    history_page.wait_for_function('()=>document.querySelector("[data-testid=report-history] [data-history-id=\\"r1\\"]")?.dataset.selected==="true"', timeout=8_000)
                    historical = history.locator('[data-history-id="r1"]')
                    historical.get_by_role('button', name='Restore as new revision', exact=True).click()
                    restore_dialog = history_page.locator('[data-cui-overlay="dialog"]:visible').filter(has_text='Restore a saved revision')
                    restore_dialog.wait_for(timeout=8_000)
                    restore_dialog.get_by_role('button', name='Restore as new revision', exact=True).click()
                    restored = _record(host.repository, report_id, lambda value: value.revision == old_revision + 1)
                    assert restored.title == 'CHG-178 original title'
                    assert restored.metadata['description'] == 'Original report purpose'
                    assert restored.model == initial.model
                    history_page.locator('[data-testid="history-current-context"]').get_by_text(f'Current r{restored.revision}', exact=True).wait_for(timeout=10_000)
                    history_page.screenshot(path=str(screenshots / 'history-restored-new-revision.png'), full_page=True)
                    history_page.reload(wait_until='domcontentloaded')
                    _hub(history_page, host, report_id)
                    card_after_reload = history_page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]')
                    assert card_after_reload.locator('.cui-report-card-title').inner_text() == 'CHG-178 original title'
                    assert card_after_reload.locator('.cui-report-card-description').inner_text() == 'Original report purpose'
                    card_after_reload.locator('[data-report-action="more"]:visible').click()
                    history_page.locator('.q-menu:visible').get_by_role('button', name='Review history', exact=True).click()
                    history_after_reload = history_page.locator('[data-testid="report-history"]:visible')
                    history_after_reload.locator('[data-history-id="r1"]').wait_for(timeout=10_000)
                    history_after_reload.locator(f'[data-history-id="{checkpoint_entry["history_id"]}"]').wait_for(timeout=10_000)
                    case('visible history restore creates and reloads a new revision', {
                        'restored_revision': restored.revision,
                        'restored_title': restored.title,
                        'restored_purpose': restored.metadata['description'],
                        'restored_model_exact': restored.model == initial.model,
                        'original_history_id_retained': 'r1',
                        'checkpoint_history_id_retained': checkpoint_entry['history_id'],
                        'reloaded_hub_title': card_after_reload.locator('.cui-report-card-title').inner_text(),
                        'reloaded_hub_purpose': card_after_reload.locator('.cui-report-card-description').inner_text(),
                    })

                    _editor(editor_b, host, report_id)
                    restored_state = editor_b.evaluate('()=>CompanyUIVisualizerBridge.state()')
                    assert restored_state['revision'] == restored.revision
                    restored_items = restored_state['model']['items']
                    source_items = restored.model['items']
                    assert len(restored_items) == len(source_items)
                    for loaded_item, source_item in zip(restored_items, source_items):
                        assert {key: loaded_item.get(key) for key in ('id', 'engine', 'element', 'title', 'text', 'body')} == {
                            key: source_item.get(key) for key in ('id', 'engine', 'element', 'title', 'text', 'body')
                        }
                    assert editor_b.get_by_label('Report title').input_value() == restored.title
                    assert editor_b.get_by_label('Description').input_value() == restored.metadata['description']
                    events.unexpected.extend(events.expected_fault)
                    receipt['unexpected_browser_events'] = events.unexpected
                    context_a.close()
                    context_b.close()
                    browser.close()
                receipt['status'] = 'PASS' if len(receipt['cases']) == 5 and not receipt['unexpected_browser_events'] else 'FAIL'
                receipt['case_count'] = len(receipt['cases'])
    except Exception as error:
        receipt['status'] = 'FAIL'
        receipt['error'] = f'{type(error).__name__}: {error}'
        receipt['traceback'] = traceback.format_exc()

    write_json(output / 'receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt.get('status') == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
