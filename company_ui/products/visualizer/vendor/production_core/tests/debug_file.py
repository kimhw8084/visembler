from pathlib import Path
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--allow-file-access-from-files','--disable-web-security'])
 pg=b.new_page(viewport={'width':1440,'height':1000});pg.on('console',lambda m:print(m.type,m.text));pg.on('pageerror',lambda e:print('err',e))
 pg.goto((P/'app/approval/index.html').as_uri(),wait_until='load');pg.wait_for_timeout(700);print('cards',pg.locator('.gallery-card').count());pg.get_by_role('button',name='100k Grid').click();pg.wait_for_timeout(1000);print('rows',pg.locator('.vg-row').count(),pg.locator('#gridMeta').inner_text());b.close()
