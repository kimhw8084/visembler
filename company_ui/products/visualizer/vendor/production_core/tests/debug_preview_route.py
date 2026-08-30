from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1];APP=P/'app';CORE=P/'core'
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium');pg=b.new_page(viewport={'width':1440,'height':1000})
 def route(r):
  url=r.request.url; path=url.split('preview.local/',1)[1].split('?',1)[0]
  # relative app/core mapping based on URL normalized by browser
  local=P/path
  if not local.exists(): local=APP/path
  if not local.exists():
   print('404',path);r.fulfill(status=404,body='not found');return
  ext=local.suffix;ct={'html':'text/html','css':'text/css','mjs':'text/javascript','js':'text/javascript'}.get(ext.lstrip('.'),'application/octet-stream')
  r.fulfill(status=200,body=local.read_bytes(),content_type=ct)
 pg.route('http://preview.local/**',route)
 pg.on('console',lambda m:print(m.type,m.text));pg.on('pageerror',lambda e:print('pageerror',e))
 pg.goto('http://preview.local/app/approval/index.html',wait_until='load');pg.wait_for_timeout(500)
 print('cards',pg.locator('.gallery-card').count())
 pg.get_by_role('button',name='100k Grid').click();pg.wait_for_timeout(1000);print('rows',pg.locator('.vg-row').count(),pg.locator('#gridMeta').inner_text())
 b.close()
