import { contractFor } from './authoring_contracts.mjs';
import { normalizedFieldName, mappingSchemaSignature, hasUniqueNormalizedFields, mappingToFieldNames, mappingFromFieldNames } from './authoring_mapping_presets.mjs';

const names=fields=>(fields||[]).map(field=>normalizedFieldName(field.name));
export function refreshCompatibility(oldFields,newFields) {
  if(!hasUniqueNormalizedFields(oldFields)||!hasUniqueNormalizedFields(newFields))return {kind:'ambiguous',added:[],removed:[]};
  const oldNames=names(oldFields),nextNames=names(newFields),oldSet=new Set(oldNames),nextSet=new Set(nextNames);
  const added=nextNames.filter(name=>!oldSet.has(name)),removed=oldNames.filter(name=>!nextSet.has(name));
  if(added.length||removed.length)return {kind:'changed',added,removed};
  return {kind:oldNames.every((name,index)=>name===nextNames[index])?'exact':'reordered',added:[],removed:[]};
}
export function reboundMapping(mapping,oldFields,newFields,view) {
  const saved=mappingToFieldNames(mapping,oldFields), rebound=mappingFromFieldNames(saved,newFields);
  if(!rebound)return {valid:false,reason:'A mapped field is missing from the refreshed data.'};
  const validation=contractFor(view).validate(rebound,newFields);
  return validation.valid?{valid:true,mapping:rebound}:{valid:false,reason:validation.incompatible.length?`Incompatible field for ${validation.incompatible.join(', ')}.`:`Map ${validation.missing.join(', ')} first.`,validation};
}
const FIELD_KEYS=new Set(['field','source_field','value_field','column_field']);
const FIELD_LIST_KEYS=new Set(['keep_fields','index_fields']);
export function reboundTransformRecipe(recipe,oldFields,newFields) {
  if(!recipe)return {valid:true,recipe:null};
  const oldById=new Map((oldFields||[]).map(field=>[field.id,normalizedFieldName(field.name)]));
  const nextByName=new Map((newFields||[]).map(field=>[normalizedFieldName(field.name),field.id]));
  const rebind=id=>{
    if(!oldById.has(id))return id;
    const next=nextByName.get(oldById.get(id));
    if(!next)throw new Error('A transform field is missing from the refreshed data.');
    return next;
  };
  try {
    const copy=structuredClone(recipe);
    for(const step of copy.steps||[]) {
      for(const key of FIELD_KEYS)if(typeof step[key]==='string')step[key]=rebind(step[key]);
      for(const key of FIELD_LIST_KEYS)if(Array.isArray(step[key]))step[key]=step[key].map(rebind);
      for(const [key,value] of Object.entries(step)) {
        if(FIELD_KEYS.has(key)||FIELD_LIST_KEYS.has(key)||typeof value!=='string')continue;
        if(oldById.has(value))throw new Error(`Unsupported transform field reference: ${key}.`);
      }
    }
    return {valid:true,recipe:copy};
  } catch(error) { return {valid:false,reason:error.message||'The transform cannot be rebound safely.'}; }
}
export function planDatasetRefresh({dataset,intake,items,selectedId,selectedOnly=false,viewForEntry}) {
  const compatibility=refreshCompatibility(dataset.fields,intake.fields); if(!['exact','reordered'].includes(compatibility.kind))return {valid:false,compatibility,reason:compatibility.kind==='ambiguous'?'Duplicate normalized field names prevent refresh.':'Schema changed; review mapping.'};
  const consumers=(items||[]).filter(item=>item.dataset_id===dataset.id), targets=selectedOnly?consumers.filter(item=>item.id===selectedId):consumers;
  if(!targets.length)return {valid:false,compatibility,reason:'The selected visual is no longer linked to this dataset.'};
  if(!selectedOnly&&consumers.some(entry=>entry.locked))return {valid:false,compatibility,reason:'Unlock every linked visual before refreshing shared data.'};
  if(selectedOnly&&targets.some(entry=>entry.locked))return {valid:false,compatibility,reason:'Unlock the selected visual before refreshing its data.'};
  const mappings=[]; for(const entry of targets){const rebound=reboundMapping(entry.mapping||{},dataset.fields,intake.fields,viewForEntry(entry));if(!rebound.valid)return {valid:false,compatibility,reason:rebound.reason,entry};const transform=reboundTransformRecipe(entry.transform_recipe,dataset.fields,intake.fields);if(!transform.valid)return {valid:false,compatibility,reason:transform.reason,entry};mappings.push({id:entry.id,mapping:rebound.mapping,transform_recipe:transform.recipe});}
  return {valid:true,compatibility,consumers,targets,mappings,schema_signature:mappingSchemaSignature(intake.fields)};
}
