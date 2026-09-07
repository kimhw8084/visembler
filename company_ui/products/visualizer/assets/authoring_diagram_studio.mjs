// Diagram Studio's local, versioned model and deterministic manipulation core.
// This module deliberately has no UI or network dependencies.  The report keeps
// the resulting object under item.diagram while legacy nodes/edges/direction
// fields are mirrored by diagramToEntry for older reports and renderers.

export const DIAGRAM_SCHEMA = 'visembler.diagram.studio';
export const DIAGRAM_VERSION = 1;

const finite = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clean = value => String(value ?? '').trim();
const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const idPart = value => clean(value).replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64) || 'node';

export const SHAPE_CATALOG = Object.freeze([
  {id:'start', label:'Start', group:'General', icon:'▶', width:148, height:64},
  {id:'end', label:'End', group:'General', icon:'■', width:148, height:64},
  {id:'process', label:'Process', group:'General', icon:'▣', width:168, height:76},
  {id:'decision', label:'Decision', group:'General', icon:'◇', width:168, height:88},
  {id:'data', label:'Data', group:'General', icon:'▱', width:168, height:76},
  {id:'document', label:'Document', group:'General', icon:'▤', width:168, height:82},
  {id:'database', label:'Database / Store', group:'General', icon:'◉', width:168, height:76},
  {id:'delay', label:'Delay', group:'General', icon:'◷', width:148, height:64},
  {id:'subprocess', label:'Subprocess', group:'General', icon:'▥', width:180, height:76},
  {id:'note', label:'Note / Callout', group:'General', icon:'✎', width:190, height:96},
  {id:'container', label:'Container / Group', group:'General', icon:'□', width:300, height:190},
  {id:'tool', label:'Tool', group:'Manufacturing', icon:'⚙', width:168, height:76},
  {id:'chamber', label:'Chamber', group:'Manufacturing', icon:'◌', width:168, height:76},
  {id:'recipe', label:'Recipe / Step', group:'Manufacturing', icon:'≡', width:180, height:76},
  {id:'lot', label:'Lot / Wafer', group:'Manufacturing', icon:'◉', width:168, height:76},
  {id:'inspection', label:'Inspection', group:'Manufacturing', icon:'⌕', width:168, height:76},
  {id:'hold', label:'Hold', group:'Manufacturing', icon:'Ⅱ', width:148, height:64},
  {id:'release', label:'Release', group:'Manufacturing', icon:'✓', width:148, height:64},
  {id:'defect', label:'Defect / Risk', group:'Manufacturing', icon:'!', width:168, height:76},
  {id:'handoff', label:'Handoff', group:'Manufacturing', icon:'⇄', width:168, height:76},
]);

const CATALOG = new Map(SHAPE_CATALOG.map(shape => [shape.id, shape]));
const ports = Object.freeze([
  {id:'top', x:.5, y:0}, {id:'right', x:1, y:.5},
  {id:'bottom', x:.5, y:1}, {id:'left', x:0, y:.5},
]);

function shapeDefinition(shape) { return CATALOG.get(shape) || CATALOG.get('process'); }
function uniqueId(prefix, taken) {
  const base = idPart(prefix); let index = 1; let value = base;
  while (taken.has(value)) value = `${base}-${index++}`;
  taken.add(value); return value;
}

function defaultNode(raw, index, taken) {
  const shape = shapeDefinition(clean(raw?.shape || raw?.type || 'process').toLowerCase());
  const id = uniqueId(raw?.id || `node-${index + 1}`, taken);
  const label = clean(raw?.label ?? raw?.name ?? (typeof raw === 'string' ? raw : '')) || `Node ${index + 1}`;
  return {
    id, shape: shape.id, label, secondary: clean(raw?.secondary ?? raw?.detail ?? ''),
    x: finite(raw?.x, 64 + (index % 4) * 236), y: finite(raw?.y, 64 + Math.floor(index / 4) * 142),
    width: Math.max(88, finite(raw?.width ?? raw?.w, shape.width)),
    height: Math.max(48, finite(raw?.height ?? raw?.h, shape.height)),
    style: {fill:raw?.style?.fill || '', border:raw?.style?.border || '', text:raw?.style?.text || '', borderWidth:finite(raw?.style?.borderWidth, 1), borderStyle:raw?.style?.borderStyle || 'solid'},
    status: clean(raw?.status || ''), semantic: clean(raw?.semantic || raw?.semantic_type || ''),
    role: clean(raw?.role || ''), owner: clean(raw?.owner || ''),
    parent: clean(raw?.parent || raw?.parent_id || ''), lane: clean(raw?.lane || raw?.lane_id || ''),
    layer: clean(raw?.layer || raw?.layer_id || 'base') || 'base', lock: raw?.lock === true || raw?.locked === true,
    ports: Array.isArray(raw?.ports) && raw.ports.length ? clone(raw.ports) : clone(ports),
    pinned: raw?.pinned === true || raw?.manual_layout === true,
  };
}

function normalizeLabels(raw, fallback) {
  if (Array.isArray(raw?.labels)) return raw.labels.map((label, index) => typeof label === 'string' ? {id:`label-${index + 1}`,text:label,position:'center',offset:0} : ({id:clean(label?.id) || `label-${index + 1}`,text:clean(label?.text ?? label?.label),position:label?.position || 'center',offset:finite(label?.offset, 0)})).filter(label => label.text);
  const text = clean(raw?.label ?? fallback);
  return text ? [{id:'label-1',text,position:'center',offset:0}] : [];
}

function defaultEdge(raw, index, nodeIds, fallbackLabel, taken) {
  const source = clean(raw?.source ?? raw?.from ?? raw?.[0]);
  const target = clean(raw?.target ?? raw?.to ?? raw?.[1]);
  if (!source || !target || source === target || !nodeIds.has(source) || !nodeIds.has(target)) return null;
  const id = uniqueId(raw?.id || `edge-${index + 1}`, taken);
  return {
    id, source, target, sourcePort:clean(raw?.sourcePort ?? raw?.source_port ?? '') || 'floating', targetPort:clean(raw?.targetPort ?? raw?.target_port ?? '') || 'floating',
    routing:raw?.routing === 'straight' || raw?.routing === 'curved' ? raw.routing : 'orthogonal',
    waypoints:Array.isArray(raw?.waypoints) ? raw.waypoints.map(point => ({x:finite(point?.x, 0),y:finite(point?.y, 0)})) : [],
    labels:normalizeLabels(raw, fallbackLabel), startMarker:raw?.startMarker || raw?.start_marker || 'none', endMarker:raw?.endMarker || raw?.end_marker || 'arrow',
    style:{color:raw?.style?.color || raw?.color || '', width:Math.max(1, finite(raw?.style?.width ?? raw?.width, 2)), line:raw?.style?.line || raw?.line_style || 'solid', corner:'rounded'},
    layer:clean(raw?.layer || raw?.layer_id || 'base') || 'base', lock:raw?.lock === true || raw?.locked === true,
  };
}

function normalizeGroups(raw) {
  if (Array.isArray(raw)) return raw.map((group, index) => ({id:clean(group?.id) || `group-${index + 1}`,label:clean(group?.label) || `Group ${index + 1}`,nodeIds:Array.isArray(group?.nodeIds) ? group.nodeIds.map(String) : Array.isArray(group?.items) ? group.items.map(String) : [],x:finite(group?.x, 32),y:finite(group?.y, 32),width:Math.max(180,finite(group?.width ?? group?.w,320)),height:Math.max(120,finite(group?.height ?? group?.h,220)),style:clone(group?.style || {}),layer:clean(group?.layer || 'base') || 'base',lock:group?.lock === true}));
  if (raw && typeof raw === 'object') return Object.entries(raw).map(([id, group], index) => ({id,label:clean(group?.label) || `Group ${index + 1}`,nodeIds:Array.isArray(group?.items) ? group.items.map(String) : Array.isArray(group?.nodeIds) ? group.nodeIds.map(String) : [],x:finite(group?.x,32),y:finite(group?.y,32),width:Math.max(180,finite(group?.w ?? group?.width,320)),height:Math.max(120,finite(group?.h ?? group?.height,220)),style:clone(group?.style || {}),layer:clean(group?.layer || 'base') || 'base',lock:group?.lock === true}));
  return [];
}

function normalizeLanes(raw) {
  const input = Array.isArray(raw) ? raw : [];
  return input.map((lane, index) => ({id:clean(lane?.id) || `lane-${index + 1}`,label:clean(lane?.label) || `Lane ${index + 1}`,orientation:lane?.orientation === 'vertical' ? 'vertical' : 'horizontal',x:finite(lane?.x, 24),y:finite(lane?.y, 24 + index * 160),width:Math.max(240,finite(lane?.width ?? lane?.w, 1200)),height:Math.max(110,finite(lane?.height ?? lane?.h, 140)),order:Number.isFinite(Number(lane?.order)) ? Number(lane.order) : index,style:clone(lane?.style || {}),layer:clean(lane?.layer || 'base') || 'base',lock:lane?.lock === true}));
}

function normalizeLayers(raw) {
  const input = Array.isArray(raw) ? raw : [];
  const result = input.map((layer, index) => ({id:clean(layer?.id) || `layer-${index + 1}`,name:clean(layer?.name) || `Layer ${index + 1}`,visible:layer?.visible !== false,lock:layer?.lock === true,order:Number.isFinite(Number(layer?.order)) ? Number(layer.order) : index}));
  if (!result.some(layer => layer.id === 'base')) result.unshift({id:'base',name:'Main diagram',visible:true,lock:false,order:0});
  return result;
}

export function normalizeDiagram(value = {}) {
  const source = value && typeof value === 'object' ? value : {};
  const legacyNodes = Array.isArray(source.nodes) ? source.nodes : [];
  const nodeTaken = new Set();
  const nodes = legacyNodes.map((node, index) => defaultNode(node, index, nodeTaken));
  const nodeIds = new Set(nodes.map(node => node.id));
  const nodeLookup = new Map(nodes.flatMap(node => [[node.id, node.id], [node.label, node.id]]));
  const resolveNode = value => {
    const text = clean(value);
    if (nodeLookup.has(text)) return nodeLookup.get(text);
    const index = Number(text);
    return Number.isInteger(index) && index >= 0 ? nodes[index]?.id || text : text;
  };
  const edgeTaken = new Set();
  const rawEdges = Array.isArray(source.edges) ? source.edges : [];
  const fallbackLabel = clean(source.edge_label || '');
  const edges = rawEdges.map((edge, index) => {
    const rawSource = clean(edge?.source ?? edge?.from ?? edge?.[0]);
    const rawTarget = clean(edge?.target ?? edge?.to ?? edge?.[1]);
    return defaultEdge({...edge,source:resolveNode(rawSource),target:resolveNode(rawTarget)}, index, nodeIds, fallbackLabel, edgeTaken);
  }).filter(Boolean);
  const layoutSource = source.layout && typeof source.layout === 'object' ? source.layout : {};
  return {
    schema:DIAGRAM_SCHEMA, version:DIAGRAM_VERSION,
    nodes, edges, groups:normalizeGroups(source.groups), swimlanes:normalizeLanes(source.swimlanes || source.lanes), layers:normalizeLayers(source.layers),
    layout:{direction:layoutSource.direction === 'down' || source.direction === 'down' ? 'down' : 'right',nodeSpacing:Math.max(24,finite(layoutSource.nodeSpacing, 52)),rankSpacing:Math.max(80,finite(layoutSource.rankSpacing, 92)),mode:layoutSource.mode || 'horizontal',preservePinned:layoutSource.preservePinned !== false,lastCommand:layoutSource.lastCommand || 'Imported'},
  };
}

export function diagramFromEntry(entry = {}) {
  if (entry.diagram && typeof entry.diagram === 'object') return normalizeDiagram(entry.diagram);
  const hasGeometry=(entry.nodes||[]).some(node=>node&&typeof node==='object'&&(Number.isFinite(node.x)||Number.isFinite(node.y)));
  const diagram=normalizeDiagram({nodes:entry.nodes || [],edges:entry.edges || [],direction:entry.direction,edge_label:entry.edge_label});
  return hasGeometry?diagram:autoLayout(diagram,{direction:diagram.layout.direction,preservePinned:true});
}

export function diagramToEntry(entry = {}, value = {}) {
  const diagram = normalizeDiagram(value);
  const firstLabel = diagram.edges.flatMap(edge => edge.labels || []).find(label => label.text)?.text || '';
  const labels = new Map(diagram.nodes.map(node => [node.id, node.label]));
  return {...clone(entry),diagram,nodes:diagram.nodes.map(node => node.label),edges:diagram.edges.map(edge => [labels.get(edge.source) || edge.source,labels.get(edge.target) || edge.target]),direction:diagram.layout.direction,edge_label:firstLabel};
}

export function nodeRect(node) { return {x:finite(node?.x,0),y:finite(node?.y,0),w:Math.max(1,finite(node?.width ?? node?.w,1)),h:Math.max(1,finite(node?.height ?? node?.h,1))}; }
export function rectsOverlap(a,b,padding=0) { return a.x < b.x+b.w+padding && a.x+a.w+padding > b.x && a.y < b.y+b.h+padding && a.y+a.h+padding > b.y; }
export function diagramBounds(diagram) { const nodes=(diagram?.nodes||[]).map(nodeRect); const lanes=(diagram?.swimlanes||[]).map(nodeRect); const groups=(diagram?.groups||[]).map(nodeRect); const all=[...nodes,...lanes,...groups]; if(!all.length)return {x:0,y:0,w:900,h:560}; const minX=Math.min(...all.map(rect=>rect.x)),minY=Math.min(...all.map(rect=>rect.y)),maxX=Math.max(...all.map(rect=>rect.x+rect.w)),maxY=Math.max(...all.map(rect=>rect.y+rect.h)); return {x:minX-40,y:minY-40,w:Math.max(900,maxX-minX+80),h:Math.max(560,maxY-minY+80)}; }

function graphRanks(diagram) {
  const rank = new Map((diagram.nodes || []).map((node,index) => [node.id, 0 + index * 0]));
  const incoming = new Map((diagram.nodes || []).map(node => [node.id, []]));
  (diagram.edges || []).forEach(edge => { if (incoming.has(edge.target)) incoming.get(edge.target).push(edge.source); });
  for (let round=0; round<Math.max(1,diagram.nodes.length); round += 1) (diagram.edges || []).forEach(edge => { rank.set(edge.target, Math.max(rank.get(edge.target) || 0, (rank.get(edge.source) || 0) + 1)); });
  return {rank,incoming};
}

function moveAwayFromOverlap(nodes, pinned, direction) {
  const ordered = [...nodes].sort((a,b) => a.y-b.y || a.x-b.x || a.id.localeCompare(b.id));
  for (let pass=0; pass<ordered.length*2; pass += 1) {
    let changed = false;
    for (let i=0; i<ordered.length; i += 1) for (let j=i+1; j<ordered.length; j += 1) {
      const a=ordered[i],b=ordered[j]; if (!rectsOverlap(nodeRect(a),nodeRect(b),12)) continue;
      const target = pinned.has(a.id) ? b : pinned.has(b.id) ? a : (direction === 'right' ? b : a);
      if (pinned.has(target.id)) continue;
      if (direction === 'right') target.y += target.height + 24; else target.x += target.width + 24;
      changed=true;
    }
    if (!changed) break;
  }
  return nodes;
}

export function autoLayout(value, options = {}) {
  const diagram = normalizeDiagram(value); const direction = options.direction === 'down' || options.direction === 'right' ? options.direction : diagram.layout.direction;
  const mode=options.mode || diagram.layout.mode || 'horizontal'; const spacing = Math.max(24,finite(options.nodeSpacing,mode==='compact'?28:diagram.layout.nodeSpacing)); const rankSpacing = Math.max(80,finite(options.rankSpacing,mode==='compact'?72:diagram.layout.rankSpacing));
  const preservePinned = options.preservePinned !== false; const pinned = new Set(diagram.nodes.filter(node => preservePinned && node.pinned).map(node => node.id));
  const {rank} = graphRanks(diagram); const ranks = new Map(); diagram.nodes.forEach((node,index) => { const key=rank.get(node.id)||0; if(!ranks.has(key))ranks.set(key,[]); ranks.get(key).push({...node,__index:index}); });
  for (const [key,list] of ranks) {
    list.sort((a,b)=>a.__index-b.__index);
    list.forEach((node,index) => { if (pinned.has(node.id)) return; if(direction==='right'){node.x=64+key*(Math.max(node.width,168)+rankSpacing);node.y=64+index*(Math.max(node.height,76)+spacing);}else{node.x=64+index*(Math.max(node.width,168)+spacing);node.y=64+key*(Math.max(node.height,76)+rankSpacing);} });
  }
  moveAwayFromOverlap(diagram.nodes,pinned,direction);
  diagram.layout={...diagram.layout,direction,nodeSpacing:spacing,rankSpacing,mode:options.mode || diagram.layout.mode || (direction==='down'?'vertical':'horizontal'),preservePinned,lastCommand:'Auto layout'};
  return diagram;
}

function segmentHitsRect(a,b,rect,padding=3) {
  const minX=Math.min(a.x,b.x),maxX=Math.max(a.x,b.x),minY=Math.min(a.y,b.y),maxY=Math.max(a.y,b.y);
  if (Math.abs(a.x-b.x)<.1) return a.x>rect.x-padding && a.x<rect.x+rect.w+padding && maxY>rect.y-padding && minY<rect.y+rect.h+padding;
  if (Math.abs(a.y-b.y)<.1) return a.y>rect.y-padding && a.y<rect.y+rect.h+padding && maxX>rect.x-padding && minX<rect.x+rect.w+padding;
  return false;
}
function portPoint(node, port, other) {
  const rect=nodeRect(node); const fixed=port && port !== 'floating' ? port : '';
  if (fixed==='top') return {x:rect.x+rect.w/2,y:rect.y}; if (fixed==='right') return {x:rect.x+rect.w,y:rect.y+rect.h/2}; if (fixed==='bottom') return {x:rect.x+rect.w/2,y:rect.y+rect.h}; if (fixed==='left') return {x:rect.x,y:rect.y+rect.h/2};
  const target=other||{x:rect.x+rect.w+1,y:rect.y+rect.h/2}; const dx=target.x-(rect.x+rect.w/2),dy=target.y-(rect.y+rect.h/2);
  if(Math.abs(dx)>=Math.abs(dy))return {x:rect.x+(dx>=0?rect.w:0),y:rect.y+rect.h/2}; return {x:rect.x+rect.w/2,y:rect.y+(dy>=0?rect.h:0)};
}
function simplifyPoints(points) { return points.filter((point,index)=>index===0||Math.abs(point.x-points[index-1].x)>0.1||Math.abs(point.y-points[index-1].y)>0.1); }

export function routeEdge(diagram, edge) {
  const source=(diagram.nodes||[]).find(node=>node.id===edge.source),target=(diagram.nodes||[]).find(node=>node.id===edge.target); if(!source||!target)return [];
  const targetCenter=nodeRect(target),sourceCenter=nodeRect(source); const start=portPoint(source,edge.sourcePort,{x:targetCenter.x+targetCenter.w/2,y:targetCenter.y+targetCenter.h/2}),end=portPoint(target,edge.targetPort,{x:sourceCenter.x+sourceCenter.w/2,y:sourceCenter.y+sourceCenter.h/2});
  if(edge.waypoints?.length)return [start,...edge.waypoints.map(point=>({x:point.x,y:point.y})),end];
  if(edge.routing==='straight')return [start,end];
  if(edge.routing==='curved')return [start,{x:(start.x+end.x)/2,y:start.y},{x:(start.x+end.x)/2,y:end.y},end];
  const obstacles=(diagram.nodes||[]).filter(node=>node.id!==source.id&&node.id!==target.id); const midX=(start.x+end.x)/2,midY=(start.y+end.y)/2;
  const top=Math.min(start.y,end.y,...obstacles.map(node=>nodeRect(node).y))-56,bottom=Math.max(start.y,end.y,...obstacles.map(node=>nodeRect(node).y+nodeRect(node).h))+56,left=Math.min(start.x,end.x,...obstacles.map(node=>nodeRect(node).x))-56,right=Math.max(start.x,end.x,...obstacles.map(node=>nodeRect(node).x+nodeRect(node).w))+56;
  const candidates=[ [start,{x:midX,y:start.y},{x:midX,y:end.y},end], [start,{x:start.x,y:midY},{x:end.x,y:midY},end], [start,{x:start.x,y:top},{x:end.x,y:top},end], [start,{x:start.x,y:bottom},{x:end.x,y:bottom},end], [start,{x:right,y:start.y},{x:right,y:end.y},end], [start,{x:left,y:start.y},{x:left,y:end.y},end] ];
  const scored=candidates.map(points=>{const cleanPoints=simplifyPoints(points),hits=obstacles.reduce((count,node)=>{const rect=nodeRect(node);for(let index=1;index<cleanPoints.length;index+=1)if(segmentHitsRect(cleanPoints[index-1],cleanPoints[index],rect))return count+1;return count;},0);return {points:cleanPoints,hits};});
  scored.sort((a,b)=>a.hits-b.hits||a.points.length-b.points.length); return scored[0].points;
}

export function routeAll(value) { const diagram=normalizeDiagram(value); return diagram.edges.map(edge=>({edge:edge.id,points:routeEdge(diagram,edge)})); }
export function cleanDiagram(value, options = {}) { const diagram=autoLayout(value,{...options,preservePinned:options.preservePinned !== false}); diagram.edges=diagram.edges.map(edge=>({...edge,waypoints:[]})); diagram.layout={...diagram.layout,lastCommand:'Clean Diagram'}; return diagram; }

export function addNode(value, input = {}) { const diagram=normalizeDiagram(value),taken=new Set(diagram.nodes.map(node=>node.id)); const node=defaultNode({...input,id:input.id || `node-${diagram.nodes.length+1}`},diagram.nodes.length,taken); node.x=finite(input.x,node.x); node.y=finite(input.y,node.y); diagram.nodes.push(node); diagram.layout.lastCommand='Add node'; return {diagram,node}; }
export function updateNode(value, id, patch = {}) { const diagram=normalizeDiagram(value),node=diagram.nodes.find(item=>item.id===id); if(!node||node.lock)return diagram; const shape=patch.shape?shapeDefinition(patch.shape):null; Object.assign(node,patch); if(shape){node.shape=shape.id;node.width=Math.max(88,finite(patch.width ?? patch.w,node.width||shape.width));node.height=Math.max(48,finite(patch.height ?? patch.h,node.height||shape.height));} node.x=finite(node.x,0);node.y=finite(node.y,0);node.width=Math.max(88,finite(node.width,node.w||168));node.height=Math.max(48,finite(node.height,node.h||76)); diagram.layout.lastCommand='Edit node'; return diagram; }
export function removeNodes(value, ids = []) { const diagram=normalizeDiagram(value),selected=new Set(ids); diagram.nodes=diagram.nodes.filter(node=>!selected.has(node.id)||node.lock); diagram.edges=diagram.edges.filter(edge=>!selected.has(edge.source)&&!selected.has(edge.target)||edge.lock); diagram.groups=diagram.groups.map(group=>({...group,nodeIds:group.nodeIds.filter(id=>!selected.has(id))})).filter(group=>group.nodeIds.length); diagram.layout.lastCommand='Delete selection'; return diagram; }
export function addEdge(value, source, target, patch = {}) { const diagram=normalizeDiagram(value),sourceId=clean(source),targetId=clean(target); if(!diagram.nodes.some(node=>node.id===sourceId)||!diagram.nodes.some(node=>node.id===targetId)||sourceId===targetId)return diagram; if(diagram.edges.some(edge=>edge.source===sourceId&&edge.target===targetId))return diagram; const taken=new Set(diagram.edges.map(edge=>edge.id)); const edge=defaultEdge({...patch,id:patch.id || `edge-${diagram.edges.length+1}`,source:sourceId,target:targetId},diagram.edges.length,new Set(diagram.nodes.map(node=>node.id)),patch.label || '',taken); if(edge)diagram.edges.push(edge); diagram.layout.lastCommand='Connect nodes'; return diagram; }
export function updateEdge(value, id, patch = {}) { const diagram=normalizeDiagram(value),edge=diagram.edges.find(item=>item.id===id); if(!edge||edge.lock)return diagram; if((patch.source&&!diagram.nodes.some(node=>node.id===patch.source))||(patch.target&&!diagram.nodes.some(node=>node.id===patch.target))||(patch.source&&patch.target&&patch.source===patch.target))return diagram; if(Array.isArray(patch.labels))edge.labels=clone(patch.labels); Object.assign(edge,patch); if(patch.style)edge.style={...edge.style,...patch.style}; edge.waypoints=Array.isArray(edge.waypoints)?edge.waypoints.map(point=>({x:finite(point.x,0),y:finite(point.y,0)})):[]; diagram.layout.lastCommand='Edit connector'; return diagram; }
export function reverseEdge(value, id) { const diagram=normalizeDiagram(value),edge=diagram.edges.find(item=>item.id===id); if(!edge||edge.lock)return diagram; [edge.source,edge.target]=[edge.target,edge.source]; [edge.sourcePort,edge.targetPort]=[edge.targetPort,edge.sourcePort]; edge.waypoints=edge.waypoints.slice().reverse(); edge.labels=edge.labels.map(label=>({...label,position:label.position==='source'?'target':label.position==='target'?'source':label.position})); diagram.layout.lastCommand='Reverse connector'; return diagram; }
export function addWaypoint(value, id, point, index = null) { const diagram=normalizeDiagram(value),edge=diagram.edges.find(item=>item.id===id); if(!edge||edge.lock)return diagram; const valuePoint={x:finite(point?.x,0),y:finite(point?.y,0)}; if(index===null||index<0||index>edge.waypoints.length)edge.waypoints.push(valuePoint);else edge.waypoints.splice(index,0,valuePoint); diagram.layout.lastCommand='Add waypoint'; return diagram; }
export function moveWaypoint(value, id, index, point) { const diagram=normalizeDiagram(value),edge=diagram.edges.find(item=>item.id===id); if(!edge||edge.lock||!edge.waypoints[index])return diagram; edge.waypoints[index]={x:finite(point?.x,edge.waypoints[index].x),y:finite(point?.y,edge.waypoints[index].y)}; diagram.layout.lastCommand='Move waypoint'; return diagram; }
export function deleteWaypoint(value, id, index) { const diagram=normalizeDiagram(value),edge=diagram.edges.find(item=>item.id===id); if(!edge||edge.lock)return diagram; edge.waypoints.splice(index,1); diagram.layout.lastCommand='Delete waypoint'; return diagram; }
export function clearWaypoints(value, id) { return updateEdge(value,id,{waypoints:[]}); }

function selectionNodes(diagram, ids) { const selected=new Set(ids); return diagram.nodes.filter(node=>selected.has(node.id)&&!node.lock); }
export function duplicateNodes(value, ids = [], offset = {x:28,y:28}) { const diagram=normalizeDiagram(value),selected=selectionNodes(diagram,ids),taken=new Set(diagram.nodes.map(node=>node.id)),mapping=new Map(); selected.forEach(node=>mapping.set(node.id,uniqueId(`${node.id}-copy`,taken))); const copies=selected.map(node=>({...clone(node),id:mapping.get(node.id),x:node.x+finite(offset.x,28),y:node.y+finite(offset.y,28),pinned:false,lock:false})); diagram.nodes.push(...copies); const edgeTaken=new Set(diagram.edges.map(item=>item.id)); const internal=diagram.edges.filter(edge=>mapping.has(edge.source)&&mapping.has(edge.target)).map(edge=>({...clone(edge),id:uniqueId(`${edge.id}-copy`,edgeTaken),source:mapping.get(edge.source),target:mapping.get(edge.target),waypoints:[]})); diagram.edges.push(...internal); diagram.layout.lastCommand='Duplicate selection'; return {diagram,ids:copies.map(node=>node.id)}; }
export function groupNodes(value, ids = [], label = 'Group') { const diagram=normalizeDiagram(value),selected=selectionNodes(diagram,ids); if(selected.length<2)return {diagram,group:null}; const taken=new Set(diagram.groups.map(group=>group.id)),id=uniqueId('group',taken),padding=28,minX=Math.min(...selected.map(node=>node.x))-padding,minY=Math.min(...selected.map(node=>node.y))-padding,maxX=Math.max(...selected.map(node=>node.x+node.width))+padding,maxY=Math.max(...selected.map(node=>node.y+node.height))+padding; const group={id,label:clean(label)||'Group',nodeIds:selected.map(node=>node.id),x:minX,y:minY,width:maxX-minX,height:maxY-minY,style:{},layer:'base',lock:false}; diagram.groups.push(group); selected.forEach(node=>{node.parent=id;}); diagram.layout.lastCommand='Group selection'; return {diagram,group}; }
export function ungroupNodes(value, ids = []) { const diagram=normalizeDiagram(value),groups=diagram.groups.filter(group=>group.nodeIds.some(id=>ids.includes(id))||ids.includes(group.id)); const remove=new Set(groups.map(group=>group.id)); diagram.nodes.forEach(node=>{if(remove.has(node.parent))node.parent='';}); diagram.groups=diagram.groups.filter(group=>!remove.has(group.id)); diagram.layout.lastCommand='Ungroup selection'; return diagram; }
export function alignNodes(value, ids = [], mode = 'left') { const diagram=normalizeDiagram(value),selected=selectionNodes(diagram,ids); if(selected.length<2)return diagram; const x=Math.min(...selected.map(node=>node.x)),right=Math.max(...selected.map(node=>node.x+node.width)),y=Math.min(...selected.map(node=>node.y)),bottom=Math.max(...selected.map(node=>node.y+node.height)),cx=(x+right)/2,cy=(y+bottom)/2; selected.forEach(node=>{if(mode==='left')node.x=x;else if(mode==='center')node.x=cx-node.width/2;else if(mode==='right')node.x=right-node.width;else if(mode==='top')node.y=y;else if(mode==='middle')node.y=cy-node.height/2;else if(mode==='bottom')node.y=bottom-node.height;}); diagram.layout.lastCommand=`Align ${mode}`; return diagram; }
export function distributeNodes(value, ids = [], axis = 'horizontal') { const diagram=normalizeDiagram(value),selected=selectionNodes(diagram,ids).sort((a,b)=>axis==='horizontal'?a.x-b.x:b.y-a.y); if(selected.length<3)return diagram; const first=selected[0],last=selected.at(-1),span=axis==='horizontal'?(last.x+last.width-first.x):(last.y+last.height-first.y),total=selected.reduce((sum,node)=>sum+(axis==='horizontal'?node.width:node.height),0),gap=(span-total)/(selected.length-1); let cursor=axis==='horizontal'?first.x:first.y; selected.forEach(node=>{if(axis==='horizontal'){node.x=cursor;cursor+=node.width+gap;}else{node.y=cursor;cursor+=node.height+gap;}}); diagram.layout.lastCommand=`Distribute ${axis}`; return diagram; }
export function equalizeNodes(value, ids = [], mode = 'size') { const diagram=normalizeDiagram(value),selected=selectionNodes(diagram,ids); if(selected.length<2)return diagram; const width=selected[0].width,height=selected[0].height; selected.forEach(node=>{if(mode==='width'||mode==='size')node.width=width;if(mode==='height'||mode==='size')node.height=height;}); diagram.layout.lastCommand=`Equal ${mode}`; return diagram; }
export function moveContainer(value, id, delta = {x:0,y:0}) { const diagram=normalizeDiagram(value),group=diagram.groups.find(item=>item.id===id); if(!group||group.lock)return diagram; const dx=finite(delta.x,0),dy=finite(delta.y,0),members=new Set(group.nodeIds); group.x+=dx;group.y+=dy;diagram.nodes.forEach(node=>{if(members.has(node.id)&&!node.lock){node.x+=dx;node.y+=dy;}}); diagram.layout.lastCommand='Move container'; return diagram; }
export function selectConnected(value, id) { const diagram=normalizeDiagram(value),result=new Set([id]),changed=true; while(changed){changed=false;diagram.edges.forEach(edge=>{if(result.has(edge.source)&&!result.has(edge.target)){result.add(edge.target);changed=true;}if(result.has(edge.target)&&!result.has(edge.source)){result.add(edge.source);changed=true;}});} return [...result]; }
export function selectSameType(value, id) { const diagram=normalizeDiagram(value),node=diagram.nodes.find(item=>item.id===id); return node?diagram.nodes.filter(item=>item.shape===node.shape).map(item=>item.id):[]; }

export function addLane(value, input = {}) { const diagram=normalizeDiagram(value),taken=new Set(diagram.swimlanes.map(lane=>lane.id)),orientation=input.orientation==='vertical'?'vertical':'horizontal',index=diagram.swimlanes.length,id=uniqueId(input.id || `lane-${index+1}`,taken); const lane={id,label:clean(input.label)||`Lane ${index+1}`,orientation,x:finite(input.x,24),y:finite(input.y,24+index*160),width:Math.max(240,finite(input.width,1200)),height:Math.max(110,finite(input.height,140)),order:index,style:{},layer:'base',lock:false}; diagram.swimlanes.push(lane); diagram.layout.lastCommand='Add swimlane'; return {diagram,lane}; }
export function updateLane(value, id, patch = {}) { const diagram=normalizeDiagram(value),lane=diagram.swimlanes.find(item=>item.id===id); if(!lane||lane.lock)return diagram; Object.assign(lane,patch); lane.label=clean(lane.label)||'Lane'; diagram.layout.lastCommand='Edit swimlane'; return diagram; }
export function removeLane(value, id) { const diagram=normalizeDiagram(value),lane=diagram.swimlanes.find(item=>item.id===id); if(!lane||lane.lock)return diagram; diagram.swimlanes=diagram.swimlanes.filter(item=>item.id!==id);diagram.nodes.forEach(node=>{if(node.lane===id)node.lane='';});diagram.layout.lastCommand='Remove swimlane';return diagram; }
export function moveNodesToLane(value, ids = [], laneId = '') { const diagram=normalizeDiagram(value),lane=diagram.swimlanes.find(item=>item.id===laneId); if(!lane||lane.lock)return diagram; const selected=new Set(ids); diagram.nodes.forEach(node=>{if(selected.has(node.id)&&!node.lock){node.lane=lane.id;node.parent='';node.x=Math.max(lane.x+34,Math.min(node.x,lane.x+lane.width-node.width-24));node.y=Math.max(lane.y+34,Math.min(node.y,lane.y+lane.height-node.height-24));}}); diagram.layout.lastCommand='Move nodes to lane'; return diagram; }
export function flowToSwimlanes(value) { let diagram=normalizeDiagram(value); const byId=new Map(diagram.swimlanes.map(lane=>[lane.id,lane])); const metadata=node=>clean(node.owner||node.role||(byId.has(node.lane)?'':node.lane)); const labels=[...new Set(diagram.nodes.map(metadata).filter(Boolean))]; if(!labels.length)return diagram; const existing=new Map(diagram.swimlanes.map(lane=>[lane.label,lane])); labels.forEach((label,index)=>{if(!existing.has(label)){const result=addLane(diagram,{label,y:24+index*160});diagram=result.diagram;existing.set(label,result.lane);}}); diagram.nodes.forEach(node=>{const label=metadata(node);const lane=existing.get(label);if(lane&&!node.lock){node.lane=lane.id;node.x=Math.max(lane.x+34,Math.min(node.x,lane.x+lane.width-node.width-24));node.y=lane.y+34;}});diagram.layout.lastCommand='Create swimlanes from flow metadata';return diagram; }
export function reorderLane(value, id, direction = 1) { const diagram=normalizeDiagram(value),lane=diagram.swimlanes.find(item=>item.id===id); if(!lane)return diagram; const sorted=diagram.swimlanes.slice().sort((a,b)=>a.order-b.order),index=sorted.indexOf(lane),next=Math.max(0,Math.min(sorted.length-1,index+direction)); [sorted[index].order,sorted[next].order]=[sorted[next].order,sorted[index].order]; sorted.forEach((item,position)=>{item.order=position;}); diagram.swimlanes=sorted; diagram.layout.lastCommand='Reorder swimlane'; return diagram; }
export function addLayer(value, name = 'New layer') { const diagram=normalizeDiagram(value),taken=new Set(diagram.layers.map(layer=>layer.id)),id=uniqueId('layer',taken),layer={id,name:clean(name)||'New layer',visible:true,lock:false,order:diagram.layers.length}; diagram.layers.push(layer); diagram.layout.lastCommand='Add layer'; return {diagram,layer}; }
export function updateLayer(value, id, patch = {}) { const diagram=normalizeDiagram(value),layer=diagram.layers.find(item=>item.id===id); if(!layer)return diagram; Object.assign(layer,patch); layer.name=clean(layer.name)||'Layer'; diagram.layout.lastCommand='Edit layer'; return diagram; }
export function duplicateLayer(value, id) { const diagram=normalizeDiagram(value),source=diagram.layers.find(item=>item.id===id); if(!source)return {diagram,layer:null}; const taken=new Set(diagram.layers.map(layer=>layer.id)),newId=uniqueId(`${source.id}-copy`,taken),layer={...clone(source),id:newId,name:`${source.name} copy`,order:diagram.layers.length,lock:false,visible:true};diagram.layers.push(layer);diagram.nodes.forEach(node=>{if(node.layer===id)node.layer=newId;});diagram.edges.forEach(edge=>{if(edge.layer===id)edge.layer=newId;});diagram.layout.lastCommand='Duplicate layer';return {diagram,layer}; }
export function removeLayer(value, id) { const diagram=normalizeDiagram(value); if(id==='base')return diagram; if(!diagram.layers.some(layer=>layer.id===id))return diagram;diagram.layers=diagram.layers.filter(layer=>layer.id!==id);diagram.nodes.forEach(node=>{if(node.layer===id)node.layer='base';});diagram.edges.forEach(edge=>{if(edge.layer===id)edge.layer='base';});diagram.layout.lastCommand='Remove layer';return diagram; }
export function reorderLayer(value, id, direction = 1) { const diagram=normalizeDiagram(value),sorted=diagram.layers.slice().sort((a,b)=>a.order-b.order),index=sorted.findIndex(layer=>layer.id===id);if(index<0)return diagram;const next=Math.max(0,Math.min(sorted.length-1,index+direction));[sorted[index].order,sorted[next].order]=[sorted[next].order,sorted[index].order];sorted.forEach((layer,position)=>{layer.order=position;});diagram.layers=sorted;diagram.layout.lastCommand='Reorder layer';return diagram; }
export function moveSelectionToLayer(value, ids = [], layerId = 'base') { const diagram=normalizeDiagram(value),layer=diagram.layers.find(item=>item.id===layerId); if(!layer||layer.lock)return diagram; const selected=new Set(ids); diagram.nodes.forEach(node=>{if(selected.has(node.id)&&!node.lock)node.layer=layerId;}); diagram.edges.forEach(edge=>{if(selected.has(edge.source)&&selected.has(edge.target)&&!edge.lock)edge.layer=layerId;}); diagram.layout.lastCommand='Move selection to layer'; return diagram; }

export function pasteProcessSteps(value, text, options = {}) { const lines=String(text||'').split(/\r?\n/).map(clean).filter(Boolean); const labels=lines.filter(line=>!/^step\s*$/i.test(line)); let diagram=normalizeDiagram(value); const ids=[]; labels.forEach((label,index)=>{const result=addNode(diagram,{label,shape:index===0?'start':index===labels.length-1?'end':'process',x:64+index*236,y:64});diagram=result.diagram;ids.push(result.node.id);}); ids.slice(0,-1).forEach((source,index)=>{diagram=addEdge(diagram,source,ids[index+1],{label:options.edgeLabel||''});}); diagram.layout.lastCommand='Paste process steps'; return {diagram,ids}; }
export function parseSourceTargetTable(text) { const rows=String(text||'').split(/\r?\n/).map(row=>row.split(/\t|,/).map(clean)).filter(row=>row.length>=2&&row[0]&&row[1]); const header=/^(source|from)$/i.test(rows[0]?.[0]||'')&&/^(target|to)$/i.test(rows[0]?.[1]||'')?rows.shift():null; void header; return rows.map(row=>({source:row[0],target:row[1],label:row[2]||''})); }
export function pasteSourceTargetTable(value, text, options = {}) { const rows=parseSourceTargetTable(text); let diagram=normalizeDiagram(value); const byLabel=new Map(diagram.nodes.map(node=>[node.label,node.id])); const ids=[]; rows.forEach(row=>{for(const label of [row.source,row.target])if(!byLabel.has(label)){const result=addNode(diagram,{label,shape:'process',x:64+byLabel.size*236,y:64+(byLabel.size%3)*132});diagram=result.diagram;byLabel.set(label,result.node.id);ids.push(result.node.id);}}); rows.forEach(row=>{diagram=addEdge(diagram,byLabel.get(row.source),byLabel.get(row.target),{label:row.label});}); diagram.layout.lastCommand='Paste source target graph'; if(options.clean)diagram=cleanDiagram(diagram); return {diagram,ids:[...new Set(ids)]}; }
function freeNodePosition(diagram, proposed, size) { let x=finite(proposed.x,64),y=finite(proposed.y,64),attempts=0; while(attempts<diagram.nodes.length+2&&diagram.nodes.some(node=>rectsOverlap({x,y,w:size.width,h:size.height},nodeRect(node),12))){y+=size.height+36;attempts+=1;if(y>1200){x+=size.width+48;y=64;}} return {x,y}; }
export function quickBranch(value, sourceId, input = {}) { let diagram=normalizeDiagram(value); const source=diagram.nodes.find(node=>node.id===sourceId); if(!source)return {diagram,node:null}; const shape=shapeDefinition(input.shape||'process'),position=freeNodePosition(diagram,{x:source.x+source.width+96,y:source.y},{width:shape.width,height:shape.height}); const result=addNode(diagram,{label:input.label||'New step',shape:shape.id,x:position.x,y:position.y}); diagram=result.diagram; const edge=addEdge(diagram,sourceId,result.node.id,{label:input.edgeLabel||''}); return {diagram:edge,node:result.node}; }
export function insertNodeOnEdge(value, edgeId, input = {}) { let diagram=normalizeDiagram(value); const edge=diagram.edges.find(item=>item.id===edgeId); if(!edge)return {diagram,node:null}; const source=diagram.nodes.find(node=>node.id===edge.source),target=diagram.nodes.find(node=>node.id===edge.target); if(!source||!target)return {diagram,node:null}; const shape=shapeDefinition(input.shape||'process'),position=freeNodePosition(diagram,{x:(source.x+target.x)/2,y:(source.y+target.y)/2},{width:shape.width,height:shape.height}); const result=addNode(diagram,{label:input.label||'Inserted step',shape:shape.id,x:position.x,y:position.y}); diagram=result.diagram; diagram.edges=diagram.edges.filter(item=>item.id!==edgeId); diagram=addEdge(diagram,edge.source,result.node.id,{label:edge.labels?.[0]?.text||''}); diagram=addEdge(diagram,result.node.id,edge.target,{label:edge.labels?.[0]?.text||''}); return {diagram,node:result.node}; }

export function createSubflow(value, ids = [], name = 'Subflow') { const diagram=normalizeDiagram(value),selected=new Set(ids),nodes=diagram.nodes.filter(node=>selected.has(node.id)).map(node=>clone(node)),edges=diagram.edges.filter(edge=>selected.has(edge.source)&&selected.has(edge.target)).map(edge=>clone(edge)); return {schema:DIAGRAM_SCHEMA,version:DIAGRAM_VERSION,name:clean(name)||'Subflow',nodes,edges,created_at:new Date().toISOString()}; }
export function insertSubflow(value, subflow, origin = {x:64,y:64}) { let diagram=normalizeDiagram(value); if(!subflow||!Array.isArray(subflow.nodes))return {diagram,ids:[]}; const taken=new Set(diagram.nodes.map(node=>node.id)),mapping=new Map(),minX=Math.min(...subflow.nodes.map(node=>node.x),0),minY=Math.min(...subflow.nodes.map(node=>node.y),0); const ids=[]; subflow.nodes.forEach(node=>{const id=uniqueId(`${idPart(subflow.name||'subflow')}-${node.id}`,taken);mapping.set(node.id,id);const result=addNode(diagram,{...clone(node),id,x:finite(origin.x,64)+node.x-minX,y:finite(origin.y,64)+node.y-minY,lock:false,pinned:false});diagram=result.diagram;ids.push(result.node.id);}); subflow.edges?.forEach(edge=>{if(mapping.has(edge.source)&&mapping.has(edge.target))diagram=addEdge(diagram,mapping.get(edge.source),mapping.get(edge.target),clone(edge));}); diagram.layout.lastCommand='Insert subflow'; return {diagram,ids}; }

export function diagramSummary(value) { const diagram=normalizeDiagram(value); return `${diagram.nodes.length} nodes · ${diagram.edges.length} connectors · ${diagram.swimlanes.length} lanes · ${diagram.layers.length} layers`; }

const svgEscape=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
function staticPath(points,routing) {
  if(!points.length)return '';
  if(routing==='curved'&&points.length>2)return `M${points[0].x} ${points[0].y} Q${points[1].x} ${points[1].y} ${points.at(-1).x} ${points.at(-1).y}`;
  return `M${points.map(point=>`${point.x} ${point.y}`).join(' L')}`;
}
function staticPoint(points,fraction=.5) {
  if(points.length<2)return points[0]||{x:0,y:0};
  const lengths=points.slice(1).map((point,index)=>Math.hypot(point.x-points[index].x,point.y-points[index].y)),total=lengths.reduce((sum,value)=>sum+value,0),target=total*fraction;
  let traversed=0;for(let index=0;index<lengths.length;index+=1){if(traversed+lengths[index]>=target){const ratio=(target-traversed)/Math.max(1,lengths[index]),start=points[index],end=points[index+1];return {x:start.x+(end.x-start.x)*ratio,y:start.y+(end.y-start.y)*ratio};}traversed+=lengths[index];}
  return points.at(-1);
}
export function renderDiagramSvg(value={},options={}) {
  const diagram=value?.engine?diagramFromEntry(value):normalizeDiagram(value),visibleLayers=new Set(diagram.layers.filter(layer=>layer.visible!==false).map(layer=>layer.id)),nodes=diagram.nodes.filter(node=>visibleLayers.has(node.layer)),nodeIds=new Set(nodes.map(node=>node.id));
  const all=[...nodes.map(nodeRect),...diagram.swimlanes.filter(lane=>visibleLayers.has(lane.layer)).map(nodeRect),...diagram.groups.filter(group=>visibleLayers.has(group.layer)).map(nodeRect)];
  const minX=all.length?Math.min(...all.map(rect=>rect.x))-28:0,minY=all.length?Math.min(...all.map(rect=>rect.y))-28:0,maxX=all.length?Math.max(...all.map(rect=>rect.x+rect.w))+28:640,maxY=all.length?Math.max(...all.map(rect=>rect.y+rect.h))+28:360,width=Math.max(1,maxX-minX),height=Math.max(1,maxY-minY);
  const lanes=diagram.swimlanes.filter(lane=>visibleLayers.has(lane.layer)).map(lane=>`<g class="diagram-static-lane"><rect x="${lane.x}" y="${lane.y}" width="${lane.width}" height="${lane.height}" rx="10"/><text x="${lane.x+14}" y="${lane.y+22}">${svgEscape(lane.label)}</text></g>`).join('');
  const groups=diagram.groups.filter(group=>visibleLayers.has(group.layer)).map(group=>`<g class="diagram-static-group"><rect x="${group.x}" y="${group.y}" width="${group.width}" height="${group.height}" rx="10"/><text x="${group.x+12}" y="${group.y+20}">${svgEscape(group.label)}</text></g>`).join('');
  const edges=diagram.edges.filter(edge=>visibleLayers.has(edge.layer)&&nodeIds.has(edge.source)&&nodeIds.has(edge.target)).map(edge=>{const points=routeEdge(diagram,edge),dash=edge.style.line==='dashed'?' stroke-dasharray="8 5"':edge.style.line==='dotted'?' stroke-dasharray="2 5"':'';const labels=(edge.labels||[]).map((label,index)=>{const fraction=label.position==='source'?.25:label.position==='target'?.75:.5,point=staticPoint(points,fraction);return `<text class="diagram-edge-label" data-edge-label="${svgEscape(label.id||index)}" x="${point.x+finite(label.offset,0)}" y="${point.y-7-index*14}" text-anchor="middle">${svgEscape(label.text)}</text>`;}).join('');return `<g data-diagram-edge="${svgEscape(edge.id)}"><path d="${staticPath(points,edge.routing)}" stroke="${svgEscape(edge.style.color||'currentColor')}" stroke-width="${edge.style.width}" fill="none" marker-end="${edge.endMarker==='none'?'':'url(#diagram-static-arrow)'}"${dash}/>${labels}</g>`;}).join('');
  const nodeMarkup=nodes.map((node,index)=>{const shape=node.shape==='decision'?`<path d="M${node.x+node.width/2} ${node.y}L${node.x+node.width} ${node.y+node.height/2}L${node.x+node.width/2} ${node.y+node.height}L${node.x} ${node.y+node.height/2}Z"/>`:`<rect x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="${['start','end'].includes(node.shape)?node.height/2:9}"/>`;return `<g data-diagram-node="${svgEscape(node.id)}" data-shape="${svgEscape(node.shape)}">${shape}<text data-direct="diagram-node:${index}" x="${node.x+node.width/2}" y="${node.y+node.height/2+(node.secondary?-6:4)}" text-anchor="middle">${svgEscape(node.label)}</text>${node.secondary?`<text class="diagram-node-secondary" x="${node.x+node.width/2}" y="${node.y+node.height/2+13}" text-anchor="middle">${svgEscape(node.secondary)}</text>`:''}</g>`;}).join('');
  return `<svg class="diagram-svg flow-svg diagram-studio-static" data-graph-plan="canonical-${nodes.length}-${diagram.edges.length}" data-diagram-nodes="${nodes.length}" data-diagram-edges="${diagram.edges.length}" data-direction="${diagram.layout.direction}" viewBox="${minX} ${minY} ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${svgEscape(options.label||diagramSummary(diagram))}" xmlns="http://www.w3.org/2000/svg"><defs><marker id="diagram-static-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker></defs>${lanes}${groups}${edges}${nodeMarkup}</svg>`;
}
