"""Bounded editor timings; not hardware-independent performance certification."""
import argparse,json,os,platform,shutil,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(Path(__file__).parent)]
from editor_host import EditorHost,NativeHost,load_editor
from run_editor_workflows import ready
from playwright.sync_api import sync_playwright

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--native',action='store_true');a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 result={'host':'native' if a.native else 'embedded test host','platform':platform.platform(),'cpu_count':os.cpu_count(),'measurements':[],'interpretation':'Observed timings only, not a deployment SLA or a complete memory/load test.'}
 with tempfile.TemporaryDirectory() as td,sync_playwright() as pw,(NativeHost if a.native else EditorHost)(ROOT,Path(td)) as host:
  kwargs={'headless':True};exe=os.environ.get('VISEMBLER_BROWSER') or shutil.which('chromium')
  if exe:kwargs.update(executable_path=exe,args=['--no-sandbox'])
  b=pw.chromium.launch(**kwargs);result['browser']=b.version
  for count in (1,20,100):
   # Synthetic setup only; this stage measures rendering, not authoring usability.
   model={'mode':'free','items':[{'id':f'p{i}','type':'metric','engine':'MetricEngine','element':'Hero KPI','title':f'KPI {i}','value':i,'order':i,'x':(i%5)*300,'y':(i//5)*150,'w':280,'h':140,'locked':False,'z':i} for i in range(count)]}
   rid=host.create(model);ctx=b.new_context(viewport={'width':1440,'height':1000});p=ctx.new_page();start=time.perf_counter();load_editor(p,host,rid);ready(p);elapsed=(time.perf_counter()-start)*1000
   timing=p.evaluate('''()=>{const measure=(fn,n)=>Array.from({length:n},()=>{const t=performance.now();fn();return performance.now()-t});return {geometry_ms:measure(()=>__VIZ_PROD__.renderGeometryOnly(),20),full_render_ms:measure(()=>__VIZ_PROD__.renderAll(),5),cache_entries:__VIZ_PROD__.ui.resolvedDataCache.size};}''')
   result['measurements'].append({'elements':count,'ready_ms':elapsed,**timing});ctx.close()
  b.close()
 (a.output/'performance.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
