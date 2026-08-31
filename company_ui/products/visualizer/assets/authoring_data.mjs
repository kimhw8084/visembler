// Deterministic, dependency-free data intake for the report authoring loop.
import { contractFor } from './authoring_contracts.mjs';
import { PERFORMANCE_LIMITS, sampledRows } from './authoring_performance.mjs';
const SEMANTIC_ALIASES = Object.freeze({
  lot_id:['lot','lot_id','lotid'], wafer_id:['wafer','wafer_id','waferid','slot'], tool:['tool','tool_id','eqp','equipment','equipment_id'], chamber:['chamber','chamber_id','module'], recipe:['recipe','recipe_id'], process:['step','operation','op','process','process_step'], product:['product','product_id','device'], die_x:['die_x','x','x_coord','wafer_x'], die_y:['die_y','y','y_coord','wafer_y'], bin:['bin','bin_code','die_bin'], value:['value','measure','measurement','result','yield','yield_pct','yield_percent'], specification_low:['lsl','spec_low','lower_spec','specification_low'], specification_high:['usl','spec_high','upper_spec','specification_high'], time:['timestamp','time','datetime','date_time','event_time','date'], source:['source','from'], target:['target','to'], weight:['weight','count','volume'], subgroup:['subgroup','group']
});
const numeric = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i;
const dateOnly = /^\d{4}-\d{2}-\d{2}$/;
const idLike = /^0\d+$/;
const slug = value => String(value ?? '').trim().toLowerCase().replace(/[\s\-/.]+/g, '_');
const fieldId = (name, index) => `${slug(name).replace(/[^a-z0-9_]/g, '') || 'field'}_${index + 1}`;

export function parseGridText(text, { limit = 100001 } = {}) {
  const source=String(text ?? '').replace(/^\uFEFF/, '').replace(/\r\n?/g,'\n');
  if (!source.trim()) return { rows:[], delimiter:null, warnings:[] };
  const first=source.split('\n').find(line=>line.trim()) || '';
  const counts=[['\t',(first.match(/\t/g)||[]).length],[',',(first.match(/,/g)||[]).length],[';',(first.match(/;/g)||[]).length]];
  const delimiter=counts.sort((a,b)=>b[1]-a[1])[0][1] ? counts[0][0] : '\t';
  const rows=[]; let row=[], cell='', quoted=false;
  for(let i=0;i<source.length;i+=1) {
    const ch=source[i];
    if(ch==='"') { if(quoted && source[i+1]==='"') { cell+='"'; i+=1; } else quoted=!quoted; continue; }
    if(ch===delimiter && !quoted) { row.push(cell); cell=''; continue; }
    if(ch==='\n' && !quoted) { row.push(cell); rows.push(row); if(rows.length>=limit) return {rows,delimiter,warnings:[{code:'row_limit',message:`Only the first ${limit.toLocaleString()} rows were profiled.`}]}; row=[]; cell=''; continue; }
    cell+=ch;
  }
  row.push(cell); rows.push(row);
  if(rows.at(-1)?.every(value=>value==='')) rows.pop();
  return { rows, delimiter, warnings: quoted ? [{code:'unclosed_quote',message:'Input ended inside a quoted value; the final value was retained.'}] : [] };
}

function typed(value, type='unknown') {
  const raw=String(value ?? '').trim();
  if(raw==='') return null;
  if(type==='boolean' && /^(true|false)$/i.test(raw)) return /^true$/i.test(raw);
  const percentage=/^[-+]?(?:\d+\.?\d*|\.\d+)%$/.test(raw);
  const currency=/^[\$€£¥]\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i.test(raw);
  const normalized=raw.replace(/[,$€£¥%\s]/g,'');
  if(['integer','number'].includes(type) && !idLike.test(raw) && numeric.test(normalized)) return percentage ? Number(normalized)/100 : Number(normalized);
  return raw;
}
function profile(name, values, index) {
  const present=values.filter(value=>String(value ?? '').trim()!==''); const raw=present.map(value=>String(value).trim());
  const tags=Object.entries(SEMANTIC_ALIASES).filter(([, aliases])=>aliases.includes(slug(name))).map(([tag])=>tag);
  const all=(predicate)=>raw.length>0 && raw.every(predicate);
  let type='string';
  if(all(value=>/^(true|false)$/i.test(value))) type='boolean';
  else if(all(value=>dateOnly.test(value))) type='date';
  else if(all(value=>!Number.isNaN(Date.parse(value)) && /[-:T/ ]/.test(value))) type='datetime';
  else if(all(value=>numeric.test(value.replace(/[,$€£¥%\s]/g,'')))) type=raw.every(value=>Number.isInteger(Number(value.replace(/[,$€£¥%\s]/g,'')))) ? 'integer' : 'number';
  if(raw.some(value=>idLike.test(value)) || /(^|_)(id|code|lot|wafer|bin)(_|$)/.test(slug(name))) type='identifier';
  else if(type==='string' && new Set(raw).size <= Math.min(20, Math.max(3, raw.length/2))) type='categorical';
  return {id:fieldId(name,index),name:String(name),type,nullable:present.length!==values.length,semantic_tags:tags,profile:{missing:values.length-present.length,distinct:new Set(raw).size}};
}
function headerConfidence(rows) {
  if(rows.length<2) return {present:false,confidence:0,source_row:null};
  const first=rows[0], rest=rows.slice(1,Math.min(rows.length,12)); let score=0;
  first.forEach((value,index)=>{ const label=String(value??'').trim(); const below=rest.map(row=>row[index]??''); if(label && !numeric.test(label) && !dateOnly.test(label)) score+=1; if(below.some(value=>numeric.test(String(value??'').trim().replace(/[,$€£¥%\s]/g,'')))) score+=1; });
  const confidence=Math.min(1,score/Math.max(1,first.length*2)); return {present:confidence>=.65,confidence,source_row:confidence>=.65?0:null};
}
export function intakeText(text) {
  const parsed=parseGridText(text); if(!parsed.rows.length)return {rows:[],fields:[],header:{present:false,confidence:0,source_row:null},warnings:parsed.warnings,candidate_mappings:[],recommendations:[]};
  const header=headerConfidence(parsed.rows), width=Math.max(...parsed.rows.map(row=>row.length));
  const names=header.present ? Array.from({length:width},(_,i)=>String(parsed.rows[0][i]||`Column ${i+1}`).trim()||`Column ${i+1}`) : Array.from({length:width},(_,i)=>`Column ${i+1}`);
  const rawRows=(header.present?parsed.rows.slice(1):parsed.rows).map(row=>Array.from({length:width},(_,i)=>row[i]??''));
  const profileRows=sampledRows(rawRows,PERFORMANCE_LIMITS.profileRows),fields=names.map((name,index)=>profile(name,profileRows.map(row=>row[index]),index));
  const warnings=[...parsed.warnings]; if(rawRows.length>profileRows.length)warnings.push({code:'profile_sampled',message:`Types were profiled from a deterministic ${profileRows.length.toLocaleString()}-row sample; all ${rawRows.length.toLocaleString()} rows were retained.`}); fields.forEach((field,index)=>{const rawValues=profileRows.map(row=>String(row[index]??'').trim()),values=rawValues.filter(Boolean),dateLike=values.filter(value=>!Number.isNaN(Date.parse(value))&&/[-:T/ ]/.test(value)),numericLike=values.filter(value=>numeric.test(value.replace(/[,$€£¥%\s]/g,'')));if((['date','datetime'].includes(field.type)||field.semantic_tags?.includes('time'))&&dateLike.length<values.length)rawValues.forEach((value,rowIndex)=>{if(value&&!dateLike.includes(value))warnings.push({code:'invalid_date',row:rowIndex+(header.present?2:1),field:field.id,message:`${field.name} contains an invalid date; the original text was retained.`});});if(numericLike.length&&numericLike.length<values.length)warnings.push({code:'mixed_type',field:field.id,message:`${field.name} contains mixed numeric and text values; values were retained as text.`});});
  const rows=rawRows.map(row=>row.map((value,index)=>typed(value,fields[index]?.type))); const candidate_mappings=inferMappings(fields); const recommendations=recommendViews(fields,candidate_mappings);
  return {rows,fields,header,warnings,delimiter:parsed.delimiter,candidate_mappings,recommendations};
}
export function inferMappings(fields) {
  const byTag=tag=>fields.find(field=>field.semantic_tags?.includes(tag)); const numericFields=fields.filter(field=>['integer','number'].includes(field.type)); const category=fields.find(field=>['categorical','identifier','string'].includes(field.type));
  const mapping={}; const set=(role,field)=>{if(field)mapping[role]=field.id;};
  set('source',byTag('source')); set('target',byTag('target')); set('weight',byTag('weight')); set('time',byTag('time')); set('x',byTag('die_x')||byTag('time')||numericFields[0]); set('y',byTag('die_y')||numericFields[1]||byTag('value')); set('value',byTag('value')||numericFields.find(field=>field.id!==mapping.x)||numericFields[0]); set('category',category); set('series',fields.find(field=>field!==category && ['categorical','identifier'].includes(field.type))); set('die_x',byTag('die_x')); set('die_y',byTag('die_y')); ['lot_id','wafer_id','tool','chamber','recipe','product','subgroup','specification_low','specification_high'].forEach(role=>set(role,byTag(role)));
  const contracts=['bar','line','scatter','table','timeline','diagram_flow','engineering','wafer'];
  return contracts.map(view=>{const validation=contractFor(view).validate(mapping,fields);return {view,mapping,confidence:Math.min(1,Object.keys(mapping).length/Math.max(1,fields.length)),unresolved:validation.missing,incompatible:validation.incompatible};}).sort((a,b)=>(a.unresolved.length+a.incompatible.length)-(b.unresolved.length+b.incompatible.length));
}
const contractView=view=>view==='diagram'?'diagram_flow':view;
export function candidateForView(result, view) {
  return (result?.candidate_mappings||[]).find(candidate=>candidate.view===contractView(view))||null;
}
export function recommendViews(fields, candidates=inferMappings(fields)) {
  const mapping=candidateForView({candidate_mappings:candidates},'bar')?.mapping||{}, tags=new Set(fields.flatMap(field=>field.semantic_tags||[])), numeric=fields.filter(field=>['integer','number'].includes(field.type)); const out=[];
  const add=(view,reason,confidence)=>{const candidate=candidateForView({candidate_mappings:candidates},view);if(candidate&&!candidate.unresolved.length&&!candidate.incompatible.length)out.push({view,contract_view:candidate.view,mapping:{...candidate.mapping},unresolved:[...candidate.unresolved],incompatible:[...candidate.incompatible],reason,confidence});};
  if(mapping.die_x&&mapping.die_y&&mapping.value)add('wafer','Die coordinates and a measured value were recognized.',.98);
  if(mapping.source&&mapping.target)add('diagram','Source and target fields were recognized.',.95);
  if(mapping.time&&numeric.length)add('line','Time and measurement fields were recognized.',.92);
  if(numeric.length>=2)add('scatter','Two numeric fields were recognized.',.84);
  if(mapping.category&&mapping.value)add('bar','A category and measured value were recognized.',.88);
  if(tags.has('subgroup')&&mapping.value)add('engineering','Subgroup and measurement fields were recognized.',.9);
  add('table','Tabular data is always available.',.5); return out.sort((a,b)=>b.confidence-a.confidence);
}
export function datasetFromIntake(result, id, name='Pasted data') { return {id,name,revision:1,fields:result.fields,rows:result.rows,source:{kind:'clipboard',label:result.delimiter==='\t'?'TSV':'delimited text',imported_at:new Date().toISOString()},warnings:result.warnings,metadata:{header:result.header}}; }
export function appendCompatibleDataset(existing, incoming) {
  const normalized=fields=>fields.map(field=>slug(field.name));
  const current=normalized(existing.fields||[]), next=normalized(incoming.fields||[]);
  if(!current.length || current.length!==next.length || current.some((name,index)=>name!==next[index])) return {ok:false,reason:'Append requires the same column headings in the same order.'};
  const dataset=structuredClone(existing);
  dataset.rows.push(...(incoming.rows||[]).map(row=>Array.from({length:current.length},(_,index)=>row[index]??null)));
  dataset.revision=(existing.revision||0)+1;
  dataset.warnings=[...(existing.warnings||[]),...(incoming.warnings||[])];
  return {ok:true,dataset};
}
