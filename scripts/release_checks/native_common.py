"""Shared helpers for Visembler native closeout checks.

Only synthetic temporary repositories are used.  These helpers never touch the
operator's normal Visembler data directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path


def browser_kwargs() -> dict:
    kwargs={'headless':True}
    executable=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium') or shutil.which('chromium-browser')
    if executable:
        kwargs.update(executable_path=executable,args=['--no-sandbox'])
    return kwargs


def text_model(text='Seed') -> dict:
    return {
        'schema_version':1,
        'items':[{
            'id':'c1','type':'text','engine':'TextEngine','element':'Body Narrative',
            'title':'Body Narrative','showTitle':True,'text':text,'body':text,
            'weight':1.1,'order':0,'locked':False,'z':1,
        }],
        'groups':{},'datasets':[],'mode':'smart','layoutPreset':'editorial',
        'crossFilter':None,'canvas':{'width':1600,'height':900},'nextId':2,
    }


def acceptance_model() -> dict:
    return {
        'schema_version':1,
        'items':[
            {'id':'c1','type':'text','engine':'TextEngine','element':'Key Takeaway','title':'Key Takeaway','text':'Native acceptance','body':'Native acceptance','weight':1.0,'order':0,'locked':False,'z':1},
            {'id':'c2','type':'metric','engine':'MetricEngine','element':'Hero KPI','title':'Hero KPI','value':84.2,'unit':'%','weight':1.1,'order':1,'locked':False,'z':2},
            {'id':'c3','type':'chart','engine':'CoreChartEngine','element':'Line Chart','title':'Line Chart','data':[['A',1],['B',3],['C',2]],'rows':[{'label':'A','value':1},{'label':'B','value':3},{'label':'C','value':2}],'brush':[0,2],'cross':None,'drill':None,'revealed':True,'weight':1.6,'order':2,'locked':False,'z':3},
        ],
        'groups':{},'datasets':[],'mode':'smart','layoutPreset':'editorial',
        'crossFilter':None,'canvas':{'width':1600,'height':900},'nextId':4,
    }


def state(page):
    return page.evaluate('window.CompanyUIVisualizerBridge.state()')


def ready(page, *, timeout=20000, require_settled=False):
    page.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=timeout)
    if require_settled:
        page.wait_for_function('()=>{const s=window.CompanyUIVisualizerBridge?.state?.();return s&&s.pending===0&&!s.inflight}',timeout=timeout)


def select(page,item_id='c1'):
    node=page.locator(f'.component[data-id="{item_id}"]')
    node.evaluate('(el)=>el.click()')
    page.wait_for_function('(id)=>document.querySelector(`.component[data-id="${id}"]`)?.getAttribute("aria-selected")==="true"', arg=item_id)


def edit_text(page,value, *, settle=True):
    select(page,'c1')
    field=page.locator('#iText');field.scroll_into_view_if_needed();field.fill(value);field.press('Tab')
    if settle:
        page.wait_for_function('()=>{const s=window.CompanyUIVisualizerBridge.state();return s.pending===0&&!s.inflight}',timeout=15000)


def item_text(model,item_id='c1'):
    item=next(x for x in model['items'] if x['id']==item_id)
    return item.get('text') or item.get('body') or ''


def wait_repository_text(repository,report_id,value, *, timeout=15):
    deadline=time.monotonic()+timeout
    last=None
    while time.monotonic()<deadline:
        try:
            last=item_text(repository.get(report_id).model)
            if last==value:return repository.get(report_id)
        except Exception as exc:last=str(exc)
        time.sleep(.15)
    raise AssertionError(f'repository text did not become {value!r}; last={last!r}')


class BrowserEvents:
    def __init__(self):
        self.unexpected=[];self.expected_fault=[];self.fault=False

    def attach(self,page):
        page.on('pageerror',lambda err:self._add('pageerror',str(err)))
        page.on('console',lambda msg:self._add('console',msg.text) if msg.type=='error' else None)
        page.on('requestfailed',lambda req:self._add('requestfailed',f'{req.url} :: {req.failure}'))

    def _add(self,kind,detail):
        row={'kind':kind,'detail':detail}
        (self.expected_fault if self.fault else self.unexpected).append(row)


def file_hashes(root: Path, paths: list[Path]) -> dict[str,str]:
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
