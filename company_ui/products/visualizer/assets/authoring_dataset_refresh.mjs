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
export function planDatasetRefresh({dataset,intake,items,selectedId,selectedOnly=false,viewForEntry}) {
  const compatibility=refreshCompatibility(dataset.fields,intake.fields); if(!['exact','reordered'].includes(compatibility.kind))return {valid:false,compatibility,reason:compatibility.kind==='ambiguous'?'Duplicate normalized field names prevent refresh.':'Schema changed; review mapping.'};
  const consumers=(items||[]).filter(item=>item.dataset_id===dataset.id), targets=selectedOnly?consumers.filter(item=>item.id===selectedId):consumers;
  const mappings=[]; for(const entry of targets){const rebound=reboundMapping(entry.mapping||{},dataset.fields,intake.fields,viewForEntry(entry));if(!rebound.valid)return {valid:false,compatibility,reason:rebound.reason,entry};mappings.push({id:entry.id,mapping:rebound.mapping});}
  return {valid:true,compatibility,consumers,targets,mappings,schema_signature:mappingSchemaSignature(intake.fields)};
}
