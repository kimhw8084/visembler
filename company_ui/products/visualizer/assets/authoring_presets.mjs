export function personalPresetKind(preset) {
  return preset?.kind==='section' ? 'section' : 'report';
}

export function personalPresetSummary(preset) {
  if(personalPresetKind(preset)==='section') {
    const count=Array.isArray(preset?.payload?.items)?preset.payload.items.length:0;
    return `Section · ${count} element${count===1?'':'s'}`;
  }
  const count=Array.isArray(preset?.model?.items)?preset.model.items.length:0;
  const mode=String(preset?.model?.mode||'smart');
  return `Report · ${count} element${count===1?'':'s'} · ${mode}`;
}

export function clonePersonalPreset(preset, {id, name}={}) {
  const kind=personalPresetKind(preset);
  if(kind==='section') {
    return {
      id:String(id||preset.id||''),
      name:String(name||preset.name||''),
      kind:'section',
      payload:structuredClone(preset.payload),
    };
  }
  return {
    id:String(id||preset.id||''),
    name:String(name||preset.name||''),
    kind:'report',
    model:structuredClone(preset.model),
  };
}
