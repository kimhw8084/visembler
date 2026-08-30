import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  NumericalContractError, describe, histogram, boxPlot, ecdf, kde, meanConfidenceInterval,
  linearRegression, linearModel, residualDiagnostics, doeMainEffects, doeInteraction, fitResponseSurface,
  individualsMovingRange, xbarR, cusum, ewma, processCapability, pareto, normalizeStackedSeries, stepSeries,
} from '../core/statistics_engine.mjs';

const F=JSON.parse(fs.readFileSync(new URL('./fixtures/stat_reference.json', import.meta.url),'utf8'));
const close=(a,b,tol=1e-8,msg='')=>assert.ok(Math.abs(a-b)<=tol,`${msg} ${a} != ${b} (tol ${tol})`);
const closeArray=(a,b,tol=1e-8,msg='')=>{assert.equal(a.length,b.length,`${msg} length`);a.forEach((v,i)=>close(v,b[i],tol,`${msg}[${i}]`));};

const d=describe(F.distribution.values); const de=F.distribution.describe;
for(const k of ['min','q1','median','q3','max','mean','variance','stddev']) close(d[k],de[k],1e-10,`describe.${k}`);
const h=histogram(F.distribution.values,{bins:4}); closeArray(h.edges,F.distribution.histogram4.edges,1e-10,'hist.edges'); assert.deepEqual(h.counts,F.distribution.histogram4.counts);
const b=boxPlot(F.distribution.values); for(const k of ['lowerFence','upperFence','lowerWhisker','upperWhisker'])close(b[k],F.distribution.box[k],1e-10,`box.${k}`); assert.deepEqual(b.outliers,F.distribution.box.outliers);
const e=ecdf([2,1,2,3,3,3]); assert.deepEqual(e.points,[{x:1,count:1,cumulativeCount:1,p:1/6},{x:2,count:2,cumulativeCount:3,p:.5},{x:3,count:3,cumulativeCount:6,p:1}]);
const kd=kde(F.distribution.values,{points:32}); close(kd.bandwidth,F.distribution.kde.bandwidth,2e-12,'kde bandwidth'); closeArray(kd.x,F.distribution.kde.x,2e-10,'kde x'); closeArray(kd.density,F.distribution.kde.density,2e-10,'kde density');
const ci=meanConfidenceInterval(F.distribution.values); close(ci.critical,F.distribution.mean_ci95.critical,2e-4,'t critical'); close(ci.lower,F.distribution.mean_ci95.lower,5e-5,'mean ci lower'); close(ci.upper,F.distribution.mean_ci95.upper,5e-5,'mean ci upper');

const lr=linearRegression(F.simple_regression.x,F.simple_regression.y);
close(lr.slope,F.simple_regression.slope,1e-10,'slope'); close(lr.interceptValue,F.simple_regression.intercept,1e-10,'intercept'); close(lr.r,F.simple_regression.r,1e-10,'r'); close(lr.r2,F.simple_regression.r2,1e-10,'r2'); closeArray(lr.coefficients,F.simple_regression.coefficients,1e-10,'lr coefs'); closeArray(lr.standardErrors,F.simple_regression.standardErrors,1e-10,'lr se'); closeArray(lr.residuals,F.simple_regression.residuals,1e-10,'lr residuals'); closeArray(lr.predicted,F.simple_regression.predicted,1e-10,'lr predicted'); close(lr.rmse,F.simple_regression.rmse,1e-10,'lr rmse');

const ml=linearModel(F.multiple_regression.X,F.multiple_regression.y); closeArray(ml.coefficients,F.multiple_regression.coefficients,1e-9,'ml coefs'); closeArray(ml.standardErrors,F.multiple_regression.standardErrors,1e-9,'ml se'); close(ml.r2,F.multiple_regression.r2,1e-10,'ml r2'); close(ml.adjustedR2,F.multiple_regression.adjustedR2,1e-10,'ml adjr2'); close(ml.rmse,F.multiple_regression.rmse,1e-10,'ml rmse');
const rd=residualDiagnostics(F.multiple_regression.X,F.multiple_regression.y); assert.equal(rd.length,F.multiple_regression.y.length); assert.ok(rd.every(x=>Number.isFinite(x.standardizedResidual)&&Number.isFinite(x.leverage)));

const ma=doeMainEffects(F.doe.rows,{factors:['A','B'],response:'response'}); closeArray(ma[0].levels.map(x=>x.mean),F.doe.mainA,1e-12,'DOE A'); closeArray(ma[1].levels.map(x=>x.mean),F.doe.mainB,1e-12,'DOE B'); close(ma[0].effect,F.doe.mainA[1]-F.doe.mainA[0],1e-12,'DOE A effect');
const inter=doeInteraction(F.doe.rows,{factorA:'A',factorB:'B',response:'response'}); for(let i=0;i<2;i++)closeArray(inter.cells[i].map(x=>x.mean),F.doe.interactionCells[i],1e-12,`DOE cells ${i}`); close(inter.interactionEffect,F.doe.interactionEffect,1e-12,'DOE interaction effect');
const rs=fitResponseSurface(F.response_surface.rows,{x1:'temp',x2:'pressure',response:'yield'}); closeArray(rs.coefficients,F.response_surface.coefficients,1e-9,'response surface'); close(rs.r2,F.response_surface.r2,1e-12,'response surface r2');

const imr=individualsMovingRange(F.individuals.values); close(imr.iLimits.center,F.individuals.center,1e-12,'I center'); closeArray(imr.movingRanges,F.individuals.mr,1e-12,'MR'); close(imr.mrbar,F.individuals.mrbar,1e-12,'MRbar'); close(imr.sigma,F.individuals.sigma,1e-12,'I sigma'); close(imr.iLimits.lcl,F.individuals.iLcl,1e-12,'I LCL'); close(imr.iLimits.ucl,F.individuals.iUcl,1e-12,'I UCL'); close(imr.mrLimits.ucl,F.individuals.mrUcl,1e-12,'MR UCL');
const xr=xbarR(F.xbarR.subgroups); closeArray(xr.means,F.xbarR.means,1e-12,'Xbar means'); closeArray(xr.ranges,F.xbarR.ranges,1e-12,'ranges'); for(const [actual,expected,name] of [[xr.xbarbar,F.xbarR.xbarbar,'xbarbar'],[xr.rbar,F.xbarR.rbar,'rbar'],[xr.sigma,F.xbarR.sigma,'sigma'],[xr.xbarLimits.lcl,F.xbarR.xbarLcl,'xbar lcl'],[xr.xbarLimits.ucl,F.xbarR.xbarUcl,'xbar ucl'],[xr.rLimits.lcl,F.xbarR.rLcl,'r lcl'],[xr.rLimits.ucl,F.xbarR.rUcl,'r ucl']])close(actual,expected,1e-12,name);
const cs=cusum(F.cusum.values,{target:F.cusum.target,sigma:F.cusum.sigma,k:F.cusum.k,h:F.cusum.h}); closeArray(cs.points.map(x=>x.cPlus),F.cusum.points.map(x=>x.cPlus),1e-12,'CUSUM +'); closeArray(cs.points.map(x=>x.cMinus),F.cusum.points.map(x=>x.cMinus),1e-12,'CUSUM -'); assert.deepEqual(cs.points.map(x=>x.signalPlus),F.cusum.points.map(x=>x.signalPlus));
const ew=ewma(F.ewma.values,{target:F.ewma.target,sigma:F.ewma.sigma,lambda:F.ewma.lambda,L:F.ewma.L}); for(const k of ['ewma','sigmaZ','lcl','ucl'])closeArray(ew.points.map(x=>x[k]),F.ewma.points.map(x=>x[k]),1e-12,`EWMA ${k}`); assert.deepEqual(ew.points.map(x=>x.signal),F.ewma.points.map(x=>x.signal));
const cap=processCapability(F.capability.values,{lsl:F.capability.lsl,usl:F.capability.usl}); for(const k of ['mean','sigma','cp','cpu','cpl','cpk'])close(cap[k],F.capability[k],1e-12,`cap ${k}`);

const pa=pareto(F.pareto.categories,F.pareto.values); assert.deepEqual(pa.rows.map(x=>x.category),F.pareto.sorted); closeArray(pa.rows.map(x=>x.cumulativePercent),F.pareto.cumulativePercent,1e-12,'pareto cum');
const st=normalizeStackedSeries(F.stacked.categories,F.stacked.series,{percent:true}); st.series.forEach((s,i)=>closeArray(s.values,F.stacked.percent[i],1e-12,`stack ${i}`));
const step=stepSeries([1,2,3],[10,20,15]); assert.deepEqual(step.points,[{x:1,y:10},{x:2,y:10},{x:2,y:20},{x:3,y:20},{x:3,y:15}]);

assert.throws(()=>histogram([1,2,3],{bins:0}),NumericalContractError);
assert.throws(()=>linearRegression([1,1,1],[2,3,4]),NumericalContractError);
assert.throws(()=>xbarR([[1,2],[1,2,3]]),NumericalContractError);
assert.throws(()=>normalizeStackedSeries(['A'],[{name:'x',values:[0]},{name:'y',values:[0]}],{percent:true}),NumericalContractError);

console.log(JSON.stringify({pass:true, reference:'NumPy/SciPy/statsmodels', distribution:true, regression:true, doe:true, spc:true, transforms:true, invalidInputBlocking:true},null,2));
