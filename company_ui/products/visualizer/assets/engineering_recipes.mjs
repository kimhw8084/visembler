// Deterministic semiconductor analysis recipes.
//
// A recipe is deliberately split into three concerns:
//   1. compatibility discovery (what the data can support),
//   2. mapping review (what is automatic, unresolved, or confirmed), and
//   3. execution planning (which production elements are created).
// Execution is performed by the Editor transaction layer; this module never
// mutates report state and never executes arbitrary code.

const clone=value=>typeof structuredClone==='function'?structuredClone(value):JSON.parse(JSON.stringify(value));
const numericTypes=new Set(['integer','number']);
const tagsOf=fields=>new Set((fields||[]).flatMap(field=>Array.isArray(field.semantic_tags)?field.semantic_tags:[]));
const fieldByTag=(fields,tag)=>fields.find(field=>(field.semantic_tags||[]).includes(tag));
const fieldByName=(fields,pattern)=>fields.find(field=>pattern.test(String(field.name||'').toLowerCase()));
const fieldId=field=>field?.id||null;

export const RECIPE_VERSION='v1';

// Limited to elements already in the production library. Hidden fab variants
// are evaluated separately and are not silently made executable by a recipe.
export const RECIPE_TARGETS=Object.freeze({
  'yield-pareto':Object.freeze([
    {engine:'CoreChartEngine',element:'Pareto',view:'pareto',role:'primary'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
    {engine:'MetricEngine',element:'Hero KPI',view:'metric',role:'summary'},
  ]),
  'spc-excursion':Object.freeze([
    {engine:'EngineeringChartEngine',element:'SPC Control Chart',view:'engineering',role:'primary'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
  'tool-chamber-matching':Object.freeze([
    {engine:'CoreChartEngine',element:'Horizontal Bar',view:'bar',role:'primary'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
  'golden-affected':Object.freeze([
    {engine:'CoreChartEngine',element:'Line Chart',view:'line',role:'primary'},
    {engine:'CoreChartEngine',element:'Box Plot',view:'box',role:'distribution'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
  'wafer-difference':Object.freeze([
    {engine:'WaferFabEngine',element:'Wafer Map',view:'wafer',role:'primary'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
  'pre-post-change':Object.freeze([
    {engine:'ComparisonEngine',element:'Before/After KPI',view:'comparison',role:'summary'},
    {engine:'CoreChartEngine',element:'Line Chart',view:'line',role:'primary'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
  'distribution-comparison':Object.freeze([
    {engine:'CoreChartEngine',element:'Box Plot',view:'box',role:'primary'},
    {engine:'CoreChartEngine',element:'Histogram',view:'histogram',role:'distribution'},
    {engine:'TableEngine',element:'Clean Table',view:'table',role:'evidence'},
  ]),
});

const ROLE_LABELS=Object.freeze({
  category:'Cause / category',value:'Contribution / measurement',time:'Ordered time',
  tool:'Tool',chamber:'Chamber',cohort:'Cohort / condition',x:'Process position',
  die_x:'Die X',die_y:'Die Y',reference_value:'Reference / golden value',
  affected_value:'Affected value',subgroup:'Subgroup',
});

export const ENGINEERING_RECIPES=Object.freeze([
  Object.freeze({id:'yield-pareto',version:RECIPE_VERSION,name:'Yield Pareto',reason:'Ranked contribution plus cumulative loss makes the largest yield drivers obvious.',visuals:['Pareto','Clean Table','Hero KPI'],roles:['category','value']}),
  Object.freeze({id:'spc-excursion',version:RECIPE_VERSION,name:'SPC Excursion Review',reason:'Ordered measurements can be reviewed with process behavior and excursion context.',visuals:['SPC Control Chart','Clean Table'],roles:['time','value']}),
  Object.freeze({id:'tool-chamber-matching',version:RECIPE_VERSION,name:'Tool / Chamber Matching',reason:'Tool, chamber, and metric fields support a governed comparison surface.',visuals:['Horizontal Bar','Clean Table'],roles:['tool','chamber','value']}),
  Object.freeze({id:'golden-affected',version:RECIPE_VERSION,name:'Golden vs Affected',reason:'Cohort and ordered measurements support a reference-versus-affected comparison.',visuals:['Line Chart','Box Plot','Clean Table'],roles:['cohort','x','value','reference_value','affected_value']}),
  Object.freeze({id:'wafer-difference',version:RECIPE_VERSION,name:'Wafer Difference Investigation',reason:'Die coordinates and reference/affected measurements support a spatial comparison.',visuals:['Wafer Map','Clean Table'],roles:['die_x','die_y','reference_value','affected_value']}),
  Object.freeze({id:'pre-post-change',version:RECIPE_VERSION,name:'Pre / Post Process Change',reason:'A period or cohort field can frame a measured process change without rebuilding the report.',visuals:['Before/After KPI','Line Chart','Clean Table'],roles:['cohort','value']}),
  Object.freeze({id:'distribution-comparison',version:RECIPE_VERSION,name:'Capability / Distribution Comparison',reason:'A numeric measurement is available for spread, outlier, and distribution review.',visuals:['Box Plot','Histogram','Clean Table'],roles:['value']}),
]);

function resolve(fields,role) {
  const tagged=fieldByTag(fields,role); if(tagged)return tagged;
  if(role==='category') { const category=fieldByTag(fields,'category'); if(category)return category; }
  if(role==='value') { const value=fieldByTag(fields,'value')||fieldByTag(fields,'weight'); if(value)return value; }
  if(role==='time') { const time=fieldByTag(fields,'time'); if(time)return time; }
  if(role==='cohort') { const cohort=fieldByTag(fields,'cohort')||fieldByTag(fields,'status'); if(cohort)return cohort; }
  if(role==='x') { const axis=fieldByTag(fields,'x')||fieldByTag(fields,'time')||fieldByTag(fields,'process'); if(axis)return axis; }
  const patterns={
    category:/(defect|cause|failure|alarm|category|reason|bin)/,
    value:/(yield|measure|value|count|loss|defect|rate|metric)/,
    time:/(timestamp|time|date|sequence|order|step)/,
    cohort:/(cohort|status|condition|population|group|golden|affected|control|reference)/,
    x:/(position|process|time|sequence|order|step)/,
    reference_value:/(reference|golden|baseline|control)/,
    affected_value:/(affected|actual|test|failed|exposed)/,
  };
  const named=patterns[role]?fieldByName(fields,patterns[role]):null;
  if(['value','reference_value','affected_value'].includes(role)) {
    if(named&&numericTypes.has(named.type))return named;
    return (fields||[]).find(field=>numericTypes.has(field.type))||null;
  }
  return named;
}

function inferMapping(fields) {
  const list=Array.isArray(fields)?fields:[],numeric=list.filter(field=>numericTypes.has(field.type));
  const mapping={};
  for(const role of ['category','value','time','tool','chamber','cohort','x','die_x','die_y','reference_value','affected_value','subgroup']) {
    const value=resolve(list,role); if(value)mapping[role]=fieldId(value);
  }
  if(!mapping.value&&numeric[0])mapping.value=numeric[0].id;
  if(!mapping.x)mapping.x=mapping.time||numeric[0]?.id;
  if(!mapping.y&&numeric[1])mapping.y=numeric[1].id;
  return mapping;
}

function mappingFor(recipe,fields,overrides={}) {
  const list=Array.isArray(fields)?fields:[],byId=new Set(list.map(field=>field.id));
  const inferred=inferMapping(list),mapping={...inferred};
  for(const role of recipe.roles||[]) if(Object.prototype.hasOwnProperty.call(overrides,role)) mapping[role]=overrides[role]||null;
  for(const role of Object.keys(mapping)) if(mapping[role]&&!byId.has(mapping[role])) mapping[role]=null;
  return mapping;
}

function roleStatus(recipe,fields,mapping) {
  const byId=new Map((fields||[]).map(field=>[field.id,field]));
  const unresolved=[],incompatible=[];
  for(const role of recipe.roles||[]) {
    const field=mapping[role]?byId.get(mapping[role]):null;
    if(!field){unresolved.push(role);continue;}
    if(['value','reference_value','affected_value'].includes(role)&&!numericTypes.has(field.type)) incompatible.push(role);
    if(role==='time'&&!['date','datetime','integer','number','string'].includes(field.type)) incompatible.push(role);
  }
  return {unresolved,incompatible,valid:!unresolved.length&&!incompatible.length};
}

function transformPlan(recipe,mapping) {
  if(recipe.id==='yield-pareto'&&mapping.value) return {steps:[
    {type:'sort',field:mapping.value,direction:'desc'},
    {type:'cumulative_percent',source_field:mapping.value,name:'Cumulative contribution %'},
  ],summary:'rank descending · cumulative percent'};
  return {steps:[],summary:'No transform required'};
}

function targetMapping(recipeId,target,mapping) {
  if(target.view==='table')return {};
  if(target.view==='bar')return {category:mapping.category||mapping.tool||mapping.chamber,value:mapping.value,series:mapping.chamber||mapping.tool};
  if(target.view==='line')return {x:mapping.x||mapping.time,y:mapping.value,series:mapping.cohort};
  if(target.view==='box'||target.view==='histogram')return {value:mapping.value||mapping.affected_value||mapping.reference_value,category:mapping.cohort};
  if(target.view==='wafer')return {die_x:mapping.die_x,die_y:mapping.die_y,value:mapping.affected_value||mapping.reference_value,reference_value:mapping.reference_value,affected_value:mapping.affected_value,wafer_id:mapping.wafer_id,lot_id:mapping.lot_id,tool:mapping.tool,chamber:mapping.chamber};
  if(target.view==='engineering')return {time:mapping.time||mapping.x,value:mapping.value,subgroup:mapping.subgroup,specification_low:mapping.specification_low,specification_high:mapping.specification_high};
  return {...mapping};
}

function instantiated(recipe,fields,overrides={}) {
  const mapping=mappingFor(recipe,fields,overrides),status=roleStatus(recipe,fields,mapping),targets=RECIPE_TARGETS[recipe.id]||[];
  const numeric=(fields||[]).filter(field=>numericTypes.has(field.type));
  const resolvedCount=(recipe.roles||[]).filter(role=>mapping[role]).length;
  return {...clone(recipe),mapping,missing:status.unresolved,incompatible:status.incompatible,ready:status.valid,compatible:resolvedCount>0||numeric.length>0,confidence:(recipe.roles||[]).length?resolvedCount/(recipe.roles||[]).length:0,semantic_tags:[...tagsOf(fields)],targets:clone(targets)};
}

export function instantiateRecipe(recipe,fields=[],overrides={}) {
  const source=typeof recipe==='string'?ENGINEERING_RECIPES.find(value=>value.id===recipe):recipe;
  if(!source)return {id:String(recipe||''),name:'Unknown analysis',ready:false,missing:['recipe'],incompatible:[],mapping:{},targets:[]};
  return instantiated(source,fields,overrides);
}

export function engineeringRecipeCandidates(fields=[]) {
  return ENGINEERING_RECIPES.map(recipe=>instantiateRecipe(recipe,fields)).filter(recipe=>recipe.compatible).sort((a,b)=>Number(b.ready)-Number(a.ready)||b.confidence-a.confidence||a.name.localeCompare(b.name));
}

export function recommendEngineeringRecipes(fields=[]) {
  const list=Array.isArray(fields)?fields:[],tags=tagsOf(list),numeric=list.filter(field=>numericTypes.has(field.type));
  return engineeringRecipeCandidates(list).filter(recipe=>{
    if(!recipe.ready)return false;
    if(recipe.id==='yield-pareto')return tags.has('weight')||/defect|cause|loss|scrap|failure|alarm/i.test(String(list.find(field=>field.id===recipe.mapping.value)?.name||''));
    if(recipe.id==='golden-affected')return Boolean(recipe.mapping.reference_value&&recipe.mapping.affected_value);
    if(recipe.id==='wafer-difference')return Boolean(recipe.mapping.reference_value&&recipe.mapping.affected_value&&recipe.mapping.die_x&&recipe.mapping.die_y);
    if(recipe.id==='pre-post-change')return Boolean(recipe.mapping.cohort);
    return numeric.length>0;
  }).sort((a,b)=>b.confidence-a.confidence||a.name.localeCompare(b.name));
}

export function recipeExecutionPlan(recipe,fields=[],overrides={}) {
  const instantiatedRecipe=instantiateRecipe(recipe,fields,overrides),targets=instantiatedRecipe.targets||[];
  const transform=transformPlan(instantiatedRecipe,instantiatedRecipe.mapping);
  const visuals=targets.map(target=>({...target,mapping:targetMapping(instantiatedRecipe.id,target,instantiatedRecipe.mapping),production:true}));
  return {
    valid:Boolean(instantiatedRecipe.ready&&visuals.length),
    status:instantiatedRecipe.ready?'ready':instantiatedRecipe.incompatible.length?'incompatible':'needs-mapping',
    recipe_id:instantiatedRecipe.id,
    recipe_version:instantiatedRecipe.version||RECIPE_VERSION,
    recipe:instantiatedRecipe,
    source_dataset:null,
    required_roles:clone(instantiatedRecipe.roles||[]),
    mappings:clone(instantiatedRecipe.mapping||{}),
    unresolved:clone(instantiatedRecipe.missing||[]),
    incompatible:clone(instantiatedRecipe.incompatible||[]),
    transform_plan:transform,
    visuals,
    message_roles:visuals.map((visual,index)=>({element:visual.element,role:visual.role|| (index===0?'Primary Evidence':'Supporting Evidence')})),
    provenance:{recipe_id:instantiatedRecipe.id,recipe_version:instantiatedRecipe.version||RECIPE_VERSION,mapping:clone(instantiatedRecipe.mapping||{}),transform_summary:transform.summary},
    error:instantiatedRecipe.incompatible.length?`Choose compatible fields for ${instantiatedRecipe.incompatible.join(', ')}.`:instantiatedRecipe.missing.length?`Map ${instantiatedRecipe.missing.join(', ')} before applying this analysis.`:null,
  };
}

// Backwards-compatible name used by the first analytics wave.
export function recipePlan(recipe,fields=[],overrides={}) { return recipeExecutionPlan(recipe,fields,overrides); }
export function recipeRoleLabel(role) { return ROLE_LABELS[role]||String(role||'').replaceAll('_',' '); }
