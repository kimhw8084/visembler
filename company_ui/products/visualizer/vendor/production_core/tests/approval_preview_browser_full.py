#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
PROD=Path(__file__).resolve().parents[1]

def strip_module(src):
    src=re.sub(r"^import .*?;\s*$","",src,flags=re.M)
    src=src.replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
    return src

def bundle_html():
    html=(PROD/'app/approval/index.html').read_text()
    tokens=(PROD/'app/tokens.css').read_text()
    css=(PROD/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'')
    js='\n'.join(strip_module((PROD/p).read_text()) for p in ['core/runtime_registry.mjs','core/universal_renderer.mjs','core/grid_layout_engine.mjs','core/data_grid_engine.mjs','app/approval/preview.mjs'])
    return html.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{tokens}\n{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script type="module">{js}</script>')

report={'pass':False,'console_errors':[],'checks':{},'viewports':{}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
    for label,viewport in [('desktop',{'width':1440,'height':1000}),('phone',{'width':390,'height':844})]:
        page=browser.new_page(viewport=viewport)
        errs=[];page.on('console',lambda m,e=errs:e.append(f'{m.type}:{m.text}') if m.type=='error' else None);page.on('pageerror',lambda e,er=errs:er.append(f'pageerror:{e}'))
        page.set_content(bundle_html(),wait_until='load'); page.wait_for_timeout(350)
        cards=page.locator('.gallery-card').count(); engines=page.locator('.engine-section').count()
        report['checks'][f'{label}_248_cards']=cards==248;report['checks'][f'{label}_17_engines']=engines==17
        geom=page.evaluate("""() => { const vw=document.documentElement.clientWidth; const bad=[...document.querySelectorAll('body *')].filter(e=>e.offsetParent!==null).map(e=>e.getBoundingClientRect()).filter(r=>r.left < -1 || r.right > vw+1); const texts=[...document.querySelectorAll('.gallery-card *')].filter(e=>e.offsetParent!==null&&e.children.length===0&&e.textContent.trim()); const fonts=texts.map(e=>parseFloat(getComputedStyle(e).fontSize)).filter(Number.isFinite); return {horizontalOverflow:bad.length,minFont:Math.min(...fonts),docWidth:document.documentElement.scrollWidth,vw}; }""")
        report['checks'][f'{label}_no_horizontal_overflow']=geom['horizontalOverflow']==0 and geom['docWidth']<=geom['vw']+1;report['checks'][f'{label}_font_floor']=geom['minFont']>=10
        ctrls=page.evaluate("""() => [...document.querySelectorAll('button,input,select')].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return {name:e.getAttribute('aria-label')||e.textContent.trim()||e.placeholder||'',w:r.width,h:r.height}})""")
        report['checks'][f'{label}_controls_named']=all(x['name'] for x in ctrls); floor=43.5 if label=='phone' else 35.5;report['checks'][f'{label}_control_targets']=all(x['h']>=floor for x in ctrls)
        page.locator('#gallerySearch').fill('wafer');filtered=page.locator('.gallery-card').count(); report['checks'][f'{label}_search']=1<=filtered<248;page.locator('#gallerySearch').fill('')
        for _ in range(2): page.locator('#themeBtn').click()
        report['checks'][f'{label}_theme']=page.locator('.preview-app').get_attribute('data-theme')=='corporate'
        page.get_by_role('button',name='Dynamic Grid').click();page.wait_for_timeout(80);report['checks'][f'{label}_dynamic_grid']=page.locator('#slideStage .sim-item').count()==5
        target=page.locator('#slideTarget').bounding_box();stage=page.locator('#slideStage').bounding_box();report['checks'][f'{label}_target_inside_slide']=bool(target and stage and target['x']>=stage['x']-1 and target['y']>=stage['y']-1 and target['x']+target['width']<=stage['x']+stage['width']+1 and target['y']+target['height']<=stage['y']+stage['height']+1)
        page.get_by_role('button',name='100k Grid').click();page.wait_for_timeout(1500);rendered=page.locator('.vg-row').count();meta=page.locator('#gridMeta').inner_text();report['checks'][f'{label}_100k_grid']=0<rendered<100 and '100,000' in meta
        page.locator('#gridFilter').fill('ETCH-12');page.wait_for_timeout(500);report['checks'][f'{label}_typed_filter']='rows' in page.locator('#gridMeta').inner_text()
        page.get_by_role('button',name='PPT Region').click();page.wait_for_timeout(80);report['checks'][f'{label}_ppt_middle_region']=page.locator('#exportStage .sim-item').count()==5
        page.screenshot(path=str(PROD/f'qa/approval_preview_{label}.png'),full_page=True)
        report['viewports'][label]={'cards':cards,'engines':engines,'geometry':geom,'visibleControls':len(ctrls),'virtualRows':rendered,'gridMeta':meta};report['console_errors']+=errs;page.close()
    browser.close()
report['pass']=not report['console_errors'] and all(report['checks'].values());(PROD/'qa/approval_preview_browser.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
