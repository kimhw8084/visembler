"""Contract tests for the browser CHECK, not native-host product receipts.

An isolated DOM fixture with explicitly mocked HTTP responses proves that
queueing is not submission, the helper clicks and issues a POST, and failures
retain the target window. These are NOT native NiceGUI product tests.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'native_upload_check', ROOT / 'scripts/release_checks/native_upload.py')
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

FIXTURE = r'''<!doctype html><meta charset="utf-8"><title>Upload-check fixture</title>
<style>body{font-family:sans-serif}.cui-visualizer-import-card{display:none;border:1px solid;padding:20px}
.q-btn{display:inline-block;padding:10px;border:1px solid}button{margin:6px}.queued{display:none}</style>
<button id="manage">Manage</button><button id="import" hidden>Import…</button>
<section class="cui-visualizer-import-card">
<h2>Fixture import</h2><div class="q-uploader"><div class="q-uploader__header">
<input type="file"><a role="button" class="q-btn queued" aria-label="Remove queued files"><i class="q-icon">clear_all</i></a>
__UPLOAD__</div></div><button id="done">Done</button></section>
<script>
const card=document.querySelector('section'), input=document.querySelector('input');
let rid='case-fresh-target', pending=0;
window.CompanyUIVisualizerBridge={state:()=>({report_id:rid,revision:1,pending,inflight:null,recovery:false})};
manage.onclick=()=>document.querySelector('#import').hidden=false;
document.querySelector('#import').onclick=()=>card.style.display='block';
done.onclick=()=>card.style.display='none';
input.onchange=()=>document.querySelectorAll('.queued').forEach(n=>n.style.display='inline-block');
for (const button of document.querySelectorAll('[data-upload]')) button.onclick=async()=>{
 pending=1;const form=new FormData();form.append('file',input.files[0]);
 const res=await fetch('https://visembler-upload-fixture.test/_nicegui/client/fixture/upload/7',{method:'POST',body:form});
 const data=await res.json(); pending=0;
 if(data.error){const n=document.createElement('div');n.className='q-notification';n.textContent='Report import rejected: '+data.error;document.body.append(n)}
 else rid=data.report_id;
};
</script>'''


@pytest.fixture(scope='module')
def browser():
    api = pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        exe = os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
        kwargs = {'headless': True}
        if exe:
            kwargs.update(executable_path=exe, args=['--no-sandbox'])
        try:
            instance = pw.chromium.launch(**kwargs)
        except api.Error as error:
            pytest.skip(f'Optional browser-check contract tests need Chromium: {error}')
        yield instance
        instance.close()


@pytest.fixture
def upload_fixture(browser):
    launched = []

    def start(kind='accessible', reject=False, status=200):
        controls = {
            'accessible': '<a role="button" aria-label="Upload files" class="q-btn queued" data-upload><i class="q-icon">custom-upload</i></a>',
            'legacy': '<a role="button" class="q-btn queued" data-upload><i class="q-icon">cloud_upload</i></a>',
            'both': '<a role="button" aria-label="Upload" class="q-btn queued" data-upload><i class="q-icon">cloud_upload</i></a>',
            'missing': '',
        }
        html = FIXTURE.replace('__UPLOAD__', controls[kind]).encode()
        requests = []

        context = browser.new_context(viewport={'width': 800, 'height': 600})
        def respond(route):
            request = route.request
            requests.append({'path': request.url, 'raw': request.post_data_buffer,
                             'content_type': request.headers.get('content-type')})
            payload = {'error': 'synthetic validation rejection'} if reject else {'report_id': 'import-fixture-verified'}
            route.fulfill(status=status, content_type='application/json',
                          headers={'Access-Control-Allow-Origin': '*'},
                          body=json.dumps(payload))
        context.route('https://visembler-upload-fixture.test/**', respond)
        page = context.new_page(); page.set_content(html.decode())
        launched.append(context)
        return page, requests

    yield start
    for context in launched:
        context.close()


@pytest.mark.parametrize('kind', ['accessible', 'legacy', 'both'])
def test_native_import_check_submits_once_via_real_visible_button(upload_fixture, tmp_path, kind):
    page, requests = upload_fixture(kind)
    source = tmp_path / 'portable.json'; source.write_text('{"model":{"items":[]}}')
    receipt = module.import_native_report(page, source, tmp_path / 'evidence', timeout_ms=3000)
    assert receipt['status'] == 'PASS'
    assert receipt['before']['report_id'] == 'case-fresh-target'
    assert receipt['imported_report_id'] == 'import-fixture-verified'
    assert receipt['upload_button_clicks'] == len(requests) == 1
    assert 'multipart/form-data' in requests[0]['content_type']
    assert b'portable.json' in requests[0]['raw']
    # Playwright's intercepted multipart body omits file payload bytes. Verify
    # the selected browser File independently, rather than claiming a server read.
    assert page.locator('input[type=file]').evaluate('async n => await n.files[0].text()') == source.read_text()
    assert receipt['upload_responses'][0]['status'] == 200
    assert (tmp_path / 'evidence/native-import-queued.png').is_file()
    assert (tmp_path / 'evidence/native-import-activated.png').is_file()
    assert not page.locator('.cui-visualizer-import-card').is_visible()


def test_application_rejection_is_not_an_import_pass(upload_fixture, tmp_path):
    page, requests = upload_fixture(reject=True)
    source = tmp_path / 'bad.json'; source.write_text('{}')
    with pytest.raises(AssertionError, match='synthetic validation rejection'):
        module.import_native_report(page, source, tmp_path / 'evidence', timeout_ms=3000)
    receipt = json.loads((tmp_path / 'evidence/native-import.json').read_text())
    assert receipt['status'] == 'FAIL' and receipt['stage'] == 'report-activation'
    assert receipt['after']['report_id'] == 'case-fresh-target'
    assert len(requests) == 1
    assert (tmp_path / 'evidence/native-import-failure.png').is_file()
    assert 'synthetic validation rejection' in str(receipt['target_ui']['notifications'])


def test_http_failure_is_not_an_import_pass(upload_fixture, tmp_path):
    page, _ = upload_fixture(status=500)
    source = tmp_path / 'bad.json'; source.write_text('{}')
    with pytest.raises(AssertionError, match='HTTP 500'):
        module.import_native_report(page, source, tmp_path / 'evidence', timeout_ms=3000)
    receipt = json.loads((tmp_path / 'evidence/native-import.json').read_text())
    assert receipt['status'] == 'FAIL' and receipt['stage'] == 'upload-response'


def test_no_upload_control_fails_instead_of_invoking_private_handler(upload_fixture, tmp_path):
    page, requests = upload_fixture(kind='missing')
    source = tmp_path / 'portable.json'; source.write_text('{}')
    with pytest.raises(Exception, match='Timeout'):
        module.import_native_report(page, source, tmp_path / 'evidence', timeout_ms=200)
    receipt = json.loads((tmp_path / 'evidence/native-import.json').read_text())
    assert receipt['stage'] == 'click-upload' and receipt['status'] == 'FAIL'
    assert receipt['upload_button_clicks'] == 0 and requests == []
    assert receipt['after']['report_id'] == receipt['before']['report_id']
    assert receipt['target_ui']['uploader_headers']
