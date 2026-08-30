import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]
def strip(s):return re.sub(r'^import .*?;\s*$','',s,flags=re.M).replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
def bundle():
 rt=strip((P/'core/runtime_registry.mjs').read_text())+'\nglobalThis.__REG={ELEMENTS_BY_ENGINE,ALL_ELEMENTS};';ur=strip((P/'core/universal_renderer.mjs').read_text())+'\nglobalThis.__RENDER={renderElement,findEngineForElement,renderEngineGallery,renderAllElements};';gl=strip((P/'core/grid_layout_engine.mjs').read_text())+'\nglobalThis.__GRID={compileGridLayout,findLargestEmptyRegion,mapPlacementToRegion};';dg=strip((P/'core/data_grid_engine.mjs').read_text())+'\nglobalThis.__DATA={prepareDataGrid,gridVirtualWindow,rowAt};';pv=re.sub(r'^import .*?;\s*$','',(P/'app/approval/preview.mjs').read_text(),flags=re.M);pv="const {ELEMENTS_BY_ENGINE}=globalThis.__REG;const {renderElement}=globalThis.__RENDER;const {compileGridLayout,findLargestEmptyRegion}=globalThis.__GRID;const {prepareDataGrid,gridVirtualWindow}=globalThis.__DATA;\n"+pv;js=';\n'.join([f'(()=>{{{rt}}})()',f'(()=>{{const {{ELEMENTS_BY_ENGINE}}=globalThis.__REG;{ur}}})()',f'(()=>{{{gl}}})()',f'(()=>{{{dg}}})()',pv]);h=(P/'app/approval/index.html').read_text();css=(P/'app/tokens.css').read_text()+(P/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'');return h.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script>{js}</script>')
r={'pass':False,'checks':{},'errors':[]}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium');pg=b.new_page(viewport={'width':390,'height':844});pg.on('console',lambda m:r['errors'].append(m.text) if m.type=='error' else None);pg.on('pageerror',lambda e:r['errors'].append(str(e)));pg.set_content(bundle(),wait_until='load');pg.wait_for_timeout(250)
 r['checks']['cards']=pg.locator('.gallery-card').count()==248;r['checks']['engines']=pg.locator('.engine-section').count()==17;r['checks']['no_overflow']=pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
 # Only immediate phone controls + first interaction control need layout measurement.
 dims=pg.evaluate("""()=>[...document.querySelectorAll('.approval-top button,.control input,.control select,.gallery-card button')].slice(0,12).map(e=>{const x=e.getBoundingClientRect();return{x:x.width,y:x.height,name:e.getAttribute('aria-label')||e.textContent.trim()||e.placeholder}})""");r['checks']['touch_targets']=all(x['y']>=43.5 for x in dims);r['checks']['named']=all(x['name'] for x in dims)
 pg.get_by_role('button',name='Dynamic Grid').click();pg.wait_for_timeout(60);r['checks']['layout']=pg.locator('#slideStage .sim-item').count()==5
 pg.get_by_role('button',name='100k Grid').click();pg.wait_for_timeout(900);r['checks']['grid']='100,000' in pg.locator('#gridMeta').inner_text() and pg.locator('.vg-row:visible').count()<70
 pg.get_by_role('button',name='PPT Region').click();pg.wait_for_timeout(60);r['checks']['ppt']=pg.locator('#exportStage .sim-item').count()==5
 pg.screenshot(path=str(P/'qa/approval_preview_phone.png'),full_page=False);b.close()
r['pass']=not r['errors'] and all(r['checks'].values());(P/'qa/approval_preview_phone.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));sys.exit(0 if r['pass'] else 1)
