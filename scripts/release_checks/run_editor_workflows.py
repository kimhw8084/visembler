"""Run real Chromium edit/store/render workflows, explicitly in an isolated test host."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from urllib.request import urlopen
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import EditorHost, NativeHost, load_editor
from playwright.sync_api import sync_playwright, expect
from PIL import Image, ImageDraw


def state(p):return p.evaluate('window.CompanyUIVisualizerBridge.state()')
def model(p):return state(p)['model']
def settled(p):p.wait_for_function('()=>window.CompanyUIVisualizerBridge?.state().pending===0 && !window.CompanyUIVisualizerBridge.state().inflight',timeout=12000)
def ready(p):p.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=15000);settled(p)
def content(p):return p.locator('.component .integrated-element-content').first.inner_html()
def edit(p,selector,value):
    # A user must focus the intended window before native Tab/blur editing.
    p.bring_to_front()
    c=p.locator(selector);c.scroll_into_view_if_needed();c.fill(value);c.press('Tab');settled(p)
def panels(p,library=True,inspector=True):
    for sel,want in [('#libraryToggle',library),('#inspectorToggle',inspector)]:
        if (p.locator(sel).get_attribute('aria-pressed')=='true')!=want:p.locator(sel).click()
def add(p,engine,name):
    panels(p)
    p.locator('#componentSearch').fill(name)
    b=p.locator('#fullLibrary .library-item[data-element='+json.dumps(name,ensure_ascii=False)+']')
    expect(b).to_have_count(1);b.locator('.library-insert').click();settled(p)
    p.locator('#componentSearch').fill('')
    return model(p)['items'][-1]['id']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--only',default='');ap.add_argument('--native',action='store_true');args=ap.parse_args();Host=NativeHost if args.native else EditorHost
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'screenshots').mkdir(exist_ok=True);(out/'exports').mkdir(exist_ok=True)
    report={'host':'native NiceGUI' if args.native else 'embedded editor+production-ReportRepository; NOT NiceGUI','source_sha256':hashlib.sha256((ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest(),'cases':[],'unexpected_errors':[]}
    hints=json.loads((Path(__file__).parent/'element_fixtures.json').read_text())['cases']
    image=out/'synthetic.png';im=Image.new('RGB',(320,200),'#146090');ImageDraw.Draw(im).rectangle((45,45,160,160),fill='#ffdd00');im.save(image)
    with tempfile.TemporaryDirectory(prefix='visembler-editor-workflows-') as td,sync_playwright() as pw,Host(ROOT,Path(td)/'data') as host:
        kw={'headless':True};exe=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
        if exe:kw.update(executable_path=exe,args=['--no-sandbox'])
        browser=pw.chromium.launch(**kw);report['browser']=browser.version
        for n,case in enumerate(hints):
            if args.only and args.only.lower() not in case['element'].lower():continue
            name=case['element'];result={'element':name,'engine':case['engine'],'actions':{},'errors':[]};report['cases'].append(result)
            ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True,permissions=['clipboard-read','clipboard-write'])
            def track(page):
                page.on('pageerror',lambda e,r=result:r['errors'].append(str(e)))
                page.on('console',lambda e,r=result:r['errors'].append(e.text) if e.type=='error' else None)
            ctx.on('page',track);ctx.on('requestfailed',lambda e,r=result:r['errors'].append(str(e.failure)))
            p=ctx.new_page();p.set_default_timeout(6000)
            rid=host.create()
            def save(): (out/'workflows.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
            try:
                load_editor(p,host,rid);ready(p);ident=add(p,case['engine'],name);result['actions']['create']='PASS'
                original=model(p);before=content(p);changes=0
                if case.get('upload'):
                    p.locator(case['upload']).set_input_files(str(image));settled(p);changes+=1
                    p.wait_for_function('()=>document.querySelector(".component [style*=background-image]")')
                    decoded=p.locator('.component [style*=background-image]').first.evaluate("""async n=>{const src=getComputedStyle(n).backgroundImage.slice(4,-1).replace(/^['"]|['"]$/g,'');const i=new Image();i.src=src;await i.decode();return i.naturalWidth;}""")
                    assert decoded>0
                for selector,value in case.get('fields',{}).items():
                    old=model(p);edit(p,selector,value)
                    if model(p)!=old:changes+=1
                after=model(p);rendered=content(p)
                assert after!=original and rendered!=before,'Edit did not change BOTH model and rendered content'
                result['actions']['meaningful_edit']='PASS';result['edit_count']=changes
                result['render_before_sha256']=hashlib.sha256(before.encode()).hexdigest();result['render_after_sha256']=hashlib.sha256(rendered.encode()).hexdigest()
                result['observed_content']=p.locator('.component .card-body').first.inner_text()[:1000]
                for _ in range(changes):p.locator('#undo').click();settled(p)
                assert model(p)==original,'Undo did not exactly restore model'
                assert content(p)==before,'Undo did not restore rendered content'
                result['actions']['undo']='PASS'
                for _ in range(changes):p.locator('#redo').click();settled(p)
                assert model(p)==after and content(p)==rendered,'Redo did not restore edited model/render'
                result['actions']['redo']='PASS'
                # Real user clipboard interaction via inspector, not model insertion.
                p.locator('[data-reuse-action="copy-visual"]').click();p.locator('[data-reuse-action="paste-new"]').click();settled(p)
                items=model(p)['items'];assert len(items)==2 and items[0]['id']!=items[1]['id'];result['actions']['copy_paste']='PASS'
                # Persist via production file repository, then recreate editor with server payload.
                p.close();p=ctx.new_page();p.set_default_timeout(6000);load_editor(p,host,rid);ready(p);assert len(model(p)['items'])==2
                assert model(p)['items'][0]['element']==name;result['actions']['save_reload']='PASS'
                p.locator('#previewBtn').click();expect(p.locator('.cui-visualizer-root')).to_have_class(re.compile('preview-mode'))
                result['actions']['preview']='PASS';p.screenshot(path=str(out/'screenshots'/f'{n+1:02d}.png'))
                p.locator('#previewExit').click()
                p.locator('#exportBtn').click()
                with p.expect_download() as download:p.locator('#exportJsonAction').click()
                path=out/'exports'/f'{n+1:02d}.json';download.value.save_as(str(path));payload=json.loads(path.read_text());assert payload.get('model',payload)['items'][0]['element']==name
                result['actions']['json_download']='PASS'
                p.locator('#exportBtn').click()
                with p.expect_download() as download:p.locator('#exportSvgAction').click()
                path=out/'exports'/f'{n+1:02d}.svg';download.value.save_as(str(path));assert '<svg' in path.read_text()
                result['actions']['svg_download']='PASS'
                assert not result['errors'],result['errors'];result['status']='PASS'
            except Exception as e:
                result['status']='FAIL';result['error']=str(e);result['traceback']=traceback.format_exc()
                try:p.screenshot(path=str(out/'screenshots'/f'{n+1:02d}-failure.png'))
                except Exception:pass
            finally:
                print(name,result['status'],result.get('error','')[:130],flush=True);save();ctx.close()
        browser.close()
    report['passed']=sum(c['status']=='PASS' for c in report['cases']);report['total']=len(report['cases']);report['status']='PASS' if report['passed']==report['total'] else 'FAIL';save()
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
