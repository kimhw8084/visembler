function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

export function matchSizePatches(entries, kind, {
  canvasWidth=1600,
  canvasHeight=900,
  inset=0,
}={}) {
  const usable=(entries||[]).filter(entry=>entry?.id&&entry?.r);
  if(usable.length<2)return [];
  if(!['width','height','size'].includes(kind))throw new Error(`Unsupported match-size kind: ${kind}`);

  const reference=usable[0];
  const availableW=Math.max(1,canvasWidth-inset*2);
  const availableH=Math.max(1,canvasHeight-inset*2);
  const patches=[];

  for(const target of usable.slice(1)) {
    const minW=Math.max(1,Number(target.minW)||1);
    const minH=Math.max(1,Number(target.minH)||1);
    const requestedW=kind==='width'||kind==='size' ? reference.r.w : target.r.w;
    const requestedH=kind==='height'||kind==='size' ? reference.r.h : target.r.h;
    const w=Math.min(availableW,Math.max(minW,Number(requestedW)||minW));
    const h=Math.min(availableH,Math.max(minH,Number(requestedH)||minH));
    const x=clamp(Number(target.r.x)||0,inset,Math.max(inset,canvasWidth-inset-w));
    const y=clamp(Number(target.r.y)||0,inset,Math.max(inset,canvasHeight-inset-h));
    const patch={};
    if(kind==='width'||kind==='size')patch.w=w;
    if(kind==='height'||kind==='size')patch.h=h;
    if(Math.abs(x-(Number(target.r.x)||0))>.01)patch.x=x;
    if(Math.abs(y-(Number(target.r.y)||0))>.01)patch.y=y;
    patches.push({id:target.id,patch});
  }
  return patches;
}
