"""Native Company controls, sharing state and action-closure regression."""
from pathlib import Path
import argparse, hashlib, json, sys, tempfile, time, traceback

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
OUT=parser.parse_args().output.resolve()
if OUT.exists() and any(OUT.iterdir()): parser.error('--output must be new or empty')
OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT),str(ROOT/'scripts/release_checks')]
from editor_host import NativeHost
from native_common import BrowserEvents, acceptance_model, browser_kwargs, ready
from source_identity import candidate_sha
from company_ui.products.visualizer.governance import ReportAccessCatalog
from playwright.sync_api import sync_playwright

receipt={'schema':'visembler-company-controls.v1','candidate_sha':candidate_sha(ROOT),'status':'FAIL','cases':[],'source_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['company_ui/products/visualizer/page.py','company_ui/products/visualizer/presentation.py','company_ui/products/visualizer/assets/integrated_editor.css']}}
events=BrowserEvents()

def snapshot(page,locator):
    return locator.evaluate('''root=>({viewport:{width:innerWidth,height:innerHeight},scroll:{x:scrollX,y:scrollY},overflow:document.documentElement.scrollWidth>innerWidth+1,
      expectedActions:root.classList.contains('cui-visualizer-reportbar')?['New report','Duplicate','Manage']:['Grid','List','Create report'],
      actions:[...root.querySelectorAll('button')].filter(e=>e.offsetWidth&&e.offsetHeight&&!e.disabled).map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {name:e.innerText||e.getAttribute('aria-label'),left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height,radius:s.borderRadius}})})''')

def oracle(state):
    w,h=state['viewport']['width'],state['viewport']['height']
    assert state['actions'],'missing enabled actions'
    assert all(any(a['name']==name for a in state['actions']) for name in state['expectedActions']), 'missing required action'
    for a in state['actions']:
        assert a['width']>0 and a['height']>0 and a['left']>=-1 and a['right']<=w+1 and a['top']>=-1 and a['bottom']<=h+1, f"clipped action: {a['name']}"
    assert not state['overflow'],'document overflow'

def wait_grants(access,rid,predicate):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        grants=access.get(rid).get('grants',{})
        if predicate(grants): return grants
        time.sleep(.1)
    raise AssertionError(f'grant effect did not settle: {grants}')

try:
    with tempfile.TemporaryDirectory(prefix='visembler-chg304-controls-') as tmp, NativeHost(ROOT,Path(tmp)/'data') as host, sync_playwright() as pw:
        rid=host.create(acceptance_model(),'chg304-controls')
        access=ReportAccessCatalog(host.repository)
        browser=pw.chromium.launch(**browser_kwargs())
        for width,height in [(1440,900),(390,844),(320,844)]:
            context=browser.new_context(viewport={'width':width,'height':height})
            page=context.new_page(); events.attach(page)
            page.goto(f'{host.url}/visualizer?report={rid}',wait_until='domcontentloaded'); ready(page,require_settled=True)
            bar=page.locator('.cui-visualizer-reportbar')
            fields=page.get_by_role('textbox',name='Report title',exact=True)
            assert fields.count()==1
            relations=fields.evaluate('''e=>{const g=e.closest('.cui-field');const label=document.getElementById(g.getAttribute('aria-labelledby'));return {groupRole:g.getAttribute('role'),label:label.textContent,inputLabel:e.getAttribute('aria-label')}}''')
            assert relations=={'groupRole':'group','label':'Report title','inputLabel':'Report title'}
            state=snapshot(page,bar); oracle(state)
            page.screenshot(path=str(OUT/f'editor-{width}.png'))
            receipt['cases'].append({'name':f'editor actions and accessible field {width}','status':'PASS','state':state,'field_relationship':relations})
            if width==320:
                button=bar.get_by_role('button',name='Manage',exact=True)
                button.evaluate("e=>{e.style.setProperty('position','fixed','important');e.style.setProperty('left','10000px','important')}")
                bad=snapshot(page,bar)
                try: oracle(bad)
                except AssertionError as e:
                    assert 'clipped action' in str(e) or 'document overflow' in str(e)
                    receipt['negative_control']={'detected':True,'reason':str(e),'state':bad}
                else: raise AssertionError('clipped-action control falsely passed')
                button.evaluate("e=>{e.style.removeProperty('position');e.style.removeProperty('left')}")
                oracle(snapshot(page,bar))
            bar.get_by_role('button',name='New report',exact=True).click()
            dialog=page.locator('[data-cui-overlay="dialog"]:visible').filter(has_text='New report')
            dialog.wait_for(); dialog.get_by_role('button',name='Blank canvas',exact=True).wait_for()
            overlay=dialog.bounding_box(); assert overlay['x']>=0 and overlay['x']+overlay['width']<=width+1
            # Footer and close controls are functional even when template body scrolls.
            dialog.get_by_role('button',name='Close',exact=True).click()
            dialog.wait_for(state='hidden'); bar.get_by_role('button',name='New report',exact=True).click()
            dialog.wait_for(state='visible')
            page.keyboard.press('Escape'); dialog.wait_for(state='hidden')
            page.locator('.q-dialog:visible').wait_for(state='hidden')
            bar.get_by_role('button',name='Manage',exact=True).click()
            page.locator('[data-testid="report-hub"]').wait_for()
            page.wait_for_function('()=>window.socket?.connected===true&&window.did_handshake===true')
            toolbar=page.locator('.cui-report-hub-toolbar')
            state=snapshot(page,toolbar); oracle(state)
            page.screenshot(path=str(OUT/f'hub-{width}.png'))
            receipt['cases'].append({'name':f'hub actions and overlay close/Escape {width}','status':'PASS','state':state})
            context.close()
        context=browser.new_context(viewport={'width':1440,'height':900}); page=context.new_page(); events.attach(page)
        page.goto(f'{host.url}/visualizer/reports?report={rid}',wait_until='domcontentloaded')
        card=page.locator(f'[data-report-id="{rid}"][data-testid="report-card"]')
        card.wait_for(); page.wait_for_function('()=>window.socket?.connected===true&&window.did_handshake===true')
        def sharing():
            card.locator('[data-report-action="more"]').click()
            page.locator('.q-menu:visible').get_by_role('button',name='Manage access',exact=True).click()
            dialog=page.locator('[data-cui-overlay="dialog"]:visible').filter(has_text='Manage report access')
            dialog.wait_for(); return dialog
        d=sharing(); d.get_by_role('textbox',name='Person or group',exact=True).fill('chg304-engineering')
        d.get_by_text('This identifier represents a group',exact=True).click()
        assert d.get_by_role('checkbox',name='This identifier represents a group',exact=True).is_checked()
        d.get_by_role('button',name='Grant access',exact=True).click(); d.wait_for(state='hidden')
        grants=wait_grants(access,rid,lambda g:g.get('group:chg304-engineering')=='viewer')
        assert 'chg304-engineering' not in grants
        d=sharing(); d.get_by_role('textbox',name='Person or group',exact=True).fill('chg304-engineering')
        assert d.get_by_role('checkbox',name='This identifier represents a group',exact=True).is_checked(), 'reopened choice must match retained group action'
        d.get_by_text('This identifier represents a group',exact=True).click()
        assert not d.get_by_role('checkbox',name='This identifier represents a group',exact=True).is_checked()
        d.get_by_role('button',name='Grant access',exact=True).click(); d.wait_for(state='hidden')
        wait_grants(access,rid,lambda g:g.get('chg304-engineering')=='viewer' and g.get('group:chg304-engineering')=='viewer')
        d=sharing(); d.get_by_role('textbox',name='Person or group',exact=True).fill('chg304-engineering')
        d.get_by_role('checkbox',name='This identifier represents a group',exact=True).focus()
        page.keyboard.press('Space')
        assert d.get_by_role('checkbox',name='This identifier represents a group',exact=True).is_checked()
        d.get_by_role('button',name='Remove access',exact=True).click(); d.wait_for(state='hidden')
        grants=wait_grants(access,rid,lambda g:'group:chg304-engineering' not in g and g.get('chg304-engineering')=='viewer')
        receipt['cases'].append({'name':'native checked/unchecked sharing and scoped revoke effects','status':'PASS','final_grants':grants})
        record=host.repository.get(rid); literal='<b>literal title</b> & *plain*'
        host.repository.rename(rid,title=literal,expected_revision=record.revision)
        page.reload(wait_until='domcontentloaded'); card.wait_for()
        title=card.locator('.cui-report-card-title'); assert title.inner_text()==literal and title.locator('b').count()==0
        page.screenshot(path=str(OUT/'literal-report-copy.png'))
        receipt['cases'].append({'name':'native literal report copy remains text','status':'PASS'})
        assert not events.unexpected,events.unexpected
        browser.close(); receipt['status']='PASS'
except Exception as exc:
    receipt['error']=str(exc); receipt['traceback']=traceback.format_exc()
finally:
    receipt['unexpected_browser_events']=events.unexpected
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'cases':len(receipt['cases']),'error':receipt.get('error')},indent=2))
    if receipt['status']!='PASS': sys.exit(1)
