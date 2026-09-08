"""Cold-page asset regression (production bootstrap expression + real repository).

These tests evaluate the actual initial-page bootstrap AST without pretending
that NiceGUI runs in this test. The browser test uses an explicitly synthetic
asset HTTP route; all editor/render/export code and the repository are real.
NativeHost portability remains the native integration test.
"""
from __future__ import annotations
import ast
import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys

from PIL import Image
import pytest
from company_ui.products.visualizer import page as page_module
from company_ui.products.visualizer.repository import ReportRepository

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/'company_ui/products/visualizer/page.py'


def initial_page_bootstrap(record):
    """Evaluate only the actual initial page's bootstrap assignment."""
    tree=ast.parse(PAGE.read_text(encoding='utf-8'))
    page=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='visualizer_page')
    assignments=[n for n in ast.walk(page) if isinstance(n,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id=='bootstrap' for t in n.targets)]
    assert len(assignments)==1, 'Review the initial-page bootstrap binding if its shape changed.'
    expr=ast.fix_missing_locations(ast.Expression(assignments[0].value))
    return eval(compile(expr,str(PAGE),'eval'),vars(page_module)|{'current':record,'build':'fixture-build'})


def png_bytes():
    stream=io.BytesIO();Image.new('RGB',(240,140),(123,21,76)).save(stream,format='PNG');return stream.getvalue()


def source_model(element='Image + Caption'):
    return {'items':[{'id':'c1','order':0,'type':'image','engine':'ImageMediaEngine','element':element,
      'title':element,'showTitle':False,'src':'data:image/png;base64,'+base64.b64encode(png_bytes()).decode(),
      'caption':'Portable metrology Δ','alt':'Synthetic metrology image',
      'x':14,'y':14,'w':420,'h':260,'z':1,'locked':False,'groupId':None}],
      'groups':{},'mode':'guided','nextId':2,
      'datasets':[{'id':'unbound-typed-data','name':'Typed fixture','revision':1,
        'fields':[{'id':f'c{i}','name':f'C{i}','type':'unknown'} for i in range(6)],
        'rows':[[0,'0','',None,True,'00123']]}]}


@pytest.mark.parametrize('element',['Image','Image + Caption','Screenshot Frame'])
def test_actual_cold_bootstrap_hydrates_saved_images_without_mutating_repository(tmp_path,element):
    repository=ReportRepository(tmp_path/'reports');record=repository.create('cold',model=source_model(element))
    before=copy.deepcopy(record.to_dict());stored=record.model['items'][0]
    assert stored.get('asset_id') and 'src' not in stored, 'Must test the saved asset-only shape.'
    bootstrap=initial_page_bootstrap(record);media=bootstrap['model']['items'][0]
    assert media.get('src')==f'{page_module.STATIC_ROUTE}/report-assets/{stored["asset_id"]}', (
        'Cold page load must hydrate src from the saved asset_id, just as report activation does.')
    assert bootstrap['asset_build']=='fixture-build'
    assert bootstrap['model']['datasets'][0]['rows']==[[0,'0','',None,True,'00123']]
    assert bootstrap['report_id']==record.report_id and bootstrap['revision']==record.revision
    assert repository.assets.read_image(media['asset_id'])==png_bytes()
    assert record.to_dict()==before and repository.get('cold').to_dict()==before


def test_actual_cold_bootstrap_uses_the_same_report_payload_as_activation(tmp_path):
    repository=ReportRepository(tmp_path/'reports');record=repository.create('cold',model=source_model())
    bootstrap=initial_page_bootstrap(record);bootstrap.pop('asset_build')
    assert bootstrap==page_module._payload(record,lambda aid:f'{page_module.STATIC_ROUTE}/report-assets/{aid}')


def test_cold_bootstrap_keeps_empty_media_empty_and_does_not_touch_inline_bytes(tmp_path):
    repository=ReportRepository(tmp_path/'reports');value=source_model();value['items'][0]['src']=''
    record=repository.create('empty',model=value)
    assert initial_page_bootstrap(record)['model']['items'][0]['src']==''
    # Record payloads may also contain a just-created inline image before storage.
    from dataclasses import replace
    inline=replace(record,model=source_model());before=copy.deepcopy(inline.model)
    assert initial_page_bootstrap(inline)['model']==before and inline.model==before


@pytest.fixture(scope='module')
def browser():
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        executable=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
        opts={'headless':True}
        if executable:opts.update(executable_path=executable,args=['--no-sandbox'])
        try:instance=pw.chromium.launch(**opts)
        except api.Error as exc:pytest.skip(f'Chromium unavailable: {exc}')
        yield instance
        instance.close()


@pytest.mark.parametrize('element',['Image','Image + Caption','Screenshot Frame'])
def test_real_editor_cold_asset_and_standalone_svg_decode(browser,tmp_path,element):
    # Explicit test host, not NiceGUI: unlike the previous embedded test it uses
    # the *actual* initial page bootstrap expression, not activation's _payload.
    scripts=str(ROOT/'scripts/release_checks');sys.path.insert(0,scripts)
    try:
        from editor_host import EditorHost,load_editor
        from media_assertions import assert_rendered_media
        from run_editor_workflows import ready
    finally:sys.path.remove(scripts)
    with EditorHost(ROOT,tmp_path/'data') as host:
        host.payload=initial_page_bootstrap
        rid=host.create(model=source_model(element));asset=host.repository.get(rid).model['items'][0]['asset_id']
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        errors=[]
        def track(page):
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda e:errors.append(e.text) if e.type=='error' else None)
        context.on('page',track);context.on('requestfailed',lambda r:errors.append(f'{r.url}: {r.failure}'))
        # Only the image HTTP endpoint is routed; bytes come from the production
        # asset store. No editor/model/render/export functions are mocked.
        endpoint=host.url+page_module.STATIC_ROUTE+'/report-assets/'
        def serve_asset(route):
            aid=route.request.url.split('?',1)[0].rsplit('/',1)[-1]
            route.fulfill(status=200,content_type='image/png',body=host.repository.assets.read_image(aid))
        context.route(endpoint+'*',serve_asset)
        try:
            p=context.new_page();load_editor(p,host,rid);ready(p)
            observed=assert_rendered_media(p,'c1',width=240,height=140)
            assert observed['resources'][0]['source'].endswith(asset)
            p.evaluate('()=>window.__VIZ_PROD__.setTheme("dark")')
            p.locator('#exportBtn').click()
            with p.expect_download() as response:p.locator('#exportSvgAction').click()
            svg_file=tmp_path/'standalone.svg';response.value.save_as(str(svg_file));svg=svg_file.read_text()
            assert 'data-theme="dark"' in svg and source_model()['items'][0]['src'] in svg
            assert '/report-assets/' not in svg and host.url not in svg
            from xml.etree import ElementTree
            ElementTree.fromstring(svg)
            offline=context.new_page();external=[]
            offline.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
            offline.set_content(svg);offline.locator('body > svg').evaluate('n=>{n.style.width="100%";n.style.height="auto";}')
            decoded=assert_rendered_media(offline,'c1',width=240,height=140)
            assert all(r['embedded'] for r in decoded['resources']) and not external
            assert not errors,errors
        finally:context.close()
