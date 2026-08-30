import assert from 'node:assert/strict';
import { ADVANCED_CHART_TYPES, prepareAdvancedChart, renderAdvancedChartSvg } from '../core/advanced_chart_engine.mjs';
import { NumericalContractError } from '../core/statistics_engine.mjs';

const fixtures={
  histogram:{values:[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
  box:{values:[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
  violin:{values:[9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4]},
  ecdf:{values:[4,2,3,5,5,7,8,8,9,10,12]},
  regression:{x:[1,2,3,4,5,6,7,8],y:[2.3,4.2,5.8,8.1,9.7,12.4,13.8,16.1]},
  bubble:{x:[1,2,3,4,5],y:[8,5,9,4,7],size:[10,45,22,70,35],labels:['Etch','CVD','CMP','Litho','Diffusion']},
  stacked100:{categories:['Q1','Q2','Q3','Q4'],series:[{name:'Pass',values:[72,80,76,84]},{name:'Review',values:[18,12,16,10]},{name:'Fail',values:[10,8,8,6]}]},
  stackedArea:{categories:['Jan','Feb','Mar','Apr','May'],series:[{name:'A',values:[20,24,22,30,34]},{name:'B',values:[12,15,19,18,22]},{name:'C',values:[8,10,13,15,17]}]},
  step:{x:[1,2,3,4,5],y:[10,14,13,18,21]},
  treemap:{nodes:[{id:'a',label:'Etch',value:42},{id:'b',label:'CVD',value:35},{id:'c',label:'CMP',value:27},{id:'d',label:'Litho',value:21},{id:'e',label:'Diffusion',value:15}]},
  funnel:{stages:['Cases','Qualified','Rooted','Verified','Closed'],values:[120,88,61,42,37]},
  sankey:{nodes:[{id:'fdc',label:'FDC'},{id:'spc',label:'SPC'},{id:'norm',label:'Normalize'},{id:'reason',label:'Reason'},{id:'close',label:'Close'}],links:[{source:'fdc',target:'norm',value:50},{source:'spc',target:'norm',value:35},{source:'norm',target:'reason',value:70},{source:'reason',target:'close',value:62}]},
};
const dims={xs:[330,230],s:[440,280],m:[600,350],l:[760,430],xl:[980,540]};
const plans={};
for(const type of ADVANCED_CHART_TYPES){
  const plan=prepareAdvancedChart(type,fixtures[type]);plans[type]=plan;
  for(const [size,[w,h]] of Object.entries(dims)){
    const svg=renderAdvancedChartSvg(plan,{width:w,height:h,title:`${type} ${size}`});
    assert.ok(svg.startsWith('<svg '),`${type}/${size} emits SVG`);
    assert.ok(svg.includes(`data-chart-type="${type}"`),`${type}/${size} type marker`);
    assert.ok(!/NaN|undefined|Infinity/.test(svg),`${type}/${size} must not leak invalid numeric UI`);
    assert.equal(svg,renderAdvancedChartSvg(plan,{width:w,height:h,title:`${type} ${size}`}),`${type}/${size} deterministic render`);
  }
}

assert.equal(plans.histogram.stats.counts.reduce((a,b)=>a+b,0),fixtures.histogram.values.length);
assert.ok(plans.box.stats.outliers.includes(12.4));
assert.ok(plans.violin.kde.density.every(Number.isFinite));
assert.equal(plans.ecdf.stats.points.at(-1).p,1);
assert.ok(plans.regression.fit.r2>.99);
assert.equal(plans.bubble.x.length,plans.bubble.size.length);
for(let i=0;i<plans.stacked100.categories.length;i++){
  const total=plans.stacked100.series.reduce((s,x)=>s+x.values[i],0);assert.ok(Math.abs(total-100)<1e-10);
}
assert.equal(plans.step.points.length,fixtures.step.x.length*2-1);
assert.equal(plans.treemap.nodes.reduce((s,n)=>s+n.value,0),140);
assert.deepEqual(plans.funnel.stages,fixtures.funnel.stages);
assert.equal(plans.sankey.links.length,4);

assert.throws(()=>prepareAdvancedChart('bubble',{x:[1],y:[2],size:[-1]}),NumericalContractError);
assert.throws(()=>prepareAdvancedChart('stacked100',{categories:['A'],series:[{name:'x',values:[0]},{name:'y',values:[0]}]}),NumericalContractError);
assert.throws(()=>prepareAdvancedChart('sankey',{nodes:[{id:'a'},{id:'b'}],links:[{source:'a',target:'b',value:1},{source:'b',target:'a',value:1}]}),NumericalContractError);
assert.throws(()=>prepareAdvancedChart('funnel',{stages:['A'],values:[1,2]}),NumericalContractError);

console.log(JSON.stringify({pass:true,charts:ADVANCED_CHART_TYPES.length,sizes:Object.keys(dims).length,renderCases:ADVANCED_CHART_TYPES.length*Object.keys(dims).length,deterministic:true,invalidInputBlocking:true},null,2));
