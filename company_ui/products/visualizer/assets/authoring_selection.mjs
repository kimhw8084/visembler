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
export function isAdditiveSelectionGesture(event) {
  return !!(event?.shiftKey || event?.metaKey || event?.ctrlKey);
}
export function selectionLockState(entries) {
  const valid=(entries||[]).filter(Boolean);
  const locked=valid.filter(entry=>!!entry.locked).length;
  const unlocked=valid.length-locked;
  return {
    count:valid.length,
    locked,
    unlocked,
    mixed:locked>0&&unlocked>0,
    allLocked:valid.length>0&&unlocked===0,
    allUnlocked:valid.length>0&&locked===0,
  };
}
export function selectionLockPlan(entries, target) {
  target=!!target;
  return (entries||[])
    .filter(entry=>entry&&!!entry.locked!==target)
    .map(entry=>({id:entry.id,patch:{locked:target}}));
}

export function structuralSelectionState(model, selectedIds) {
  const items=Array.isArray(model?.items)?model.items:[];
  const groups=model?.groups&&typeof model.groups==='object'?model.groups:{};
  const selected=new Set((selectedIds||[]).map(String));
  const entries=items.filter(entry=>entry&&selected.has(String(entry.id)));
  const lockedCount=entries.filter(entry=>!!entry.locked).length;
  const unlockedCount=entries.length-lockedCount;
  const groupedCount=entries.filter(entry=>!!entry.groupId).length;
  const groupIds=[...new Set(entries.map(entry=>entry.groupId).filter(Boolean).map(String))];
  const byId=new Map(items.map(entry=>[String(entry.id),entry]));
  const blockedGroupIds=[];
  const ungroupableGroupIds=[];
  for(const gid of groupIds) {
    const group=groups[gid];
    if(!group)continue;
    const members=(group.items||[]).map(id=>byId.get(String(id))).filter(Boolean);
    if(members.some(entry=>!!entry.locked))blockedGroupIds.push(gid);
    else ungroupableGroupIds.push(gid);
  }
  return {
    selectedCount:entries.length,
    lockedCount,
    unlockedCount,
    groupedCount,
    groupable:entries.length>=2&&lockedCount===0&&groupedCount===0,
    groupIds,
    blockedGroupIds,
    ungroupableGroupIds,
  };
}
export function selectionActionEligibility(model, selectedIds, {mode=model?.mode||'smart',hasClipboard=false}={}) {
  const structure=structuralSelectionState(model,selectedIds);
  const noUnlocked='No eligible unlocked members';
  const atomicLocked='Locked members prevent an atomic structural action';
  const groupReason=structure.selectedCount<2?'Selection count insufficient':structure.lockedCount?atomicLocked:structure.groupedCount?'Existing group membership conflicts with Group':'';
  const ungroupReason=!structure.groupIds.length?'Selection has no group membership':structure.blockedGroupIds.length?atomicLocked:'';
  const partialReason=structure.unlockedCount?'' : noUnlocked;
  const arrangeReason=mode==='smart'?'Arrange is automatic in Smart mode':structure.unlockedCount<2?(structure.unlockedCount? 'Selection count insufficient':noUnlocked):'';
  return {
    summary:{count:structure.selectedCount,unlocked:structure.unlockedCount,locked:structure.lockedCount,grouped:structure.groupedCount},
    group:{enabled:!groupReason,reason:groupReason,atomic:true},
    ungroup:{enabled:!ungroupReason,reason:ungroupReason,atomic:true},
    front:{enabled:!!structure.unlockedCount,reason:partialReason,partial:structure.lockedCount>0},
    back:{enabled:!!structure.unlockedCount,reason:partialReason,partial:structure.lockedCount>0},
    delete:{enabled:!!structure.unlockedCount,reason:partialReason,partial:structure.lockedCount>0},
    lock:{enabled:structure.unlockedCount>0,reason:structure.unlockedCount?'':noUnlocked,partial:structure.lockedCount>0},
    unlock:{enabled:structure.lockedCount>0,reason:structure.lockedCount?'':'No locked members'},
    arrange:{enabled:!arrangeReason,reason:arrangeReason,partial:structure.lockedCount>0},
    batch:{enabled:!!structure.unlockedCount,reason:partialReason,partial:structure.lockedCount>0},
    reuse:{copySelection:{enabled:structure.selectedCount>1,reason:structure.selectedCount>1?'':'Selection count insufficient'},cut:{enabled:structure.selectedCount>0&&structure.lockedCount===0,reason:!structure.selectedCount?'Selection count insufficient':structure.lockedCount?atomicLocked:''},pasteStyle:{enabled:!!hasClipboard&&!!structure.unlockedCount,reason:!hasClipboard?'Clipboard empty':partialReason,partial:structure.lockedCount>0}},
  };
}
export function layerSelectionPlan(entries, delta) {
  const step=Number(delta)||0;
  return (entries||[])
    .filter(entry=>entry&&!entry.locked)
    .map(entry=>({
      id:entry.id,
      patch:{z:clamp((Number(entry.z)||1)+step,0,99)},
    }));
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
