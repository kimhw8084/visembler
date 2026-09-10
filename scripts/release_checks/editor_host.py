"""Test-only loopback host: real editor modules + real ReportRepository.

This is NOT NiceGUI and must never be reported as a native-host pass. The small
HTTP bridge provides deterministic fault injection without user data or mocks
of editor/store/rendering code. Only synthetic temporary repositories are used.
"""
from __future__ import annotations
import json
import threading
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.page import _payload, _validate_model_images
from company_ui.products.visualizer.domain import canonical_model, RevisionConflictError

BRIDGE = r'''
window.__HOST_TEST__={requests:[],replies:[],paused:false,held:[],errors:[]};
async function hostSend(message){
 const test=window.__HOST_TEST__;test.requests.push(message);
 if(test.paused){test.held.push(message);return;}
 try{const r=await fetch(new URL('/message',document.baseURI),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message)});
 const reply=await r.json();test.replies.push(reply);window.CompanyUIVisualizerBridge.receive(reply);
 }catch(e){test.errors.push(String(e));}
}
document.addEventListener('visualizer_bridge',e=>hostSend(JSON.parse(e.detail)));
'''

class EditorHost:
    def __init__(self, root: Path, data: Path):
        self.root = root.resolve()
        self.data = data.resolve()
        self.repository = ReportRepository(self.data / 'reports')
        self.http = None
        self.thread = None
        self.preferences = {}

    def create(self, model=None, name=None):
        ident=name or 'case-'+uuid.uuid4().hex
        return self.repository.create(ident,title=ident,model=model or {}).report_id

    def payload(self, record):
        return _payload(record, lambda aid: f'/asset/{aid}')

    def __enter__(self):
        outer=self
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*_): pass
            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                super().end_headers()
            def do_OPTIONS(self):
                self.send_response(204);self.send_header("Access-Control-Allow-Headers", "Content-Type");self.send_header("Access-Control-Allow-Methods", "POST,GET,OPTIONS");self.end_headers()
            def send_json(self, data, status=200):
                raw=json.dumps(data,ensure_ascii=False).encode()
                self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                u=urlparse(self.path)
                if u.path=='/favicon.ico': self.send_response(204);self.end_headers();return
                if u.path.startswith('/asset/'):
                    try:
                        data=outer.repository.assets.read_image(u.path.split('/')[-1])
                        from company_ui.products.visualizer.files import validate_image_bytes
                        self.send_response(200);self.send_header('Content-Type',validate_image_bytes(data)['mime']);self.end_headers();self.wfile.write(data)
                    except Exception as exc:self.send_json({'error':str(exc)},404)
                    return
                if u.path=='/editor':
                    rid=parse_qs(u.query)['report'][0]
                    bootstrap=outer.payload(outer.repository.get(rid))
                    assets='/company_ui/products/visualizer/assets/'
                    markup=(outer.root/'company_ui/products/visualizer/assets/integrated_editor.html').read_text()
                    doc='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    doc+=f'<base href="{outer.url}/"><link rel="stylesheet" href="{assets}tokens.css"><link rel="stylesheet" href="{assets}integrated_editor.css">'
                    doc+='<style>body{margin:0;font-family:Arial,sans-serif}*{box-sizing:border-box}</style></head><body>'
                    boot=json.dumps(bootstrap,ensure_ascii=False).replace('<','\\u003c')
                    doc+=f'<script>window.__CUI_VISUALIZER_BOOTSTRAP__={boot};{BRIDGE}</script>'+markup
                    doc+=f'<script type="module" src="{assets}integrated_editor.mjs"></script></body></html>'
                    self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.end_headers();self.wfile.write(doc.encode());return
                return super().do_GET()
            def do_POST(self):
                size=int(self.headers.get('Content-Length','0'))
                if size>2_000_000: self.send_json({'error':'too large'},413);return
                m=json.loads(self.rfile.read(size));kind=m.get('type');p=m.get('payload',{});rid=p.get('report_id')
                try:
                    if kind=='report.commit':
                        _validate_model_images(p['model'])
                        r=outer.repository.commit(rid,base_revision=p['base_revision'],model=p['model'],commit_id=p['commit_id'])
                        response={'type':'report.commit_result','payload':{'report_id':rid,'revision':r.revision,'commit_id':p['commit_id']}}
                    elif kind in ('mapping.preferences_requested','preset.preferences_requested'):
                        typ=kind.split('.')[0];response={'type':typ+'.preferences_result','payload':{'presets':outer.preferences.get(typ,[])}}
                    elif kind in ('mapping.preferences_save_requested','preset.preferences_save_requested'):
                        typ=kind.split('.')[0];outer.preferences[typ]=p['presets'];response={'type':typ+'.preferences_result','payload':{'presets':p['presets'],'saved':True}}
                    else:response={'type':'application.notification','payload':{'message':'Test host: unsupported event '+str(kind)}}
                except RevisionConflictError:
                    response={'type':'report.conflict','payload':dict(outer.payload(outer.repository.get(rid)),rejected_commit_id=p['commit_id'])}
                except Exception as exc:
                    response={'type':'report.error','payload':{'message':str(exc),'commit_id':p.get('commit_id'),'report_id':rid}}
                response['bridge_version']=1;self.send_json(response)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(self.root)))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.http.server_port}'
        return self
    def __exit__(self,*args):
        if self.http:self.http.shutdown();self.http.server_close()
        if self.thread:self.thread.join(timeout=3)

class NativeHost(EditorHost):
    """Synthetic report data served by the actual NiceGUI CLI.

    No test bridge or replacement application code is installed in this mode.
    Working directory, user storage, port and report data are isolated.  The
    explicit stop/restart methods exist only for native recovery verification.
    """
    native=True

    def create(self, model=None, name=None):
        """Create an isolated native fixture with an explicit local owner.

        Native acceptance fixtures may be created before or after the NiceGUI
        process starts.  Registering the fixture in the same ACL sidecar used
        by the application keeps the harness faithful to the production
        resource boundary without broadening access to real user data.
        """
        report_id = super().create(model=model, name=name)
        from company_ui.products.visualizer.governance import ReportAccessCatalog

        ReportAccessCatalog(self.repository).migrate(
            [self.repository.get(report_id)],
            owner_subject="local-dev",
            require_explicit_owner=True,
        )
        return report_id

    def __init__(self, root: Path, data: Path):
        super().__init__(root,data)
        self.port=None; self.url=None; self.process=None; self.log=None
        self.log_path=self.data/'native-server.log'

    @staticmethod
    def _free_port():
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

    def _start(self, *, reuse_port: bool=False):
        import importlib.metadata, os, subprocess, sys, time
        from urllib.request import urlopen
        if importlib.metadata.version('nicegui')!='3.15.0':
            raise RuntimeError('The declared NiceGUI 3.15.0 runtime is required.')
        self.data.mkdir(parents=True,exist_ok=True)
        if self.port is None or not reuse_port:self.port=self._free_port()
        self.url=f'http://127.0.0.1:{self.port}'
        env=os.environ|{
            'PYTHONPATH':str(self.root),
            'COMPANY_UI_HOST':'127.0.0.1',
            'COMPANY_UI_PORT':str(self.port),
            # NiceGUI's screen-test runtime reads this dedicated port when a
            # native host is launched from pytest instead of the release
            # runner. Keep it identical to the isolated application port.
            'NICEGUI_SCREEN_TEST_PORT':str(self.port),
            'COMPANY_UI_VISUALIZER_DATA_DIR':str(self.data),
            'COMPANY_UI_ENVIRONMENT':'test',
            'PYTHONUNBUFFERED':'1',
        }
        self.log=self.log_path.open('a',encoding='utf-8')
        self.process=subprocess.Popen(
            [sys.executable,'-m','company_ui.products.visualizer.cli'],
            cwd=self.data,env=env,stdout=self.log,stderr=subprocess.STDOUT,
        )
        for _ in range(160):
            if self.process.poll() is not None:
                self.log.flush();self.log.close()
                raise RuntimeError(self.log_path.read_text(encoding='utf-8',errors='replace')[-12000:])
            try:
                with urlopen(self.url+'/visualizer',timeout=1) as response:
                    if response.status==200:return self
            except Exception:time.sleep(.25)
        self.stop();raise TimeoutError('Isolated NiceGUI startup exceeded 40 seconds.')

    def __enter__(self):
        return self._start()

    def stop(self):
        import subprocess
        process=getattr(self,'process',None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
        self.process=None
        if getattr(self,'log',None) and not self.log.closed:
            self.log.flush();self.log.close()
        self.log=None

    def restart(self):
        import time
        port=self.port
        self.stop();time.sleep(.35);self.port=port
        return self._start(reuse_port=True)

    def __exit__(self,*args):
        self.stop()


def load_editor(page, host, report_id):
    if getattr(host,'native',False):
        page.goto(host.url+'/visualizer',wait_until='domcontentloaded')
    else:
        from urllib.request import urlopen
        page.set_content(urlopen(host.url+'/editor?report='+report_id).read().decode(),wait_until='load')
