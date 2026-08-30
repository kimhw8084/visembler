#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, statistics, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROD=Path(__file__).resolve().parents[1]
QA=PROD/'qa'
CONNECTOR=PROD/'core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
EXPECTED='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
sha=hashlib.sha256(CONNECTOR.read_bytes()).hexdigest()
html='''<!doctype html><html><head><style>
html,body{margin:0;background:#fff}#root{position:relative;width:1900px;height:1300px}.node{position:absolute;width:120px;height:64px;border:1px solid #999;border-radius:8px;background:white}
</style></head><body><div id="root"></div><script>__CONNECTOR__</script><script>
const root=document.getElementById('root');
const nodes=[];
for(let r=0;r<10;r++)for(let c=0;c<10;c++){const n=document.createElement('div');n.className='node';n.dataset.i=String(r*10+c);n.style.left=(35+c*180)+'px';n.style.top=(35+r*120)+'px';root.appendChild(n);nodes.push(n);}
const edges=[];for(let r=0;r<10;r++)for(let c=0;c<9;c++)edges.push([r*10+c,r*10+c+1]);
function snapshotNodes(){return nodes.map(n=>{const r=n.getBoundingClientRect();return {getBoundingClientRect:()=>r};});}
function runRoutes(validate=false){
  const proxies=snapshotNodes(),used=new Map(),existing=[];let failed=0,hits=0,arrows=0;
  const rects=validate?proxies.map(n=>g4Rect(n,root)):null;
  for(let i=0;i<edges.length;i++){
    const [a,b]=edges[i],s=proxies[a],t=proxies[b],obs=proxies.filter((_,j)=>j!==a&&j!==b);
    const route=g5MonotoneLR(s,t,root,obs,{clearance:8,escape:14,sourceKey:'s'+a,targetKey:'t'+b,sourceDegree:2,targetDegree:2},{usedPorts:used,existing});
    if(route.failed){failed++;continue}
    if(validate)hits+=g5RouteHitsNodes(route,rects,[rects[a],rects[b]]);
    const painted=g5PaintEdge(route,'edge','#333');if(painted.includes('g5-arrowhead'))arrows++;
    existing.push(...g4Segments(route.points));
  }
  return {failed,hits,arrows};
}
window.__runRoutes=runRoutes;
</script></body></html>'''.replace('__CONNECTOR__',CONNECTOR.read_text())

def pct(vals,q):
    vals=sorted(vals);return vals[min(len(vals)-1,max(0,round((len(vals)-1)*q)))] if vals else 0

report={'pass':False,'connector_sha256':sha,'authority_identical':sha==EXPECTED,'nodes':100,'edges':90,'budget':{'full_reroute_p95_ms':150.0}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium')
    page=browser.new_page(viewport={'width':1900,'height':1300})
    errors=[];page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None);page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load');page.wait_for_timeout(80)
    for _ in range(3): page.evaluate('window.__runRoutes(false)')
    times=[]
    for _ in range(30):
        out=page.evaluate("""() => {const t0=performance.now();window.__runRoutes(false);return performance.now()-t0;}""")
        times.append(out)
    validated=page.evaluate('window.__runRoutes(true)')
    report['route_result']=validated
    report['timing']={'runs':len(times),'mean_ms':statistics.fmean(times),'median_ms':statistics.median(times),'p95_ms':pct(times,.95),'max_ms':max(times)}
    report['console_errors']=errors
    report['pass']=sha==EXPECTED and not errors and validated['failed']==0 and validated['hits']==0 and validated['arrows']==90 and report['timing']['p95_ms']<=report['budget']['full_reroute_p95_ms']
    browser.close()
(QA/'diagram_connector_benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['pass'] else 1)
