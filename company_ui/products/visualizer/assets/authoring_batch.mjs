const BATCH_FIELDS=Object.freeze({
  showTitle:Object.freeze({
    read:entry=>entry?.showTitle===true||entry?.show_title===true,
    normalize:value=>value==='true'||value===true,
  }),
  textAlign:Object.freeze({
    read:entry=>entry?.textAlign||entry?.text_align||'left',
    normalize:value=>['left','center','right'].includes(value)?value:null,
  }),
  contentDensity:Object.freeze({
    read:entry=>entry?.contentDensity||'fit',
    normalize:value=>['fit','fill'].includes(value)?value:null,
  }),
  emphasis:Object.freeze({
    read:entry=>entry?.emphasis||'standard',
    normalize:value=>['compact','standard','prominent','hero'].includes(value)?value:null,
  }),
});

export function batchPropertyState(entries, field) {
  const spec=BATCH_FIELDS[field];
  if(!spec)return {mixed:false,value:null,count:0,unlocked:0};
  const values=(entries||[]).filter(Boolean).map(entry=>spec.read(entry));
  const unique=[...new Set(values.map(value=>JSON.stringify(value)))];
  return {
    mixed:unique.length>1,
    value:unique.length===1?values[0]:null,
    count:values.length,
    unlocked:(entries||[]).filter(entry=>entry&&!entry.locked).length,
  };
}

export function batchSelectionState(entries) {
  return Object.fromEntries(
    Object.keys(BATCH_FIELDS).map(field=>[field,batchPropertyState(entries,field)])
  );
}

export function batchPatchPlan(entries, field, rawValue) {
  const spec=BATCH_FIELDS[field];
  if(!spec)return [];
  const value=spec.normalize(rawValue);
  if(value===null)return [];
  return (entries||[])
    .filter(entry=>entry&&!entry.locked)
    .map(entry=>({id:entry.id,patch:{[field]:value}}));
}

export function batchFieldLabel(field) {
  return ({
    showTitle:'title visibility',
    textAlign:'content alignment',
    contentDensity:'vertical space',
    emphasis:'visual emphasis',
  })[field]||field;
}
