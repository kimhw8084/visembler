#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, statistics
from pathlib import Path
from playwright.sync_api import sync_playwright

PROD = Path(__file__).resolve().parents[1]
QA = PROD/'qa'
QA.mkdir(exist_ok=True)

def strip(src: str) -> str:
    return re.sub(r'^import .*?;\s*$', '', src, flags=re.M).replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')

def bundle_html() -> str:
    rt=strip((PROD/'core/runtime_registry.mjs').read_text())+'\nglobalThis.__REG={ELEMENTS_BY_ENGINE,ALL_ELEMENTS};'
    ur=strip((PROD/'core/universal_renderer.mjs').read_text())+'\nglobalThis.__RENDER={renderElement,findEngineForElement,renderEngineGallery,renderAllElements};'
    gl=strip((PROD/'core/grid_layout_engine.mjs').read_text())+'\nglobalThis.__GRID={compileGridLayout,findLargestEmptyRegion,mapPlacementToRegion};'
    dg=strip((PROD/'core/data_grid_engine.mjs').read_text())+'\nglobalThis.__DATA={prepareDataGrid,gridVirtualWindow,rowAt};'
    pv=re.sub(r'^import .*?;\s*$','',(PROD/'app/approval/preview.mjs').read_text(),flags=re.M)
    pv="const {ELEMENTS_BY_ENGINE}=globalThis.__REG; const {renderElement}=globalThis.__RENDER; const {compileGridLayout,findLargestEmptyRegion}=globalThis.__GRID; const {prepareDataGrid,gridVirtualWindow}=globalThis.__DATA;\n"+pv
    js=';\n'.join([f'(()=>{{{rt}}})()',f'(()=>{{const {{ELEMENTS_BY_ENGINE}}=globalThis.__REG;{ur}}})()',f'(()=>{{{gl}}})()',f'(()=>{{{dg}}})()',pv])
    html=(PROD/'app/approval/index.html').read_text()
    css=(PROD/'app/tokens.css').read_text()+(PROD/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'')
    return html.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script>{js}</script>')

def pct(vals, q):
    vals=sorted(vals)
    return vals[min(len(vals)-1,max(0,round((len(vals)-1)*q)))] if vals else 0.0

report={'pass':False,'viewports':{},'checks':{},'console_errors':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
    for label, viewport, target_floor in [
        ('desktop', {'width':1440,'height':1000}, 32),
        ('tablet', {'width':900,'height':1100}, 44),
        ('phone', {'width':390,'height':844}, 44),
    ]:
        page=browser.new_page(viewport=viewport)
        errs=[]
        page.on('console', lambda m,e=errs:e.append(f'{m.type}: {m.text}') if m.type=='error' else None)
        page.on('pageerror', lambda e,er=errs:er.append(f'pageerror: {e}'))
        page.emulate_media(reduced_motion='reduce')
        page.set_content(bundle_html(),wait_until='load')
        page.wait_for_timeout(300)
        base=page.evaluate("""() => {
          const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
          const cards=[...document.querySelectorAll('.gallery-card')];
          const leaf=[...document.querySelectorAll('.gallery-card *')].filter(e=>visible(e)&&e.children.length===0&&e.textContent.trim());
          const fonts=leaf.map(e=>parseFloat(getComputedStyle(e).fontSize)).filter(Number.isFinite);
          const svgs=[...document.querySelectorAll('.gallery-card svg')].filter(visible);
          const controls=[...document.querySelectorAll('.gallery-card button,.gallery-card input,.gallery-card select,.gallery-card [tabindex="0"]')].filter(visible);
          const ctl=controls.map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,name:e.getAttribute('aria-label')||e.textContent.trim()||e.getAttribute('title')||'',w:r.width,h:r.height,role:e.getAttribute('role')||''}});
          const cardProblems=cards.map(c=>{const r=c.getBoundingClientRect();const kids=[...c.querySelectorAll('*')].filter(visible);let outside=0;for(const k of kids){const q=k.getBoundingClientRect();if(q.left<r.left-2||q.right>r.right+2||q.top<r.top-2||q.bottom>r.bottom+2)outside++;}return {name:c.dataset.element,outside,scrollX:c.scrollWidth>c.clientWidth+2};}).filter(x=>x.outside||x.scrollX);
          const ids=[...document.querySelectorAll('[id]')].map(e=>e.id); const dup=[...new Set(ids.filter((x,i)=>ids.indexOf(x)!==i))];
          const vw=document.documentElement.clientWidth;const horizontal=[...document.querySelectorAll('body *')].filter(visible).map(e=>({e,r:e.getBoundingClientRect()})).filter(x=>x.r.left<-2||x.r.right>vw+2).map(x=>x.e.className||x.e.id||x.e.tagName);
          const unlabeledSvg=svgs.filter(e=>!(e.getAttribute('aria-label')||e.querySelector('title'))).length;
          const badNames=ctl.filter(x=>!x.name).length;
          const badTargets=ctl.filter(x=>x.w<32-0.1||x.h<32-0.1).length;
          const reduced=[...document.querySelectorAll('.gallery-card')].slice(0,12).map(e=>({t:getComputedStyle(e).transitionDuration,a:getComputedStyle(e).animationDuration}));
          return {cards:cards.length,engines:document.querySelectorAll('.engine-section').length,minFont:Math.min(...fonts),unlabeledSvg,badNames,badTargets,cardProblems:cardProblems.slice(0,12),cardProblemCount:cardProblems.length,duplicateIds:dup,horizontalCount:horizontal.length,docWidth:document.documentElement.scrollWidth,vw,controlCount:ctl.length,reduced};
        }""")
        report['checks'][f'{label}_248']=base['cards']==248 and base['engines']==17
        report['checks'][f'{label}_font_floor']=base['minFont']>=10.99
        report['checks'][f'{label}_aria']=base['unlabeledSvg']==0 and base['badNames']==0
        # CSS switches all interactive chrome to 44px at <=900px; desktop follows 32px floor.
        controls=page.evaluate("""() => [...document.querySelectorAll('button,input,select,[tabindex="0"]')].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,w:r.width,h:r.height,name:e.getAttribute('aria-label')||e.textContent.trim()||e.placeholder||''}})""")
        report['checks'][f'{label}_targets']=all(c['name'] and c['w']>=target_floor-0.5 and c['h']>=target_floor-0.5 for c in controls if c['tag']!='ARTICLE')
        report['checks'][f'{label}_containment']=base['cardProblemCount']==0 and base['horizontalCount']==0 and base['docWidth']<=base['vw']+2
        report['checks'][f'{label}_unique_ids']=not base['duplicateIds']
        report['checks'][f'{label}_reduced_motion']=all((x['t'] in ('0s','0.001ms','0.000001s') or float(x['t'].replace('s','') or 0)<=0.001) for x in base['reduced'])

        # Theme stability: card count and geometry must stay invariant in all themes.
        theme_counts={}
        for theme in ['light','dark','corporate']:
            page.evaluate("t=>document.querySelector('.preview-app').dataset.theme=t", theme)
            page.wait_for_timeout(30)
            theme_counts[theme]=page.evaluate("""() => ({cards:document.querySelectorAll('.gallery-card').length,w:document.documentElement.scrollWidth,vw:document.documentElement.clientWidth})""")
        report['checks'][f'{label}_themes']=all(x['cards']==248 and x['w']<=x['vw']+2 for x in theme_counts.values())

        # Localization-like long labels: inject expansion while preserving layout containment.
        long_result=page.evaluate("""() => {
          const originals=[]; document.querySelectorAll('.gallery-card h3').forEach((e,i)=>{originals.push(e.textContent);e.textContent=e.textContent+' — Extended operational qualification context '+String(i+1).padStart(3,'0');});
          const cards=[...document.querySelectorAll('.gallery-card')]; const bad=cards.filter(c=>c.scrollWidth>c.clientWidth+2); const docBad=document.documentElement.scrollWidth>document.documentElement.clientWidth+2;
          document.querySelectorAll('.gallery-card h3').forEach((e,i)=>e.textContent=originals[i]); return {bad:bad.length,docBad};
        }""")
        report['checks'][f'{label}_long_labels']=long_result['bad']==0 and not long_result['docBad']

        # Keyboard/focus traversal through gallery-specific controls.
        focusable=page.locator('.gallery-card button,.gallery-card [tabindex="0"]').count()
        focus_ok=True
        if focusable:
            page.locator('.gallery-card').first.focus()
            for _ in range(min(focusable+20,90)):
                page.keyboard.press('Tab')
                info=page.evaluate("() => ({tag:document.activeElement?.tagName, name:document.activeElement?.getAttribute('aria-label')||document.activeElement?.textContent?.trim()||''})")
                if info['tag']=='BUTTON' and not info['name']:
                    focus_ok=False;break
        report['checks'][f'{label}_keyboard_focus']=focus_ok

        # Dynamic grid random profile smoke at the UI boundary.
        page.get_by_role('button',name='Dynamic Grid').click();page.wait_for_timeout(40)
        profiles=[(13.333,7.5,12,6,.08),(10,8,16,9,.05),(7.5,13.333,8,12,.06),(16,9,24,8,.04)]
        grid_ok=True
        for w,h,c,r,g in profiles:
            page.locator('#pageW').fill(str(w));page.locator('#pageH').fill(str(h));page.locator('#cols').fill(str(c));page.locator('#rows').fill(str(r));page.locator('#gap').fill(str(g));page.locator('#recompileBtn').click();page.wait_for_timeout(25)
            state=page.evaluate("""() => {const stage=document.querySelector('#slideStage'), target=document.querySelector('#slideTarget'); const sr=stage.getBoundingClientRect(),tr=target.getBoundingClientRect(); const items=[...stage.querySelectorAll('.sim-item')].map(e=>e.getBoundingClientRect()); return {count:items.length, inside:items.every(r=>r.left>=tr.left-1&&r.top>=tr.top-1&&r.right<=tr.right+1&&r.bottom<=tr.bottom+1), targetInside:tr.left>=sr.left-1&&tr.top>=sr.top-1&&tr.right<=sr.right+1&&tr.bottom<=sr.bottom+1};}""")
            grid_ok &= state['count']==5 and state['inside'] and state['targetInside']
        report['checks'][f'{label}_grid_profiles']=bool(grid_ok)

        # 100k retained virtual grid including missing-last descending sort and keyboard end/home.
        page.get_by_role('button',name='100k Grid').click();page.wait_for_timeout(750)
        meta=page.locator('#gridMeta').inner_text(); retained=page.locator('.vg-row').count(); visible=page.locator('.vg-row:visible').count()
        page.locator('#gridSort').select_option('yield:desc');page.wait_for_timeout(160)
        first_yield=page.locator('.vg-row:visible').first.locator('[role="gridcell"]').nth(4).inner_text()
        grid=page.locator('#virtualGrid');grid.evaluate('(e)=>e.scrollTop=0');page.wait_for_timeout(50);row=page.locator('.vg-row:visible').first;row.focus();page.keyboard.press('End');page.wait_for_timeout(80);end_idx=page.evaluate("document.activeElement?.dataset?.index")
        page.keyboard.press('Home');page.wait_for_timeout(80);home_idx=page.evaluate("document.activeElement?.dataset?.index")
        report['checks'][f'{label}_100k_grid']='100,000' in meta and retained==80 and visible<70 and first_yield!='Missing' and end_idx=='99999' and home_idx=='0'

        # PPT safe middle-region simulation must not place generated content over template header/footer.
        page.get_by_role('button',name='PPT Region').click();page.wait_for_timeout(50)
        export_state=page.evaluate("""() => {const stage=document.querySelector('#exportStage'), target=document.querySelector('#exportTarget'), tr=target.getBoundingClientRect();const items=[...stage.querySelectorAll('.sim-item')].map(e=>e.getBoundingClientRect());const hr=stage.querySelector('.slide-header').getBoundingClientRect(),fr=stage.querySelector('.slide-footer').getBoundingClientRect();const ov=(a,b)=>!(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top);return {count:items.length,inside:items.every(r=>r.left>=tr.left-1&&r.top>=tr.top-1&&r.right<=tr.right+1&&r.bottom<=tr.bottom+1),overlap:items.some(r=>ov(r,hr)||ov(r,fr))};}""")
        report['checks'][f'{label}_ppt_region']=export_state['count']==5 and export_state['inside'] and not export_state['overlap']

        page.screenshot(path=str(QA/f'release_248_{label}.png'),full_page=False)
        report['viewports'][label]={'base':base,'themes':theme_counts,'controls':len(controls),'virtual':{'retained':retained,'visible':visible,'meta':meta},'focusables':focusable}
        report['console_errors']+=errs
        page.close()
    browser.close()
report['pass']=not report['console_errors'] and all(report['checks'].values())
(QA/'release_248_browser.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['pass'] else 1)
