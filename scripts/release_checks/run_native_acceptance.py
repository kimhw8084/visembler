#!/usr/bin/env python3
"""Targeted final responsive, keyboard and visual acceptance on native NiceGUI."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from editor_host import NativeHost
from native_common import BrowserEvents,acceptance_model,browser_kwargs,ready,write_json
from playwright.sync_api import sync_playwright

VIEWPORTS=[('desktop-1440',1440,900),('desktop-1024',1024,800),('tablet-768',768,900),('mobile-480',480,820),('mobile-390',390,844),('mobile-360',360,740)]


def visible_control_violations(page):
    return page.evaluate("""()=>[...document.querySelectorAll('.cui-visualizer-reportbar button,.cui-visualizer-reportbar input,.cui-visualizer-reportbar select,.cui-visualizer-root button,.cui-visualizer-root input,.cui-visualizer-root select,.cui-visualizer-root textarea')].filter(n=>n.offsetParent!==null).map(n=>{const r=n.getBoundingClientRect();return {label:n.getAttribute('aria-label')||n.textContent.trim()||n.id,left:r.left,right:r.right,top:r.top,bottom:r.bottom};}).filter(r=>r.left<-1||r.right>innerWidth+1)""")


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);shots=out/'screenshots';shots.mkdir(exist_ok=True)
    report={'scope':'native final responsive/keyboard/visual acceptance','cases':[],'unexpected_errors':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='visembler-acceptance-') as td, NativeHost(ROOT,Path(td)/'data') as host, sync_playwright() as pw:
            host.create(model=acceptance_model());browser=pw.chromium.launch(**browser_kwargs());ctx=browser.new_context();events=BrowserEvents();page=ctx.new_page();events.attach(page)
            for vp,w,h in VIEWPORTS:
                page.set_viewport_size({'width':w,'height':h});page.goto(host.url+'/visualizer',wait_until='domcontentloaded');ready(page,require_settled=True)
                for theme in ('light','dark'):
                    case={'name':f'{vp}-{theme}','status':'FAIL','checks':[]};report['cases'].append(case)
                    try:
                        page.evaluate('(t)=>__VIZ_PROD__.setTheme(t)',theme);page.wait_for_timeout(120)
                        overflow=page.evaluate('()=>document.documentElement.scrollWidth-innerWidth');assert overflow<=1,overflow
                        violations=visible_control_violations(page);assert not violations,violations[:4]
                        preflight=page.evaluate('()=>__VIZ_PROD__.preflight()');assert preflight['controls']==0,preflight['warnings']
                        case['checks']+=['no document horizontal overflow','visible controls viewport-contained','no wrapped editor controls']

                        # Keyboard command palette and focus return.
                        page.locator('#commandBtn').focus();page.keyboard.press('ControlOrMeta+k');page.locator('#cmdModal.show').wait_for();assert page.locator('#cmdInput').evaluate('(n)=>document.activeElement===n')
                        page.keyboard.press('Escape');page.wait_for_function('()=>!document.querySelector("#cmdModal")?.classList.contains("show")')
                        case['checks'].append('keyboard command palette + escape')

                        # Keyboard-select a semantic component.
                        component=page.locator('.component').first;component.focus();page.keyboard.press('Enter');assert component.get_attribute('aria-selected')=='true'
                        case['checks'].append('keyboard component selection')

                        if w<=800:
                            # Mobile drawer mutual exclusion and active button state.
                            if page.locator('#libraryToggle').get_attribute('aria-pressed')=='true':page.locator('#libraryToggle').click()
                            if page.locator('#inspectorToggle').get_attribute('aria-pressed')=='true':page.locator('#inspectorToggle').click()
                            page.locator('#libraryToggle').click();assert page.locator('#libraryToggle').get_attribute('aria-pressed')=='true';assert page.locator('#inspectorToggle').get_attribute('aria-pressed')=='false'
                            page.locator('#inspectorToggle').click();assert page.locator('#inspectorToggle').get_attribute('aria-pressed')=='true';assert page.locator('#libraryToggle').get_attribute('aria-pressed')=='false'
                            case['checks'].append('mobile drawer mutual exclusion + state')
                        elif vp=='desktop-1440' and theme=='dark':
                            # Host chrome/dialog dark surface regression.
                            bar=page.locator('.cui-visualizer-reportbar');bg=bar.evaluate('(n)=>getComputedStyle(n).backgroundColor');assert bg not in ('rgb(255, 255, 255)','rgba(255, 255, 255, 1)'),bg
                            page.get_by_role('button',name=re.compile(r'^New report$',re.I)).click();card=page.locator('.q-dialog .cui-dialog-card').last;card.wait_for(state='visible');card_bg=card.evaluate('(n)=>getComputedStyle(n).backgroundColor');assert card_bg not in ('rgb(255, 255, 255)','rgba(255, 255, 255, 1)'),card_bg
                            case['checks'].append('dark host reportbar/dialog surfaces');page.screenshot(path=str(shots/'desktop-1440-dark-dialog.png'));page.keyboard.press('Escape')

                        page.screenshot(path=str(shots/f'{vp}-{theme}.png'));case['status']='PASS'
                    except Exception as exc:
                        case['error']=str(exc);case['traceback']=traceback.format_exc()
                        try:page.screenshot(path=str(shots/f'{vp}-{theme}-failure.png'))
                        except Exception:pass
            report['unexpected_errors']=events.unexpected
            if host.log_path.exists():(out/'native-server.log').write_text(host.log_path.read_text(encoding='utf-8',errors='replace'),encoding='utf-8')
            ctx.close();browser.close()
    except Exception as exc:report['harness_error']=str(exc);report['traceback']=traceback.format_exc()
    report['passed']=sum(c.get('status')=='PASS' for c in report['cases']);report['total']=len(VIEWPORTS)*2
    report['status']='PASS' if report['passed']==report['total'] and not report['unexpected_errors'] and 'harness_error' not in report else 'FAIL'
    report['source_editor_sha256']=hashlib.sha256((ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_bytes()).hexdigest()
    write_json(out/'native-acceptance.json',report);print(json.dumps(report,indent=2,ensure_ascii=False));return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
