import {
  NumericalContractError, histogram, boxPlot, ecdf, kde, linearRegression,
  normalizeStackedSeries, stepSeries,
} from './statistics_engine.mjs';

export const ADVANCED_CHART_TYPES = Object.freeze([
  'histogram','box','violin','ecdf','regression','bubble','stacked100','stackedArea','step','treemap','funnel','sankey',
]);

const CHART_EPS=1e-12;
const esc=(v)=>String(v??'').replace(/[&<>"']/g,(m)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const chartFinite=(v)=>typeof v==='number'&&Number.isFinite(v);
const chartClamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function chartFail(code,message,details={}){throw new NumericalContractError(code,message,details);}
function nums(values,name,min=1){if(!Array.isArray(values)||values.length<min)chartFail('CHART_DATA',`${name} requires at least ${min} values.`);return values.map((v,i)=>{const n=Number(v);if(!chartFinite(n))chartFail('CHART_DATA',`${name}[${i}] must be chartFinite.`);return n;});}
function extent(values,{zero=false,pad=.06}={}){const a=nums(values,'extent');let lo=Math.min(...a),hi=Math.max(...a);if(zero){lo=Math.min(0,lo);hi=Math.max(0,hi);}if(Math.abs(hi-lo)<=CHART_EPS){const d=Math.max(Math.abs(lo)*.05,1);lo-=d;hi+=d;}const p=(hi-lo)*pad;return[lo-p,hi+p];}
function scale(v,a,b,c,d){return c+(v-a)/(b-a)*(d-c);}
function path(points){return points.map((p,i)=>`${i?'L':'M'} ${p[0].toFixed(3)} ${p[1].toFixed(3)}`).join(' ');}
function commonSvg(type,width,height,title,body,desc=''){
  const W=Math.max(220,Number(width)||600),H=Math.max(140,Number(height)||350);
  return `<svg class="viz-advanced-chart" data-chart-type="${esc(type)}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title||type)}"><title>${esc(title||type)}</title>${desc?`<desc>${esc(desc)}</desc>`:''}${body}</svg>`;
}
function grid(W,H,m,xTicks=0,yTicks=4){let s='';if(yTicks>0){for(let i=0;i<=yTicks;i++){const y=m.t+(H-m.t-m.b)*i/yTicks;s+=`<line class="viz-grid" x1="${m.l}" y1="${y}" x2="${W-m.r}" y2="${y}"/>`;}}if(xTicks>0){for(let i=0;i<=xTicks;i++){const x=m.l+(W-m.l-m.r)*i/xTicks;s+=`<line class="viz-grid" x1="${x}" y1="${m.t}" x2="${x}" y2="${H-m.b}"/>`;}}return s;}

export function prepareAdvancedChart(type,input={},options={}){
  if(!ADVANCED_CHART_TYPES.includes(type))chartFail('CHART_TYPE',`Unsupported advanced chart type: ${type}`,{type});
  if(type==='histogram')return{type,stats:histogram(nums(input.values,'values',2),{bins:options.bins??'fd'}),title:options.title||'Histogram'};
  if(type==='box')return{type,stats:boxPlot(nums(input.values,'values',2),{whisker:options.whisker??1.5}),values:nums(input.values,'values',2),title:options.title||'Box Plot'};
  if(type==='violin')return{type,kde:kde(nums(input.values,'values',2),{points:options.points??96,bandwidth:options.bandwidth??null}),box:boxPlot(nums(input.values,'values',2)),title:options.title||'Violin Plot'};
  if(type==='ecdf')return{type,stats:ecdf(nums(input.values,'values',1)),title:options.title||'ECDF'};
  if(type==='regression'){
    const x=nums(input.x,'x',3),y=nums(input.y,'y',3);if(x.length!==y.length)chartFail('PAIR_LENGTH','Regression x/y lengths must match.');
    return{type,x,y,fit:linearRegression(x,y,{confidence:options.confidence??.95}),title:options.title||'Regression Scatter'};
  }
  if(type==='bubble'){
    const x=nums(input.x,'x',1),y=nums(input.y,'y',1),size=nums(input.size,'size',1);if(x.length!==y.length||x.length!==size.length)chartFail('PAIR_LENGTH','Bubble x/y/size lengths must match.');if(size.some(v=>v<0))chartFail('BUBBLE_SIZE','Bubble sizes must be non-negative.');
    const labels=Array.isArray(input.labels)&&input.labels.length===x.length?input.labels.map(String):x.map((_,i)=>`Point ${i+1}`);
    return{type,x,y,size,labels,title:options.title||'Bubble Plot'};
  }
  if(type==='stacked100'||type==='stackedArea'){
    const normalized=normalizeStackedSeries(input.categories,input.series,{percent:type==='stacked100'});
    return{type,...normalized,title:options.title||(type==='stacked100'?'100% Stacked Bar':'Stacked Area')};
  }
  if(type==='step')return{type,...stepSeries(input.x,input.y,{where:options.where??'post'}),x:nums(input.x,'x',2),y:nums(input.y,'y',2),title:options.title||'Step Chart'};
  if(type==='treemap'){
    if(!Array.isArray(input.nodes)||!input.nodes.length)chartFail('TREEMAP_DATA','Treemap requires nodes.');
    const nodes=input.nodes.map((n,i)=>{const value=Number(n.value);if(!n||n.id==null||!chartFinite(value)||value<0)chartFail('TREEMAP_DATA','Treemap nodes require id and non-negative chartFinite value.',{index:i});return{id:String(n.id),label:String(n.label??n.id),value};});
    if(nodes.reduce((s,n)=>s+n.value,0)<=CHART_EPS)chartFail('TREEMAP_TOTAL','Treemap requires positive total value.');
    return{type,nodes,title:options.title||'Treemap'};
  }
  if(type==='funnel'){
    const stages=Array.isArray(input.stages)?input.stages.map(String):[];const values=nums(input.values,'values',2);if(stages.length!==values.length)chartFail('FUNNEL_DATA','Funnel stages/values lengths must match.');if(values.some(v=>v<0))chartFail('FUNNEL_VALUE','Funnel values must be non-negative.');
    return{type,stages,values,title:options.title||'Funnel'};
  }
  if(type==='sankey'){
    if(!Array.isArray(input.nodes)||!input.nodes.length||!Array.isArray(input.links)||!input.links.length)chartFail('SANKEY_DATA','Sankey requires non-empty nodes and links.');
    const nodes=input.nodes.map((n,i)=>{if(!n||n.id==null)chartFail('SANKEY_NODE','Sankey node requires id.',{index:i});return{id:String(n.id),label:String(n.label??n.id)};});
    const ids=new Set(nodes.map(n=>n.id));if(ids.size!==nodes.length)chartFail('SANKEY_NODE','Sankey node ids must be unique.');
    const links=input.links.map((l,i)=>{const source=String(l.source),target=String(l.target),value=Number(l.value);if(!ids.has(source)||!ids.has(target)||!chartFinite(value)||value<=0||source===target)chartFail('SANKEY_LINK','Sankey links require distinct known source/target and value > 0.',{index:i});return{source,target,value};});
    validateDag(nodes,links);
    return{type,nodes,links,title:options.title||'Sankey'};
  }
  chartFail('CHART_TYPE','Unreachable chart type.');
}

function validateDag(nodes,links){
  const out=new Map(nodes.map(n=>[n.id,[]]));links.forEach(l=>out.get(l.source).push(l.target));const visiting=new Set(),done=new Set();
  function dfs(id){if(visiting.has(id))chartFail('SANKEY_CYCLE','Sankey requires an acyclic flow graph.',{node:id});if(done.has(id))return;visiting.add(id);for(const n of out.get(id))dfs(n);visiting.delete(id);done.add(id);}nodes.forEach(n=>dfs(n.id));
}

function binaryTreemap(nodes,x,y,w,h){
  if(!nodes.length)return[];if(nodes.length===1)return[{...nodes[0],x,y,w,h}];
  const total=nodes.reduce((s,n)=>s+n.value,0);let acc=0,best=1,diff=Infinity;
  for(let i=1;i<nodes.length;i++){acc+=nodes[i-1].value;const d=Math.abs(acc-total/2);if(d<diff){diff=d;best=i;}}
  const A=nodes.slice(0,best),B=nodes.slice(best),ta=A.reduce((s,n)=>s+n.value,0),r=total<=CHART_EPS?.5:ta/total;
  if(w>=h){const w1=w*r;return binaryTreemap(A,x,y,w1,h).concat(binaryTreemap(B,x+w1,y,w-w1,h));}
  const h1=h*r;return binaryTreemap(A,x,y,w,h1).concat(binaryTreemap(B,x,y+h1,w,h-h1));
}

function sankeyLayout(plan,W,H,m){
  const incoming=new Map(plan.nodes.map(n=>[n.id,[]])),outgoing=new Map(plan.nodes.map(n=>[n.id,[]]));plan.links.forEach((l,i)=>{incoming.get(l.target).push({...l,i});outgoing.get(l.source).push({...l,i});});
  const depth=new Map();function dep(id){if(depth.has(id))return depth.get(id);const ins=incoming.get(id);const d=!ins.length?0:Math.max(...ins.map(l=>dep(l.source)+1));depth.set(id,d);return d;}plan.nodes.forEach(n=>dep(n.id));
  const maxDepth=Math.max(...depth.values(),1),cols=Array.from({length:maxDepth+1},()=>[]);plan.nodes.forEach(n=>cols[depth.get(n.id)].push(n));
  const nodeValue=new Map(plan.nodes.map(n=>[n.id,Math.max(incoming.get(n.id).reduce((s,l)=>s+l.value,0),outgoing.get(n.id).reduce((s,l)=>s+l.value,0),CHART_EPS)]));
  const nodeW=Math.max(10,Math.min(18,(W-m.l-m.r)/(maxDepth+1)*.12));const layout=new Map();
  cols.forEach((col,ci)=>{const gap=12,total=col.reduce((s,n)=>s+nodeValue.get(n.id),0),usable=H-m.t-m.b-gap*Math.max(0,col.length-1);let y=m.t;col.sort((a,b)=>b.label.localeCompare(a.label));for(const n of col){const h=Math.max(18,usable*nodeValue.get(n.id)/total);const x=m.l+(W-m.l-m.r-nodeW)*ci/maxDepth;layout.set(n.id,{x,y,w:nodeW,h,node:n});y+=h+gap;}});
  const outOffset=new Map(plan.nodes.map(n=>[n.id,0])),inOffset=new Map(plan.nodes.map(n=>[n.id,0]));const maxFlow=Math.max(...plan.links.map(l=>l.value));
  const links=plan.links.map((l,i)=>{const a=layout.get(l.source),b=layout.get(l.target),sw=Math.max(2,Math.min(24,l.value/maxFlow*20));const y1=a.y+a.h*(outOffset.get(l.source)+l.value/2)/nodeValue.get(l.source);const y2=b.y+b.h*(inOffset.get(l.target)+l.value/2)/nodeValue.get(l.target);outOffset.set(l.source,outOffset.get(l.source)+l.value);inOffset.set(l.target,inOffset.get(l.target)+l.value);const x1=a.x+a.w,x2=b.x,c1=x1+(x2-x1)*.42,c2=x1+(x2-x1)*.58;return{...l,i,sw,path:`M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`};});
  return{nodes:[...layout.values()],links};
}

export function renderAdvancedChartSvg(plan,{width=600,height=350,title=null}={}){
  if(!plan||!ADVANCED_CHART_TYPES.includes(plan.type))chartFail('CHART_PLAN','A prepared advanced chart plan is required.');
  const W=Math.max(220,Number(width)||600),H=Math.max(140,Number(height)||350),m={l:46,r:20,t:22,b:38},pw=W-m.l-m.r,ph=H-m.t-m.b;
  let body='';
  if(plan.type==='histogram'){
    const max=Math.max(...plan.stats.counts,1);body+=grid(W,H,m,0,4);plan.stats.counts.forEach((c,i)=>{const x=m.l+pw*i/plan.stats.counts.length+1,w=Math.max(1,pw/plan.stats.counts.length-2),h=ph*c/max,y=m.t+ph-h;body+=`<rect class="viz-mark viz-series-0" x="${x}" y="${y}" width="${w}" height="${h}" rx="3"><title>${esc(`${plan.stats.edges[i].toFixed(2)}–${plan.stats.edges[i+1].toFixed(2)}: ${c}`)}</title></rect>`;});
  } else if(plan.type==='box'){
    const ex=extent(plan.values,{pad:.08}),sx=(v)=>scale(v,ex[0],ex[1],m.l,W-m.r),cy=m.t+ph/2,bh=Math.min(80,ph*.45);body+=grid(W,H,m,5,0);body+=`<line class="viz-axis-strong" x1="${sx(plan.stats.lowerWhisker)}" y1="${cy}" x2="${sx(plan.stats.upperWhisker)}" y2="${cy}"/><rect class="viz-box" x="${sx(plan.stats.q1)}" y="${cy-bh/2}" width="${Math.max(1,sx(plan.stats.q3)-sx(plan.stats.q1))}" height="${bh}" rx="6"/><line class="viz-axis-strong" x1="${sx(plan.stats.median)}" y1="${cy-bh/2}" x2="${sx(plan.stats.median)}" y2="${cy+bh/2}"/>`+plan.stats.outliers.map(v=>`<circle class="viz-mark viz-series-1" cx="${sx(v)}" cy="${cy}" r="5"><title>Outlier ${v}</title></circle>`).join('');
  } else if(plan.type==='violin'){
    const ys=plan.kde.x,ds=plan.kde.density,maxD=Math.max(...ds,CHART_EPS),ey=[Math.min(...ys),Math.max(...ys)],sy=(v)=>scale(v,ey[0],ey[1],H-m.b,m.t),cx=m.l+pw/2,half=pw*.34;const left=ys.map((v,i)=>[cx-ds[i]/maxD*half,sy(v)]),right=ys.slice().reverse().map((v,ri)=>{const i=ys.length-1-ri;return[cx+ds[i]/maxD*half,sy(v)]});body+=grid(W,H,m,0,4)+`<path class="viz-area viz-series-0" d="${path(left)} ${right.map(p=>`L ${p[0].toFixed(3)} ${p[1].toFixed(3)}`).join(' ')} Z"/><line class="viz-axis-strong" x1="${cx-half*.1}" y1="${sy(plan.box.median)}" x2="${cx+half*.1}" y2="${sy(plan.box.median)}"/>`;
  } else if(plan.type==='ecdf'){
    const pts=plan.stats.points,ex=extent(pts.map(p=>p.x),{pad:.03}),sx=(v)=>scale(v,ex[0],ex[1],m.l,W-m.r),sy=(v)=>scale(v,0,1,H-m.b,m.t);body+=grid(W,H,m,4,4);let d=`M ${sx(pts[0].x)} ${sy(0)}`;let prev=0;for(const p of pts){d+=` L ${sx(p.x)} ${sy(prev)} L ${sx(p.x)} ${sy(p.p)}`;prev=p.p;}body+=`<path class="viz-line viz-series-0" d="${d}"/>`;
  } else if(plan.type==='regression'){
    const ex=extent(plan.x,{pad:.08}),ey=extent(plan.y,{pad:.08}),sx=(v)=>scale(v,ex[0],ex[1],m.l,W-m.r),sy=(v)=>scale(v,ey[0],ey[1],H-m.b,m.t);body+=grid(W,H,m,5,4)+plan.x.map((v,i)=>`<circle class="viz-mark viz-series-1" cx="${sx(v)}" cy="${sy(plan.y[i])}" r="4"><title>${esc(`${v}, ${plan.y[i]}`)}</title></circle>`).join('');const x0=Math.min(...plan.x),x1=Math.max(...plan.x),y0=plan.fit.interceptValue+plan.fit.slope*x0,y1=plan.fit.interceptValue+plan.fit.slope*x1;body+=`<path class="viz-line viz-series-0" d="M ${sx(x0)} ${sy(y0)} L ${sx(x1)} ${sy(y1)}"/><text class="viz-label" x="${m.l+6}" y="${m.t+16}">R² ${plan.fit.r2.toFixed(3)}</text>`;
  } else if(plan.type==='bubble'){
    const ex=extent(plan.x,{pad:.08}),ey=extent(plan.y,{pad:.08}),maxS=Math.max(...plan.size,CHART_EPS),sx=(v)=>scale(v,ex[0],ex[1],m.l,W-m.r),sy=(v)=>scale(v,ey[0],ey[1],H-m.b,m.t);body+=grid(W,H,m,5,4)+plan.x.map((v,i)=>`<circle class="viz-bubble viz-series-${i%3}" cx="${sx(v)}" cy="${sy(plan.y[i])}" r="${4+Math.sqrt(plan.size[i]/maxS)*18}"><title>${esc(`${plan.labels[i]}: x ${v}, y ${plan.y[i]}, size ${plan.size[i]}`)}</title></circle>`).join('');
  } else if(plan.type==='stacked100'){
    const n=plan.categories.length,gw=pw/n;body+=grid(W,H,m,0,4);for(let i=0;i<n;i++){let acc=0;plan.series.forEach((s,si)=>{const v=s.values[i],h=ph*v/100,y=H-m.b-(acc+v)/100*ph;body+=`<rect class="viz-mark viz-series-${si%3}" x="${m.l+i*gw+2}" y="${y}" width="${Math.max(1,gw-4)}" height="${h}"><title>${esc(`${plan.categories[i]} · ${s.name}: ${v.toFixed(1)}%`)}</title></rect>`;acc+=v;});body+=`<text class="viz-label" x="${m.l+i*gw+gw/2}" y="${H-m.b+18}" text-anchor="middle">${esc(plan.categories[i])}</text>`;}
  } else if(plan.type==='stackedArea'){
    const n=plan.categories.length,totals=plan.totals,max=Math.max(...totals,CHART_EPS),sx=(i)=>m.l+pw*i/Math.max(1,n-1),sy=(v)=>H-m.b-v/max*ph;let lower=Array(n).fill(0);body+=grid(W,H,m,0,4);plan.series.forEach((s,si)=>{const upper=s.values.map((v,i)=>lower[i]+v),top=upper.map((v,i)=>[sx(i),sy(v)]),bottom=lower.map((v,i)=>[sx(i),sy(v)]).reverse();body+=`<path class="viz-area viz-series-${si%3}" d="${path(top)} ${bottom.map(p=>`L ${p[0]} ${p[1]}`).join(' ')} Z"><title>${esc(s.name)}</title></path>`;lower=upper;});
  } else if(plan.type==='step'){
    const ex=extent(plan.x,{pad:.04}),ey=extent(plan.y,{pad:.08}),sx=(v)=>scale(v,ex[0],ex[1],m.l,W-m.r),sy=(v)=>scale(v,ey[0],ey[1],H-m.b,m.t);body+=grid(W,H,m,5,4)+`<path class="viz-line viz-series-0" d="${path(plan.points.map(p=>[sx(p.x),sy(p.y)]))}"/>`;
  } else if(plan.type==='treemap'){
    const rects=binaryTreemap([...plan.nodes].sort((a,b)=>b.value-a.value||a.id.localeCompare(b.id)),m.l,m.t,pw,ph);body+=rects.map((r,i)=>`<g class="viz-treemap-node"><rect class="viz-mark viz-series-${i%3}" x="${r.x+1}" y="${r.y+1}" width="${Math.max(1,r.w-2)}" height="${Math.max(1,r.h-2)}" rx="5"><title>${esc(`${r.label}: ${r.value}`)}</title></rect>${r.w>65&&r.h>34?`<text class="viz-label viz-label-invert" x="${r.x+8}" y="${r.y+18}">${esc(r.label)}</text>`:''}</g>`).join('');
  } else if(plan.type==='funnel'){
    const max=Math.max(...plan.values,CHART_EPS),stepH=ph/plan.values.length,cx=m.l+pw/2;for(let i=0;i<plan.values.length;i++){const w1=pw*plan.values[i]/max,w2=pw*(plan.values[i+1]??plan.values[i])/max*.96,y=m.t+i*stepH;const pts=[[cx-w1/2,y+2],[cx+w1/2,y+2],[cx+w2/2,y+stepH-2],[cx-w2/2,y+stepH-2]];body+=`<polygon class="viz-mark viz-series-${i%3}" points="${pts.map(p=>p.join(',')).join(' ')}"><title>${esc(`${plan.stages[i]}: ${plan.values[i]}`)}</title></polygon><text class="viz-label viz-label-invert" x="${cx}" y="${y+stepH/2+4}" text-anchor="middle">${esc(plan.stages[i])} · ${plan.values[i]}</text>`;}
  } else if(plan.type==='sankey'){
    const l=sankeyLayout(plan,W,H,m);body+=l.links.map((x,i)=>`<path class="viz-sankey-link viz-series-${i%3}" d="${x.path}" style="stroke-width:${x.sw}"><title>${esc(`${x.source} → ${x.target}: ${x.value}`)}</title></path>`).join('')+l.nodes.map((x,i)=>`<g><rect class="viz-sankey-node viz-series-${i%3}" x="${x.x}" y="${x.y}" width="${x.w}" height="${x.h}" rx="3"><title>${esc(x.node.label)}</title></rect><text class="viz-label" x="${x.x+(x.x<W/2?x.w+5:-5)}" y="${x.y+Math.min(x.h-4,16)}" text-anchor="${x.x<W/2?'start':'end'}">${esc(x.node.label)}</text></g>`).join('');
  }
  return commonSvg(plan.type,W,H,title||plan.title,body,`${plan.type} generated by Visualizer advanced chart engine`);
}
