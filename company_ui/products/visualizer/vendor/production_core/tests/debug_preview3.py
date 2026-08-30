import re
from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]
def strip(s): return re.sub(r'^import .*?;\s*$','',s,flags=re.M).replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
rt=strip((P/'core/runtime_registry.mjs').read_text())+'\nglobalThis.__REG={ELEMENTS_BY_ENGINE,ALL_ELEMENTS};'
ur=strip((P/'core/universal_renderer.mjs').read_text())+'\nglobalThis.__RENDER={renderElement,findEngineForElement,renderEngineGallery,renderAllElements};'
gl=strip((P/'core/grid_layout_engine.mjs').read_text())+'\nglobalThis.__GRID={compileGridLayout,findLargestEmptyRegion,mapPlacementToRegion};'
dg=strip((P/'core/data_grid_engine.mjs').read_text())+'\nglobalThis.__DATA={prepareDataGrid,gridVirtualWindow,rowAt};'
pv=re.sub(r'^import .*?;\s*$','',(P/'app/approval/preview.mjs').read_text(),flags=re.M)
pv="const {ELEMENTS_BY_ENGINE}=globalThis.__REG; const {renderElement}=globalThis.__RENDER; const {compileGridLayout,findLargestEmptyRegion}=globalThis.__GRID; const {prepareDataGrid,gridVirtualWindow}=globalThis.__DATA;\n"+pv
js=';\n'.join([f'(()=>{{{rt}}})()',f'(()=>{{const {{ELEMENTS_BY_ENGINE}}=globalThis.__REG;{ur}}})()',f'(()=>{{{gl}}})()',f'(()=>{{{dg}}})()',pv])
html=(P/'app/approval/index.html').read_text();css=(P/'app/tokens.css').read_text()+(P/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'');html=html.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script>{js}</script>')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium');pg=b.new_page(viewport={'width':1440,'height':1000});pg.on('pageerror',lambda e:print('ERR',e));pg.on('console',lambda m:print(m.type,m.text));pg.set_content(html,wait_until='load');pg.wait_for_timeout(300);print('cards',pg.locator('.gallery-card').count()); print('small', pg.evaluate("[...document.querySelectorAll('button,input,select')].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return [e.getAttribute('aria-label')||e.textContent.trim()||e.placeholder,r.width,r.height,e.className]}).filter(x=>x[2]<35.5)"));pg.get_by_role('button',name='Dynamic Grid').click();print('layout',pg.locator('#slideStage .sim-item').count());pg.get_by_role('button',name='100k Grid').click();pg.wait_for_timeout(1500);print('data',pg.locator('.vg-row').count(),pg.locator('.vg-row:visible').count(),pg.locator('#gridMeta').inner_text());b.close()
