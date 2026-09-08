function clone(value) {
  return structuredClone(value);
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function uniqueId(existing, base) {
  let value=base, suffix=2;
  while(existing.has(value)) value=`${base}-${suffix++}`;
  existing.add(value);
  return value;
}

function rectFor(entry, rects) {
  const supplied=rects?.[entry.id];
  if(supplied) return clone(supplied);
  return {
    x:Number(entry.x)||0,
    y:Number(entry.y)||0,
    w:Math.max(1,Number(entry.w)||200),
    h:Math.max(1,Number(entry.h)||140),
  };
}

export function buildCompositionClipboard(model, selectedIds, {rects={}}={}) {
  const selected=new Set((selectedIds||[]).map(String));
  const items=(model?.items||[]).filter(entry=>entry&&selected.has(String(entry.id)));
  if(items.length<2) return null;

  const groups=[];
  for(const [gid,group] of Object.entries(model?.groups||{})) {
    const members=(group?.items||[]).map(String);
    if(members.length&&members.every(id=>selected.has(id))) groups.push(clone(group));
  }

  const datasetIds=new Set(items.map(entry=>entry.dataset_id).filter(Boolean).map(String));
  const datasets=(model?.datasets||[])
    .filter(dataset=>datasetIds.has(String(dataset?.id)))
    .map(clone);

  return {
    version:2,
    kind:'composition',
    source_mode:model?.mode||'smart',
    items:items.map(entry=>({...clone(entry),_clipboard_rect:rectFor(entry,rects)})),
    groups,
    datasets,
  };
}

export function pasteCompositionPlan(model, payload, {
  mode=model?.mode||'smart',
  canvasWidth=1600,
  canvasHeight=900,
  inset=0,
  offset=24,
}={}) {
  if(payload?.kind!=='composition'||!Array.isArray(payload.items)||payload.items.length<2) {
    return {ops:[],newIds:[],nextId:Number(model?.nextId)||1};
  }

  const baseNext=Math.max(1,Number(model?.nextId)||1);
  const itemIdMap=new Map();
  payload.items.forEach((source,index)=>itemIdMap.set(String(source.id),`c${baseNext+index}`));

  const existingGroupIds=new Set(Object.keys(model?.groups||{}));
  const groupIdMap=new Map();
  (payload.groups||[]).forEach((group,index)=>{
    groupIdMap.set(
      String(group.id),
      uniqueId(existingGroupIds,`g-paste-${baseNext}-${index+1}`),
    );
  });

  const existingDatasetIds=new Set((model?.datasets||[]).map(dataset=>String(dataset.id)));
  const datasetIdMap=new Map();
  const clonedDatasets=[];
  (payload.datasets||[]).forEach((dataset,index)=>{
    const id=uniqueId(existingDatasetIds,`dataset-paste-${baseNext}-${index+1}`);
    datasetIdMap.set(String(dataset.id),id);
    clonedDatasets.push({
      ...clone(dataset),
      id,
      name:`${String(dataset.name||'Dataset')} copy`.slice(0,120),
      revision:1,
    });
  });

  const sourceRects=payload.items.map(source=>source._clipboard_rect||rectFor(source,{}));
  const left=Math.min(...sourceRects.map(r=>Number(r.x)||0));
  const top=Math.min(...sourceRects.map(r=>Number(r.y)||0));
  const right=Math.max(...sourceRects.map(r=>(Number(r.x)||0)+(Number(r.w)||200)));
  const bottom=Math.max(...sourceRects.map(r=>(Number(r.y)||0)+(Number(r.h)||140)));
  const union={x:left,y:top,w:right-left,h:bottom-top};

  let dx=offset,dy=offset;
  if(mode!=='smart') {
    const minDx=inset-union.x;
    const maxDx=canvasWidth-inset-(union.x+union.w);
    const minDy=inset-union.y;
    const maxDy=canvasHeight-inset-(union.y+union.h);
    dx=minDx<=maxDx?clamp(offset,minDx,maxDx):minDx;
    dy=minDy<=maxDy?clamp(offset,minDy,maxDy):minDy;
  }

  const maxZ=(model?.items||[]).reduce((value,entry)=>Math.max(value,Number(entry?.z)||0),0);
  const ops=[],newIds=[];

  payload.items.forEach((source,index)=>{
    const copy=clone(source);
    const rect=copy._clipboard_rect||rectFor(copy,{});
    delete copy._clipboard_rect;
    copy.id=itemIdMap.get(String(source.id));
    copy.order=(model?.items||[]).length+index;
    copy.z=maxZ+index+1;
    copy.title=`${String(copy.title||copy.element||'Element')} copy`.slice(0,120);

    if(copy.groupId&&groupIdMap.has(String(copy.groupId))) {
      copy.groupId=groupIdMap.get(String(copy.groupId));
    } else {
      copy.groupId=null;
    }

    if(copy.dataset_id) {
      if(datasetIdMap.has(String(copy.dataset_id))) copy.dataset_id=datasetIdMap.get(String(copy.dataset_id));
      else delete copy.dataset_id;
    }

    if(mode!=='smart') {
      const w=Math.max(1,Number(rect.w)||200);
      const h=Math.max(1,Number(rect.h)||140);
      copy.w=w;
      copy.h=h;
      copy.x=clamp((Number(rect.x)||0)+dx,inset,Math.max(inset,canvasWidth-inset-w));
      copy.y=clamp((Number(rect.y)||0)+dy,inset,Math.max(inset,canvasHeight-inset-h));
    }

    newIds.push(copy.id);
    ops.push({op:'item.add',item:copy});
  });

  for(const group of payload.groups||[]) {
    const gid=groupIdMap.get(String(group.id));
    if(!gid) continue;
    ops.push({
      op:'group.set',
      id:gid,
      value:{
        ...clone(group),
        id:gid,
        items:(group.items||[]).map(id=>itemIdMap.get(String(id))).filter(Boolean),
      },
    });
  }

  const nextId=baseNext+payload.items.length;
  const patch={nextId};
  if(clonedDatasets.length) patch.datasets=[...(model?.datasets||[]),...clonedDatasets];
  ops.push({op:'model.patch',patch});
  return {ops,newIds,nextId,datasetIds:[...datasetIdMap.values()]};
}
