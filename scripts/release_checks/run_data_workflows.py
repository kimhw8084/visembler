"""Browser data/portable-output checks against the real editor and repository.

Host scope is recorded, not silently upgraded to NiceGUI/session verification.
Every fixture repository is temporary and contains only synthetic records.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,os,shutil,sys,tempfile,time,traceback,zipfile
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import EditorHost, NativeHost, load_editor
from native_upload import import_native_report
from media_assertions import assert_rendered_media
from run_editor_workflows import state,model,settled,ready,edit,panels,add
from company_ui.products.visualizer.page import _validate_model_images
from playwright.sync_api import sync_playwright,expect
from PIL import Image,ImageDraw

CASE_NAMES = (
 'displayed-table-refresh-undo', 'displayed-line-refresh-undo', 'displayed-wafer-refresh-undo',
 'linked-locked-peer-detach', 'transform-reordered-columns', 'clear-cancel-review',
 'grid-scroll-preserves-active-edit', 'two-session-conflict-retained-export',
 'keyboard-typing-cancel-command', 'json-image-fresh-directory-svg',
)
MOD='Meta' if sys.platform=='darwin' else 'Control'
TYPED='CODE\tVALUE\tTEXT_ZERO\tEMPTY\tABSENT\tENABLED\tDATE\n00123\t0\t"0"\t""\t\ttrue\t2026-09-05\n00456\t2\t"0"\t""\t\tfalse\t2026-09-06'
BASE='Category\tValue\nLot-A\t101\nLot-B\t202'
UPDATE='Category\tValue\nLot-A\t707\nLot-B\t909'
ALTERNATE='Category\tValue\nLot-A\t313\nLot-B\t515'
REORDER='Value\tCategory\n727\tLot-A\n919\tLot-B'

def mount(ctx,host,rid):
 p=ctx.new_page();p.set_default_timeout(7000);load_editor(p,host,rid);ready(p);return p

def paste_create(p,text,view='table'):
 panels(p);p.locator('#pasteDataBtn').click();p.locator('#dataFirstText').fill(text)
 expect(p.locator('.data-first-summary')).to_be_visible()
 p.locator(f'[data-data-first-view="{view}"]').click()
 with_change=model(p)
 p.locator('#dataFirstCreate').click();settled(p)
 p.locator('#genericModal.show').wait_for(state='hidden')
 assert len(model(p)['items'])==len(with_change['items'])+1
 return model(p)['items'][-1]['id']

def select(p,ident):
 p.bring_to_front()
 # Keyboard selection targets the component itself, avoiding overlapping hit areas.
 c=p.locator(f'.component[data-id="{ident}"]');c.focus();c.press('Enter');panels(p,False,True)
 expect(c).to_have_attribute('aria-selected','true')

def dataset(p,ident):
 m=model(p);e=next(v for v in m['items'] if v['id']==ident);return next(d for d in m['datasets'] if d['id']==e['dataset_id'])
def entry(p,ident):return next(v for v in model(p)['items'] if v['id']==ident)
def body(p,ident):return p.locator(f'.component[data-id="{ident}"] .card-body').inner_html()
def open_refresh(p,ident,text):
 select(p,ident);p.locator('[data-refresh-dataset]').click();p.locator('#refreshDataText').fill(text)
 expect(p.locator('#modalBody')).not_to_contain_text('Parsing and profiling data…')
def refresh(p,ident,text,only=False):
 open_refresh(p,ident,text);p.locator('#refreshOnly' if only else '#refreshLinked').click();settled(p);p.locator('#genericModal.show').wait_for(state='hidden')
def download(p,action,path):
 p.locator('#exportBtn').click()
 with p.expect_download() as d:p.locator(action).click()
 d.value.save_as(str(path));return path


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);ap.add_argument('--native',action='store_true');ap.add_argument('--only',default='');ap.add_argument('--archive',action='store_true',help='Package this run, including targeted receipts, in a sibling ZIP');args=ap.parse_args();Host=NativeHost if args.native else EditorHost;out=args.output.expanduser().resolve()
 selected_cases=[name for name in CASE_NAMES if not args.only or args.only in name]
 if not selected_cases:ap.error('--only matched no known data-workflow case; no tests were run')
 if out==ROOT or ROOT in out.parents:ap.error('--output must be outside the checkout')
 if out.exists() and any(out.iterdir()):ap.error('--output must be new or empty; do not mix old and new receipts')
 out.mkdir(parents=True,exist_ok=True)
 report={'unexpected_browser_events':[],'host':'native NiceGUI' if args.native else 'embedded editor + real file repository (not NiceGUI)','cases':[],'source_sha256':hashlib.sha256((ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest()}
 report.update(scope='targeted data workflow' if args.only else 'complete data-workflow group',selected_cases=selected_cases,
  test_source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
   'scripts/release_checks/run_data_workflows.py','scripts/release_checks/native_upload.py',
   'scripts/release_checks/media_assertions.py',
   'scripts/release_checks/editor_host.py','company_ui/integrations/nicegui_components.py',
   'company_ui/products/visualizer/page.py','company_ui/products/visualizer/assets/authoring_portability.mjs')})
 with tempfile.TemporaryDirectory(prefix='visembler-data-checks-') as td,sync_playwright() as pw,Host(ROOT,Path(td)/'A') as a,Host(ROOT,Path(td)/'B') as b:
  kw={'headless':True};exe=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
  if exe:kw.update(executable_path=exe,args=['--no-sandbox'])
  browser=pw.chromium.launch(**kw);report['browser']=browser.version
  original_new_context=browser.new_context
  def tracked_context(**options):
   context=original_new_context(**options)
   def track(page):
    page.on('pageerror',lambda e:report['unexpected_browser_events'].append({'kind':'page','message':str(e)}))
    page.on('console',lambda e:report['unexpected_browser_events'].append({'kind':'console','message':e.text}) if e.type=='error' else None)
   context.on('page',track);context.on('requestfailed',lambda r:report['unexpected_browser_events'].append({'kind':'request','url':r.url,'message':str(r.failure)}));return context
  browser.new_context=tracked_context
  def run(name,fn):
   if args.only and args.only not in name:return
   ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True,permissions=['clipboard-read','clipboard-write']);rid=a.create();p=mount(ctx,a,rid);r={'name':name,'errors':[]};report['cases'].append(r)
   p.on('pageerror',lambda e:r['errors'].append(str(e)))
   try:
    r['observed']=fn(ctx,p,rid);assert not r['errors'],r['errors'];r['status']='PASS'
   except Exception as exc:
    r['status']='FAIL';r['error']=str(exc);r['traceback']=traceback.format_exc()
    try:p.screenshot(path=str(out/(name+'-failure.png')))
    except Exception:pass
   finally:
    ctx.close();(out/'data-workflows.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));print(name,r['status'],r.get('error','')[:200],flush=True)
  def displayed(ctx,p,rid,view='table'):
   initial,updated_text,alternate_text=BASE,UPDATE,ALTERNATE
   if view=='line':
    initial='Time\tValue\n2026-01-01\t101\n2026-01-02\t202';updated_text='Time\tValue\n2026-01-01\t707\n2026-01-02\t909';alternate_text='Time\tValue\n2026-01-01\t313\n2026-01-02\t515'
   if view=='wafer':
    initial='LOT\tX_COORD\tY_COORD\tMEASURE\nL001\t1\t1\t101\nL001\t2\t1\t202';updated_text='LOT\tX_COORD\tY_COORD\tMEASURE\nL002\t1\t1\t707\nL002\t2\t1\t909';alternate_text='LOT\tX_COORD\tY_COORD\tMEASURE\nL003\t1\t1\t313\nL003\t2\t1\t515'
   ident=paste_create(p,initial,view);old=model(p);refresh(p,ident,updated_text);updated=model(p)
   assert '707' in body(p,ident) and '909' in body(p,ident);first=body(p,ident)
   p.locator('#undo').click();settled(p);assert model(p)==old and '101' in body(p,ident)
   refresh(p,ident,alternate_text);assert '313' in body(p,ident) and '707' not in body(p,ident)
   alternate=model(p);p.locator('#undo').click();settled(p);p.locator('#redo').click();settled(p)
   assert model(p)==alternate and '515' in body(p,ident)
   p.locator('#previewBtn').click();assert '313' in body(p,ident);p.screenshot(path=str(out/('displayed-'+view+'-preview.png')));p.locator('#previewExit').click()
   q=mount(ctx,a,rid);assert '313' in body(q,ident);q.close()
   return {'same_schema_values':[707,909],'alternate_after_undo':[313,515],'reload':'PASS','preview':'PASS','dataset_revision':dataset(p,ident)['revision']}
  run('displayed-table-refresh-undo',displayed)
  run('displayed-line-refresh-undo',lambda ctx,p,rid:displayed(ctx,p,rid,'line'))
  run('displayed-wafer-refresh-undo',lambda ctx,p,rid:displayed(ctx,p,rid,'wafer'))
  def linked(ctx,p,rid):
   ident=paste_create(p,BASE);select(p,ident);p.locator(f'.component[data-id="{ident}"]').focus();p.keyboard.press(MOD+'+c');p.keyboard.press(MOD+'+v');settled(p)
   other=model(p)['items'][-1]['id'];assert ident!=other and entry(p,ident)['dataset_id']==entry(p,other)['dataset_id']
   refresh(p,ident,UPDATE);assert '707' in body(p,ident) and '707' in body(p,other)
   select(p,other);p.locator('[data-inspector="lock"]').click();settled(p);unchanged=copy.deepcopy(dataset(p,other))
   open_refresh(p,ident,ALTERNATE);expect(p.locator('#refreshLinked')).to_be_disabled();expect(p.locator('#refreshOnly')).to_be_enabled()
   p.locator('#refreshOnly').click();settled(p)
   assert dataset(p,other)==unchanged and dataset(p,ident)['id']!=unchanged['id'];assert '313' in body(p,ident) and '707' in body(p,other)
   p.locator('#undo').click();settled(p);assert entry(p,ident)['dataset_id']==entry(p,other)['dataset_id']
   return {'linked_values':'707/707','detached_values':'313/707','locked_sibling_unchanged':True,'undo_relinked':True}
  run('linked-locked-peer-detach',linked)
  def transform(ctx,p,rid):
   ident=paste_create(p,BASE);select(p,ident)
   p.locator('[data-transform-type]').select_option('sort');p.locator('[data-transform-field]').select_option('value_2');p.locator('[data-transform-action="save"]').click();settled(p)
   refresh(p,ident,REORDER)
   assert entry(p,ident)['transform_recipe']['steps'][0]['field']=='value_1'
   assert '727' in body(p,ident) and '919' in body(p,ident)
   return {'rebound_sort_field':'value_1','rendered_values':[727,919]}
  run('transform-reordered-columns',transform)
  def clear_cancel(ctx,p,rid):
   ident=paste_create(p,BASE);before=model(p)
   open_refresh(p,ident,UPDATE);p.locator('#refreshDataText').fill('');expect(p.locator('#refreshLinked')).to_be_disabled()
   p.locator('#modalBody [data-close]').click();p.locator('#genericModal.show').wait_for(state='hidden');assert model(p)==before
   open_refresh(p,ident,'Value\tRenamed\n1\tA');expect(p.locator('#refreshLinked')).to_be_disabled()
   p.locator('#refreshReview').click();expect(p.locator('#dataFirstText')).to_have_value('Value\tRenamed\n1\tA');p.keyboard.press('Escape');assert model(p)==before
   return {'clear_disables_refresh':True,'dynamic_cancel_works':True,'review_preserves_input':True,'no_mutation':True}
  run('clear-cancel-review',clear_cancel)
  def scroll_edit(ctx,p,rid):
   ident=paste_create(p,BASE);select(p,ident);field=p.locator('[data-dataset-cell="0:1"]');field.scroll_into_view_if_needed();field.fill('707')
   # Deterministic scroll-event fault injection runs the real pooled-row painter.
   p.locator('#dataDockGrid .data-dock-scroll').evaluate('n=>n.dispatchEvent(new Event("scroll"))')
   expect(field).to_have_value('707');field.press('Tab');settled(p);assert dataset(p,ident)['rows'][0][1]==707
   table_id=add(p,'TableEngine','Clean Table');cell=p.locator('[data-table-cell="0:1"]');cell.fill('42.77')
   p.locator('#tableEditorGrid .data-dock-scroll').evaluate('n=>n.dispatchEvent(new Event("scroll"))')
   expect(cell).to_have_value('42.77');cell.press('Tab');settled(p);assert entry(p,table_id)['customTable']['rows'][0][1]==42.77
   return {'source_grid_draft':707,'custom_table_draft':42.77,'method':'UI editing with deterministic scroll-event injection'}
  run('grid-scroll-preserves-active-edit',scroll_edit)
  def concurrent(ctx,p,rid):
   ident=paste_create(p,BASE);qc=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);q=mount(qc,a,rid)
   try:
    select(p,ident);select(q,ident)
    assert state(p)['revision']==state(q)['revision'],'Conflict setup must begin from the same revision.'
    edit(p,'[data-dataset-cell="0:1"]','707')
    assert dataset(p,ident)['rows'][0][1]==707,'First session edit was not committed.'
    assert a.repository.get(rid).model['datasets'][0]['rows'][0][1]==707,'First session must be saved before the stale edit.'
    edit(q,'[data-dataset-cell="0:1"]','808')
    (out/'conflict-diagnostic.json').write_text(json.dumps({'p':state(p),'q':state(q),'q_bridge':q.evaluate('window.__HOST_TEST__||null')},indent=2))
    expect(q.locator('#saveBtn')).to_have_text('Recover edits');assert state(q)['recovery']
    retained=q.evaluate('window.__VIZ_PROD__.ui.recovery.model');assert retained['datasets'][0]['rows'][0][1]==808
    assert a.repository.get(rid).model['datasets'][0]['rows'][0][1]==707
    exported=json.loads(download(q,'#exportRecoveryJsonAction',out/'retained-conflict.json').read_text())
    assert exported['model']['datasets'][0]['rows'][0][1]==808
    assert a.repository.get(rid).model['datasets'][0]['rows'][0][1]==707
    q.screenshot(path=str(out/'two-session-conflict.png'))
    return {'server_value':707,'retained_local_value':808,'downloaded_local_value':808,'no_silent_overwrite':True,'transport':'NiceGUI' if args.native else 'test HTTP bridge'}
   finally:qc.close()
  run('two-session-conflict-retained-export',concurrent)
  def keyboard(ctx,p,rid):
   ident=paste_create(p,BASE);before=model(p);select(p,ident);p.locator('[data-refresh-dataset]').click()
   field=p.locator('#refreshDataText');field.press_sequentially(UPDATE,delay=5)
   expect(field).to_have_value(UPDATE);expect(field).to_be_focused()
   assert model(p)==before
   p.keyboard.press('Escape');p.locator('#genericModal.show').wait_for(state='hidden');assert model(p)==before
   panels(p);p.locator('#pasteDataBtn').click();ta=p.locator('#dataFirstText');ta.press_sequentially(BASE,delay=5)
   expect(ta).to_have_value(BASE);expect(ta).to_be_focused();p.keyboard.press(MOD+'+z');assert model(p)==before
   p.keyboard.press('Escape');p.locator('#genericModal.show').wait_for(state='hidden')
   p.locator('#commandBtn').click();p.locator('#cmdInput').fill('Save preset');p.locator('#cmdInput').press('Enter')
   expect(p.locator('#presetSaveName')).to_be_visible();p.keyboard.press('Escape')
   return {'typed_characters':len(BASE)+len(UPDATE),'caret_preserved':True,'native_text_undo_did_not_undo_report':True,'command_opened_dialog':True}
  run('keyboard-typing-cancel-command',keyboard)
  def portability(ctx,p,rid):
   progress={'status':'RUNNING','stage':'source-data','completed':[]}
   report['portability_progress']=progress
   q=target=offline=qc=None
   active=p
   def begin(stage,page):
    nonlocal active
    active=page;progress['stage']=stage
    (out/'portability-progress.json').write_text(json.dumps(progress,indent=2,ensure_ascii=False)+'\n')
   def completed(stage,observed):
    progress['completed'].append({'stage':stage,'status':'PASS','observed':observed})
    (out/'portability-progress.json').write_text(json.dumps(progress,indent=2,ensure_ascii=False)+'\n')
   def media_check(page,stage):
    begin(stage,page)
    observed=assert_rendered_media(page,image_id,width=240,height=140)
    page.screenshot(path=str(out/(stage+'.png')))
    completed(stage,observed)
    return observed
   def svg_check(page,path):
    page.bring_to_front();page.evaluate('()=>window.__VIZ_PROD__.setTheme("dark")')
    svg=download(page,'#exportSvgAction',path).read_text()
    assert 'data-theme="dark"' in svg,'Standalone SVG did not preserve the dark theme.'
    assert media['src'] in svg,'Standalone SVG omitted the actual replacement image bytes.'
    assert a.url not in svg and b.url not in svg and '/asset/' not in svg and '/_cui_visualizer/report-assets/' not in svg,'Standalone SVG still depends on a server-local image.'
    assert 'c-head' not in svg and 'resize-h' not in svg,'SVG contains authoring controls.'
    from xml.etree import ElementTree
    ElementTree.fromstring(svg)
    return svg
   try:
    ident=paste_create(p,TYPED);rows=dataset(p,ident)['rows'];assert rows[0]==['00123',0,'0','',None,True,'2026-09-05']
    select(p,ident);p.locator('[data-transform-type]').select_option('sort');p.locator('[data-transform-field]').select_option('code_1');p.locator('[data-transform-action="save"]').click();settled(p)
    image_id=add(p,'ImageMediaEngine','Image + Caption')
    im=Image.new('RGB',(240,140),'#145f91');ImageDraw.Draw(im).rectangle((20,20,180,100),fill='#f0b030');ip=out/'fixture.png';im.save(ip)
    p.locator('#iImageFile').set_input_files(str(ip));p.wait_for_function('()=>window.CompanyUIVisualizerBridge.state().model.items.some(i=>i.src?.startsWith("data:"))');settled(p)
    edit(p,'#iCaption','Portable metrology Δ');edit(p,'#iAlt','Synthetic metrology image')
    q=mount(ctx,a,rid);assert any(e.get('asset_id') for e in model(q)['items']), 'Need reloaded server asset fixture'
    media_check(q,'source-initial-reload-image')
    old_asset=entry(q,image_id)['asset_id'];select(q,image_id)
    im=Image.new('RGB',(240,140),'#7b154c');ImageDraw.Draw(im).rectangle((25,15,160,105),fill='#77dacc');replacement=out/'replacement.png';im.save(replacement)
    q.locator('#iImageFile').set_input_files(str(replacement));q.wait_for_function('()=>window.CompanyUIVisualizerBridge.state().model.items.some(i=>i.src?.startsWith("data:")&&!i.asset_id)');settled(q)
    q.close();q=mount(ctx,a,rid);assert entry(q,image_id)['asset_id']!=old_asset,'Replacing a reloaded image must replace its stored asset, not only its preview.'
    media_check(q,'source-replacement-reload-image')
    begin('portable-json-export',q)
    path=download(q,'#exportJsonAction',out/'portable.json');envelope=json.loads(path.read_text());source=envelope['model']
    media=next(e for e in source['items'] if e['engine']=='ImageMediaEngine');assert media['src'].startswith('data:image/png;base64,') and 'asset_id' not in media
    import base64
    assert base64.b64decode(media['src'].split(',',1)[1])==replacement.read_bytes(),'Portable JSON contains the wrong image bytes.'
    assert source['datasets'][0]['rows']==rows
    _validate_model_images(source)
    completed('portable-json-export',{'typed_rows_preserved':True,'image_bytes_match':True,'file':'portable.json'})
    qc=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    import_receipt=None
    if args.native:
     target=mount(qc,b,b.create());begin('native-fresh-directory-import',target)
     import_receipt=import_native_report(target,path,out)
     settled(target);new_id=import_receipt['imported_report_id']
     saved=b.repository.get(new_id).model
     assert saved['datasets']==source['datasets'],'Native import changed the typed dataset or its metadata.'
     imported_media=next(e for e in saved['items'] if e['engine']=='ImageMediaEngine')
     assert b.repository.assets.read_image(imported_media['asset_id'])==replacement.read_bytes(),'Fresh-directory imported image differs from the exported replacement.'
    else:
     new_id=b.create(model=source);target=mount(qc,b,new_id)
    assert state(target)['report_id']==new_id,'Wrong target report activated.'
    assert dataset(target,ident)['rows']==rows;assert 'Portable metrology' in body(target,image_id)
    media_check(target,'destination-imported-image')
    begin('destination-edit-reload',target)
    select(target,ident);edit(target,'[data-dataset-cell="0:1"]','33');assert dataset(target,ident)['rows'][0][1]==33
    target.close();target=mount(qc,b,new_id)
    assert state(target)['report_id']==new_id,'Reload selected a different report.'
    expected_rows=copy.deepcopy(rows);expected_rows[0][1]=33
    assert dataset(target,ident)['rows']==expected_rows and '33' in body(target,ident),'Fresh-directory edit did not persist/display.'
    completed('destination-edit-reload',{'report_id':new_id,'edited_value':33,'other_typed_values_preserved':True})
    media_check(target,'destination-reloaded-image')
    # Check both the source cold load and the imported/edited destination cold load.
    begin('source-svg-export',q);source_svg=svg_check(q,out/'source-reloaded-dark.svg')
    completed('source-svg-export',{'file':'source-reloaded-dark.svg','image_bytes_match':True,'bytes':len(source_svg.encode())})
    begin('destination-svg-export',target);svg=svg_check(target,out/'portable-dark.svg')
    completed('destination-svg-export',{'file':'portable-dark.svg','image_bytes_match':True,'bytes':len(svg.encode())})
    offline=qc.new_page();begin('standalone-svg-render',offline);requests=[]
    offline.on('request',lambda r:requests.append(r.url))
    # Abort any unexpected server dependency rather than allowing cache/server
    # availability to masquerade as a portable file.
    offline.route('http://**/*',lambda route:route.abort())
    offline.route('https://**/*',lambda route:route.abort())
    offline.set_content(svg)
    expect(offline.locator('foreignObject')).to_have_count(1)
    offline.locator('body > svg').evaluate("n=>{n.style.width='100%';n.style.height='auto';}")
    assert 'Portable metrology' in offline.locator('body').inner_text()
    assert '33' in body(offline,ident),'Standalone SVG missed the destination edit.'
    decoded=assert_rendered_media(offline,image_id,width=240,height=140)
    assert all(resource['embedded'] for resource in decoded['resources']),'Standalone image is not embedded.'
    color=offline.locator('.canvas-hull').evaluate('(n)=>getComputedStyle(n).backgroundColor')
    assert color not in ('rgb(245, 245, 247)','rgba(0, 0, 0, 0)','transparent'),color
    assert not [u for u in requests if u.startswith(('http:','https:'))],requests
    offline.screenshot(path=str(out/'portable-dark-offline.png'))
    completed('standalone-svg-render',{'decoded_image':decoded,'external_requests':0,'canvas':color,'edited_value_visible':33})
    progress['status']='PASS';progress['stage']='complete'
    return {'native_import':({'status':import_receipt['status'],'upload_requests':len(import_receipt['upload_requests']),'upload_button_clicks':import_receipt['upload_button_clicks'],'report_id':import_receipt['imported_report_id']} if import_receipt else {'status':'NOT_RUN','reason':'Embedded host'}),'image_embedded':True,'typed_row':rows[0],'separate_repository_edit_reload':True,'source_and_destination_reload_images':'PASS','standalone_svg_external_requests':0,'standalone_svg_image_decoded':True,'standalone_svg_canvas':color,'file_bytes':len(svg.encode())}
   except Exception as error:
    progress['status']='FAIL';progress['error']=str(error);progress['traceback']=traceback.format_exc()
    if active and not active.is_closed():
     try:
      active.screenshot(path=str(out/'portability-active-page-failure.png'))
      progress['active_page_url']=active.url
      progress['active_page_state']=active.evaluate('()=>window.CompanyUIVisualizerBridge?.state?.()||null')
     except Exception as evidence_error:progress['evidence_error']=str(evidence_error)
    raise
   finally:
    (out/'portability-progress.json').write_text(json.dumps(progress,indent=2,ensure_ascii=False)+'\n')
    if qc:qc.close()
    if q and not q.is_closed():q.close()
  run('json-image-fresh-directory-svg',portability)
  # Real worker creation cannot be tested in a null-origin embedded document.
  report['native_host_scope']={'status':'EXECUTED' if args.native else 'NOT_RUN','reason':'Native mode requested.' if args.native else 'Test host/embedded document only: native routes/socket/user storage not certified.'}
  if args.native:
   server_logs=out/'native-server-logs';server_logs.mkdir(exist_ok=True)
   for label,host in [('A',a),('B',b)]:
    host.log.flush()
    log_path=host.data/'native-server.log'
    if log_path.exists():shutil.copyfile(log_path,server_logs/f'instance-{label}.log')
  browser.close()
 report['passed']=sum(c['status']=='PASS' for c in report['cases']);report['status']='PASS' if report['passed']==len(selected_cases) and [c['name'] for c in report['cases']]==selected_cases and not report['unexpected_browser_events'] else 'FAIL'
 report['release_status']='NOT_ASSESSED';report['release_note']='This is a data-workflow receipt, not a whole-release verdict.'
 (out/'data-workflows.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 if args.archive:
  artifacts={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
  (out/'artifact-sha256.json').write_text(json.dumps(artifacts,indent=2)+'\n')
  archive=out.parent/(out.name+'.zip')
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
   for p in sorted(out.rglob('*')):
    if p.is_file():bundle.write(p,Path(out.name)/p.relative_to(out))
  print(json.dumps({'scope':report['scope'],'status':report['status'],'passed':report['passed'],'executed':len(report['cases']),'evidence_zip':str(archive)},indent=2))
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
