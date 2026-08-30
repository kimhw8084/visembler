#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.nonparametric.bandwidths import bw_silverman

OUT=Path(__file__).resolve().parent/'fixtures/stat_reference.json'
values=np.array([9.8,10.1,10.4,9.9,10.2,10.0,10.6,9.7,10.3,10.5,9.6,12.4],dtype=float)
q=np.quantile(values,[.25,.5,.75],method='linear')
hcounts,hedges=np.histogram(values,bins=4)
iqr=q[2]-q[0]; lf=q[0]-1.5*iqr; uf=q[2]+1.5*iqr
inliers=values[(values>=lf)&(values<=uf)]

# KDE reference uses statsmodels' standard Silverman bandwidth and direct Gaussian evaluation.
bw=float(bw_silverman(values))
xs=np.linspace(values.min()-3*bw,values.max()+3*bw,32)
dens=np.mean(np.exp(-0.5*((xs[:,None]-values[None,:])/bw)**2)/(bw*np.sqrt(2*np.pi)),axis=1)

x=np.arange(1,13,dtype=float)
y=np.array([3.1,4.8,7.2,8.7,11.1,12.9,15.4,17.2,18.9,21.5,23.2,25.1])
lin=stats.linregress(x,y)
ols=sm.OLS(y,sm.add_constant(x)).fit()
ci_mean=stats.t.interval(.95,df=len(values)-1,loc=values.mean(),scale=stats.sem(values))

X=np.array([
 [1,2],[2,1],[3,4],[4,3],[5,6],[6,5],[7,8],[8,7],[9,10],[10,9],[11,12],[12,11]
],dtype=float)
y2=5+1.4*X[:,0]-0.7*X[:,1]+np.array([.2,-.1,.1,-.2,.3,-.2,.1,-.1,.2,-.2,.1,-.1])
ols2=sm.OLS(y2,sm.add_constant(X)).fit()

# 2^2 DOE with replicates.
doe=[]
for A in (-1,1):
  for B in (-1,1):
    for rep,noise in enumerate((-.2,.0,.2)):
      resp=20+3*A-2*B+1.5*A*B+noise
      doe.append({'A':A,'B':B,'response':resp})

def group_mean(key, val):
  arr=[r['response'] for r in doe if r[key]==val]
  return float(np.mean(arr))
mainA=[group_mean('A',-1),group_mean('A',1)]
mainB=[group_mean('B',-1),group_mean('B',1)]
cells=[[float(np.mean([r['response'] for r in doe if r['A']==a and r['B']==b])) for b in (-1,1)] for a in (-1,1)]
interaction=(cells[0][0]+cells[1][1]-cells[0][1]-cells[1][0])/2

# Response-surface fixture.
rs=[]
for a,b in [(-2,-2),(-2,0),(-2,2),(0,-2),(0,0),(0,2),(2,-2),(2,0),(2,2),(1,-1),(-1,1),(0,0)]:
  resp=50+2*a-3*b+0.8*a*a+0.4*b*b+1.2*a*b
  rs.append({'temp':a,'pressure':b,'yield':resp})
R=np.array([[1,r['temp'],r['pressure'],r['temp']**2,r['pressure']**2,r['temp']*r['pressure']] for r in rs],dtype=float)
ry=np.array([r['yield'] for r in rs])
rs_fit=sm.OLS(ry,R).fit()

# SPC fixtures.
individual=np.array([10.0,10.2,9.9,10.1,10.3,10.4,10.2,10.5,10.7,10.8,10.6,10.9],dtype=float)
mr=np.abs(np.diff(individual)); mrbar=float(mr.mean()); sigma_i=mrbar/1.128; center=float(individual.mean())

subgroups=np.array([
 [10.1,10.0,9.9,10.2,10.1],
 [10.2,10.3,10.1,10.2,10.4],
 [9.9,10.0,10.1,9.8,10.0],
 [10.4,10.5,10.3,10.4,10.6],
 [10.1,10.2,10.0,10.1,10.3],
 [10.3,10.4,10.2,10.5,10.4],
],dtype=float)
means=subgroups.mean(axis=1); ranges=np.ptp(subgroups,axis=1); xb=float(means.mean()); rb=float(ranges.mean())
A2,D3,D4,d2=.577,0,2.114,2.326

cusum_vals=np.array([10,10.1,9.9,10.0,10.2,10.5,10.7,10.9,11.0,11.1],dtype=float)
target=10.0; sigma=.25; k=.5; h=5
plus=minus=0.; cus=[]
for i,v in enumerate(cusum_vals):
  z=(v-target)/sigma; plus=max(0,plus+z-k); minus=min(0,minus+z+k)
  cus.append({'index':i,'cPlus':plus,'cMinus':minus,'signalPlus':bool(plus>h),'signalMinus':bool(-minus>h)})

lam=.2; L=3.; ew_target=10.; ew_sigma=.3; z=ew_target; ew=[]
for i,v in enumerate(cusum_vals):
  z=lam*v+(1-lam)*z
  sz=ew_sigma*math.sqrt(lam/(2-lam)*(1-(1-lam)**(2*(i+1))))
  ew.append({'index':i,'ewma':z,'sigmaZ':sz,'lcl':ew_target-L*sz,'ucl':ew_target+L*sz,'signal':bool(z<ew_target-L*sz or z>ew_target+L*sz)})

cap_vals=np.array([9.8,10.0,10.1,10.2,9.9,10.3,10.1,10.0,9.7,10.2],dtype=float)
cap_mu=float(cap_vals.mean()); cap_s=float(cap_vals.std(ddof=1)); lsl,usl=9.0,11.0
cp=(usl-lsl)/(6*cap_s); cpu=(usl-cap_mu)/(3*cap_s); cpl=(cap_mu-lsl)/(3*cap_s)

fixture={
 'distribution':{
  'values':values.tolist(),
  'describe':{'n':len(values),'min':float(values.min()),'q1':float(q[0]),'median':float(q[1]),'q3':float(q[2]),'max':float(values.max()),'mean':float(values.mean()),'variance':float(values.var(ddof=1)),'stddev':float(values.std(ddof=1))},
  'histogram4':{'edges':hedges.tolist(),'counts':hcounts.tolist()},
  'box':{'lowerFence':float(lf),'upperFence':float(uf),'lowerWhisker':float(inliers.min()),'upperWhisker':float(inliers.max()),'outliers':sorted(values[(values<lf)|(values>uf)].tolist())},
  'kde':{'bandwidth':bw,'x':xs.tolist(),'density':dens.tolist()},
  'mean_ci95':{'lower':float(ci_mean[0]),'upper':float(ci_mean[1]),'critical':float(stats.t.ppf(.975,len(values)-1))},
 },
 'simple_regression':{
  'x':x.tolist(),'y':y.tolist(),
  'slope':float(lin.slope),'intercept':float(lin.intercept),'r':float(lin.rvalue),'r2':float(lin.rvalue**2),
  'coefficients':ols.params.tolist(),'standardErrors':ols.bse.tolist(),'residuals':ols.resid.tolist(),'predicted':ols.fittedvalues.tolist(),'rmse':float(math.sqrt(ols.mse_resid)),
 },
 'multiple_regression':{'X':X.tolist(),'y':y2.tolist(),'coefficients':ols2.params.tolist(),'standardErrors':ols2.bse.tolist(),'r2':float(ols2.rsquared),'adjustedR2':float(ols2.rsquared_adj),'rmse':float(math.sqrt(ols2.mse_resid))},
 'doe':{'rows':doe,'mainA':mainA,'mainB':mainB,'interactionCells':cells,'interactionEffect':float(interaction)},
 'response_surface':{'rows':rs,'coefficients':rs_fit.params.tolist(),'r2':float(rs_fit.rsquared)},
 'individuals':{'values':individual.tolist(),'center':center,'mr':mr.tolist(),'mrbar':mrbar,'sigma':sigma_i,'iLcl':center-3*sigma_i,'iUcl':center+3*sigma_i,'mrUcl':3.267*mrbar},
 'xbarR':{'subgroups':subgroups.tolist(),'means':means.tolist(),'ranges':ranges.tolist(),'xbarbar':xb,'rbar':rb,'sigma':rb/d2,'xbarLcl':xb-A2*rb,'xbarUcl':xb+A2*rb,'rLcl':D3*rb,'rUcl':D4*rb},
 'cusum':{'values':cusum_vals.tolist(),'target':target,'sigma':sigma,'k':k,'h':h,'points':cus},
 'ewma':{'values':cusum_vals.tolist(),'target':ew_target,'sigma':ew_sigma,'lambda':lam,'L':L,'points':ew},
 'capability':{'values':cap_vals.tolist(),'lsl':lsl,'usl':usl,'mean':cap_mu,'sigma':cap_s,'cp':cp,'cpu':cpu,'cpl':cpl,'cpk':min(cpu,cpl)},
 'pareto':{'categories':['A','B','C','D'],'values':[12,5,20,3],'sorted':['C','A','B','D'],'cumulativePercent':[50,80,92.5,100]},
 'stacked':{'categories':['Q1','Q2'],'series':[{'name':'A','values':[20,10]},{'name':'B','values':[30,30]},{'name':'C','values':[50,60]}],'percent':[[20,10],[30,30],[50,60]]},
}
OUT.write_text(json.dumps(fixture,indent=2)+'\n')
print(OUT)
