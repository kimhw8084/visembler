export function personalPresetKind(preset) {
  return preset?.kind==='section' ? 'section' : 'report';
}

export function personalPresetSummary(preset) {
  const bindings=Array.isArray(preset?.binding_contract?.slots)?preset.binding_contract.slots.length:0;
  const source=preset?.reuse_mode?(preset.reuse_mode==='copy'?'source data included':'reusable structure'):'';
  const dataSummary=`${bindings?`${bindings} data source${bindings===1?'':'s'} · `:''}${source}`;
  if(personalPresetKind(preset)==='section') {
    const count=Array.isArray(preset?.payload?.items)?preset.payload.items.length:0;
    return `Section · ${count} element${count===1?'':'s'}${dataSummary?` · ${dataSummary}`:''}`;
  }
  const count=Array.isArray(preset?.model?.items)?preset.model.items.length:0;
  const mode=String(preset?.model?.mode||'smart');
  return `Report · ${count} element${count===1?'':'s'} · ${mode}${dataSummary?` · ${dataSummary}`:''}`;
}

export function clonePersonalPreset(preset, {id, name}={}) {
  const kind=personalPresetKind(preset);
  if(kind==='section') {
    return {
      id:String(id||preset.id||''),
      name:String(name||preset.name||''),
      kind:'section',
      payload:structuredClone(preset.payload),
      reuse_mode:preset.reuse_mode||'copy',
      binding_contract:structuredClone(preset.binding_contract||null),
    };
  }
  return {
    id:String(id||preset.id||''),
    name:String(name||preset.name||''),
    kind:'report',
    model:structuredClone(preset.model),
    reuse_mode:preset.reuse_mode||'copy',
    binding_contract:structuredClone(preset.binding_contract||null),
  };
}
