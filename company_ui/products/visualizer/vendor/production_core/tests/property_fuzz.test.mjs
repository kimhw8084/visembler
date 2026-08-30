import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { writeFileSync } from 'node:fs';
import { describe, histogram, ecdf, pareto, normalizeStackedSeries, NumericalContractError } from '../core/statistics_engine.mjs';
import { buildPivot, cellValue, pivotFingerprint, projectVisibleRows, virtualWindow, TableContractError } from '../core/table_pivot_engine.mjs';
import { EditorStore, serializeCanonical, RevisionConflictError } from '../core/editor_store.mjs';
import { ADVANCED_CHART_TYPES, prepareAdvancedChart, renderAdvancedChartSvg } from '../core/advanced_chart_engine.mjs';
import { compileGridLayout } from '../core/grid_layout_engine.mjs';
import { prepareImagePlan, assetToView, viewToAsset } from '../core/image_media_engine.mjs';
import { compareWafers } from '../core/wafer_fab_engine.mjs';
import { prepareTimeline } from '../core/timeline_semantics_engine.mjs';

const SEED = 0x5a17c0de;
let state = SEED >>> 0;
function rnd(){ state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 0x100000000; }
function int(a,b){ return a + Math.floor(rnd()*(b-a+1)); }
function pick(a){ return a[int(0,a.length-1)]; }
function close(a,b,t=1e-9){ return Math.abs(a-b) <= t*Math.max(1,Math.abs(a),Math.abs(b)); }

let statsCases=0,pivotCases=0,editorCases=0,chartCases=0,gridCases=0,imageCases=0,waferCases=0,timelineCases=0,invalidCases=0;
const started=performance.now();

// 3,500 statistical/property cases.
for(let c=0;c<3500;c++){
  const n=int(2,40), values=Array.from({length:n},()=>int(-10000,10000)/100);
  const d=describe(values);
  assert.ok(d.min<=d.q1&&d.q1<=d.median&&d.median<=d.q3&&d.q3<=d.max);
  assert.ok(d.mean>=d.min-1e-12&&d.mean<=d.max+1e-12);
  const h=histogram(values,{bins:int(1,Math.min(12,n))});
  assert.equal(h.counts.reduce((a,b)=>a+b,0),n);
  assert.equal(h.total,n);
  const e=ecdf(values); assert.equal(e.points.at(-1).cumulativeCount,n); assert.equal(e.points.at(-1).p,1);
  const cats=Array.from({length:int(2,8)},(_,i)=>`C${i}`), vals=cats.map(()=>int(0,1000));
  if(vals.some(v=>v>0)) { const p=pareto(cats,vals); assert.ok(close(p.rows.at(-1).cumulativePercent,100,1e-12)); }
  const s1=cats.map(()=>int(0,50)),s2=cats.map(()=>int(0,50));
  if(cats.every((_,i)=>s1[i]+s2[i]>0)){
    const st=normalizeStackedSeries(cats,[{name:'A',values:s1},{name:'B',values:s2}],{percent:true});
    for(let i=0;i<cats.length;i++) assert.ok(close(st.series[0].values[i]+st.series[1].values[i],100,1e-10));
  }
  statsCases++;
}

// 3,000 typed pivot / hierarchy / virtualization cases.
for(let c=0;c<3000;c++){
  const n=int(1,35); const rows=[];
  for(let i=0;i<n;i++) rows.push({
    a:pick(['A','B','C',1,'1',null]), b:pick(['x','y','z']), col:pick(['Q1','Q2','Q3']),
    v:int(-1000,1000), defect:int(0,20), lot:`L${int(1,12)}`,
  });
  const model=buildPivot(rows,{rows:['a','b'],columns:['col'],measures:[
    {id:'sum',field:'v',aggregator:'sum'}, {id:'avg',field:'defect',aggregator:'avg'}, {id:'distinct',field:'lot',aggregator:'distinct_count'},
  ]});
  const direct=rows.reduce((s,r)=>s+r.v,0);
  assert.ok(close(cellValue(model,model.rowRootId,model.columnRootId,'sum'),direct,1e-12));
  assert.equal(cellValue(model,model.rowRootId,model.columnRootId,'distinct'),new Set(rows.map(r=>r.lot)).size);
  // Parent source counts must equal children when children exist.
  for(const node of Object.values(model.rowsById)) if(node.childIds.length){
    assert.equal(node.childIds.reduce((s,id)=>s+model.rowsById[id].sourceCount,0),node.sourceCount);
  }
  const vis=projectVisibleRows(model,{expandedIds:'all'}); const vw=virtualWindow(vis.length,{scrollTop:rnd()*1000,viewportHeight:int(0,900),rowHeight:int(20,60),overscan:int(0,10)});
  assert.ok(vw.start>=0&&vw.end>=vw.start&&vw.end<=vis.length&&vw.count===vw.end-vw.start);
  if(c%50===0) assert.equal(pivotFingerprint(model),pivotFingerprint(buildPivot([...rows].reverse(),{rows:['a','b'],columns:['col'],measures:[{id:'sum',field:'v',aggregator:'sum'},{id:'avg',field:'defect',aggregator:'avg'},{id:'distinct',field:'lot',aggregator:'distinct_count'}]})));
  pivotCases++;
}

// 1,500 exact editor command/history cases.
for(let c=0;c<1500;c++){
  const initial={schema_version:1,mode:'smart',layoutPreset:'editorial',crossFilter:null,nextId:20,groups:{},items:Array.from({length:5},(_,i)=>({id:`c${i+1}`,type:'metric',order:i,x:i*10,y:i*4,w:120,h:80,weight:1,z:i}))};
  const store=new EditorStore(initial,{revision:1}); const before=serializeCanonical(store.model);
  const id=`c${int(1,5)}`; const patch={x:int(-500,1000),y:int(-500,1000),w:int(32,800),h:int(32,600),z:int(0,50)};
  const accepted=store.commit(store.command([{op:'item.patch',id,patch}],`fuzz ${c}`));
  const after=serializeCanonical(store.model); assert.notEqual(after,before); assert.equal(accepted.canonical_after,after);
  store.undo(); assert.equal(serializeCanonical(store.model),before);
  store.redo(); assert.equal(serializeCanonical(store.model),after);
  assert.throws(()=>store.commit({...store.command([{op:'item.patch',id,patch:{x:1}}]),base_revision:store.revision-1}),RevisionConflictError);
  editorCases++;
}

function chartInput(type){
  const n=int(4,12); const values=Array.from({length:n},(_,i)=>i+rnd()*5+1);
  switch(type){
    case 'histogram':case 'box':case 'violin':case 'ecdf': return {values};
    case 'regression': return {x:Array.from({length:n},(_,i)=>i+1),y:Array.from({length:n},(_,i)=>2*(i+1)+rnd())};
    case 'bubble': return {x:values,y:values.map(v=>v+rnd()*2),size:values.map(()=>rnd()*100),labels:values.map((_,i)=>`P${i}`)};
    case 'stacked100':case 'stackedArea': { const categories=Array.from({length:n},(_,i)=>`C${i}`); return {categories,series:[{name:'A',values:categories.map(()=>int(1,20))},{name:'B',values:categories.map(()=>int(1,20))}]}; }
    case 'step': return {x:Array.from({length:n},(_,i)=>i+1),y:values};
    case 'treemap': return {nodes:Array.from({length:n},(_,i)=>({id:`n${i}`,value:int(1,100)}))};
    case 'funnel': return {stages:Array.from({length:n},(_,i)=>`S${i}`),values:Array.from({length:n},(_,i)=>Math.max(1,100-i*5))};
    case 'sankey': return {nodes:Array.from({length:n},(_,i)=>({id:`n${i}`})),links:Array.from({length:n-1},(_,i)=>({source:`n${i}`,target:`n${i+1}`,value:int(1,50)}))};
  }
}

// 2,000 chart-plan + SVG safety/determinism cases, including invalid-input blocks.
for(let c=0;c<2000;c++){
  const type=ADVANCED_CHART_TYPES[c%ADVANCED_CHART_TYPES.length];
  if(c%10===0){
    assert.throws(()=>prepareAdvancedChart('bubble',{x:[1],y:[2],size:[-1]}),NumericalContractError); invalidCases++; chartCases++; continue;
  }
  const input=chartInput(type), plan=prepareAdvancedChart(type,input), width=int(220,1200), height=int(140,800);
  const a=renderAdvancedChartSvg(plan,{width,height}), b=renderAdvancedChartSvg(plan,{width,height});
  assert.equal(a,b); assert.ok(a.startsWith('<svg')); assert.ok(!/NaN|Infinity|undefined/.test(a)); assert.ok(/role="img"/.test(a));
  chartCases++;
}


// 2,500 release-hardening cases: arbitrary grid, asset-relative media, registered wafer, no-invented-date timeline.
for(let c=0;c<625;c++){
  const w=4+rnd()*12,h=3+rnd()*10,cols=int(1,24),rows=int(1,16),gap=rnd()*.12;
  const plan=compileGridLayout({page:{width:w,height:h},targetRegion:{x:.05,y:.05,width:w-.1,height:h-.1},columns:cols,rows,gap,items:[{id:'full',col:0,row:0,colSpan:cols,rowSpan:rows}]});
  assert.ok(Number.isFinite(plan.placements[0].x)&&close(plan.placements[0].width,w-.1,1e-8));gridCases++;
}
for(let c=0;c<625;c++){
  const crop={x:rnd()*.2,y:rnd()*.2,width:.55+rnd()*.2,height:.55+rnd()*.2};if(crop.x+crop.width>1)crop.x=1-crop.width;if(crop.y+crop.height>1)crop.y=1-crop.height;
  const plan=prepareImagePlan({asset:{id:`a${c}`,width:7680,height:4320},crop});const p={x:crop.x+rnd()*crop.width,y:crop.y+rnd()*crop.height};const v=assetToView(p,plan.crop,{width:840,height:520}),q=viewToAsset(v,plan.crop,{width:840,height:520});assert.ok(close(p.x,q.x,1e-12)&&close(p.y,q.y,1e-12));imageCases++;
}
for(let c=0;c<625;c++){
  const val=c%11===0?0:c%13===0?null:c%17;const a={diameterMm:300,unit:'nm',dies:[{x:0,y:0,value:val},{x:1,y:0,value:2}]},b={diameterMm:300,unit:'nm',dies:[{x:0,y:0,value:1},{x:0,y:-1,value:4}]};const x=compareWafers(a,b,{registration:{rotateDeg:-90}});assert.equal(x.cells[0].missingA,val===null);if(val===0)assert.equal(x.cells[0].delta,1);waferCases++;
}
for(let c=0;c<625;c++){
  const n=int(2,8),tasks=Array.from({length:n},(_,i)=>({id:`t${i}`,order:i,label:`Task ${i}`})),dependencies=Array.from({length:n-1},(_,i)=>({source:`t${i}`,target:`t${i+1}`}));const p=prepareTimeline('sequence',{tasks,dependencies});assert.equal(p.dateSemantics,'none');assert.ok(p.tasks.every(t=>!('start' in t)&&!('end' in t)));timelineCases++;
}

// Explicit invalid pivot corpus.
for(let i=0;i<20;i++){
  assert.throws(()=>buildPivot([{k:'x',v:Infinity}],{rows:['k'],measures:[{field:'v',aggregator:'sum'}]}),TableContractError); invalidCases++;
}

const elapsedMs=performance.now()-started;
const total=statsCases+pivotCases+editorCases+chartCases+gridCases+imageCases+waferCases+timelineCases;
assert.equal(total,12500);
const report={pass:true,seed:SEED,totalCases:total,statsCases,pivotCases,editorCases,chartCases,gridCases,imageCases,waferCases,timelineCases,invalidCases,elapsedMs:+elapsedMs.toFixed(2)};
writeFileSync(new URL('../qa/property_fuzz.json', import.meta.url), JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
