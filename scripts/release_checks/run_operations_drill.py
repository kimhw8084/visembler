#!/usr/bin/env python3
"""Fresh application environment plus backup/restore drill for local pilot scope."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import venv
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import NativeHost
from native_common import BrowserEvents,browser_kwargs,ready,write_json
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw


def png_bytes():
    image=Image.new('RGB',(180,110),'#174f85');draw=ImageDraw.Draw(image);draw.rectangle((24,24,100,86),fill='#ffdf57')
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()


def model_with_image(data:bytes):
    src='data:image/png;base64,'+base64.b64encode(data).decode()
    return {'schema_version':1,'items':[
        {'id':'c1','type':'image','engine':'ImageMediaEngine','element':'Image + Caption','title':'Evidence Image','src':src,'alt':'Synthetic backup image','caption':'Backup drill','fit':'fill','focal':'50% 50%','weight':1.2,'order':0,'locked':False,'z':1},
        {'id':'c2','type':'text','engine':'TextEngine','element':'Body Narrative','title':'Narrative','text':'Before backup','body':'Before backup','weight':1.0,'order':1,'locked':False,'z':2},
    ],'groups':{},'datasets':[],'mode':'smart','layoutPreset':'editorial','crossFilter':None,'canvas':{'width':1600,'height':900},'nextId':3}


def durable_hashes(data:Path):
    keep=[]
    if (data/'.storage_secret').is_file():keep.append(data/'.storage_secret')
    reports=data/'reports'
    if reports.exists():keep.extend(p for p in reports.rglob('*') if p.is_file() and p.name!='native-server.log')
    return {p.relative_to(data).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(keep)}


def decoded_width(page):
    locator=page.locator('.component [style*="background-image"]').first
    locator.wait_for(state='visible',timeout=10000)
    return locator.evaluate("""async n=>{const raw=getComputedStyle(n).backgroundImage;const src=raw.slice(4,-1).replace(/^['\"]|['\"]$/g,'');const i=new Image();i.src=src;await i.decode();return i.naturalWidth;}""")


def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def wait_url(url,process,timeout=35):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if process.poll() is not None:return False
        try:
            with urlopen(url,timeout=1) as response:
                if response.status==200:return True
        except Exception:time.sleep(.25)
    return False


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'screenshots').mkdir(exist_ok=True);(out/'logs').mkdir(exist_ok=True)
    report={'scope':'local/internal-pilot operations drill','cases':[],'limitations':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='visembler-ops-') as td,sync_playwright() as pw:
            td=Path(td);source=td/'source-data';backup=td/'backup';restored=td/'restored-data';payload=png_bytes()
            host=NativeHost(ROOT,source);rid=host.create(model=model_with_image(payload))
            first=host.repository.get(rid);changed=json.loads(json.dumps(first.model));next(x for x in changed['items'] if x['id']=='c2')['text']='After history';next(x for x in changed['items'] if x['id']=='c2')['body']='After history'
            host.repository.commit(rid,base_revision=first.revision,model=changed,commit_id='ops-history-2')

            case={'name':'native-source-before-backup','status':'FAIL'};report['cases'].append(case)
            with host:
                browser=pw.chromium.launch(**browser_kwargs());ctx=browser.new_context(viewport={'width':1280,'height':900});events=BrowserEvents();page=ctx.new_page();events.attach(page)
                page.goto(host.url+'/visualizer',wait_until='domcontentloaded');ready(page,require_settled=True)
                assert decoded_width(page)==180
                assert len(host.repository.list_history(rid))>=2
                page.screenshot(path=str(out/'screenshots'/'01-source-before-backup.png'));case.update(status='PASS',history_entries=len(host.repository.list_history(rid)))
                ctx.close();browser.close()
            before=durable_hashes(source);assert before and '.storage_secret' in before

            case={'name':'complete-data-directory-backup-and-restore','status':'FAIL'};report['cases'].append(case)
            try:
                shutil.copytree(source,backup);backup_hash=durable_hashes(backup);assert backup_hash==before
                shutil.copytree(backup,restored);restore_pre=durable_hashes(restored);assert restore_pre==before
                restored_host=NativeHost(ROOT,restored)
                with restored_host:
                    browser=pw.chromium.launch(**browser_kwargs());ctx=browser.new_context(viewport={'width':1280,'height':900});page=ctx.new_page();page.goto(restored_host.url+'/visualizer',wait_until='domcontentloaded');ready(page,require_settled=True)
                    assert decoded_width(page)==180
                    assert len(restored_host.repository.list_history(rid))>=2
                    assert restored_host.repository.assets.ids()==host.repository.assets.ids()
                    page.screenshot(path=str(out/'screenshots'/'02-restored-data.png'));ctx.close();browser.close()
                case.update(status='PASS',files=len(before),history_entries=len(restored_host.repository.list_history(rid)),image_assets=len(restored_host.repository.assets.ids()))
            except Exception as exc:case['error']=str(exc);case['traceback']=traceback.format_exc()

            # Fresh application install uses a new venv and installs this checkout
            # without network. Runtime dependencies are inherited from the already
            # verified host Python, so this is a cold *application/package* install,
            # not a claim that an air-gapped machine can obtain third-party wheels.
            case={'name':'fresh-application-venv-install-and-start','status':'FAIL','dependency_mode':'system-site-packages inherited, exact versions checked'};report['cases'].append(case)
            try:
                envdir=td/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=True).create(envdir);py=envdir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
                install=subprocess.run([str(py),'-m','pip','install','--disable-pip-version-check','--no-input','--no-deps','--no-build-isolation','-e',str(ROOT)],text=True,capture_output=True,timeout=180,env=os.environ|{'PIP_NO_INDEX':'1'})
                (out/'logs'/'fresh-install.log').write_text(install.stdout+install.stderr,encoding='utf-8');assert install.returncode==0,install.stderr[-3000:]
                versions=json.loads(subprocess.check_output([str(py),'-c',"import importlib.metadata,json;print(json.dumps({n:importlib.metadata.version(n) for n in ['nicegui','Pillow','python-pptx']}))"],text=True))
                assert versions=={'nicegui':'3.15.0','Pillow':'12.3.0','python-pptx':'1.0.2'},versions
                port=free_port();cold_data=td/'cold-data';log=(out/'logs'/'fresh-start.log').open('w',encoding='utf-8')
                process=subprocess.Popen([str(py),'-m','company_ui.products.visualizer.cli'],cwd=td,env=os.environ|{'COMPANY_UI_HOST':'127.0.0.1','COMPANY_UI_PORT':str(port),'COMPANY_UI_VISUALIZER_DATA_DIR':str(cold_data),'COMPANY_UI_ENVIRONMENT':'test','PYTHONUNBUFFERED':'1'},stdout=log,stderr=subprocess.STDOUT)
                try:
                    assert wait_url(f'http://127.0.0.1:{port}/visualizer',process),f'cold start failed rc={process.poll()}'
                finally:
                    if process.poll() is None:process.terminate();process.wait(timeout=12)
                    log.close()
                assert (cold_data/'reports').is_dir() and (cold_data/'.storage_secret').is_file()
                case.update(status='PASS',versions=versions)
                report['limitations'].append('Fresh venv inherits the verified pinned third-party runtime; dependency acquisition from the company package index is outside this offline-safe drill.')
            except Exception as exc:case['error']=str(exc);case['traceback']=traceback.format_exc()
    except Exception as exc:report['harness_error']=str(exc);report['traceback']=traceback.format_exc()
    report['passed']=sum(c.get('status')=='PASS' for c in report['cases']);report['total']=3
    report['status']='PASS' if report['passed']==3 and 'harness_error' not in report else 'FAIL'
    write_json(out/'operations-drill.json',report);print(json.dumps(report,indent=2,ensure_ascii=False));return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
