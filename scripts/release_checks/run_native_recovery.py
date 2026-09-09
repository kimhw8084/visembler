#!/usr/bin/env python3
"""Native NiceGUI disconnect/restart recovery verification.

Uses only a temporary synthetic report repository and one isolated browser
context. Network failures during deliberately injected outages are recorded as
expected fault events; failures after recovery are release-blocking.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import NativeHost
from native_common import BrowserEvents,browser_kwargs,edit_text,item_text,ready,state,text_model,wait_repository_text,write_json
from playwright.sync_api import sync_playwright


def report_value(host,rid):return item_text(host.repository.get(rid).model)

def recover_if_needed(page,host,rid,value):
    current=state(page)
    if current.get('recovery'):
        button=page.locator('#saveBtn');button.wait_for(state='visible');button.click()
    wait_repository_text(host.repository,rid,value,timeout=20)
    page.wait_for_function('()=>{const s=CompanyUIVisualizerBridge.state();return !s.recovery&&s.pending===0&&!s.inflight}',timeout=20000)


def reopen_after_restart(page, host):
    """Open a fresh document after NativeHost has completed its bounded restart.

    Reloading the old NiceGUI frame races the browser's closing transport and
    can raise ERR_ABORTED even after the new server is healthy.  A same-origin
    navigation exercises the same recovery path without depending on that
    stale frame lifecycle.
    """
    page.goto(host.url + '/visualizer', wait_until='domcontentloaded', timeout=20000)


def fresh_page_after_restart(context, host, events):
    """Use a new page in the same context after a server restart.

    The context retains the recovery journal in local storage, while the new
    page avoids navigation races with the old NiceGUI transport document.
    """
    page = context.new_page()
    events.attach(page)
    page.goto(host.url + '/visualizer', wait_until='domcontentloaded', timeout=20000)
    return page


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'screenshots').mkdir(exist_ok=True)
    result={'scope':'native NiceGUI synthetic recovery','cases':[],'unexpected_errors':[],'expected_fault_events':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='visembler-native-recovery-') as td, sync_playwright() as pw:
            data=Path(td)/'data';host=NativeHost(ROOT,data);rid=host.create(model=text_model('Seed'))
            with host:
                browser=pw.chromium.launch(**browser_kwargs());ctx=browser.new_context(viewport={'width':1280,'height':900})
                events=BrowserEvents();p=ctx.new_page();events.attach(p);p.goto(host.url+'/visualizer',wait_until='domcontentloaded');ready(p,require_settled=True)
                assert report_value(host,rid)=='Seed'

                # C01: browser transport loss. Make a local edit while offline, then
                # reconnect/reload. The edit must either have arrived on reconnect or
                # be explicitly recoverable from the local journal; silent loss fails.
                c={'name':'socket-disconnect-local-draft-recovery','status':'FAIL','steps':[]};result['cases'].append(c)
                try:
                    events.fault=True;ctx.set_offline(True);p.wait_for_timeout(700)
                    edit_text(p,'Offline draft',settle=False)
                    p.wait_for_function('()=>CompanyUIVisualizerBridge.state().pending>=1',timeout=8000)
                    journal=p.evaluate('(k)=>localStorage.getItem(k)',f'viz-pending-report:{rid}')
                    assert journal and 'Offline draft' in journal
                    c['steps']+=['offline edit journaled','pending commit retained']
                    p.screenshot(path=str(out/'screenshots'/'01-offline-draft.png'))
                    ctx.set_offline(False);p.wait_for_timeout(900)
                    reopen_after_restart(p,host);ready(p);events.fault=False
                    recover_if_needed(p,host,rid,'Offline draft')
                    assert report_value(host,rid)=='Offline draft'
                    c['steps']+=['reconnected','draft persisted/recovered'];c['status']='PASS'
                    p.screenshot(path=str(out/'screenshots'/'02-offline-recovered.png'))
                except Exception as exc:
                    c['error']=str(exc);c['traceback']=traceback.format_exc()

                # C02: process restart on the same origin. An edit made while the
                # server is down must survive local reload and apply exactly once.
                c={'name':'server-restart-local-draft-recovery','status':'FAIL','steps':[]};result['cases'].append(c)
                try:
                    edit_text(p,'Stable before restart',settle=True)
                    stable=wait_repository_text(host.repository,rid,'Stable before restart')
                    before_revision=stable.revision
                    events.fault=True;host.stop();p.wait_for_timeout(700)
                    edit_text(p,'Restart draft',settle=False)
                    p.wait_for_function('()=>CompanyUIVisualizerBridge.state().pending>=1',timeout=8000)
                    journal=p.evaluate('(k)=>localStorage.getItem(k)',f'viz-pending-report:{rid}')
                    assert journal and 'Restart draft' in journal
                    c['steps']+=['server stopped','offline edit journaled']
                    p.screenshot(path=str(out/'screenshots'/'03-server-down-draft.png'))
                    host.restart()
                    p.reload(wait_until='domcontentloaded');ready(p);events.fault=False
                    recover_if_needed(p,host,rid,'Restart draft')
                    recovered=host.repository.get(rid)
                    assert recovered.revision==before_revision+1,(before_revision,recovered.revision)
                    c['steps']+=['server restarted same origin','draft recovered once']
                    # A second restart proves durable server persistence and that the
                    # recovery journal is not replayed again.
                    revision_after=recovered.revision
                    events.fault=True;host.restart()
                    p.close()
                    p=fresh_page_after_restart(ctx,host,events);ready(p,require_settled=True);events.fault=False
                    assert report_value(host,rid)=='Restart draft'
                    assert host.repository.get(rid).revision==revision_after
                    assert not state(p).get('recovery')
                    c['steps']+=['second restart durable','no duplicate replay'];c['status']='PASS'
                    p.screenshot(path=str(out/'screenshots'/'04-restart-recovered.png'))
                except Exception as exc:
                    c['error']=str(exc);c['traceback']=traceback.format_exc()
                finally:
                    if host.process is None:
                        try:host.restart()
                        except Exception:pass

                result['unexpected_errors']=events.unexpected
                result['expected_fault_events']=events.expected_fault
                if host.log_path.exists():
                    (out/'native-server.log').write_text(host.log_path.read_text(encoding='utf-8',errors='replace'),encoding='utf-8')
                ctx.close();browser.close()
    except Exception as exc:
        result['harness_error']=str(exc);result['traceback']=traceback.format_exc()
    result['passed']=sum(case.get('status')=='PASS' for case in result['cases'])
    result['total']=2
    result['status']='PASS' if result['passed']==2 and not result['unexpected_errors'] and 'harness_error' not in result else 'FAIL'
    result['source_editor_sha256']=hashlib.sha256((ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest()
    write_json(out/'native-recovery.json',result);print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
