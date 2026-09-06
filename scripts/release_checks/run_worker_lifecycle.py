#!/usr/bin/env python3
"""Exercise the actual browser module-worker failure/cancel/retry lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import NativeHost
from native_common import BrowserEvents,browser_kwargs,ready,write_json
from playwright.sync_api import sync_playwright


def large_grid(rows=30000,offset=0):
    return 'category\tvalue\n'+''.join(f'A{i+offset:05d}\t{(i+offset)%10}\n' for i in range(rows))


def inject_text(page,text):
    page.locator('#dataFirstText').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}))}',text)


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'screenshots').mkdir(exist_ok=True)
    report={'scope':'native NiceGUI + real browser Worker','cases':[],'unexpected_errors':[],'expected_fault_events':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='visembler-worker-') as td, NativeHost(ROOT,Path(td)/'data') as host, sync_playwright() as pw:
            browser=pw.chromium.launch(**browser_kwargs());ctx=browser.new_context(viewport={'width':1280,'height':900});events=BrowserEvents()
            p=ctx.new_page();events.attach(p);p.goto(host.url+'/visualizer',wait_until='domcontentloaded');ready(p,require_settled=True)
            pattern='**/authoring_data_worker.mjs*'

            # B05a: fail the real module-worker script load. Product must surface
            # an actionable error and clear its loading state.
            case={'name':'worker-load-failure-visible','status':'FAIL'};report['cases'].append(case)
            hit={'count':0}
            try:
                def fail_worker(route):
                    hit['count']+=1;route.abort()
                ctx.route(pattern,fail_worker);events.fault=True
                p.locator('#pasteDataBtn').click();inject_text(p,large_grid())
                p.wait_for_function('()=>__VIZ_PROD__.ui.dataFirst && !__VIZ_PROD__.ui.dataFirst.loading && !!__VIZ_PROD__.ui.dataFirst.error',timeout=15000)
                events.fault=False
                assert hit['count']>=1,'worker request was not exercised'
                status=p.locator('.data-first-status.error');status.wait_for(state='visible');text=status.inner_text()
                assert 'failed' in text.lower() or 'parser' in text.lower(),text
                case.update(status='PASS',worker_requests=hit['count'],visible_error=text)
                p.screenshot(path=str(out/'screenshots'/'01-worker-failure.png'))
            except Exception as exc:
                events.fault=False;case['error']=str(exc);case['traceback']=traceback.format_exc()
            finally:
                try:ctx.unroute(pattern)
                except Exception:pass

            # B05b: the next large parse must construct a new real worker and
            # succeed without page reload or a permanent loading state.
            case={'name':'worker-retry-after-failure','status':'FAIL'};report['cases'].append(case)
            try:
                inject_text(p,large_grid(offset=40000))
                p.wait_for_function('()=>__VIZ_PROD__.ui.dataFirst?.intake?.rows?.length===30000 && !__VIZ_PROD__.ui.dataFirst.loading',timeout=25000)
                assert not p.evaluate('()=>__VIZ_PROD__.ui.dataFirst.error')
                case['status']='PASS';case['rows']=p.evaluate('()=>__VIZ_PROD__.ui.dataFirst.intake.rows.length')
                p.screenshot(path=str(out/'screenshots'/'02-worker-retry-success.png'))
            except Exception as exc:
                case['error']=str(exc);case['traceback']=traceback.format_exc()

            # B05c: superseded/cancelled work cannot mutate a closed dialog. A
            # delayed module worker imports the real parser but responds later.
            case={'name':'worker-cancel-stale-result-isolated','status':'FAIL'};report['cases'].append(case)
            try:
                p.locator('#genericModal').get_by_role('button',name='Cancel',exact=True).click();p.wait_for_timeout(200)
                delayed="""import { intakeText } from './authoring_data.mjs';\nself.onmessage=({data})=>setTimeout(()=>{try{self.postMessage({id:data.id,result:intakeText(data.text)})}catch(error){self.postMessage({id:data.id,error:String(error?.message||error)})}},1800);"""
                def delay_worker(route):
                    route.fulfill(status=200,content_type='text/javascript; charset=utf-8',body=delayed)
                ctx.route(pattern,delay_worker)
                p.locator('#pasteDataBtn').click();inject_text(p,large_grid(offset=80000))
                p.wait_for_function('()=>__VIZ_PROD__.ui.dataFirst?.loading===true',timeout=8000)
                p.locator('#genericModal').get_by_role('button',name='Cancel',exact=True).click()
                p.wait_for_timeout(2400)
                assert p.evaluate('()=>__VIZ_PROD__.ui.dataFirst===null')
                assert not p.locator('#genericModal').evaluate('(n)=>n.classList.contains("show")')
                case['status']='PASS'
                p.screenshot(path=str(out/'screenshots'/'03-worker-cancelled.png'))
            except Exception as exc:
                case['error']=str(exc);case['traceback']=traceback.format_exc()
            finally:
                try:ctx.unroute(pattern)
                except Exception:pass

            # B05d: cancellation also leaves the parser reusable.
            case={'name':'worker-retry-after-cancel','status':'FAIL'};report['cases'].append(case)
            try:
                p.locator('#pasteDataBtn').click();inject_text(p,large_grid(offset=120000))
                p.wait_for_function('()=>__VIZ_PROD__.ui.dataFirst?.intake?.rows?.length===30000 && !__VIZ_PROD__.ui.dataFirst.loading',timeout=25000)
                case['status']='PASS'
                p.screenshot(path=str(out/'screenshots'/'04-worker-post-cancel-success.png'))
            except Exception as exc:
                case['error']=str(exc);case['traceback']=traceback.format_exc()

            report['unexpected_errors']=events.unexpected;report['expected_fault_events']=events.expected_fault
            if host.log_path.exists():(out/'native-server.log').write_text(host.log_path.read_text(encoding='utf-8',errors='replace'),encoding='utf-8')
            ctx.close();browser.close()
    except Exception as exc:
        report['harness_error']=str(exc);report['traceback']=traceback.format_exc()
    report['passed']=sum(c.get('status')=='PASS' for c in report['cases']);report['total']=4
    report['status']='PASS' if report['passed']==4 and not report['unexpected_errors'] and 'harness_error' not in report else 'FAIL'
    report['source_editor_sha256']=hashlib.sha256((ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest()
    write_json(out/'worker-lifecycle.json',report);print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
