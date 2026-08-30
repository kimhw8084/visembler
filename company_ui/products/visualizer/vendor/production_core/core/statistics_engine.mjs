/**
 * Visualizer renderer-independent numerical backend.
 *
 * Production constraints:
 * - deterministic pure functions
 * - no network / no runtime third-party dependency
 * - invalid assumptions throw typed NumericalContractError instead of emitting NaN UI
 * - renderer consumes these results; renderer never reimplements statistics
 */

export class NumericalContractError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'NumericalContractError';
    this.code = code;
    this.details = details;
  }
}

const EPS = 1e-12;
const SQRT_2PI = Math.sqrt(2 * Math.PI);

function fail(code, message, details = {}) { throw new NumericalContractError(code, message, details); }
function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
function kahanSum(values) {
  let sum = 0; let c = 0;
  for (const value of values) {
    const y = value - c;
    const t = sum + y;
    c = (t - sum) - y;
    sum = t;
  }
  return sum;
}
function finiteArray(values, { min = 1, name = 'values' } = {}) {
  if (!Array.isArray(values) || values.length < min) fail('DATA_LENGTH', `${name} requires at least ${min} finite value(s).`, { name, min });
  const out = values.map(Number);
  const bad = out.findIndex((v) => !finite(v));
  if (bad >= 0) fail('NON_FINITE', `${name}[${bad}] is not finite.`, { name, index: bad, value: values[bad] });
  return out;
}
function sorted(values) { return finiteArray(values).slice().sort((a, b) => a - b); }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function uniqueSorted(values) { return [...new Set(values)].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true })); }

export function mean(values) {
  const a = finiteArray(values);
  return kahanSum(a) / a.length;
}

export function variance(values, { sample = true } = {}) {
  const a = finiteArray(values, { min: sample ? 2 : 1 });
  const mu = mean(a);
  const ss = kahanSum(a.map((v) => (v - mu) ** 2));
  return ss / (a.length - (sample ? 1 : 0));
}

export function stddev(values, options = {}) { return Math.sqrt(variance(values, options)); }

export function quantile(values, q) {
  if (!finite(q) || q < 0 || q > 1) fail('QUANTILE_RANGE', 'q must be between 0 and 1.', { q });
  const a = sorted(values);
  if (a.length === 1) return a[0];
  // Hyndman & Fan type 7 (NumPy default / R default).
  const h = (a.length - 1) * q;
  const lo = Math.floor(h); const hi = Math.ceil(h); const t = h - lo;
  return a[lo] * (1 - t) + a[hi] * t;
}

export function describe(values) {
  const a = finiteArray(values);
  const q1 = quantile(a, 0.25); const median = quantile(a, 0.5); const q3 = quantile(a, 0.75);
  const mu = mean(a);
  const sampleVariance = a.length > 1 ? variance(a) : 0;
  const populationVariance = variance(a, { sample: false });
  return {
    n: a.length,
    min: Math.min(...a), q1, median, q3, max: Math.max(...a), iqr: q3 - q1,
    sum: kahanSum(a), mean: mu,
    variance: sampleVariance, stddev: Math.sqrt(sampleVariance),
    populationVariance, populationStddev: Math.sqrt(populationVariance),
  };
}

export function histogram(values, { bins = 'fd', minBins = 1, maxBins = 128 } = {}) {
  const a = finiteArray(values);
  const lo = Math.min(...a); const hi = Math.max(...a); const range = hi - lo;
  let count;
  if (Number.isInteger(bins)) {
    if (bins < 1) fail('HISTOGRAM_BINS', 'Explicit histogram bin count must be >= 1.', { bins });
    count = bins;
  }
  else if (range <= EPS) count = 1;
  else if (bins === 'sqrt') count = Math.ceil(Math.sqrt(a.length));
  else if (bins === 'sturges') count = Math.ceil(Math.log2(a.length) + 1);
  else if (bins === 'fd') {
    const iqr = quantile(a, 0.75) - quantile(a, 0.25);
    const width = 2 * iqr * Math.pow(a.length, -1 / 3);
    count = width > EPS ? Math.ceil(range / width) : Math.ceil(Math.sqrt(a.length));
  } else fail('HISTOGRAM_BINS', 'bins must be a positive integer or fd/sqrt/sturges.', { bins });
  count = clamp(Math.trunc(count), minBins, maxBins);
  if (count < 1) fail('HISTOGRAM_BINS', 'Histogram requires at least one bin.', { count });
  const width = range <= EPS ? Math.max(Math.abs(lo) * 0.02, 1) : range / count;
  const start = range <= EPS ? lo - width / 2 : lo;
  const edges = Array.from({ length: count + 1 }, (_, i) => start + i * width);
  const counts = Array(count).fill(0);
  for (const v of a) {
    let idx = Math.floor((v - start) / width);
    if (idx < 0) idx = 0;
    if (idx >= count) idx = count - 1;
    counts[idx] += 1;
  }
  return {
    bins: count, edges, counts, width,
    density: counts.map((c) => c / (a.length * width)),
    total: a.length,
  };
}

export function boxPlot(values, { whisker = 1.5 } = {}) {
  if (!finite(whisker) || whisker < 0) fail('BOX_WHISKER', 'whisker multiplier must be non-negative.', { whisker });
  const a = sorted(values);
  const q1 = quantile(a, 0.25); const median = quantile(a, 0.5); const q3 = quantile(a, 0.75); const iqr = q3 - q1;
  const lowerFence = q1 - whisker * iqr; const upperFence = q3 + whisker * iqr;
  const inliers = a.filter((v) => v >= lowerFence && v <= upperFence);
  return {
    n: a.length, q1, median, q3, iqr, lowerFence, upperFence,
    lowerWhisker: inliers.length ? inliers[0] : q1,
    upperWhisker: inliers.length ? inliers.at(-1) : q3,
    outliers: a.filter((v) => v < lowerFence || v > upperFence),
  };
}

export function ecdf(values) {
  const a = sorted(values);
  const points = [];
  let i = 0;
  while (i < a.length) {
    const x = a[i]; let j = i + 1;
    while (j < a.length && a[j] === x) j += 1;
    points.push({ x, count: j - i, cumulativeCount: j, p: j / a.length });
    i = j;
  }
  return { n: a.length, points };
}

export function kde(values, { points = 96, bandwidth = null, extent = null } = {}) {
  const a = finiteArray(values, { min: 2 });
  if (!Number.isInteger(points) || points < 8 || points > 2048) fail('KDE_POINTS', 'KDE points must be an integer from 8 to 2048.', { points });
  const d = describe(a);
  let bw = bandwidth;
  if (bw == null) {
    const robustSigma = d.iqr > EPS ? d.iqr / 1.349 : d.stddev;
    const scale = Math.min(d.stddev || robustSigma, robustSigma || d.stddev) || Math.max(Math.abs(d.mean) * 1e-3, 1e-6);
    bw = 0.9 * scale * Math.pow(a.length, -1 / 5);
  }
  if (!finite(bw) || bw <= 0) fail('KDE_BANDWIDTH', 'KDE bandwidth must be > 0.', { bandwidth: bw });
  const lo = extent?.[0] ?? d.min - 3 * bw; const hi = extent?.[1] ?? d.max + 3 * bw;
  if (!finite(lo) || !finite(hi) || hi <= lo) fail('KDE_EXTENT', 'KDE extent must be finite and increasing.', { extent: [lo, hi] });
  const xs = Array.from({ length: points }, (_, i) => lo + (hi - lo) * i / (points - 1));
  const density = xs.map((x) => kahanSum(a.map((v) => Math.exp(-0.5 * ((x - v) / bw) ** 2))) / (a.length * bw * SQRT_2PI));
  return { bandwidth: bw, x: xs, density };
}

// Acklam inverse-normal approximation. Sufficient for confidence-level plumbing.
export function inverseNormal(p) {
  if (!finite(p) || p <= 0 || p >= 1) fail('PROBABILITY_RANGE', 'Probability must be in (0,1).', { p });
  const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
  const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
  const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
  const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
  const plow = 0.02425; const phigh = 1 - plow;
  if (p < plow) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
  }
  if (p > phigh) {
    const q = Math.sqrt(-2 * Math.log(1-p));
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
  }
  const q = p - 0.5; const r = q*q;
  return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
}

export function tCritical(confidence, df) {
  if (!finite(confidence) || confidence <= 0 || confidence >= 1) fail('CONFIDENCE_RANGE', 'confidence must be in (0,1).', { confidence });
  if (!Number.isInteger(df) || df < 1) fail('DEGREES_FREEDOM', 'df must be a positive integer.', { df });
  // Cornish-Fisher expansion around Normal. Accurate to useful engineering tolerance for df>=2.
  if (df === 1 && Math.abs(confidence - 0.95) < 1e-12) return 12.706204736432095;
  const z = inverseNormal((1 + confidence) / 2); const v = df;
  const z2=z*z, z3=z2*z, z5=z3*z2, z7=z5*z2, z9=z7*z2;
  return z + (z3+z)/(4*v)
    + (5*z5+16*z3+3*z)/(96*v*v)
    + (3*z7+19*z5+17*z3-15*z)/(384*v**3)
    + (79*z9+776*z7+1482*z5-1920*z3-945*z)/(92160*v**4);
}

export function meanConfidenceInterval(values, { confidence = 0.95 } = {}) {
  const a = finiteArray(values, { min: 2 }); const mu = mean(a); const se = stddev(a) / Math.sqrt(a.length); const critical = tCritical(confidence, a.length - 1);
  return { n: a.length, mean: mu, se, confidence, critical, lower: mu - critical * se, upper: mu + critical * se };
}

function solveLinearSystem(A, b) {
  const n = A.length;
  if (!n || A.some((row) => !Array.isArray(row) || row.length !== n) || !Array.isArray(b) || b.length !== n) fail('MATRIX_SHAPE', 'Linear system must be square.');
  const m = A.map((row, i) => row.map(Number).concat(Number(b[i])));
  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let r = col + 1; r < n; r += 1) if (Math.abs(m[r][col]) > Math.abs(m[pivot][col])) pivot = r;
    if (Math.abs(m[pivot][col]) <= EPS) fail('SINGULAR_MATRIX', 'Design matrix is singular or ill-conditioned.', { column: col });
    [m[col], m[pivot]] = [m[pivot], m[col]];
    const div = m[col][col];
    for (let c = col; c <= n; c += 1) m[col][c] /= div;
    for (let r = 0; r < n; r += 1) {
      if (r === col) continue;
      const f = m[r][col];
      if (Math.abs(f) <= EPS) continue;
      for (let c = col; c <= n; c += 1) m[r][c] -= f * m[col][c];
    }
  }
  return m.map((row) => row[n]);
}

function invertMatrix(A) {
  const n = A.length; const cols = [];
  for (let j = 0; j < n; j += 1) cols.push(solveLinearSystem(A, Array.from({ length: n }, (_, i) => i === j ? 1 : 0)));
  return Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => cols[j][i]));
}
function dot(a, b) { return kahanSum(a.map((v, i) => v * b[i])); }
function quadraticForm(row, matrix) { return dot(row, matrix.map((r) => dot(r, row))); }

export function linearModel(features, response, { intercept = true, confidence = 0.95 } = {}) {
  if (!Array.isArray(features) || !features.length || !Array.isArray(features[0])) fail('DESIGN_SHAPE', 'features must be a non-empty matrix.');
  const y = finiteArray(response, { min: 2, name: 'response' });
  if (features.length !== y.length) fail('DESIGN_LENGTH', 'features and response must have the same row count.');
  const k = features[0].length;
  if (!k || features.some((row) => !Array.isArray(row) || row.length !== k)) fail('DESIGN_SHAPE', 'All feature rows must have the same non-zero width.');
  const raw = features.map((row, r) => row.map((v, c) => {
    const n = Number(v); if (!finite(n)) fail('NON_FINITE', `features[${r}][${c}] is not finite.`); return n;
  }));
  const X = raw.map((row) => intercept ? [1, ...row] : row.slice());
  const p = X[0].length; const n = X.length;
  if (n <= p) fail('REGRESSION_DF', 'Regression requires more observations than coefficients.', { observations: n, coefficients: p });
  const XtX = Array.from({ length: p }, (_, i) => Array.from({ length: p }, (_, j) => kahanSum(X.map((row) => row[i] * row[j]))));
  const Xty = Array.from({ length: p }, (_, i) => kahanSum(X.map((row, r) => row[i] * y[r])));
  const coefficients = solveLinearSystem(XtX, Xty);
  const predicted = X.map((row) => dot(row, coefficients));
  const residuals = y.map((v, i) => v - predicted[i]);
  const sse = kahanSum(residuals.map((v) => v*v)); const ybar = mean(y); const sst = kahanSum(y.map((v) => (v-ybar)**2));
  const dfResidual = n - p; const mse = sse / dfResidual; const rmse = Math.sqrt(mse); const r2 = sst <= EPS ? (sse <= EPS ? 1 : 0) : 1 - sse/sst;
  const adjustedR2 = 1 - (1-r2)*(n-1)/dfResidual;
  const covarianceBase = invertMatrix(XtX); const standardErrors = covarianceBase.map((row, i) => Math.sqrt(Math.max(0, row[i]*mse)));
  const critical = tCritical(confidence, dfResidual);
  const coefficientCI = coefficients.map((b, i) => ({ lower:b-critical*standardErrors[i], upper:b+critical*standardErrors[i] }));
  const leverage = X.map((row) => quadraticForm(row, covarianceBase));
  const standardizedResiduals = residuals.map((r, i) => r / Math.sqrt(Math.max(EPS, mse*(1-leverage[i]))));
  return { n, p, intercept, coefficients, standardErrors, coefficientCI, predicted, residuals, standardizedResiduals, leverage, sse, mse, rmse, r2, adjustedR2, dfResidual, confidence, critical, covarianceBase };
}

export function linearRegression(x, y, options = {}) {
  const xa = finiteArray(x, { min: 3, name: 'x' }); const ya = finiteArray(y, { min: 3, name: 'y' });
  if (xa.length !== ya.length) fail('PAIR_LENGTH', 'x and y must have equal length.');
  const model = linearModel(xa.map((v) => [v]), ya, options);
  const slope = model.coefficients[1]; const intercept = model.coefficients[0];
  const sx = stddev(xa); const sy = stddev(ya); const covariance = kahanSum(xa.map((v,i) => (v-mean(xa))*(ya[i]-mean(ya))))/(xa.length-1);
  const r = sx <= EPS || sy <= EPS ? 0 : covariance/(sx*sy);
  return { ...model, interceptValue: intercept, slope, r };
}

export function residualDiagnostics(features, response, options = {}) {
  const model = linearModel(features, response, options);
  return model.residuals.map((residual, i) => ({ index:i, predicted:model.predicted[i], actual:Number(response[i]), residual, standardizedResidual:model.standardizedResiduals[i], leverage:model.leverage[i] }));
}

export function doeMainEffects(rows, { factors, response }) {
  if (!Array.isArray(rows) || !rows.length || !Array.isArray(factors) || !factors.length || typeof response !== 'string') fail('DOE_SCHEMA', 'DOE requires rows, factors, and response.');
  return factors.map((factor) => {
    const levels = uniqueSorted(rows.map((r) => r[factor]));
    if (levels.length < 2) fail('DOE_LEVELS', `Factor ${factor} requires at least two levels.`);
    const byLevel = levels.map((level) => {
      const values = finiteArray(rows.filter((r) => r[factor] === level).map((r) => Number(r[response])), { name: `${factor}:${level}` });
      return { level, n: values.length, mean: mean(values) };
    });
    return { factor, levels: byLevel, effect: byLevel.length === 2 ? byLevel[1].mean - byLevel[0].mean : null };
  });
}

export function doeInteraction(rows, { factorA, factorB, response }) {
  if (!Array.isArray(rows) || !rows.length) fail('DOE_SCHEMA', 'DOE rows are required.');
  const levelsA = uniqueSorted(rows.map((r) => r[factorA])); const levelsB = uniqueSorted(rows.map((r) => r[factorB]));
  if (levelsA.length < 2 || levelsB.length < 2) fail('DOE_LEVELS', 'Interaction plot requires at least two levels per factor.');
  const cells = levelsA.map((a) => levelsB.map((b) => {
    const vals = finiteArray(rows.filter((r) => r[factorA] === a && r[factorB] === b).map((r) => Number(r[response])), { name: `${factorA}:${a}/${factorB}:${b}` });
    return { a, b, n: vals.length, mean: mean(vals) };
  }));
  let interactionEffect = null;
  if (levelsA.length === 2 && levelsB.length === 2) interactionEffect = (cells[0][0].mean + cells[1][1].mean - cells[0][1].mean - cells[1][0].mean) / 2;
  return { factorA, factorB, levelsA, levelsB, cells, interactionEffect };
}

export function fitResponseSurface(rows, { x1, x2, response, confidence = 0.95 }) {
  if (!Array.isArray(rows) || rows.length < 7) fail('RESPONSE_SURFACE_ROWS', 'Second-order response surface requires at least 7 observations.');
  const features = rows.map((r) => {
    const a=Number(r[x1]); const b=Number(r[x2]);
    if (!finite(a)||!finite(b)) fail('NON_FINITE','Response-surface factors must be finite.');
    return [a,b,a*a,b*b,a*b];
  });
  const y=rows.map((r)=>Number(r[response]));
  const fit=linearModel(features,y,{intercept:true,confidence});
  const names=['intercept',x1,x2,`${x1}^2`,`${x2}^2`,`${x1}*${x2}`];
  return { ...fit, coefficientNames:names, namedCoefficients:Object.fromEntries(names.map((name,i)=>[name,fit.coefficients[i]])) };
}

const XR_CONSTANTS = {
  2:{A2:1.880,D3:0,D4:3.267,d2:1.128}, 3:{A2:1.023,D3:0,D4:2.574,d2:1.693}, 4:{A2:0.729,D3:0,D4:2.282,d2:2.059},
  5:{A2:0.577,D3:0,D4:2.114,d2:2.326}, 6:{A2:0.483,D3:0,D4:2.004,d2:2.534}, 7:{A2:0.419,D3:0.076,D4:1.924,d2:2.704},
  8:{A2:0.373,D3:0.136,D4:1.864,d2:2.847}, 9:{A2:0.337,D3:0.184,D4:1.816,d2:2.970}, 10:{A2:0.308,D3:0.223,D4:1.777,d2:3.078},
};

export function westernElectricRules(values, { center = null, sigma = null } = {}) {
  const a=finiteArray(values,{min:2}); const c=center??mean(a); const s=sigma??stddev(a);
  if (!finite(s)||s<=0) fail('SPC_SIGMA','SPC sigma must be > 0.',{sigma:s});
  const z=a.map((v)=>(v-c)/s); const signals=[]; const seen=new Set();
  const add=(rule,end,start=end)=>{const key=`${rule}:${start}:${end}`;if(!seen.has(key)){seen.add(key);signals.push({rule,start,end,indices:Array.from({length:end-start+1},(_,i)=>start+i)});}};
  z.forEach((v,i)=>{if(Math.abs(v)>3)add('WE1',i);});
  for(let i=2;i<z.length;i++){
    const w=z.slice(i-2,i+1); if(w.filter(v=>v>2).length>=2||w.filter(v=>v<-2).length>=2)add('WE2',i,i-2);
  }
  for(let i=4;i<z.length;i++){
    const w=z.slice(i-4,i+1); if(w.filter(v=>v>1).length>=4||w.filter(v=>v<-1).length>=4)add('WE3',i,i-4);
  }
  for(let i=7;i<z.length;i++){
    const w=z.slice(i-7,i+1); if(w.every(v=>v>0)||w.every(v=>v<0))add('WE4',i,i-7);
  }
  return { center:c, sigma:s, z, signals };
}

export function individualsMovingRange(values) {
  const a=finiteArray(values,{min:2}); const center=mean(a); const movingRanges=a.slice(1).map((v,i)=>Math.abs(v-a[i])); const mrbar=mean(movingRanges); const sigma=mrbar/XR_CONSTANTS[2].d2;
  if (sigma<=EPS) fail('SPC_SIGMA','Moving-range estimate is zero; control limits are undefined.');
  const iLimits={center,lcl:center-3*sigma,ucl:center+3*sigma};
  const mrLimits={center:mrbar,lcl:0,ucl:XR_CONSTANTS[2].D4*mrbar};
  return { values:a,movingRanges,mrbar,sigma,iLimits,mrLimits,rules:westernElectricRules(a,{center,sigma}) };
}

export function xbarR(subgroups) {
  if(!Array.isArray(subgroups)||subgroups.length<2)fail('SUBGROUPS','Xbar-R requires at least two subgroups.');
  const groups=subgroups.map((g,i)=>finiteArray(g,{min:2,name:`subgroup[${i}]`})); const n=groups[0].length;
  if(groups.some(g=>g.length!==n))fail('SUBGROUP_SIZE','Xbar-R requires constant subgroup size.');
  const constants=XR_CONSTANTS[n]; if(!constants)fail('SUBGROUP_SIZE','Xbar-R supports subgroup sizes 2..10.',{n});
  const means=groups.map(mean); const ranges=groups.map(g=>Math.max(...g)-Math.min(...g)); const xbarbar=mean(means); const rbar=mean(ranges); const sigma=rbar/constants.d2;
  return {n,means,ranges,xbarbar,rbar,sigma,constants,xbarLimits:{center:xbarbar,lcl:xbarbar-constants.A2*rbar,ucl:xbarbar+constants.A2*rbar},rLimits:{center:rbar,lcl:constants.D3*rbar,ucl:constants.D4*rbar},rules:westernElectricRules(means,{center:xbarbar,sigma:sigma/Math.sqrt(n)})};
}

export function cusum(values,{target=null,sigma=null,k=0.5,h=5}={}){
  const a=finiteArray(values,{min:2}); const t=target??mean(a); const s=sigma??stddev(a);
  if(!finite(s)||s<=0)fail('SPC_SIGMA','CUSUM sigma must be > 0.'); if(!finite(k)||k<0||!finite(h)||h<=0)fail('CUSUM_PARAMS','CUSUM requires k>=0 and h>0.');
  let plus=0,minus=0; const points=a.map((v,i)=>{const z=(v-t)/s;plus=Math.max(0,plus+z-k);minus=Math.min(0,minus+z+k);return{index:i,value:v,z,cPlus:plus,cMinus:minus,signalPlus:plus>h,signalMinus:-minus>h};});
  return{target:t,sigma:s,k,h,points,signals:points.filter(p=>p.signalPlus||p.signalMinus).map(p=>p.index)};
}

export function ewma(values,{target=null,sigma=null,lambda=0.2,L=3}={}){
  const a=finiteArray(values,{min:2}); const t=target??mean(a); const s=sigma??stddev(a);
  if(!finite(s)||s<=0)fail('SPC_SIGMA','EWMA sigma must be > 0.'); if(!finite(lambda)||lambda<=0||lambda>1||!finite(L)||L<=0)fail('EWMA_PARAMS','EWMA requires 0<lambda<=1 and L>0.');
  let z=t; const points=a.map((v,i)=>{z=lambda*v+(1-lambda)*z;const sigmaZ=s*Math.sqrt(lambda/(2-lambda)*(1-(1-lambda)**(2*(i+1))));const lcl=t-L*sigmaZ,ucl=t+L*sigmaZ;return{index:i,value:v,ewma:z,sigmaZ,lcl,ucl,signal:z<lcl||z>ucl};});
  return{target:t,sigma:s,lambda,L,points,signals:points.filter(p=>p.signal).map(p=>p.index)};
}

export function processCapability(values,{lsl=null,usl=null,target=null}={}){
  const a=finiteArray(values,{min:2}); if(lsl==null&&usl==null)fail('SPEC_LIMITS','At least one specification limit is required.');
  if(lsl!=null&&!finite(Number(lsl))||usl!=null&&!finite(Number(usl)))fail('SPEC_LIMITS','Specification limits must be finite.');
  if(lsl!=null&&usl!=null&&Number(usl)<=Number(lsl))fail('SPEC_LIMITS','USL must be greater than LSL.');
  const mu=mean(a),sigma=stddev(a); if(sigma<=EPS)fail('SPC_SIGMA','Capability is undefined for zero variation.');
  const cpu=usl==null?null:(Number(usl)-mu)/(3*sigma); const cpl=lsl==null?null:(mu-Number(lsl))/(3*sigma); const cp=lsl==null||usl==null?null:(Number(usl)-Number(lsl))/(6*sigma); const cpk=cpu==null?cpl:cpl==null?cpu:Math.min(cpu,cpl);
  return{n:a.length,mean:mu,sigma,lsl:lsl==null?null:Number(lsl),usl:usl==null?null:Number(usl),target:target==null?null:Number(target),cp,cpu,cpl,cpk};
}

export function pareto(categories, values) {
  if(!Array.isArray(categories)||!Array.isArray(values)||categories.length!==values.length||!categories.length)fail('PARETO_DATA','Pareto requires equal non-empty category/value arrays.');
  const v=values.map((x,i)=>{const n=Number(x);if(!finite(n)||n<0)fail('PARETO_VALUE','Pareto values must be finite and non-negative.',{index:i,value:x});return n;});
  const rows=categories.map((category,i)=>({category,value:v[i],sourceIndex:i})).sort((a,b)=>b.value-a.value||a.sourceIndex-b.sourceIndex); const total=kahanSum(v); let cumulative=0;
  rows.forEach(r=>{cumulative+=r.value;r.cumulative=cumulative;r.cumulativePercent=total<=EPS?0:cumulative/total*100;});
  return{total,rows};
}

export function normalizeStackedSeries(categories, series, { percent = false } = {}) {
  if(!Array.isArray(categories)||!categories.length||!Array.isArray(series)||!series.length)fail('STACK_DATA','Stacked chart requires categories and series.');
  const clean=series.map((s,si)=>{if(!s||typeof s.name!=='string'||!Array.isArray(s.values)||s.values.length!==categories.length)fail('STACK_DATA','Each stacked series requires a name and a value per category.',{series:si});return{name:s.name,values:s.values.map((v,i)=>{const n=Number(v);if(!finite(n)||(percent&&n<0))fail('STACK_VALUE',percent?'100% stacked values must be finite and non-negative.':'Stacked values must be finite.',{series:si,index:i,value:v});return n;})};});
  const totals=categories.map((_,i)=>kahanSum(clean.map(s=>s.values[i]))); if(percent&&totals.some(t=>t<=EPS))fail('STACK_ZERO_TOTAL','100% stacked categories require positive totals.');
  const normalized=clean.map(s=>({name:s.name,values:s.values.map((v,i)=>percent?v/totals[i]*100:v)}));
  return{categories:categories.slice(),series:normalized,totals,percent};
}

export function stepSeries(x,y,{where='post'}={}){
  const xa=finiteArray(x,{min:2,name:'x'}),ya=finiteArray(y,{min:2,name:'y'});if(xa.length!==ya.length)fail('PAIR_LENGTH','x and y must have equal length.');if(!['pre','post'].includes(where))fail('STEP_WHERE','where must be pre or post.');
  const points=[{x:xa[0],y:ya[0]}]; for(let i=1;i<xa.length;i++){if(where==='post'){points.push({x:xa[i],y:ya[i-1]},{x:xa[i],y:ya[i]});}else{points.push({x:xa[i-1],y:ya[i]},{x:xa[i],y:ya[i]});}} return{where,points};
}
