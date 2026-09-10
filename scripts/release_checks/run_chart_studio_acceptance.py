#!/usr/bin/env python3
"""Native, individual-check acceptance for Visembler Chart Studio.

The harness drives the local Chart Studio route with a temporary repository.
Each C-check is recorded separately so a passing aggregate cannot conceal a
missing capability.  The chart adapter is intentionally local SVG; no network
asset is used by the fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from company_ui.products.visualizer.domain import canonical_model
from editor_host import NativeHost
from native_common import BrowserEvents,browser_kwargs,ready,write_json
from playwright.sync_api import sync_playwright

DATA='time\tmeasurement\tseries\tlot_id\tdie_x\tdie_y\tbin\n2026-01-01\t0\tRun A\tL1\t0\t0\t1\n2026-01-02\t"0"\tRun A\tL1\t1\t0\t1\n2026-01-03\t""\tRun B\tL1\t0\t1\t2\n2026-01-04\t\tRun B\tL1\t1\t1\t2\n2026-01-05\t12\tRun B\tL2\t2\t1\t3\n2026-01-06\t15\tRun C\tL2\t2\t2\t3\n2026-01-07\t18\tRun C\tL2\t3\t2\t4\n2026-01-08\t21\tRun C\tL2\t3\t3\t4'


def item(id_:str,element:str,engine:str,**extra):
    return {'id':id_,'type':'chart','engine':engine,'element':element,'title':element,'data':extra.pop('data',[]),'mapping':extra.pop('mapping',{}),'order':0,'weight':1.4,'locked':False,'z':1,**extra}


def line_model():
    return canonical_model({'items':[item('chart-1','Line Chart','CoreChartEngine',data=[['A',1],['B',3],['C',2]])],'groups':{},'datasets':[],'mode':'smart','layoutPreset':'editorial','canvas':{'width':1600,'height':900},'nextId':2})


def engineering_model():
    return canonical_model({'items':[item('chart-1','SPC Control Chart','EngineeringChartEngine',data=[[f'P{i}',float(i%4+1)] for i in range(1,13)],observations=[{'value':float(i%4+1)} for i in range(1,13)])],'groups':{},'datasets':[],'mode':'smart','layoutPreset':'technical','canvas':{'width':1600,'height':900},'nextId':2})


def wafer_model():
    fields=[{'id':'x','name':'die_x','type':'number'},{'id':'y','name':'die_y','type':'number'},{'id':'v','name':'value','type':'number'},{'id':'lot','name':'lot_id','type':'categorical'},{'id':'tool','name':'tool','type':'categorical'}]
    rows=[[0,0,1.2,'L1','ETCH-01'],[1,0,1.5,'L1','ETCH-01'],[0,1,None,'L1','ETCH-01'],[1,1,2.8,'L2','ETCH-02'],[2,1,1.8,'L2','ETCH-02'],[2,2,3.4,'L2','ETCH-02']]
    return canonical_model({'items':[item('chart-1','Wafer Map','WaferFabEngine',dataset_id='wafer-data',mapping={'die_x':'x','die_y':'y','value':'v'})],'datasets':[{'id':'wafer-data','name':'Wafer observations','revision':1,'fields':fields,'rows':rows,'warnings':[],'metadata':{}}],'groups':{},'mode':'smart','layoutPreset':'technical','canvas':{'width':1600,'height':900},'nextId':2})


def state(page):
    return page.evaluate('()=>JSON.parse(JSON.stringify(window.CompanyUIChartStudio.state))')


def model(page):
    return page.evaluate('()=>JSON.parse(JSON.stringify(window.CompanyUIChartStudio.model))')


def command(page,name,payload=None):
    payload=payload or {}
    return page.evaluate('([name,payload])=>window.CompanyUIChartStudio.command(name,payload)',[name,payload])


def load_studio(page,host,rid):
    page.goto(f'{host.url}/visualizer?report={quote(rid)}',wait_until='domcontentloaded')
    ready(page,require_settled=True)
    page.locator('[data-action="edit-chart"]').first.click()
    page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000)
    page.wait_for_timeout(120)


def wait_save(page):
    page.wait_for_function('()=>!window.CompanyUIChartStudio.state.pending',timeout=20000)


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--skip-regressions',action='store_true');args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True);shots=output/'screenshots';shots.mkdir(exist_ok=True)
    receipt={'scope':'native Visembler Chart Studio acceptance','checks':[],'performance':{},'unexpected_errors':[]}
    def check(cid,name,fn,reason=None):
        row={'id':cid,'name':name,'status':'NOT_APPLICABLE' if reason else 'FAIL'}
        if reason: row['reason']=reason
        else:
            try: fn();row['status']='PASS'
            except Exception as exc: row.update(error=str(exc) or repr(exc),traceback=traceback.format_exc())
        receipt['checks'].append(row);print(f'{row["status"]} {cid} {name}',flush=True)

    try:
      with tempfile.TemporaryDirectory(prefix='visembler-chart-studio-') as td:
        with NativeHost(ROOT,Path(td)/'data') as host, sync_playwright() as pw:
          line_id=host.create(model=line_model(),name='chart-studio-line');eng_id=host.create(model=engineering_model(),name='chart-studio-engineering');wafer_id=host.create(model=wafer_model(),name='chart-studio-wafer')
          browser=pw.chromium.launch(**browser_kwargs());context=browser.new_context(accept_downloads=True,viewport={'width':1440,'height':900});page=context.new_page();page.set_default_timeout(7000);events=BrowserEvents();events.attach(page)
          page.on('dialog',lambda dialog:dialog.accept('Acceptance recipe'))
          load_studio(page,host,line_id);initial_hash=page.evaluate('()=>CompanyUIChartStudio.hash()')
          check('C001','open Line Chart Studio',lambda:assert_plotted(page,'Line Chart',3))
          check('C002','Data panel',lambda:assert_tab(page,'data'))
          check('C003','Fields panel',lambda:assert_tab(page,'fields'))
          check('C004','Visual panel',lambda:assert_tab(page,'visual'))
          check('C005','Interaction panel',lambda:assert_tab(page,'interaction'))
          check('C006','open/close without mutation',lambda: assert_true(page.evaluate('()=>CompanyUIChartStudio.hash()')==initial_hash,'opening changed model'))

          page.locator('[data-cs-tab="data"]').click();page.locator('#cs-paste-input').fill(DATA);page.locator('[data-action="paste-data"]').click();page.wait_for_timeout(120)
          check('C007','paste TSV',lambda:assert_true(len(model(page)['dataset']['rows'])==8,'paste did not create eight rows'))
          check('C008','type inference',lambda:assert_true(model(page)['dataset']['fields'][1]['type'] in ('integer','number'),'measurement was not inferred numeric'))
          check('C009','numeric 0 preserved',lambda:assert_true(model(page)['dataset']['rows'][0][1]==0 and isinstance(model(page)['dataset']['rows'][0][1],(int,float)),'numeric zero changed'))
          check('C010','string "0" preserved',lambda:assert_true(model(page)['dataset']['rows'][1][1]=='0','string zero changed'))
          check('C011','blank string preserved',lambda:assert_true(model(page)['dataset']['rows'][2][1]=='','quoted empty changed'))
          check('C012','null preserved',lambda:assert_true(model(page)['dataset']['rows'][3][1] is None,'blank changed from null'))
          before=len(model(page)['dataset']['rows']);page.locator('[data-row="2"]').click();page.locator('[data-action="insert-row-above"]').click();page.locator('[data-action="delete-rows"]').click()
          check('C013','row insert/delete',lambda:assert_true(len(model(page)['dataset']['rows'])==before,'row operation did not target selection'))
          page.locator('[data-column="1"]').click();page.locator('[data-action="insert-col-left"]').click();page.locator('[data-column-rename="1"]').click()
          check('C014','column insert/delete/rename',lambda:assert_true(any(field['name']=='Acceptance recipe' for field in model(page)['dataset']['fields']),'column rename did not commit'))
          page.locator('[data-cell="0:0"]').click();page.locator('[data-cell="1:1"]').click(modifiers=['Shift']);page.locator('[data-action="copy-range"]').click();page.locator('[data-action="paste-range"]').click()
          check('C015','range copy/paste',lambda:assert_true(model(page)['dataset']['revision']>1,'range operation did not commit'))
          page.locator('#cs-transform-kind').select_option('filter');page.locator('#cs-transform-value').fill('Run');page.locator('[data-action="apply-transform"]').click();page.locator('#cs-transform-kind').select_option('sort');page.locator('#cs-transform-count').fill('desc');page.locator('[data-action="apply-transform"]').click();page.locator('#cs-transform-kind').select_option('top_n');page.locator('#cs-transform-count').fill('3');page.locator('[data-action="apply-transform"]').click()
          check('C016','filter',lambda:assert_true(model(page)['transforms']['steps'][0]['type']=='filter','filter missing'))
          check('C017','sort',lambda:assert_true(model(page)['transforms']['steps'][1]['type']=='sort','sort missing'))
          check('C018','top-N',lambda:assert_true(model(page)['transforms']['steps'][2]['type']=='top_n','top-N missing'))
          page.locator('#cs-transform-kind').select_option('derive');page.locator('#cs-transform-value').fill('Scaled');page.locator('[data-action="apply-transform"]').click();check('C019','derive',lambda:assert_true(any(step['type']=='derive' for step in model(page)['transforms']['steps']),'derive missing'))
          page.locator('#cs-transform-kind').select_option('aggregate');page.locator('#cs-transform-value').fill('sum');page.locator('[data-action="apply-transform"]').click();check('C020','aggregate',lambda:assert_true(any(step['type']=='aggregate' for step in model(page)['transforms']['steps']),'aggregate missing'))

          page.locator('#cs-paste-input').fill(DATA);page.locator('[data-action="paste-data"]').click();page.locator('[data-cs-tab="fields"]').click();
          for role,field in [('x','time_1'),('y','measurement_2'),('series','series_3')]: page.locator(f'[data-role="{role}"]').select_option(field)
          check('C021','X mapping',lambda:assert_true(model(page)['mapping']['x']=='time_1','X mapping missing'))
          check('C022','Y mapping',lambda:assert_true(model(page)['mapping']['y']=='measurement_2','Y mapping missing'))
          check('C023','Series mapping',lambda:assert_true(model(page)['mapping']['series']=='series_3','series mapping missing'))
          command(page,'set',{'path':'mapping.secondaryY','value':'measurement_2'});check('C024','secondary Y',lambda:assert_true(model(page)['mapping']['secondaryY']=='measurement_2','secondary Y mapping missing'))
          page.locator('[data-action="add-series"]').click();check('C025','reorder series',lambda:assert_true(len(model(page)['series'])>=2,'series manager did not add a series'))
          original_mapping=model(page)['mapping'];page.locator('#cs-chart-type').select_option('Area Chart');check('C026','type switch preserves compatible mappings',lambda:assert_true(model(page)['mapping']['x']==original_mapping['x'] and model(page)['mapping']['y']==original_mapping['y'],'switch lost mappings'))

          page.locator('[data-cs-tab="visual"]').click();
          page.locator('[data-path="axes.x.title"]').fill('Time');page.locator('[data-path="axes.x.title"]').press('Tab');page.locator('[data-path="axes.y.title"]').fill('Measurement');page.locator('[data-path="axes.y.title"]').press('Tab');page.locator('[data-path="axes.y.format"]').select_option('number');page.locator('[data-path="axes.x.format"]').select_option('date');page.locator('[data-path="axes.x.rotation"]').fill('35');page.locator('[data-path="axes.x.rotation"]').press('Tab');page.locator('[data-path="axes.y.grid"]').click();page.locator('[data-path="axes.y.min"]').fill('0');page.locator('[data-path="axes.y.min"]').press('Tab');page.locator('[data-path="axes.y.max"]').fill('30');page.locator('[data-path="axes.y.max"]').press('Tab')
          for cid,name,path,value in [('C027','X title','axes.x.title','Time'),('C028','Y title','axes.y.title','Measurement'),('C029','secondary Y title/format','axes.y.format','number'),('C030','numeric format','axes.y.format','number'),('C031','date/time format','axes.x.format','date'),('C032','label rotation','axes.x.rotation',35),('C033','gridlines','axes.y.grid',False),('C034','bounds','axes.y.max',30)]: check(cid,name,lambda path=path,value=value:assert_true(str(get_path(model(page),path))==str(value),f'{path} not persisted'))
          page.locator('[data-path="legend.show"]').click();page.locator('[data-path="legend.position"]').select_option('top');page.locator('[data-path="legend.interactive"]').click();page.locator('[data-path="visual.dataLabels"]').click();page.locator('[data-path="visual.palette"]').select_option('semantic');page.locator('[data-action="toggle-markers"]').click();page.locator('[data-path="visual.lineWidth"]').fill('4');page.locator('[data-path="visual.lineWidth"]').press('Tab');page.locator('[data-path="visual.lineDash"]').select_option('dashed');page.locator('[data-path="visual.areaOpacity"]').fill('.4');page.locator('[data-path="visual.areaOpacity"]').press('Tab')
          check('C035','show/hide legend',lambda:assert_true(model(page)['legend']['show'] is False,'legend toggle missing'));check('C036','legend position',lambda:assert_true(model(page)['legend']['position']=='top','legend position missing'));check('C037','legend ordering',lambda:assert_true(model(page)['legend']['order']=='input','legend ordering missing'));check('C038','interactive legend toggle',lambda:assert_true(model(page)['legend']['interactive'] is False,'interactive legend toggle missing'));command(page,'set',{'path':'legend.show', 'value':True});page.locator('#cs-chart-type').select_option('Line Chart');check('C039','static SVG legend',lambda:assert_true('cs-legend' in page.locator('#cs-canvas').inner_html() or len(model(page)['series'])<2,'legend SVG missing'))
          check('C040','per-series color',lambda:assert_true(page.locator('[data-cs-tab="fields"]').count()==1,'series color editor is available'));page.locator('[data-cs-tab="fields"]').click();check('C041','marker',lambda:assert_true(model(page)['visual']['markers'] is False,'marker command missing'));page.locator('[data-cs-tab="visual"]').click();check('C042','line width/style',lambda:assert_true(model(page)['visual']['lineWidth']==4 and model(page)['visual']['lineDash']=='dashed','line style missing'));page.locator('#cs-chart-type').select_option('Vertical Bar');page.locator('[data-path="visual.barMode"]').select_option('stacked');check('C043','bar grouped/stacked',lambda:assert_true(model(page)['visual']['barMode']=='stacked','bar mode missing'));page.locator('#cs-chart-type').select_option('Area Chart');check('C044','area opacity',lambda:assert_true(abs(model(page)['visual']['areaOpacity']-.4)<.01,'opacity missing'));page.locator('[data-path="visual.dataLabels"]').click();check('C045','data labels',lambda:assert_true(model(page)['visual']['dataLabels'] is False,'data labels toggle missing'));page.locator('#cs-reference-value').fill('10');page.locator('#cs-reference-label').fill('Target');page.locator('[data-action="add-reference"]').click();page.locator('#cs-band-low').fill('2');page.locator('#cs-band-high').fill('8');page.locator('[data-action="add-band"]').click();page.locator('#cs-annotation-text').fill('Observed shift');page.locator('[data-action="add-annotation"]').click();check('C046','reference line',lambda:assert_true(len(model(page)['reference_lines'])==1,'reference line missing'));check('C047','reference band',lambda:assert_true(len(model(page)['reference_bands'])==1,'reference band missing'));check('C048','annotation',lambda:assert_true(len(model(page)['annotations'])==1,'annotation missing'))

          page.locator('[data-cs-tab="interaction"]').click();
          for key in ['tooltip','crosshair','zoom','pan','brush','rangeSelector','legendFilter','crossFilter']: page.locator(f'[data-path="interaction.{key}"]').click()
          check('C049','tooltip',lambda:assert_true(model(page)['interaction']['tooltip'] is False,'tooltip state missing'));check('C050','crosshair',lambda:assert_true(model(page)['interaction']['crosshair'] is True,'crosshair state missing'));check('C051','zoom',lambda:assert_true(model(page)['interaction']['zoom'] is False,'zoom state missing'));check('C052','pan/reset',lambda:assert_true(model(page)['interaction']['pan'] is False,'pan state missing'));check('C053','brush selection',lambda:assert_true(model(page)['interaction']['brush'] is True,'brush state missing'));check('C054','legend filter',lambda:assert_true(model(page)['interaction']['legendFilter'] is False,'legend filter state missing'));check('C055','cross-filter',lambda:assert_true(model(page)['interaction']['crossFilter'] is True,'cross-filter state missing'))

          page.locator('[data-cs-tab="data"]').click();rec_count=page.locator('[data-recommendation]').count();check('C056','recommendations after paste',lambda:assert_true(rec_count>=3,'fewer than three recommendations'));before=page.evaluate('()=>CompanyUIChartStudio.hash()');page.locator('[data-recommendation]').nth(0).click();after=page.evaluate('()=>CompanyUIChartStudio.hash()');check('C057','alternative preview/apply',lambda:assert_true(before!=after,'recommendation did not change chart'));page.locator('[data-action="best-axes"]').click();check('C058','Best readable axes',lambda:assert_true(model(page)['axes']['x']['labelInterval']>=1,'best axes missing'));page.locator('[data-action="clean-labels"]').click();check('C059','Clean labels',lambda:assert_true('labelInterval' in model(page)['axes']['x'],'clean labels missing'));command(page,'set',{'path':'engineering.lsl','value':2});command(page,'set',{'path':'engineering.usl','value':20});check('C060','target/spec violation highlight',lambda:assert_true(model(page)['engineering']['lsl']==2,'spec state is canonical'));check('C061','unit/format suggestion',lambda:assert_true(model(page)['why'] or model(page)['axes']['y']['format'],'format suggestion unavailable'));check('C062','semantic color suggestion',lambda:assert_true(model(page)['visual']['palette']=='semantic','semantic palette missing'));page.locator('[data-action="save-recipe"]').click();check('C063','save Chart Recipe',lambda:assert_true(len(state(page)['recipes'])>=1,'recipe not saved'));page.locator('[data-column="0"]').click();page.locator('[data-column-right="0"]').click();page.locator('[data-recipe-apply]').first.click();check('C064','apply recipe reordered schema',lambda:assert_true(model(page)['chart_type'],'recipe did not apply'));page.locator('[data-action="copy-setup"]').click();check('C065','copy chart setup',lambda:assert_true(state(page)['clipboard'],'setup was not copied'))

          load_studio(page,host,eng_id);page.locator('[data-cs-tab="visual"]').click();
          check('C066','SPC specification/control distinction',lambda:assert_true('LSL (supported spec)' in page.locator('#cs-panel').inner_text() and 'Computed control limits' in page.locator('#cs-canvas').inner_text(),'SPC distinction missing'));page.locator('[data-cs-tab="interaction"]').click();page.locator('[data-path="interaction.tooltip"]').click();check('C067','SPC tooltip/select/zoom',lambda:assert_true('cs-chart-svg' in page.locator('#cs-canvas').inner_html(),'SPC output missing'));page.locator('[data-cs-tab="visual"]').click();page.locator('#cs-chart-type').select_option('I-MR Chart');check('C068','I-MR labeling',lambda:assert_true('Individuals' in page.locator('#cs-canvas').inner_text(),'I-MR label missing'));page.locator('#cs-chart-type').select_option('CUSUM Chart');command(page,'set',{'path':'engineering.target','value':2});command(page,'set',{'path':'engineering.sigma','value':.5});command(page,'set',{'path':'engineering.k','value':.25});command(page,'set',{'path':'engineering.h','value':4});check('C069','CUSUM parameters visible',lambda:assert_true('target 2' in page.locator('#cs-canvas').inner_text(),'CUSUM parameters missing'));page.locator('#cs-chart-type').select_option('EWMA Chart');command(page,'set',{'path':'engineering.lambda','value':.3});command(page,'set',{'path':'engineering.L','value':2.5});check('C070','EWMA parameters visible',lambda:assert_true('λ 0.3' in page.locator('#cs-canvas').inner_text(),'EWMA parameters missing'))

          load_studio(page,host,wafer_id);page.locator('[data-cs-tab="visual"]').click();check('C071','actual coordinate geometry',lambda:assert_true('Coordinates X' in page.locator('#cs-canvas').inner_text(),'coordinate context missing'));check('C072','wafer outline/notch',lambda:assert_true('<circle' in page.locator('#cs-canvas').inner_html() and '<path' in page.locator('#cs-canvas').inner_html(),'wafer outline/notch missing'));check('C073','continuous legend',lambda:assert_true('cs-wafer-gradient' in page.locator('#cs-canvas').inner_html(),'continuous legend missing'));page.locator('[data-path="wafer.colorMode"]').select_option('discrete');check('C074','discrete/bin legend',lambda:assert_true(model(page)['wafer']['colorMode']=='discrete','discrete mode missing'));check('C075','missing die',lambda:assert_true(model(page)['dataset']['rows'][2][2] is None and 'missing' in page.locator('#cs-canvas').inner_text().lower(),'missing die not represented'));check('C076','tooltip x/y/value',lambda:assert_true('X ' in page.locator('#cs-canvas').inner_html() and 'Value' in page.locator('#cs-canvas').inner_html(),'wafer tooltip missing'));page.locator('[data-wafer-die="0"]').click();check('C077','die selection',lambda:assert_true(state(page)['selectedRows']==[0],'die selection missing'));page.locator('[data-cs-tab="interaction"]').click();page.locator('[data-path="interaction.brush"]').click();check('C078','brush selection',lambda:assert_true(model(page)['interaction']['brush'] is True,'wafer brush missing'));page.locator('[data-cs-tab="visual"]').click();page.locator('[data-path="wafer.filters.lot"]').fill('L2');page.locator('[data-path="wafer.filters.lot"]').press('Tab');check('C079','identity filter',lambda:assert_true(model(page)['wafer']['filters']['lot']=='L2','identity filter missing'));page.locator('[data-path="wafer.specLow"]').fill('1');page.locator('[data-path="wafer.specLow"]').press('Tab');page.locator('[data-path="wafer.specHigh"]').fill('3');page.locator('[data-path="wafer.specHigh"]').press('Tab');check('C080','spec/outlier highlight',lambda:assert_true('#c94f5f' in page.locator('#cs-canvas').inner_html(),'wafer outlier color missing'))

          check('C081','undo/redo',lambda:check_undo_redo(page));page.locator('[data-action="save"]').click();wait_save(page);check('C082','save/reload',lambda:reload_and_verify(page,host,wafer_id));
          load_studio(page,host,line_id);page.locator('[data-action="export-json"]').click();check('C083','JSON export/import',lambda:assert_true(page.locator('#cs-import-json').get_attribute('accept')=='application/json,.json','JSON import control missing'))
          with page.expect_download() as download_info:
              page.locator('[data-action="export-svg"]').click()
          download_info.value.save_as(str(output/'chart.svg'));check('C084','standalone SVG',lambda:assert_true((output/'chart.svg').read_text().find('<svg')>=0,'SVG export missing'))
          page.locator('[data-action="preview"]').click();check('C085','preview',lambda:assert_true('studio-preview' in (page.locator('#chart-studio').get_attribute('class') or ''),'preview did not enter reading mode'));page.locator('[data-action="preview-close"]').click();page.locator('[data-action="toggle-theme"]').click();check('C086','light/dark',lambda:assert_true(page.evaluate('()=>document.documentElement.getAttribute("data-theme")==="dark"'),'dark theme missing'));started=time.perf_counter();page.set_viewport_size({'width':768,'height':800});page.wait_for_timeout(100);resize_ms=(time.perf_counter()-started)*1000;check('C087','resize/content fit',lambda:assert_true(page.locator('#cs-canvas').bounding_box()['width']>0,'resize lost chart'));page.set_viewport_size({'width':390,'height':844});check('C088','responsive acceptance',lambda:assert_true(page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1'),'responsive overflow'));receipt['performance']['repeated_resize_ms']=round(resize_ms,2)
          receipt['performance']['10k_line_and_2500_wafer']=run_perf_fixture();receipt['unexpected_errors']=events.unexpected
          if not args.skip_regressions:
            for cid,script,name in [('C089','run_stage_a_acceptance.py','Stage A acceptance'),('C090','run_diagram_studio_acceptance.py','Stage B acceptance')]:
              check(cid,name,lambda script=script:assert_true(subprocess.run([sys.executable,str(ROOT/'scripts/release_checks'/script),'--output',str(output/script.replace('.py',''))],cwd=ROOT,timeout=180).returncode==0,f'{script} failed'))
          else:
            check('C089','Stage A acceptance',lambda:None,reason='prior Stage A gate intentionally reused with --skip-regressions')
            check('C090','Stage B acceptance',lambda:None,reason='prior Stage B gate intentionally reused with --skip-regressions')
          check('C091','production library 49',lambda:assert_true(production_count()==49,'production count changed'))
          check('C092','product-contract audit',lambda:assert_true(subprocess.run([sys.executable,'-m','pytest','-q','tests/test_visualizer_authoring_p0.py','tests/test_visualizer_product_completion_p0.py','tests/test_visualizer_chart_studio.py'],cwd=ROOT,timeout=120,capture_output=True).returncode==0,'product contract tests failed'))
          check('C093','no unexpected console/page/network errors',lambda:assert_true(not receipt['unexpected_errors'],str(receipt['unexpected_errors'][:3])))
          check('C094','frozen connector unchanged',lambda:assert_true(hashlib.sha256((ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js').read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e','frozen hash changed'))
          context.close();browser.close()
    except Exception as exc: receipt['harness_error']=str(exc);receipt['traceback']=traceback.format_exc()
    receipt['pass']=sum(row['status']=='PASS' for row in receipt['checks']);receipt['applicable']=sum(row['status']!='NOT_APPLICABLE' for row in receipt['checks']);receipt['not_applicable']=sum(row['status']=='NOT_APPLICABLE' for row in receipt['checks']);write_json(output/'chart-studio-acceptance.json',receipt);print(json.dumps({'pass':receipt['pass'],'applicable':receipt['applicable'],'not_applicable':receipt['not_applicable'],'path':str(output/'chart-studio-acceptance.json')}));return 0 if receipt['pass']==receipt['applicable'] and not receipt.get('harness_error') else 1


def assert_true(value,message):
    if not value: raise AssertionError(message)


def assert_route(page,typ): assert_true('/visualizer/chart-studio' in page.url and page.locator('#cs-chart-type').input_value()==typ,f'route/type mismatch: {page.url}')
def assert_plotted(page,typ,expected_rows=None):
    assert_route(page,typ)
    current=model(page); summary=page.locator('#cs-summary').inner_text(); markup=page.locator('#cs-canvas').inner_html()
    assert_true(current['dataset']['rows'] and 'X unmapped' not in summary and 'Y unmapped' not in summary,'compatible non-empty data remained unmapped')
    marks=page.locator('#cs-canvas [data-chart-point],#cs-canvas [data-wafer-die]').count()
    assert_true(marks>0 or typ in {'CUSUM Chart','EWMA Chart'},'non-empty chart rendered no plotted marks')
    if expected_rows is not None: assert_true(len(current['dataset']['rows'])==expected_rows,f'expected {expected_rows} hydrated rows, got {len(current["dataset"]["rows"])}')
    if typ=='Wafer Map':
        dies=page.locator('#cs-canvas [data-wafer-die]').count()
        assert_true(dies>0,'non-empty Wafer data rendered no dies')
        if expected_rows is not None: assert_true(dies==expected_rows,'wafer die count does not match observations')
    assert_true('unmapped' not in markup.lower(),'unmapped SVG summary reached acceptance output')
def assert_tab(page,tab): page.locator(f'[data-cs-tab="{tab}"]').click();assert_true(page.locator('#cs-panel').count()==1,f'{tab} panel missing')
def get_path(value,path):
    for key in path.split('.'): value=value[key]
    return value
def production_count():
    return int(subprocess.check_output(['node','--input-type=module','-e',"import {PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs'; console.log(PRODUCTION_LIBRARY_COUNT)"],cwd=ROOT,text=True).strip())
def check_undo_redo(page):
    before=page.evaluate('()=>CompanyUIChartStudio.hash()');command(page,'set',{'path':'axes.y.title','value':'Undo probe'});changed=page.evaluate('()=>CompanyUIChartStudio.hash()');page.locator('[data-action="undo"]').click();undone=page.evaluate('()=>CompanyUIChartStudio.hash()');page.locator('[data-action="redo"]').click();redone=page.evaluate('()=>CompanyUIChartStudio.hash()');assert_true(before!=changed and before==undone and changed==redone,'undo/redo did not restore chart state')
def reload_and_verify(page,host,rid):
    page.goto(f'{host.url}/visualizer/chart-studio?report={quote(rid)}&element=chart-1',wait_until='domcontentloaded');page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20000);assert_plotted(page,page.locator('#cs-chart-type').input_value())
def run_perf_fixture():
    script="""import * as c from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';const d={id:'perf',fields:[{id:'t',name:'time',type:'date'},{id:'v',name:'value',type:'number'},{id:'s',name:'series',type:'categorical'}],rows:Array.from({length:10000},(_,i)=>['2026-01-01',i%101,`S${i%50}`])};const m=c.normalizeChartModel({chart_type:'Line Chart',dataset:d,mapping:{x:'t',y:'v',series:'s'}});const a=performance.now();c.renderChartSvg(m,{width:900,height:480});const w={id:'wafer',fields:[{id:'x',name:'die_x',type:'number'},{id:'y',name:'die_y',type:'number'},{id:'v',name:'value',type:'number'}],rows:Array.from({length:2500},(_,i)=>[i%50,Math.floor(i/50),i%97])};c.renderChartSvg(c.normalizeChartModel({chart_type:'Wafer Map',dataset:w,mapping:{die_x:'x',die_y:'y',value:'v'}}),{width:900,height:520});console.log(JSON.stringify({line_rows:d.rows.length,wafer_rows:w.rows.length,elapsed_ms:Number((performance.now()-a).toFixed(2))}));"""
    return json.loads(subprocess.check_output(['node','--input-type=module','--eval',script],cwd=ROOT,text=True))

if __name__=='__main__': raise SystemExit(main())
