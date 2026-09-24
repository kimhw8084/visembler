// Versioned reusable bindings. Dataset identities remain local to the report;
// reusable contracts carry field names and semantic requirements only.
import { contractFor } from './authoring_contracts.mjs';
import { normalizedFieldName } from './authoring_mapping_presets.mjs';
import { executeRecipeSemantics, recipeRoleContract } from './analysis_semantics.mjs';

export const REUSE_BINDING_VERSION = 1;

const clone = value => structuredClone(value);
const text = value => String(value ?? '').trim();
const slug = value => normalizedFieldName(value).replace(/_/g, '-') || 'data';
const stableHash = value => { let hash=2166136261; for(const char of String(value)){hash^=char.charCodeAt(0);hash=Math.imul(hash,16777619);} return (hash>>>0).toString(36); };
const hasContent = value => Array.isArray(value) ? value.some(hasContent) : value&&typeof value==='object' ? Object.values(value).some(hasContent) : value!==undefined&&value!==null&&value!=='';
const fieldsOf = dataset => Array.isArray(dataset?.fields)?dataset.fields:[];
const viewsFor = item => item?.view_type || (item?.engine==='TableEngine'?'table':item?.engine==='TimelineEngine'?'timeline':item?.engine==='DiagramEngine'?'diagram':item?.engine==='EngineeringChartEngine'?'engineering':item?.engine==='WaferFabEngine'?'wafer':item?.engine==='CoreChartEngine'?String(item.element||'').toLowerCase().includes('scatter')?'scatter':String(item.element||'').toLowerCase().includes('line')?'line':'bar':'table');

function schemaFields(fields=[]) {
  return fields.map(field=>({name:text(field?.name),type:text(field?.type||'string'),semantic_tags:[...(field?.semantic_tags||[])].map(text).filter(Boolean).sort()}));
}
function schemaSignature(fields) {
  return schemaFields(fields).map(field=>`${normalizedFieldName(field.name)}:${field.type}:${field.semantic_tags.join(',')}`).sort().join('|');
}
function compatibleField(role, source, target) {
  const sourceType=text(source?.field_type||source?.type),targetType=text(target?.type),sourceTags=source?.semantic_tags||[],targetTags=target?.semantic_tags||[];
  if(!target)return false;
  if(sourceTags.length&&targetTags.length&&!sourceTags.some(tag=>targetTags.includes(tag)))return false;
  if(['value','y','size','weight','die_x','die_y','reference_value','affected_value','specification_low','specification_high','lower_limit','upper_limit'].includes(role))return ['integer','number'].includes(targetType);
  if(role==='time')return ['date','datetime'].includes(targetType);
  if(sourceType==='identifier')return ['identifier','string','categorical'].includes(targetType);
  if(['string','categorical','identifier'].includes(sourceType))return ['string','categorical','identifier'].includes(targetType);
  return !sourceType||sourceType===targetType||(sourceType==='integer'&&targetType==='number')||(sourceType==='number'&&targetType==='integer');
}

function itemBinding(item,dataset) {
  const view=viewsFor(item),dataContract=contractFor(view),fieldById=new Map(fieldsOf(dataset).map(field=>[String(field.id),field]));
  const roles=Object.entries(item.mapping||{}).map(([role,id])=>{
    const source=fieldById.get(String(id));
    return {role,field_name:text(source?.name),field_type:text(source?.type),semantic_tags:[...(source?.semantic_tags||[])].map(text).filter(Boolean).sort(),required:dataContract.required_roles.includes(role)};
  });
  const recipe=item.analysis_recipe||{};
  const safeTransform=stripSourceIdentity(clone(item.transform_recipe||{}));
  const safeAnalysis=stripSourceIdentity(clone(recipe));
  const safeStatistical=stripSourceIdentity(clone(item.statistical_recipe||{}));
  const safeEngineering=stripSourceIdentity(clone(item.engineering_recipe||{}));
  const safePipeline=stripSourceIdentity(clone(item.transform_pipeline||item.transforms||recipe.transform_pipeline||[]));
  const safeChart=item.chart_studio?stripSourceIdentity(clone(item.chart_studio)):null;
  if(safeChart){delete safeChart.dataset;delete safeChart.dataset_id;delete safeChart.mapping;}
  const referenceTargets={transform_recipe:safeTransform,transform_pipeline:safePipeline,analysis_recipe:safeAnalysis,statistical_recipe:safeStatistical,engineering_recipe:safeEngineering,...(safeChart?{chart_studio:safeChart}:{})},references=[];
  const visit=(value,path=[])=>{
    if(typeof value==='string'&&fieldById.has(value)){const field=fieldById.get(value);references.push({role:`$reference:${JSON.stringify(path)}`,path,field_name:text(field.name),field_type:text(field.type),semantic_tags:[...(field.semantic_tags||[])].map(text).filter(Boolean).sort(),required:true});return;}
    if(Array.isArray(value)){value.forEach((child,index)=>visit(child,[...path,index]));return;}
    if(value&&typeof value==='object')for(const [key,child] of Object.entries(value))visit(child,[...path,key]);
  };
  visit(referenceTargets);
  const fieldNames=new Map(fieldsOf(dataset).map(field=>[String(field.id),text(field.name)]));
  const namesOnly=value=>{if(typeof value==='string')return fieldNames.get(value)||value;if(Array.isArray(value))return value.map(namesOnly);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,child])=>[key,namesOnly(child)]));return value;};
  return {
    item_id:String(item.id),element:text(item.element||item.title||item.engine),view,
    required_roles:[...dataContract.required_roles],field_roles:roles,references,
    transform_recipe:namesOnly(safeTransform),transform_pipeline:namesOnly(safePipeline),analysis_recipe:namesOnly(safeAnalysis),statistical_recipe:namesOnly(safeStatistical),engineering_recipe:namesOnly(safeEngineering),chart_studio:safeChart?namesOnly(safeChart):null,
    transforms:namesOnly(safePipeline),
    analysis_recipe_identity:{id:text(recipe.id),version:recipe.version??null,role:text(recipe.role),semantic_contract:text(recipe.semantic_contract)},
    statistical_recipe_identity:{id:text(item.statistical_recipe?.id||item.statistical_recipe_id||''),version:item.statistical_recipe?.version??null},
    engineering_recipe_identity:{id:text(item.engineering_recipe?.id||item.engineering_recipe_id||''),version:item.engineering_recipe?.version??null},
  };
}

export function buildReusableBindingContract(model={}) {
  const datasets=new Map((model.datasets||[]).filter(dataset=>dataset?.id).map(dataset=>[String(dataset.id),dataset]));
  const bySourceId=new Map();
  for(const item of model.items||[])if(item?.dataset_id){const key=String(item.dataset_id);if(!bySourceId.has(key))bySourceId.set(key,[]);bySourceId.get(key).push(item);}
  const slots=[...bySourceId.entries()].map(([sourceId,items])=>{
    const dataset=datasets.get(sourceId)||{name:items[0]?.dataset_name||'Data source unavailable',fields:[]},fields=schemaFields(fieldsOf(dataset)),signature=schemaSignature(fieldsOf(dataset));
    const bindings=items.map(item=>itemBinding(item,dataset));
    const logicalName=text(dataset.name||items[0]?.dataset_name||'Data source');
    return {identity:`slot-${slug(logicalName)}-${stableHash(signature)}`,name:logicalName,source_schema_signature:signature,source_fields:fields,required_roles:[...new Set(bindings.flatMap(binding=>binding.required_roles))].sort(),bindings};
  }).sort((a,b)=>a.name.localeCompare(b.name)||a.source_schema_signature.localeCompare(b.source_schema_signature)||String(a.bindings[0]?.item_id||'').localeCompare(String(b.bindings[0]?.item_id||'')));
  slots.forEach((slot,index)=>{slot.identity=`${slot.identity}-${index+1}`;});
  const manual_value_items=(model.items||[]).filter(item=>!item?.dataset_id&&(
    item.engine==='MetricEngine'||item.engine==='ComparisonEngine'||
    item.engine==='TableEngine'&&(item.customTable?.rows||[]).some(row=>Array.isArray(row)&&row.some(value=>value!==null&&value!==undefined&&String(value).trim()!==''))
  )).map(item=>({
    item_id:text(item.id),
    element:text(item.title||item.element||'Report element'),
    kind:item.engine==='MetricEngine'?'key_metric':item.engine==='ComparisonEngine'?'comparison':'evidence_table',
  })).filter(item=>item.item_id).slice(0,500);
  return {version:REUSE_BINDING_VERSION,kind:'analytical-bindings',slots,manual_value_items};
}

function stripSourceIdentity(value) {
  if(Array.isArray(value))return value.map(stripSourceIdentity);
  if(!value||typeof value!=='object')return value;
  const result={};
  for(const [key,child] of Object.entries(value))if(!['dataset_id','source_dataset_id','datasetId','sourceDatasetId'].includes(key))result[key]=stripSourceIdentity(child);
  return result;
}

function setPath(target,path,value){let current=target;for(let index=0;index<path.length-1;index++){const key=path[index];if(current==null)return;current=current[key];}if(current!=null&&path.length)current[path.at(-1)]=value;}

export function reusableStructure(content={},contract=buildReusableBindingContract(content)) {
  const next=clone(content||{}),slotByDataset=new Map();
  (contract.slots||[]).forEach(slot=>slot.bindings.forEach(binding=>slotByDataset.set(String(binding.item_id),slot.identity)));
  next.items=(next.items||[]).map(item=>{
    const copy=stripSourceIdentity(item);
    const hasSlot=slotByDataset.has(String(item.id));
    if(hasSlot){
      delete copy.dataset_id;delete copy.mapping;
      // These are cached projections of the source rows, not reusable meaning.
      for(const key of ['data','rows','observations','result','resolved_rows','row_data','statistical_result','analysis_result','analysis_id'])delete copy[key];
    }
    // Static analytical values and table rows are cleared in structure mode as
    // well. They have no reusable field mapping, so keeping them would present
    // source-report facts beside a newly selected data source.
    if(item.engine==='MetricEngine'){
      for(const key of ['value','actual','current','target','delta','variance','metric_share','series'])delete copy[key];
      if(Array.isArray(copy.metrics))copy.metrics=copy.metrics.map(metric=>{
        if(Array.isArray(metric))return [metric[0]??'',null];
        if(!metric||typeof metric!=='object')return metric;
        const clean={...metric};
        for(const key of ['value','actual','current','target','delta','variance','share','series','data'])delete clean[key];
        return clean;
      });
    }
    if(item.engine==='ComparisonEngine')for(const key of ['before','after','current','value','delta','variance'])delete copy[key];
    if(item.engine==='TableEngine'&&Array.isArray(copy.rows))copy.rows=[];
    if(item.customTable&&typeof item.customTable==='object')copy.customTable={...clone(item.customTable),rows:[]};
    if(hasSlot&&item.engine==='WaferFabEngine')for(const key of ['tool','chamber','lot','wafer','wafer_id','lot_id','recipe','process','product','route','bin'])delete copy[key];
    if(!hasSlot)return copy;
    const binding=(contract.slots||[]).flatMap(slot=>slot.bindings||[]).find(value=>String(value.item_id)===String(item.id));
    if(binding){for(const [key,value] of [['transform_recipe',binding.transform_recipe],['transform_pipeline',binding.transform_pipeline||binding.transforms],['analysis_recipe',binding.analysis_recipe],['statistical_recipe',binding.statistical_recipe],['engineering_recipe',binding.engineering_recipe]]){if(hasContent(value))copy[key]=clone(value);else delete copy[key];}delete copy.transforms;if(binding.chart_studio){copy.chart_studio=clone(binding.chart_studio);delete copy.chart_studio.dataset_id;delete copy.chart_studio.dataset;copy.chart_studio.wafer={...(copy.chart_studio.wafer||{}),filters:{}};} }
    copy.reuse_slot=slotByDataset.get(String(item.id));
    return copy;
  });
  next.datasets=[];
  return next;
}

export function normalizedBindingContract(raw) {
  if(!raw||typeof raw!=='object'||Number(raw.version)!==REUSE_BINDING_VERSION||raw.kind!=='analytical-bindings'||!Array.isArray(raw.slots)||raw.slots.length>100) return null;
  const slots=[];
  for(const slot of raw.slots){
    if(!slot||typeof slot!=='object'||!Array.isArray(slot.source_fields)||!Array.isArray(slot.bindings)||slot.source_fields.length>500||slot.bindings.length>500) return null;
    const source_fields=slot.source_fields.map(field=>({name:text(field?.name).slice(0,160),type:text(field?.type||'string').slice(0,32),semantic_tags:Array.isArray(field?.semantic_tags)?field.semantic_tags.map(text).filter(Boolean).slice(0,32):[]}));
    const normalizeField=field=>({role:text(field?.role).slice(0,240),field_name:text(field?.field_name).slice(0,160),field_type:text(field?.field_type).slice(0,32),semantic_tags:Array.isArray(field?.semantic_tags)?field.semantic_tags.map(text).filter(Boolean).slice(0,32):[],required:field?.required===true,...(Array.isArray(field?.path)?{path:field.path}: {})});
    const bindings=slot.bindings.map(binding=>({item_id:text(binding?.item_id).slice(0,160),element:text(binding?.element).slice(0,160),view:text(binding?.view).slice(0,64),required_roles:Array.isArray(binding?.required_roles)?binding.required_roles.map(text).filter(Boolean).slice(0,64):[],field_roles:Array.isArray(binding?.field_roles)?binding.field_roles.map(normalizeField):[],references:Array.isArray(binding?.references)?binding.references.map(field=>({...normalizeField(field),path:Array.isArray(field?.path)?field.path:[]})):[],transform_recipe:clone(binding?.transform_recipe||{}),transform_pipeline:clone(binding?.transform_pipeline||binding?.transforms||[]),analysis_recipe:clone(binding?.analysis_recipe||{}),statistical_recipe:clone(binding?.statistical_recipe||{}),engineering_recipe:clone(binding?.engineering_recipe||{}),chart_studio:binding?.chart_studio?clone(binding.chart_studio):null,transforms:clone(binding?.transforms||[]),analysis_recipe_identity:clone(binding?.analysis_recipe_identity||{}),statistical_recipe_identity:clone(binding?.statistical_recipe_identity||{}),engineering_recipe_identity:clone(binding?.engineering_recipe_identity||{})}));
    slots.push({identity:text(slot.identity).slice(0,180),name:text(slot.name||'Data source').slice(0,120),source_schema_signature:text(slot.source_schema_signature).slice(0,12000),source_fields,required_roles:Array.isArray(slot.required_roles)?slot.required_roles.map(text).filter(Boolean).slice(0,64):[],bindings});
  }
  const manual_value_items=(Array.isArray(raw.manual_value_items)?raw.manual_value_items:[]).slice(0,500).map(item=>({item_id:text(item?.item_id).slice(0,160),element:text(item?.element||'Report element').slice(0,160),kind:['key_metric','comparison','evidence_table'].includes(item?.kind)?item.kind:'key_metric'})).filter(item=>item.item_id);
  const normalized={version:REUSE_BINDING_VERSION,kind:'analytical-bindings',slots,manual_value_items};
  const hasDatasetIdentity=value=>Array.isArray(value)?value.some(hasDatasetIdentity):!!value&&typeof value==='object'?Object.entries(value).some(([key,child])=>['dataset_id','source_dataset_id','datasetId','sourceDatasetId'].includes(key)||hasDatasetIdentity(child)):false;
  if(hasDatasetIdentity(normalized)||new Blob([JSON.stringify(normalized)]).size>1_500_000)return null;
  return normalized;
}

function fieldMatches(roleBinding,target) {
  const expected=roleBinding.field_name,normalized=normalizedFieldName(expected);
  return normalizedFieldName(target?.name)===normalized&&compatibleField(roleBinding.role,roleBinding,target);
}

export function suggestSlotMapping(binding,dataset,overrides={}) {
  const mapping={},unresolved=[],problems=[];
  for(const item of binding?.bindings||[]){
    const itemMap={};
    const knownRoles=new Set((item.field_roles||[]).map(value=>value.role));
    const roles=[...(item.field_roles||[]),...(item.references||[]),...(item.required_roles||[]).filter(role=>!knownRoles.has(role)).map(role=>({role,field_name:'',field_type:'',semantic_tags:[],required:true}))];
    for(const role of roles){
      const sameName=fieldsOf(dataset).filter(field=>normalizedFieldName(field.name)===normalizedFieldName(role.field_name));
      const candidates=sameName.filter(field=>fieldMatches(role,field));
      const hasOverride=Object.hasOwn(overrides?.[item.item_id]||{},role.role),selected=String(overrides?.[item.item_id]?.[role.role]||'');
      const explicit=selected?fieldsOf(dataset).find(field=>String(field.id)===selected):null;
      if(explicit){if(compatibleField(role.role,role,explicit))itemMap[role.role]=selected;else problems.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:'incompatible type'});}
      else if(selected)problems.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:'selected field is unavailable'});
      else if(hasOverride)unresolved.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:'Choose a compatible field',required:role.required});
      else if(candidates.length===1)itemMap[role.role]=String(candidates[0].id);
      else if(candidates.length>1)unresolved.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:'ambiguous',required:role.required});
      else if(sameName.length)problems.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:'incompatible type'});
      else unresolved.push({item_id:item.item_id,element:item.element,role:role.role,source_field:role.field_name,reason:role.required?'required field not found':'field not found',required:role.required});
    }
    const checked=contractFor(item.view).validate(itemMap,fieldsOf(dataset));
    checked.missing.forEach(role=>{if(!unresolved.some(value=>value.item_id===item.item_id&&value.role===role))unresolved.push({item_id:item.item_id,element:item.element,role,source_field:'',reason:'required role is unmapped'});});
    checked.incompatible.forEach(role=>{if(!problems.some(value=>value.item_id===item.item_id&&value.role===role))problems.push({item_id:item.item_id,element:item.element,role,source_field:'',reason:'field type is incompatible'});});
    const recipe=item.analysis_recipe||{},recipeId=text(recipe.id),recipeContract=recipeRoleContract(recipeId);
    if(recipeId&&recipeContract.required_roles.length){
      const recipeMapping=clone(recipe.mapping||recipe.mappings||{});
      for(const role of recipeContract.required_roles)if(!recipeMapping[role]&&itemMap[role])recipeMapping[role]=itemMap[role];
      for(const reference of item.references||[]){
        const [root,key,role]=reference.path||[],fieldId=itemMap[reference.role];
        if(root==='analysis_recipe'&&(key==='mapping'||key==='mappings')&&role&&fieldId)recipeMapping[role]=fieldId;
      }
      const result=executeRecipeSemantics(recipeId,dataset,recipeMapping,recipe.options||{});
      if(!result.ok||!result.rows?.length){
        const detail=result.errors?.[0]?.message||'This source has no usable rows for the saved analysis.';
        const label=recipeId.split(/[-_]+/).filter(Boolean).map(word=>word[0]?.toUpperCase()+word.slice(1)).join(' ');
        problems.push({item_id:item.item_id,element:item.element,role:'analysis',reason:'analysis requirements are not met',message:`${label} cannot use this data: ${detail}`});
      }
    }
    mapping[item.item_id]=itemMap;
  }
  return {mapping,unresolved,problems,ready:unresolved.length===0&&problems.length===0};
}

export function planReusableRemap(contract,datasets,selections={}) {
  const normalized=normalizedBindingContract(contract);
  if(!normalized)return {ok:false,slots:[],errors:[{reason:'The saved reusable data bindings are not supported.'}]};
  const slots=normalized.slots.map(slot=>{
    const selection=selections[slot.identity]||{},chosenId=String(selection.dataset_id||'');
    const chosen=chosenId?(datasets||[]).find(dataset=>String(dataset.id)===chosenId):null;
    const candidates=(datasets||[]).map(dataset=>({dataset,result:suggestSlotMapping(slot,dataset)})).filter(row=>row.result.problems.every(problem=>problem.reason==='analysis requirements are not met'));
    const destination=chosen|| (candidates.length===1?candidates[0].dataset:null);
    const userMappings=selection.mappings||{};
    const suggestion=destination?suggestSlotMapping(slot,destination,userMappings):null;
    const ambiguousDataset=!chosen&&candidates.length>1;
    const datasetMissing=!destination;
    return {identity:slot.identity,name:slot.name,dataset_id:destination?.id||'',dataset_name:destination?.name||'',bindings:slot.bindings,mapping:suggestion?.mapping||{},unresolved:suggestion?.unresolved||[],problems:suggestion?.problems||[],ambiguous_dataset:ambiguousDataset,dataset_missing:datasetMissing,ready:!!destination&&!!suggestion?.ready};
  });
  const errors=slots.flatMap(slot=>slot.problems.map(problem=>({slot:slot.name,...problem,reason:problem.message||problem.reason}))).concat(slots.filter(slot=>!slot.ready&&!slot.problems.length).map(slot=>({slot:slot.name,reason:slot.ambiguous_dataset?'Choose a data source because more than one match is available.':'Choose a compatible data source and complete its required fields.'})));
  return {ok:slots.every(slot=>slot.ready),slots,errors};
}

export function applyReusableRemap(content,plan,datasets=[]) {
  if(!plan?.ok)return null;
  const next=clone(content||{}),byItem=new Map(),datasetById=new Map((datasets||[]).map(dataset=>[String(dataset.id),dataset]));
  for(const slot of plan.slots)for(const binding of slot.bindings)byItem.set(String(binding.item_id),{slot,binding});
  next.items=(next.items||[]).map(item=>{
    const found=byItem.get(String(item.id));if(!found)return item;
    const {slot,binding}=found,selected=slot.mapping[String(item.id)]||{},mapping=Object.fromEntries(Object.entries(selected).filter(([role])=>!role.startsWith('$reference:')));
    const copy={...item,dataset_id:slot.dataset_id,mapping};
    for(const [key,value] of [['transform_recipe',binding.transform_recipe],['transform_pipeline',binding.transform_pipeline||binding.transforms],['analysis_recipe',binding.analysis_recipe],['statistical_recipe',binding.statistical_recipe],['engineering_recipe',binding.engineering_recipe]]){if(!hasContent(value)){delete copy[key];continue;}copy[key]=clone(value);if(copy[key]&&typeof copy[key]==='object'&&!Array.isArray(copy[key])&&key.endsWith('_recipe'))copy[key].source_dataset_id=slot.dataset_id;}
    if(binding.chart_studio){copy.chart_studio=clone(binding.chart_studio);copy.chart_studio.dataset_id=slot.dataset_id;copy.chart_studio.mapping=clone(mapping);const dataset=datasetById.get(String(slot.dataset_id));if(dataset)copy.chart_studio.dataset=clone(dataset);}
    for(const reference of binding.references||[]){const key=`$reference:${JSON.stringify(reference.path)}`,fieldId=selected[key];if(fieldId)setPath(copy,reference.path,String(fieldId));}
    delete copy.reuse_slot;
    return copy;
  });
  const selectedDatasets=[...new Set((plan.slots||[]).map(slot=>String(slot.dataset_id||'')).filter(Boolean))].map(id=>datasetById.get(id)).filter(Boolean).map(dataset=>clone(dataset));
  next.datasets=selectedDatasets;
  return next;
}
