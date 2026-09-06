"""Exercise the native report uploader through visible controls, with receipts.

Selecting a file queues it: Company UI's FileUpload does not enable auto_upload.
This helper clicks the real upload button exactly once. It never calls private
Vue methods, invokes the server handler directly, or fabricates report state.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_UPLOAD_NAME = re.compile(r'^upload(?:\s+(?:files?|all))?$', re.IGNORECASE)
_UPLOAD_ICON = re.compile(r'^(?:cloud_upload|file_upload|upload)$')


def _state(page: Any) -> dict[str, Any]:
    return page.evaluate('''() => {
        const s = window.CompanyUIVisualizerBridge?.state?.();
        return s ? {report_id:s.report_id, revision:s.revision,
                    pending:s.pending, inflight:s.inflight, recovery:s.recovery} : {};
    }''')


def _is_upload_request(request: Any) -> bool:
    path = urlsplit(request.url).path
    content_type = request.headers.get('content-type', '').lower()
    return request.method == 'POST' and (
        '/upload' in path or content_type.startswith('multipart/form-data')
    )


def _upload_button(page: Any, header: Any, timeout_ms: int) -> Any:
    """Prefer accessibility labels; support older QUploader Material icons.

    Quasar renders icon actions as .q-btn anchors as well as HTML buttons, so
    don't restrict the fallback selector to the tag name `button`.
    """
    named = header.get_by_role('button', name=_UPLOAD_NAME)
    legacy = header.locator('.q-btn').filter(
        has=page.locator('.q-icon').filter(has_text=_UPLOAD_ICON)
    )
    candidate = named.or_(legacy)
    # A union de-duplicates a single node matching both selectors. Deliberately
    # don't use first(): multiple candidates indicate an ambiguous test target.
    candidate.wait_for(state='visible', timeout=timeout_ms)
    if candidate.count() != 1:
        raise AssertionError('Expected one visible Upload action in the import uploader.')
    return candidate


def import_native_report(page: Any, source: Path, evidence: Path,
                         *, timeout_ms: int = 15000) -> dict[str, Any]:
    """Queue, upload and activate a JSON report via Manage -> Import.

    Persist evidence on success AND failure, including the actual target page.
    HTTP completion and report activation are separate assertions. A successful
    HTTP response alone does not mean the application's import was accepted.
    """
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    evidence.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        'scope': 'report-import UI interaction; host identity is recorded by caller',
        'status': 'RUNNING', 'stage': 'open-dialog',
        'file': source.name, 'bytes': source.stat().st_size,
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'before': _state(page), 'upload_button_clicks': 0,
        'upload_requests': [], 'upload_responses': [],
    }
    started = time.monotonic()

    def requested(request: Any) -> None:
        if _is_upload_request(request):
            receipt['upload_requests'].append({
                'method': request.method, 'path': urlsplit(request.url).path,
                'elapsed_ms': round((time.monotonic() - started) * 1000),
            })

    def responded(response: Any) -> None:
        if _is_upload_request(response.request):
            receipt['upload_responses'].append({
                'path': urlsplit(response.url).path, 'status': response.status,
                'elapsed_ms': round((time.monotonic() - started) * 1000),
            })

    def diagnostics() -> None:
        try:
            receipt['after'] = _state(page)
            receipt['target_ui'] = page.evaluate('''() => ({
                notifications: [...document.querySelectorAll('.q-notification')]
                    .map(n => (n.innerText || '').slice(0, 1500)).slice(-10),
                uploader_headers: [...document.querySelectorAll(
                    '.cui-visualizer-import-card .q-uploader__header')]
                    .map(n => n.outerHTML.slice(0, 12000)),
                import_dialog_text: [...document.querySelectorAll(
                    '.cui-visualizer-import-card')]
                    .map(n => (n.innerText || '').slice(0, 5000))
            })''')
        except Exception as exc:
            receipt['diagnostic_error'] = str(exc)

    page.on('request', requested)
    page.on('response', responded)
    try:
        page.get_by_role('button', name='Manage', exact=True).click()
        page.get_by_role('button', name='Import…', exact=True).click()
        card = page.locator('.cui-visualizer-import-card:visible')
        card.wait_for(state='visible', timeout=timeout_ms)
        uploader = card.locator('.q-uploader')
        receipt['stage'] = 'queue-file'
        uploader.locator('input[type="file"]').set_input_files(str(source))

        receipt['stage'] = 'click-upload'
        upload = _upload_button(page, uploader.locator('.q-uploader__header'), timeout_ms)
        page.screenshot(path=str(evidence / 'native-import-queued.png'))
        # Register response observation before clicking so fast loopback uploads
        # are not missed. No force-click or synthetic state change is permitted.
        with page.expect_response(lambda r: _is_upload_request(r.request),
                                  timeout=timeout_ms) as pending:
            upload.click(timeout=timeout_ms)
            receipt['upload_button_clicks'] += 1
        response = pending.value
        receipt['stage'] = 'upload-response'
        if not 200 <= response.status < 300:
            raise AssertionError(f'Native upload returned HTTP {response.status}.')
        if len(receipt['upload_requests']) != 1:
            raise AssertionError('Expected exactly one upload request for the single JSON file.')

        receipt['stage'] = 'report-activation'
        # Callback failures are displayed by the app, not necessarily emitted as
        # page errors. Stop on that message rather than hiding it in a timeout.
        page.wait_for_function('''before => {
            const id = window.CompanyUIVisualizerBridge?.state?.().report_id || '';
            const rejected = [...document.querySelectorAll('.q-notification')]
                .some(n => /report import rejected/i.test(n.innerText || ''));
            return rejected || (id !== before && id.startsWith('import-'));
        }''', arg=receipt['before'].get('report_id'), timeout=timeout_ms)
        after = _state(page)
        new_id = after.get('report_id', '')
        if new_id == receipt['before'].get('report_id') or not new_id.startswith('import-'):
            notices = page.locator('.q-notification').all_inner_texts()
            raise AssertionError('Application rejected the JSON import: ' + ' | '.join(notices))
        receipt['imported_report_id'] = new_id
        page.screenshot(path=str(evidence / 'native-import-activated.png'))
        done = card.get_by_role('button', name='Done', exact=True)
        if card.count() and card.is_visible():
            done.click(timeout=timeout_ms)
            card.wait_for(state='hidden', timeout=timeout_ms)
        receipt.update(status='PASS', stage='complete')
        return receipt
    except Exception as exc:
        receipt.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
        try:
            page.screenshot(path=str(evidence / 'native-import-failure.png'))
        except Exception as screenshot_error:
            receipt['screenshot_error'] = str(screenshot_error)
        raise
    finally:
        diagnostics()
        page.remove_listener('request', requested)
        page.remove_listener('response', responded)
        receipt['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (evidence / 'native-import.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
