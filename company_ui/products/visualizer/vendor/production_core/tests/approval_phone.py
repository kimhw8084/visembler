#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
PROD=Path(__file__).resolve().parents[1]

def strip(src): return re.sub(r'^import .*?;\s*$','',src,flags=re.M).replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
def bundle_html():
    rt=strip((PROD/'core/runtime_registry.mjs').read_text())+'\nglobalThis.__REG={ELEMENTS_BY_ENGINE,ALL_ELEMENTS};'
    ur=strip((PROD/'core/universal_renderer.mjs').read_text())+'\nglobalThis.__RENDER={renderElement,findEngineForElement,renderEngineGallery,renderAllElements};'
    gl=strip((PROD/'core/grid_layout_engine.mjs').read_text())+'\nglobalThis.__GRID={compileGridLayout,findLargestEmptyRegion,mapPlacementToRegion};'
    dg=strip((PROD/'core/data_grid_engine.mjs').read_text())+'\nglobalThis.__DATA={prepareDataGrid,gridVirtualWindow,rowAt};'
    pv=re.sub(r'^import .*?;\s*$','',(PROD/'app/approval/preview.mjs').read_text(),flags=re.M)
    pv="const {ELEMENTS_BY_ENGINE}=globalThis.__REG; const {renderElement}=globalThis.__RENDER; const {compileGridLayout,findLargestEmptyRegion}=globalThis.__GRID; const {prepareDataGrid,gridVirtualWindow}=globalThis.__DATA;\n"+pv
    js=';\n'.join([f'(()=>{{{rt}}})()',f'(()=>{{const {{ELEMENTS_BY_ENGINE}}=globalThis.__REG;{ur}}})()',f'(()=>{{{gl}}})()',f'(()=>{{{dg}}})()',pv])
    html=(PROD/'app/approval/index.html').read_text();css=(PROD/'app/tokens.css').read_text()+(PROD/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'')
    return html.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script>{js}</script>')

def percentile(vals,p):
    vals=sorted(vals);return vals[min(len(vals)-1,max(0,int((len(vals)-1)*p)))] if vals else 0

report={'pass':False,'checks':{},'console_errors':[],'viewports':{}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
    for label,viewport in [('phone',{'width':390,'height':844})]:
        page=browser.new_page(viewport=viewport);errs=[]
        page.on('console',lambda m,e=errs:e.append(f'{m.type}: {m.text}') if m.type=='error' else None);page.on('pageerror',lambda e,er=errs:er.append(f'pageerror: {e}'))
        page.set_content(bundle_html(),wait_until='load');page.wait_for_timeout(350)
        cards=page.locator('.gallery-card').count();engines=page.locator('.engine-section').count()
        report['checks'][f'{label}_248_cards']=cards==248;report['checks'][f'{label}_17_engines']=engines==17
        geom=page.evaluate("""() => {const vw=document.documentElement.clientWidth;const bad=[...document.querySelectorAll('body *')].filter(e=>e.offsetParent!==null).map(e=>e.getBoundingClientRect()).filter(r=>r.left<-1||r.right>vw+1);const texts=[...document.querySelectorAll('.gallery-card *')].filter(e=>e.offsetParent!==null&&e.children.length===0&&e.textContent.trim());const fonts=texts.map(e=>parseFloat(getComputedStyle(e).fontSize)).filter(Number.isFinite);return{horizontalOverflow:bad.length,minFont:Math.min(...fonts),docWidth:document.documentElement.scrollWidth,vw};}""")
        report['checks'][f'{label}_no_horizontal_overflow']=geom['horizontalOverflow']==0 and geom['docWidth']<=geom['vw']+1;report['checks'][f'{label}_font_floor']=geom['minFont']>=10
        ctrls=page.evaluate("""() => [...document.querySelectorAll('button,input,select')].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return{name:e.getAttribute('aria-label')||e.textContent.trim()||e.placeholder||'',h:r.height,w:r.width}})""")
        report['checks'][f'{label}_controls_named']=all(x['name'] for x in ctrls);floor=43.5 if label=='phone' else 35.5;report['checks'][f'{label}_control_targets']=all(x['h']>=floor for x in ctrls)
        # Search/filter and theme.
        page.locator('#gallerySearch').fill('wafer');report['checks'][f'{label}_search']=1<=page.locator('.gallery-card').count()<248;page.locator('#gallerySearch').fill('')
        page.locator('#engineFilter').select_option('CoreChartEngine');report['checks'][f'{label}_engine_filter']=page.locator('.gallery-card').count()==29;page.locator('#engineFilter').select_option('all')
        page.locator('#themeBtn').click();page.locator('#themeBtn').click();report['checks'][f'{label}_theme']=page.locator('.preview-app').get_attribute('data-theme')=='corporate'
        # Layout compile and arbitrary size.
        page.get_by_role('button',name='Dynamic Grid').click();page.wait_for_timeout(80);report['checks'][f'{label}_dynamic_grid']=page.locator('#slideStage .sim-item').count()==5
        page.locator('#pageW').fill('10');page.locator('#pageH').fill('8');page.locator('#recompileBtn').click();page.wait_for_timeout(40);report['checks'][f'{label}_arbitrary_canvas']='10.00 × 8.00' in page.locator('#layoutMeta').inner_text()
        # 100k grid and retained rows; exercise scroll frames.
        page.get_by_role('button',name='100k Grid').click();page.wait_for_timeout(950)
        grid=page.locator('#virtualGrid');times=[]
        for pos in [0,5000,20000,50000,120000,500000,900000,2500000,0,1500000,3000000]:
            t=time.perf_counter();grid.evaluate('(e,y)=>e.scrollTop=y',pos);page.wait_for_timeout(20);times.append((time.perf_counter()-t)*1000)
        visible=page.locator('.vg-row:visible').count();retained=page.locator('.vg-row').count();meta=page.locator('#gridMeta').inner_text()
        report['checks'][f'{label}_100k_grid']='100,000' in meta and visible<70 and retained<=80;report['checks'][f'{label}_retained_grid']=retained==80
        page.locator('#gridFilter').fill('ETCH-12');page.wait_for_timeout(250);report['checks'][f'{label}_typed_filter']='rows' in page.locator('#gridMeta').inner_text()
        # Keyboard row movement.
        page.locator('#gridFilter').fill('');page.wait_for_timeout(120);grid.evaluate('(e)=>e.scrollTop=0');page.wait_for_timeout(80);first=page.locator('.vg-row:visible').first;first.focus();page.keyboard.press('ArrowDown');page.wait_for_timeout(60);active=page.evaluate('document.activeElement?.dataset?.index');report['checks'][f'{label}_keyboard_grid']=active=='1'
        # PPT region simulation.
        page.get_by_role('button',name='PPT Region').click();page.wait_for_timeout(70);report['checks'][f'{label}_ppt_middle_region']=page.locator('#exportStage .sim-item').count()==5
        page.screenshot(path=str(PROD/f'qa/approval_preview_{label}.png'),full_page=False)
        report['viewports'][label]={'cards':cards,'engines':engines,'geometry':geom,'controls':len(ctrls),'visibleVirtualRows':visible,'retainedVirtualRows':retained,'gridMeta':meta,'browserActionP95Ms':round(percentile(times,.95),2)}
        report['console_errors']+=errs;page.close()
    browser.close()
report['pass']=not report['console_errors'] and all(report['checks'].values());(PROD/'qa/approval_preview_browser.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
