const COMMON_PRESENTATION_FIELDS=Object.freeze([
  'showTitle',
  'show_title',
  'textAlign',
  'text_align',
  'contentDensity',
  'emphasis',
  'variant',
]);

const ENGINE_PRESENTATION_FIELDS=Object.freeze({
  MetricEngine:Object.freeze(['value_format','decimals','currency_symbol']),
  ImageMediaEngine:Object.freeze(['fit','focal']),
});

function pick(source, fields) {
  const result={};
  for(const key of fields) if(Object.prototype.hasOwnProperty.call(source||{},key)) {
    result[key]=structuredClone(source[key]);
  }
  return result;
}

export function styleSnapshot(entry) {
  const engine=String(entry?.engine||'');
  return {
    version:1,
    kind:'presentation-style',
    sourceEngine:engine,
    common:pick(entry,COMMON_PRESENTATION_FIELDS),
    engine:pick(entry,ENGINE_PRESENTATION_FIELDS[engine]||[]),
  };
}

export function stylePatchForTarget(snapshot, target) {
  if(snapshot?.kind!=='presentation-style'||!target)return {};
  const patch={...structuredClone(snapshot.common||{})};
  if(String(target.engine||'')===String(snapshot.sourceEngine||'')) {
    Object.assign(patch,structuredClone(snapshot.engine||{}));
  }
  return patch;
}

export function stylePastePlan(entries, snapshot) {
  return (entries||[])
    .filter(entry=>entry&&!entry.locked)
    .map(entry=>({id:entry.id,patch:stylePatchForTarget(snapshot,entry)}))
    .filter(({patch})=>Object.keys(patch).length>0);
}

export function styleSummary(snapshot) {
  if(snapshot?.kind!=='presentation-style')return 'No copied style';
  const common=Object.keys(snapshot.common||{}).length;
  const engine=Object.keys(snapshot.engine||{}).length;
  return `${common} shared${engine?` · ${engine} ${snapshot.sourceEngine||'engine'}-specific`:''}`;
}
