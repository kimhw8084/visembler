import {
  NumericalContractError, westernElectricRules, individualsMovingRange, xbarR, cusum, ewma,
  doeMainEffects, doeInteraction, fitResponseSurface, residualDiagnostics, linearModel,
  meanConfidenceInterval,
} from './statistics_engine.mjs';

/** Renderer-independent EngineeringChartEngine plans + deterministic SVG renderer. */
export const ENGINEERING_CHART_TYPES = Object.freeze([
  'spc','imr','xbarr','cusum','ewma','doe_main','doe_interaction','surface','contour',
  'residual','predicted','ci','errorbar',
]);

const ENG_EPS=1e-12;
const engFinite=(v)=>typeof v==='number'&&Number.isFinite(v);
const esc=(v)=>String(v??'').replace(/[&<>"']/g,(m)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const engFail=(code,message,details={})=>{throw new NumericalContractError(code,message,details);};
function nums(values,name,min=1){if(!Array.isArray(values)||values.length<min)engFail('ENG_DATA',`${name} requires at least ${min} values.`);return values.map((v,i)=>{const n=Number(v);if(!engFinite(n))engFail('ENG_DATA',`${name}[${i}] must be finite.`);return n;});}
function range(values,pad=.08){const a=nums(values,'range');let lo=Math.min(...a),hi=Math.max(...a);if(Math.abs(hi-lo)<=ENG_EPS){const d=Math.max(1,Math.abs(lo)*.05);lo-=d;hi+=d;}const p=(hi-lo)*pad;return[lo-p,hi+p];}
function scale(v,a,b,c,d){return c+(v-a)/(b-a)*(d-c);}
function path(points){return points.map((p,i)=>`${i?'L':'M'} ${p[0].toFixed(3)} ${p[1].toFixed(3)}`).join(' ');}
function predictSurface(coeffs,x1,x2){return coeffs[0]+coeffs[1]*x1+coeffs[2]*x2+coeffs[3]*x1*x1+coeffs[4]*x2*x2+coeffs[5]*x1*x2;}
function gridValues(rows,field){return nums(rows.map(r=>r[field]),field);}

export function prepareEngineeringChart(type,input={},options={}){
  if(!ENGINEERING_CHART_TYPES.includes(type))engFail('ENG_TYPE',`Unsupported engineering chart type: ${type}`,{type});
  if(type==='spc'){
    const values=nums(input.values,'values',2); const rules=westernElectricRules(values,{center:options.center??null,sigma:options.sigma??null});
    return {type,values,center:rules.center,sigma:rules.sigma,lcl:rules.center-3*rules.sigma,ucl:rules.center+3*rules.sigma,rules,spec:{lsl:options.lsl??null,usl:options.usl??null},title:options.title||'SPC Control Chart'};
  }
  if(type==='imr') return {type,stats:individualsMovingRange(nums(input.values,'values',2)),title:options.title||'Individuals / Moving Range'};
  if(type==='xbarr') return {type,stats:xbarR(input.subgroups),title:options.title||'X̄ / R Control Chart'};
  if(type==='cusum') return {type,stats:cusum(nums(input.values,'values',2),options),title:options.title||'CUSUM Change Detection'};
  if(type==='ewma') return {type,stats:ewma(nums(input.values,'values',2),options),title:options.title||'EWMA Trend Control'};
  if(type==='doe_main'){
    const factors=options.factors??input.factors, response=options.response??input.response;
    return {type,effects:doeMainEffects(input.rows,{factors,response}),title:options.title||'DOE Main Effects'};
  }
  if(type==='doe_interaction'){
    const factorA=options.factorA??input.factorA, factorB=options.factorB??input.factorB, response=options.response??input.response;
    return {type,interaction:doeInteraction(input.rows,{factorA,factorB,response}),title:options.title||'DOE Interaction Plot'};
  }
  if(type==='surface'||type==='contour'){
    const x1=options.x1??input.x1,x2=options.x2??input.x2,response=options.response??input.response;
    if(typeof x1!=='string'||typeof x2!=='string'||typeof response!=='string')engFail('RESPONSE_SURFACE_SCHEMA','Response surface requires x1, x2, and response field names.');
    const fit=fitResponseSurface(input.rows,{x1,x2,response,confidence:options.confidence??.95});
    const xa=gridValues(input.rows,x1),xb=gridValues(input.rows,x2),za=gridValues(input.rows,response),[xlo,xhi]=range(xa,.02),[ylo,yhi]=range(xb,.02);
    const nx=Math.max(5,Math.min(40,Number(options.gridX)||18)),ny=Math.max(5,Math.min(40,Number(options.gridY)||14));
    const cells=[];let zmin=Infinity,zmax=-Infinity;
    for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
      const a=xlo+(xhi-xlo)*i/(nx-1),b=ylo+(yhi-ylo)*j/(ny-1),z=predictSurface(fit.coefficients,a,b);zmin=Math.min(zmin,z);zmax=Math.max(zmax,z);cells.push({i,j,x1:a,x2:b,z});
    }
    return {type,fit,fields:{x1,x2,response},observed:{x:xa,y:xb,z:za},grid:{nx,ny,xlo,xhi,ylo,yhi,zmin,zmax,cells},title:options.title||(type==='surface'?'Response Surface':'Response Contour')};
  }
  if(type==='residual'||type==='predicted'){
    if(!Array.isArray(input.features)||!Array.isArray(input.response))engFail('REGRESSION_SCHEMA','Regression diagnostics require features matrix and response array.');
    const model=linearModel(input.features,input.response,{intercept:options.intercept??true,confidence:options.confidence??.95});
    const diagnostics=residualDiagnostics(input.features,input.response,{intercept:options.intercept??true,confidence:options.confidence??.95});
    return {type,model,diagnostics,title:options.title||(type==='residual'?'Residual Diagnostic':'Predicted vs Actual')};
  }
  if(type==='ci'){
    if(!Array.isArray(input.groups)||!input.groups.length)engFail('CI_GROUPS','Confidence interval plot requires groups.');
    const groups=input.groups.map((g,i)=>{
      if(!g||!Array.isArray(g.values))engFail('CI_GROUPS','Each CI group requires values.',{index:i});
      return {label:String(g.label??`Group ${i+1}`),...meanConfidenceInterval(g.values,{confidence:options.confidence??.95})};
    });
    return {type,groups,confidence:options.confidence??.95,title:options.title||'Confidence Interval Plot'};
  }
  if(type==='errorbar'){
    if(!Array.isArray(input.groups)||!input.groups.length)engFail('ERRORBAR_GROUPS','Error-bar plot requires groups.');
    const groups=input.groups.map((g,i)=>{
      const value=Number(g?.value),lower=Number(g?.lower),upper=Number(g?.upper);
      if(!g||!engFinite(value)||!engFinite(lower)||!engFinite(upper)||lower>value||upper<value)engFail('ERRORBAR_GROUP','Error-bar group requires finite lower <= value <= upper.',{index:i});
      return {label:String(g.label??`Group ${i+1}`),value,lower,upper};
    });
    return {type,groups,title:options.title||'Error-bar Comparison'};
  }
  engFail('ENG_TYPE','Unreachable engineering chart type.');
}

function svgShell(plan,W,H,body,desc){return `<svg class="viz-engineering-chart" data-engineering-chart="${esc(plan.type)}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(plan.title)}"><title>${esc(plan.title)}</title><desc>${esc(desc)}</desc>${body}</svg>`;}
function chartGrid(W,H,m,{x=5,y=4}={}){let s='';if(y>0){for(let i=0;i<=y;i++){const yy=m.t+(H-m.t-m.b)*i/y;s+=`<line class="viz-grid" x1="${m.l}" y1="${yy}" x2="${W-m.r}" y2="${yy}"/>`;}}if(x>0){for(let i=0;i<=x;i++){const xx=m.l+(W-m.l-m.r)*i/x;s+=`<line class="viz-grid" x1="${xx}" y1="${m.t}" x2="${xx}" y2="${H-m.b}"/>`;}}return s;}
function lineClass(x1,y1,x2,y2,cls='viz-eng-limit'){return `<line class="${cls}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;}
function seriesPlot(values,{W,H,m,limits=[],center=null,signalIndices=new Set(),label='value'}={}){
  const extra=limits.map(x=>x.value).concat(center==null?[]:[center]),ey=range(values.concat(extra),.08),sx=(i)=>scale(i,0,Math.max(1,values.length-1),m.l,W-m.r),sy=(v)=>scale(v,ey[0],ey[1],H-m.b,m.t);
  let s=chartGrid(W,H,m,{x:5,y:4});
  for(const l of limits)s+=lineClass(m.l,sy(l.value),W-m.r,sy(l.value),l.className||'viz-eng-limit');
  if(center!=null)s+=lineClass(m.l,sy(center),W-m.r,sy(center),'viz-eng-center');
  s+=`<path class="viz-line viz-series-0" d="${path(values.map((v,i)=>[sx(i),sy(v)]))}"/>`;
  values.forEach((v,i)=>{const bad=signalIndices.has(i);s+=`<circle class="viz-eng-point ${bad?'viz-eng-signal':'viz-series-0'}" cx="${sx(i)}" cy="${sy(v)}" r="4"><title>${esc(`${label} ${i+1}: ${v}`)}</title></circle>`;});
  return s;
}

export function renderEngineeringChartSvg(plan,{width=700,height=390}={}){
  if(!plan||!ENGINEERING_CHART_TYPES.includes(plan.type))engFail('ENG_PLAN','A prepared engineering chart plan is required.');
  const W=Math.max(260,Number(width)||700),H=Math.max(180,Number(height)||390),m={l:48,r:22,t:24,b:38};let body='';
  if(plan.type==='spc'){
    const signals=new Set(plan.rules.signals.flatMap(s=>s.indices));const limits=[{value:plan.ucl},{value:plan.lcl}];
    if(engFinite(Number(plan.spec.usl)))limits.push({value:Number(plan.spec.usl),className:'viz-eng-spec'});if(engFinite(Number(plan.spec.lsl)))limits.push({value:Number(plan.spec.lsl),className:'viz-eng-spec'});
    body=seriesPlot(plan.values,{W,H,m,limits,center:plan.center,signalIndices:signals,label:'Sample'});
  } else if(plan.type==='imr'||plan.type==='xbarr'){
    const topH=Math.floor((H-18)/2),gap=18,bottomY=topH+gap;
    const a=plan.type==='imr'?plan.stats.values:plan.stats.means,b=plan.type==='imr'?plan.stats.movingRanges:plan.stats.ranges;
    const al=plan.type==='imr'?plan.stats.iLimits:plan.stats.xbarLimits,bl=plan.type==='imr'?plan.stats.mrLimits:plan.stats.rLimits;
    const sigA=new Set(plan.stats.rules?.signals?.flatMap(x=>x.indices)??[]);
    const top=seriesPlot(a,{W,H:topH,m:{l:48,r:22,t:20,b:28},limits:[{value:al.ucl},{value:al.lcl}],center:al.center,signalIndices:sigA,label:plan.type==='imr'?'Individual':'Subgroup mean'});
    const bottom=seriesPlot(b,{W,H:topH,m:{l:48,r:22,t:18,b:28},limits:[{value:bl.ucl},{value:bl.lcl}],center:bl.center,label:plan.type==='imr'?'Moving range':'Range'});
    body=`<g>${top}<text class="viz-eng-panel-label" x="8" y="22">${plan.type==='imr'?'I':'X̄'}</text></g><g transform="translate(0 ${bottomY})">${bottom}<text class="viz-eng-panel-label" x="8" y="22">${plan.type==='imr'?'MR':'R'}</text></g>`;
  } else if(plan.type==='cusum'){
    const plus=plan.stats.points.map(p=>p.cPlus),minus=plan.stats.points.map(p=>p.cMinus),all=plus.concat(minus,[plan.stats.h,-plan.stats.h]),ey=range(all,.08),sx=i=>scale(i,0,Math.max(1,plus.length-1),m.l,W-m.r),sy=v=>scale(v,ey[0],ey[1],H-m.b,m.t);
    body=chartGrid(W,H,m)+lineClass(m.l,sy(plan.stats.h),W-m.r,sy(plan.stats.h))+lineClass(m.l,sy(-plan.stats.h),W-m.r,sy(-plan.stats.h))+lineClass(m.l,sy(0),W-m.r,sy(0),'viz-eng-center')+`<path class="viz-line viz-series-0" d="${path(plus.map((v,i)=>[sx(i),sy(v)]))}"/><path class="viz-line viz-series-1" d="${path(minus.map((v,i)=>[sx(i),sy(v)]))}"/>`;
  } else if(plan.type==='ewma'){
    const z=plan.stats.points.map(p=>p.ewma),all=z.concat(plan.stats.points.map(p=>p.lcl),plan.stats.points.map(p=>p.ucl),[plan.stats.target]),ey=range(all,.06),sx=i=>scale(i,0,Math.max(1,z.length-1),m.l,W-m.r),sy=v=>scale(v,ey[0],ey[1],H-m.b,m.t);
    body=chartGrid(W,H,m)+lineClass(m.l,sy(plan.stats.target),W-m.r,sy(plan.stats.target),'viz-eng-center')+`<path class="viz-eng-limit-path" d="${path(plan.stats.points.map((p,i)=>[sx(i),sy(p.ucl)]))}"/><path class="viz-eng-limit-path" d="${path(plan.stats.points.map((p,i)=>[sx(i),sy(p.lcl)]))}"/><path class="viz-line viz-series-0" d="${path(z.map((v,i)=>[sx(i),sy(v)]))}"/>`+plan.stats.points.map((p,i)=>p.signal?`<circle class="viz-eng-point viz-eng-signal" cx="${sx(i)}" cy="${sy(p.ewma)}" r="4"><title>EWMA signal ${i+1}</title></circle>`:'').join('');
  } else if(plan.type==='doe_main'){
    const all=plan.effects.flatMap(e=>e.levels.map(l=>l.mean)),ey=range(all,.1),plotW=W-m.l-m.r,band=plotW/plan.effects.length,sy=v=>scale(v,ey[0],ey[1],H-m.b,m.t);body=chartGrid(W,H,m,{x:0,y:4});
    plan.effects.forEach((e,ei)=>{const left=m.l+ei*band+band*.2,right=m.l+(ei+1)*band-band*.2,pts=e.levels.map((l,i)=>[scale(i,0,Math.max(1,e.levels.length-1),left,right),sy(l.mean)]);body+=`<path class="viz-line viz-series-${ei%3}" d="${path(pts)}"/>`+pts.map((p,i)=>`<circle class="viz-eng-point viz-series-${ei%3}" cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(`${e.factor} ${e.levels[i].level}: ${e.levels[i].mean}`)}</title></circle>`).join('')+`<text class="viz-label" x="${left+(right-left)/2}" y="${H-10}" text-anchor="middle">${esc(e.factor)}</text>`;});
  } else if(plan.type==='doe_interaction'){
    const it=plan.interaction,all=it.cells.flat().map(c=>c.mean),ey=range(all,.1),sy=v=>scale(v,ey[0],ey[1],H-m.b,m.t),sx=i=>scale(i,0,Math.max(1,it.levelsB.length-1),m.l,W-m.r);body=chartGrid(W,H,m,{x:Math.max(1,it.levelsB.length-1),y:4});
    it.levelsA.forEach((a,ai)=>{const pts=it.cells[ai].map((c,i)=>[sx(i),sy(c.mean)]);body+=`<path class="viz-line viz-series-${ai%3}" d="${path(pts)}"/>`+pts.map((p,i)=>`<circle class="viz-eng-point viz-series-${ai%3}" cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(`${it.factorA} ${a}, ${it.factorB} ${it.levelsB[i]}: ${it.cells[ai][i].mean}`)}</title></circle>`).join('');});
  } else if(plan.type==='surface'){
    const g=plan.grid,isoX=(i,j)=>m.l+(W-m.l-m.r)*(i/(g.nx-1)*.72+j/(g.ny-1)*.28),baseY=(i,j)=>H-m.b-(H-m.t-m.b)*(j/(g.ny-1)*.48+i/(g.nx-1)*.10),zr=Math.max(ENG_EPS,g.zmax-g.zmin),zY=z=>((z-g.zmin)/zr)*(H-m.t-m.b)*.34;body='';
    for(let j=0;j<g.ny;j++){const pts=[];for(let i=0;i<g.nx;i++){const c=g.cells[j*g.nx+i];pts.push([isoX(i,j),baseY(i,j)-zY(c.z)]);}body+=`<path class="viz-eng-mesh ${j%2?'viz-series-1':'viz-series-0'}" d="${path(pts)}"/>`;}
    for(let i=0;i<g.nx;i++){const pts=[];for(let j=0;j<g.ny;j++){const c=g.cells[j*g.nx+i];pts.push([isoX(i,j),baseY(i,j)-zY(c.z)]);}body+=`<path class="viz-eng-mesh viz-eng-mesh-minor" d="${path(pts)}"/>`;}
    body+=`<text class="viz-label" x="${m.l}" y="${H-10}">R² ${plan.fit.r2.toFixed(3)}</text>`;
  } else if(plan.type==='contour'){
    const g=plan.grid,cw=(W-m.l-m.r)/g.nx,ch=(H-m.t-m.b)/g.ny,zr=Math.max(ENG_EPS,g.zmax-g.zmin);body=chartGrid(W,H,m,{x:0,y:0});
    for(const c of g.cells){const level=Math.max(0,Math.min(4,Math.floor((c.z-g.zmin)/zr*5)));body+=`<rect class="viz-eng-heat viz-eng-heat-${level}" x="${m.l+c.i*cw}" y="${m.t+(g.ny-1-c.j)*ch}" width="${cw+.2}" height="${ch+.2}"><title>${esc(`${plan.fields.x1} ${c.x1.toFixed(3)}, ${plan.fields.x2} ${c.x2.toFixed(3)}, ${plan.fields.response} ${c.z.toFixed(3)}`)}</title></rect>`;}
    body+=`<text class="viz-label" x="${m.l}" y="${H-10}">Fitted response · R² ${plan.fit.r2.toFixed(3)}</text>`;
  } else if(plan.type==='residual'||plan.type==='predicted'){
    const x=plan.type==='residual'?plan.diagnostics.map(d=>d.predicted):plan.diagnostics.map(d=>d.actual),y=plan.type==='residual'?plan.diagnostics.map(d=>d.standardizedResidual):plan.diagnostics.map(d=>d.predicted),ex=range(x,.08),ey=range(y.concat(plan.type==='residual'?[0]:x),.08),sx=v=>scale(v,ex[0],ex[1],m.l,W-m.r),sy=v=>scale(v,ey[0],ey[1],H-m.b,m.t);body=chartGrid(W,H,m);
    if(plan.type==='residual')body+=lineClass(m.l,sy(0),W-m.r,sy(0),'viz-eng-center');else{const lo=Math.max(ex[0],ey[0]),hi=Math.min(ex[1],ey[1]);body+=lineClass(sx(lo),sy(lo),sx(hi),sy(hi),'viz-eng-reference');}
    body+=x.map((v,i)=>`<circle class="viz-eng-point ${Math.abs(plan.diagnostics[i].standardizedResidual)>2?'viz-eng-signal':'viz-series-0'}" cx="${sx(v)}" cy="${sy(y[i])}" r="4"><title>${esc(`Observation ${i+1}: ${x[i].toFixed(3)}, ${y[i].toFixed(3)}`)}</title></circle>`).join('');
  } else if(plan.type==='ci'||plan.type==='errorbar'){
    const groups=plan.groups,vals=groups.flatMap(g=>[g.lower,g.upper,g.mean??g.value]),ex=range(vals,.08),sx=v=>scale(v,ex[0],ex[1],m.l,W-m.r),rowH=(H-m.t-m.b)/groups.length;body='';groups.forEach((g,i)=>{const y=m.t+(i+.5)*rowH,center=g.mean??g.value;body+=lineClass(sx(g.lower),y,sx(g.upper),y,'viz-eng-errorbar')+lineClass(sx(g.lower),y-7,sx(g.lower),y+7,'viz-eng-errorbar')+lineClass(sx(g.upper),y-7,sx(g.upper),y+7,'viz-eng-errorbar')+`<circle class="viz-eng-point viz-series-${i%3}" cx="${sx(center)}" cy="${y}" r="5"><title>${esc(`${g.label}: ${center} [${g.lower}, ${g.upper}]`)}</title></circle><text class="viz-label" x="${m.l-8}" y="${y+4}" text-anchor="end">${esc(g.label)}</text>`;});
  }
  return svgShell(plan,W,H,body,`${plan.type} computed by the Visualizer reference-tested engineering statistics backend.`);
}
