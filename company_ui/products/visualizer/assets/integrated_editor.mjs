import {
  EditorStore,
  RevisionConflictError,
  parseCanonical,
  serializeCanonical,
} from '../vendor/production_core/core/editor_store.mjs';
import { ELEMENTS_BY_ENGINE } from '../vendor/production_core/core/runtime_registry.mjs';
import { renderIntegratedElement } from './element_renderer.mjs';
import { intakeText, datasetFromIntake, parseGridText as parseUniversalGridText } from './authoring_data.mjs';
import { applyRecipe } from './authoring_transforms.mjs';
import { contractFor } from './authoring_contracts.mjs';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const storage = { get(key) { try { return localStorage.getItem(key); } catch { return null; } }, set(key, value) { try { localStorage.setItem(key, value); return true; } catch { return false; } }, remove(key) { try { localStorage.removeItem(key); } catch { /* unavailable */ } } };
function storageJson(key, fallback) { try { const raw=storage.get(key); return raw==null?fallback:JSON.parse(raw); } catch { storage.remove(key); return fallback; } }
const BASE_CANVAS_H = 675;
const MAX_CANVAS_H = 4800;
const SCENE = { w: 1300, h: 820 };
const CANVAS = { x: 50, y: 55, w: 1200, h: BASE_CANVAS_H, gap: 14 };
const BRIDGE_VERSION = 1;
const MAX_BRIDGE_BYTES = 2_000_000;
const MAX_MODEL_BYTES = 1_500_000;
const MAX_IMAGE_BYTES = 750_000;
const AUTHORING_VERSION = 'v0.3.5';
const bootstrap = window.__CUI_VISUALIZER_BOOTSTRAP__ || {};
let activeRoot = null;
let eventAbort = null;
let personalPresets = [];
let presetRenderFrame = 0;

const typeDefaults = {
  metric: { title: 'Hero KPI', weight: 1.15, minW: 180, minH: 130 },
  chart: { title: 'Line Chart', weight: 1.8, minW: 270, minH: 180 },
  text: { title: 'Key Takeaway', weight: 1.1, minW: 190, minH: 120 },
  table: { title: 'Clean Table', weight: 1.55, minW: 250, minH: 190 },
  tabs: { title: 'Tabs / View Switcher', weight: 1.15, minW: 210, minH: 150 },
  timeline: { title: 'Event Timeline', weight: 1.3, minW: 270, minH: 140 },
  image: { title: 'Image', weight: 1.25, minW: 220, minH: 150 },
  diagram: { title: 'Process Flow', weight: 1.5, minW: 290, minH: 170 },
  risk: { title: 'Risk Callout', weight: 1, minW: 200, minH: 130 },
  comparison: { title: 'Before/After KPI', weight: 1.15, minW: 220, minH: 140 },
  matrix: { title: 'Decision Matrix', weight: 1.35, minW: 250, minH: 180 },
  evidence: { title: 'Evidence Card', weight: 1.15, minW: 220, minH: 150 },
  decision: { title: 'Decision Needed', weight: 1.15, minW: 220, minH: 150 },
  project: { title: 'Project Card', weight: 1.15, minW: 220, minH: 150 },
  engineering: { title: 'SPC Control Chart', weight: 1.5, minW: 270, minH: 180 },
  wafer: { title: 'Wafer Map', weight: 1.5, minW: 260, minH: 190 },
  layout: { title: 'Smart Canvas', weight: 1.0, minW: 210, minH: 130 },
  interaction: { title: 'Cross-filter', weight: 1.0, minW: 210, minH: 130 },
  editor: { title: 'Right Inspector', weight: 1.0, minW: 210, minH: 130 },
};
const engineToType = Object.freeze({SmartLayoutEngine:'layout',TextEngine:'text',MetricEngine:'metric',ComparisonEngine:'comparison',CoreChartEngine:'chart',TableEngine:'table',MatrixEngine:'matrix',TimelineEngine:'timeline',DiagramEngine:'diagram',ImageMediaEngine:'image',EvidenceCompositeEngine:'evidence',DecisionCompositeEngine:'decision',ProjectCompositeEngine:'project',EngineeringChartEngine:'engineering',WaferFabEngine:'wafer',InteractionLayer:'interaction',EditorInfrastructure:'editor'});
const quickCanonical = Object.freeze({metric:['Hero KPI','MetricEngine'],chart:['Line Chart','CoreChartEngine'],text:['Key Takeaway','TextEngine'],table:['Clean Table','TableEngine'],tabs:['Tabs / View Switcher','SmartLayoutEngine'],timeline:['Event Timeline','TimelineEngine'],image:['Image','ImageMediaEngine'],diagram:['Process Flow','DiagramEngine'],risk:['Risk Callout','DecisionCompositeEngine']});

const defaultChartData = [['Collect', 84], ['Normalize', 71], ['Reason', 48], ['Verify', 31], ['Close', 14]];
function chartStarterData(element='') {
  const name=String(element).toLowerCase();
  if(name.includes('funnel')) return [['Visited',1200],['Qualified',760],['Validated',410],['Approved',185]];
  if(name.includes('pareto')) return [['Pressure',38],['Temperature',26],['Recipe',17],['Alignment',11],['Other',8]];
  if(name.includes('pie')||name.includes('donut')) return [['On track',62],['Watch',25],['At risk',13]];
  if(name.includes('scatter')||name.includes('bubble')) return [['Lot A',64],['Lot B',72],['Lot C',68],['Lot D',81],['Lot E',77],['Lot F',89]];
  return [['Baseline',72],['Pilot',78],['Validation',84],['Release',91],['Sustain',94]];
}
function timelineStarter() { return [{label:'Discover',date:'Week 1'},{label:'Validate',date:'Week 2'},{label:'Implement',date:'Week 3'},{label:'Verify',date:'Week 4'}]; }
function diagramStarter() { return {nodes:['Signal','Analyze','Validate','Decision'],edges:[['Signal','Analyze'],['Analyze','Validate'],['Validate','Decision']],direction:'right'}; }
function starterContent(engine, element) {
  if(engine==='MetricEngine') return {value:84.2,unit:'%',delta:6.4,target:90,detail:false};
  if(engine==='ComparisonEngine') return {before:62,after:91,unit:'%'};
  if(engine==='CoreChartEngine') { const data=chartStarterData(element); return {variant:'line',data,rows:data.map(([label,value])=>({label,value})),brush:[0,data.length-1],cross:null,drill:null,revealed:true}; }
  if(engine==='TextEngine') return {text:'State the insight, evidence, and intended decision in one clear sentence.',body:'State the insight, evidence, and intended decision in one clear sentence.'};
  if(engine==='TableEngine') { const rows=[['Yield','98.7%','On track'],['Cycle time','42.8 min','Improving'],['Risk','Low','Monitored']]; return {customTable:{headers:['Measure','Current','Status'],rows},rows}; }
  if(engine==='MatrixEngine') return {matrix:[['Impact','Low','Medium','High'],['Likelihood','2','3','4'],['Priority','Monitor','Plan','Act']]};
  if(engine==='TimelineEngine') return {milestones:timelineStarter(),tm:1};
  if(engine==='DiagramEngine') return diagramStarter();
  if(engine==='ImageMediaEngine') return {src:'',alt:'',caption:'',fit:'fill',focal:'50% 50%'};
  if(engine==='EvidenceCompositeEngine') return {statement:'Pressure excursion aligns with defect onset.',detail:'Validate with a matched control lot before closure.',status:'Observed'};
  if(engine==='DecisionCompositeEngine') return {statement:'Approve the controlled validation path.',detail:'The option reduces cycle time while keeping the change reversible.',status:'Open'};
  if(engine==='ProjectCompositeEngine') return {statement:'Validate chamber recovery.',detail:'Owner: Process Engineering · due Friday · verify with control lot.',status:'Planned'};
  if(engine==='EngineeringChartEngine') return {observations:[{label:'1',value:98.2},{label:'2',value:98.8},{label:'3',value:98.5},{label:'4',value:99.1},{label:'5',value:98.9}],role:'measurement',lower_limit:97.5,upper_limit:99.5,lcl:97.5,ucl:99.5};
  if(engine==='WaferFabEngine') return {observations:[{x:1,y:1,value:98.4},{x:2,y:1,value:98.8},{x:3,y:2,value:97.9},{x:2,y:3,value:98.6}],tool:'ETCH-04',chamber:'B',lot:'24-118',route:'ETCH → MET'};
  if(engine==='SmartLayoutEngine') return {configuration:'14px governed composition'};
  if(engine==='InteractionLayer') return {behavior:'select → filter → inspect'};
  if(engine==='EditorInfrastructure') return {configuration:'Editor-only infrastructure'};
  return {};
}
const initialItems = [
  { id: 'c1', type: 'metric', title: 'Investigation Time', weight: 1.1, order: 0, value: 92, detail: false, locked: false, z: 1 },
  { id: 'c2', type: 'chart', title: 'Investigation Trend', weight: 1.85, order: 1, variant: 'line', data: defaultChartData, brush: [0, 4], cross: null, drill: null, revealed: true, locked: false, z: 2 },
  { id: 'c3', type: 'text', title: 'Key Takeaway', weight: 1.05, order: 2, locked: false, z: 3 },
  { id: 'c4', type: 'table', title: 'Evidence Log', weight: 1.5, order: 3, locked: false, z: 4 },
  { id: 'c5', type: 'tabs', title: 'Investigation Summary', weight: 1.05, order: 4, tab: 'Summary', expanded: false, locked: false, z: 5 },
  { id: 'c6', type: 'timeline', title: 'Validation Path', weight: 1.35, order: 5, tm: 2, locked: false, z: 6 },
];

let store = new EditorStore(parseCanonical(bootstrap.model || {
  schema_version: 1,
  items: structuredClone(initialItems), groups: {}, mode: 'smart', layoutPreset: 'editorial', crossFilter: null, nextId: 20,
}), { revision: Number.isInteger(bootstrap.revision) ? bootstrap.revision : 1 });

const ui = {
  zoom: 1,
  selected: new Set(),
  lasso: null,
  space: false,
  snap: true,
  showMini: true,
  preview: false,
  autoFit: true,
  previewPatches: new Map(),
  kpiAnimate: new Set(['c1']),
  pointerSession: null,
  modalReturnFocus: null,
  commandIndex: 0,
  resizeEpoch: 0,
  componentNodes: new Map(),
  minimapNodes: new Map(),
  contextSignature: '',
  contextSize: null,
  contextBoundsCache: null,
  lastPreflight: null,
  inspectorOpen: true,
  libraryLimit: 60,
  pendingCommits: new Map(),
  intrinsicOverrides: new Map(),
  smartLayoutConflict: null,
  libraryTab: 'elements',
  favorites: new Set(Array.isArray(storageJson('viz-library-favorites',[]))?storageJson('viz-library-favorites',[]):[]),
  recentElements: Array.isArray(storageJson('viz-library-recent',[]))?storageJson('viz-library-recent',[]):[],
  guideEpoch: 0,
  guideReason: 'initial',
  contentMeasurePass: 0,
  debugLog: [],
  debugSequence: 0,
  semanticClipboard: null,
  dataDockCell: null,
  dataDockRange: null,
  dataDockFilter: '',
};

function model() { return store.model; }
function item(id) { return model().items.find((entry) => entry.id === id); }
function esc(value) { return String(value ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }
function overlap(a, b, p = 0) { return !(a.x + a.w + p <= b.x || b.x + b.w + p <= a.x || a.y + a.h + p <= b.y || b.y + b.h + p <= a.y); }
function intersectionArea(a, b) {
  const w = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  const h = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  return w * h;
}
function rectUnion(rects) {
  if (!rects.length) return null;
  return {
    x: Math.min(...rects.map((r) => r.x)),
    y: Math.min(...rects.map((r) => r.y)),
    w: Math.max(...rects.map((r) => r.x + r.w)) - Math.min(...rects.map((r) => r.x)),
    h: Math.max(...rects.map((r) => r.y + r.h)) - Math.min(...rects.map((r) => r.y)),
  };
}

function viewItem(entry) {
  const patch = ui.previewPatches.get(entry.id);
  return patch ? { ...entry, ...patch } : entry;
}
function viewItems() { return model().items.map(viewItem); }
function defaultEmphasis(entry) {
  const name=String(entry.element||entry.title||'').toLowerCase();
  if (entry.emphasis && ['compact','standard','prominent','hero'].includes(entry.emphasis)) return entry.emphasis;
  if (name.includes('hero') || name==='executive statement') return 'hero';
  if (name.includes('section divider') || name.includes('spacer') || name.includes('metadata') || name.includes('footnote') || name.includes('eyebrow')) return 'compact';
  if (name.includes('decision needed') || name.includes('recommendation') || name.includes('key takeaway')) return 'prominent';
  return 'standard';
}
function semanticPolicy(entry) {
  const d=typeDefaults[entry.type]||typeDefaults.text;
  const name=String(entry.element||entry.title||'').toLowerCase();
  const engine=entry.engine||'';
  let p={minW:d.minW,minH:d.minH,prefW:Math.max(d.minW,320),prefH:Math.max(d.minH,180),maxW:CANVAS.w-2*CANVAS.gap,maxH:900,growth:'balanced',aspect:null};
  if(engine==='MetricEngine') {
    p={...p,minW:190,minH:128,prefW:270,prefH:150,growth:'horizontal'};
    if(name.includes('hero kpi')) p={...p,minW:280,minH:145,prefW:420,prefH:170};
    if(name.includes('pair')||name.includes('strip')) p={...p,minW:300,minH:128,prefW:390,prefH:145};
    if(name.includes('ring')) p={...p,minW:205,minH:205,prefW:245,prefH:245,aspect:1,growth:'square'};
    if(name.includes('ladder')) p={...p,minW:235,minH:185,prefW:300,prefH:205};
    if(name.includes('sparkline')) p={...p,minW:235,minH:165,prefW:320,prefH:185};
    if(name.includes('confidence')) p={...p,minW:245,minH:165,prefW:330,prefH:185};
    if(name.includes('threshold')||name.includes('target')||name.includes('progress')||name.includes('capacity')||name.includes('rate')) p={...p,minW:225,minH:150,prefW:310,prefH:170};
  } else if(engine==='CoreChartEngine') {
    p={...p,minW:320,minH:220,prefW:470,prefH:270,growth:'plot'};
    if(name==='sparkline') p={...p,minW:240,minH:130,prefW:340,prefH:150};
    if(name.includes('donut')||name.includes('pie')) p={...p,minW:235,minH:235,prefW:285,prefH:285,aspect:1,growth:'square'};
    if(name.includes('sankey')||name.includes('treemap')||name.includes('funnel')) p={...p,minW:350,minH:220,prefW:500,prefH:260};
  } else if(engine==='EngineeringChartEngine') {
    p={...p,minW:330,minH:225,prefW:480,prefH:270,growth:'plot'};
    if(name.includes('response surface')||name.includes('contour')) p={...p,minW:310,minH:245,prefW:420,prefH:300};
  } else if(engine==='TableEngine') {
    p={...p,minW:340,minH:210,prefW:480,prefH:260,growth:'data'};
    if(name.includes('dense')) p={...p,minH:235,prefH:300};
  } else if(engine==='MatrixEngine') {
    p={...p,minW:290,minH:220,prefW:390,prefH:270,growth:'square'};
    if(name.includes('risk matrix')||name.includes('heatmap')||name.includes('correlation')) p={...p,minW:260,minH:250,prefW:320,prefH:300,aspect:1};
  } else if(engine==='TimelineEngine') {
    p={...p,minW:360,minH:165,prefW:520,prefH:195,growth:'horizontal'};
    if(name.includes('vertical')) p={...p,minW:245,minH:285,prefW:300,prefH:340,growth:'vertical'};
    if(name.includes('gantt')||name.includes('swimlane')||name.includes('roadmap')||name.includes('schedule')) p={...p,minW:390,minH:220,prefW:560,prefH:260};
  } else if(engine==='DiagramEngine') {
    p={...p,minW:340,minH:225,prefW:480,prefH:275,growth:'plot'};
    if(name.includes('architecture')||name.includes('swimlane')||name.includes('sequence')) p={...p,minW:380,minH:245,prefW:540,prefH:300};
    if(name.includes(' node')) p={...p,minW:190,minH:135,prefW:240,prefH:155,growth:'balanced'};
  } else if(engine==='ImageMediaEngine') {
    p={...p,minW:280,minH:190,prefW:420,prefH:260,growth:'media',aspect:16/10};
    if(name.includes('hero image')) p={...p,minW:400,minH:220,prefW:620,prefH:310,aspect:16/9};
    if(name.includes('before/after')||name.includes('gallery')||name.includes('slider')) p={...p,minW:360,minH:220,prefW:520,prefH:280};
  } else if(engine==='WaferFabEngine') {
    p={...p,minW:260,minH:250,prefW:320,prefH:310,growth:'square',aspect:1};
    if(name.includes('matrix')||name.includes('timeline')||name.includes('profile')||name.includes('distribution')||name.includes('route diagram')) p={...p,minW:340,minH:220,prefW:480,prefH:260,aspect:null,growth:'plot'};
  } else if(engine==='TextEngine') {
    p={...p,minW:260,minH:125,prefW:390,prefH:165,growth:'text'};
    if(name.includes('hero title')) p={...p,minW:420,minH:135,prefW:700,prefH:160};
    if(name.includes('body narrative')||name.includes('narrative sequence')) p={...p,minW:320,minH:190,prefW:500,prefH:240};
    if(name.includes('section heading')||name.includes('eyebrow')||name.includes('footnote')||name.includes('metadata')) p={...p,minW:260,minH:76,prefW:440,prefH:92};
  } else if(engine==='ComparisonEngine') {
    p={...p,minW:300,minH:175,prefW:430,prefH:210,growth:'horizontal'};
  } else if(['EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'].includes(engine)) {
    p={...p,minW:280,minH:180,prefW:400,prefH:220,growth:'text'};
    if(name.includes('hero')) p={...p,minW:380,minH:190,prefW:540,prefH:230};
    if(name.includes('grid')||name.includes('register')||name.includes('cluster')) p={...p,minW:340,minH:220,prefW:470,prefH:270};
  } else if(engine==='SmartLayoutEngine') {
    p={...p,minW:230,minH:150,prefW:360,prefH:210,growth:'balanced'};
    if(name.includes('section divider')||name.includes('spacer')) p={...p,minW:320,minH:64,prefW:520,prefH:74,growth:'horizontal'};
  } else if(engine==='InteractionLayer'||engine==='EditorInfrastructure') {
    p={...p,minW:230,minH:155,prefW:330,prefH:195,growth:'balanced'};
  }
  const emphasis=defaultEmphasis(entry);
  const scale={compact:.84,standard:1,prominent:1.18,hero:1.38}[emphasis]||1;
  p.prefW=Math.min(p.maxW,Math.max(p.minW,p.prefW*scale));
  p.prefH=Math.min(p.maxH,Math.max(p.minH,p.prefH*(emphasis==='hero'?1.12:emphasis==='compact'?.9:1)));
  const measured=ui.intrinsicOverrides.get(entry.id);
  if(measured){p.minW=Math.max(p.minW,measured.w||0);p.minH=Math.max(p.minH,measured.h||0);p.prefW=Math.max(p.prefW,p.minW);p.prefH=Math.max(p.prefH,p.minH);}
  return {...p,emphasis};
}
function effectiveWeight(entry) {
  const emphasis=defaultEmphasis(entry);
  const base={compact:.72,standard:1,prominent:1.35,hero:1.8}[emphasis]||1;
  const raw=Number.isFinite(+entry.weight)?+entry.weight:1;
  const advanced=clamp(raw,.45,3.4);
  const preset=model().layoutPreset==='executive'?(entry.engine==='MetricEngine'||entry.engine==='DecisionCompositeEngine'||entry.engine==='TextEngine'?1.18:.96):model().layoutPreset==='technical'?(['TableEngine','DiagramEngine','TimelineEngine','EngineeringChartEngine','WaferFabEngine'].includes(entry.engine)?1.18:.92):1;
  return base*Math.sqrt(advanced)*preset;
}
function allocateRowWidths(row, innerW, gap) {
  const available=Math.max(1,innerW-gap*(row.length-1));
  const mins=row.map(({policy})=>Math.min(available,policy.minW));
  const totalMin=mins.reduce((a,b)=>a+b,0);
  if(totalMin>available+.1){return mins.map((v)=>v*available/totalMin);}
  let widths=[...mins],left=available-totalMin;
  const desires=row.map(({policy},i)=>Math.max(0,policy.prefW-widths[i]));
  let desireSum=desires.reduce((a,b)=>a+b,0);
  if(left>0&&desireSum>0){const used=Math.min(left,desireSum);widths=widths.map((w,i)=>w+used*desires[i]/desireSum);left-=used;}
  if(left>0){const weights=row.map(({entry})=>effectiveWeight(entry));const sum=weights.reduce((a,b)=>a+b,0)||1;widths=widths.map((w,i)=>w+left*weights[i]/sum);}
  return widths;
}
function semanticSmartLayout(items=viewItems()) {
  const ordered=[...items].sort((a,b)=>a.order-b.order);
  if(!ordered.length){CANVAS.h=BASE_CANVAS_H;SCENE.h=820;return {rects:[],height:CANVAS.h,conflict:null};}
  const g=CANVAS.gap,innerW=CANVAS.w-2*g;
  const rows=[];let row=[];let minUsed=0;
  for(const entry of ordered){const policy=semanticPolicy(entry);const need=(row.length?g:0)+policy.minW;if(row.length&&minUsed+need>innerW){rows.push(row);row=[];minUsed=0;}row.push({entry,policy});minUsed+=(row.length>1?g:0)+policy.minW;if(policy.minW>innerW+.1){rows.push(row);row=[];minUsed=0;}}
  if(row.length)rows.push(row);
  const rowSpecs=rows.map((members)=>{const widths=allocateRowWidths(members,innerW,g);const desired=members.map(({policy},i)=>{let h=Math.max(policy.minH,policy.prefH);if(policy.aspect&&policy.growth==='square')h=Math.max(policy.minH,Math.min(policy.prefH,widths[i]/policy.aspect));return h;});return {members,widths,height:Math.max(...desired)};});
  const baseNeeded=rowSpecs.reduce((sum,r)=>sum+r.height,0)+g*Math.max(0,rowSpecs.length-1)+2*g;
  let targetH=Math.max(BASE_CANVAS_H,Math.ceil(baseNeeded));
  let conflict=null;
  if(targetH>MAX_CANVAS_H){conflict=`Smart layout requires ${targetH}px document height, above the governed ${MAX_CANVAS_H}px limit.`;targetH=MAX_CANVAS_H;}
  if(baseNeeded<BASE_CANVAS_H&&rowSpecs.length){let extra=BASE_CANVAS_H-baseNeeded;for(const r of rowSpecs){if(extra<=0)break;const cap=Math.max(0,r.height*.22);const add=Math.min(cap,extra/rowSpecs.length);r.height+=add;extra-=add;}}
  CANVAS.h=targetH;SCENE.h=CANVAS.h+145;
  const rects=[];let y=g;
  for(const spec of rowSpecs){let x=g;for(let i=0;i<spec.members.length;i+=1){const {entry,policy}=spec.members[i];const w=spec.widths[i];const h=Math.max(policy.minH,spec.height);rects.push({id:entry.id,x,y,w,h,touch:{L:x===g,R:Math.abs(x+w-(CANVAS.w-g))<.2,T:y===g,B:false},policy});x+=w+g;}y+=spec.height+g;}
  if(rects.length){const maxBottom=Math.max(...rects.map(r=>r.y+r.h));if(maxBottom>CANVAS.h-g+.5&&!conflict)conflict='Semantic minimum sizes exceed the current document safe hull.';for(const r of rects)r.touch.B=Math.abs(r.y+r.h-(CANVAS.h-g))<.2;}
  return {rects,height:CANVAS.h,conflict};
}
function smartRects(items = viewItems()) {
  const layout=semanticSmartLayout(items);ui.smartLayoutConflict=layout.conflict;return layout.rects;
}
function committedRects() {
  if (model().mode === 'smart') return smartRects(model().items);
  const fallback = new Map(smartRects(model().items).map((r)=>[r.id,r]));
  return model().items.map((entry)=>{const base=fallback.get(entry.id)||{x:CANVAS.gap,y:CANVAS.gap,w:240,h:160};return {id:entry.id,x:Number.isFinite(entry.x)?entry.x:base.x,y:Number.isFinite(entry.y)?entry.y:base.y,w:Number.isFinite(entry.w)?entry.w:base.w,h:Number.isFinite(entry.h)?entry.h:base.h,touch:{}};});
}
function currentRects() { return committedRects().map((r)=>({ ...r, ...(ui.previewPatches.get(r.id)||{}) })); }
function rectMap() { return new Map(currentRects().map((r) => [r.id, r])); }
function committedRectMap() { return new Map(committedRects().map((r)=>[r.id,r])); }

function localCommitId(prefix='commit', revision=store.revision) { return `${prefix}-${revision}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,9)}`; }
function debugEvent(level, event, detail = '') {
  ui.debugLog.unshift({id:++ui.debugSequence,time:new Date().toLocaleTimeString(),level,event,detail:String(detail||'').slice(0,600)});
  if (ui.debugLog.length > 200) ui.debugLog.length=200;
  if ($('#debugModal')?.classList.contains('show')) renderDeveloperConsole();
}
function dispatchSemantic(type, payload={}) {
  const message={bridge_version:BRIDGE_VERSION,type,payload};
  const encoded=JSON.stringify(message);
  if (new Blob([encoded]).size > MAX_BRIDGE_BYTES) { debugEvent('error','Bridge rejected','Message exceeds the bridge size limit'); toast('Operation is too large to send'); return false; }
  const root=$('.cui-visualizer-root');
  root?.dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:encoded}));
  document.dispatchEvent(new CustomEvent('visualizer_bridge_trace',{detail:message}));
  debugEvent('outbound',type,`Sent ${new Blob([encoded]).size.toLocaleString()} bytes`);
  return true;
}
function prospectiveModel(ops,label='Edit') {
  const probe=new EditorStore(parseCanonical(store.serialize()),{revision:store.revision});
  probe.commit(probe.command(ops,label,'probe')); return parseCanonical(probe.serialize());
}
function modelBytes(value) { return new Blob([serializeCanonical(value)]).size; }
function setSaveStatus(text, tone='good') { const node=$('#saveStatus'); if(!node)return; node.textContent=text; node.dataset.tone=tone; }
function syncAccepted(accepted) {
  const payload={report_id:String(bootstrap.report_id||'default'),base_revision:accepted.base_revision,commit_id:accepted.id,model:parseCanonical(accepted.canonical_after),fingerprint:null};
  ui.pendingCommits.set(accepted.id,payload);
  setSaveStatus('Saving…','pending');
  dispatchSemantic('report.commit',payload);
}
function replaceFromServer(payload, reason='Server synchronization') {
  if (!payload?.model || !Number.isInteger(payload.revision)) return;
  cancelPointerSession('report-switch'); clearTransientInteractionVisuals('report-switch');
  store=new EditorStore(parseCanonical(payload.model),{revision:payload.revision});
  bootstrap.report_id=payload.report_id||bootstrap.report_id; bootstrap.revision=payload.revision; ui.pendingCommits.clear(); pruneSelection(); ui.previewPatches.clear(); ui.intrinsicOverrides.clear(); renderAll(); toast(reason);
}
window.CompanyUIVisualizerBridge={receive(message){try{const m=typeof message==='string'?JSON.parse(message):message;if(!m||m.bridge_version!==BRIDGE_VERSION)return;const p=m.payload||{};debugEvent('inbound',m.type,typeof p.message==='string'?p.message:'Received from application');if(m.type==='report.commit_result'){ui.pendingCommits.delete(p.commit_id);setSaveStatus(ui.pendingCommits.size?'Saving…':'Saved',ui.pendingCommits.size?'pending':'good');return;}if(m.type==='report.conflict'){replaceFromServer(p,'Report changed elsewhere; reloaded latest revision');setSaveStatus('Synced','good');return;}if(m.type==='report.bootstrap'){replaceFromServer(p,'Report loaded');setSaveStatus('Saved','good');return;}if(m.type==='report.error'){setSaveStatus('Not saved','bad');if(p.report)replaceFromServer(p.report,'Rejected edit; restored server state');else toast(p.message||'Operation failed');return;}if(m.type==='preset.preferences_result'){personalPresets=Array.isArray(p.presets)?p.presets:[];schedulePresetListRender();return;}if(m.type==='application.notification')toast(p.message||'');}catch(error){debugEvent('error','Bridge receive failure',error?.stack||error);throw error;}},state(){return {editor_ready:$('.cui-visualizer-root')?.dataset.editorReady==='true',report_id:bootstrap.report_id,revision:store.revision,model:parseCanonical(store.serialize()),pending:ui.pendingCommits.size};}};

function commitOps(label, ops, { announce = null, render = true } = {}) {
  let next;
  try { next=prospectiveModel(ops,label); } catch(err) { debugEvent('error',`Rejected edit: ${label}`,err?.stack||err); toast(String(err.message||err)); return null; }
  if (modelBytes(next)>MAX_MODEL_BYTES) { toast('This edit would make the report too large; nothing was changed'); return null; }
  const accepted=store.commit(store.command(ops,label,localCommitId('commit',store.revision))); debugEvent('action',label,`${ops.length} operation${ops.length===1?'':'s'} · revision ${accepted.base_revision} → ${store.revision}`);
  pruneSelection(); ui.previewPatches.clear(); clearTransientInteractionVisuals('commit'); if(render)renderAll(); if(announce)toast(announce); syncAccepted(accepted); return accepted;
}
function undo() {
  if (!store.canUndo) return toast('Nothing to undo'); cancelPointerSession('undo'); const base=store.revision; store.undo(base); pruneSelection(); ui.previewPatches.clear(); clearTransientInteractionVisuals('undo'); renderAll(); dispatchSemantic('report.commit',{report_id:String(bootstrap.report_id||'default'),base_revision:base,commit_id:localCommitId('undo',base),model:parseCanonical(store.serialize())}); toast('Undid last edit');
}
function redo() {
  if (!store.canRedo) return toast('Nothing to redo'); cancelPointerSession('redo'); const base=store.revision; store.redo(base); pruneSelection(); ui.previewPatches.clear(); clearTransientInteractionVisuals('redo'); renderAll(); dispatchSemantic('report.commit',{report_id:String(bootstrap.report_id||'default'),base_revision:base,commit_id:localCommitId('redo',base),model:parseCanonical(store.serialize())}); toast('Redid last edit');
}
function pruneSelection() {
  const ids = new Set(model().items.map((entry) => entry.id));
  ui.selected = new Set([...ui.selected].filter((id) => ids.has(id)));
}

function chartData(entry) { return Array.isArray(entry.data) && entry.data.length ? entry.data : defaultChartData; }
function metricMarkup(entry) {
  return `<div class="kicker">Metric · live interaction</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">From 188 min manual → 14 min governed workflow</div><div class="metric-big" data-kpi="${entry.id}">${entry.value}%</div><div class="metric-delta">↓ ${entry.value}% cycle-time reduction</div><button class="mini-btn detail-toggle align-start mt-2" data-action="detail" aria-expanded="${entry.detail ? 'true' : 'false'}">${entry.detail ? 'Hide' : 'Show'} detail</button>${entry.detail ? '<div class="metric-detail">Derived from the same before/after model. Web can expand; PPT keeps the accepted summary.</div>' : ''}`;
}
function chartMarkup(entry, r) {
  const D = chartData(entry);
  if (entry.variant === 'nochart') {
    return `<div class="kicker">No Chart · semantic fallback</div><div class="ctitle">${esc(entry.title)}</div><div class="metric-big compact">${D.at(-1)[1]}m</div><div class="metric-delta">Current investigation time</div><div class="csub mt-2">Plot removed because direct hierarchy is the selected representation.</div>`;
  }
  const W = Math.max(220, r.w - 36);
  const H = Math.max(90, r.h - 116);
  const left = 24; const right = 12; const top = 10; const bottom = 30;
  const plotW = W - left - right; const plotH = H - top - bottom;
  const max = Math.max(...D.map((x) => +x[1] || 0), 1);
  const pts = D.map((d, k) => ({ x: left + plotW * k / Math.max(1, D.length - 1), y: top + plotH - (+d[1] || 0) / max * plotH, v: +d[1] || 0, l: d[0] }));
  let marks = '';
  if (entry.variant === 'bar') {
    const bw = Math.max(12, plotW / D.length * 0.55);
    marks = pts.map((p, k) => `<rect aria-hidden="true" class="chart-point-visual ${entry.cross === k ? 'active' : ''}" x="${p.x - bw / 2}" y="${p.y}" width="${bw}" height="${top + plotH - p.y}" rx="5"></rect>`).join('');
  } else {
    const linePath = pts.map((p, k) => `${k ? 'L' : 'M'}${p.x} ${p.y}`).join(' ');
    const areaPath = `M ${pts[0].x} ${top + plotH} ${pts.map((p) => `L ${p.x} ${p.y}`).join(' ')} L ${pts.at(-1).x} ${top + plotH} Z`;
    const clip = entry.revealed ? 'inset(0 0 0 0)' : 'inset(0 100% 0 0)';
    marks = (entry.variant === 'area' ? `<path d="${areaPath}" class="chart-area reveal-mask" style="clip-path:${clip}"></path>` : '')
      + `<path d="${linePath}" class="chart-line reveal-mask" style="clip-path:${clip}"></path>`
      + pts.map((p, k) => `<circle aria-hidden="true" class="chart-point-visual ${entry.cross === k ? 'active' : ''}" cx="${p.x}" cy="${p.y}" r="${entry.cross === k ? 6.5 : 4.5}"></circle>`).join('');
  }
  const hitButtons = pts.map((p, k) => {
    const cy = entry.variant === 'bar' ? p.y + (top + plotH - p.y) / 2 : p.y;
    return `<button type="button" class="chart-hit" data-point="${k}" aria-label="${esc(p.l)} ${p.v} minutes" aria-pressed="${entry.cross === k ? 'true' : 'false'}" style="left:${p.x / W * 100}%;top:${cy / H * 100}%"></button>`;
  }).join('');
  const bs = entry.brush || [0, D.length - 1];
  const bx1 = left + plotW * bs[0] / Math.max(1, D.length - 1);
  const bx2 = left + plotW * bs[1] / Math.max(1, D.length - 1);
  const drill = entry.drill != null ? `<div class="chart-drill"><b>${esc(D[entry.drill][0])}</b> · ${D[entry.drill][1]} min. Drill-down is interactive on web and flattens to the selected state for PPT.</div>` : '';
  return `<div class="kicker">Chart · cross-filter + brush + drill</div><div class="row-between"><div><div class="ctitle">${esc(entry.title)}</div><div class="csub">Click mark to filter evidence · double-click for drill-down</div></div><button class="mini-btn reveal" data-action="reveal" aria-pressed="${entry.revealed ? 'true' : 'false'}">${entry.revealed ? 'Hide' : 'Reveal'}</button></div><div class="chart-wrap"><svg class="chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" data-chart="${entry.id}" aria-label="${esc(entry.title)} chart">${[0, .5, 1].map((t) => `<line x1="${left}" y1="${top + plotH * t}" x2="${left + plotW}" y2="${top + plotH * t}" class="chart-grid"></line>`).join('')}${marks}<rect x="${left}" y="${H - 13}" width="${plotW}" height="5" rx="3" class="brush-track"></rect><rect x="${bx1}" y="${H - 16}" width="${Math.max(3, bx2 - bx1)}" height="11" rx="4" class="brush-window"></rect><rect aria-hidden="true" x="${bx1 - 3}" y="${H - 20}" width="6" height="19" rx="2" class="brush-handle-visual brush-handle-start"></rect><rect aria-hidden="true" x="${bx2 - 3}" y="${H - 20}" width="6" height="19" rx="2" class="brush-handle-visual brush-handle-end"></rect></svg><div class="chart-hit-layer">${hitButtons}<button type="button" role="slider" aria-label="Brush start" aria-valuemin="0" aria-valuemax="${D.length - 1}" aria-valuenow="${bs[0]}" class="brush-handle" data-brush="start" style="left:${bx1 / W * 100}%"></button><button type="button" role="slider" aria-label="Brush end" aria-valuemin="0" aria-valuemax="${D.length - 1}" aria-valuenow="${bs[1]}" class="brush-handle" data-brush="end" style="left:${bx2 / W * 100}%"></button></div></div><div class="chart-footer"><span>Brush: ${esc(D[bs[0]][0])} → ${esc(D[bs[1]][0])}</span><span>${entry.cross != null ? `Filter: ${esc(D[entry.cross][0])}` : 'No cross-filter'}</span></div>${drill}`;
}
function textMarkup(entry, r = {}) {
  const compact = Number(r.w) < 220 || Number(r.h) < 245;
  const full = 'Evidence is prepared deterministically before reasoning—not discovered by the model on demand.';
  const statement = compact ? 'Evidence is prepared before reasoning.' : full;
  const foot = compact ? 'Deterministic · source-backed' : `${esc(entry.title)} · source-backed narrative`;
  return `<div class="kicker">Executive statement</div><div class="text-hero ${compact ? 'compact' : ''}" title="${esc(full)}">${esc(statement)}</div><div class="text-foot">${foot}</div>`;
}
const evidenceRows = [['Collect', 'FDC pressure excursion', 'Support', 'High'], ['Normalize', 'Control population clean', 'Support', 'High'], ['Reason', 'Recipe unchanged', 'Contradict', 'High'], ['Verify', 'Spatial signature match', 'Support', 'Medium'], ['Close', 'Containment verified', 'Support', 'High']];
function tableMarkup(entry) {
  if (entry.customTable) {
    const headers = entry.customTable.headers.slice(0, 4);
    const rows = entry.customTable.rows;
    return `<div class="kicker">Table · pasted data target</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">${rows.length} pasted rows · raw values preserved</div><table class="table-mini"><thead><tr>${headers.map((x) => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((_, k) => `<td>${esc(row[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  const rows = model().crossFilter ? evidenceRows.filter((row) => row[0] === model().crossFilter) : evidenceRows;
  return `<div class="kicker">Table · cross-filter target</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">${model().crossFilter ? `Filtered by chart: ${esc(model().crossFilter)}` : 'All evidence'} · hover rows for highlight</div><table class="table-mini"><thead><tr><th>Evidence</th><th>Polarity</th><th>Confidence</th></tr></thead><tbody>${rows.map((row) => `<tr><td><span class="status-dot ${row[2] === 'Contradict' ? 'warn' : ''}" aria-hidden="true"></span>${esc(row[1])}</td><td>${esc(row[2])}</td><td>${esc(row[3])}</td></tr>`).join('')}</tbody></table>`;
}
function tabsMarkup(entry) {
  const copy = { Summary: 'Leading hypothesis remains Chamber A after contradiction-aware evidence review.', Evidence: '4 supporting observations · 1 meaningful contradiction · controls remain essential.', Next: 'Run targeted chamber verification before upgrading the root-cause status.' };
  return `<div class="kicker">Tabs + expandable detail</div><div class="ctitle">${esc(entry.title)}</div><div class="tabbar" role="tablist" aria-label="Investigation views">${Object.keys(copy).map((key) => `<button role="tab" aria-selected="${entry.tab === key ? 'true' : 'false'}" data-tab="${key}" class="${entry.tab === key ? 'active' : ''}">${key}</button>`).join('')}</div><div class="tab-copy" role="tabpanel">${copy[entry.tab] || copy.Summary}</div><button class="mini-btn expand align-start" data-action="expand" aria-expanded="${entry.expanded ? 'true' : 'false'}">${entry.expanded ? 'Collapse' : 'Expand'} evidence</button>${entry.expanded ? '<div class="metric-detail">Expanded detail remains inside the component boundary; Smart mode reallocates visual mass instead of overflowing.</div>' : ''}`;
}
function timelineMarkup(entry) {
  const milestones = [['Schema', 'Aug 18'], ['Data', 'Aug 31'], ['Reason', 'Sep 08'], ['Pilot', 'Sep 16'], ['Prod', 'Sep 26']];
  return `<div class="kicker">Interactive timeline</div><div class="ctitle">${esc(entry.title)}</div><div class="timeline" role="group" aria-label="Timeline milestones">${milestones.map((m, k) => `<button class="tm ${k < entry.tm ? 'done' : ''} ${k === entry.tm ? 'active' : ''}" data-tm="${k}" aria-pressed="${k === entry.tm ? 'true' : 'false'}"><i aria-hidden="true"></i><b>${m[0]}</b><span>${m[1]}</span></button>`).join('')}</div><div class="csub">Selected: <b>${milestones[entry.tm][0]}</b> · activate a milestone to inspect its state.</div>`;
}
function imageMarkup(entry) { return `<div class="kicker">Image / media</div><div class="ctitle">${esc(entry.title)}</div><div class="image-art" role="img" aria-label="Spatial signature engineering visual"><div class="image-cap">Spatial signature · focal crop</div></div>`; }
function diagramMarkup(entry) { return `<div class="kicker">Diagram</div><div class="ctitle">${esc(entry.title)}</div><div class="diagram-mini" aria-label="Source to Normalize to Reason flow"><div class="dnode"><b>Source</b><span>FDC / SPC</span></div><div class="dedge" aria-hidden="true"></div><div class="dnode"><b>Normalize</b><span>Evidence model</span></div><div class="dedge" aria-hidden="true"></div><div class="dnode"><b>Reason</b><span>Grounded AI</span></div></div><div class="csub">Connections are routed automatically and stay editable.</div>`; }
function riskMarkup(entry) { return `<div class="kicker">Decision / risk</div><div class="ctitle">${esc(entry.title)}</div><div class="text-hero compact">Proceed to production gate after control-population validation.</div><div class="riskbox"><b>Residual risk · Medium</b><span>Support coverage remains the gating constraint.</span></div>`; }
function semanticallyEmpty(entry){
  if(entry.engine==='CoreChartEngine')return !(entry.data||[]).some((row)=>Array.isArray(row)&&row[1]!==null&&row[1]!==undefined&&row[1]!=='');
  if(entry.engine==='TableEngine')return !(entry.customTable?.rows||entry.rows||[]).some((row)=>(Array.isArray(row)?row:Object.values(row||{})).some((v)=>v!==null&&v!==undefined&&String(v).trim()!==''));
  if(entry.engine==='ImageMediaEngine')return !entry.src;
  if(entry.engine==='DiagramEngine')return !(entry.nodes||[]).length;
  if(entry.engine==='TimelineEngine')return !(entry.milestones||[]).length;
  return false;
}
function emptyStateMarkup(entry){
  if(!semanticallyEmpty(entry))return '';
  const engine=entry.engine;
  if(engine==='CoreChartEngine')return '<div class="author-empty-state"><b>Add chart data</b><span>Paste from a spreadsheet or enter values.</span><div class="empty-state-actions"><button type="button" data-empty-action="paste">Paste data</button><button type="button" data-empty-action="enter">Enter data</button></div></div>';
  if(engine==='TableEngine')return '<div class="author-empty-state"><b>Build this table</b><span>Paste rows or start with one editable row.</span><div class="empty-state-actions"><button type="button" data-empty-action="paste">Paste rows</button><button type="button" data-empty-action="add-row">Add row</button></div></div>';
  if(engine==='ImageMediaEngine')return '<div class="author-empty-state"><b>Add an image</b><span>Paste directly or choose an image file.</span><div class="empty-state-actions"><button type="button" data-empty-action="paste-image">Paste image</button><button type="button" data-empty-action="upload">Upload</button></div></div>';
  if(engine==='DiagramEngine')return '<div class="author-empty-state"><b>Start the diagram</b><span>Add the first node and connect it to the next step.</span><div class="empty-state-actions"><button type="button" data-empty-action="add-node">Add node</button></div></div>';
  if(engine==='TimelineEngine')return '<div class="author-empty-state"><b>Add the first event</b><span>Dates are optional and remain null when omitted.</span><div class="empty-state-actions"><button type="button" data-empty-action="add-event">Add event</button></div></div>';
  return '';
}
function contentMarkup(entry, r) {
  if (entry.element && entry.engine) return `<div class="integrated-element-content">${renderIntegratedElement(entry)}</div>${emptyStateMarkup(entry)}`;
  if (entry.type === 'metric') return metricMarkup(entry);
  if (entry.type === 'chart') return chartMarkup(entry, r);
  if (entry.type === 'text') return textMarkup(entry, r);
  if (entry.type === 'table') return tableMarkup(entry);
  if (entry.type === 'tabs') return tabsMarkup(entry);
  if (entry.type === 'timeline') return timelineMarkup(entry);
  if (entry.type === 'image') return imageMarkup(entry);
  if (entry.type === 'diagram') return diagramMarkup(entry);
  if (entry.type === 'risk') return riskMarkup(entry);
  return textMarkup(entry, r);
}

function ensureCanvasScaffold() {
  const hull = $('#hull');
  if (!$('#componentLayer', hull)) {
    hull.innerHTML = '<div class="canvas-grid"></div><div class="group-layer" id="groupLayer"></div><div class="component-layer" id="componentLayer"></div><div class="drop-ghost" id="dropGhost"></div><div class="overlay-layer"><div class="guide v" id="guideV"></div><div class="guide h" id="guideH"></div><div class="lasso" id="lasso"></div></div>';
  }
  // Contextual controls belong to the scene perimeter, not the clipped canvas.
  // This lets edge-touching components expose actions without obscuring content.
  $('#context', hull)?.remove();
  const scene = $('#scene');
  if (!$('#context', scene)) scene.insertAdjacentHTML('beforeend', '<div class="context" id="context"></div>');
}
function createComponentNode(entry) {
  const node = document.createElement('div');
  node.className = 'component';
  node.dataset.id = entry.id;
  node.tabIndex = 0;
  node.setAttribute('role', 'group');
  node.innerHTML = '<button type="button" class="c-head"><span class="c-grip" aria-hidden="true"></span></button><div class="c-content"></div><button type="button" class="resize-h"></button>';
  return node;
}
function contentSignature(entry, r) {
  const data = {
    entry,
    width: Math.round(r.w),
    height: Math.round(r.h),
    crossFilter: entry.type === 'table' ? model().crossFilter : undefined,
  };
  return JSON.stringify(data);
}
function syncCanvasDimensions() {
  if (!activeRoot) return;
  activeRoot.style.setProperty('--viz-canvas-height', `${Math.ceil(CANVAS.h)}px`);
  activeRoot.style.setProperty('--viz-scene-height', `${Math.ceil(SCENE.h)}px`);
  const frame=$('#sceneFrame'); const scene=$('#scene'); const hull=$('#hull');
  if(frame){frame.style.width=`${(SCENE.w*ui.zoom).toFixed(2)}px`;frame.style.height=`${(SCENE.h*ui.zoom).toFixed(2)}px`;}
  if(scene)scene.style.height=`${Math.ceil(SCENE.h)}px`;
  if(hull)hull.style.height=`${Math.ceil(CANVAS.h)}px`;
}
function nodeOverflow(node) {
  if (!node) return { x:0, y:0 };
  let x=Math.max(0,node.scrollWidth-node.clientWidth); let y=Math.max(0,node.scrollHeight-node.clientHeight);
  for (const child of node.querySelectorAll('.integrated-element-content,.gallery-card,.card-body,.table-wrap,.chart-wrap,.diagram-svg')) {
    x=Math.max(x,Math.max(0,child.scrollWidth-child.clientWidth));
    y=Math.max(y,Math.max(0,child.scrollHeight-child.clientHeight));
  }
  return {x,y};
}
function measureSmartContentRequirements(rm) {
  if(model().mode!=='smart') return false;
  let changed=false;
  for(const entry of model().items) {
    const r=rm.get(entry.id); const node=ui.componentNodes.get(entry.id); if(!r||!node)continue;
    const overflow=nodeOverflow($('.c-content',node));
    if(overflow.x<=1&&overflow.y<=1)continue;
    const policy=semanticPolicy(entry); const previous=ui.intrinsicOverrides.get(entry.id)||{w:0,h:0};
    let nextW=previous.w||0, nextH=previous.h||0;
    if(overflow.x>1)nextW=Math.min(policy.maxW,Math.max(nextW,Math.ceil(r.w+overflow.x+10)));
    if(overflow.y>1)nextH=Math.min(policy.maxH,Math.max(nextH,Math.ceil(r.h+overflow.y+10)));
    if(nextW>previous.w+.5||nextH>previous.h+.5){ui.intrinsicOverrides.set(entry.id,{w:nextW,h:nextH});changed=true;}
  }
  return changed;
}
function positionMinimap() {
  const mm=$('#minimap'); const viewport=$('#viewport'); if(!mm||!viewport||!ui.showMini)return;
  const vr=viewport.getBoundingClientRect(); const w=mm.offsetWidth||164; const h=mm.offsetHeight||102;
  mm.style.left=`${Math.max(vr.left+12,vr.right-w-14)}px`;
  mm.style.top=`${Math.max(vr.top+12,vr.bottom-h-14)}px`;
}
function reconcileCanvas({ content = true } = {}) {
  ensureCanvasScaffold();
  const hull = $('#hull');
  hull.className = `canvas-hull ${model().mode}`;
  const layer = $('#componentLayer');
  const rm = rectMap();
  syncCanvasDimensions();
  const liveIds = new Set(model().items.map((entry) => entry.id));
  $$('.component', layer).forEach((node) => {
    if (!liveIds.has(node.dataset.id)) {
      ui.componentNodes.delete(node.dataset.id);
      node.remove();
    } else {
      ui.componentNodes.set(node.dataset.id, node);
    }
  });

  for (const entry of model().items) {
    const r = rm.get(entry.id);
    let node = $(`.component[data-id="${entry.id}"]`, layer);
    if (!node) {
      node = createComponentNode(entry);
      layer.appendChild(node);
    }
    ui.componentNodes.set(entry.id, node);
    node.classList.toggle('selected', ui.selected.has(entry.id));
    node.classList.toggle('locked', !!entry.locked);
    node.classList.toggle('grouped', !!entry.groupId);
    node.style.left = `${r.x}px`; node.style.top = `${r.y}px`; node.style.width = `${r.w}px`; node.style.height = `${r.h}px`; node.style.zIndex = String(10 + (entry.z || 0));
    node.setAttribute('aria-selected', ui.selected.has(entry.id) ? 'true' : 'false');
    node.setAttribute('aria-label', `${typeDefaults[entry.type]?.title || entry.type}: ${entry.title}${entry.locked ? ', locked' : ''}`);
    const head = $('.c-head', node); const resize = $('.resize-h', node);
    head.setAttribute('aria-label', `Move ${entry.title}`);
    resize.setAttribute('aria-label', `Resize ${entry.title}`);
    resize.disabled = !!entry.locked;
    const sig = contentSignature(entry, r);
    if (content && node.dataset.contentSignature !== sig) {
      const contentNode = $('.c-content', node);
      const activeKey = document.activeElement && node.contains(document.activeElement) ? focusKey(document.activeElement) : null;
      contentNode.innerHTML = contentMarkup(entry, r);
      node.dataset.contentSignature = sig;
      if (activeKey) restoreFocusKey(node, activeKey);
    }
  }
  renderGroups(rm);
  renderContext(rm);
  renderMinimap(rm);
  positionMinimap();
  runKpiAnimations();
  updateStatus();
}
function focusKey(el) {
  if (!el) return null;
  if (el.id) return `#${CSS.escape(el.id)}`;
  for (const key of ['data-action', 'data-tab', 'data-tm', 'data-point', 'data-brush']) if (el.hasAttribute?.(key)) return `[${key}="${CSS.escape(el.getAttribute(key))}"]`;
  return null;
}
function restoreFocusKey(root, key) { try { root.querySelector(key)?.focus({ preventScroll: true }); } catch { /* ignore */ } }
function renderGroups(rm) {
  const layer = $('#groupLayer');
  const members = model().items.filter((entry) => entry.groupId);
  if (!members.length) {
    if (layer.childElementCount) layer.replaceChildren();
    if (layer.dataset.signature) delete layer.dataset.signature;
    return;
  }
  const groups = {};
  members.forEach((entry) => (groups[entry.groupId] ??= []).push(rm.get(entry.id)));
  const specs = Object.entries(groups).map(([gid, rects]) => [gid, rectUnion(rects)]);
  const signature = specs.map(([gid, u]) => `${gid}:${u.x.toFixed(2)},${u.y.toFixed(2)},${u.w.toFixed(2)},${u.h.toFixed(2)}`).join('|');
  if (layer.dataset.signature === signature) return;
  layer.dataset.signature = signature;
  layer.innerHTML = specs.map(([gid, u]) => `<div class="group-outline" data-group="${esc(gid)}" style="left:${u.x - 4}px;top:${u.y - 4}px;width:${u.w + 8}px;height:${u.h + 8}px"></div>`).join('');
}

function renderGeometryOnly() {
  const rm = rectMap();
  for (const [id, r] of rm.entries()) {
    const node = ui.componentNodes.get(id);
    if (!node) continue;
    node.style.left = `${r.x}px`; node.style.top = `${r.y}px`; node.style.width = `${r.w}px`; node.style.height = `${r.h}px`;
  }
  renderGroups(rm);
  renderContext(rm);
  renderMinimap(rm);
  positionMinimap();
  updateStatus({ recomputePreflight: false });
}


function renderContext(rm) {
  const c = $('#context');
  if (!ui.selected.size) { c.classList.remove('show'); if (ui.contextSignature) c.replaceChildren(); ui.contextSignature = ''; ui.contextSize = null; delete c.dataset.placement; return; }
  const rects = [...ui.selected].map((id) => rm.get(id)).filter(Boolean);
  const u = rectUnion(rects);
  if (!u) return;
  const locked = [...ui.selected].some((id) => item(id)?.locked);
  const eligibility=commandEligibility();
  const contextSignature = `${[...ui.selected].sort().join(',')}|${locked ? 1 : 0}|${eligibility.group?1:0}|${eligibility.ungroup?1:0}`;
  if (ui.contextSignature !== contextSignature) {
    c.innerHTML = `<button data-ctx="lock" ${eligibility.lock?'':'disabled'}>${locked ? 'Unlock' : 'Lock'}</button><button data-ctx="group" ${eligibility.group?'':'disabled'}>Group</button><button data-ctx="ungroup" ${eligibility.ungroup?'':'disabled'}>Ungroup</button><button data-ctx="front" ${eligibility.front?'':'disabled'}>Front</button><button data-ctx="delete" ${eligibility.delete?'':'disabled'}>Delete</button>`;
    ui.contextSignature = contextSignature;
    ui.contextSize = null;
  }
  c.classList.add('show');

  const scene=$('#scene'); const viewport=$('#viewport');
  const sceneRect=scene.getBoundingClientRect(); const viewportRect=viewport.getBoundingClientRect();
  const scaleX=sceneRect.width/Math.max(1,scene.clientWidth||SCENE.w); const scaleY=sceneRect.height/Math.max(1,scene.clientHeight||SCENE.h);
  const toolbarRect=c.getBoundingClientRect(); const tw=Math.max(1,toolbarRect.width); const th=Math.max(1,toolbarRect.height); const gap=8;
  const selectedScreen=[...ui.selected].map((id)=>ui.componentNodes.get(id)?.getBoundingClientRect()).filter(Boolean);
  const us=selectedScreen.reduce((acc,r)=>acc?{x:Math.min(acc.x,r.x),y:Math.min(acc.y,r.y),right:Math.max(acc.right,r.right),bottom:Math.max(acc.bottom,r.bottom)}:{x:r.x,y:r.y,right:r.right,bottom:r.bottom},null);
  if(!us)return; us.w=us.right-us.x; us.h=us.bottom-us.y;
  const candidates=[
    {placement:'above',x:us.x+us.w/2-tw/2,y:us.y-th-gap},
    {placement:'below',x:us.x+us.w/2-tw/2,y:us.bottom+gap},
    {placement:'right',x:us.right+gap,y:us.y+us.h/2-th/2},
    {placement:'left',x:us.x-tw-gap,y:us.y+us.h/2-th/2},
    {placement:'viewport-top-left',x:viewportRect.left+8,y:viewportRect.top+8},
    {placement:'viewport-top-right',x:viewportRect.right-tw-8,y:viewportRect.top+8},
    {placement:'viewport-bottom-left',x:viewportRect.left+8,y:viewportRect.bottom-th-8},
    {placement:'viewport-bottom-right',x:viewportRect.right-tw-8,y:viewportRect.bottom-th-8},
  ];
  const peers=[...rm.keys()].filter((id)=>!ui.selected.has(id)).map((id)=>ui.componentNodes.get(id)?.getBoundingClientRect()).filter(Boolean).map((r)=>({x:r.x,y:r.y,w:r.width,h:r.height}));
  const minX=viewportRect.left+4,maxX=viewportRect.right-tw-4,minY=viewportRect.top+4,maxY=viewportRect.bottom-th-4;
  const scored=candidates.map((candidate,order)=>{
    const x=clamp(candidate.x,minX,maxX),y=clamp(candidate.y,minY,maxY),r={x,y,w:tw,h:th};
    const selectedOverlap=intersectionArea(r,{x:us.x,y:us.y,w:us.w,h:us.h});
    const peerOverlap=peers.reduce((sum,peer)=>sum+intersectionArea(r,peer),0);
    const displacement=Math.abs(x-candidate.x)+Math.abs(y-candidate.y);
    return {...candidate,x,y,order,score:selectedOverlap*1e9+peerOverlap*1e4+displacement};
  }).sort((a,b)=>a.score-b.score||a.order-b.order)[0];
  c.style.left=`${(scored.x-sceneRect.left)/Math.max(scaleX,1e-6)}px`;
  c.style.top=`${(scored.y-sceneRect.top)/Math.max(scaleY,1e-6)}px`;
  c.dataset.placement=scored.placement;
}
function renderMinimap(rm) {
  const mm = $('#minimap');
  if (!ui.showMini) { mm.style.display = 'none'; return; }
  mm.style.display = 'block';
  const mw=152, mh=92; const sx = mw / CANVAS.w; const sy = mh / CANVAS.h;
  let svg = $('svg', mm);
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${mw} ${mh}`);
    mm.replaceChildren(svg);
    ui.minimapNodes.clear();
  }
  const live = new Set(rm.keys());
  for (const [id, node] of [...ui.minimapNodes.entries()]) { if (!live.has(id)) { node.remove(); ui.minimapNodes.delete(id); } }
  for (const [id, r] of rm.entries()) {
    let rect = ui.minimapNodes.get(id);
    if (!rect) {
      rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('rx', '2');
      svg.appendChild(rect);
      ui.minimapNodes.set(id, rect);
    }
    rect.setAttribute('x', String(r.x * sx)); rect.setAttribute('y', String(r.y * sy));
    rect.setAttribute('width', String(r.w * sx)); rect.setAttribute('height', String(r.h * sy));
    rect.setAttribute('class', ui.selected.has(id) ? 'mmselected' : 'mmitem');
  }
}

function parseTypedCell(raw) {
  const text=String(raw ?? '').trim();
  if (text==='') return null;
  const normalized=text.replace(/,/g,'');
  if (/^[-+]?\d*\.?\d+(?:e[-+]?\d+)?$/i.test(normalized)) {
    const value=Number(normalized); return Number.isFinite(value) ? value : text;
  }
  return text;
}
function parseDelimitedLine(line, delimiter) {
  const out=[]; let cell=''; let quoted=false;
  for (let i=0;i<line.length;i+=1) {
    const ch=line[i];
    if (ch==='"') { if (quoted && line[i+1]==='"') { cell+='"'; i+=1; } else quoted=!quoted; continue; }
    if (ch===delimiter && !quoted) { out.push(cell); cell=''; continue; }
    cell+=ch;
  }
  out.push(cell); return out.map((value)=>value.trim());
}
function parseGridText(text) {
  return parseUniversalGridText(text).rows;
}
function parsePairs(text) { return parseGridText(text).filter((row)=>row.some((v)=>v!=='')).map((row)=>[String(row[0]??'').trim(),parseTypedCell(row[1])]); }
function pairsText(entry) { return (entry.data||entry.observations||[]).map((row)=>Array.isArray(row)?`${row[0]??''}\t${row[1]??''}`:`${row.label??''}\t${row.value??''}`).join('\n'); }
function parseTable(text) { return parseGridText(text).map((row)=>row.map(parseTypedCell)); }
function tableText(entry) {
  if (entry.customTable) return [entry.customTable.headers||[],...(entry.customTable.rows||[])].map((row)=>row.map((v)=>v??'').join('\t')).join('\n');
  return (entry.rows||[]).map((row)=>Array.isArray(row)?row.map((v)=>v??'').join('\t'):Object.values(row).map((v)=>v??'').join('\t')).join('\n');
}
function matrixText(entry) { return (entry.matrix||[]).map((row)=>row.map((v)=>v??'').join('\t')).join('\n'); }
function timelineText(entry) { return (entry.milestones||[]).map((m)=>`${m.label??''}|${m.date??''}`).join('\n'); }
function parseTimeline(text) { return String(text||'').split(/\r?\n/).filter((line)=>line.trim()).map((line)=>{const pos=line.indexOf('|');const label=(pos<0?line:line.slice(0,pos)).trim();const raw=pos<0?'':line.slice(pos+1).trim();return {label,date:raw||null};}); }
function observationsText(entry, fields=['label','value']) { return (entry.observations||[]).map((row)=>fields.map((f)=>row?.[f]??'').join('\t')).join('\n'); }
function parseObservations(text, fields=['label','value']) { return parseGridText(text).filter((row)=>row.some((v)=>v!=='')).map((row)=>Object.fromEntries(fields.map((field,index)=>[field,index===fields.length-1?parseTypedCell(row[index]):parseTypedCell(row[index])]))); }
function metricInspectorMarkup(entry){
  const name=String(entry.element||'').toLowerCase();
  if(name.includes('ladder'))return `<div class="field"><label for="iLevels">Levels / steps · label + value</label><textarea id="iLevels" rows="7">${esc((entry.levels||[['P90',52],['Median',42.8],['P10',31]]).map((row)=>Array.isArray(row)?row.join('\t'):`${row.label??''}\t${row.value??''}`).join('\n'))}</textarea><div class="field-grid"><select id="iOrientation"><option value="vertical" ${entry.orientation==='vertical'?'selected':''}>Vertical</option><option value="horizontal" ${entry.orientation==='horizontal'?'selected':''}>Horizontal</option></select><input id="iValue" placeholder="Current position" value="${esc(entry.value??'')}"></div><small>Each step remains semantic and editable.</small></div>`;
  if(name.includes('ring'))return `<div class="field"><label>Ring value</label><div class="field-grid"><input id="iValue" placeholder="Value" value="${esc(entry.value??'')}"><input id="iMax" placeholder="Maximum" value="${esc(entry.max??100)}"></div><input id="iCenterLabel" placeholder="Center label" value="${esc(entry.center_label||'Progress')}"><textarea id="iThresholds" rows="4" placeholder="Threshold label,value">${esc((entry.thresholds||[]).map((x)=>Array.isArray(x)?x.join('\t'):`${x.label??''}\t${x.value??''}`).join('\n'))}</textarea></div>`;
  if(name.includes('confidence'))return `<div class="field"><label>Confidence</label><div class="field-grid"><input id="iConfidence" placeholder="Confidence %" value="${esc(entry.confidence??entry.value??'')}" inputmode="decimal"><input id="iInterpretation" placeholder="Interpretation" value="${esc(entry.interpretation||'')}"></div><textarea id="iContext" rows="4" placeholder="Interpretation context">${esc(entry.context||'')}</textarea><input id="iBands" placeholder="Bands, e.g. 0-54 Low; 55-79 Moderate; 80-100 High" value="${esc(entry.bands||'')}"></div>`;
  if(name.includes('capacity'))return `<div class="field"><label>Capacity</label><div class="field-grid"><input id="iCurrent" placeholder="Current" value="${esc(entry.current??entry.value??'')}"><input id="iCapacity" placeholder="Capacity" value="${esc(entry.capacity??'')}"></div><input id="iUnit" placeholder="Unit" value="${esc(entry.unit||'')}"></div>`;
  if(name.includes('rate'))return `<div class="field"><label>Rate basis</label><div class="field-grid"><input id="iNumerator" placeholder="Numerator" value="${esc(entry.numerator??'')}"><input id="iDenominator" placeholder="Denominator" value="${esc(entry.denominator??'')}"></div><div class="field-grid"><input id="iValue" placeholder="Displayed rate" value="${esc(entry.value??'')}"><input id="iPeriod" placeholder="Period" value="${esc(entry.period||'per period')}"></div></div>`;
  if(name.includes('threshold'))return `<div class="field"><label>Threshold metric</label><input id="iValue" placeholder="Current value" value="${esc(entry.value??'')}"><div class="field-grid"><input id="iWarning" placeholder="Warning" value="${esc(entry.warning??'')}"><input id="iCritical" placeholder="Critical" value="${esc(entry.critical??'')}"></div><select id="iThresholdLogic"><option value="higher-is-worse" ${entry.threshold_logic==='higher-is-worse'?'selected':''}>Higher is worse</option><option value="lower-is-worse" ${entry.threshold_logic==='lower-is-worse'?'selected':''}>Lower is worse</option></select></div>`;
  if(name.includes('target'))return `<div class="field"><label>Target vs actual</label><div class="field-grid"><input id="iActual" placeholder="Actual" value="${esc(entry.actual??entry.value??'')}"><input id="iTarget" placeholder="Target" value="${esc(entry.target??'')}"></div><input id="iVariance" placeholder="Variance" value="${esc(entry.variance??'')}"></div>`;
  if(name.includes('progress'))return `<div class="field"><label>Progress</label><div class="field-grid"><input id="iCurrent" placeholder="Current" value="${esc(entry.current??entry.value??'')}"><input id="iMax" placeholder="Maximum" value="${esc(entry.max??100)}"></div></div>`;
  if(name.includes('sparkline'))return `<div class="field"><label>Metric & series</label><div class="field-grid"><input id="iValue" placeholder="Value" value="${esc(entry.value??'')}"><input id="iUnit" placeholder="Unit" value="${esc(entry.unit||'')}"></div><textarea id="iSeries" rows="5" placeholder="Period,value">${esc((entry.series||[]).map((x)=>Array.isArray(x)?x.join('\t'):`${x.label??''}\t${x.value??''}`).join('\n'))}</textarea><div class="field-grid"><input id="iDelta" placeholder="Comparison" value="${esc(entry.delta??'')}"><input id="iPeriod" placeholder="Period label" value="${esc(entry.period||'last 7 periods')}"></div></div>`;
  return `<div class="field"><label>Metric</label><div class="inline2"><input id="iValue" placeholder="Value" value="${esc(entry.value??'')}"><input id="iUnit" placeholder="Unit" value="${esc(entry.unit||'')}"></div><div class="inline2"><input id="iDelta" placeholder="Delta" value="${esc(entry.delta??'')}"><input id="iTarget" placeholder="Target" value="${esc(entry.target??'')}"></div><small>Blank remains missing; numeric 0 remains zero.</small></div>`;
}
function tableInspectorMarkup(entry){
  const headers=entry.customTable?.headers||['Field','Value'];const rows=entry.customTable?.rows||entry.rows||[];const cols=Math.max(1,headers.length,...rows.map((r)=>Array.isArray(r)?r.length:0));
  const head=Array.from({length:cols},(_,c)=>`<th><input data-table-header="${c}" aria-label="Column ${c+1} header" value="${esc(headers[c]??'')}"></th>`).join('');
  const body=rows.slice(0,20).map((row,r)=>`<tr>${Array.from({length:cols},(_,c)=>`<td><input data-table-cell="${r}:${c}" aria-label="Row ${r+1}, column ${c+1}" value="${esc(row?.[c]??'')}"></td>`).join('')}</tr>`).join('');
  return `<div class="field"><label>Data grid</label><div class="table-editor-grid"><table><thead><tr>${head}</tr></thead><tbody>${body||`<tr>${Array.from({length:cols},(_,c)=>`<td><input data-table-cell="0:${c}" aria-label="Row 1, column ${c+1}" value=""></td>`).join('')}</tr>`}</tbody></table></div><div class="data-actions"><button type="button" data-table-action="add-row">Add row</button><button type="button" data-table-action="add-column">Add column</button><button type="button" data-table-action="paste">Paste rows</button></div><small>Use Tab/Shift+Tab for cell navigation. Clipboard values preserve blank versus numeric zero.</small></div>`;
}
function paddedTable(entry){const headers=[...(entry.customTable?.headers||['Field','Value'])];const rows=(entry.customTable?.rows||entry.rows||[]).map((row)=>Array.isArray(row)?[...row]:Object.values(row));const cols=Math.max(1,headers.length,...rows.map((row)=>row.length));while(headers.length<cols)headers.push(`Column ${headers.length+1}`);rows.forEach((row)=>{while(row.length<cols)row.push(null);});return {headers,rows};}
function selectedDataset(entry) { return entry?.dataset_id ? model().datasets.find((dataset)=>dataset.id===entry.dataset_id) : null; }
function dataDockMarkup(entry) {
  const dataset=selectedDataset(entry); if(!dataset) return '';
  const fields=dataset.fields||[], mapping=entry.mapping||{};
  const option=(selected)=>`<option value="">Unmapped</option>${fields.map(field=>`<option value="${esc(field.id)}" ${selected===field.id?'selected':''}>${esc(field.name)} · ${esc(field.type)}</option>`).join('')}`;
  const roles=['category','x','y','value','series','color','size','time','source','target','die_x','die_y','wafer_id','lot_id','tool','chamber','recipe','process','product','bin','subgroup','specification_low','specification_high','lower_limit','upper_limit'];
  const contextualRoles=()=>{const name=String(entry.element||'').toLowerCase();if(entry.engine==='WaferFabEngine')return ['die_x','die_y','value','wafer_id','lot_id','tool','chamber','recipe','process','product','bin'];if(entry.engine==='MatrixEngine')return ['category','series','value'];if(entry.engine!=='EngineeringChartEngine')return [];if(name.includes('main effects')||name.includes('interaction plot'))return ['value','category','series'];if(name.includes('response surface')||name.includes('contour')||name.includes('residual')||name.includes('predicted vs actual'))return ['value','x','y'];if(name.includes('confidence interval'))return ['value','category'];if(name.includes('error-bar'))return ['value','category','lower_limit','upper_limit'];return ['value','time','subgroup','specification_low','specification_high'];};
  const visibleRoles=new Set(['x','y','value','category',...contextualRoles(),...roles.filter(role=>mapping[role])]);
  const mappingValidation=contractFor(entry.view_type||entry.type).validate(mapping,fields);
  const mappingStatus=mappingValidation.incompatible.length?`<small class="mapping-status error">Choose a compatible field for ${esc(mappingValidation.incompatible.join(', '))}.</small>`:mappingValidation.missing.length?`<small class="mapping-status">Map ${esc(mappingValidation.missing.join(', '))} to complete this view.</small>`:'<small class="mapping-status valid">Mapping ready.</small>';
  const views=['bar','line','scatter','table','engineering','wafer','diagram'];
  const transformTypes=['filter','sort','group','aggregate','unpivot','pivot','derive','bin','rank','cumulative','normalize','date_extract'];
  return inspectorSection('Data Dock',`<div class="data-dock-meta"><b>${esc(dataset.name)}</b><span>${dataset.rows.length.toLocaleString()} rows · rev ${dataset.revision}</span></div><input id="dataDockFind" class="data-dock-find" type="search" value="${esc(ui.dataDockFilter)}" placeholder="Find in data" aria-label="Find in dataset"><label class="data-view-switch">View<select data-view-type>${views.map(view=>`<option value="${view}" ${(entry.view_type||entry.type)===view?'selected':''}>${view}</option>`).join('')}</select></label><div class="mapping-chips">${roles.filter(role=>visibleRoles.has(role)).map(role=>`<label data-role-drop="${esc(role)}">${esc(role)}<select data-dataset-role="${esc(role)}">${option(mapping[role])}</select></label>`).join('')}</div>${mappingStatus}<div id="dataDockGrid" class="data-dock-grid" role="grid" aria-label="${esc(dataset.name)}"></div><small>Virtualized rows · use Tab/Shift+Tab to move between visible cells.</small><div class="data-actions"><button type="button" data-dataset-action="add-row">Add row</button><button type="button" data-dataset-action="add-column">Add column</button><button type="button" data-dataset-action="delete-row">Delete last row</button></div><div class="paste-special" role="group" aria-label="Paste Special"><button type="button" data-paste-special="dataset_data">Copy data</button><button type="button" data-paste-special="mapping">Copy mapping</button><button type="button" data-paste-special="style">Copy style</button><button type="button" data-paste-special="paste-data">Paste data</button><button type="button" data-paste-special="independent">Paste independent</button></div><div class="data-transform"><select data-transform-type>${transformTypes.map(type=>`<option value="${type}">${type.replace('_',' ')}</option>`).join('')}</select><select data-transform-field>${fields.map(field=>`<option value="${esc(field.id)}">${esc(field.name)}</option>`).join('')}</select><input data-transform-value placeholder="Value / parameter" aria-label="Transform value or parameter"><button type="button" data-transform-action="apply">Apply</button><button type="button" data-transform-action="clear">Clear</button></div>`);
}
function renderVirtualDataDock(entry, dataset) {
  const host=$('#dataDockGrid');if(!host)return;const rowHeight=31,poolSize=24,fields=dataset.fields||[];
  const fieldTypes=['string','integer','number','boolean','date','datetime','categorical','identifier','unknown'];
  host.innerHTML=`<table><thead><tr>${fields.map((field,index)=>`<th><input draggable="true" data-dataset-field="${index}" data-field-id="${esc(field.id)}" value="${esc(field.name)}" aria-label="Rename ${esc(field.name)}"><select data-dataset-type="${index}" aria-label="${esc(field.name)} type">${fieldTypes.map(type=>`<option value="${type}" ${field.type===type?'selected':''}>${type}</option>`).join('')}</select></th>`).join('')}</tr></thead></table><div class="data-dock-scroll"><div class="data-dock-spacer"></div><table class="data-dock-rows"><tbody></tbody></table></div>`;
  const scroll=$('.data-dock-scroll',host),spacer=$('.data-dock-spacer',host),body=$('tbody',host),pool=Array.from({length:poolSize},()=>{const row=document.createElement('tr');row.innerHTML=fields.map(()=>'<td><input></td>').join('');body.appendChild(row);return row;});const visible=dataset.rows.map((row,index)=>({row,index})).filter(({row})=>!ui.dataDockFilter||row.some(value=>String(value??'').toLowerCase().includes(ui.dataDockFilter.toLowerCase())));spacer.style.height=`${visible.length*rowHeight}px`;
  const selected=(row,column)=>{const range=ui.dataDockRange;if(!range)return false;const [ar,ac]=range.anchor.split(':').map(Number),[fr,fc]=range.focus.split(':').map(Number);return row>=Math.min(ar,fr)&&row<=Math.max(ar,fr)&&column>=Math.min(ac,fc)&&column<=Math.max(ac,fc);};
  const paint=()=>{const start=Math.max(0,Math.min(Math.max(0,visible.length-poolSize),Math.floor(scroll.scrollTop/rowHeight)-4));body.style.transform=`translateY(${start*rowHeight}px)`;pool.forEach((tr,slot)=>{const record=visible[start+slot];tr.hidden=!record;if(!record)return;[...tr.querySelectorAll('input')].forEach((input,column)=>{input.dataset.datasetCell=`${record.index}:${column}`;input.value=record.row[column]??'';input.classList.toggle('range-selected',selected(record.index,column));input.setAttribute('aria-label',`Row ${record.index+1}, ${fields[column].name}`);});});};host.__dockPaint=paint;host.__dockScroll=scroll;host.__dockVisible=visible.map(record=>record.index);scroll.addEventListener('scroll',paint,{passive:true});paint();
}
function commitDataset(entry, label, nextDataset, nextMapping=entry.mapping||{}) {
  const datasets=model().datasets.map(dataset=>dataset.id===nextDataset.id?nextDataset:dataset);
  const ops=[{op:'model.patch',patch:{datasets}}];
  model().items.filter(candidate=>candidate.dataset_id===nextDataset.id).forEach(candidate=>ops.push({op:'item.patch',id:candidate.id,patch:{mapping:candidate.id===entry.id?nextMapping:candidate.mapping||{},...canonicalPatch(candidate,nextDataset,candidate.id===entry.id?nextMapping:candidate.mapping||{})}}));
  return commitOps(label,ops);
}
function bindDataDock(entry) {
  const dataset=selectedDataset(entry); if(!dataset)return;
  renderVirtualDataDock(entry,dataset);
  const update=(label,mutate,mapping=entry.mapping||{})=>{const next=structuredClone(dataset);mutate(next);next.revision=(dataset.revision||0)+1;commitDataset(entry,label,next,mapping);};
  $('#dataDockFind')?.addEventListener('input',event=>{ui.dataDockFilter=event.target.value;renderVirtualDataDock(entry,dataset);});
  $('#dataDockGrid')?.addEventListener('change',event=>{const target=event.target;if(target.matches('[data-dataset-field]'))return update('Rename dataset field',next=>{next.fields[+target.dataset.datasetField].name=target.value.trim()||`Column ${+target.dataset.datasetField+1}`;});if(target.matches('[data-dataset-type]'))return update('Override field type',next=>{next.fields[+target.dataset.datasetType].type=target.value;});if(target.matches('[data-dataset-cell]')){const [row,column]=target.dataset.datasetCell.split(':').map(Number);update('Edit dataset cell',next=>{next.rows[row][column]=parseTypedCell(target.value);});}});
  $('#dataDockGrid')?.addEventListener('focusin',event=>{const target=event.target;if(target.matches('[data-dataset-cell]')){ui.dataDockCell=target.dataset.datasetCell;if(ui.dataDockRange?.focus!==ui.dataDockCell)ui.dataDockRange={anchor:ui.dataDockCell,focus:ui.dataDockCell};}});
  $('#dataDockGrid')?.addEventListener('keydown',event=>{const target=event.target;if(!target.matches('[data-dataset-cell]'))return;const [row,column]=target.dataset.datasetCell.split(':').map(Number),host=$('#dataDockGrid'),visible=host.__dockVisible||[];if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='c'){event.preventDefault();const range=ui.dataDockRange||{anchor:target.dataset.datasetCell,focus:target.dataset.datasetCell},[ar,ac]=range.anchor.split(':').map(Number),[fr,fc]=range.focus.split(':').map(Number),loRow=Math.min(ar,fr),hiRow=Math.max(ar,fr),loColumn=Math.min(ac,fc),hiColumn=Math.max(ac,fc),text=dataset.rows.slice(loRow,hiRow+1).map(record=>record.slice(loColumn,hiColumn+1).map(value=>value??'').join('\t')).join('\n');navigator.clipboard?.writeText(text).then(()=>toast('Copied selected data cells')).catch(()=>toast('Copy unavailable in this browser'));return;}const delta={ArrowLeft:[0,-1],ArrowRight:[0,1],ArrowUp:[-1,0],ArrowDown:[1,0]}[event.key];if(!delta)return;event.preventDefault();const position=Math.max(0,visible.indexOf(row)),nextRow=visible[clamp(position+delta[0],0,Math.max(0,visible.length-1))]??row,nextColumn=clamp(column+delta[1],0,Math.max(0,dataset.fields.length-1)),next=`${nextRow}:${nextColumn}`;ui.dataDockRange=event.shiftKey?{anchor:ui.dataDockRange?.anchor||target.dataset.datasetCell,focus:next}:{anchor:next,focus:next};host.__dockScroll.scrollTop=Math.max(0,visible.indexOf(nextRow)*31-80);host.__dockPaint();requestAnimationFrame(()=>host.querySelector(`[data-dataset-cell="${next}"]`)?.focus());});
  $('#dataDockGrid')?.addEventListener('paste',event=>{const target=event.target;if(!target.matches('[data-dataset-cell]'))return;const text=event.clipboardData?.getData('text/plain');if(!text)return;const rows=parseGridText(text);if(!rows.length)return;event.preventDefault();const [startRow,startColumn]=target.dataset.datasetCell.split(':').map(Number);update('Paste dataset cells',next=>{rows.forEach((row,rowOffset)=>{const rowIndex=startRow+rowOffset;while(next.rows.length<=rowIndex)next.rows.push(Array(next.fields.length).fill(null));row.forEach((value,columnOffset)=>{const columnIndex=startColumn+columnOffset;if(columnIndex<next.fields.length)next.rows[rowIndex][columnIndex]=parseTypedCell(value);});});});});
  $$('[data-dataset-role]').forEach(select=>select.addEventListener('change',event=>{const role=event.target.dataset.datasetRole,mapping={...(entry.mapping||{})};if(event.target.value)mapping[role]=event.target.value;else delete mapping[role];const validation=contractFor(entry.view_type||entry.type).validate(mapping,dataset.fields);if(validation.incompatible.includes(role)){event.target.value=entry.mapping?.[role]||'';return toast(`${role} needs a numeric field for this view`);}update(`Map ${role}`,()=>{},mapping);}));
  $$('[data-role-drop]').forEach(zone=>{zone.addEventListener('dragover',event=>{event.preventDefault();zone.classList.add('drag-over');});zone.addEventListener('dragleave',()=>zone.classList.remove('drag-over'));zone.addEventListener('drop',event=>{event.preventDefault();zone.classList.remove('drag-over');const fieldId=event.dataTransfer?.getData('application/x-visembler-field');if(!fieldId)return;const role=zone.dataset.roleDrop,mapping={...(entry.mapping||{}),[role]:fieldId},validation=contractFor(entry.view_type||entry.type).validate(mapping,dataset.fields);if(validation.incompatible.includes(role))return toast(`${role} needs a numeric field for this view`);update(`Map ${role}`,()=>{},mapping);});});
  $('#dataDockGrid')?.addEventListener('dragstart',event=>{const field=event.target.closest('[data-field-id]');if(field)event.dataTransfer?.setData('application/x-visembler-field',field.dataset.fieldId);});
  $('[data-view-type]')?.addEventListener('change',event=>{
    const view=event.target.value, engine=({bar:'CoreChartEngine',line:'CoreChartEngine',scatter:'CoreChartEngine',table:'TableEngine',engineering:'EngineeringChartEngine',wafer:'WaferFabEngine',diagram:'DiagramEngine'})[view];
    const validation=contractFor(view).validate(entry.mapping||{},dataset.fields); if(!validation.valid){event.target.value=entry.view_type||entry.type;return toast(`Map ${validation.missing.join(', ')||validation.incompatible.join(', ')} before changing view`);}
    const type=engineToType[engine]||entry.type; const patch={engine,type,element:view==='wafer'?'Wafer Map':view==='diagram'?'Data Flow':view==='engineering'?'SPC Control Chart':view==='table'?'Clean Table':`${view[0].toUpperCase()+view.slice(1)} Chart`,view_type:view,...canonicalPatch({...entry,engine,type},dataset,entry.mapping||{})};
    commitOps(`Change view to ${view}`,[{op:'item.patch',id:entry.id,patch}],{announce:`Changed view to ${view}`});
  });
  $('[data-transform-action="apply"]')?.addEventListener('click',()=>{const type=$('[data-transform-type]')?.value,field=$('[data-transform-field]')?.value,value=$('[data-transform-value]')?.value;if(!type||!field)return toast('Choose a transform field');const recipe=structuredClone(entry.transform_recipe||{id:`recipe-${entry.id}`,source_dataset_id:dataset.id,steps:[]});const step={type,field,direction:'asc'};if(type==='filter')Object.assign(step,{operator:'contains',value});if(type==='derive')Object.assign(step,{source_field:field,multiplier:Number(value)||1});if(type==='bin')Object.assign(step,{size:Number(value)||1});if(type==='date_extract')Object.assign(step,{part:value||'date'});if(type==='group'||type==='aggregate')Object.assign(step,{by:field,value_field:(entry.mapping||{}).value||field,aggregation:value||'sum'});if(type==='unpivot')Object.assign(step,{keep_fields:value?value.split(',').map(item=>item.trim()).filter(Boolean):[field]});if(type==='pivot'){const [columnField,valueField]=value.split(',').map(item=>item.trim());Object.assign(step,{index_fields:[field],column_field:columnField||(entry.mapping||{}).series,value_field:valueField||(entry.mapping||{}).value,aggregation:'sum'});}recipe.steps.push(step);commitOps(`Apply ${type} transform`,[{op:'item.patch',id:entry.id,patch:{transform_recipe:recipe,...canonicalPatch({...entry,transform_recipe:recipe},dataset,entry.mapping||{})}}],{announce:`Applied ${type} transform`});});
  $('[data-transform-action="clear"]')?.addEventListener('click',()=>commitOps('Clear transforms',[{op:'item.patch',id:entry.id,patch:{transform_recipe:null,...canonicalPatch({...entry,transform_recipe:null},dataset,entry.mapping||{})}}],{announce:'Cleared transforms'}));
  $$('[data-paste-special]').forEach(button=>button.addEventListener('click',()=>{const mode=button.dataset.pasteSpecial;if(mode==='dataset_data'||mode==='mapping'||mode==='style')return copySemanticSelection(mode);if(!ui.semanticClipboard)return toast('Copy a visual, data, mapping, or style first');pasteSemanticPayload(ui.semanticClipboard,mode==='paste-data'?'data':mode);}));
  $$('[data-dataset-action]').forEach(button=>button.addEventListener('click',()=>{const action=button.dataset.datasetAction;if(action==='add-row')update('Add dataset row',next=>next.rows.push(Array(next.fields.length).fill(null)));if(action==='add-column')update('Add dataset column',next=>{const index=next.fields.length;next.fields.push({id:`column_${index+1}`,name:`Column ${index+1}`,type:'unknown',nullable:true});next.rows.forEach(row=>row.push(null));});if(action==='delete-row')update('Delete dataset row',next=>next.rows.pop());}));
}
function semanticInspectorMarkup(entry) {
  const engine=entry.engine||'';
  if (engine==='TextEngine') return `<div class="field"><label for="iText">Narrative</label><textarea id="iText" rows="7">${esc(entry.text||entry.body||'')}</textarea></div>`;
  if (engine==='MetricEngine') return metricInspectorMarkup(entry);
  if (engine==='ComparisonEngine') return `<div class="field"><label>Comparison</label><div class="inline2"><input id="iBefore" placeholder="Before" value="${esc(entry.before??'')}"><input id="iAfter" placeholder="After" value="${esc(entry.after??'')}"></div></div>`;
  if (engine==='CoreChartEngine') {const behaviors=entry.behaviors||{};return `<div class="field"><label for="iData">Chart data · label + value</label><textarea id="iData" rows="8" spellcheck="false">${esc(pairsText(entry))}</textarea><div class="data-actions"><button type="button" data-chart-action="sample">Restore useful sample</button><button type="button" data-chart-action="clear">Clear values</button></div><small>Paste TSV/CSV. Blank numeric cells remain missing; the starter data is safe to overwrite.</small></div><div class="field"><label>Attached behaviors</label><div class="behavior-options"><label><input type="checkbox" data-chart-behavior="tooltip" ${behaviors.tooltip!==false?'checked':''}> Tooltip</label><label><input type="checkbox" data-chart-behavior="cross_filter" ${behaviors.cross_filter!==false?'checked':''}> Cross-filter</label><label><input type="checkbox" data-chart-behavior="drill" ${behaviors.drill!==false?'checked':''}> Drill</label></div><small>Click a mark to filter; double-click it to drill when enabled.</small></div>`;}
  if (engine==='TableEngine') return tableInspectorMarkup(entry);
  if (engine==='MatrixEngine') return `<div class="field"><label for="iMatrix">Matrix data</label><textarea id="iMatrix" rows="9" spellcheck="false">${esc(matrixText(entry))}</textarea></div>`;
  if (engine==='TimelineEngine') return `<div class="field"><label for="iTimeline">Events · Label|Date</label><textarea id="iTimeline" rows="8">${esc(timelineText(entry))}</textarea><div class="data-actions"><button type="button" data-timeline-action="add">Add event</button><button type="button" data-timeline-action="sequence">Sequence only</button><button type="button" data-timeline-action="sample">Restore sample</button></div><small>Blank dates remain null; sequence-only timelines never invent dates.</small></div>`;
  if (engine==='DiagramEngine') return `<div class="field"><label for="iNodes">Nodes · one per line</label><textarea id="iNodes" rows="5">${esc((entry.nodes||[]).join('\n'))}</textarea><div class="data-actions"><button type="button" data-diagram-action="add-node">Add node</button><button type="button" data-diagram-action="add-connected">Add connected node</button><button type="button" data-diagram-action="sample">Restore sample</button></div></div><div class="field"><label for="iEdges">Edges · A -&gt; B</label><textarea id="iEdges" rows="5">${esc((entry.edges||[]).map((edge)=>`${edge[0]} -> ${edge[1]}`).join('\n'))}</textarea><div class="field-grid"><select id="iDirection"><option value="right" ${entry.direction==='right'?'selected':''}>Left → right</option><option value="down" ${entry.direction==='down'?'selected':''}>Top → bottom</option></select><input id="iEdgeLabel" placeholder="Default edge label" value="${esc(entry.edge_label||'')}"></div><small>Connections are routed automatically, remain editable, and can be extended from the last node.</small></div>`;
  if (engine==='ImageMediaEngine') return `<div class="field"><label for="iImageFile">Image</label><input id="iImageFile" type="file" accept="image/png,image/jpeg,image/webp"><div class="data-actions"><button type="button" data-image-action="paste">Paste image</button><button type="button" data-image-action="replace">Replace</button></div><small>Choose a file or paste with Ctrl/Cmd+V. Embedded image limit: ${Math.round(MAX_IMAGE_BYTES/1000)} KB.</small></div><div class="field"><label>Presentation</label><div class="field-grid"><select id="iImageFit"><option value="fit" ${entry.fit==='fit'?'selected':''}>Fit</option><option value="fill" ${entry.fit==='fill'?'selected':''}>Fill</option></select><input id="iFocal" value="${esc(entry.focal||'50% 50%')}" placeholder="Focal position"></div></div><div class="field"><label for="iAlt">Alt text</label><input id="iAlt" value="${esc(entry.alt||'')}"></div><div class="field"><label for="iCaption">Caption</label><textarea id="iCaption" rows="3">${esc(entry.caption||'')}</textarea></div>`;
  if (['EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'].includes(engine)) return `<div class="field"><label for="iStatement">Statement</label><textarea id="iStatement" rows="4">${esc(entry.statement||'')}</textarea></div><div class="field"><label for="iDetail">Detail</label><textarea id="iDetail" rows="5">${esc(entry.detail||'')}</textarea></div><div class="field"><label for="iStatus">Status</label><input id="iStatus" value="${esc(entry.status||'Draft')}"></div>`;
  if (engine==='EngineeringChartEngine') return `<div class="field"><label for="iObservations">Observations · label + measurement</label><textarea id="iObservations" rows="8">${esc(observationsText(entry))}</textarea></div><div class="field"><label>Role / limits</label><input id="iRole" value="${esc(entry.role||'measurement')}"><div class="inline2"><input id="iLcl" placeholder="Lower limit" value="${esc(entry.lower_limit??entry.lcl??'')}"><input id="iUcl" placeholder="Upper limit" value="${esc(entry.upper_limit??entry.ucl??'')}"></div></div>`;
  if (engine==='WaferFabEngine') return `<div class="field"><label for="iObservations">Wafer observations · X + Y + Value</label><textarea id="iObservations" rows="8">${esc(observationsText(entry,['x','y','value']))}</textarea></div><div class="field"><label>Process identity</label><div class="inline2"><input id="iTool" placeholder="Tool" value="${esc(entry.tool||'')}"><input id="iChamber" placeholder="Chamber" value="${esc(entry.chamber||'')}"></div><div class="inline2"><input id="iLot" placeholder="Lot" value="${esc(entry.lot||'')}"><input id="iRoute" placeholder="Route" value="${esc(entry.route||'')}"></div></div>`;
  if (engine==='SmartLayoutEngine') return `<div class="field"><label for="iConfiguration">Layout configuration</label><textarea id="iConfiguration" rows="5">${esc(entry.configuration||'14px governed composition')}</textarea></div>`;
  if (engine==='InteractionLayer') return `<div class="field"><label for="iBehavior">Interaction behavior</label><textarea id="iBehavior" rows="5">${esc(entry.behavior||'select → filter → inspect')}</textarea></div>`;
  if (engine==='EditorInfrastructure') return `<div class="field"><label for="iConfiguration">Editor configuration</label><textarea id="iConfiguration" rows="5">${esc(entry.configuration||'Editor-only infrastructure')}</textarea></div>`;
  return `<div class="field"><label for="iText">Content</label><textarea id="iText" rows="6">${esc(entry.text||entry.body||'')}</textarea></div>`;
}
async function fileToDataUrl(file) { return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('Image read failed'));reader.readAsDataURL(file);}); }
async function validatedImageDataUrl(file) {
  if (!file || !['image/png','image/jpeg','image/webp'].includes(String(file.type||'').toLowerCase())) throw new Error('Only PNG, JPEG, or WebP images are supported');
  if (file.size > MAX_IMAGE_BYTES) throw new Error(`Image exceeds ${Math.round(MAX_IMAGE_BYTES/1000)} KB embedded-image limit`);
  return await fileToDataUrl(file);
}
function bindSemanticInspector(entry) {
  const patch=(label,value)=>{ if (entry.locked) return toast('Unlock the component before editing'); return commitOps(label,[{op:'item.patch',id:entry.id,patch:value}]); };
  $('#iText')?.addEventListener('change',(e)=>patch('Edit narrative',{text:e.target.value,body:e.target.value}));
  $('#iValue')?.addEventListener('change',(e)=>patch('Edit metric',{value:parseTypedCell(e.target.value)})); $('#iUnit')?.addEventListener('change',(e)=>patch('Edit metric unit',{unit:e.target.value})); $('#iDelta')?.addEventListener('change',(e)=>patch('Edit metric delta',{delta:parseTypedCell(e.target.value)})); $('#iTarget')?.addEventListener('change',(e)=>patch('Edit metric target',{target:parseTypedCell(e.target.value)}));
  for(const [id,key] of [['iMax','max'],['iConfidence','confidence'],['iCurrent','current'],['iCapacity','capacity'],['iNumerator','numerator'],['iDenominator','denominator'],['iWarning','warning'],['iCritical','critical'],['iActual','actual'],['iVariance','variance']])$('#'+id)?.addEventListener('change',(e)=>patch(`Edit ${key}`,{[key]:parseTypedCell(e.target.value),...(key==='actual'?{value:parseTypedCell(e.target.value)}:{})}));
  for(const [id,key] of [['iCenterLabel','center_label'],['iInterpretation','interpretation'],['iContext','context'],['iBands','bands'],['iPeriod','period'],['iThresholdLogic','threshold_logic'],['iOrientation','orientation'],['iDirection','direction'],['iEdgeLabel','edge_label'],['iImageFit','fit']])$('#'+id)?.addEventListener('change',(e)=>patch(`Edit ${key.replaceAll('_',' ')}`,{[key]:e.target.value}));
  $('#iLevels')?.addEventListener('change',(e)=>patch('Edit metric ladder levels',{levels:parseGridText(e.target.value).filter((row)=>row.some((x)=>x!=='')).map((row)=>[String(row[0]??''),parseTypedCell(row[1])])}));
  $('#iThresholds')?.addEventListener('change',(e)=>patch('Edit ring thresholds',{thresholds:parseGridText(e.target.value).filter((row)=>row.some((x)=>x!=='')).map((row)=>[String(row[0]??''),parseTypedCell(row[1])])}));
  $('#iSeries')?.addEventListener('change',(e)=>patch('Edit metric sparkline series',{series:parseGridText(e.target.value).filter((row)=>row.some((x)=>x!=='')).map((row)=>[String(row[0]??''),parseTypedCell(row[1])])}));
  $('#iBefore')?.addEventListener('change',(e)=>patch('Edit comparison before',{before:parseTypedCell(e.target.value)})); $('#iAfter')?.addEventListener('change',(e)=>patch('Edit comparison after',{after:parseTypedCell(e.target.value)}));
  $('#iData')?.addEventListener('change',(e)=>{const data=parsePairs(e.target.value);patch('Edit chart data',{data,rows:data.map(([label,value])=>({label,value})),brush:[0,Math.max(0,data.length-1)],cross:null,drill:null});});
  $$('[data-chart-behavior]').forEach(control=>control.addEventListener('change',event=>patch(`Toggle ${event.target.dataset.chartBehavior.replace('_',' ')} behavior`,{behaviors:{...(entry.behaviors||{}),[event.target.dataset.chartBehavior]:event.target.checked}})));
  $$('[data-chart-action]').forEach((button)=>button.addEventListener('click',()=>{const data=button.dataset.chartAction==='clear'?[['Category A',null],['Category B',null],['Category C',null]]:chartStarterData(entry.element);patch(button.dataset.chartAction==='clear'?'Clear chart values':'Restore chart sample',{data,rows:data.map(([label,value])=>({label,value})),brush:[0,Math.max(0,data.length-1)],cross:null,drill:null});}));
  $('#iTable')?.addEventListener('change',(e)=>{const rows=parseTable(e.target.value);patch('Edit table data',{customTable:{headers:rows[0]||[],rows:rows.slice(1)},rows:rows.slice(1)});});
  const tableSnapshot=()=>{const headers=[...paddedTable(entry).headers];const rows=paddedTable(entry).rows.map((row)=>[...row]);return {headers,rows};};
  $$('[data-table-header]').forEach((input)=>input.addEventListener('change',(e)=>{const grid=tableSnapshot();grid.headers[+e.target.dataset.tableHeader]=e.target.value;patch('Rename table header',{customTable:grid,rows:grid.rows});}));
  $$('[data-table-cell]').forEach((input)=>input.addEventListener('change',(e)=>{const [r,c]=e.target.dataset.tableCell.split(':').map(Number);const grid=tableSnapshot();while(grid.rows.length<=r)grid.rows.push(Array(grid.headers.length).fill(null));while(grid.rows[r].length<grid.headers.length)grid.rows[r].push(null);grid.rows[r][c]=parseTypedCell(e.target.value);patch('Edit table cell',{customTable:grid,rows:grid.rows});}));
  $$('[data-table-action]').forEach((button)=>button.addEventListener('click',async()=>{
    const grid=tableSnapshot();
    if(button.dataset.tableAction==='add-row'){
      grid.rows.push(Array(grid.headers.length).fill(null));
      patch('Add table row',{customTable:grid,rows:grid.rows}); return;
    }
    if(button.dataset.tableAction==='add-column'){
      grid.headers.push(`Column ${grid.headers.length+1}`); grid.rows.forEach((row)=>row.push(null));
      patch('Add table column',{customTable:grid,rows:grid.rows}); return;
    }
    if(button.dataset.tableAction==='paste'){
      try {
        const text=await navigator.clipboard?.readText?.();
        if(text){const parsed=parseTable(text);const next={headers:parsed[0]||grid.headers,rows:parsed.slice(1)};patch('Paste table rows',{customTable:next,rows:next.rows});return;}
      } catch { /* clipboard may require browser permission */ }
      toast('Copy spreadsheet cells, then press Ctrl/Cmd+V while this table is selected');
    }
  }));
  $('#iMatrix')?.addEventListener('change',(e)=>patch('Edit matrix data',{matrix:parseTable(e.target.value)}));
  $('#iTimeline')?.addEventListener('change',(e)=>patch('Edit timeline',{milestones:parseTimeline(e.target.value)}));
  $('[data-timeline-action="add"]')?.addEventListener('click',()=>patch('Add timeline event',{milestones:[...(entry.milestones||[]),{label:`Event ${(entry.milestones||[]).length+1}`,date:null}]}));
  $('[data-timeline-action="sequence"]')?.addEventListener('click',()=>patch('Use sequence-only timeline',{milestones:(entry.milestones||[]).map((m)=>({...m,date:null}))}));
  $('[data-timeline-action="sample"]')?.addEventListener('click',()=>patch('Restore timeline sample',{milestones:timelineStarter()}));
  $('#iNodes')?.addEventListener('change',(e)=>patch('Edit diagram nodes',{nodes:String(e.target.value).split(/\r?\n/).map((x)=>x.trim()).filter(Boolean)})); $('#iEdges')?.addEventListener('change',(e)=>patch('Edit diagram edges',{edges:String(e.target.value).split(/\r?\n/).map((line)=>line.split(/\s*->\s*/)).filter((edge)=>edge.length===2&&edge[0]&&edge[1])}));
  $('[data-diagram-action="add-node"]')?.addEventListener('click',()=>patch('Add diagram node',{nodes:[...(entry.nodes||[]),`Node ${(entry.nodes||[]).length+1}`]}));
  $('[data-diagram-action="add-connected"]')?.addEventListener('click',()=>{const nodes=entry.nodes?.length?[...entry.nodes]:['Source'];const next=`Node ${nodes.length+1}`;patch('Add connected diagram node',{nodes:[...nodes,next],edges:[...(entry.edges||[]),[nodes.at(-1),next]]});});
  $('[data-diagram-action="sample"]')?.addEventListener('click',()=>patch('Restore diagram sample',diagramStarter()));
  $('#iImageFile')?.addEventListener('change',async(e)=>{try{const file=e.target.files?.[0];if(file)patch('Set image',{src:await validatedImageDataUrl(file)});}catch(err){toast(String(err.message||err));}}); $('#iAlt')?.addEventListener('change',(e)=>patch('Edit image alt text',{alt:e.target.value})); $('#iCaption')?.addEventListener('change',(e)=>patch('Edit image caption',{caption:e.target.value})); $('#iFocal')?.addEventListener('change',(e)=>patch('Edit image focal point',{focal:e.target.value||'50% 50%'}));
  $('[data-image-action="replace"]')?.addEventListener('click',()=>$('#iImageFile')?.click());$('[data-image-action="paste"]')?.addEventListener('click',()=>toast('Paste an image with Ctrl/Cmd+V while this image is selected'));
  $('#iStatement')?.addEventListener('change',(e)=>patch('Edit statement',{statement:e.target.value})); $('#iDetail')?.addEventListener('change',(e)=>patch('Edit detail',{detail:e.target.value})); $('#iStatus')?.addEventListener('change',(e)=>patch('Edit status',{status:e.target.value}));
  $('#iObservations')?.addEventListener('change',(e)=>patch('Edit observations',{observations:parseObservations(e.target.value,entry.engine==='WaferFabEngine'?['x','y','value']:['label','value'])})); $('#iRole')?.addEventListener('change',(e)=>patch('Edit statistical role',{role:e.target.value})); $('#iLcl')?.addEventListener('change',(e)=>patch('Edit lower limit',{lower_limit:parseTypedCell(e.target.value),lcl:parseTypedCell(e.target.value)})); $('#iUcl')?.addEventListener('change',(e)=>patch('Edit upper limit',{upper_limit:parseTypedCell(e.target.value),ucl:parseTypedCell(e.target.value)}));
  for (const [id,key] of [['iTool','tool'],['iChamber','chamber'],['iLot','lot'],['iRoute','route'],['iBehavior','behavior'],['iConfiguration','configuration']]) $('#'+id)?.addEventListener('change',(e)=>patch(`Edit ${key}`,{[key]:e.target.value}));
}
function inspectorSection(title, body) { return `<section class="inspector-section"><div class="inspector-section-title">${esc(title)}</div>${body}</section>`; }
function semanticSectionName(engine) {
  if (['CoreChartEngine','TableEngine','MatrixEngine','EngineeringChartEngine','WaferFabEngine'].includes(engine)) return 'Data';
  if (engine==='ImageMediaEngine') return 'Media';
  if (engine==='DiagramEngine') return 'Structure';
  if (engine==='TimelineEngine') return 'Milestones';
  if (['SmartLayoutEngine','EditorInfrastructure'].includes(engine)) return 'Configuration';
  if (engine==='InteractionLayer') return 'Behavior';
  return 'Content';
}
function renderInspector() {
  const p = $('#inspector'); if (!p) return;
  const ids = [...ui.selected];
  if (ids.length === 1) {
    const entry = item(ids[0]); const d=typeDefaults[entry.type]||typeDefaults.text; const policy=semanticPolicy(entry);const actualRect=rectMap().get(entry.id);
    const identity=`<div class="inspector-identity"><span>${esc((entry.engine||entry.type).replace(/Engine|Composite|Layer|Infrastructure/g,''))}</span><b>${esc(entry.element||entry.title)}</b></div>`;
    const titleSection=inspectorSection('Identity',`<div class="field"><label for="iTitle">Title</label><input id="iTitle" value="${esc(entry.title)}"><label class="toggle-field"><input id="iShowTitle" type="checkbox" ${entry.showTitle===true||entry.show_title===true?'checked':''}> <span>Show title on canvas</span></label><label for="iTextAlign">Content alignment</label><select id="iTextAlign"><option value="left" ${(entry.textAlign||entry.text_align||'left')==='left'?'selected':''}>Left</option><option value="center" ${(entry.textAlign||entry.text_align)==='center'?'selected':''}>Center</option><option value="right" ${(entry.textAlign||entry.text_align)==='right'?'selected':''}>Right</option></select><small>Titles are optional. Alignment applies to text and data labels inside this element.</small></div>`);
    const contentSection=inspectorSection(semanticSectionName(entry.engine||''),semanticInspectorMarkup(entry));
    const emphasis=defaultEmphasis(entry);
    const layoutBody=model().mode==='smart'?`<div class="field"><label>Visual emphasis</label><div class="emphasis-options" role="group" aria-label="Visual emphasis">${['compact','standard','prominent','hero'].map((level)=>`<button type="button" class="emphasis-option ${emphasis===level?'active':''}" data-emphasis="${level}">${level[0].toUpperCase()+level.slice(1)}</button>`).join('')}</div><small>Smart mode uses semantic size constraints plus this report-authoring emphasis.</small><details class="advanced-details"><summary>Advanced</summary><label for="iWeight">Raw layout weight</label><input id="iWeight" aria-label="Advanced layout weight" type="range" min=".45" max="3.4" step=".05" value="${entry.weight||1}"><div class="info-row"><span>Weight</span><b>${Number(entry.weight||1).toFixed(2)}</b></div></details><div class="info-row"><span>Intrinsic minimum</span><b>${Math.ceil(policy.minW)} × ${Math.ceil(policy.minH)}</b></div></div>`:`<div class="field"><label>Size</label><div class="inline2"><input id="iW" aria-label="Width" value="${Math.round(actualRect?.w||entry.w||policy.minW)}" placeholder="Width"><input id="iH" aria-label="Height" value="${Math.round(actualRect?.h||entry.h||policy.minH)}" placeholder="Height"></div><div class="info-row"><span>Minimum</span><b>${Math.ceil(policy.minW)} × ${Math.ceil(policy.minH)}</b></div><small>${model().mode==='guided'?'Guided mode snaps placement and resize to the 14px safe margin, grid, peer edges, centers and equal gaps.':'Free mode keeps exact manual geometry with no snapping while still enforcing readable minimum size and valid canvas bounds.'}</small></div>`;
    const accessibility=entry.engine==='ImageMediaEngine'?inspectorSection('Accessibility / Export',`<div class="info-row"><span>Alt text</span><b>${String(entry.alt||'').trim()?'Ready':'Required'}</b></div><div class="info-row"><span>PowerPoint</span><b>Editable region</b></div>`):inspectorSection('Accessibility / Export','<div class="info-row"><span>PowerPoint</span><b>Semantic export eligible</b></div>');
    p.innerHTML=identity+titleSection+contentSection+dataDockMarkup(entry)+inspectorSection('Layout',layoutBody)+accessibility+`<div class="inspector-meta">${entry.locked?'Locked · ':''}Changes apply to this element only.</div>`;
    $('#iTitle').addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Rename component',[{op:'item.patch',id:entry.id,patch:{title:e.target.value}}]));
    $('#iShowTitle')?.addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Toggle canvas title',[{op:'item.patch',id:entry.id,patch:{showTitle:e.target.checked}}]));
    $('#iTextAlign')?.addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Set content alignment',[{op:'item.patch',id:entry.id,patch:{textAlign:e.target.value}}]));
    bindSemanticInspector(entry);
    bindDataDock(entry);
    $$('[data-emphasis]',p).forEach((button)=>button.addEventListener('click',()=>entry.locked?toast('Unlock the component before editing'):commitOps('Set visual emphasis',[{op:'item.patch',id:entry.id,patch:{emphasis:button.dataset.emphasis}}])));
    $('#iWeight')?.addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Set advanced layout weight',[{op:'item.patch',id:entry.id,patch:{weight:+e.target.value}}])); $('#iW')?.addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Set width',[{op:'item.patch',id:entry.id,patch:{w:Math.max(policy.minW,+e.target.value||entry.w)}}])); $('#iH')?.addEventListener('change',(e)=>entry.locked?toast('Unlock the component before editing'):commitOps('Set height',[{op:'item.patch',id:entry.id,patch:{h:Math.max(policy.minH,+e.target.value||entry.h)}}]));
    if (entry.locked) p.querySelectorAll('input,textarea,select').forEach((node)=>{node.disabled=true;});
    return;
  }
  if (ids.length > 1) {
    p.innerHTML = `<div class="inspector-identity"><span>Selection</span><b>${ids.length} elements</b></div>${inspectorSection('Arrange','<div class="field"><div class="r-actions"><button class="tb" data-inspector="align-left">Align left</button><button class="tb" data-inspector="align-top">Align top</button><button class="tb" data-inspector="align-center">Center</button><button class="tb" data-inspector="distribute-x">Distribute H</button><button class="tb" data-inspector="distribute-y">Distribute V</button></div></div>')}${inspectorSection('Structure','<div class="field"><div class="r-actions"><button class="tb" data-inspector="group">Group</button><button class="tb" data-inspector="ungroup">Ungroup</button><button class="tb" data-inspector="lock">Lock / unlock</button></div></div>')}`; return;
  }
  renderCanvasInspector(p);
}
function renderCanvasInspector(p) {
  const pf = preflight();
  p.innerHTML = `<div class="inspector-identity"><span>Report</span><b>Canvas</b></div>${inspectorSection('Overview',`<div class="info-row"><span>Mode</span><b>${model().mode[0].toUpperCase()+model().mode.slice(1)}</b></div><div class="info-row"><span>Elements</span><b>${model().items.length}</b></div><div class="info-row"><span>Layout warnings</span><b>${pf.warnings.length}</b></div><div class="info-row"><span>Locked</span><b>${model().items.filter((entry)=>entry.locked).length}</b></div>`)}${inspectorSection('Smart layout',`<div class="suggestion"><b>Editorial Bento</b><p>Balanced narrative and analytical hierarchy.</p><button class="tb" data-suggestion="editorial">Apply</button></div><div class="suggestion"><b>Executive</b><p>Promote KPI, takeaway, comparison and decision.</p><button class="tb" data-suggestion="executive">Apply</button></div><div class="suggestion"><b>Technical</b><p>Promote diagram, table, timeline and engineering evidence.</p><button class="tb" data-suggestion="technical">Apply</button></div>`)}`;
}

function renderAll() {
  if(!ui.pointerSession)clearTransientInteractionVisuals('render-idle');
  let pass=0; let changed=false;
  do {
    reconcileCanvas({ content: true });
    changed=measureSmartContentRequirements(rectMap());
    pass+=1;
  } while(changed&&pass<4);
  ui.contentMeasurePass=pass;
  reconcileCanvas({content:false});
  renderInspector(); setZoom(ui.zoom, false); syncModeButtons();
}

function syncModeButtons() {
  $$('[data-mode]').forEach((button) => {
    const active = button.dataset.mode === model().mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  const help=$('#modeHelp'); if(help) help.textContent=model().mode==='smart'?'Auto composition · 14px safe frame + peer gap':model().mode==='guided'?'Manual · 14px grid + margin + peer alignment/equal-gap snapping':'Exact manual geometry · no snapping';
}
function commandEligibility() {
  const entries=[...ui.selected].map(item).filter(Boolean);
  const any=entries.length>0; const groupIds=new Set(entries.map((entry)=>entry.groupId).filter(Boolean));
  const sameExistingGroup=entries.length>1&&groupIds.size===1&&entries.every((entry)=>entry.groupId);
  return {
    group: entries.length>=2&&!sameExistingGroup,
    ungroup: entries.some((entry)=>!!entry.groupId),
    lock:any, front:any, back:any, delete:entries.some((entry)=>!entry.locked),
  };
}
function updateCommandEligibility() {
  const state=commandEligibility();
  for(const [selector,key] of [['#group','group'],['#ungroup','ungroup'],['#lock','lock'],['#front','front'],['#back','back']]){const node=$(selector);if(node)node.disabled=!state[key];}
}
function preflight() {
  const R = currentRects();
  const pf = { coverage: model().mode === 'smart' ? 100 : 0, overlaps: 0, out: 0, min: 0, clipping:0, plot:0, controls:0, staleGuides:0, warnings: [], issues:[], layoutIssues:[], accessibilityIssues:[], dataIssues:[] };
  const addIssue=(kind,id,message,severity='layout')=>{const issue={kind,id,message,severity};pf.issues.push(issue);if(severity==='layout')pf.layoutIssues.push(issue);else if(severity==='accessibility')pf.accessibilityIssues.push(issue);else pf.dataIssues.push(issue);};
  const inset=model().mode==='free'?0:CANVAS.gap;
  for (let a = 0; a < R.length; a += 1) {
    const entry = item(R[a].id); if(!entry)continue; const policy=semanticPolicy(entry);
    if (R[a].w < policy.minW-.1 || R[a].h < policy.minH-.1){pf.min += 1;addIssue('intrinsic-size',entry.id,`${entry.title} is below its readable ${Math.ceil(policy.minW)}×${Math.ceil(policy.minH)} minimum.`);}
    if (R[a].x < inset-.1 || R[a].y < inset-.1 || R[a].x + R[a].w > CANVAS.w-inset+.1 || R[a].y + R[a].h > CANVAS.h-inset+.1){pf.out += 1;addIssue('safe-hull',entry.id,`${entry.title} extends outside the document safe hull.`);}
    for (let b = a + 1; b < R.length; b += 1) if (overlap(R[a], R[b], 1)){pf.overlaps += 1;addIssue('overlap',entry.id,`${entry.title} overlaps ${item(R[b].id)?.title||'another element'}.`);}
    const node=ui.componentNodes.get(entry.id); const overflow=nodeOverflow(node&&$('.c-content',node));
    if(overflow.x>1||overflow.y>1){pf.clipping+=1;addIssue('content-clipping',entry.id,`${entry.title} has ${Math.ceil(overflow.x)}px horizontal / ${Math.ceil(overflow.y)}px vertical hidden content.`);}
    if(['CoreChartEngine','EngineeringChartEngine'].includes(entry.engine)){
      const plot=node?.querySelector('svg,.chart-wrap,.plot-area');
      if(plot&&(plot.clientWidth<160||plot.clientHeight<90)){pf.plot+=1;addIssue('plot-area',entry.id,`${entry.title} does not have a readable plot area.`);}
    }
    if(entry.engine==='ImageMediaEngine'&&entry.src&&!String(entry.alt||'').trim())addIssue('alt-text',entry.id,`${entry.title} needs alt text for accessibility.`,'accessibility');
  }
  if (model().mode !== 'smart') {
    const area = R.reduce((s, r) => s + r.w * r.h, 0);
    pf.coverage = Math.min(100, Math.round(area / (CANVAS.w * CANVAS.h) * 100));
  }
  if(ui.smartLayoutConflict)addIssue('smart-conflict',null,ui.smartLayoutConflict);
  if(!ui.pointerSession){const guides=Number(activeRoot?.dataset.snapGuideCount||0);if(guides){pf.staleGuides=guides;addIssue('stale-guide',null,`${guides} alignment guide(s) survived after interaction ended.`);}}
  for(const button of $$('.tb,.mini-btn,.library-tab',activeRoot||document)){if(button.offsetParent!==null&&button.scrollWidth>button.clientWidth+1){pf.controls+=1;addIssue('control-wrap',null,`Control “${button.textContent.trim()}” does not fit on one line.`);}}
  if (pf.overlaps) pf.warnings.push(`${pf.overlaps} overlap${pf.overlaps===1?'':'s'}`);
  if (pf.out) pf.warnings.push(`${pf.out} safe-hull violation${pf.out===1?'':'s'}`);
  if (pf.min) pf.warnings.push(`${pf.min} intrinsic-size violation${pf.min===1?'':'s'}`);
  if (pf.clipping) pf.warnings.push(`${pf.clipping} clipped element${pf.clipping===1?'':'s'}`);
  if (pf.plot) pf.warnings.push(`${pf.plot} unreadable plot${pf.plot===1?'':'s'}`);
  if (pf.controls) pf.warnings.push(`${pf.controls} wrapped control${pf.controls===1?'':'s'}`);
  if (pf.staleGuides) pf.warnings.push(`${pf.staleGuides} stale guide${pf.staleGuides===1?'':'s'}`);
  return pf;
}
function focusDiagnostic(issue){
  if(!issue?.id)return;const target=item(issue.id);if(!target)return;clearTransientInteractionVisuals('diagnostic-focus');ui.selected=new Set([issue.id]);reconcileCanvas({content:false});renderInspector();ui.componentNodes.get(issue.id)?.scrollIntoView?.({block:'center',inline:'center',behavior:'smooth'});ui.componentNodes.get(issue.id)?.focus?.({preventScroll:true});
}
function showPreflight() {
  const pf = preflight();
  $('#modalTitle').textContent = pf.issues.length?'Validation issues':'Ready to export';
  const summary=`<div class="modal-form"><div class="field-grid three"><div class="info-row"><span>Layout</span><b>${pf.layoutIssues.length}</b></div><div class="info-row"><span>Accessibility</span><b>${pf.accessibilityIssues.length}</b></div><div class="info-row"><span>Data</span><b>${pf.dataIssues.length}</b></div></div></div>`;
  const issues=pf.issues.length?`<div class="diagnostic-list">${pf.issues.map((issue,index)=>`<button type="button" class="diagnostic-item" data-diagnostic="${index}"><b>${issue.severity==='layout'?'!':issue.severity==='accessibility'?'A':'D'}</b><span><b>${esc(issue.message)}</b><span>${esc(issue.kind.replaceAll('-',' '))}${issue.id?` · ${esc(issue.id)}`:''}</span></span><em>${issue.id?'Focus':'Report'}</em></button>`).join('')}</div>`:'<div class="modal-form"><b>Ready to export</b><span>No layout, accessibility, or data issues were detected in the current rendered state.</span></div>';
  $('#modalBody').innerHTML = summary+issues;
  $('#modalBody').onclick=(event)=>{const button=event.target.closest('[data-diagnostic]');if(!button)return;const issue=pf.issues[+button.dataset.diagnostic];closeModals();focusDiagnostic(issue);};
  openModal($('#genericModal'));
}
function updateStatus({ recomputePreflight = true } = {}) {
  const pf = recomputePreflight || !ui.lastPreflight ? preflight() : ui.lastPreflight;
  if (recomputePreflight) ui.lastPreflight = pf;
  const mode=$('#modeStatus'); if(mode)mode.textContent=model().mode[0].toUpperCase()+model().mode.slice(1);
  const sel=$('#selStatus'); if(sel)sel.textContent=ui.selected.size?`${ui.selected.size} selected`:`${model().items.length} elements`;
  const zs=$('#zoomStatus'); if(zs)zs.textContent=`${Math.round(ui.zoom*100)}%`;
  const pre=$('#preflightStatus'); if(pre){pre.textContent=pf.issues.length?`${pf.layoutIssues.length} layout · ${pf.accessibilityIssues.length} access · ${pf.dataIssues.length} data`:'Ready to export';pre.className=`preflight-status-button ${pf.issues.length?'warn':'good'}`;}
  $('#undo').disabled = !store.canUndo; $('#redo').disabled = !store.canRedo;
  updateCommandEligibility();
}


function logicalPoint(e) {
  const r = $('#hull').getBoundingClientRect();
  return { x: (e.clientX - r.left) / ui.zoom, y: (e.clientY - r.top) / ui.zoom };
}
function beginPointerSession(target, e, handlers) {
  cancelPointerSession('superseded');
  const controller = new AbortController();
  const session = { pointerId: e.pointerId, target, controller, done: false, handlers };
  ui.pointerSession = session;
  if (activeRoot) activeRoot.dataset.pointerActive = 'true';
  try { target.setPointerCapture(e.pointerId); } catch { /* synthetic events */ }
  const finish = (kind, event) => {
    if (session.done) return;
    session.done = true;
    controller.abort();
    if (ui.pointerSession === session) ui.pointerSession = null;
    if (activeRoot) delete activeRoot.dataset.pointerActive;
    try { if (target.hasPointerCapture?.(e.pointerId)) target.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
    try {
      if (kind === 'end') handlers.end?.(event);
      else handlers.cancel?.(event, kind);
    } finally {
      clearTransientInteractionVisuals(`pointer-${kind}`);
    }
  };
  target.addEventListener('pointermove', (ev) => handlers.move?.(ev), { signal: controller.signal });
  target.addEventListener('pointerup', (ev) => finish('end', ev), { signal: controller.signal });
  target.addEventListener('pointercancel', (ev) => finish('cancel', ev), { signal: controller.signal });
  target.addEventListener('lostpointercapture', (ev) => { if (!session.done) finish('lostcapture', ev); }, { signal: controller.signal });
  return session;
}
function cancelPointerSession(reason = 'cancel') {
  const s = ui.pointerSession;
  if (!s || s.done) { clearTransientInteractionVisuals(reason); return; }
  s.done = true; s.controller.abort(); ui.pointerSession = null; if (activeRoot) delete activeRoot.dataset.pointerActive;
  try { s.handlers.cancel?.(null, reason); } finally { clearTransientInteractionVisuals(reason); }
}
function selectedMovers(id) {
  const entry = item(id);
  if (entry.groupId) return model().items.filter((x) => x.groupId === entry.groupId && !x.locked);
  if (ui.selected.has(id) && ui.selected.size > 1) return model().items.filter((x) => ui.selected.has(x.id) && !x.locked);
  return entry.locked ? [] : [entry];
}
function nearestSnap(value, targets, threshold=8) { let best=null; for(const target of targets){const off=target-value;if(Math.abs(off)<=threshold&&(!best||Math.abs(off)<Math.abs(best.off)))best={off,pos:target};}return best; }
function snapDelta(orig, dx, dy, movers) {
  const ids=new Set(movers.map(x=>x.id)); const rm=committedRectMap(); const others=[...rm.entries()].filter(([id])=>!ids.has(id)).map(([,r])=>r); const g=CANVAS.gap; let bestX=null,bestY=null;
  for(const o of orig){const base=rm.get(o.id);if(!base)continue;const r={x:o.x+dx,y:o.y+dy,w:base.w,h:base.h};const xt=[g,CANVAS.w-g-r.w,Math.round(r.x/g)*g];const yt=[g,CANVAS.h-g-r.h,Math.round(r.y/g)*g];for(const b of others){xt.push(b.x,b.x+b.w/2-r.w/2,b.x+b.w-r.w,b.x+b.w+g,b.x-r.w-g);yt.push(b.y,b.y+b.h/2-r.h/2,b.y+b.h-r.h,b.y+b.h+g,b.y-r.h-g);}const sx=nearestSnap(r.x,xt),sy=nearestSnap(r.y,yt);if(sx&&(!bestX||Math.abs(sx.off)<Math.abs(bestX.off)))bestX=sx;if(sy&&(!bestY||Math.abs(sy.off)<Math.abs(bestY.off)))bestY=sy;}
  return {dx:dx+(bestX?.off||0),dy:dy+(bestY?.off||0),gx:bestX?.pos,gy:bestY?.pos};
}
function snapResizeRect(entry, raw){if(model().mode!=='guided'||!ui.snap)return {...raw,gx:null,gy:null};const g=CANVAS.gap,rm=committedRectMap(),others=[...rm.entries()].filter(([id])=>id!==entry.id).map(([,r])=>r),right=raw.x+raw.w,bottom=raw.y+raw.h,xt=[CANVAS.w-g,Math.round(right/g)*g],yt=[CANVAS.h-g,Math.round(bottom/g)*g];for(const b of others){xt.push(b.x-g,b.x+b.w,b.x+b.w+g);yt.push(b.y-g,b.y+b.h,b.y+b.h+g);}const sx=nearestSnap(right,xt),sy=nearestSnap(bottom,yt),p=semanticPolicy(entry);return {...raw,w:Math.max(p.minW,(sx?.pos??right)-raw.x),h:Math.max(p.minH,(sy?.pos??bottom)-raw.y),gx:sx?.pos??null,gy:sy?.pos??null};}

function showGuides(d) {
  const v=$('#guideV'); const h=$('#guideH'); if(!v||!h)return;
  if (d.gx != null) { v.style.left = `${d.gx}px`; v.style.display = 'block'; } else v.style.display = 'none';
  if (d.gy != null) { h.style.top = `${d.gy}px`; h.style.display = 'block'; } else h.style.display = 'none';
  if(activeRoot)activeRoot.dataset.snapGuideCount=String((d.gx!=null?1:0)+(d.gy!=null?1:0));
  ui.guideReason='active-snap';
}
function hideGuides(reason='idle') {
  const v=$('#guideV'); const h=$('#guideH'); if(v)v.style.display='none'; if(h)h.style.display='none';
  if(activeRoot)activeRoot.dataset.snapGuideCount='0'; ui.guideEpoch+=1; ui.guideReason=reason;
}
function clearTransientInteractionVisuals(reason='idle') {
  hideGuides(reason);
  const ghost=$('#dropGhost'); if(ghost)ghost.style.display='none';
  const lasso=$('#lasso'); if(lasso)lasso.style.display='none'; ui.lasso=null;
  $$('.component.dragging').forEach((node)=>node.classList.remove('dragging'));
  if(activeRoot&&!ui.pointerSession){delete activeRoot.dataset.pointerActive;activeRoot.dataset.dragOverlayCount='0';activeRoot.dataset.resizeOverlayCount='0';}
}
function hasSelectedOverlap() {
  const rm = rectMap(); const ids = new Set(ui.selected); const selected = [...ids].map((id) => rm.get(id)).filter(Boolean);
  for (const a of selected) for (const [id, b] of rm) if (!ids.has(id) && overlap(a, b, 3)) return true;
  return false;
}
function smartOrderAt(q) {
  const rs = currentRects().map((r) => ({ ...r, cx: r.x + r.w / 2, cy: r.y + r.h / 2 }));
  rs.sort((a, b) => Math.hypot(q.x - a.cx, q.y - a.cy) - Math.hypot(q.x - b.cx, q.y - b.cy));
  return item(rs[0]?.id);
}
function showSmartReorderGhost(q, id) {
  const target = smartOrderAt(q); const g = $('#dropGhost'); const r = rectMap().get(target?.id || id);
  if (!r) return;
  Object.assign(g.style, { display: 'block', left: `${r.x}px`, top: `${r.y}px`, width: `${r.w}px`, height: `${r.h}px` });
}
function smartReorderOps(q, id) {
  const target = smartOrderAt(q); if (!target) return [];
  const moving = item(id).groupId ? model().items.filter((x) => x.groupId === item(id).groupId).map((x) => x.id) : ui.selected.size > 1 ? [...ui.selected] : [id];
  if (moving.includes(target.id)) return [];
  const ordered = [...model().items].sort((a, b) => a.order - b.order); const block = ordered.filter((x) => moving.includes(x.id)); const rest = ordered.filter((x) => !moving.includes(x.id));
  let idx = rest.findIndex((x) => x.id === target.id); if (idx < 0) idx = rest.length;
  rest.splice(idx, 0, ...block);
  return rest.map((entry, k) => entry.order === k ? null : { op: 'item.patch', id: entry.id, patch: { order: k } }).filter(Boolean);
}
function startDrag(e, id, el) {
  if(e.button!==0)return;const movers=selectedMovers(id);if(!movers.length)return toast('Locked component');e.preventDefault();e.stopPropagation();if(!ui.selected.has(id)){ui.selected.clear();ui.selected.add(id);renderAll();return;}
  const rm=committedRectMap(),p=logicalPoint(e),orig=movers.map(m=>{const r=rm.get(m.id);return{id:m.id,x:r.x,y:r.y}});movers.forEach(m=>$(`.component[data-id="${m.id}"]`)?.classList.add('dragging'));
  const previewAt=(ev)=>{const q=logicalPoint(ev),dx=q.x-p.x,dy=q.y-p.y;if(model().mode==='smart'){showSmartReorderGhost(q,id);return;}let sx=dx,sy=dy;if(model().mode==='guided'&&ui.snap){const d=snapDelta(orig,dx,dy,movers);sx=d.dx;sy=d.dy;showGuides(d);}const inset=model().mode==='guided'?CANVAS.gap:0;orig.forEach(o=>{const r=rm.get(o.id);ui.previewPatches.set(o.id,{x:clamp(o.x+sx,inset,CANVAS.w-inset-r.w),y:clamp(o.y+sy,inset,CANVAS.h-inset-r.h)});});renderGeometryOnly();};
  beginPointerSession(el,e,{move:previewAt,end(ev){hideGuides();$('#dropGhost').style.display='none';movers.forEach(m=>$(`.component[data-id="${m.id}"]`)?.classList.remove('dragging'));if(model().mode==='smart'){const ops=smartReorderOps(logicalPoint(ev),id);ui.previewPatches.clear();if(ops.length)commitOps('Reorder components',ops);else renderGeometryOnly();return;}previewAt(ev);if(model().mode==='guided'&&hasSelectedOverlap()){ui.previewPatches.clear();renderGeometryOnly();toast('Guided mode blocked an overlap');return;}const ops=[...ui.previewPatches.entries()].map(([entryId,patch])=>({op:'item.patch',id:entryId,patch}));ui.previewPatches.clear();if(ops.length)commitOps('Move components',ops);else renderGeometryOnly();},cancel(){hideGuides();$('#dropGhost').style.display='none';ui.previewPatches.clear();movers.forEach(m=>$(`.component[data-id="${m.id}"]`)?.classList.remove('dragging'));renderGeometryOnly();toast('Move cancelled');}});
}
function startResize(e,id,el){const entry=item(id);if(entry.locked)return toast('Locked component');e.preventDefault();e.stopPropagation();const p=logicalPoint(e),base=committedRectMap().get(id),start={x:base.x,y:base.y,w:base.w,h:base.h,weight:entry.weight};const previewAt=(ev)=>{const q=logicalPoint(ev),dx=q.x-p.x,dy=q.y-p.y;if(model().mode==='smart')ui.previewPatches.set(id,{weight:clamp(start.weight+(dx+dy)/240,.45,3.4)});else{const policy=semanticPolicy(entry),inset=model().mode==='guided'?CANVAS.gap:0;let raw={x:start.x,y:start.y,w:Math.min(Math.max(policy.minW,start.w+dx),CANVAS.w-start.x-inset),h:Math.min(Math.max(policy.minH,start.h+dy),CANVAS.h-start.y-inset)};raw=snapResizeRect(entry,raw);if(model().mode==='guided')showGuides(raw);ui.previewPatches.set(id,{w:raw.w,h:raw.h});}renderGeometryOnly();};beginPointerSession(el,e,{move:previewAt,end(ev){previewAt(ev);hideGuides('resize-end');if(model().mode==='guided'&&hasSelectedOverlap()){ui.previewPatches.clear();renderGeometryOnly();toast('Guided mode blocked resize overlap');return;}const patch=ui.previewPatches.get(id);ui.previewPatches.clear();if(patch)commitOps('Resize component',[{op:'item.patch',id,patch}]);else renderGeometryOnly();},cancel(){ui.previewPatches.clear();renderGeometryOnly();toast('Resize cancelled');}});}

function startLasso(e) {
  ui.selected.clear(); const p = logicalPoint(e); const box = $('#lasso'); box.style.display = 'block'; ui.lasso = { start: p };
  beginPointerSession($('#hull'), e, {
    move(ev) {
      const q = logicalPoint(ev); const x = Math.min(p.x, q.x); const y = Math.min(p.y, q.y); const w = Math.abs(q.x - p.x); const h = Math.abs(q.y - p.y);
      Object.assign(box.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
      const L = { x, y, w, h }; ui.selected = new Set(currentRects().filter((r) => overlap(L, r, 0)).map((r) => r.id));
      $$('.component').forEach((n) => { n.classList.toggle('selected', ui.selected.has(n.dataset.id)); n.setAttribute('aria-selected', ui.selected.has(n.dataset.id) ? 'true' : 'false'); });
    },
    end() { box.style.display = 'none'; ui.lasso = null; reconcileCanvas({ content: false }); renderInspector(); },
    cancel() { box.style.display = 'none'; ui.lasso = null; ui.selected.clear(); reconcileCanvas({ content: false }); renderInspector(); },
  });
}
function startPan(e) {
  const vp = $('#viewport'); const sx = e.clientX; const sy = e.clientY; const sl = vp.scrollLeft; const st = vp.scrollTop; vp.classList.add('panning');
  beginPointerSession(vp, e, {
    move(ev) { vp.scrollLeft = sl - (ev.clientX - sx); vp.scrollTop = st - (ev.clientY - sy); },
    end() { vp.classList.remove('panning'); },
    cancel() { vp.classList.remove('panning'); },
  });
}
function startBrush(e, handle) {
  e.stopPropagation(); e.preventDefault(); const comp = handle.closest('.component'); const entry = item(comp.dataset.id); const D = chartData(entry); const kind = handle.dataset.brush; const wrap = handle.closest('.chart-wrap'); const svg = $('.chart-svg', wrap); const initial = [...(entry.brush || [0, D.length - 1])]; let preview = [...initial];
  const updateDom = () => {
    const vb = svg.viewBox.baseVal; const left = 24; const right = 12; const plotW = vb.width - left - right; const bx1 = left + plotW * preview[0] / Math.max(1, D.length - 1); const bx2 = left + plotW * preview[1] / Math.max(1, D.length - 1);
    $('.brush-window', svg).setAttribute('x', bx1); $('.brush-window', svg).setAttribute('width', Math.max(3, bx2 - bx1)); $('.brush-handle-start', svg).setAttribute('x', bx1 - 3); $('.brush-handle-end', svg).setAttribute('x', bx2 - 3);
    const startHandle = $('[data-brush="start"]', wrap); const endHandle = $('[data-brush="end"]', wrap);
    startHandle.style.left = `${bx1 / vb.width * 100}%`; startHandle.setAttribute('aria-valuenow', preview[0]); endHandle.style.left = `${bx2 / vb.width * 100}%`; endHandle.setAttribute('aria-valuenow', preview[1]);
  };
  beginPointerSession(handle, e, {
    move(ev) { const r = svg.getBoundingClientRect(); const x = (ev.clientX - r.left) / r.width * svg.viewBox.baseVal.width; const left = 24; const right = 12; const plotW = svg.viewBox.baseVal.width - left - right; const k = clamp(Math.round((x - left) / plotW * (D.length - 1)), 0, D.length - 1); if (kind === 'start') preview[0] = Math.min(k, preview[1]); else preview[1] = Math.max(k, preview[0]); updateDom(); },
    end() { if (preview[0] !== initial[0] || preview[1] !== initial[1]) commitOps('Brush chart range', [{ op: 'item.patch', id: entry.id, patch: { brush: preview } }]); else reconcileCanvas(); },
    cancel() { reconcileCanvas(); toast('Brush cancelled'); },
  });
}

function normalizeOrderOps(items = model().items) { return [...items].sort((a, b) => a.order - b.order).map((entry, k) => entry.order === k ? null : { op: 'item.patch', id: entry.id, patch: { order: k } }).filter(Boolean); }
function addComponent(type, pos = null) {
  const canonical=quickCanonical[type]; if (!canonical) return;
  addLibraryElement(canonical[0],canonical[1],pos);
}
function addLibraryElement(element, engine, pos = null) {
  const type=engineToType[engine]||'text'; const d=typeDefaults[type]||typeDefaults.text; const id=`c${model().nextId}`;
  const entry={id,type,element,engine,title:element,showTitle:false,textAlign:'left',weight:d.weight,order:model().items.length,locked:false,groupId:null,z:Math.max(0,...model().items.map((x)=>x.z||0))+1,...starterContent(engine,element)};
  if (model().mode!=='smart') {
    const inset=model().mode==='guided'?CANVAS.gap:0; const width=Math.min(CANVAS.w-inset*2,d.minW*1.3); const height=Math.min(CANVAS.h-inset*2,d.minH*1.25);
    entry.x=clamp((pos?.x??CANVAS.w/2)-width/2,inset,CANVAS.w-inset-width); entry.y=clamp((pos?.y??CANVAS.h/2)-height/2,inset,CANVAS.h-inset-height); entry.w=width; entry.h=height;
  }
  const accepted=commitOps('Add Visembler element',[{op:'item.add',item:entry},{op:'model.patch',patch:{nextId:model().nextId+1}}],{announce:`${element} added`});
  if (!accepted) return;
  const recentKey=`${engine}::${element}`;ui.recentElements=[recentKey,...ui.recentElements.filter((key)=>key!==recentKey)].slice(0,8);storage.set('viz-library-recent',JSON.stringify(ui.recentElements));
  ui.selected=new Set([id]); renderAll(); renderLibrary();
}
function libraryEntries() {
  return Object.entries(ELEMENTS_BY_ENGINE).filter(([engine])=>!['EditorInfrastructure','InteractionLayer','SmartLayoutEngine'].includes(engine)).flatMap(([engine,elements])=>(Array.isArray(elements)?elements:[]).map((entry)=>({engine,element:typeof entry==='string'?entry:String(entry?.element||entry?.name||'')}))).filter((x)=>x.element);
}
function libraryDescription(entry) {
  return ({SmartLayoutEngine:'Composition and layout',TextEngine:'Narrative and annotation',MetricEngine:'KPI and measurement',ComparisonEngine:'Before / after comparison',CoreChartEngine:'Analytical chart',TableEngine:'Editable data grid',MatrixEngine:'Matrix and heatmap',TimelineEngine:'Milestones and sequence',DiagramEngine:'Nodes and connectors',ImageMediaEngine:'Image and media',EvidenceCompositeEngine:'Evidence and provenance',DecisionCompositeEngine:'Decision and risk',ProjectCompositeEngine:'Project execution',EngineeringChartEngine:'Engineering analysis',WaferFabEngine:'Wafer / fab analysis',InteractionLayer:'Interactive behavior',EditorInfrastructure:'Editor workflow'})[entry.engine]||'Report element';
}
function libraryThumbMarkup(entry) {
  const name=entry.element.toLowerCase(); const engine=entry.engine;
  if(engine==='MetricEngine'){
    if(name.includes('ring'))return '<span class="thumb-ring"></span>';
    if(name.includes('ladder'))return '<span class="thumb-ladder"><i></i><i></i><i></i></span>';
    if(name.includes('sparkline'))return '<svg viewBox="0 0 42 30" aria-hidden="true"><path d="M3 24 L11 17 L18 20 L26 8 L34 12 L39 4" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
    if(name.includes('threshold'))return '<span class="thumb-threshold"></span>';
    if(name.includes('capacity')||name.includes('progress'))return '<svg viewBox="0 0 42 30" aria-hidden="true"><rect x="3" y="12" width="36" height="7" rx="3" fill="currentColor" opacity=".2"/><rect x="3" y="12" width="25" height="7" rx="3" fill="currentColor"/></svg>';
    return `<span class="thumb-value">${name.includes('hero')?'84.2':'42.8'}</span>`;
  }
  if(engine==='CoreChartEngine'||engine==='EngineeringChartEngine')return '<svg viewBox="0 0 42 30" aria-hidden="true"><path d="M3 25 L10 18 L17 21 L24 10 L31 14 L39 5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 25 H39" stroke="currentColor" opacity=".25"/></svg>';
  if(engine==='TableEngine'||engine==='MatrixEngine')return `<span class="thumb-grid">${'<i></i>'.repeat(9)}</span>`;
  if(engine==='TimelineEngine')return '<svg viewBox="0 0 42 30" aria-hidden="true"><path d="M4 15 H38" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="15" r="3" fill="currentColor"/><circle cx="21" cy="15" r="3" fill="currentColor"/><circle cx="34" cy="15" r="3" fill="currentColor"/></svg>';
  if(engine==='DiagramEngine')return '<svg viewBox="0 0 42 30" aria-hidden="true"><rect x="2" y="10" width="11" height="9" rx="2" fill="none" stroke="currentColor"/><rect x="29" y="10" width="11" height="9" rx="2" fill="none" stroke="currentColor"/><path d="M13 14.5 H29 M25 11 L29 14.5 L25 18" fill="none" stroke="currentColor"/></svg>';
  if(engine==='ImageMediaEngine')return '<svg viewBox="0 0 42 30" aria-hidden="true"><rect x="3" y="4" width="36" height="23" rx="3" fill="none" stroke="currentColor"/><circle cx="13" cy="11" r="3" fill="currentColor" opacity=".55"/><path d="M5 25 L16 16 L23 21 L29 14 L38 25" fill="currentColor" opacity=".35"/></svg>';
  if(engine==='WaferFabEngine')return '<span class="thumb-wafer"></span>';
  if(engine==='TextEngine')return '<span class="thumb-lines"><i></i><i></i><i></i></span>';
  if(['EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine','ComparisonEngine'].includes(engine))return '<svg viewBox="0 0 42 30" aria-hidden="true"><rect x="3" y="4" width="36" height="22" rx="3" fill="none" stroke="currentColor"/><path d="M8 10 H33 M8 15 H28 M8 20 H24" stroke="currentColor" opacity=".55"/></svg>';
  return '<svg viewBox="0 0 42 30" aria-hidden="true"><rect x="4" y="5" width="34" height="20" rx="3" fill="none" stroke="currentColor"/><path d="M10 11 H32 M10 16 H27 M10 21 H30" stroke="currentColor" opacity=".45"/></svg>';
}
function libraryItemMarkup(entry) {
  const key=`${entry.engine}::${entry.element}`;const favorite=ui.favorites.has(key);
  return `<div class="library-item" draggable="true" data-element="${esc(entry.element)}" data-engine="${esc(entry.engine)}"><span class="library-thumb">${libraryThumbMarkup(entry)}</span><button type="button" class="library-copy library-insert" data-insert-element="true" title="Insert ${esc(entry.element)}"><b>${esc(entry.element)}</b><small>${esc(libraryDescription(entry))}</small></button><button type="button" class="favorite-toggle ${favorite?'active':''}" data-favorite="${esc(key)}" aria-label="${favorite?'Remove from':'Add to'} favorites" aria-pressed="${favorite?'true':'false'}">${favorite?'★':'☆'}</button></div>`;
}
function resolveEntryKey(key){const pos=String(key||'').indexOf('::');if(pos<0)return null;return {engine:key.slice(0,pos),element:key.slice(pos+2)};}
function toggleFavorite(key){if(ui.favorites.has(key))ui.favorites.delete(key);else ui.favorites.add(key);storage.set('viz-library-favorites',JSON.stringify([...ui.favorites]));renderLibrary();}
function renderLibrary() {
  const host=$('#fullLibrary'); if (!host) return;
  const query=String($('#componentSearch')?.value||'').trim().toLowerCase(); const engine=String($('#engineFilter')?.value||'');
  const all=libraryEntries(); const filtered=all.filter((entry)=>(!engine||entry.engine===engine)&&(!query||`${entry.element} ${entry.engine}`.toLowerCase().includes(query))); const shown=filtered.slice(0,ui.libraryLimit);
  host.innerHTML=shown.map(libraryItemMarkup).join('') || '<div class="keyboard-help">No elements match this search.</div>';
  const sections=$('#librarySections');if(sections){
    const byKey=new Map(all.map((entry)=>[`${entry.engine}::${entry.element}`,entry]));
    const recent=ui.recentElements.map((key)=>byKey.get(key)).filter(Boolean).slice(0,4);const favorites=[...ui.favorites].map((key)=>byKey.get(key)).filter(Boolean).slice(0,4);
    const recommended=['Hero KPI','Key Takeaway','Line Chart','Clean Table'].map((name)=>all.find((entry)=>entry.element===name)).filter(Boolean);
    sections.innerHTML=[favorites.length?`<div class="library-section-title"><span>Favorites</span></div><div class="library-mini-list">${favorites.map(libraryItemMarkup).join('')}</div>`:'',recent.length?`<div class="library-section-title"><span>Recent</span></div><div class="library-mini-list">${recent.map(libraryItemMarkup).join('')}</div>`:'',!query&&!engine?`<div class="library-section-title"><span>Recommended</span></div><div class="library-mini-list">${recommended.map(libraryItemMarkup).join('')}</div><div class="library-section-title"><span>All elements</span><small>${all.length}</small></div>`:''].join('');
  }
  const more=$('#libraryMore'); if (more) { more.hidden=shown.length>=filtered.length; more.textContent=shown.length<filtered.length?`Show more · ${shown.length}/${filtered.length}`:`${filtered.length} shown`; }
}

function initializeLibrary() {
  const select=$('#engineFilter'); if (select && !select.dataset.ready) { select.innerHTML='<option value="">All families</option>'+Object.keys(ELEMENTS_BY_ENGINE).map((engine)=>`<option value="${esc(engine)}">${esc(engine.replace(/Engine|Composite|Layer|Infrastructure/g,''))}</option>`).join(''); select.dataset.ready='true'; }
  renderLibrary();
}
function deleteSelected() {
  const ids = [...ui.selected].filter((id) => !item(id)?.locked); if (!ids.length) return toast('Nothing deletable selected');
  const ops = ids.map((id) => ({ op: 'item.remove', id }));
  for (const [gid, group] of Object.entries(model().groups)) if (group.items.some((id) => ids.includes(id))) ops.push({ op: 'group.set', id: gid, value: { ...group, items: group.items.filter((id) => !ids.includes(id)) } });
  const survivors = model().items.filter((entry) => !ids.includes(entry.id));
  ops.push(...normalizeOrderOps(survivors)); ui.selected.clear(); commitOps('Delete components', ops, { announce: `${ids.length} component${ids.length > 1 ? 's' : ''} deleted` });
}
function toggleLock() {
  if (!ui.selected.size) return; const want = [...ui.selected].some((id) => !item(id).locked); const ops = [...ui.selected].map((id) => ({ op: 'item.patch', id, patch: { locked: want } })); commitOps(want ? 'Lock selection' : 'Unlock selection', ops, { announce: want ? 'Selection locked' : 'Selection unlocked' });
}
function groupSelected() {
  if (ui.selected.size < 2) return toast('Select 2+ components');
  const gid = `g${store.revision}-${model().nextId}`; const ids = [...ui.selected]; const ops = [{ op: 'group.set', id: gid, value: { id: gid, items: ids } }, ...ids.map((id) => ({ op: 'item.patch', id, patch: { groupId: gid } }))]; commitOps('Group selection', ops, { announce: 'Group created' });
}
function ungroupSelected() {
  const gids = new Set([...ui.selected].map((id) => item(id)?.groupId).filter(Boolean)); if (!gids.size) return toast('No selected group');
  const ops = []; for (const gid of gids) { model().items.filter((entry) => entry.groupId === gid).forEach((entry) => ops.push({ op: 'item.patch', id: entry.id, patch: { groupId: null } })); ops.push({ op: 'group.delete', id: gid }); }
  commitOps('Ungroup selection', ops, { announce: 'Ungrouped' });
}
function layer(delta) { if (!ui.selected.size) return; commitOps(delta > 0 ? 'Bring forward' : 'Send backward', [...ui.selected].map((id) => ({ op: 'item.patch', id, patch: { z: clamp((item(id).z || 1) + delta, 0, 99) } }))); }
function align(kind) {
  if (model().mode === 'smart') return toast('Align is automatic in Smart mode'); if (ui.selected.size < 2) return toast('Select 2+ components');
  const rm = rectMap(); const A = [...ui.selected].map((id) => ({ entry: item(id), r: rm.get(id) })); const u = rectUnion(A.map((x) => x.r)); const ops = [];
  for (const x of A) { const patch = {}; if (kind === 'left') patch.x = u.x; if (kind === 'top') patch.y = u.y; if (kind === 'center') patch.x = u.x + (u.w - x.r.w) / 2; if (kind === 'middle') patch.y = u.y + (u.h - x.r.h) / 2; ops.push({ op: 'item.patch', id: x.entry.id, patch }); }
  commitOps(`Align ${kind}`, ops);
}
function distribute(axis) {
  if (model().mode === 'smart') return toast('Distribution is automatic in Smart mode'); if (ui.selected.size < 3) return toast('Select 3+ components');
  const A = [...ui.selected].map((id) => item(id)).sort((a, b) => axis === 'x' ? a.x - b.x : a.y - b.y); const ops = [];
  if (axis === 'x') { const first = A[0]; const last = A.at(-1); const span = last.x + last.w - first.x; const sum = A.reduce((s, entry) => s + entry.w, 0); const gap = (span - sum) / (A.length - 1); let x = first.x; A.forEach((entry) => { ops.push({ op: 'item.patch', id: entry.id, patch: { x } }); x += entry.w + gap; }); }
  else { const first = A[0]; const last = A.at(-1); const span = last.y + last.h - first.y; const sum = A.reduce((s, entry) => s + entry.h, 0); const gap = (span - sum) / (A.length - 1); let y = first.y; A.forEach((entry) => { ops.push({ op: 'item.patch', id: entry.id, patch: { y } }); y += entry.h + gap; }); }
  commitOps(`Distribute ${axis}`, ops);
}
function performModeSwitch(nextMode) {
  if (model().mode === nextMode) return;
  const ops = [];
  if (model().mode === 'smart' && nextMode !== 'smart') { const sm = new Map(smartRects(model().items).map((r) => [r.id, r])); model().items.forEach((entry) => { const r = sm.get(entry.id); ops.push({ op: 'item.patch', id: entry.id, patch: { x: r.x, y: r.y, w: r.w, h: r.h } }); }); }
  ops.push({ op: 'model.patch', patch: { mode: nextMode } }); commitOps('Change canvas mode', ops);
}
function setMode(nextMode) {
  if(model().mode===nextMode)return;
  cancelPointerSession('mode-switch');clearTransientInteractionVisuals('mode-switch');
  if(nextMode==='smart'&&model().mode!=='smart'&&model().items.length){
    $('#modalTitle').textContent='Switch to Smart mode?';$('#modalBody').innerHTML='<div class="modal-form"><b>Smart mode will recompose the report.</b><span>Your manual Guided/Free positions remain in the report model, but Smart mode owns the visible composition while active.</span><div class="modal-actions"><button type="button" class="tb" id="modeCancel">Keep manual mode</button><button type="button" class="tb accent" id="modeConfirm">Recompose</button></div></div>';$('#modeCancel').onclick=closeModals;$('#modeConfirm').onclick=()=>{closeModals();performModeSwitch('smart');};openModal($('#genericModal'),$('#modeConfirm'));return;
  }
  performModeSwitch(nextMode);
}
function applySuggestion(preset) {
  const ops = [{ op: 'model.patch', patch: { layoutPreset: preset, mode: 'smart' } }];
  const orderMap = preset === 'executive' ? ['metric', 'text', 'chart', 'timeline', 'tabs', 'table', 'image', 'diagram', 'risk'] : preset === 'technical' ? ['diagram', 'chart', 'table', 'timeline', 'metric', 'tabs', 'text', 'image', 'risk'] : null;
  if (orderMap) [...model().items].sort((a, b) => orderMap.indexOf(a.type) - orderMap.indexOf(b.type)).forEach((entry, k) => { if (entry.order !== k) ops.push({ op: 'item.patch', id: entry.id, patch: { order: k } }); });
  commitOps('Apply layout suggestion', ops, { announce: `${preset[0].toUpperCase() + preset.slice(1)} composition applied` });
}
function autoLayout() { cancelPointerSession('reflow');clearTransientInteractionVisuals('reflow');const ops = [{ op: 'model.patch', patch: { mode: 'smart' } }, ...normalizeOrderOps()]; commitOps('Reflow report', ops, { announce: 'Smart composition reflowed' }); }
function duplicateOne(id) {
  const source = item(id); const copy = structuredClone(source); const nextId = `c${model().nextId}`; copy.id = nextId; copy.order = model().items.length; copy.z = (source.z || 1) + 1; copy.title = `${source.title} copy`; copy.groupId = null;
  if (model().mode !== 'smart') { copy.x = clamp(source.x + 24, 0, CANVAS.w - source.w); copy.y = clamp(source.y + 24, 0, CANVAS.h - source.h); }
  commitOps('Duplicate component', [{ op: 'item.add', item: copy }, { op: 'model.patch', patch: { nextId: model().nextId + 1 } }]); ui.selected = new Set([nextId]); renderAll();
}
const CLIPBOARD_PREFIX='VISMBLER_P0:';
function copySemanticSelection(kind='visual_full') {
  if(ui.selected.size!==1)return toast('Select one visual to copy'); const entry=item([...ui.selected][0]); if(!entry)return;
  const dataset=selectedDataset(entry); const payload={version:1,kind,entry:structuredClone(entry),dataset:dataset?structuredClone(dataset):null}; ui.semanticClipboard=payload;
  const encoded=CLIPBOARD_PREFIX+JSON.stringify(payload); navigator.clipboard?.writeText?.(encoded).catch(()=>{}); toast(kind==='visual_full'?'Visual copied':`${kind.replace('_',' ')} copied`); return payload;
}
function pasteSemanticPayload(payload, mode='auto') {
  if(!payload?.entry)return false; const source=payload.entry;
  if(mode==='data' || payload.kind==='dataset_data') {
    if(ui.selected.size!==1||!payload.dataset)return false; const target=item([...ui.selected][0]); const id=target.dataset_id||datasetId(), dataset={...structuredClone(payload.dataset),id,revision:(selectedDataset(target)?.revision||0)+1};
    return !!commitOps('Paste dataset data',[{op:'model.patch',patch:{datasets:model().datasets.some(value=>value.id===id)?model().datasets.map(value=>value.id===id?dataset:value):[...model().datasets,dataset]}},{op:'item.patch',id:target.id,patch:{dataset_id:id,mapping:structuredClone(source.mapping||{}),...canonicalPatch(target,dataset,source.mapping||{})}}],{announce:'Pasted data'});
  }
  if(mode==='mapping' || payload.kind==='mapping') { if(ui.selected.size!==1)return false;const target=item([...ui.selected][0]),dataset=selectedDataset(target);if(!dataset)return false;const mapping=structuredClone(source.mapping||{});return !!commitOps('Paste mapping',[{op:'item.patch',id:target.id,patch:{mapping,...canonicalPatch(target,dataset,mapping)}}],{announce:'Pasted mapping'}); }
  if(mode==='style' || payload.kind==='style') { if(ui.selected.size!==1)return false;const target=item([...ui.selected][0]);const style=['title','showTitle','textAlign','weight','emphasis','variant','unit'].reduce((out,key)=>{if(key in source)out[key]=source[key];return out;},{});return !!commitOps('Paste style',[{op:'item.patch',id:target.id,patch:style}],{announce:'Pasted style'}); }
  const copy=structuredClone(source),nextId=`c${model().nextId}`;copy.id=nextId;copy.order=model().items.length;copy.z=(source.z||0)+1;copy.groupId=null;copy.title=`${source.title} copy`;
  let datasets=model().datasets; if(payload.dataset&&mode==='independent'){const cloned={...structuredClone(payload.dataset),id:datasetId(),name:`${payload.dataset.name} copy`,revision:1};datasets=[...datasets,cloned];copy.dataset_id=cloned.id;Object.assign(copy,canonicalPatch(copy,cloned,copy.mapping||{}));}
  if(model().mode!=='smart'){copy.x=clamp((source.x||0)+24,0,CANVAS.w-(source.w||200));copy.y=clamp((source.y||0)+24,0,CANVAS.h-(source.h||140));}
  const ops=[{op:'item.add',item:copy},{op:'model.patch',patch:{nextId:model().nextId+1,...(datasets!==model().datasets?{datasets}:{})}}];const accepted=commitOps(mode==='independent'?'Paste independent visual':'Paste linked visual',ops,{announce:mode==='independent'?'Pasted independent visual':'Pasted linked visual'});if(accepted)ui.selected=new Set([nextId]);return !!accepted;
}
function semanticPayloadFromText(text) { if(!String(text||'').startsWith(CLIPBOARD_PREFIX))return null;try{return JSON.parse(String(text).slice(CLIPBOARD_PREFIX.length));}catch{return null;} }
function showDropGhost(e) { const g = $('#dropGhost'); if (model().mode === 'smart') Object.assign(g.style, { display: 'block', left: '6px', top: `${CANVAS.h - 80}px`, width: `${CANVAS.w - 12}px`, height: '70px' }); else { const p = logicalPoint(e); Object.assign(g.style, { display: 'block', left: `${clamp(p.x - 90, 0, CANVAS.w - 180)}px`, top: `${clamp(p.y - 60, 0, CANVAS.h - 120)}px`, width: '180px', height: '120px' }); } }

function toggleChartPoint(entry, k) { const cross = entry.cross === k ? null : k; const crossFilter = cross == null ? null : chartData(entry)[cross][0]; commitOps('Toggle chart cross-filter', [{ op: 'item.patch', id: entry.id, patch: { cross } }, { op: 'model.patch', patch: { crossFilter } }]); }
function drillChartPoint(entry, k) { commitOps('Drill chart point', [{ op: 'item.patch', id: entry.id, patch: { drill: k } }]); }
function setBrushByKeyboard(entry, kind, delta) { const D = chartData(entry); const next = [...(entry.brush || [0, D.length - 1])]; if (kind === 'start') next[0] = clamp(next[0] + delta, 0, next[1]); else next[1] = clamp(next[1] + delta, next[0], D.length - 1); if (next[0] !== entry.brush[0] || next[1] !== entry.brush[1]) commitOps('Adjust brush range', [{ op: 'item.patch', id: entry.id, patch: { brush: next } }]); }
function parsePaste(txt) { const result=intakeText(txt); return result.rows.length ? result : null; }
function datasetId() { return `dataset-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`; }
function fieldById(dataset, id) { return dataset.fields.find((field)=>field.id===id); }
function fieldIndex(dataset, id) { return dataset.fields.findIndex((field)=>field.id===id); }
function valuesFor(dataset, id) { const index=fieldIndex(dataset,id); return index<0?[]:dataset.rows.map(row=>row[index]); }
function canonicalPatch(entry, dataset, mapping) {
  dataset=applyRecipe(dataset,entry.transform_recipe);
  const pick=(role)=>valuesFor(dataset,mapping[role]); const names=(role)=>fieldById(dataset,mapping[role])?.name||role;
  if(entry.engine==='TableEngine'||entry.type==='table') return {customTable:{headers:dataset.fields.map(field=>field.name),rows:dataset.rows},rows:dataset.rows};
  if(entry.engine==='MatrixEngine') { const rowIndex=fieldIndex(dataset,mapping.category||mapping.y),columnIndex=fieldIndex(dataset,mapping.series||mapping.x),valueIndex=fieldIndex(dataset,mapping.value);if(rowIndex>=0&&columnIndex>=0&&valueIndex>=0)return {matrix_long:dataset.rows.map(row=>({row:row[rowIndex],column:row[columnIndex],value:row[valueIndex]}))};return {matrix:[dataset.fields.map(field=>field.name),...dataset.rows]}; }
  if(entry.engine==='DiagramEngine'&&mapping.source&&mapping.target) { const source=pick('source'),target=pick('target'); const nodes=[...new Set([...source,...target].map(value=>String(value??'')).filter(Boolean))]; return {nodes,edges:source.map((value,index)=>[String(value??''),String(target[index]??'')]).filter(edge=>edge[0]&&edge[1])}; }
  if(entry.engine==='WaferFabEngine') { const first=(role)=>{const index=fieldIndex(dataset,mapping[role]);return index<0?null:dataset.rows.find(row=>row[index]!==null&&row[index]!==undefined&&String(row[index]).trim()!=='')?.[index]??null;};return {observations:dataset.rows.map(row=>({x:row[fieldIndex(dataset,mapping.die_x||mapping.x)],y:row[fieldIndex(dataset,mapping.die_y||mapping.y)],value:row[fieldIndex(dataset,mapping.value)]})),wafer_id:first('wafer_id'),lot:first('lot_id'),tool:first('tool'),chamber:first('chamber'),recipe:first('recipe'),process:first('process'),bin:first('bin'),fab_rows:dataset.rows.map(row=>Object.fromEntries(dataset.fields.map((field,index)=>[field.name,row[index]]))),fab_fields:dataset.fields.map(field=>({id:field.id,name:field.name,type:field.type})),fab_mapping:mapping}; }
  if(entry.engine==='TimelineEngine') return {milestones:dataset.rows.map((row,index)=>({label:String(row[fieldIndex(dataset,mapping.category||mapping.label)]??index+1),date:row[fieldIndex(dataset,mapping.time)]??null}))};
  if(entry.engine==='EngineeringChartEngine') { const valueIndex=fieldIndex(dataset,mapping.value),labelIndex=fieldIndex(dataset,mapping.time||mapping.category||mapping.x),subgroupIndex=fieldIndex(dataset,mapping.subgroup);const grouped=new Map();dataset.rows.forEach(row=>{const key=subgroupIndex<0?null:String(row[subgroupIndex]??'');if(key!==null){if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(row[valueIndex]);}});const first=(role)=>{const index=fieldIndex(dataset,mapping[role]);return index<0?null:dataset.rows.find(row=>row[index]!==null&&row[index]!==undefined)?.[index]??null;};return {observations:dataset.rows.map((row,index)=>({label:String(row[labelIndex]??index+1),value:row[valueIndex]})),subgroups:[...grouped.values()],specification_low:first('specification_low'),specification_high:first('specification_high'),analysis_rows:dataset.rows.map(row=>Object.fromEntries(dataset.fields.map((field,index)=>[field.name,row[index]]))),analysis_fields:dataset.fields.map(field=>({id:field.id,name:field.name,type:field.type})),analysis_mapping:mapping}; }
  const labelId=mapping.category||mapping.label||mapping.time||mapping.x||dataset.fields[0]?.id; const valueId=mapping.value||mapping.y||dataset.fields.find(field=>['integer','number'].includes(field.type))?.id; const labels=valuesFor(dataset,labelId), values=valuesFor(dataset,valueId); const firstValue=values.find(value=>value!==null&&value!==undefined), lastValue=[...values].reverse().find(value=>value!==null&&value!==undefined);
  if(entry.engine==='MetricEngine') return {value:lastValue??null,unit:fieldById(dataset,valueId)?.unit||entry.unit||'',title:String(labels.at(-1)||entry.title)};
  if(entry.engine==='ComparisonEngine') return {before:firstValue??null,after:lastValue??null,title:String(labels.at(-1)||entry.title)};
  if(['TextEngine','EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'].includes(entry.engine)) return {text:String(lastValue??labels.at(-1)??''),body:String(lastValue??labels.at(-1)??''),statement:String(lastValue??labels.at(-1)??''),detail:`Mapped from ${fieldById(dataset,valueId)?.name||'data'}`};
  const data=dataset.rows.map((_,index)=>[String(labels[index]??index+1),values[index]]); return {data,rows:data.map(([label,value])=>({label,value})),brush:[0,Math.max(0,data.length-1)],cross:null,drill:null,subtitle:`Mapped ${names(labelId)} to ${names(valueId)}`};
}
function pasteToBlank(result) {
  const recommendation=result.recommendations[0]; const view=recommendation?.view||'table'; const engine=({bar:'CoreChartEngine',line:'CoreChartEngine',scatter:'CoreChartEngine',table:'TableEngine',wafer:'WaferFabEngine',diagram:'DiagramEngine',engineering:'EngineeringChartEngine'})[view]||'TableEngine';
  const type=engineToType[engine]||'table', defaults=typeDefaults[type]||typeDefaults.table, id=`c${model().nextId}`, dataId=datasetId(), dataset=datasetFromIntake(result,dataId,'Pasted data'), mapping=result.candidate_mappings[0]?.mapping||{};
  const entry={id,type,element:view==='wafer'?'Wafer Map':view==='diagram'?'Data Flow':view==='engineering'?'SPC Control Chart':view==='table'?'Clean Table':'Bar Chart',engine,title:recommendation?.view==='table'?'Pasted data':`${recommendation?.view||'Data'} view`,showTitle:false,textAlign:'left',weight:defaults.weight,order:model().items.length,locked:false,groupId:null,z:Math.max(0,...model().items.map((item)=>item.z||0))+1,dataset_id:dataId,view_type:view,mapping,...starterContent(engine,'')};
  Object.assign(entry,canonicalPatch(entry,dataset,mapping));
  const accepted=commitOps('Paste data onto canvas',[{op:'model.patch',patch:{datasets:[...model().datasets,dataset],nextId:model().nextId+1}},{op:'item.add',item:entry}],{announce:`Created ${entry.title}`}); if(accepted) ui.selected=new Set([id]); return !!accepted;
}
function pasteToSelection(txt) {
  const parsed=parsePaste(txt); if (!parsed) return false;
  if(ui.selected.size!==1) return pasteToBlank(parsed);
  const entry=item([...ui.selected][0]); if(!entry) return pasteToBlank(parsed);
  const dataId=entry.dataset_id||datasetId(), existing=model().datasets.find((dataset)=>dataset.id===dataId), dataset={...datasetFromIntake(parsed,dataId,existing?.name||'Pasted data'),revision:(existing?.revision||0)+1}, mapping=parsed.candidate_mappings[0]?.mapping||{};
  const datasets=existing?model().datasets.map((value)=>value.id===dataId?dataset:value):[...model().datasets,dataset];
  const patch={dataset_id:dataId,view_type:entry.view_type||entry.type,mapping,...canonicalPatch(entry,dataset,mapping)};
  return !!commitOps('Paste data into visual',[{op:'model.patch',patch:{datasets,crossFilter:null}},{op:'item.patch',id:entry.id,patch}],{announce:parsed.warnings.length?'Pasted with data warnings':'Pasted data into visual'});
}
async function pasteImage(file) {
  const src=await validatedImageDataUrl(file); let entry=ui.selected.size===1?item([...ui.selected][0]):null;
  if (entry?.engine!=='ImageMediaEngine') { addLibraryElement('Image','ImageMediaEngine'); entry=item([...ui.selected][0]); }
  if (!entry) return false; return !!commitOps('Paste image',[{op:'item.patch',id:entry.id,patch:{src}}],{announce:'Image pasted'});
}

function showTip(e, n) { const entry = item(n.closest('.component').dataset.id); if(entry?.behaviors?.tooltip===false)return; const d = chartData(entry)[+(n.dataset.point??n.dataset.behaviorPoint)]; if(!d)return; const tip = $('#tooltip'); tip.innerHTML = `<b>${esc(d[0])}</b><span>${d[1]} · activate to cross-filter</span>`; tip.style.display = 'block'; moveTip(e); }
function moveTip(e) { const tip = $('#tooltip'); tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY + 12}px`; }
function hideTip() { $('#tooltip').style.display = 'none'; }
function runKpiAnimations() {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  $$('[data-kpi]').forEach((el) => {
    const id = el.dataset.kpi; if (!ui.kpiAnimate.has(id)) return; const target = item(id).value; ui.kpiAnimate.delete(id);
    if (reduce) { el.textContent = `${target}%`; return; }
    const start = performance.now();
    function tick(t) { const p = clamp((t - start) / 620, 0, 1); el.textContent = `${Math.round(target * (1 - Math.pow(1 - p, 3)))}%`; if (p < 1) requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  });
}
function toast(text) { const x = $('#toast'); x.textContent = text; x.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => x.classList.remove('show'), matchMedia('(prefers-reduced-motion: reduce)').matches ? 600 : 1500); }

function setZoom(z, renderMini = true) {
  ui.zoom=clamp(z,0.55,1.40); ui.contextSize=null; ui.contextBoundsCache=null; const scene=$('#scene'); const frame=$('#sceneFrame'); if (!scene || !frame) return;
  scene.style.transform=`scale(${ui.zoom})`; scene.style.setProperty('--viz-interaction-scale',String(ui.zoom<1?1/ui.zoom:1)); frame.style.width=`${(SCENE.w*ui.zoom).toFixed(2)}px`; frame.style.height=`${(SCENE.h*ui.zoom).toFixed(2)}px`; const zs=$('#zoomStatus'); if(zs)zs.textContent=`${Math.round(ui.zoom*100)}%`; if(renderMini)renderMinimap(rectMap()); requestAnimationFrame(()=>{positionMinimap();if(ui.selected.size)renderContext(rectMap());});
}
function fitZoom() { const vp=$('#viewport'); if(!vp)return; const pad=36; const z=Math.min((vp.clientWidth-pad)/SCENE.w,(vp.clientHeight-pad)/SCENE.h,1.15); ui.autoFit=true; setZoom(z); requestAnimationFrame(()=>{vp.scrollLeft=Math.max(0,(vp.scrollWidth-vp.clientWidth)/2);vp.scrollTop=Math.max(0,(vp.scrollHeight-vp.clientHeight)/2);}); }
function togglePreview() { ui.preview=!ui.preview; activeRoot?.classList.toggle('preview-mode',ui.preview); if(ui.preview)requestAnimationFrame(fitZoom); }
const builtInPresets=Object.freeze([{id:'editorial',name:'Editorial Bento',description:'Balanced narrative and analytical hierarchy.'},{id:'executive',name:'Executive',description:'Promote KPI, takeaway, comparison and decision.'},{id:'technical',name:'Technical',description:'Promote diagram, table, timeline and engineering evidence.'}]);
function normalizedPersonalPresets(raw) { const result=[]; for(const value of Array.isArray(raw)?raw:[]){try{if(!value||typeof value!=='object')continue;const name=String(value.name||'').trim().slice(0,80);const modelValue=typeof value.model==='string'?parseCanonical(value.model):parseCanonical(serializeCanonical(value.model));if(!name||modelBytes(modelValue)>MAX_MODEL_BYTES)continue;result.push({id:String(value.id||localCommitId('preset')),name,model:modelValue});if(result.length>=50)break;}catch{/* isolate corrupt preset */}} return result; }
function schedulePresetListRender(){if(presetRenderFrame)cancelAnimationFrame(presetRenderFrame);presetRenderFrame=requestAnimationFrame(()=>{presetRenderFrame=0;renderPresetList();});}
function persistPersonalPresets(){personalPresets=normalizedPersonalPresets(personalPresets);storage.set('viz-prod-presets-cache',JSON.stringify(personalPresets));dispatchSemantic('preset.preferences_save_requested',{presets:personalPresets});schedulePresetListRender();}
function savePresetNamed(name){const cleaned=String(name||'').trim().slice(0,80);if(!cleaned)return toast('Preset name cannot be blank');personalPresets.unshift({id:localCommitId('preset'),name:cleaned,model:parseCanonical(store.serialize())});persistPersonalPresets();toast('Personal preset saved');}
function savePreset(){
  $('#modalTitle').textContent='Save as preset';$('#modalBody').innerHTML='<form class="modal-form" id="presetSaveForm"><label for="presetSaveName"><b>Preset name</b></label><input id="presetSaveName" maxlength="80" autocomplete="off" placeholder="Quarterly review layout"><small>Personal presets are editable. Built-in presets remain immutable.</small><div class="modal-actions"><button type="button" class="tb" data-close>Cancel</button><button type="submit" class="tb accent">Save preset</button></div></form>';
  const form=$('#presetSaveForm');form.addEventListener('submit',(event)=>{event.preventDefault();const name=$('#presetSaveName').value;if(!String(name).trim())return toast('Enter a preset name');savePresetNamed(name);closeModals();});
  $('[data-close]',form)?.addEventListener('click',closeModals,{once:true});openModal($('#genericModal'),$('#presetSaveName'));
}
function renderPresetList(){const built=$('#builtinPresetList');if(built)built.innerHTML=builtInPresets.map((p)=>`<div class="preset"><div class="preset-copy"><b>${esc(p.name)}</b><small>${esc(p.description)}</small></div><button class="mini-btn" data-built-preset="${p.id}">Apply</button></div>`).join('');const host=$('#presetList');if(!host)return;host.innerHTML=personalPresets.length?personalPresets.slice(0,20).map((p,index)=>`<div class="preset"><div class="preset-copy"><input class="preset-name-edit" data-preset-rename="${index}" value="${esc(p.name)}" aria-label="Preset name"><small>Personal preset</small></div><div class="preset-actions"><button class="mini-btn" data-loadpreset="${index}">Apply</button><button class="mini-btn" data-updatepreset="${index}">Update</button><button class="mini-btn" data-duplicatepreset="${index}">Duplicate</button><button class="mini-btn" data-deletepreset="${index}">Delete</button></div></div>`).join(''):'<div class="keyboard-help">No personal presets yet. Save the current report when you have a reusable composition.</div>';}
function loadPreset(index){const saved=personalPresets[index];if(!saved)return;try{const next=parseCanonical(serializeCanonical(saved.model));const base=store.revision;store.replaceModel(next,'Load preset');ui.selected.clear();renderAll();dispatchSemantic('report.commit',{report_id:String(bootstrap.report_id||'default'),base_revision:base,commit_id:localCommitId('preset-load',base),model:next});toast('Preset loaded');}catch{toast('Preset is corrupt and was not loaded');}}
function updatePreset(index){if(!personalPresets[index])return;personalPresets[index]={...personalPresets[index],model:parseCanonical(store.serialize())};persistPersonalPresets();toast('Preset updated');}
function duplicatePreset(index){const source=personalPresets[index];if(!source)return;personalPresets.splice(index+1,0,{id:localCommitId('preset'),name:`${source.name} copy`.slice(0,80),model:parseCanonical(serializeCanonical(source.model))});persistPersonalPresets();toast('Preset duplicated');}
function renamePreset(index,name){if(!personalPresets[index])return;const cleaned=String(name||'').trim().slice(0,80);if(!cleaned){schedulePresetListRender();return toast('Preset name cannot be blank');}personalPresets[index]={...personalPresets[index],name:cleaned};persistPersonalPresets();}
function deletePreset(index){if(!personalPresets[index])return;personalPresets.splice(index,1);persistPersonalPresets();toast('Preset deleted');}
function hydratePresets(){try{personalPresets=normalizedPersonalPresets(JSON.parse(storage.get('viz-prod-presets-cache')||'[]'));}catch{personalPresets=[];storage.remove('viz-prod-presets-cache');}renderPresetList();dispatchSemantic('preset.preferences_requested',{});}
function saveReport(){dispatchSemantic('report.save_requested',{report_id:String(bootstrap.report_id||'default'),revision:store.revision});toast('Save requested');}
function exportPpt(){const pf=preflight();if(pf.layoutIssues.length||pf.dataIssues.length){showPreflight();return toast('Resolve export-blocking validation issues first');}dispatchSemantic('ppt.export_requested',{report_id:String(bootstrap.report_id||'default'),revision:store.revision});toast('PowerPoint export requested');}
function exportModel(){showPreflight();const blob=new Blob([store.exportEnvelope(2)],{type:'application/json'});const a=document.createElement('a');const url=URL.createObjectURL(blob);a.href=url;a.download='visembler_report_model.json';setTimeout(()=>{a.click();URL.revokeObjectURL(url);},80);toast('Canonical report model exported');}
function openExportMenu(){
  const pf=preflight();$('#modalTitle').textContent='Export';$('#modalBody').innerHTML=`<div class="modal-form"><div class="info-row"><span>Validation</span><b>${pf.issues.length?`${pf.issues.length} issue${pf.issues.length===1?'':'s'}`:'Ready'}</b></div><button type="button" class="tb accent full-width" id="exportPptAction">PowerPoint</button><button type="button" class="tb full-width" id="exportJsonAction">Report JSON</button><small>PowerPoint keeps supported report objects editable and uses the configured template content region.</small></div>`;$('#exportPptAction').onclick=()=>{closeModals();exportPpt();};$('#exportJsonAction').onclick=()=>{closeModals();exportModel();};openModal($('#genericModal'));
}
function openHelp(){
  $('#modalTitle').textContent='Help & shortcuts';$('#modalBody').innerHTML='<div class="help-grid"><kbd>⌘/Ctrl K</kbd><span>Open commands</span><kbd>⌘/Ctrl Z</kbd><span>Undo</span><kbd>⇧⌘/Ctrl Z</kbd><span>Redo</span><kbd>Delete</kbd><span>Delete unlocked selection</span><kbd>G</kbd><span>Group eligible selection</span><kbd>L</kbd><span>Lock / unlock selection</span><kbd>Space + drag</kbd><span>Pan canvas</span><kbd>Esc</kbd><span>Cancel interaction / clear selection</span><kbd>Double click</kbd><span>Edit element directly</span></div>';openModal($('#genericModal'));
}
function developerSnapshot() {
  const pf=preflight(); const modelValue=parseCanonical(store.serialize());
  return {report_id:bootstrap.report_id,revision:store.revision,mode:modelValue.mode,items:modelValue.items.length,selected:[...ui.selected],pending_commits:ui.pendingCommits.size,model_bytes:modelBytes(modelValue),preflight:{layout:pf.layoutIssues.length,accessibility:pf.accessibilityIssues.length,data:pf.dataIssues.length},pointer_active:!!ui.pointerSession,editor_ready:activeRoot?.dataset.editorReady||'unknown'};
}
function renderDeveloperConsole() {
  const body=$('#debugBody'),summary=$('#debugSummary'); if(!body||!summary)return;
  const snapshot=developerSnapshot(); summary.textContent=`Revision ${snapshot.revision} · ${snapshot.items} elements · ${ui.debugLog.length} events`;
  const state=Object.entries(snapshot).filter(([key])=>key!=='preflight').map(([key,value])=>`<div><span>${esc(key.replaceAll('_',' '))}</span><b>${esc(Array.isArray(value)?value.join(', ')||'none':value)}</b></div>`).join('');
  const log=ui.debugLog.length?ui.debugLog.map((entry)=>`<div class="debug-event ${esc(entry.level)}"><time>${esc(entry.time)}</time><b>${esc(entry.level)}</b><span>${esc(entry.event)}</span><small>${esc(entry.detail)}</small></div>`).join(''):'<div class="debug-empty">No events yet. Interact with the editor to inspect actions, bridge messages, and errors here.</div>';
  body.innerHTML=`<div class="debug-actions"><button type="button" class="tb" data-debug-action="refresh">Refresh diagnostics</button><button type="button" class="tb" data-debug-action="copy">Copy diagnostic</button><button type="button" class="tb" data-debug-action="model">Copy model</button><button type="button" class="tb" data-debug-action="clear">Clear log</button></div><section class="debug-section"><b>Live state</b><div class="debug-state">${state}<div><span>preflight</span><b>${snapshot.preflight.layout} layout · ${snapshot.preflight.accessibility} access · ${snapshot.preflight.data} data</b></div></div></section><section class="debug-section"><b>Event stream</b><div class="debug-log" aria-live="polite">${log}</div></section>`;
}
async function copyDeveloperPayload(kind) {
  const payload=kind==='model'?parseCanonical(store.serialize()):{snapshot:developerSnapshot(),events:ui.debugLog};
  const text=JSON.stringify(payload,null,2);
  try { await navigator.clipboard?.writeText?.(text); toast(`${kind==='model'?'Model':'Diagnostic'} copied`); }
  catch { debugEvent('warn','Clipboard unavailable','Use Report JSON export if copy permission is denied'); toast('Clipboard permission is unavailable'); }
}
function openDeveloperConsole() { renderDeveloperConsole(); openModal($('#debugModal')); }
function setLibraryTab(tab){ui.libraryTab=tab==='presets'?'presets':'elements';$$('[data-library-tab]').forEach((button)=>{const active=button.dataset.libraryTab===ui.libraryTab;button.classList.toggle('active',active);button.setAttribute('aria-selected',active?'true':'false');});const ev=$('#elementsView'),pv=$('#presetsView');if(ev)ev.hidden=ui.libraryTab!=='elements';if(pv)pv.hidden=ui.libraryTab!=='presets';if(ui.libraryTab==='presets')renderPresetList();}
function setInspector(open){ui.inspectorOpen=!!open;activeRoot?.setAttribute('data-inspector',ui.inspectorOpen?'open':'closed');storage.set('viz-inspector-open',ui.inspectorOpen?'1':'0');requestAnimationFrame(()=>{if(ui.autoFit||ui.preview)fitZoom();else renderGeometryOnly();});}

const commands = [
  ['Add KPI', 'Add a metric component', () => addComponent('metric')], ['Add chart', 'Add an analytical chart', () => addComponent('chart')], ['Add table', 'Add an evidence table', () => addComponent('table')], ['Add timeline', 'Add an interactive timeline', () => addComponent('timeline')], ['Reflow report', 'Recompose with Smart Layout', autoLayout], ['Executive layout', 'Apply executive composition', () => applySuggestion('executive')], ['Technical layout', 'Apply technical composition', () => applySuggestion('technical')], ['Group selection', 'Group selected components', groupSelected], ['Toggle lock', 'Lock or unlock selection', toggleLock], ['Save preset', 'Save current report as a personal preset', savePreset], ['Run preflight', 'Validate current composition', showPreflight], ['Export JSON', 'Download canonical report model', exportModel], ['Zoom to fit', 'Fit the whole report canvas', fitZoom],
];
function renderCommands(query = '') {
  const needle = query.toLowerCase(); const filtered = commands.map((c, index) => ({ c, index })).filter(({ c }) => `${c[0]} ${c[1]}`.toLowerCase().includes(needle)); ui.commandIndex = clamp(ui.commandIndex, 0, Math.max(0, filtered.length - 1));
  $('#cmdList').innerHTML = filtered.map(({ c, index }, k) => `<div class="cmd ${k === ui.commandIndex ? 'active' : ''}" role="option" aria-selected="${k === ui.commandIndex ? 'true' : 'false'}" data-command="${index}" data-visible-index="${k}" tabindex="-1"><div><b>${c[0]}</b><span>${c[1]}</span></div><span>↵</span></div>`).join('');
}
function openPalette() { ui.commandIndex = 0; $('#cmdInput').value = ''; renderCommands(''); openModal($('#cmdModal'), $('#cmdInput')); }
function executeCommandIndex(index) { commands[index]?.[2](); closeModals(); }
function openModal(modal, focusTarget = null) { ui.modalReturnFocus = document.activeElement; modal.classList.add('show'); requestAnimationFrame(() => (focusTarget || $('button, input, select, textarea, [tabindex]:not([tabindex="-1"])', modal))?.focus()); }
function closeModals() { $$('.modal.show').forEach((m) => m.classList.remove('show')); const target = ui.modalReturnFocus; ui.modalReturnFocus = null; target?.focus?.({ preventScroll: true }); }
function trapModalFocus(e) {
  const modal = e.target.closest('.modal.show'); if (!modal || e.key !== 'Tab') return;
  const nodes = $$('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', modal).filter((n) => n.offsetParent !== null); if (!nodes.length) return;
  const first = nodes[0]; const last = nodes.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

async function handleEmptyAction(entry,action){
  if(!entry)return;ui.selected=new Set([entry.id]);
  if(action==='add-row'){const grid=paddedTable(entry);grid.rows.push(Array(grid.headers.length).fill(null));return commitOps('Add table row',[{op:'item.patch',id:entry.id,patch:{customTable:grid,rows:grid.rows}}]);}
  if(action==='add-node')return commitOps('Add diagram node',[{op:'item.patch',id:entry.id,patch:{nodes:[`Node 1`],edges:[]}}]);
  if(action==='add-event')return commitOps('Add timeline event',[{op:'item.patch',id:entry.id,patch:{milestones:[{label:'Event 1',date:null}],tm:0}}]);
  if(action==='upload'){setInspector(true);renderInspector();requestAnimationFrame(()=>$('#iImageFile')?.click());return;}
  if(action==='paste-image'){toast('Paste an image with Ctrl/Cmd+V');return;}
  if(action==='enter'){setInspector(true);renderInspector();requestAnimationFrame(()=>$('#iData')?.focus());return;}
  if(action==='paste'){
    try{const text=await navigator.clipboard?.readText?.();if(text&&pasteToSelection(text))return;}catch{/* permission fallback */}
    setInspector(true);renderInspector();requestAnimationFrame(()=>{const selector=entry.engine==='TableEngine'?'[data-table-cell]':'#iData';$(selector)?.focus();});toast('Press Ctrl/Cmd+V to paste spreadsheet data');
  }
}
function onHullClick(e) {
  const interactive = e.target.closest('[data-action], [data-tab], [data-tm], [data-point], [data-behavior-point], [data-ctx], [data-empty-action], .brush-handle');
  const comp = e.target.closest('.component');
  if (interactive) {
    e.stopPropagation();
    if (interactive.dataset.ctx) { if(interactive.disabled)return;const a = interactive.dataset.ctx; if (a === 'lock') toggleLock(); else if (a === 'group') groupSelected(); else if(a==='ungroup')ungroupSelected();else if (a === 'front') layer(1); else deleteSelected(); return; }
    if (!comp) return; const entry = item(comp.dataset.id);
    if(interactive.dataset.emptyAction){handleEmptyAction(entry,interactive.dataset.emptyAction);return;}
    if (interactive.dataset.action === 'detail') commitOps('Toggle metric detail', [{ op: 'item.patch', id: entry.id, patch: { detail: !entry.detail } }]);
    else if (interactive.dataset.action === 'reveal') commitOps('Toggle chart reveal', [{ op: 'item.patch', id: entry.id, patch: { revealed: !entry.revealed } }]);
    else if (interactive.dataset.action === 'expand') commitOps('Toggle expanded detail', [{ op: 'item.patch', id: entry.id, patch: { expanded: !entry.expanded, ...(model().mode === 'smart' ? { weight: clamp(entry.weight + (entry.expanded ? -0.3 : 0.3), 0.6, 3) } : {}) } }]);
    else if (interactive.dataset.tab) commitOps('Switch tab', [{ op: 'item.patch', id: entry.id, patch: { tab: interactive.dataset.tab } }]);
    else if (interactive.dataset.tm != null) commitOps('Select timeline milestone', [{ op: 'item.patch', id: entry.id, patch: { tm: +interactive.dataset.tm } }]);
    else if (interactive.dataset.point != null) toggleChartPoint(entry, +interactive.dataset.point);
    else if (interactive.dataset.behaviorPoint != null && entry.behaviors?.cross_filter!==false) toggleChartPoint(entry,+interactive.dataset.behaviorPoint);
    return;
  }
  if (!comp) return;
  const id = comp.dataset.id;
  if (e.shiftKey) ui.selected.has(id) ? ui.selected.delete(id) : ui.selected.add(id); else if (!(ui.selected.size === 1 && ui.selected.has(id))) { ui.selected.clear(); ui.selected.add(id); }
  reconcileCanvas({ content: false }); renderInspector(); comp.focus({ preventScroll: true });
}
function focusEditorField(selector) {
  setInspector(true);
  requestAnimationFrame(() => { const field=$(selector); field?.focus?.({preventScroll:true}); field?.select?.(); });
}
function openInlineEditor(entry, comp, directKind=null) {
  if (!entry || entry.locked || !comp) return;
  comp.querySelector('.direct-editor')?.remove();
  const wrap=document.createElement('div'); wrap.className='direct-editor';
  const isText=entry.engine==='TextEngine', isMetric=entry.engine==='MetricEngine', isTitle=directKind==='title', milestoneIndex=directKind?.startsWith('milestone:')?Number(directKind.split(':')[1]):null, directParts=String(directKind||'').split(':'),isDatasetCell=directParts[0]==='dataset-cell',isDatasetHeader=directParts[0]==='dataset-header',isTableCell=directParts[0]==='table-cell',isTableHeader=directParts[0]==='table-header';
  if (!isText && !isMetric && !isTitle && !Number.isInteger(milestoneIndex) && !isDatasetCell && !isDatasetHeader && !isTableCell && !isTableHeader) return;
  const directDataset=selectedDataset(entry),directRow=Number(directParts[1]),directColumn=Number(directParts[2]);const directGrid=paddedTable(entry);
  const control=document.createElement(isText?'textarea':'input');
  control.className='direct-editor-control';
  control.value=String(isText?(entry.text??entry.body??''):isMetric?(entry.value??''):isTitle?(entry.title??entry.element):Number.isInteger(milestoneIndex)?entry.milestones?.[milestoneIndex]?.label??'':isDatasetCell?directDataset?.rows?.[directRow]?.[directColumn]??'':isDatasetHeader?directDataset?.fields?.[Number(directParts[1])]?.name??'':isTableCell?directGrid.rows?.[directRow]?.[directColumn]??'':directGrid.headers?.[Number(directParts[1])]??'');
  if(!isText){control.type='text';if(isMetric||isDatasetCell||isTableCell)control.inputMode='decimal';control.setAttribute('aria-label',isTitle?'Component title':Number.isInteger(milestoneIndex)?'Timeline label':isDatasetHeader||isTableHeader?'Table column name':isDatasetCell||isTableCell?'Table cell':'Metric value');}
  else {control.rows=5;control.setAttribute('aria-label','Text content');}
  wrap.appendChild(control); comp.appendChild(wrap);
  let settled=false;
  const finish=(commit=true)=>{if(settled)return;settled=true;const value=control.value.trim();wrap.remove();if(!commit)return;if(isText)commitOps('Edit text inline',[{op:'item.patch',id:entry.id,patch:{text:value,body:value}}]);else if(isMetric)commitOps('Edit metric inline',[{op:'item.patch',id:entry.id,patch:{value:parseTypedCell(value)}}]);else if(isTitle)commitOps('Edit title inline',[{op:'item.patch',id:entry.id,patch:{title:value||entry.element}}]);else if(isDatasetCell&&directDataset?.rows?.[directRow]){const next=structuredClone(directDataset);next.rows[directRow][directColumn]=parseTypedCell(value);next.revision=(next.revision||0)+1;commitDataset(entry,'Edit dataset table cell',next);}else if(isDatasetHeader&&directDataset?.fields?.[Number(directParts[1])]){const next=structuredClone(directDataset);next.fields[Number(directParts[1])].name=value||`Column ${Number(directParts[1])+1}`;next.revision=(next.revision||0)+1;commitDataset(entry,'Rename dataset table column',next);}else if(isTableCell){while(directGrid.rows.length<=directRow)directGrid.rows.push(Array(directGrid.headers.length).fill(null));directGrid.rows[directRow][directColumn]=parseTypedCell(value);commitOps('Edit table cell inline',[{op:'item.patch',id:entry.id,patch:{customTable:directGrid,rows:directGrid.rows}}]);}else if(isTableHeader){directGrid.headers[Number(directParts[1])]=value||`Column ${Number(directParts[1])+1}`;commitOps('Rename table column inline',[{op:'item.patch',id:entry.id,patch:{customTable:directGrid,rows:directGrid.rows}}]);}else {const milestones=structuredClone(entry.milestones||[]);if(!milestones[milestoneIndex])return;milestones[milestoneIndex].label=value||`Step ${milestoneIndex+1}`;commitOps('Edit timeline label inline',[{op:'item.patch',id:entry.id,patch:{milestones}}]);}};
  control.addEventListener('pointerdown',(ev)=>ev.stopPropagation()); control.addEventListener('click',(ev)=>ev.stopPropagation()); control.addEventListener('dblclick',(ev)=>ev.stopPropagation());
  control.addEventListener('keydown',(ev)=>{if(ev.key==='Escape'){ev.preventDefault();finish(false);}else if((ev.metaKey||ev.ctrlKey)&&ev.key==='Enter'){ev.preventDefault();finish(true);}});
  control.addEventListener('blur',()=>finish(true),{once:true});
  requestAnimationFrame(()=>{control.focus({preventScroll:true});control.select?.();});
}
function onHullDoubleClick(e) {
  const point=e.target.closest('[data-point]');
  if(point){e.stopPropagation();const entry=item(point.closest('.component').dataset.id);drillChartPoint(entry,+point.dataset.point);return;}
  const behaviorPoint=e.target.closest('[data-behavior-point]');
  if(behaviorPoint){e.stopPropagation();const entry=item(behaviorPoint.closest('.component').dataset.id);if(entry?.behaviors?.drill!==false)drillChartPoint(entry,+behaviorPoint.dataset.behaviorPoint);return;}
  const comp=e.target.closest('.component'); if(!comp)return;
  e.preventDefault(); e.stopPropagation(); const entry=item(comp.dataset.id); if(!entry)return;
  ui.selected.clear();ui.selected.add(entry.id);reconcileCanvas({content:false});renderInspector();
  const direct=e.target.closest('[data-direct]');
  if(direct?.dataset.direct?.startsWith('milestone:')&&entry.dataset_id){focusEditorField('[data-dataset-cell]');toast('Edit linked timeline labels in the Data Dock');return;}
  if(entry.engine==='TextEngine'||entry.engine==='MetricEngine'||direct){openInlineEditor(entry,comp,direct?.dataset.direct||null);return;}
  const focusByEngine={CoreChartEngine:'#iData',TableEngine:'[data-table-cell], [data-table-header]',MatrixEngine:'#iMatrix',TimelineEngine:'#iTimeline',DiagramEngine:'#iNodes',ImageMediaEngine:'#iImageFile',EngineeringChartEngine:'#iObservations',WaferFabEngine:'#iTool',ComparisonEngine:'#iBefore',EvidenceCompositeEngine:'#iStatement',DecisionCompositeEngine:'#iStatement',ProjectCompositeEngine:'#iStatement'};
  focusEditorField(focusByEngine[entry.engine]||'#iTitle');
}
function onHullPointerDown(e) {
  const handle = e.target.closest('.brush-handle'); if (handle) return startBrush(e, handle);
  const resize = e.target.closest('.resize-h'); if (resize) return startResize(e, resize.closest('.component').dataset.id, resize);
  const head = e.target.closest('.c-head'); if (head) return startDrag(e, head.closest('.component').dataset.id, head);
  if (e.target === $('#hull') || e.target.classList.contains('canvas-grid') || e.target.id === 'componentLayer') { if (ui.space) startPan(e); else startLasso(e); }
}
function onHullKeyDown(e) {
  const point = e.target.closest('[data-point]'); if (point && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleChartPoint(item(point.closest('.component').dataset.id), +point.dataset.point); return; }
  const brush = e.target.closest('.brush-handle'); if (brush && ['ArrowLeft', 'ArrowRight'].includes(e.key)) { e.preventDefault(); setBrushByKeyboard(item(brush.closest('.component').dataset.id), brush.dataset.brush, e.key === 'ArrowLeft' ? -1 : 1); return; }
  const comp = e.target.closest('.component'); if (comp && e.target === comp && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); const id = comp.dataset.id; if (e.shiftKey) ui.selected.has(id) ? ui.selected.delete(id) : ui.selected.add(id); else { ui.selected.clear(); ui.selected.add(id); } reconcileCanvas({ content: false }); renderInspector(); }
}
function wireGlobal(signal) {
  const on=(node,event,handler,options={})=>node?.addEventListener(event,handler,{...options,signal});
  on($('#debugBtn'),'click',openDeveloperConsole);
  on($('#debugModal'),'click',(event)=>{if(event.target===$('#debugModal'))return closeModals();const button=event.target.closest('[data-debug-action]');if(!button)return;const action=button.dataset.debugAction;if(action==='refresh')return renderDeveloperConsole();if(action==='clear'){ui.debugLog=[];return renderDeveloperConsole();}if(action==='copy')copyDeveloperPayload('diagnostic');if(action==='model')copyDeveloperPayload('model');});
  $$('[data-mode]').forEach((button)=>on(button,'click',()=>setMode(button.dataset.mode))); on($('#undo'),'click',undo); on($('#redo'),'click',redo); on($('#auto'),'click',autoLayout); on($('#group'),'click',groupSelected); on($('#ungroup'),'click',ungroupSelected); on($('#lock'),'click',toggleLock); on($('#front'),'click',()=>layer(1)); on($('#back'),'click',()=>layer(-1)); on($('#preflightBtn'),'click',showPreflight);on($('#preflightStatus'),'click',showPreflight); on($('#presetSave'),'click',savePreset); on($('#commandBtn'),'click',openPalette);on($('#helpBtn'),'click',openHelp); on($('#previewBtn'),'click',togglePreview); on($('#previewExit'),'click',togglePreview); on($('#saveBtn'),'click',saveReport); on($('#exportBtn'),'click',openExportMenu);
  on($('#zoomIn'),'click',()=>{ui.autoFit=false;setZoom(ui.zoom+.1);}); on($('#zoomOut'),'click',()=>{ui.autoFit=false;setZoom(ui.zoom-.1);}); on($('#zoomFit'),'click',fitZoom); on($('#miniToggle'),'click',()=>{ui.showMini=!ui.showMini;$('#miniToggle').setAttribute('aria-pressed',ui.showMini?'true':'false');renderMinimap(rectMap());});
  on($('#inspectorClose'),'click',()=>setInspector(false)); on($('#inspectorToggle'),'click',()=>setInspector(true));
  $$('.pal').forEach((p)=>{p.draggable=true;on(p,'click',()=>addComponent(p.dataset.type));on(p,'dragstart',(e)=>{e.dataTransfer.setData('application/x-viz-type',p.dataset.type);e.dataTransfer.effectAllowed='copy';});});
  $$('[data-library-tab]').forEach((button)=>on(button,'click',()=>setLibraryTab(button.dataset.libraryTab)));
  on($('#componentSearch'),'input',()=>{ui.libraryLimit=60;renderLibrary();}); on($('#engineFilter'),'change',()=>{ui.libraryLimit=60;renderLibrary();}); on($('#libraryMore'),'click',()=>{ui.libraryLimit+=60;renderLibrary();});
  const libraryClick=(e)=>{const favorite=e.target.closest('[data-favorite]');if(favorite){e.preventDefault();e.stopPropagation();return toggleFavorite(favorite.dataset.favorite);}const block=e.target.closest('[data-element][data-engine]');if(block)addLibraryElement(block.dataset.element,block.dataset.engine);};
  const libraryDrag=(e)=>{const block=e.target.closest('[data-element][data-engine]');if(!block)return;e.dataTransfer.setData('application/x-viz-element',JSON.stringify({element:block.dataset.element,engine:block.dataset.engine}));e.dataTransfer.effectAllowed='copy';};
  on($('#fullLibrary'),'click',libraryClick);on($('#librarySections'),'click',libraryClick);on($('#fullLibrary'),'dragstart',libraryDrag);on($('#librarySections'),'dragstart',libraryDrag);
  on($('#builtinPresetList'),'click',(e)=>{const button=e.target.closest('[data-built-preset]');if(button)applySuggestion(button.dataset.builtPreset);});
  on($('#presetList'),'click',(e)=>{const load=e.target.closest('[data-loadpreset]');const update=e.target.closest('[data-updatepreset]');const dup=e.target.closest('[data-duplicatepreset]');const del=e.target.closest('[data-deletepreset]');if(load)loadPreset(+load.dataset.loadpreset);else if(update)updatePreset(+update.dataset.updatepreset);else if(dup)duplicatePreset(+dup.dataset.duplicatepreset);else if(del)deletePreset(+del.dataset.deletepreset);});
  on($('#presetList'),'change',(e)=>{const input=e.target.closest('[data-preset-rename]');if(input)renamePreset(+input.dataset.presetRename,input.value);});
  on($('#inspector'),'click',(e)=>{const suggestion=e.target.closest('[data-suggestion]');if(suggestion)applySuggestion(suggestion.dataset.suggestion);const action=e.target.closest('[data-inspector]');if(!action)return;const value=action.dataset.inspector;if(value==='align-left')align('left');else if(value==='align-top')align('top');else if(value==='align-center')align('center');else if(value==='distribute-x')distribute('x');else if(value==='distribute-y')distribute('y');else if(value==='group')groupSelected();else if(value==='ungroup')ungroupSelected();else if(value==='lock')toggleLock();});
  const hull=$('#hull'); on(hull,'click',onHullClick);on(hull,'dblclick',onHullDoubleClick);on(hull,'pointerdown',onHullPointerDown);on(hull,'keydown',onHullKeyDown);
  on(hull,'dragover',(e)=>{e.preventDefault();showDropGhost(e);});on(hull,'dragleave',(e)=>{if(!hull.contains(e.relatedTarget))$('#dropGhost').style.display='none';});on(hull,'drop',(e)=>{e.preventDefault();$('#dropGhost').style.display='none';const encoded=e.dataTransfer.getData('application/x-viz-element');if(encoded){try{const payload=JSON.parse(encoded);return addLibraryElement(payload.element,payload.engine,logicalPoint(e));}catch{/* fall through */}}const type=e.dataTransfer.getData('application/x-viz-type')||e.dataTransfer.getData('text/plain');if(typeDefaults[type])addComponent(type,logicalPoint(e));});
  on(hull,'mouseover',(e)=>{const node=e.target.closest('[data-point], [data-behavior-point]');if(node)showTip(e,node);});on(hull,'mousemove',(e)=>{if(e.target.closest('[data-point], [data-behavior-point]'))moveTip(e);});on(hull,'mouseout',(e)=>{if(e.target.closest('[data-point], [data-behavior-point]')&&!e.relatedTarget?.closest?.('[data-point], [data-behavior-point]'))hideTip();});
  on($('#cmdInput'),'input',(e)=>{ui.commandIndex=0;renderCommands(e.target.value);}); on($('#cmdInput'),'keydown',(e)=>{const options=$$('[data-command]',$('#cmdList'));if(e.key==='ArrowDown'){e.preventDefault();ui.commandIndex=clamp(ui.commandIndex+1,0,Math.max(0,options.length-1));renderCommands(e.target.value);}else if(e.key==='ArrowUp'){e.preventDefault();ui.commandIndex=clamp(ui.commandIndex-1,0,Math.max(0,options.length-1));renderCommands(e.target.value);}else if(e.key==='Enter'){e.preventDefault();const active=$('[aria-selected="true"]',$('#cmdList'));if(active)executeCommandIndex(+active.dataset.command);}}); on($('#cmdList'),'click',(e)=>{const node=e.target.closest('[data-command]');if(node)executeCommandIndex(+node.dataset.command);});
  $$('[data-close]').forEach((button)=>on(button,'click',closeModals));$$('.modal').forEach((modal)=>on(modal,'click',(e)=>{if(e.target===modal)closeModals();}));on(document,'keydown',trapModalFocus);
  on(window,'keydown',(e)=>{const tag=document.activeElement?.tagName;const editing=tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT';if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette();return;}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();return;}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='y'){e.preventDefault();redo();return;}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='c'&&!editing){e.preventDefault();copySemanticSelection(e.shiftKey?'dataset_data':'visual_full');return;}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='v'&&!editing&&ui.semanticClipboard){const payload=ui.semanticClipboard;e.preventDefault();pasteSemanticPayload(payload,e.shiftKey?'independent':'auto');return;}if(e.key==='Escape'){cancelPointerSession();if($('.modal.show'))closeModals();else{ui.selected.clear();reconcileCanvas({content:false});renderInspector();}return;}if(editing)return;if(e.code==='Space'){ui.space=true;e.preventDefault();}if(e.key==='Delete'||e.key==='Backspace')deleteSelected();if(e.key.toLowerCase()==='g'&&!e.metaKey&&!e.ctrlKey)groupSelected();if(e.key.toLowerCase()==='l'&&!e.metaKey&&!e.ctrlKey)toggleLock();if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)&&model().mode!=='smart'&&ui.selected.size){e.preventDefault();const step=e.shiftKey?10:1;const dx=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0;const dy=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;const inset=model().mode==='guided'?CANVAS.gap:0;const ops=[...ui.selected].filter((id)=>!item(id).locked).map((id)=>{const entry=item(id);return{op:'item.patch',id,patch:{x:clamp(entry.x+dx,inset,CANVAS.w-inset-entry.w),y:clamp(entry.y+dy,inset,CANVAS.h-inset-entry.h)}};});if(ops.length)commitOps('Nudge selection',ops);}});
  on(window,'keyup',(e)=>{if(e.code==='Space')ui.space=false;});on(window,'blur',()=>{ui.space=false;cancelPointerSession('window-blur');});
  on(window,'error',(event)=>debugEvent('error','Window error',event.error?.stack||event.message)); on(window,'unhandledrejection',(event)=>debugEvent('error','Unhandled rejection',event.reason?.stack||event.reason));
  on(window,'paste',async(e)=>{const tag=document.activeElement?.tagName;if(tag==='INPUT'||tag==='TEXTAREA')return;const image=[...(e.clipboardData?.files||[])].find((file)=>String(file.type||'').startsWith('image/'));if(image){e.preventDefault();try{await pasteImage(image);}catch(err){toast(String(err.message||err));}return;}const text=e.clipboardData?.getData('text/plain');const semantic=semanticPayloadFromText(text);if(semantic&&pasteSemanticPayload(semantic)){e.preventDefault();return;}if(text&&pasteToSelection(text))e.preventDefault();});
}

function setupResizeObserver() {
  window.__VIZ_RESIZE_OBSERVER__?.disconnect?.();
  if (typeof ResizeObserver==='undefined'||!$('#viewport')) return;
  let raf=0; const observer=new ResizeObserver(()=>{ui.resizeEpoch+=1;cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>{if(ui.autoFit||ui.preview)fitZoom();else renderGeometryOnly();});}); observer.observe($('#viewport')); window.__VIZ_RESIZE_OBSERVER__=observer;
}
function buildSelfTest() {
  const result = { smartHull: preflight().coverage === 100, initialOverlaps: preflight().overlaps, revisionSafety: false, undoRedo: false, pointerLifecycle: true, resizeObserver: !!window.__VIZ_RESIZE_OBSERVER__, deterministic: false, noPointerMoveFullRender: true };
  const before = store.serialize(); const rev = store.revision;
  try {
    const cmd = store.command([{ op: 'model.patch', patch: { layoutPreset: 'executive' } }], 'QA command'); store.commit(cmd); result.revisionSafety = false;
    try { store.commit({ ...cmd, id: `${cmd.id}-stale` }); } catch (err) { result.revisionSafety = err instanceof RevisionConflictError; }
    store.undo(store.revision); result.undoRedo = store.serialize() === before; result.deterministic = serializeCanonical(parseCanonical(store.serialize())) === store.serialize();
  } catch (err) { result.error = String(err); }
  result.final = result.smartHull && result.initialOverlaps === 0 && result.revisionSafety && result.undoRedo && result.pointerLifecycle && result.resizeObserver && result.deterministic;
  document.body.dataset.qa = result.final ? 'pass' : 'fail'; $('#qaHidden').textContent = JSON.stringify(result); window.__VIZ_QA__ = result; return result;
}
function init(root=$('.cui-visualizer-root')) {
  if (!root) return false;
  if (root===activeRoot && root.dataset.editorReady==='true') return true;
  eventAbort?.abort(); cancelPointerSession('rebind'); window.__VIZ_RESIZE_OBSERVER__?.disconnect?.(); activeRoot=root; eventAbort=new AbortController();
  activeRoot.dataset.editorReady='false'; activeRoot.setAttribute('data-inspector',ui.inspectorOpen?'open':'closed'); $('#authoringVersion')?.replaceChildren(AUTHORING_VERSION);
  ensureCanvasScaffold(); initializeLibrary(); hydratePresets(); wireGlobal(eventAbort.signal); renderAll(); setupResizeObserver(); setInspector(storage.get('viz-inspector-open')!=='0'); requestAnimationFrame(fitZoom);
  activeRoot.dataset.editorReady='true';
  window.__VIZ_PROD__={store,ui,preflight,buildSelfTest,serialize:()=>store.serialize(),setTheme:(theme)=>document.documentElement.setAttribute('data-theme',theme),cancelPointerSession,renderAll,renderGeometryOnly,setZoom,fitZoom,setInspector,addLibraryElement,renderLibrary,snapDelta,snapResizeRect};
  if(new URLSearchParams(location.search).get('qa')==='1')setTimeout(buildSelfTest,120); return true;
}
function installRootObserver(){if(window.__CUI_VISUALIZER_ROOT_OBSERVER__)return;const observer=new MutationObserver(()=>{const root=$('.cui-visualizer-root');if(root&&root!==activeRoot)init(root);});observer.observe(document.documentElement,{subtree:true,childList:true});window.__CUI_VISUALIZER_ROOT_OBSERVER__=observer;}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{init();installRootObserver();},{once:true});else{init();installRootObserver();}
