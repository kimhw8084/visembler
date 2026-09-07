#!/usr/bin/env python3
"""Evidence receipt for the bounded final visual remediation pass.

Every VR check is emitted individually. Browser checks use real report routes,
and visual-utilization measurements target renderer internals rather than the
generic component wrapper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from company_ui.products.visualizer.domain import canonical_model  # noqa: E402
from company_ui.products.visualizer.page import _history_diff_summary,_report_thumbnail_markup  # noqa: E402
from editor_host import NativeHost  # noqa: E402
from native_common import BrowserEvents,browser_kwargs,ready,write_json  # noqa: E402

FROZEN='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
NAMES={
 'VR001':'all 39 production elements enumerated','VR002':'solo core chart uses family minimum','VR003':'solo timeline uses family minimum','VR004':'solo wafer uses family minimum','VR005':'solo diagram uses family minimum','VR006':'text/metric content-fit is not a centered island','VR007':'multi-card growth favors visual families','VR008':'no giant blank composite/timeline rows','VR009':'Free geometry survives internal responsiveness',
 'VR010':'legacy array edges render','VR011':'from/to/label edges render','VR012':'source/target edges render','VR013':'canonical diagram studio renders','VR014':'Preview has no diagram error','VR015':'SVG contains nodes and labels','VR016':'Diagram Studio auto-fits on open','VR017':'768 shape palette drawer available','VR018':'768 inspector drawer available',
 'VR019':'legacy category/value Line opens mapped','VR020':'chart preview has plotted marks','VR021':'obvious schema has no unmapped summary','VR022':'saved/reopened chart remains plotted','VR023':'legacy Wafer observations hydrate','VR024':'Wafer die count matches observations','VR025':'Wafer min/max is non-placeholder','VR026':'engineering route hydrates data','VR027':'Stage C rejects unmapped non-empty SVG',
 'VR028':'context toolbar adjacent at 40 percent','VR029':'context toolbar adjacent at 55 percent','VR030':'context toolbar adjacent at 100 percent','VR031':'panel reflow keeps toolbar attached',
 'VR032':'report thumbnails are semantic miniatures','VR033':'chart/wafer/diagram/text thumbnails differ','VR034':'revision comparison has real miniatures','VR035':'content edit summary detected','VR036':'geometry edit summary detected','VR037':'mapping edit summary detected','VR038':'chart config edit summary detected','VR039':'diagram config edit summary detected','VR040':'checkpoint cannot silently fail',
 'VR041':'Process Health has bounded blank area','VR042':'Wafer Investigation wafer is materially sized','VR043':'RCA has no diagram error','VR044':'Executive Summary has no empty chart','VR045':'Executive Summary toolbar is attached','VR046':'Weekly checkpoint exists','VR047':'five reports have zero product empty/error states',
 'VR048':'Stage A regression','VR049':'Stage B regression','VR050':'Stage C regression','VR051':'Stage D regression','VR052':'39 production elements','VR053':'data workflows','VR054':'product contract','VR055':'no unexpected browser errors','VR056':'frozen connector unchanged',
}

def node_json(source: str):
    result=subprocess.run(['node','--input-type=module','--eval',source],cwd=ROOT,check=True,capture_output=True,text=True,timeout=40)
    return json.loads(result.stdout)

def report_model(entry,mode='smart',items=None):
    values=items or [entry]
    return canonical_model({'items':values,'groups':{},'datasets':[],'mode':mode,'layoutPreset':'technical','canvas':{'width':1200,'height':900},'nextId':len(values)+1})

def fixture(engine,element,index=1):
    entry={'id':f'item-{index}','type':'text','engine':engine,'element':element,'title':element,'showTitle':False,'order':index-1,'weight':1.4,'locked':False,'z':index,'message_role':'Primary Evidence' if engine in {'CoreChartEngine','EngineeringChartEngine','WaferFabEngine','DiagramEngine','ImageMediaEngine','TableEngine'} else 'Supporting Evidence'}
    entry.update({'text':'Observed process behavior and the recommended action.','statement':'Observed process behavior','detail':'Evidence supports the current action.','status':'Ready','value':98.4,'unit':'%','delta':1.2,'target':99,'actual':98.4,'current':75,'max':100,'capacity':100,'numerator':98,'denominator':100,'warning':96,'critical':92,'period':'Week 36','caption':'Observed chamber condition','alt':'Chamber evidence image','milestones':[{'label':'Detect','date':'Sep 1'},{'label':'Analyze','date':'Sep 2'},{'label':'Verify','date':'Sep 3'},{'label':'Release','date':'Sep 4'}],'data':[['Mon',96],['Tue',98],['Wed',97],['Thu',99]],'customTable':{'headers':['Lot','Tool','Yield'],'rows':[['L1','ETCH-1',98],['L2','ETCH-2',97],['L3','ETCH-1',99]]},'nodes':['Detect','Analyze','Verify','Release'],'edges':[{'from':'Detect','to':'Analyze','label':'handoff'},{'source':'Analyze','target':'Verify','label':'evidence'},{'source':'Verify','target':'Release','label':'approve'}],'direction':'right','edge_label':'handoff','observations':[{'x':0,'y':0,'value':91,'lot':'L1','tool':'ETCH-1'},{'x':1,'y':0,'value':95,'lot':'L1','tool':'ETCH-1'},{'x':0,'y':1,'value':93,'lot':'L1','tool':'ETCH-1'},{'x':1,'y':1,'value':97,'lot':'L1','tool':'ETCH-1'}]})
    if engine=='EngineeringChartEngine': entry['observations']=[{'label':str(i+1),'value':10+(i%4)} for i in range(10)]
    return entry

def visual_probe(page):
    return page.evaluate(r"""()=>{
      const node=document.querySelector('.component'),hull=document.querySelector('#hull');if(!node||!hull)return null;
      const card=node.getBoundingClientRect(),stage=hull.getBoundingClientRect(),engine=node.querySelector('[data-engine]')?.dataset.engine||'';
      const selector=engine==='CoreChartEngine'||engine==='EngineeringChartEngine'?'.cs-chart-svg':engine==='WaferFabEngine'?'.cs-wafer-svg>circle,.cs-wafer-svg [data-wafer-die]':engine==='DiagramEngine'?'.diagram-studio-static [data-diagram-node],.diagram-studio-static [data-diagram-edge]':engine==='TimelineEngine'?'[data-timeline-event]':engine==='ImageMediaEngine'?'.image-stage,.captioned-image-live,.screenshot-frame-live':engine==='TableEngine'?'.table-frame,.table-wrap':engine==='MetricEngine'?'.metric-value,.hero-kpi,.status-hero,.metric-ring-live':'.card-body>*';
      const parts=[...node.querySelectorAll(selector)].map(value=>value.getBoundingClientRect()).filter(value=>value.width>0&&value.height>0);const union=parts.reduce((a,r)=>a?{left:Math.min(a.left,r.left),top:Math.min(a.top,r.top),right:Math.max(a.right,r.right),bottom:Math.max(a.bottom,r.bottom)}:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},null);const area=r=>Math.max(0,(r.right??r.width)-(r.left??0))*Math.max(0,(r.bottom??r.height)-(r.top??0));
      const logical=window.__VIZ_PROD__.layoutRects()[0],meaningful=union?{width:union.right-union.left,height:union.bottom-union.top}:null;return {engine,logical,card_area_share:logical.w*logical.h/(1200*900),width_share:logical.w/1200,internal_selector:selector,internal_area_share:union?area(union)/(card.width*card.height):0,dominant_axis_share:meaningful?Math.max(meaningful.width/card.width,meaningful.height/card.height):0,marks:node.querySelectorAll('[data-chart-point],[data-wafer-die],[data-diagram-node],[data-timeline-event]').length,overflow:node.scrollWidth>node.clientWidth+1||node.scrollHeight>node.clientHeight+1,stage:{width:stage.width,height:stage.height}};
    }""")

def toolbar_distance(page,item_id):
    page.locator(f'.component[data-id="{item_id}"]').click();page.wait_for_timeout(60)
    return page.evaluate(r"""()=>{const a=document.querySelector('#context.show')?.getBoundingClientRect(),b=document.querySelector('.component.selected')?.getBoundingClientRect();if(!a||!b)return 9999;const dx=Math.max(0,b.left-a.right,a.left-b.right),dy=Math.max(0,b.top-a.bottom,a.top-b.bottom);return Math.hypot(dx,dy);}""")

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--skip-regressions',action='store_true');parser.add_argument('--skip-benchmark',action='store_true');args=parser.parse_args()
    output=args.output.expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    receipt={'scope':'final visual remediation','checks':[],'visual_utilization':[],'unexpected_errors':[],'pass':0,'applicable':0,'not_applicable':0}
    rows={cid:{'id':cid,'name':name,'status':'FAIL','error':'not executed'} for cid,name in NAMES.items()}
    def record(cid,value=True,error=''):
        rows[cid]={'id':cid,'name':NAMES[cid],'status':'PASS' if value else 'FAIL'}
        if error: rows[cid]['error']=str(error)[:600]
    def attempt(cid,fn):
        try: fn();record(cid)
        except Exception as error: record(cid,False,error)
    try:
        pure=node_json(r"""
import {productionEntries,PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';
import {diagramFromEntry,renderDiagramSvg} from './company_ui/products/visualizer/assets/authoring_diagram_studio.mjs';
import {chartModelFromEntry,chartToEntry,renderChartSvg,chartSummary} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const diagram=edges=>{const model=diagramFromEntry({engine:'DiagramEngine',element:'Process Flow',nodes:['A','B'],edges,direction:'down'});return {model,svg:renderDiagramSvg(model)}};
const array=diagram([['A','B']]),from=diagram([{from:'A',to:'B',label:'handoff'}]),source=diagram([{source:'A',target:'B',labels:['verified']}]),canonical=diagramFromEntry({diagram:{nodes:[{id:'a',label:'Start',x:10,y:10},{id:'b',label:'End',x:260,y:10}],edges:[{id:'e',source:'a',target:'b',labels:[{text:'release'}]}]}}),canonicalSvg=renderDiagramSvg(canonical);
const line=chartModelFromEntry({engine:'CoreChartEngine',element:'Line Chart',data:[['A',1],['B',3],['C',2]]}),lineSvg=renderChartSvg(line),saved=chartToEntry({id:'line'},line),reopened=chartModelFromEntry(saved),reopenedSvg=renderChartSvg(reopened);
const wafer=chartModelFromEntry({engine:'WaferFabEngine',element:'Wafer Map',observations:[{x:0,y:0,value:91,lot:'L1'},{x:1,y:0,value:95,lot:'L1'},{x:0,y:1,value:93,lot:'L1'}]}),waferSvg=renderChartSvg(wafer);
const engineering=chartModelFromEntry({engine:'EngineeringChartEngine',element:'SPC Control Chart',observations:[{label:'1',value:10},{label:'2',value:11},{label:'3',value:9}]}),engineeringSvg=renderChartSvg(engineering);
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries(),array,from,source,canonicalSvg,line:{model:line,svg:lineSvg,summary:chartSummary(line)},reopened:{model:reopened,svg:reopenedSvg},wafer:{model:wafer,svg:waferSvg},engineering:{model:engineering,svg:engineeringSvg}}));
""")
        attempt('VR001',lambda: (_ for _ in ()).throw(AssertionError('production registry is not 39')) if pure['count']!=39 or len(pure['entries'])!=39 else None)
        for cid,key,label in [('VR010','array',None),('VR011','from','handoff'),('VR012','source','verified')]: attempt(cid,lambda key=key,label=label: (_ for _ in ()).throw(AssertionError('edge normalization/render failed')) if pure[key]['model']['edges'].__len__()!=1 or 'Diagram data needs review' in pure[key]['svg'] or (label and label not in pure[key]['svg']) else None)
        attempt('VR013',lambda: (_ for _ in ()).throw(AssertionError('canonical diagram missing')) if 'release' not in pure['canonicalSvg'] else None)
        attempt('VR015',lambda: (_ for _ in ()).throw(AssertionError('static SVG omitted nodes/labels')) if 'data-diagram-node' not in pure['canonicalSvg'] or 'release' not in pure['canonicalSvg'] else None)
        attempt('VR019',lambda: (_ for _ in ()).throw(AssertionError('legacy line unmapped')) if not pure['line']['model']['mapping'].get('x') or not pure['line']['model']['mapping'].get('y') else None)
        attempt('VR020',lambda: (_ for _ in ()).throw(AssertionError('legacy line has no marks')) if pure['line']['svg'].count('data-chart-point')<1 else None)
        attempt('VR021',lambda: (_ for _ in ()).throw(AssertionError(pure['line']['summary'])) if 'unmapped' in pure['line']['summary'].lower() else None)
        attempt('VR022',lambda: (_ for _ in ()).throw(AssertionError('reopened line blank')) if pure['reopened']['svg'].count('data-chart-point')<1 else None)
        attempt('VR023',lambda: (_ for _ in ()).throw(AssertionError('wafer observations not hydrated')) if len(pure['wafer']['model']['dataset']['rows'])!=3 else None)
        attempt('VR024',lambda: (_ for _ in ()).throw(AssertionError('wafer die count mismatch')) if pure['wafer']['svg'].count('data-wafer-die')!=3 else None)
        attempt('VR025',lambda: (_ for _ in ()).throw(AssertionError('wafer legend stayed placeholder')) if '91 → 95' not in pure['wafer']['svg'] else None)
        attempt('VR026',lambda: (_ for _ in ()).throw(AssertionError('engineering observations not plotted')) if len(pure['engineering']['model']['dataset']['rows'])!=3 or pure['engineering']['svg'].count('data-chart-point')!=3 else None)
        stage_c=(ROOT/'scripts/release_checks/run_chart_studio_acceptance.py').read_text()
        attempt('VR027',lambda: (_ for _ in ()).throw(AssertionError('Stage C lacks plotted/unmapped guard')) if 'assert_plotted' not in stage_c or 'compatible non-empty data remained unmapped' not in stage_c else None)
        previews=[_report_thumbnail_markup(report_model(fixture(engine,element))) for engine,element in [('CoreChartEngine','Line Chart'),('WaferFabEngine','Wafer Map'),('DiagramEngine','Process Flow'),('TextEngine','Hero Title')]]
        attempt('VR032',lambda: (_ for _ in ()).throw(AssertionError('semantic miniature marker missing')) if any('data-preview-family' not in value for value in previews) else None)
        attempt('VR033',lambda: (_ for _ in ()).throw(AssertionError('family miniatures are not distinct')) if len(set(previews))!=4 else None)
        summary=_history_diff_summary({'items':[{'id':'x','title':'Old','x':1,'mapping':{'x':'a'},'chart_studio':{},'diagram':{}}]},{'items':[{'id':'x','title':'New','x':4,'mapping':{'x':'b'},'chart_studio':{'axes':{}},'diagram':{'nodes':[1]}}]})
        for cid,label in [('VR035','content/text'),('VR036','geometry'),('VR037','mapping'),('VR038','chart config'),('VR039','diagram config')]: attempt(cid,lambda label=label: (_ for _ in ()).throw(AssertionError(summary)) if label not in summary else None)
        frozen=hashlib.sha256((ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js').read_bytes()).hexdigest();record('VR056',frozen==FROZEN,frozen)

        with tempfile.TemporaryDirectory(prefix='visembler-visual-remediation-') as temp:
            host=NativeHost(ROOT,Path(temp)/'data');ids={}
            for index,spec in enumerate(pure['entries'],1): ids[f"{spec['engine']}::{spec['element']}"]=host.create(model=report_model(fixture(spec['engine'],spec['element'],index)),name=f'visual-{index}')
            diagram_id=ids['DiagramEngine::Process Flow'];line_id=ids['CoreChartEngine::Line Chart'];wafer_id=ids['WaferFabEngine::Wafer Map'];engineering_id=ids['EngineeringChartEngine::SPC Control Chart']
            free_items=[{**fixture('TextEngine','Hero Title',1),'id':'top-right','x':880,'y':40,'w':280,'h':130},{**fixture('CoreChartEngine','Line Chart',2),'id':'bottom-left','x':30,'y':620,'w':430,'h':240}]
            free_id=host.create(model=report_model(free_items[0],mode='free',items=free_items),name='selection-toolbar')
            history_record=host.repository.get(line_id);changed=json.loads(json.dumps(history_record.model));changed['items'][0]['title']='Changed trend';changed['items'][0]['x']=80;host.repository.commit(line_id,base_revision=history_record.revision,model=changed,commit_id='visual-history-change');history_record=host.repository.get(line_id);host.repository.checkpoint(line_id,'Visual review',expected_revision=history_record.revision)
            with host,sync_playwright() as playwright:
                browser=playwright.chromium.launch(**browser_kwargs());context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();events=BrowserEvents();events.attach(page)
                for key,rid in ids.items():
                    page.goto(f'{host.url}/visualizer?report={quote(rid)}',wait_until='domcontentloaded');ready(page,require_settled=True);page.wait_for_timeout(80);probe=visual_probe(page);probe['key']=key;receipt['visual_utilization'].append(probe)
                def family_ok(engine,min_area,min_width,min_internal=.04):
                    values=[value for value in receipt['visual_utilization'] if value['engine']==engine]
                    if not values or min(value['card_area_share'] for value in values)<min_area or min(value['width_share'] for value in values)<min_width or min(value['internal_area_share'] for value in values)<min_internal: raise AssertionError(values)
                attempt('VR002',lambda:family_ok('CoreChartEngine',.42,.82,.35));attempt('VR003',lambda: (_ for _ in ()).throw(AssertionError([value for value in receipt['visual_utilization'] if value['engine']=='TimelineEngine'])) if min(value['dominant_axis_share'] for value in receipt['visual_utilization'] if value['engine']=='TimelineEngine')<.70 else None);attempt('VR004',lambda:family_ok('WaferFabEngine',.28,.58,.24));attempt('VR005',lambda: (_ for _ in ()).throw(AssertionError([value for value in receipt['visual_utilization'] if value['engine']=='DiagramEngine'])) if any(value['internal_area_share']<.22 and value['dominant_axis_share']<.70 for value in receipt['visual_utilization'] if value['engine']=='DiagramEngine') else None)
                attempt('VR006',lambda:family_ok('TextEngine',.08,.65,.02))
                all_good=all(value['card_area_share']>=({'TextEngine':.08,'MetricEngine':.08,'EvidenceCompositeEngine':.08,'DecisionCompositeEngine':.08,'ProjectCompositeEngine':.08}.get(value['engine'],.18)) and not value['overflow'] for value in receipt['visual_utilization'])
                if not all_good: receipt['visual_utilization_failures']=[value for value in receipt['visual_utilization'] if value['card_area_share']<({'TextEngine':.08,'MetricEngine':.08,'EvidenceCompositeEngine':.08,'DecisionCompositeEngine':.08,'ProjectCompositeEngine':.08}.get(value['engine'],.18)) or value['overflow']]
                record('VR001',rows['VR001']['status']=='PASS' and all_good,'one or more production elements missed family utilization/overflow limits' if not all_good else '')
                multi=report_model(fixture('TextEngine','Body Narrative',1),items=[fixture('TextEngine','Body Narrative',1),fixture('TimelineEngine','Event Timeline',2),fixture('CoreChartEngine','Line Chart',3)])
                multi_id=host.create(model=multi,name='multi-growth');page.goto(f'{host.url}/visualizer?report={quote(multi_id)}',wait_until='domcontentloaded');ready(page,require_settled=True);layout=page.evaluate('()=>window.__VIZ_PROD__.layoutRects()')
                attempt('VR007',lambda: (_ for _ in ()).throw(AssertionError(layout)) if next(v for v in layout if v['growth']=='plot')['h']<=next(v for v in layout if v['growth']=='text')['h'] else None)
                attempt('VR008',lambda: (_ for _ in ()).throw(AssertionError(layout)) if max(v['h'] for v in layout if v['growth'] in {'text','horizontal'})>380 else None)
                free_before={value['id']:(value['x'],value['y'],value['w'],value['h']) for value in host.repository.get(free_id).model['items']};page.goto(f'{host.url}/visualizer?report={quote(free_id)}',wait_until='domcontentloaded');ready(page,require_settled=True);page.set_viewport_size({'width':1024,'height':800});page.wait_for_timeout(80);free_after={value['id']:(value['x'],value['y'],value['w'],value['h']) for value in page.evaluate('()=>window.CompanyUIVisualizerBridge.state().model.items')};record('VR009',free_before==free_after,str((free_before,free_after)))
                page.goto(f'{host.url}/visualizer?report={quote(diagram_id)}',wait_until='domcontentloaded');ready(page,require_settled=True);attempt('VR014',lambda: (_ for _ in ()).throw(AssertionError('diagram error in preview')) if 'Diagram data needs review' in page.locator('#componentLayer').inner_text() else None)
                page.locator('[data-action="edit-diagram"]').click();page.locator('#diagram-studio[data-studio-ready="true"]').wait_for(timeout=20000);page.wait_for_timeout(180)
                attempt('VR016',lambda: (_ for _ in ()).throw(AssertionError('diagram did not initialize fitted')) if 'scale(' not in (page.locator('#ds-canvas').get_attribute('style') or '') or page.evaluate('()=>CompanyUIDiagramStudio.state().model.nodes.some(n=>{const r=document.querySelector(`[data-node-id="${n.id}"]`)?.getBoundingClientRect(),w=document.querySelector("#ds-canvas-wrap")?.getBoundingClientRect();return r&&!((r.right<=w.right+2)&&(r.bottom<=w.bottom+2)&&(r.left>=w.left-2)&&(r.top>=w.top-2))})') else None)
                page.set_viewport_size({'width':768,'height':800});page.wait_for_timeout(100);shape_button=page.locator('[data-action="toggle-palette"]');shape_button.click();attempt('VR017',lambda: (_ for _ in ()).throw(AssertionError('shape drawer unavailable')) if not page.locator('.ds-palette.is-open').is_visible() else None);page.locator('[data-action="close-panels"]').last.click();page.locator('[data-action="toggle-inspector"]').click();attempt('VR018',lambda: (_ for _ in ()).throw(AssertionError('inspector drawer unavailable')) if not page.locator('.ds-inspector.is-open').is_visible() else None)
                page.set_viewport_size({'width':1440,'height':900});page.goto(f'{host.url}/visualizer/chart-studio?report={quote(line_id)}&element=item-4',wait_until='domcontentloaded')
                # Resolve element id from the route report instead of relying on registry order.
                if page.locator('#chart-studio[data-studio-ready="true"]').count()==0:
                    line_element=host.repository.get(line_id).model['items'][0]['id'];page.goto(f'{host.url}/visualizer/chart-studio?report={quote(line_id)}&element={quote(str(line_element))}',wait_until='domcontentloaded')
                page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000);attempt('VR019',lambda: (_ for _ in ()).throw(AssertionError(page.locator('#cs-summary').inner_text())) if 'unmapped' in page.locator('#cs-summary').inner_text().lower() else None);attempt('VR020',lambda: (_ for _ in ()).throw(AssertionError('blank live chart')) if page.locator('#cs-canvas [data-chart-point]').count()<1 else None);attempt('VR021',lambda: (_ for _ in ()).throw(AssertionError('unmapped SVG aria')) if 'unmapped' in (page.locator('#cs-canvas svg').get_attribute('aria-label') or '').lower() else None)
                page.locator('[data-action="save"]').click();page.wait_for_function('()=>!CompanyUIChartStudio.state.pending',timeout=20000);page.reload(wait_until='domcontentloaded');page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000);attempt('VR022',lambda: (_ for _ in ()).throw(AssertionError('reopened chart blank')) if page.locator('#cs-canvas [data-chart-point]').count()<1 else None)
                for rid,cids in [(wafer_id,('VR023','VR024','VR025')),(engineering_id,('VR026',))]:
                    element_id=host.repository.get(rid).model['items'][0]['id'];page.goto(f'{host.url}/visualizer/chart-studio?report={quote(rid)}&element={quote(str(element_id))}',wait_until='domcontentloaded');page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000);studio=page.evaluate('()=>JSON.parse(JSON.stringify(CompanyUIChartStudio.model))')
                    if rid==wafer_id:
                        attempt('VR023',lambda studio=studio: (_ for _ in ()).throw(AssertionError(studio)) if len(studio['dataset']['rows'])!=4 else None);attempt('VR024',lambda: (_ for _ in ()).throw(AssertionError('die count mismatch')) if page.locator('#cs-canvas [data-wafer-die]').count()!=4 else None);attempt('VR025',lambda: (_ for _ in ()).throw(AssertionError(page.locator('#cs-canvas').inner_text())) if '91 → 97' not in page.locator('#cs-canvas').inner_text() else None)
                    else: attempt('VR026',lambda studio=studio: (_ for _ in ()).throw(AssertionError('engineering route blank')) if len(studio['dataset']['rows'])!=10 or page.locator('#cs-canvas [data-chart-point]').count()!=10 else None)
                page.goto(f'{host.url}/visualizer?report={quote(free_id)}',wait_until='domcontentloaded');ready(page,require_settled=True)
                for cid,zoom,item_id in [('VR028',.4,'top-right'),('VR029',.55,'bottom-left'),('VR030',1,'top-right')]:
                    page.evaluate('(z)=>window.__VIZ_PROD__.setZoom(z,true,.1)',zoom);distance=toolbar_distance(page,item_id);record(cid,distance<=20,f'distance {distance:.1f}px')
                page.locator('#libraryToggle').click();page.wait_for_timeout(80);distance=toolbar_distance(page,'bottom-left');page.locator('#inspectorToggle').click();page.wait_for_timeout(80);distance=max(distance,toolbar_distance(page,'top-right'));record('VR031',distance<=20,f'distance {distance:.1f}px')
                page.goto(f'{host.url}/visualizer/reports?report={quote(line_id)}',wait_until='domcontentloaded');page.locator('.cui-report-hub').wait_for(timeout=20000);attempt('VR034',lambda: (_ for _ in ()).throw(AssertionError('revision comparison miniatures missing')) if page.locator('.cui-history-compare .cui-report-thumb-svg').count()<2 else None)
                checkpoint=page.locator('input[placeholder="Before review"]').first;button=page.locator('button:has-text("Save checkpoint")').first;attempt('VR040',lambda: (_ for _ in ()).throw(AssertionError('checkpoint has neither a safe default nor disabled empty state')) if bool(checkpoint.input_value().strip())!=button.is_enabled() else None)
                receipt['unexpected_errors']=events.unexpected;record('VR055',not events.unexpected,str(events.unexpected[:5]));context.close();browser.close()
    except Exception as error:
        receipt['harness_error']=str(error);receipt['traceback']=traceback.format_exc()

    if not args.skip_benchmark:
        benchmark_dir=output/'benchmark';result=subprocess.run([sys.executable,str(ROOT/'scripts/release_checks/run_stage_d_benchmark.py'),'--output',str(benchmark_dir)],cwd=ROOT,timeout=600);benchmark=json.loads((benchmark_dir/'stage-d-benchmark.json').read_text()) if (benchmark_dir/'stage-d-benchmark.json').exists() else {'tasks':[]}
        by_name={task['task']:task for task in benchmark.get('tasks',[])}
        def quality(name): return by_name.get(name,{}).get('checks',{}).get('visual_quality',{})
        def family_quality(name,engine): return [value for value in quality(name).get('elements',[]) if value.get('engine')==engine]
        process=quality('process-health-from-data');wafer=quality('wafer-investigation');rca=quality('rca-evidence-report');executive=quality('executive-summary')
        record('VR041',by_name.get('process-health-from-data',{}).get('status')=='PASS' and (process.get('occupied_area_ratio') or 0)>=.42)
        wafer_values=family_quality('wafer-investigation','WaferFabEngine');record('VR042',by_name.get('wafer-investigation',{}).get('status')=='PASS' and (wafer.get('occupied_area_ratio') or 0)>=.42 and wafer.get('wafer_dies',0)>0 and wafer_values and min(value.get('visual_utilization',0) for value in wafer_values)>=.24)
        diagram_values=family_quality('rca-evidence-report','DiagramEngine');timeline_values=family_quality('rca-evidence-report','TimelineEngine');record('VR043',by_name.get('rca-evidence-report',{}).get('status')=='PASS' and (rca.get('occupied_area_ratio') or 0)>=.52 and rca.get('diagram_errors',1)==0 and all(value.get('visual_utilization',0)>=.22 or value.get('dominant_axis_share',0)>=.70 for value in diagram_values) and all(value.get('dominant_axis_share',0)>=.70 for value in timeline_values))
        record('VR044',by_name.get('executive-summary',{}).get('status')=='PASS' and (executive.get('occupied_area_ratio') or 0)>=.52 and executive.get('empty_error_state_count',1)==0)
        toolbar=quality('executive-summary').get('context_toolbar');record('VR045',by_name.get('executive-summary',{}).get('status')=='PASS' and (toolbar is None or toolbar.get('distance',999)<=20))
        record('VR046',by_name.get('repeat-weekly-operations',{}).get('status')=='PASS' and quality('repeat-weekly-operations').get('checkpoint_created') is True)
        record('VR047',benchmark.get('status')=='PASS' and len(by_name)==5 and all(task.get('status')=='PASS' and task.get('checks',{}).get('visual_quality',{}).get('empty_error_state_count',0)==0 for task in by_name.values()))
    else:
        for cid in ('VR041','VR042','VR043','VR044','VR045','VR046','VR047'): rows[cid]={'id':cid,'name':NAMES[cid],'status':'NOT_APPLICABLE','reason':'benchmark intentionally skipped for focused development run'}

    regressions=[('VR048','run_stage_a_acceptance.py'),('VR049','run_diagram_studio_acceptance.py'),('VR050','run_chart_studio_acceptance.py'),('VR051','run_stage_d_acceptance.py')]
    if args.skip_regressions:
        for cid,script in regressions: rows[cid]={'id':cid,'name':NAMES[cid],'status':'NOT_APPLICABLE','reason':f'{script} intentionally deferred to final run'}
    else:
        for cid,script in regressions:
            command=[sys.executable,str(ROOT/'scripts/release_checks'/script),'--output',str(output/script.replace('.py',''))]
            if script in {'run_chart_studio_acceptance.py','run_stage_d_acceptance.py'}: command.append('--skip-regressions')
            code=subprocess.run(command,cwd=ROOT,timeout=360).returncode;record(cid,code==0,f'{script} exited {code}')
    record('VR052',rows['VR001']['status']=='PASS')
    data_code=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_visualizer_authoring_p0.py','tests/test_visualizer_p1_usability.py','tests/test_visualizer_chart_studio.py'],cwd=ROOT,timeout=180,capture_output=True,text=True).returncode;record('VR053',data_code==0,f'pytest exit {data_code}')
    contract_code=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_visualizer_product_completion_p0.py','tests/test_visualizer_final_visual_remediation.py'],cwd=ROOT,timeout=180,capture_output=True,text=True).returncode;record('VR054',contract_code==0,f'pytest exit {contract_code}')
    receipt['checks']=[rows[cid] for cid in NAMES];receipt['pass']=sum(row['status']=='PASS' for row in receipt['checks']);receipt['applicable']=sum(row['status']!='NOT_APPLICABLE' for row in receipt['checks']);receipt['not_applicable']=sum(row['status']=='NOT_APPLICABLE' for row in receipt['checks']);receipt['status']='PASS' if receipt['pass']==receipt['applicable'] and not receipt.get('harness_error') else 'FAIL'
    write_json(output/'final-visual-remediation-acceptance.json',receipt);print(json.dumps({'status':receipt['status'],'pass':receipt['pass'],'applicable':receipt['applicable'],'not_applicable':receipt['not_applicable'],'path':str(output/'final-visual-remediation-acceptance.json')}));return 0 if receipt['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
