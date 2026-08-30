import assert from 'node:assert/strict';
import { NumericalContractError } from '../core/statistics_engine.mjs';
import { ENGINEERING_CHART_TYPES, prepareEngineeringChart, renderEngineeringChartSvg } from '../core/engineering_chart_engine.mjs';

const spcValues=[10.1,9.9,10.0,10.2,10.1,10.0,10.3,10.2,10.1,10.0,10.8,10.9];
const subgroups=Array.from({length:9},(_,g)=>Array.from({length:5},(_,i)=>50+g*.08+i*.03+((g+i)%3)*.02));
const doeRows=[]; for(const A of [-1,1])for(const B of [-1,1])for(let r=0;r<3;r++)doeRows.push({A,B,y:80+7*A+3*B+5*A*B+r*.4});
const surfaceRows=[]; for(const x of [-2,-1,0,1,2])for(const y of [-2,-1,0,1,2])surfaceRows.push({x,y,z:70+4*x-2*y+1.2*x*x+.8*y*y+2*x*y});
const features=Array.from({length:20},(_,i)=>[i/3,(i%5)-2]); const response=features.map(([a,b],i)=>8+2*a-1.5*b+((i%3)-1)*.25);
const groups=[{label:'Control',values:[10,11,9,10,10.5,9.5,10.2]},{label:'Affected',values:[12,13,11.5,12.4,13.1,11.9,12.2]}];
const errorGroups=[{label:'A',value:10,lower:8.5,upper:11.5},{label:'B',value:14,lower:12,upper:15},{label:'C',value:9,lower:8,upper:10.5}];

function inputFor(type){
  if(type==='spc')return [{values:spcValues},{center:10,sigma:.2,lsl:9.2,usl:10.8}];
  if(type==='imr')return [{values:spcValues},{}];
  if(type==='xbarr')return [{subgroups},{}];
  if(type==='cusum')return [{values:spcValues},{target:10,sigma:.2,k:.5,h:4}];
  if(type==='ewma')return [{values:spcValues},{target:10,sigma:.2,lambda:.25,L:3}];
  if(type==='doe_main')return [{rows:doeRows,factors:['A','B'],response:'y'},{}];
  if(type==='doe_interaction')return [{rows:doeRows,factorA:'A',factorB:'B',response:'y'},{}];
  if(type==='surface'||type==='contour')return [{rows:surfaceRows,x1:'x',x2:'y',response:'z'},{gridX:14,gridY:10}];
  if(type==='residual'||type==='predicted')return [{features,response},{}];
  if(type==='ci')return [{groups},{confidence:.95}];
  if(type==='errorbar')return [{groups:errorGroups},{}];
}
let cases=0;
for(const type of ENGINEERING_CHART_TYPES){
  const [input,options]=inputFor(type),plan=prepareEngineeringChart(type,input,options);
  for(const [w,h] of [[330,230],[600,350],[980,540]]){
    const a=renderEngineeringChartSvg(plan,{width:w,height:h}),b=renderEngineeringChartSvg(plan,{width:w,height:h});
    assert.equal(a,b,`${type} deterministic`); assert.ok(a.includes(`data-engineering-chart="${type}"`)); assert.ok(a.includes('role="img"')); assert.ok(!/NaN|Infinity|undefined/.test(a)); cases++;
  }
}
assert.throws(()=>prepareEngineeringChart('spc',{values:[1,1,1]}),NumericalContractError);
assert.throws(()=>prepareEngineeringChart('xbarr',{subgroups:[[1,2],[1,2,3]]}),NumericalContractError);
assert.throws(()=>prepareEngineeringChart('errorbar',{groups:[{value:3,lower:4,upper:5}]}),NumericalContractError);
console.log(JSON.stringify({pass:true,types:ENGINEERING_CHART_TYPES.length,renderCases:cases,deterministic:true,invalidInputBlocking:true},null,2));
