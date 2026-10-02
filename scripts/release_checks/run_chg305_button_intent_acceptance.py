"""Measure Company button intent colors in the real lab and application."""
from pathlib import Path
import argparse,json,os,re,subprocess,sys,tempfile,traceback

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts/release_checks')]
from company_ui.certification.runtime_smoke import _free_port,_wait_ready,_stop_process
from editor_host import NativeHost
from native_common import BrowserEvents,acceptance_model,browser_kwargs,ready,file_hashes
from source_identity import candidate_sha
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True,type=Path)
OUT=parser.parse_args().output.resolve()
if OUT.exists() and any(OUT.iterdir()):parser.error('--output must be new or empty')
OUT.mkdir(parents=True,exist_ok=True)
receipt={'candidate_sha':candidate_sha(ROOT),'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'source_files':file_hashes(ROOT,[*(ROOT/'company_ui/integrations'/f'nicegui_{name}.py' for name in ['components','interactions','layout','visualization','data_table']),ROOT/'company_ui/design/hardening_css.py',Path(__file__)]),'status':'FAIL','cases':[],'claim':'bounded native intent probes; not screenshot-baseline or production certification'}
events=BrowserEvents()
probe='''e=>{const s=getComputedStyle(e),content=e.querySelector('.q-btn__content'),r=e.getBoundingClientRect();
const resolve=value=>{const n=document.createElement('span');n.style.color=value;e.append(n);const c=getComputedStyle(n).color;n.remove();return c;};
const rgba=c=>{const n=document.createElement('canvas');n.width=n.height=1;const ctx=n.getContext('2d');ctx.fillStyle=c;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];};
const tokens={accent:resolve('var(--cui-accent)'),accentHover:resolve('var(--cui-accent-hover)'),surface:resolve('var(--cui-surface)'),danger:resolve('var(--cui-danger)'),dangerHover:resolve('color-mix(in srgb,var(--cui-danger) 88%,black)'),text:resolve('var(--cui-text-primary)'),muted:resolve('var(--cui-text-secondary)'),inverse:resolve('var(--cui-text-inverse)'),tertiary:resolve('color-mix(in srgb,var(--cui-accent) 11%,var(--cui-surface))')};
const background=s.backgroundColor,color=content?getComputedStyle(content).color:s.color;
const stops=s.backgroundImage.match(/rgba?\\([^)]*\\)|color\\([^)]*\\)/g)||[];
return {name:e.innerText,classes:e.className,background,color,image:s.backgroundImage,filter:s.filter,tokens,rgba:{background:rgba(background),color:rgba(color),stops:stops.map(rgba),tokens:Object.fromEntries(Object.entries(tokens).map(([k,v])=>[k,rgba(v)]))},rect:{left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height},viewport:{width:innerWidth,height:innerHeight}};}'''

def contrast(a,b):
    def lum(rgb):
        c=[v/255 for v in rgb[:3]]
        c=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c]
        return sum(v*w for v,w in zip(c,[.2126,.7152,.0722]))
    x,y=sorted([lum(a),lum(b)])
    return (y+.05)/(x+.05)

def oracle(f,intent,*,hover=False):
    receipt['current_observation']={'intent':intent,'hover':hover,'facts':f}
    expected={'primary':'accent','secondary':'surface','tertiary':'tertiary','danger':'danger'}
    if intent=='ghost':assert f['rgba']['background'][3]==0,'ghost must have a transparent background'
    elif intent in {'primary','danger'} and f['rgba']['stops']:
        assert f['rgba']['stops'][-1]==f['rgba']['tokens'][expected[intent]],f'{intent} gradient differs from Company token'
    else:
        token={'primary':'accentHover','danger':'dangerHover'}[intent] if hover else expected[intent]
        assert f['background']==f['tokens'][token],f'{intent} background differs from Company token'
    color={'primary':'inverse','danger':'inverse','secondary':'text','tertiary':'accent','ghost':'muted'}[intent]
    assert f['color']==f['tokens'][color],f'{intent} text differs from Company token'
    if intent in {'primary','danger'}:
        backgrounds=f['rgba']['stops'] or [f['rgba']['background']]
        brightness=re.search(r'brightness\(([\d.]+)\)',f['filter'])
        factor=float(brightness.group(1)) if brightness else 1
        def painted(c):return [min(255,round(v*factor)) for v in c[:3]]
        contrasts=[contrast(painted(f['rgba']['color']),painted(c)) for c in backgrounds]
        f['contrast_ratios']=contrasts
        assert min(contrasts)>=4.5,f'{intent} text contrast below 4.5: {min(contrasts):.3f}'

def fact(page,locator,intent):
    locator.scroll_into_view_if_needed();page.mouse.move(1,1);page.wait_for_timeout(150)
    f=locator.evaluate(probe);oracle(f,intent);return f

process=None
try:
    with tempfile.TemporaryDirectory(prefix='company-intent-lab-') as neutral, (OUT/'lab-server.log').open('w') as log, sync_playwright() as pw:
        port=_free_port();url=f'http://127.0.0.1:{port}'
        env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONUNBUFFERED':'1'}
        process=subprocess.Popen([sys.executable,'-m','company_ui.certification.live_lab_cli','--host','127.0.0.1','--port',str(port)],cwd=neutral,env=env,stdout=log,stderr=subprocess.STDOUT,text=True)
        ok,detail=_wait_ready(url,process);assert ok,detail
        browser=pw.chromium.launch(**browser_kwargs())
        context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();events.attach(page)
        page.goto(url+'/controls',wait_until='domcontentloaded');page.locator('.cui-lab-route-controls').wait_for()
        page.wait_for_function('()=>window.socket?.connected===true&&window.did_handshake===true')
        for theme in ['light','dark']:
            page.locator('.cui-lab-controlbar').get_by_role('button',name=theme.title(),exact=True).click()
            page.wait_for_function('(theme)=>document.documentElement.dataset.theme===theme',arg=theme)
            facts=[];failures=[]
            for intent in ['primary','secondary','tertiary','ghost','danger']:
                locator=page.get_by_role('button',name=intent.title(),exact=True)
                try:f=fact(page,locator,intent)
                except AssertionError as exc:
                    f=locator.evaluate(probe);failures.append(str(exc))
                facts.append(f)
            page.screenshot(path=str(OUT/f'lab-{theme}.png'))
            receipt['cases'].append({'name':f'five live intents {theme}','status':'FAIL' if failures else 'PASS','facts':facts,'failures':failures})
            assert not failures,failures
            interaction=[]
            for intent in ['primary','danger']:
                locator=page.get_by_role('button',name=intent.title(),exact=True)
                locator.hover();page.wait_for_timeout(180);f=locator.evaluate(probe);oracle(f,intent,hover=True);interaction.append({'state':'hover','facts':f})
                page.mouse.move(1,1);locator.focus();f=locator.evaluate(probe);oracle(f,intent);interaction.append({'state':'focus','facts':f})
            receipt['cases'].append({'name':f'hover/focus contrast {theme}','status':'PASS','facts':interaction})
        assert page.get_by_role('button',name='Disabled',exact=True).is_disabled()
        assert page.get_by_role('button',name='Processing',exact=True).is_disabled()
        assert page.get_by_role('button',name='Processing',exact=True).locator('.cui-button__spinner').count()==1
        receipt['cases'].append({'name':'disabled and loading retain native behavior','status':'PASS'})
        ghost=page.get_by_role('button',name='Ghost',exact=True)
        ghost.evaluate("e=>{e.style.setProperty('background','var(--cui-accent)','important');e.style.setProperty('color','white','important')}")
        ghost.evaluate('async e=>{getComputedStyle(e).backgroundColor;await Promise.all(e.getAnimations().map(a=>a.finished))}')
        broken=ghost.evaluate(probe)
        try:oracle(broken,'ghost')
        except AssertionError as exc:
            assert 'ghost' in str(exc)
            receipt['negative_control']={'detected':True,'reason':str(exc),'facts':broken}
        else:raise AssertionError('stock-primary repaint fault falsely passed')
        ghost.evaluate("e=>{e.style.removeProperty('background');e.style.removeProperty('color')}")
        ghost.evaluate('async e=>{getComputedStyle(e).backgroundColor;await Promise.all(e.getAnimations().map(a=>a.finished))}')
        oracle(ghost.evaluate(probe),'ghost')
        page.goto(url+'/forms',wait_until='domcontentloaded');page.locator('.cui-lab-route-forms').wait_for()
        page.get_by_role('button',name='Danger dialog',exact=True).click()
        dialog=page.locator('[data-cui-overlay="dialog"]:visible').filter(has_text='Delete saved view?');dialog.wait_for()
        danger=dialog.get_by_role('button',name='Delete',exact=True)
        assert danger.is_disabled()
        facts=[fact(page,danger,'danger'),fact(page,dialog.get_by_role('button',name='Cancel',exact=True),'secondary')]
        dialog.get_by_role('textbox',name='Type DELETE to confirm',exact=True).fill('wrong');assert danger.is_disabled()
        dialog.get_by_role('textbox',name='Type DELETE to confirm',exact=True).fill('DELETE');danger.wait_for();assert danger.is_enabled()
        page.screenshot(path=str(OUT/'danger-dialog.png'))
        dialog.get_by_role('button',name='Cancel',exact=True).click();dialog.wait_for(state='hidden')
        page.get_by_role('button',name='Danger dialog',exact=True).click();dialog.wait_for();page.keyboard.press('Escape');dialog.wait_for(state='hidden')
        receipt['cases'].append({'name':'danger intent, typed enable, cancel and Escape','status':'PASS','facts':facts})
        context.close();browser.close();_stop_process(process);process=None
    with tempfile.TemporaryDirectory(prefix='visembler-intent-app-') as tmp,NativeHost(ROOT,Path(tmp)/'data') as host,sync_playwright() as pw:
        rid=host.create(acceptance_model(),'button-intent-acceptance');browser=pw.chromium.launch(**browser_kwargs())
        for width in [1440,390,320]:
            context=browser.new_context(viewport={'width':width,'height':900 if width==1440 else 844});page=context.new_page();events.attach(page)
            page.goto(f'{host.url}/visualizer?report={rid}',wait_until='domcontentloaded');ready(page,require_settled=True)
            bar=page.locator('.cui-visualizer-reportbar');facts=[]
            for name,intent in [('New report','primary'),('Duplicate','secondary'),('Manage','ghost')]:
                f=fact(page,bar.get_by_role('button',name=name,exact=True),intent);r=f['rect']
                assert 0<=r['left']<r['right']<=width+1 and r['bottom']<=f['viewport']['height']+1
                facts.append(f)
            page.screenshot(path=str(OUT/f'editor-{width}.png'))
            bar.get_by_role('button',name='Manage',exact=True).click();hub=page.locator('[data-testid="report-hub"]');hub.wait_for()
            page.wait_for_function('()=>window.socket?.connected===true&&window.did_handshake===true')
            hub_facts=[fact(page,hub.get_by_role('button',name=name,exact=True),intent) for name,intent in [('Grid','ghost'),('List','ghost'),('Create report','primary')]]
            page.screenshot(path=str(OUT/f'hub-{width}.png'))
            receipt['cases'].append({'name':f'native editor/Hub intent {width}','status':'PASS','editor':facts,'hub':hub_facts})
            context.close()
        browser.close()
    assert not events.unexpected,events.unexpected
    receipt['status']='PASS'
except Exception as exc:
    receipt['error']=str(exc);receipt['traceback']=traceback.format_exc()
finally:
    if process is not None:_stop_process(process)
    receipt['unexpected_browser_events']=events.unexpected
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'cases':len(receipt['cases']),'error':receipt.get('error')}))
    if receipt['status']!='PASS':sys.exit(1)
