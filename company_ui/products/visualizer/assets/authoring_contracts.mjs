const numeric=new Set(['integer','number']);
const temporal=new Set(['date','datetime']);
const numericRoles=new Set(['value','y','size','weight','die_x','die_y']);
const contract=(id,required_roles,optional_roles,compatible_views,roleTypes={})=>Object.freeze({id,required_roles,optional_roles,compatible_views,validate(mapping,fields){const byId=new Map(fields.map(field=>[field.id,field]));const missing=required_roles.filter(role=>!mapping?.[role]);const incompatible=Object.entries(mapping||{}).filter(([role,id])=>{const field=byId.get(id),allowed=roleTypes[role];return !field||(allowed?!allowed.has(field.type):numericRoles.has(role)&&!numeric.has(field.type));}).map(([role])=>role);return {valid:!missing.length&&!incompatible.length,missing,incompatible};}});

export const DATA_CONTRACTS=Object.freeze({
  bar:contract('bar',['category','value'],['series','color','tooltip'],['line','scatter','table']),
  line:contract('line',['x','y'],['series','color','tooltip'],['bar','scatter','table'],{x:new Set([...numeric,...temporal])}),
  scatter:contract('scatter',['x','y'],['size','color','label','tooltip'],['bar','line','table']),
  table:contract('table',[],['category','value','x','y','series'],['bar','line','scatter','matrix_heatmap']),
  matrix_heatmap:contract('matrix_heatmap',[],['category','series','value'],['table']),
  timeline:contract('timeline',['category'],['time','series','tooltip'],['table','diagram_flow'],{time:temporal}),
  diagram_flow:contract('diagram_flow',['source','target'],['weight','label'],['table','timeline']),
  engineering:contract('engineering',['value'],['time','subgroup','category','series','specification_low','specification_high','lower_limit','upper_limit'],['line','table']),
  wafer:contract('wafer',['die_x','die_y','value'],['wafer_id','lot_id','tool','chamber','recipe','process','product','bin'],['table','engineering']),
});
export const LEGACY_VIEW_ALIASES=Object.freeze({chart:'line',matrix:'matrix_heatmap',diagram:'diagram_flow',wafer_fab:'wafer',engineering_chart:'engineering'});
export function contractFor(view){return DATA_CONTRACTS[LEGACY_VIEW_ALIASES[view]||view]||DATA_CONTRACTS.table;}
