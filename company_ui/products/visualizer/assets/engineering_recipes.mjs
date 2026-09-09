// Deterministic semiconductor analysis recipes.  Recipes describe intent and
// compatible primitives; they never execute arbitrary code or invent data.

const clone=value=>typeof structuredClone==='function'?structuredClone(value):JSON.parse(JSON.stringify(value));
const numericTypes=new Set(['integer','number']);
const tagsOf=fields=>new Set((fields||[]).flatMap(field=>field.semantic_tags||[]));
const fieldByTag=(fields,tag)=>fields.find(field=>(field.semantic_tags||[]).includes(tag));
const fieldByName=(fields,pattern)=>fields.find(field=>pattern.test(String(field.name||'').toLowerCase()));
const fieldId=field=>field?.id||null;

export const ENGINEERING_RECIPES=Object.freeze([
  Object.freeze({id:'yield-pareto',name:'Yield Loss Investigation',reason:'Categorical loss or defect contribution can be prioritized by cumulative impact.',visuals:['Pareto','Clean Table','Hero KPI'],roles:['category','value']}),
  Object.freeze({id:'spc-excursion',name:'SPC Excursion Review',reason:'Ordered measurements can be reviewed with process behavior and excursion context.',visuals:['SPC Control Chart','Clean Table','Key Takeaway'],roles:['time','value']}),
  Object.freeze({id:'tool-chamber-matching',name:'Tool / Chamber Matching',reason:'Tool, chamber, and metric fields support a governed comparison surface.',visuals:['Horizontal Bar','Clean Table','Key Takeaway'],roles:['tool','chamber','value']}),
  Object.freeze({id:'golden-affected',name:'Golden vs Affected',reason:'Cohort and ordered measurement fields support a reference-versus-affected comparison.',visuals:['Line Chart','Clean Table','Executive Statement'],roles:['cohort','x','value']}),
  Object.freeze({id:'wafer-difference',name:'Wafer Difference Investigation',reason:'Die coordinates and reference/affected measurements support a spatial comparison.',visuals:['Wafer Map','Clean Table','Key Takeaway'],roles:['die_x','die_y','reference_value','affected_value']}),
  Object.freeze({id:'pre-post-change',name:'Pre / Post Process Change',reason:'A period or cohort field can frame a measured change without rebuilding the report.',visuals:['Before/After KPI','Line Chart','Clean Table'],roles:['cohort','value']}),
  Object.freeze({id:'distribution-comparison',name:'Capability / Distribution Comparison',reason:'A numeric measurement is available for spread, outlier, and distribution review.',visuals:['Box Plot','Histogram','Clean Table'],roles:['value']}),
]);

export function instantiateRecipe(recipe,fields=[]) {
  const list=Array.isArray(fields)?fields:[],tags=tagsOf(list),numeric=list.filter(field=>numericTypes.has(field.type));
  const category=fieldByTag(list,'category')||fieldByTag(list,'tool')||fieldByTag(list,'chamber');
  const value=fieldByTag(list,'value')||fieldByName(list,/(yield|measure|value|count|loss|defect|rate)/)||numeric[0];
  const x=fieldByTag(list,'time')||numeric[0];
  const cohort=fieldByTag(list,'lot_id')||fieldByTag(list,'wafer_id')||fieldByTag(list,'product')||fieldByTag(list,'tool')||category;
  const reference=fieldByName(list,/(reference|golden|baseline|control)/);
  const affected=fieldByName(list,/(affected|actual|test|failed)/);
  const resolved={category:fieldId(category),value:fieldId(value),x:fieldId(x),time:fieldId(fieldByTag(list,'time')),cohort:fieldId(cohort),die_x:fieldId(fieldByTag(list,'die_x')),die_y:fieldId(fieldByTag(list,'die_y')),reference_value:fieldId(reference),affected_value:fieldId(affected),tool:fieldId(fieldByTag(list,'tool')),chamber:fieldId(fieldByTag(list,'chamber'))};
  const ready=(recipe.roles||[]).every(role=>resolved[role]);
  return {...clone(recipe),ready,mapping:resolved,missing:(recipe.roles||[]).filter(role=>!resolved[role]),semantic_tags:[...tags]};
}

export function recommendEngineeringRecipes(fields=[]) {
  const list=Array.isArray(fields)?fields:[],tags=tagsOf(list),numeric=list.filter(field=>numericTypes.has(field.type));
  return ENGINEERING_RECIPES.map(recipe=>instantiateRecipe(recipe,list)).filter(recipe=>{
    if(recipe.id==='yield-pareto')return recipe.ready&&(tags.has('weight')||/defect|cause|loss|scrap|failure|alarm/i.test(String(list.find(field=>field.id===recipe.mapping.value)?.name||'')));
    if(recipe.id==='spc-excursion')return recipe.ready;
    if(recipe.id==='tool-chamber-matching')return recipe.ready;
    if(recipe.id==='golden-affected')return recipe.ready&&Boolean(recipe.mapping.reference_value&&recipe.mapping.affected_value);
    if(recipe.id==='wafer-difference')return recipe.ready&&Boolean(recipe.mapping.reference_value&&recipe.mapping.affected_value);
    if(recipe.id==='pre-post-change')return recipe.ready&&Boolean(recipe.mapping.cohort);
    return numeric.length>0&&recipe.ready;
  }).sort((a,b)=>Number(b.ready)-Number(a.ready)||a.name.localeCompare(b.name));
}

export function recipePlan(recipe,fields=[]) {
  const instantiated=instantiateRecipe(recipe,fields);
  if(!instantiated.ready)return {valid:false,recipe:instantiated,error:`Map ${instantiated.missing.join(', ')} to use this recipe.`};
  return {valid:true,recipe:instantiated,steps:[],visuals:instantiated.visuals.map(element=>({element,mapping:instantiated.mapping}))};
}
