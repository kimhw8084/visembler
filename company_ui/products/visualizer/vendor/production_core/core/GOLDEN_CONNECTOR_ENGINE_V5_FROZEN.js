/* Visualizer Golden Connector Engine v4
   Rendering invariant: route cleanly or fail closed; never emit malformed arrows.
   Dynamic rectilinear visibility graph + A* + semantic port zones + on-path labels. */
function g4Metrics(root){
  const rr=root.getBoundingClientRect();
  const lw=root.clientWidth||Number(root.getAttribute?.('width'))||rr.width||1;
  const lh=root.clientHeight||Number(root.getAttribute?.('height'))||rr.height||1;
  return {rr,lw,lh,sx:lw/(rr.width||lw||1),sy:lh/(rr.height||lh||1)};
}
function g4Rect(el,root){
  const m=g4Metrics(root),r=el.getBoundingClientRect();
  const left=(r.left-m.rr.left)*m.sx,top=(r.top-m.rr.top)*m.sy,right=(r.right-m.rr.left)*m.sx,bottom=(r.bottom-m.rr.top)*m.sy;
  return {left,top,right,bottom,width:right-left,height:bottom-top,cx:(left+right)/2,cy:(top+bottom)/2};
}
function g4Inflate(r,p){return{left:r.left-p,top:r.top-p,right:r.right+p,bottom:r.bottom+p,width:r.width+2*p,height:r.height+2*p,cx:r.cx,cy:r.cy}}
function g4Overlap(a,b,p=0){return!(a.right+p<=b.left||a.left-p>=b.right||a.bottom+p<=b.top||a.top-p>=b.bottom)}
function g4Inside(p,r,eps=.5){return p.x>r.left+eps&&p.x<r.right-eps&&p.y>r.top+eps&&p.y<r.bottom-eps}
function g4SegHitsRect(a,b,r,eps=.4){
  if(Math.abs(a.x-b.x)<.01){const x=a.x,y0=Math.min(a.y,b.y),y1=Math.max(a.y,b.y);return x>r.left+eps&&x<r.right-eps&&y1>r.top+eps&&y0<r.bottom-eps}
  if(Math.abs(a.y-b.y)<.01){const y=a.y,x0=Math.min(a.x,b.x),x1=Math.max(a.x,b.x);return y>r.top+eps&&y<r.bottom-eps&&x1>r.left+eps&&x0<r.right-eps}
  return true;
}
function g4Clear(a,b,obs){return !obs.some(r=>g4SegHitsRect(a,b,r))}
function g4Clean(P){
  const o=[];P.forEach(p=>{const q=o.at(-1);if(q&&Math.abs(q.x-p.x)<.01&&Math.abs(q.y-p.y)<.01)return;o.push({x:p.x,y:p.y})});
  let c=true;while(c&&o.length>2){c=false;for(let i=1;i<o.length-1;i++){const a=o[i-1],b=o[i],d=o[i+1];if((Math.abs(a.x-b.x)<.01&&Math.abs(b.x-d.x)<.01)||(Math.abs(a.y-b.y)<.01&&Math.abs(b.y-d.y)<.01)){o.splice(i,1);c=true;break}}}return o;
}
function g4Rounded(P,r=6){
  P=g4Clean(P);if(P.length<2)return'';let d=`M ${P[0].x} ${P[0].y}`;
  for(let i=1;i<P.length-1;i++){const a=P[i-1],p=P[i],b=P[i+1],l1=Math.abs(p.x-a.x)+Math.abs(p.y-a.y),l2=Math.abs(b.x-p.x)+Math.abs(b.y-p.y),rr=Math.min(r,l1*.28,l2*.28);let q1={x:p.x,y:p.y},q2={x:p.x,y:p.y};if(Math.abs(a.x-p.x)<.01)q1.y=p.y+(a.y<p.y?-rr:rr);else q1.x=p.x+(a.x<p.x?-rr:rr);if(Math.abs(b.x-p.x)<.01)q2.y=p.y+(b.y<p.y?-rr:rr);else q2.x=p.x+(b.x<p.x?-rr:rr);d+=` L ${q1.x} ${q1.y} Q ${p.x} ${p.y} ${q2.x} ${q2.y}`}
  const e=P.at(-1);return d+` L ${e.x} ${e.y}`;
}
function g4Port(r,side,f=.5){
  f=Math.max(.12,Math.min(.88,f));
  if(side==='left')return{x:r.left,y:r.top+r.height*f,side,dx:-1,dy:0};
  if(side==='right')return{x:r.right,y:r.top+r.height*f,side,dx:1,dy:0};
  if(side==='top')return{x:r.left+r.width*f,y:r.top,side,dx:0,dy:-1};
  return{x:r.left+r.width*f,y:r.bottom,side:'bottom',dx:0,dy:1};
}
function g4PortSet(r,sides,degree=1){
  const S=sides?.length?sides:['right','left','bottom','top'];const fs=degree>3?[.2,.4,.6,.8]:degree>1?[.32,.5,.68]:[.5],out=[];
  S.forEach(side=>fs.forEach(f=>out.push({...g4Port(r,side,f),f})));return out;
}
function g4Escape(p,d){return{x:p.x+p.dx*d,y:p.y+p.dy*d}}
function g4Unique(vals,min,max){return[...new Set(vals.map(v=>Math.round(Math.max(min,Math.min(max,v))*10)/10))].sort((a,b)=>a-b)}
function g4SegRelation(a,b,c,d){
  const ah=Math.abs(a.y-b.y)<.01,ch=Math.abs(c.y-d.y)<.01;
  if(ah&&ch&&Math.abs(a.y-c.y)<.01){const ov=Math.max(0,Math.min(Math.max(a.x,b.x),Math.max(c.x,d.x))-Math.max(Math.min(a.x,b.x),Math.min(c.x,d.x)));return ov>0?{cross:0,overlap:ov}:null}
  if(!ah&&!ch&&Math.abs(a.x-c.x)<.01){const ov=Math.max(0,Math.min(Math.max(a.y,b.y),Math.max(c.y,d.y))-Math.max(Math.min(a.y,b.y),Math.min(c.y,d.y)));return ov>0?{cross:0,overlap:ov}:null}
  if(ah&&!ch){const x=c.x,y=a.y;if(x>Math.min(a.x,b.x)&&x<Math.max(a.x,b.x)&&y>Math.min(c.y,d.y)&&y<Math.max(c.y,d.y))return{cross:1,overlap:0}}
  if(!ah&&ch){const x=a.x,y=c.y;if(x>Math.min(c.x,d.x)&&x<Math.max(c.x,d.x)&&y>Math.min(a.y,b.y)&&y<Math.max(a.y,b.y))return{cross:1,overlap:0}}
  return null;
}
function g4EdgeCost(a,b,existing=[]){let c=0;existing.forEach(s=>{const r=g4SegRelation(a,b,s.a,s.b);if(r)c+=r.cross*180+r.overlap*3});return c}
function g4GraphRoute(start,end,obs,W,H,existing=[],opts={}){
  const margin=opts.margin||8,clear=opts.channel||12,bend=opts.bendPenalty||34;
  const xs=[margin,W-margin,start.x,end.x],ys=[margin,H-margin,start.y,end.y];
  obs.forEach(r=>{xs.push(r.left-clear,r.right+clear);ys.push(r.top-clear,r.bottom+clear)});
  const X=g4Unique(xs,margin,W-margin),Y=g4Unique(ys,margin,H-margin),pts=[],index=new Map();
  function add(x,y){const p={x,y};if(obs.some(r=>g4Inside(p,r)))return;const k=x+'|'+y;if(!index.has(k)){index.set(k,pts.length);pts.push(p)}}
  X.forEach(x=>Y.forEach(y=>add(x,y)));add(start.x,start.y);add(end.x,end.y);
  const S=index.get(start.x+'|'+start.y),T=index.get(end.x+'|'+end.y);if(S==null||T==null)return null;
  const adj=Array.from({length:pts.length},()=>[]),byX={},byY={};pts.forEach((p,i)=>{(byX[p.x]??=[]).push(i);(byY[p.y]??=[]).push(i)});
  Object.values(byX).forEach(A=>{A.sort((i,j)=>pts[i].y-pts[j].y);for(let k=0;k<A.length-1;k++){const i=A[k],j=A[k+1];if(g4Clear(pts[i],pts[j],obs)){adj[i].push(j);adj[j].push(i)}}});
  Object.values(byY).forEach(A=>{A.sort((i,j)=>pts[i].x-pts[j].x);for(let k=0;k<A.length-1;k++){const i=A[k],j=A[k+1];if(g4Clear(pts[i],pts[j],obs)){adj[i].push(j);adj[j].push(i)}}});
  const dist=new Map(),prev=new Map(),open=[];function push(key,d,h){open.push({key,d,f:d+h});open.sort((a,b)=>a.f-b.f)}
  const sk=S+'|n';dist.set(sk,0);push(sk,0,Math.abs(pts[S].x-pts[T].x)+Math.abs(pts[S].y-pts[T].y));let goal=null;
  while(open.length){const cur=open.shift(),[is,dir]=cur.key.split('|'),i=+is;if(cur.d!==dist.get(cur.key))continue;if(i===T){goal=cur.key;break}for(const j of adj[i]){const a=pts[i],b=pts[j],nd=Math.abs(a.x-b.x)<.01?'v':'h',len=Math.abs(a.x-b.x)+Math.abs(a.y-b.y);let step=len+g4EdgeCost(a,b,existing);if(dir!=='n'&&dir!==nd)step+=bend;if(opts.prefer==='lr'&&b.x<a.x)step+=len*.9;if(opts.prefer==='tb'&&b.y<a.y)step+=len*.9;const nk=j+'|'+nd,nv=cur.d+step;if(nv<(dist.get(nk)??1e18)){dist.set(nk,nv);prev.set(nk,cur.key);push(nk,nv,Math.abs(b.x-pts[T].x)+Math.abs(b.y-pts[T].y))}}}
  if(!goal)return null;const ids=[];let k=goal;while(k){ids.push(+k.split('|')[0]);k=prev.get(k)}ids.reverse();return{points:g4Clean(ids.map(i=>pts[i])),score:dist.get(goal)};
}
function g4Perimeter(start,end,W,H){
  const m=6,C=[ [start,{x:W-m,y:start.y},{x:W-m,y:end.y},end], [start,{x:m,y:start.y},{x:m,y:end.y},end], [start,{x:start.x,y:m},{x:end.x,y:m},end], [start,{x:start.x,y:H-m},{x:end.x,y:H-m},end] ];
  C.sort((a,b)=>g4Manhattan(a)-g4Manhattan(b));return{points:g4Clean(C[0]),score:900000+g4Manhattan(C[0]),fallback:true};
}
function g4Manhattan(P){let n=0;for(let i=0;i<P.length-1;i++)n+=Math.abs(P[i].x-P[i+1].x)+Math.abs(P[i].y-P[i+1].y);return n}
function g4Route(source,target,root,obstacleEls=[],opts={},ctx={}){
  const m=g4Metrics(root),sr=g4Rect(source,root),tr=g4Rect(target,root),clear=opts.clearance||10,escape=opts.escape||clear+8;
  const allRects=obstacleEls.filter(Boolean).map(x=>g4Rect(x,root)),sourceSides=opts.sourceSides||null,targetSides=opts.targetSides||null;
  const sp=g4PortSet(sr,sourceSides,opts.sourceDegree||1),tp=g4PortSet(tr,targetSides,opts.targetDegree||1),existing=ctx.existing||[],used=ctx.usedPorts||new Map();let best=null;
  for(const s of sp)for(const t of tp){
    const directObs=allRects.filter(r=>!g4Overlap(r,sr,0)&&!g4Overlap(r,tr,0)).map(r=>g4Inflate(r,4));
    let micro=null;
    if(s.side==='right'&&t.side==='left'&&t.x>s.x+3){const mid=(s.x+t.x)/2,P=Math.abs(s.y-t.y)<1?[s,t]:[s,{x:mid,y:s.y},{x:mid,y:t.y},t];if(P.every((p,i)=>i===0||g4Clear(P[i-1],p,directObs)))micro=P}
    else if(s.side==='left'&&t.side==='right'&&s.x>t.x+3){const mid=(s.x+t.x)/2,P=Math.abs(s.y-t.y)<1?[s,t]:[s,{x:mid,y:s.y},{x:mid,y:t.y},t];if(P.every((p,i)=>i===0||g4Clear(P[i-1],p,directObs)))micro=P}
    else if(s.side==='bottom'&&t.side==='top'&&t.y>s.y+3){const mid=(s.y+t.y)/2,P=Math.abs(s.x-t.x)<1?[s,t]:[s,{x:s.x,y:mid},{x:t.x,y:mid},t];if(P.every((p,i)=>i===0||g4Clear(P[i-1],p,directObs)))micro=P}
    else if(s.side==='top'&&t.side==='bottom'&&s.y>t.y+3){const mid=(s.y+t.y)/2,P=Math.abs(s.x-t.x)<1?[s,t]:[s,{x:s.x,y:mid},{x:t.x,y:mid},t];if(P.every((p,i)=>i===0||g4Clear(P[i-1],p,directObs)))micro=P}
    if(micro){const sk=(opts.sourceKey||'s')+':'+s.side+':'+s.f,tk=(opts.targetKey||'t')+':'+t.side+':'+t.f,score=g4Manhattan(micro)-240+(used.get(sk)||0)*600+(used.get(tk)||0)*600;if(!best||score<best.score)best={score,points:g4Clean(micro),path:g4Rounded(micro,opts.radius||6),sourcePort:s,targetPort:t,sourceKey:sk,targetKey:tk,micro:true}}
    const se=g4Escape(s,escape),te=g4Escape(t,escape),obs=[g4Inflate(sr,clear),g4Inflate(tr,clear),...allRects.filter(r=>!g4Overlap(r,sr,0)&&!g4Overlap(r,tr,0)).map(r=>g4Inflate(r,clear))];
    if(se.x<4||se.y<4||se.x>m.lw-4||se.y>m.lh-4||te.x<4||te.y<4||te.x>m.lw-4||te.y>m.lh-4)continue;
    let q=g4GraphRoute(se,te,obs,m.lw,m.lh,existing,opts);if(!q)q=g4Perimeter(se,te,m.lw,m.lh);
    let score=q.score;const sk=(opts.sourceKey||'s')+':'+s.side+':'+s.f,tk=(opts.targetKey||'t')+':'+t.side+':'+t.f;score+=(used.get(sk)||0)*600+(used.get(tk)||0)*600;
    if(opts.prefer==='lr'&&s.side!=='right')score+=120;if(opts.prefer==='lr'&&t.side!=='left')score+=120;if(opts.prefer==='tb'&&s.side!=='bottom')score+=120;if(opts.prefer==='tb'&&t.side!=='top')score+=120;
    const P=g4Clean([s,se,...q.points,te,t]);if(!best||score<best.score)best={...q,score,points:P,path:g4Rounded(P,opts.radius||6),sourcePort:s,targetPort:t,sourceKey:sk,targetKey:tk};
  }
  if(!best)return{failed:true,path:'',points:[]};used.set(best.sourceKey,(used.get(best.sourceKey)||0)+1);used.set(best.targetKey,(used.get(best.targetKey)||0)+1);return best;
}
function g4Direct(source,target,root,sourceSide='right',targetSide='left',sf=.5,tf=.5){const a=g4Port(g4Rect(source,root),sourceSide,sf),b=g4Port(g4Rect(target,root),targetSide,tf);return{path:`M ${a.x} ${a.y} L ${b.x} ${b.y}`,points:[a,b]}}
function g4Curved(source,target,root,sourceSide='right',targetSide='left',sf=.5,tf=.5){const a=g4Port(g4Rect(source,root),sourceSide,sf),b=g4Port(g4Rect(target,root),targetSide,tf),d=Math.max(40,Math.min(115,Math.hypot(b.x-a.x,b.y-a.y)*.32)),c1={x:a.x+a.dx*d,y:a.y+a.dy*d},c2={x:b.x+b.dx*d,y:b.y+b.dy*d};return{path:`M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`,points:[a,b]}}
function g4Segments(P){const out=[];for(let i=0;i<P.length-1;i++)out.push({a:P[i],b:P[i+1]});return out}
function g4LabelOnPath(P,w,h,nodeRects,used=[]){
  const C=[];function scoreBox(cx,cy,base,leader=null){const box={left:cx-w/2,right:cx+w/2,top:cy-h/2,bottom:cy+h/2,cx,cy,score:base,leader};nodeRects.forEach(r=>{if(g4Overlap(box,r,5))box.score+=100000});used.forEach(r=>{if(g4Overlap(box,r,5))box.score+=100000});C.push(box)}
  for(let i=0;i<P.length-1;i++){const a=P[i],b=P[i+1],len=Math.abs(a.x-b.x)+Math.abs(a.y-b.y);if(len>=Math.max(w,h)+18)scoreBox((a.x+b.x)/2,(a.y+b.y)/2,-len)}
  if(!C.some(x=>x.score<50000)){const lens=[],total=g4Manhattan(P);let acc=0;for(let i=0;i<P.length-1;i++){const a=P[i],b=P[i+1],len=Math.abs(a.x-b.x)+Math.abs(a.y-b.y);lens.push({a,b,len,start:acc});acc+=len}for(const f of [.42,.5,.58]){const d=total*f,seg=lens.find(s=>d>=s.start&&d<=s.start+s.len)||lens.at(-1);if(!seg)continue;const q=(d-seg.start)/(seg.len||1),cx=seg.a.x+(seg.b.x-seg.a.x)*q,cy=seg.a.y+(seg.b.y-seg.a.y)*q;scoreBox(cx,cy,20)}}
  if(!C.some(x=>x.score<50000)){for(let i=0;i<P.length-1;i++){const a=P[i],b=P[i+1],len=Math.abs(a.x-b.x)+Math.abs(a.y-b.y);if(len<18)continue;const mx=(a.x+b.x)/2,my=(a.y+b.y)/2;if(Math.abs(a.y-b.y)<.01){for(const extra of [10,24,40,56])for(const dir of [-1,1]){const cy=my+dir*(h/2+extra),edgeY=cy-dir*h/2;scoreBox(mx,cy,80+extra,{x1:mx,y1:my,x2:mx,y2:edgeY})}}else if(Math.abs(a.x-b.x)<.01){for(const extra of [10,24,40,56])for(const dir of [-1,1]){const cx=mx+dir*(w/2+extra),edgeX=cx-dir*w/2;scoreBox(cx,my,90+extra,{x1:mx,y1:my,x2:edgeX,y2:my})}}}}
  C.sort((a,b)=>a.score-b.score);return C[0]&&C[0].score<50000?C[0]:null;
}
/* compatibility helpers for existing component logic */
function g3Metrics(r){return g4Metrics(r)}function g3Rect(e,r){return g4Rect(e,r)}function g3RectOverlap(a,b,p=0){return g4Overlap(a,b,p)}function g3SegHits(a,b,r,p=0){return g4SegHitsRect(a,b,g4Inflate(r,p))}
function g3Port(r,s,f=0){const frac=s==='left'||s==='right'?Math.max(.12,Math.min(.88,.5+f/(r.height||1))):Math.max(.12,Math.min(.88,.5+f/(r.width||1)));return g4Port(r,s,frac)}
function g3Clean(P){return g4Clean(P)}function g3Rounded(P,r=6){return g4Rounded(P,r)}function g3PathScore(P,obs){let h=0;for(let i=0;i<P.length-1;i++)obs.forEach(r=>{if(g4SegHitsRect(P[i],P[i+1],g4Inflate(r,7)))h++});return h*1000000+g4Manhattan(P)}
function g3ForcedOrthogonal(source,target,root,obstacleEls=[],sourceSide='right',targetSide='left',opts={}){return g4Route(source,target,root,obstacleEls,{sourceSides:[sourceSide],targetSides:[targetSide],clearance:opts.clearance||8,escape:opts.escape||18,radius:opts.radius||6,prefer:sourceSide==='right'&&targetSide==='left'?'lr':sourceSide==='bottom'&&targetSide==='top'?'tb':null},{existing:opts.existing||[],usedPorts:opts.usedPorts||new Map(),sourceKey:opts.sourceKey,targetKey:opts.targetKey})}
function g3Direct(source,target,root,sourceSide='right',targetSide='left'){return g4Direct(source,target,root,sourceSide,targetSide)}function g3Curved(source,target,root,sourceSide='right',targetSide='left'){return g4Curved(source,target,root,sourceSide,targetSide)}function g3LabelPlace(P,w,h,nodes,used=[]){return g4LabelOnPath(P,w,h,nodes,used)}


/* =========================
   Golden Connector Engine v5
   Layer-safe + hard-obstacle + terminal-safe rendering.
   ========================= */
function g5Unit(a,b){const dx=b.x-a.x,dy=b.y-a.y,l=Math.hypot(dx,dy)||1;return{x:dx/l,y:dy/l}}
function g5ArrowGeometry(P,size=8,half=4.5){
  P=g4Clean(P);if(P.length<2)return null;const e=P.at(-1),p=P.at(-2),u=g5Unit(p,e),base={x:e.x-u.x*size,y:e.y-u.y*size},perp={x:-u.y,y:u.x};
  return{tip:e,base,left:{x:base.x+perp.x*half,y:base.y+perp.y*half},right:{x:base.x-perp.x*half,y:base.y-perp.y*half},linePoints:g4Clean([...P.slice(0,-1),base])};
}
function g5PaintEdge(route,cls='edge',color='var(--accent)',opts={}){
  if(!route||route.failed||!route.points||route.points.length<2)return'';const a=g5ArrowGeometry(route.points,opts.arrowSize||8,opts.arrowHalf||4.5);if(!a)return'';
  const line=g4Rounded(a.linePoints,opts.radius??6),halo=opts.halo!==false?`<path d="${line}" class="${opts.haloClass||'edge-halo'}"/>`:'';
  return `${halo}<path d="${line}" class="${cls}"/><polygon points="${a.tip.x},${a.tip.y} ${a.left.x},${a.left.y} ${a.right.x},${a.right.y}" fill="${color}" class="g5-arrowhead"/>`;
}
function g5DirectionValid(route){
  if(!route||!route.points||route.points.length<2)return false;const P=g4Clean(route.points),a=P[0],b=P[1],c=P.at(-2),d=P.at(-1);
  if(route.sourcePort){const vx=b.x-a.x,vy=b.y-a.y;if(vx*route.sourcePort.dx+vy*route.sourcePort.dy<-0.01)return false}
  if(route.targetPort){const vx=d.x-c.x,vy=d.y-c.y;if(vx*route.targetPort.dx+vy*route.targetPort.dy>0.01)return false}
  return true;
}
function g5ObstacleValid(route,source,target,root,obstacleEls=[],clear=5){
  if(!route||route.failed||!route.points)return false;const sr=g4Rect(source,root),tr=g4Rect(target,root),obs=obstacleEls.filter(Boolean).map(x=>g4Rect(x,root)).filter(r=>!g4Overlap(r,sr,0)&&!g4Overlap(r,tr,0)).map(r=>g4Inflate(r,clear));
  const P=g4Clean(route.points);for(let i=0;i<P.length-1;i++)for(const r of obs)if(g4SegHitsRect(P[i],P[i+1],r))return false;return true;
}
function g5CommitPorts(route,used){if(!used||!route)return;if(route.sourceKey)used.set(route.sourceKey,(used.get(route.sourceKey)||0)+1);if(route.targetKey)used.set(route.targetKey,(used.get(route.targetKey)||0)+1)}
function g5SafeRoute(source,target,root,obstacleEls=[],opts={},ctx={}){
  const attempts=[0,4,8,12];for(const extra of attempts){const temp=new Map(ctx.usedPorts||[]);const r=g4Route(source,target,root,obstacleEls,{...opts,clearance:(opts.clearance||10)+extra,escape:(opts.escape||18)+Math.ceil(extra*.8)},{...ctx,usedPorts:temp});
    if(r&&!r.failed&&g5DirectionValid(r)&&g5ObstacleValid(r,source,target,root,obstacleEls,Math.max(3,(opts.clearance||10)-3))){g5CommitPorts(r,ctx.usedPorts);return r}}
  return{failed:true,path:'',points:[],reason:'no_valid_route'};
}
function g5MonotoneLR(source,target,root,obstacleEls=[],opts={},ctx={}){
  const sr=g4Rect(source,root),tr=g4Rect(target,root),clear=opts.clearance||10,escape=opts.escape||18,all=obstacleEls.filter(Boolean),obsRects=all.map(x=>g4Rect(x,root)).filter(r=>!g4Overlap(r,sr,0)&&!g4Overlap(r,tr,0)).map(r=>g4Inflate(r,clear));
  const fs=(opts.sourceDegree||1)>1?[.32,.5,.68]:[.5],ft=(opts.targetDegree||1)>1?[.32,.5,.68]:[.5],existing=ctx.existing||[];let best=null;
  for(const sf of fs)for(const tf of ft){const s=g4Port(sr,'right',sf),t=g4Port(tr,'left',tf),se=g4Escape(s,escape),te=g4Escape(t,escape);if(te.x<se.x+2)continue;
    const xs=[(se.x+te.x)/2,se.x+8,te.x-8];obsRects.forEach(r=>{if(r.right>se.x&&r.right<te.x)xs.push(r.right+8);if(r.left>se.x&&r.left<te.x)xs.push(r.left-8)});
    for(const x of xs){if(x<se.x-0.1||x>te.x+0.1)continue;const P=g4Clean([s,se,{x,y:se.y},{x,y:te.y},te,t]);let bad=false;for(let i=0;i<P.length-1;i++)for(const r of obsRects)if(g4SegHitsRect(P[i],P[i+1],r)){bad=true;break}if(bad)continue;
      let score=g4Manhattan(P);for(let i=0;i<P.length-1;i++)score+=g4EdgeCost(P[i],P[i+1],existing);const r={points:P,path:g4Rounded(P,opts.radius||6),score,sourcePort:s,targetPort:t,sourceKey:(opts.sourceKey||'s')+':right:'+sf,targetKey:(opts.targetKey||'t')+':left:'+tf,monotone:true};if(!best||score<best.score)best=r;
    }
  }
  if(best){g5CommitPorts(best,ctx.usedPorts);return best}
  const r=g5SafeRoute(source,target,root,obstacleEls,{...opts,sourceSides:['right'],targetSides:['left'],prefer:'lr'},ctx);if(r.failed)return r;
  const P=g4Clean(r.points);for(let i=0;i<P.length-1;i++)if(P[i+1].x<P[i].x-0.1)return{failed:true,path:'',points:[],reason:'lr_backtrack'};return r;
}
function g5RouteHitsNodes(route,nodeRects,excludeRects=[]){
  if(!route||route.failed)return 1;let hits=0;const P=g4Clean(route.points);for(let i=0;i<P.length-1;i++)nodeRects.forEach(r=>{if(excludeRects.some(x=>g4Overlap(r,x,0)))return;if(g4SegHitsRect(P[i],P[i+1],g4Inflate(r,3)))hits++});return hits;
}

function g5LabelOnPath(P,w,h,nodeRects,used=[],bounds=null){
  let p=g4LabelOnPath(P,w,h,nodeRects,used);if(p)return p;const segs=[];for(let i=0;i<P.length-1;i++){const a=P[i],b=P[i+1],len=Math.abs(a.x-b.x)+Math.abs(a.y-b.y);if(len>12)segs.push({a,b,len})}segs.sort((a,b)=>b.len-a.len);
  const C=[];function add(cx,cy,base,leader){const box={left:cx-w/2,right:cx+w/2,top:cy-h/2,bottom:cy+h/2,cx,cy,score:base,leader};if(bounds&&(box.left<bounds.left||box.right>bounds.right||box.top<bounds.top||box.bottom>bounds.bottom))box.score+=100000;nodeRects.forEach(r=>{if(g4Overlap(box,r,5))box.score+=100000});used.forEach(r=>{if(g4Overlap(box,r,5))box.score+=100000});C.push(box)}
  for(const s of segs.slice(0,4)){const mx=(s.a.x+s.b.x)/2,my=(s.a.y+s.b.y)/2,horiz=Math.abs(s.a.y-s.b.y)<.01;for(const off of [72,92,116,142])for(const dir of [-1,1]){if(horiz){const cy=my+dir*(h/2+off),edgeY=cy-dir*h/2;add(mx,cy,off,{x1:mx,y1:my,x2:mx,y2:edgeY})}else{const cx=mx+dir*(w/2+off),edgeX=cx-dir*w/2;add(cx,my,off,{x1:mx,y1:my,x2:edgeX,y2:my})}}}
  C.sort((a,b)=>a.score-b.score);return C[0]&&C[0].score<50000?C[0]:null;
}
