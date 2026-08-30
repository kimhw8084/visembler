import re,time
from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]
def strip(src):
 src=re.sub(r'^import .*?;\s*$','',src,flags=re.M);return src.replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
h=(P/'app/approval/index.html').read_text();css=(P/'app/tokens.css').read_text()+(P/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'');js='\n'.join(strip((P/x).read_text()) for x in ['core/runtime_registry.mjs','core/universal_renderer.mjs','core/grid_layout_engine.mjs','core/data_grid_engine.mjs','app/approval/preview.mjs']);h=h.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script type="module">{js}</script>')
print('bundle',len(h),flush=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium');pg=b.new_page(viewport={'width':1440,'height':1000});pg.on('console',lambda m:print('console',m.type,m.text,flush=True));pg.on('pageerror',lambda e:print('pageerror',e,flush=True))
 t=time.time();pg.set_content(h,wait_until='load',timeout=30000);print('set',time.time()-t,flush=True);pg.wait_for_timeout(500);print('cards',pg.locator('.gallery-card').count(),flush=True)
 t=time.time();print('eval geom',pg.evaluate('document.documentElement.scrollWidth'),time.time()-t,flush=True)
 print('click layout',flush=True);pg.get_by_role('button',name='Dynamic Grid').click(timeout=5000);print('layout items',pg.locator('#slideStage .sim-item').count(),flush=True)
 print('click data',flush=True);t=time.time();pg.get_by_role('button',name='100k Grid').click(timeout=5000);print('clicked data',time.time()-t,flush=True);pg.wait_for_timeout(200);print('rows',pg.locator('.vg-row').count(),pg.locator('#gridMeta').inner_text(),flush=True)
 b.close()
