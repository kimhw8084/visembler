function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
function uniqueGroupId(groups, base) {
  let candidate=base, suffix=2;
  while(Object.prototype.hasOwnProperty.call(groups||{},candidate)) {
    candidate=`${base}-${suffix++}`;
  }
  return candidate;
}
export function duplicateSelectionPlan(model, selectedIds, {
  mode=model?.mode||'smart',
  canvasWidth=1600,
  canvasHeight=900,
  offset=24,
}={}) {
  const items=Array.isArray(model?.items)?model.items:[];
  const groups=model?.groups&&typeof model.groups==='object'?model.groups:{};
  const selected=new Set((selectedIds||[]).map(String));
  const sources=items.filter(entry=>entry&&selected.has(String(entry.id)));
  if(!sources.length) return {ops:[],newIds:[],nextId:Number(model?.nextId)||1};

  const baseNext=Math.max(1,Number(model?.nextId)||1);
  const idMap=new Map();
  sources.forEach((source,index)=>idMap.set(String(source.id),`c${baseNext+index}`));

  const completeGroups=Object.entries(groups).filter(([,group])=>{
    const members=Array.isArray(group?.items)?group.items.map(String):[];
    return members.length>0 && members.every(id=>selected.has(id));
  });
  const groupMap=new Map();
  completeGroups.forEach(([gid],index)=>{
    groupMap.set(String(gid),uniqueGroupId(groups,`g-copy-${baseNext}-${index+1}`));
  });

  const maxZ=items.reduce((value,entry)=>Math.max(value,Number(entry?.z)||0),0);
  const ops=[], newIds=[];
  sources.forEach((source,index)=>{
    const copy=structuredClone(source);
    const nextId=idMap.get(String(source.id));
    copy.id=nextId;
    copy.order=items.length+index;
    copy.z=maxZ+index+1;
    copy.title=`${String(source.title||source.element||'Element')} copy`.slice(0,120);
    copy.groupId=source.groupId&&groupMap.has(String(source.groupId))
      ? groupMap.get(String(source.groupId))
      : null;
    if(mode!=='smart') {
      const width=Math.max(0,Number(source.w)||0);
      const height=Math.max(0,Number(source.h)||0);
      copy.x=clamp((Number(source.x)||0)+offset,0,Math.max(0,canvasWidth-width));
      copy.y=clamp((Number(source.y)||0)+offset,0,Math.max(0,canvasHeight-height));
    }
    newIds.push(nextId);
    ops.push({op:'item.add',item:copy});
  });

  completeGroups.forEach(([gid,group])=>{
    const nextGroupId=groupMap.get(String(gid));
    ops.push({
      op:'group.set',
      id:nextGroupId,
      value:{
        ...structuredClone(group),
        id:nextGroupId,
        items:(group.items||[]).map(id=>idMap.get(String(id))).filter(Boolean),
      },
    });
  });

  const nextId=baseNext+sources.length;
  ops.push({op:'model.patch',patch:{nextId}});
  return {ops,newIds,nextId};
}
