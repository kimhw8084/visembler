import { contractFor } from './authoring_contracts.mjs';
import { productionTargetForView } from './authoring_data.mjs';

export const MAPPING_PRESET_ROLES=Object.freeze(['category','value','x','y','series','time','source','target','weight','subgroup','specification_low','specification_high','lower_limit','upper_limit','die_x','die_y','wafer_id','lot_id','tool','chamber','recipe','process','product','bin','label','size','color','tooltip']);
export function normalizedFieldName(name) { return String(name??'').trim().toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,''); }
export function mappingSchemaSignature(fields) { return [...new Set((fields||[]).map(field=>normalizedFieldName(typeof field==='string'?field:field?.name)).filter(Boolean))].sort().join('|'); }
export function hasUniqueNormalizedFields(fields) { const names=(fields||[]).map(field=>normalizedFieldName(typeof field==='string'?field:field?.name)).filter(Boolean); return names.length===new Set(names).size&&names.length===(fields||[]).length; }
export function mappingToFieldNames(mapping, fields) {
  const byId=new Map((fields||[]).map(field=>[field.id,normalizedFieldName(field.name)])); const result={};
  for(const [role,id] of Object.entries(mapping||{})) { const name=byId.get(id); if(MAPPING_PRESET_ROLES.includes(role)&&name)result[role]=name; }
  return result;
}
export function mappingFromFieldNames(mapping, fields) {
  const byName=new Map((fields||[]).map(field=>[normalizedFieldName(field.name),field.id])); const result={};
  for(const [role,name] of Object.entries(mapping||{})) { const id=byName.get(normalizedFieldName(name)); if(!MAPPING_PRESET_ROLES.includes(role)||!id)return null; result[role]=id; }
  return result;
}
export function matchingMappingPresets(presets, intake) {
  const signature=mappingSchemaSignature(intake?.fields); if(!hasUniqueNormalizedFields(intake?.fields))return [];
  return (presets||[]).filter(preset=>preset?.schema?.signature===signature&&productionTargetForView(preset.view)).map(preset=>{
    const mapping=mappingFromFieldNames(preset.mapping,intake.fields); if(!mapping)return null;
    const validation=contractFor(preset.view).validate(mapping,intake.fields);
    return validation.valid?{preset,mapping}:null;
  }).filter(Boolean);
}
