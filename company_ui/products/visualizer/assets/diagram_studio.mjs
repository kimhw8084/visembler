import {
  DIAGRAM_SCHEMA,
  SHAPE_CATALOG,
  addEdge,
  addLane,
  addLayer,
  addNode,
  addWaypoint,
  alignNodes,
  autoLayout,
  cleanDiagram,
  clearWaypoints,
  createSubflow,
  diagramBounds,
  diagramFromEntry,
  diagramSummary,
  diagramToEntry,
  distributeNodes,
  duplicateNodes,
  duplicateLayer,
  equalizeNodes,
  flowToSwimlanes,
  groupNodes,
  insertNodeOnEdge,
  insertSubflow,
  moveNodesToLane,
  moveContainer,
  moveSelectionToLayer,
  moveWaypoint as moveWaypointModel,
  normalizeDiagram,
  pasteProcessSteps,
  pasteSourceTargetTable,
  quickBranch,
  removeNodes,
  reorderLane,
  reorderLayer,
  removeLane,
  removeLayer,
  reverseEdge,
  routeEdge,
  selectConnected,
  selectSameType,
  ungroupNodes,
  updateEdge,
  updateLane,
  updateLayer,
  updateNode,
  deleteWaypoint,
} from './authoring_diagram_studio.mjs';

const boot = window.__CUI_DIAGRAM_STUDIO_BOOTSTRAP__ || {};
const root = document.querySelector('#diagram-studio');
const $ = (selector, host = document) => host.querySelector(selector);
const $$ = (selector, host = document) => [...host.querySelectorAll(selector)];
const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const clean = value => String(value ?? '').trim();
const escapeHtml = value => clean(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const uid = prefix => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;

const state = {
  diagram: diagramFromEntry(boot.entry || {}),
  selectedNodes: new Set(),
  selectedEdges: new Set(),
  undo: [],
  redo: [],
  clipboard: null,
  subflows: [],
  dirty: false,
  pending: null,
  revision: Number.isInteger(boot.revision) ? boot.revision : 1,
  zoom: 1,
  grid: true,
  snap: true,
  preview: false,
  drag: null,
  resize: null,
  lasso: null,
  connect: null,
  waypoint: null,
  routeDrag: null,
  labelDrag: null,
  groupDrag: null,
  pointerSelectedNode: null,
};

function hash(value) {
  const text = JSON.stringify(value);
  let result = 2166136261;
  for (let index = 0; index < text.length; index += 1) result = Math.imul(result ^ text.charCodeAt(index), 16777619);
  return (result >>> 0).toString(16).padStart(8, '0');
}
function activeNode() { return state.selectedNodes.size === 1 ? state.diagram.nodes.find(node => state.selectedNodes.has(node.id)) : null; }
function activeEdge() { return state.selectedEdges.size === 1 ? state.diagram.edges.find(edge => state.selectedEdges.has(edge.id)) : null; }
function selectedIds() { return [...state.selectedNodes]; }
function selectedObjectCount() { return state.selectedNodes.size + state.selectedEdges.size; }
function notify(message, kind = 'info') { const node = $('#ds-save-status'); if (node) { node.textContent = message; node.dataset.kind = kind; } }
function svgPoint(event) {
  const svg = $('#ds-canvas'); const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY; const matrix = svg.getScreenCTM(); return matrix ? point.matrixTransform(matrix.inverse()) : {x:event.offsetX,y:event.offsetY};
}
function snapPoint(point) { if (!state.snap) return point; return {x:Math.round(point.x / 12) * 12,y:Math.round(point.y / 12) * 12}; }
function selectedLayerLocked() { return selectedIds().some(id => { const node = state.diagram.nodes.find(item => item.id === id); const layer = state.diagram.layers.find(item => item.id === node?.layer); return layer?.lock; }); }

function reportModel() {
  const model = clone(boot.model || {}); const items = Array.isArray(model.items) ? model.items : []; const index = items.findIndex(item => item?.id === boot.element_id);
  if (index < 0) throw new Error('The selected diagram element is no longer in this report.');
  items[index] = diagramToEntry(items[index], state.diagram); model.items = items; return model;
}
function sendBridge(type, payload) {
  root.dispatchEvent(new CustomEvent('visualizer_bridge', {bubbles:true, detail:JSON.stringify({bridge_version:1,type,payload})}));
}
function persist() {
  if (state.pending) return notify('Save already in progress');
  try {
    const commitId = uid('diagram-commit'); state.pending = commitId; notify('Saving…');
    sendBridge('report.commit', {report_id:boot.report_id,base_revision:state.revision,model:reportModel(),commit_id:commitId});
  } catch (error) { state.pending = null; notify(error.message || 'Save failed','error'); }
}
function goBack() {
  if (state.dirty) { persist(); state.returnAfterSave = true; return; }
  window.location.assign(`/visualizer?report=${encodeURIComponent(boot.report_id || '')}`);
}
window.CompanyUIDiagramStudio = {
  state: () => ({report_id:boot.report_id,revision:state.revision,dirty:state.dirty,pending:!!state.pending,model:clone(state.diagram),selected_nodes:selectedIds(),selected_edges:[...state.selectedEdges]}),
  diagram: () => clone(state.diagram),
  hash: () => hash(state.diagram),
  command: (name, ...args) => execute(name, ...args),
};
window.CompanyUIDiagramStudio.receive = message => {
  const value = typeof message === 'string' ? JSON.parse(message) : message; const payload = value?.payload || {};
  if (value?.type === 'report.commit_result' && payload.commit_id === state.pending) { state.revision = payload.revision; state.pending = null; state.dirty = false; notify(`Saved · revision ${state.revision}`,'success'); if (state.returnAfterSave) { state.returnAfterSave = false; window.location.assign(`/visualizer?report=${encodeURIComponent(boot.report_id || '')}`); } }
  if (value?.type === 'report.error' && (!payload.commit_id || payload.commit_id === state.pending)) { state.pending = null; notify(payload.message || 'Save rejected','error'); }
};

function applyMutation(label, producer) {
  if (state.pending) { notify('Finish saving before making another change'); return false; }
  const before = clone(state.diagram); let next;
  try { next = normalizeDiagram(producer(clone(state.diagram))); } catch (error) { notify(error.message || 'Command failed','error'); return false; }
  state.undo.push({label,before,after:clone(next)}); state.redo = []; state.diagram = next; state.dirty = true; render(); notify(`${label} · unsaved`); return true;
}
function undo() { const command = state.undo.pop(); if (!command) return notify('Nothing to undo'); state.redo.push(command); state.diagram = clone(command.before); render(); state.dirty = true; notify(`Undid ${command.label} · unsaved`); }
function redo() { const command = state.redo.pop(); if (!command) return notify('Nothing to redo'); state.undo.push(command); state.diagram = clone(command.after); render(); state.dirty = true; notify(`Redid ${command.label} · unsaved`); }
function selectNode(id, additive = false) { if (!additive) { state.selectedNodes.clear(); state.selectedEdges.clear(); } if (additive && state.selectedNodes.has(id)) state.selectedNodes.delete(id); else state.selectedNodes.add(id); renderInspector(); renderCanvas(); }
function selectEdge(id, additive = false) { if (!additive) state.selectedNodes.clear(); if (additive && state.selectedEdges.has(id)) state.selectedEdges.delete(id); else state.selectedEdges.add(id); renderInspector(); renderCanvas(); }
function clearSelection() { state.selectedNodes.clear(); state.selectedEdges.clear(); renderInspector(); renderCanvas(); }

function pointOnPolyline(points, fraction = .5) {
  if (!points.length) return {x:0,y:0}; const lengths=[];let total=0;
  for(let index=1;index<points.length;index+=1){const length=Math.hypot(points[index].x-points[index-1].x,points[index].y-points[index-1].y);lengths.push(length);total+=length;}
  let target=total*fraction;for(let index=1;index<points.length;index+=1){const length=lengths[index-1];if(target<=length){const ratio=length?target/length:0;return {x:points[index-1].x+(points[index].x-points[index-1].x)*ratio,y:points[index-1].y+(points[index].y-points[index-1].y)*ratio};}target-=length;}return points.at(-1);
}
function pathData(points) { return points.map((point,index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' '); }
function shapeMarkup(node) {
  const w=node.width,h=node.height,rx=12;
  if(node.shape==='decision') return `<path d="M ${w/2} 2 L ${w-2} ${h/2} L ${w/2} ${h-2} L 2 ${h/2} Z"/>`;
  if(node.shape==='note') return `<path d="M 2 2 H ${w-18} L ${w-2} 18 V ${h-2} H 2 Z"/>`;
  if(node.shape==='data') return `<path d="M 2 2 H ${w-20} L ${w-2} ${h/2} L ${w-20} ${h-2} H 2 L 20 ${h/2} Z"/>`;
  if(node.shape==='database') return `<path d="M 2 14 Q ${w/2} -2 ${w-2} 14 V ${h-12} Q ${w/2} ${h+2} 2 ${h-12} Z M 2 14 Q ${w/2} 29 ${w-2} 14"/>`;
  return `<rect x="1.5" y="1.5" width="${w-3}" height="${h-3}" rx="${node.shape==='start'||node.shape==='end'||node.shape==='hold'||node.shape==='release'?h/2:rx}"/>`;
}
function labelY(node) { return node.secondary || node.status ? node.height/2-7 : node.height/2+5; }
function renderNode(node) {
  const selected=state.selectedNodes.has(node.id), label=escapeHtml(node.label), secondary=escapeHtml(node.secondary),status=escapeHtml(node.status); const ports=node.ports||[],style=node.style||{},shapeStyle=[style.fill?`fill:${escapeHtml(style.fill)}`:'',style.border?`stroke:${escapeHtml(style.border)}`:'',style.borderWidth?`stroke-width:${Math.max(1,Number(style.borderWidth)||1)}`:''].filter(Boolean).join(';');
  const shape=shapeMarkup(node).replace(/^<(rect|path)/,`<$1${shapeStyle?` style="${shapeStyle}"`:''}`);
  return `<g class="ds-node ${selected?'is-selected ':''}${node.lock?'is-locked ':''}" transform="translate(${node.x} ${node.y})" data-node-id="${escapeHtml(node.id)}" data-shape="${escapeHtml(node.shape)}" role="button" tabindex="0" aria-label="${label}${secondary?` · ${secondary}`:''}${status?` · ${status}`:''}${node.lock?' · locked':''}">${shape}<text class="ds-node-label" x="${node.width/2}" y="${labelY(node)}"${style.text?` fill="${escapeHtml(style.text)}"`:''}>${label}</text>${secondary?`<text class="ds-node-secondary" x="${node.width/2}" y="${node.height/2+9}">${secondary}</text>`:''}${status?`<text class="ds-node-status" x="${node.width/2}" y="${node.height-10}">${status}</text>`:''}${selected?ports.map(port=>`<circle class="ds-port" data-port="${escapeHtml(port.id)}" cx="${port.x*node.width}" cy="${port.y*node.height}" r="6" aria-label="Connect from ${label} ${escapeHtml(port.id)}"></circle>`).join(''):''}${selected?`<rect class="ds-resize-handle" data-resize="${escapeHtml(node.id)}" x="${node.width-9}" y="${node.height-9}" width="12" height="12" rx="2"/>`:''}</g>`;
}
function edgeLabelMarkup(edge, points) {
  return (edge.labels||[]).map((label,index)=>{const fraction=label.position==='source' ? .25 : label.position==='target' ? .75 : .5;const point=pointOnPolyline(points,fraction);return `<text class="ds-edge-label" data-label-id="${escapeHtml(label.id||`${edge.id}-${index}`)}" data-edge-label-index="${index}" x="${point.x+finiteOffset(label.offset,0)}" y="${point.y-7-index*15}" text-anchor="middle">${escapeHtml(label.text)}</text>`;}).join('');
}
function finiteOffset(value,fallback) { return Number.isFinite(Number(value)) ? Number(value) : fallback; }
function renderCanvas() {
  const svg=$('#ds-canvas'),scene=$('#ds-scene'),bounds=diagramBounds(state.diagram); if(!svg||!scene)return;
  const width=Math.max(900,bounds.x+bounds.w+40),height=Math.max(560,bounds.y+bounds.h+40); svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.style.width=`${width}px`;svg.style.height=`${height}px`;svg.dataset.grid=state.grid?'on':'off';
  const visibleLayer=id=>state.diagram.layers.find(layer=>layer.id===id)?.visible!==false;
  const visibleNodes=state.diagram.nodes.filter(node=>visibleLayer(node.layer));
  const visibleNodeIds=new Set(visibleNodes.map(node=>node.id));
  const lanes=state.diagram.swimlanes.slice().sort((a,b)=>a.order-b.order).filter(lane=>visibleLayer(lane.layer)).map(lane=>`<g class="ds-lane" data-lane-id="${escapeHtml(lane.id)}"><rect x="${lane.x}" y="${lane.y}" width="${lane.width}" height="${lane.height}" rx="10"/><text class="ds-lane-label" x="${lane.x+16}" y="${lane.y+24}">${escapeHtml(lane.label)}</text></g>`).join('');
  const groups=state.diagram.groups.filter(group=>visibleLayer(group.layer)).map(group=>`<g class="ds-group" data-group-id="${escapeHtml(group.id)}"><rect x="${group.x}" y="${group.y}" width="${group.width}" height="${group.height}" rx="12"/><text class="ds-group-label" x="${group.x+14}" y="${group.y+20}">${escapeHtml(group.label)}</text></g>`).join('');
  const edges=state.diagram.edges.filter(edge=>visibleLayer(edge.layer)&&visibleNodeIds.has(edge.source)&&visibleNodeIds.has(edge.target)).map(edge=>{const points=routeEdge(state.diagram,edge),selected=state.selectedEdges.has(edge.id),dash=edge.style.line==='dashed'?' stroke-dasharray="8 5"':edge.style.line==='dotted'?' stroke-dasharray="2 5"':'';const marker=value=>value==='none'?'':value==='open'?'url(#ds-arrow-open)':'url(#ds-arrow)';return `<g class="ds-edge-group" data-edge-id="${escapeHtml(edge.id)}" role="group" aria-label="${escapeHtml(edgeDescription(edge))}"><path class="ds-edge ${selected?'is-selected ':''}${edge.lock?'is-locked ':''}" d="${pathData(points)}" stroke="${escapeHtml(edge.style.color||'')||'currentColor'}" stroke-width="${edge.style.width}" marker-start="${marker(edge.startMarker)}" marker-end="${marker(edge.endMarker)}"${dash}/>${edgeLabelMarkup(edge,points)}${selected?edge.waypoints.map((point,index)=>`<circle class="ds-waypoint" data-edge-id="${escapeHtml(edge.id)}" data-waypoint-index="${index}" cx="${point.x}" cy="${point.y}" r="6" fill="white" stroke="currentColor"/>`).join(''):''}</g>`;}).join('');
  const nodes=visibleNodes.map(renderNode).join(''); const preview=state.connect?`<path class="ds-connection-preview" d="M ${state.connect.start.x} ${state.connect.start.y} L ${state.connect.current.x} ${state.connect.current.y}"/>`:''; const routeGhost=state.routeDrag?`<circle class="ds-route-ghost" cx="${state.routeDrag.point.x}" cy="${state.routeDrag.point.y}" r="7"/>`:'';
  scene.innerHTML=lanes+groups+edges+nodes+preview+routeGhost;$('#ds-empty').hidden=state.diagram.nodes.length>0;$('#ds-diagram-summary').textContent=diagramSummary(state.diagram);$('#ds-layout-note').textContent=state.diagram.layout.lastCommand||'Ready';$('#ds-selection-summary').textContent=`${selectedObjectCount()} selected`;
  renderMinimap(bounds); renderLasso();
}
function edgeDescription(edge) { const source=state.diagram.nodes.find(node=>node.id===edge.source)?.label||edge.source;const target=state.diagram.nodes.find(node=>node.id===edge.target)?.label||edge.target;const label=edge.labels?.map(item=>item.text).filter(Boolean).join(', ');return `${source} to ${target}${label?` · ${label}`:''}`; }
function renderMinimap(bounds) { const host=$('#ds-minimap');if(!host)return;const sx=148/bounds.w,sy=88/bounds.h;const visible=id=>state.diagram.layers.find(layer=>layer.id===id)?.visible!==false;host.innerHTML=`<svg viewBox="0 0 160 100" aria-hidden="true">${state.diagram.nodes.filter(node=>visible(node.layer)).map(node=>{const r={x:(node.x-bounds.x)*sx+6,y:(node.y-bounds.y)*sy+6,w:Math.max(3,node.width*sx),h:Math.max(2,node.height*sy)};return `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}"/>`;}).join('')}</svg>`;}
function renderLasso() { const node=$('#ds-lasso');if(!node)return;if(!state.lasso){node.hidden=true;return;}node.hidden=false;node.setAttribute('x',state.lasso.x);node.setAttribute('y',state.lasso.y);node.setAttribute('width',state.lasso.width);node.setAttribute('height',state.lasso.height); }

function inputField(label, key, value, type='text') { return `<label class="ds-field"><span>${label}</span><input data-inspect="${key}" type="${type}" value="${escapeHtml(value)}"></label>`; }
function renderInspector() {
  const host=$('#ds-inspector-body'); if(!host)return; const node=activeNode(),edge=activeEdge();
  if(node){host.innerHTML=`<section class="ds-inspector-section"><h3>Node semantics</h3>${inputField('Label','label',node.label)}${inputField('Secondary text','secondary',node.secondary)}<label class="ds-field"><span>Shape</span><select data-inspect="shape">${SHAPE_CATALOG.map(shape=>`<option value="${shape.id}" ${shape.id===node.shape?'selected':''}>${escapeHtml(shape.label)}</option>`).join('')}</select></label>${inputField('Status','status',node.status)}${inputField('Semantic / icon type','semantic',node.semantic)}${inputField('Role / owner','role',node.role||node.owner||'')}</section><section class="ds-inspector-section"><h3>Appearance</h3><div class="ds-inspector-grid">${inputField('Fill','style.fill',node.style.fill||'')}${inputField('Border','style.border',node.style.border||'')}${inputField('Text','style.text',node.style.text||'')}${inputField('Border width','style.borderWidth',node.style.borderWidth||1,'number')}</div></section><section class="ds-inspector-section"><h3>Geometry and ownership</h3><div class="ds-inspector-grid">${inputField('X','x',Math.round(node.x),'number')}${inputField('Y','y',Math.round(node.y),'number')}${inputField('Width','width',Math.round(node.width),'number')}${inputField('Height','height',Math.round(node.height),'number')}</div><label class="ds-check"><input data-inspect="pinned" type="checkbox" ${node.pinned?'checked':''}> Preserve this position during layout</label><label class="ds-check"><input data-inspect="lock" type="checkbox" ${node.lock?'checked':''}> Lock node</label></section><section class="ds-inspector-section"><h3>Relationships</h3><div class="ds-action-grid"><button class="ds-button" data-action="select-connected">Select connected</button><button class="ds-button" data-action="select-same-type">Select same type</button></div>${laneOptions(node)}${layerOptions(node)}</section>`;return;}
  if(edge){host.innerHTML=`<section class="ds-inspector-section"><h3>Connector</h3><div class="ds-inspector-grid"><label class="ds-field"><span>Source node</span><select data-edge-inspect="source">${nodeOptions(edge.source)}</select></label><label class="ds-field"><span>Target node</span><select data-edge-inspect="target">${nodeOptions(edge.target)}</select></label></div><div class="ds-field"><span>Route</span><select data-edge-inspect="routing"><option value="orthogonal" ${edge.routing==='orthogonal'?'selected':''}>Orthogonal</option><option value="straight" ${edge.routing==='straight'?'selected':''}>Straight</option><option value="curved" ${edge.routing==='curved'?'selected':''}>Curved</option></select></div><div class="ds-inspector-grid"><label class="ds-field"><span>Source port</span><select data-edge-inspect="sourcePort">${portOptions(edge.sourcePort)}</select></label><label class="ds-field"><span>Target port</span><select data-edge-inspect="targetPort">${portOptions(edge.targetPort)}</select></label></div><div class="ds-inspector-grid"><label class="ds-field"><span>Start marker</span><select data-edge-inspect="startMarker">${markerOptions(edge.startMarker)}</select></label><label class="ds-field"><span>End marker</span><select data-edge-inspect="endMarker">${markerOptions(edge.endMarker)}</select></label></div><label class="ds-field"><span>Line color</span><input data-edge-inspect="color" value="${escapeHtml(edge.style.color)}" placeholder="#526b88"></label><div class="ds-inspector-grid"><label class="ds-field"><span>Line width</span><input data-edge-inspect="width" type="number" min="1" step="1" value="${edge.style.width}"></label><label class="ds-field"><span>Line style</span><select data-edge-inspect="line"><option value="solid" ${edge.style.line==='solid'?'selected':''}>Solid</option><option value="dashed" ${edge.style.line==='dashed'?'selected':''}>Dashed</option><option value="dotted" ${edge.style.line==='dotted'?'selected':''}>Dotted</option></select></label></div><label class="ds-check"><input data-edge-inspect="lock" type="checkbox" ${edge.lock?'checked':''}> Lock connector</label></section><section class="ds-inspector-section"><h3>Labels</h3>${(edge.labels||[]).map((label,index)=>`<div class="ds-inspector-grid"><label class="ds-field"><span>Label ${index+1}</span><input data-edge-label="${index}" value="${escapeHtml(label.text)}"></label><label class="ds-field"><span>Position</span><select data-edge-position="${index}"><option value="source" ${label.position==='source'?'selected':''}>Source side</option><option value="center" ${label.position==='center'?'selected':''}>Center</option><option value="target" ${label.position==='target'?'selected':''}>Target side</option></select></label></div>`).join('')}<div class="ds-action-grid"><button class="ds-button" data-action="add-edge-label">Add label</button><button class="ds-button" data-action="reverse">Reverse direction</button></div></section><section class="ds-inspector-section"><h3>Waypoints</h3><div class="ds-action-grid"><button class="ds-button" data-action="add-waypoint">Add waypoint</button><button class="ds-button" data-action="clear-waypoints">Clear route</button><button class="ds-button" data-action="delete-waypoint">Delete last waypoint</button></div><small>Drag the visible route points to tune a connector. Clean Diagram clears unnecessary manual bends.</small></section>`;return;}
  host.innerHTML='<div class="ds-inspector-empty">Select a node or connector to edit its semantic and visual properties. Shift-click adds to the selection; drag empty canvas for a lasso.</div>';
}
function portOptions(value) { return ['floating','top','right','bottom','left'].map(port=>`<option value="${port}" ${value===port?'selected':''}>${port[0].toUpperCase()+port.slice(1)}</option>`).join(''); }
function nodeOptions(value) { return state.diagram.nodes.map(node=>`<option value="${escapeHtml(node.id)}" ${node.id===value?'selected':''}>${escapeHtml(node.label)}</option>`).join(''); }
function markerOptions(value) { return ['none','arrow','open'].map(marker=>`<option value="${marker}" ${value===marker?'selected':''}>${marker[0].toUpperCase()+marker.slice(1)}</option>`).join(''); }
function laneOptions(node) { return `<label class="ds-field"><span>Swimlane</span><select data-inspect="lane"><option value="">No lane</option>${state.diagram.swimlanes.map(lane=>`<option value="${lane.id}" ${node.lane===lane.id?'selected':''}>${escapeHtml(lane.label)}</option>`).join('')}</select></label>`; }
function layerOptions(node) { return `<label class="ds-field"><span>Layer</span><select data-inspect="layer">${state.diagram.layers.map(layer=>`<option value="${layer.id}" ${node.layer===layer.id?'selected':''}>${escapeHtml(layer.name)}${layer.visible?'':' · hidden'}</option>`).join('')}</select></label>`; }
function renderManagers() {
  const layers=$('#ds-layer-list'),lanes=$('#ds-lane-list'); if(layers)layers.innerHTML=state.diagram.layers.slice().sort((a,b)=>a.order-b.order).map(layer=>`<div class="ds-layer-row ${selectedIds().some(id=>state.diagram.nodes.find(node=>node.id===id)?.layer===layer.id)?'is-active':''}"><span>${escapeHtml(layer.name)}${layer.visible?'':' · hidden'}${layer.lock?' · locked':''}</span><span class="ds-row-actions"><button data-layer-action="select" data-layer-id="${layer.id}" type="button">Select</button><button data-layer-action="visibility" data-layer-id="${layer.id}" type="button">${layer.visible?'Hide':'Show'}</button><button data-layer-action="lock" data-layer-id="${layer.id}" type="button">${layer.lock?'Unlock':'Lock'}</button><button data-layer-action="rename" data-layer-id="${layer.id}" type="button" aria-label="Rename ${escapeHtml(layer.name)}">Rename</button><button data-layer-action="duplicate" data-layer-id="${layer.id}" type="button">Copy</button>${layer.id==='base'?'':`<button data-layer-action="delete" data-layer-id="${layer.id}" type="button">Delete</button>`}<button data-layer-action="up" data-layer-id="${layer.id}" type="button" aria-label="Move ${escapeHtml(layer.name)} up">↑</button><button data-layer-action="down" data-layer-id="${layer.id}" type="button" aria-label="Move ${escapeHtml(layer.name)} down">↓</button></span></div>`).join('');if(lanes)lanes.innerHTML=state.diagram.swimlanes.slice().sort((a,b)=>a.order-b.order).map(lane=>`<div class="ds-lane-row"><span>${escapeHtml(lane.label)} · ${lane.orientation}</span><span class="ds-row-actions"><button data-lane-action="select" data-lane-id="${lane.id}" type="button">Select</button><button data-lane-action="rename" data-lane-id="${lane.id}" type="button">Rename</button><button data-lane-action="toggle-orientation" data-lane-id="${lane.id}" type="button">${lane.orientation==='horizontal'?'Vertical':'Horizontal'}</button><button data-lane-action="grow" data-lane-id="${lane.id}" type="button">Expand</button><button data-lane-action="shrink" data-lane-id="${lane.id}" type="button">Shrink</button><button data-lane-action="up" data-lane-id="${lane.id}" type="button">↑</button><button data-lane-action="down" data-lane-id="${lane.id}" type="button">↓</button><button data-lane-action="delete" data-lane-id="${lane.id}" type="button">Delete</button></span></div>`).join('') || '<small>No swimlanes yet.</small>';
  const list=$('#ds-subflow-list'); if(list)list.innerHTML=state.subflows.length?state.subflows.map((subflow,index)=>`<div class="ds-subflow-row"><span>${escapeHtml(subflow.name)} · ${subflow.nodes.length} nodes</span><button class="ds-link" data-subflow-index="${index}">Insert</button></div>`).join(''):'<small>No saved subflows yet.</small>';
}

function exportJson() { const payload={schema:DIAGRAM_SCHEMA,version:1,report_id:boot.report_id,element_id:boot.element_id,diagram:state.diagram};download(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),'visembler-diagram.json');notify('Diagram JSON exported','success'); }
function svgMarkup() { const svg=$('#ds-canvas');const copy=svg.cloneNode(true);copy.querySelectorAll('.ds-port,.ds-resize-handle,.ds-waypoint,.ds-connection-preview,.ds-route-ghost').forEach(node=>node.remove());copy.removeAttribute('tabindex');copy.setAttribute('role','img');copy.setAttribute('aria-label',`Diagram ${boot.title||''}`);return new XMLSerializer().serializeToString(copy); }
function exportSvg() { download(new Blob([svgMarkup()],{type:'image/svg+xml;charset=utf-8'}),'visembler-diagram.svg');notify('Diagram SVG exported','success'); }
function download(blob,name) { const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),500); }
function loadImport(file) { const reader=new FileReader();reader.onload=()=>{try{const value=JSON.parse(String(reader.result||''));const raw=value.diagram||value.model?.items?.find(item=>item.id===boot.element_id)||value;applyMutation('Import diagram',()=>raw.diagram ? diagramFromEntry(raw) : normalizeDiagram(raw));}catch(error){notify(error.message||'Diagram JSON could not be imported','error');}};reader.readAsText(file); }

function beginInlineNodeEdit(nodeId) {
  const node=state.diagram.nodes.find(item=>item.id===nodeId),wrap=$('#ds-canvas-wrap'),svg=$('#ds-canvas');
  if(!node||node.lock||!wrap||!svg)return;
  $('#ds-inline-editor')?.remove();
  const input=document.createElement('input'); input.id='ds-inline-editor';input.className='ds-inline-editor';input.type='text';input.value=node.label;input.setAttribute('aria-label',`Edit label for ${node.label}`);
  const svgRect=svg.getBoundingClientRect(),wrapRect=wrap.getBoundingClientRect(),scale=svgRect.width/(Number(svg.viewBox.baseVal.width)||svgRect.width);
  input.style.left=`${svgRect.left-wrapRect.left+node.x*scale}px`;input.style.top=`${svgRect.top-wrapRect.top+node.y*scale}px`;input.style.width=`${Math.max(120,node.width*scale)}px`;
  let completed=false; const finish=commit=>{if(completed)return;completed=true;const value=input.value.trim();input.remove();if(commit&&value!==node.label)applyMutation('Edit node label',current=>updateNode(current,nodeId,{label:value||'Untitled'}));};
  input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();finish(true);}else if(event.key==='Escape'){event.preventDefault();finish(false);}});input.addEventListener('blur',()=>finish(true));input.addEventListener('pointerdown',event=>event.stopPropagation());wrap.append(input);input.focus();input.select();
}

function beginGroupDrag(event,groupId) {
  const group=state.diagram.groups.find(item=>item.id===groupId);if(!group||group.lock)return notify('This container is locked');
  const members=new Set(group.nodeIds);const origin=new Map(state.diagram.nodes.filter(node=>members.has(node.id)).map(node=>[node.id,{x:node.x,y:node.y}]));
  state.groupDrag={groupId,start:svgPoint(event),group:{x:group.x,y:group.y},origin};event.currentTarget.setPointerCapture?.(event.pointerId);
}
function moveGroupDrag(event) { if(!state.groupDrag)return;const point=svgPoint(event),drag=state.groupDrag,dx=point.x-drag.start.x,dy=point.y-drag.start.y,group=state.diagram.groups.find(item=>item.id===drag.groupId);if(!group)return;group.x=drag.group.x+dx;group.y=drag.group.y+dy;drag.origin.forEach((origin,id)=>{const node=state.diagram.nodes.find(item=>item.id===id);if(node&&!node.lock){node.x=origin.x+dx;node.y=origin.y+dy;}});renderCanvas(); }
function finishGroupDrag(cancel=false) { if(!state.groupDrag)return;const drag=state.groupDrag,group=state.diagram.groups.find(item=>item.id===drag.groupId);if(!group){state.groupDrag=null;return;}const final={group:{x:group.x,y:group.y},nodes:state.diagram.nodes.filter(node=>drag.origin.has(node.id)).map(node=>({id:node.id,x:node.x,y:node.y}))};if(cancel){group.x=drag.group.x;group.y=drag.group.y;drag.origin.forEach((origin,id)=>{const node=state.diagram.nodes.find(item=>item.id===id);if(node){node.x=origin.x;node.y=origin.y;}});state.groupDrag=null;renderCanvas();return;}group.x=drag.group.x;group.y=drag.group.y;drag.origin.forEach((origin,id)=>{const node=state.diagram.nodes.find(item=>item.id===id);if(node){node.x=origin.x;node.y=origin.y;}});state.groupDrag=null;applyMutation('Move container',current=>{const value=moveContainer(current,drag.groupId,{x:final.group.x-drag.group.x,y:final.group.y-drag.group.y});return value;});}

function execute(action, ...args) {
  const node=activeNode(),edge=activeEdge();
  if(action==='undo')return undo();if(action==='redo')return redo();if(action==='save')return persist();if(action==='back')return goBack();if(action==='clear-selection')return clearSelection();if(action==='copy'){if(!selectedObjectCount())return notify('Select one or more nodes or a connector');state.clipboard=createSubflow(state.diagram,selectedIds(),'Clipboard');return notify('Selection copied','success');}if(action==='paste'){if(!state.clipboard)return notify('Copy a node selection first');const result=insertSubflow(state.diagram,state.clipboard,{x:80,y:80});const ok=applyMutation('Paste selection',()=>result.diagram);if(ok)state.selectedNodes=new Set(result.ids);return ok;}if(action==='duplicate'){if(!state.selectedNodes.size)return notify('Select one or more nodes');const result=duplicateNodes(state.diagram,selectedIds());const ok=applyMutation('Duplicate selection',()=>result.diagram);if(ok)state.selectedNodes=new Set(result.ids);return ok;}if(action==='delete'){if(!selectedObjectCount())return notify('Select something to delete');if(state.selectedEdges.size)return applyMutation('Delete connector',current=>({...removeNodes(current,[]),edges:current.edges.filter(item=>!state.selectedEdges.has(item.id)||item.lock)}));return applyMutation('Delete nodes',current=>removeNodes(current,selectedIds()));}
  if(action==='group')return applyMutation('Group selection',current=>groupNodes(current,selectedIds()).diagram);if(action==='ungroup')return applyMutation('Ungroup selection',current=>ungroupNodes(current,selectedIds()));if(action==='equal-width')return applyMutation('Equal widths',current=>equalizeNodes(current,selectedIds(),'width'));if(action==='equal-height')return applyMutation('Equal heights',current=>equalizeNodes(current,selectedIds(),'height'));if(action==='equal-size')return applyMutation('Equal size',current=>equalizeNodes(current,selectedIds(),'size'));if(action.startsWith('align-'))return applyMutation(action, current=>alignNodes(current,selectedIds(),action.slice(6)));if(action==='distribute-h')return applyMutation('Distribute horizontally',current=>distributeNodes(current,selectedIds(),'horizontal'));if(action==='distribute-v')return applyMutation('Distribute vertically',current=>distributeNodes(current,selectedIds(),'vertical'));
  if(action==='clean')return applyMutation('Clean Diagram',current=>cleanDiagram(current,{direction:current.layout.direction,preservePinned:true}));if(action==='layout-horizontal')return applyMutation('Horizontal flow',current=>autoLayout(current,{direction:'right',mode:'horizontal',preservePinned:true}));if(action==='layout-vertical')return applyMutation('Vertical flow',current=>autoLayout(current,{direction:'down',mode:'vertical',preservePinned:true}));if(action==='layout-tree')return applyMutation('Hierarchy layout',current=>autoLayout(current,{direction:'right',mode:'hierarchy',preservePinned:true}));if(action==='fit'||action==='fit-selection'){const wrap=$('#ds-canvas-wrap');const bounds=action==='fit-selection'&&node?{x:node.x,y:node.y,w:node.width,h:node.height}:diagramBounds(state.diagram);if(wrap){const available=Math.min(wrap.clientWidth-70,wrap.clientHeight-70);state.zoom=clamp(Math.min(available/bounds.w,available/bounds.h),.25,1.5);$('#ds-canvas').style.transform=`scale(${state.zoom})`;$('#ds-canvas').style.transformOrigin='top left';}return;}
  if(action==='toggle-grid'){state.grid=!state.grid;$('#ds-canvas').dataset.grid=state.grid?'on':'off';return renderCanvas();}if(action==='toggle-snap'){state.snap=!state.snap;const button=$('[data-action="toggle-snap"]');button?.setAttribute('aria-pressed',state.snap?'true':'false');return notify(`Snap ${state.snap?'on':'off'}`);}if(action==='fit-width'||action==='fit-page'||action==='fit'||action==='fit-selection'){const wrap=$('#ds-canvas-wrap');const bounds=action==='fit-selection'&&node?{x:node.x,y:node.y,w:node.width,h:node.height}:diagramBounds(state.diagram);if(wrap){const availableWidth=wrap.clientWidth-64,availableHeight=wrap.clientHeight-64;const target=action==='fit-width'?availableWidth/bounds.w:Math.min(availableWidth/bounds.w,availableHeight/bounds.h);state.zoom=clamp(target,.25,1.5);$('#ds-canvas').style.transform=`scale(${state.zoom})`;$('#ds-canvas').style.transformOrigin='top left';}return;}
  if(action==='preview'){state.preview=!state.preview;root.classList.toggle('studio-preview',state.preview);$('#ds-preview-banner').hidden=!state.preview;return renderCanvas();}if(action==='preview-close'){state.preview=false;root.classList.remove('studio-preview');$('#ds-preview-banner').hidden=true;return renderCanvas();}
  if(action==='import-json')return $('#ds-import-json')?.click();if(action==='export-json')return exportJson();if(action==='export-svg')return exportSvg();
  if(action==='add-process'||action==='add-shape'){const result=addNode(state.diagram,{shape:args[0]||'process',label:args[1]||undefined,x:args[2]?.x,y:args[2]?.y});const ok=applyMutation('Add node',()=>result.diagram);if(ok)selectNode(result.node.id);return ok;}if(action==='paste-process'){const input=$('#ds-process-input');const text=input?.value||'';if(!text.trim())return notify('Paste process steps first');const result=pasteProcessSteps(state.diagram,text);const ok=applyMutation('Paste process steps',()=>result.diagram);if(ok)state.selectedNodes=new Set(result.ids);render();return ok;}if(action==='paste-graph'){const input=$('#ds-graph-input');const text=input?.value||'';if(!text.trim())return notify('Paste a Source / Target / Label table first');const result=pasteSourceTargetTable(state.diagram,text,{clean:true});const ok=applyMutation('Paste source-target graph',()=>result.diagram);if(ok)state.selectedNodes=new Set(result.ids);render();return ok;}
  if(action==='quick-branch'){if(!node)return notify('Select a source node first');const result=quickBranch(state.diagram,node.id);const ok=applyMutation('Quick branch',()=>result.diagram);if(ok)selectNode(result.node.id);return ok;}if(action==='insert-edge'){if(!edge)return notify('Select a connector first');const result=insertNodeOnEdge(state.diagram,edge.id);const ok=applyMutation('Insert node on connector',()=>result.diagram);if(ok)selectNode(result.node.id);return ok;}
  if(action==='save-subflow'){if(state.selectedNodes.size<2)return notify('Select at least two nodes');const name=clean($('#ds-subflow-name')?.value)||`Subflow ${state.subflows.length+1}`;state.subflows.push(createSubflow(state.diagram,selectedIds(),name));persistSubflows();renderManagers();return notify(`Saved ${name}`,'success');}if(action==='add-layer'){const result=addLayer(state.diagram,'New layer');const ok=applyMutation('Add layer',()=>result.diagram);if(ok)renderManagers();return ok;}if(action==='add-lane'){const result=addLane(state.diagram,{label:`Lane ${state.diagram.swimlanes.length+1}`,orientation:'horizontal'});const ok=applyMutation('Add swimlane',()=>result.diagram);if(ok)renderManagers();return ok;}if(action==='flow-to-lanes')return applyMutation('Create swimlanes from flow metadata',current=>flowToSwimlanes(current));
  if(action==='select-connected'&&node){state.selectedNodes=new Set(selectConnected(state.diagram,node.id));return render();}if(action==='select-same-type'&&node){state.selectedNodes=new Set(selectSameType(state.diagram,node.id));return render();}if(action==='reverse'&&edge)return applyMutation('Reverse connector',current=>reverseEdge(current,edge.id));if(action==='add-edge-label'&&edge){const labels=[...(edge.labels||[]),{id:uid('label'),text:'New label',position:'center',offset:0}];return applyMutation('Add connector label',current=>updateEdge(current,edge.id,{labels}));}if(action==='add-waypoint'&&edge){const points=routeEdge(state.diagram,edge);return applyMutation('Add waypoint',current=>addWaypoint(current,edge.id,points[Math.max(1,Math.floor(points.length/2))]||{x:0,y:0}));}if(action==='clear-waypoints'&&edge)return applyMutation('Clear waypoints',current=>clearWaypoints(current,edge.id));if(action==='delete-waypoint'&&edge)return applyMutation('Delete waypoint',current=>deleteWaypoint(current,edge.id,edge.waypoints.length-1));
  return notify('Command unavailable');
}

function persistSubflows() { try { localStorage.setItem(`visembler-diagram-subflows:${boot.report_id}`,JSON.stringify(state.subflows)); } catch { /* optional local reuse */ } }
function loadSubflows() { try { const value=JSON.parse(localStorage.getItem(`visembler-diagram-subflows:${boot.report_id}`)||'[]');if(Array.isArray(value))state.subflows=value; } catch { state.subflows=[]; } }

function onInspectChange(event) {
  const target=event.target, key=target.dataset.inspect, node=activeNode(); if(!node||!key)return; const value=target.type==='checkbox'?target.checked:target.value;
  if(key==='lane')return applyMutation('Move node to lane',current=>moveNodesToLane(current,[node.id],value));if(key==='layer')return applyMutation('Move node to layer',current=>moveSelectionToLayer(current,[node.id],value));
  if(key.startsWith('style.')){const styleKey=key.slice(6);const styleValue=styleKey==='borderWidth'?Number(value):value;return applyMutation(`Edit node ${styleKey}`,current=>updateNode(current,node.id,{style:{...node.style,[styleKey]:styleValue}}));}
  const patch=['x','y','width','height'].includes(key)?{[key]:Number(value)}:{[key]:value};if(key==='pinned'||key==='lock')patch[key]=target.checked;return applyMutation(`Edit node ${key}`,current=>updateNode(current,node.id,patch));
}
function onEdgeInspectChange(event) { const target=event.target, key=target.dataset.edgeInspect, edge=activeEdge();if(!edge||!key)return;let patch={};if(['source','target','routing','sourcePort','targetPort','startMarker','endMarker'].includes(key))patch[key]=target.value;else if(key==='lock')patch.lock=target.checked;else if(key==='width')patch.style={width:Number(target.value)};else if(key==='color')patch.style={color:target.value};else if(key==='line')patch.style={line:target.value};applyMutation(`Edit connector ${key}`,current=>updateEdge(current,edge.id,patch)); }
function onLabelChange(event) { const edge=activeEdge(),index=Number(event.target.dataset.edgeLabel ?? event.target.dataset.edgePosition);if(!edge||!Number.isInteger(index))return;const labels=clone(edge.labels||[]);if(event.target.dataset.edgeLabel!==undefined)labels[index].text=event.target.value;else labels[index].position=event.target.value;applyMutation('Edit connector label',current=>updateEdge(current,edge.id,{labels})); }
function startDrag(event,nodeId) { const node=state.diagram.nodes.find(item=>item.id===nodeId);if(!node||node.lock||selectedLayerLocked())return notify('This node is locked');if(!state.selectedNodes.has(nodeId))selectNode(nodeId,event.shiftKey||event.metaKey);state.pointerSelectedNode=nodeId;const origin=new Map(selectedIds().map(id=>{const item=state.diagram.nodes.find(value=>value.id===id);return [id,{x:item.x,y:item.y}];}));state.drag={nodeId,start:svgPoint(event),origin};event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveDrag(event) { if(!state.drag)return;const point=svgPoint(event),dx=point.x-state.drag.start.x,dy=point.y-state.drag.start.y;state.drag.origin.forEach((origin,id)=>{const node=state.diagram.nodes.find(item=>item.id===id);if(node){const next=snapPoint({x:origin.x+dx,y:origin.y+dy});node.x=Math.max(0,next.x);node.y=Math.max(0,next.y);}});renderCanvas(); }
function finishDrag(cancel=false) { if(!state.drag)return;const origin=state.drag.origin;const after=clone(state.diagram);if(cancel){state.diagram.nodes.forEach(node=>{const point=origin.get(node.id);if(point){node.x=point.x;node.y=point.y;}});state.drag=null;renderCanvas();return;}state.diagram.nodes.forEach(node=>{const point=origin.get(node.id);if(point){node.x=point.x;node.y=point.y;}});const final=clone(state.diagram);state.drag=null;applyMutation('Move node',()=>{const value=clone(final);value.layout.lastCommand='Move node';return value;});}
function startResize(event,nodeId) { const node=state.diagram.nodes.find(item=>item.id===nodeId);if(!node||node.lock||selectedLayerLocked())return notify('This node is locked');state.resize={nodeId,start:svgPoint(event),width:node.width,height:node.height,after:clone(node)};event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveResize(event) { if(!state.resize)return;const point=svgPoint(event),node=state.diagram.nodes.find(item=>item.id===state.resize.nodeId);if(!node)return;node.width=Math.max(88,state.resize.width+point.x-state.resize.start.x);node.height=Math.max(48,state.resize.height+point.y-state.resize.start.y);renderCanvas(); }
function finishResize(cancel=false) { if(!state.resize)return;const current=state.diagram.nodes.find(node=>node.id===state.resize.nodeId),final=clone(current);state.diagram.nodes.splice(state.diagram.nodes.findIndex(node=>node.id===state.resize.nodeId),1,state.resize.after);state.resize=null;if(!cancel)applyMutation('Resize node',()=>{const value=clone(state.diagram);const target=value.nodes.find(node=>node.id===final.id);Object.assign(target,final);return value;});else renderCanvas(); }
function startLasso(event) { const point=svgPoint(event);state.lasso={x:point.x,y:point.y,width:0,height:0};event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveLasso(event) { if(!state.lasso)return;const point=svgPoint(event),start=state.lasso;state.lasso={x:Math.min(start.x,point.x),y:Math.min(start.y,point.y),width:Math.abs(point.x-start.x),height:Math.abs(point.y-start.y)};renderLasso(); }
function finishLasso() { if(!state.lasso)return;const box=state.lasso;state.selectedNodes=new Set(state.diagram.nodes.filter(node=>{const x=node.x+node.width/2,y=node.y+node.height/2;return x>=box.x&&x<=box.x+box.width&&y>=box.y&&y<=box.y+box.height;}).map(node=>node.id));state.lasso=null;render(); }
function startConnect(event,nodeId,portId) { const node=state.diagram.nodes.find(item=>item.id===nodeId);if(!node||node.lock)return;const port=node.ports.find(item=>item.id===portId)||node.ports[1];state.connect={source:nodeId,start:{x:node.x+port.x*node.width,y:node.y+port.y*node.height},current:{x:node.x+port.x*node.width,y:node.y+port.y*node.height}};event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveConnect(event) { if(!state.connect)return;state.connect.current=svgPoint(event);renderCanvas(); }
function finishConnect(event,cancel=false) { if(!state.connect)return;const connect=state.connect;state.connect=null;if(cancel){renderCanvas();return;}const target=event.target.closest?.('[data-node-id]');if(target&&target.dataset.nodeId!==connect.source){const result=addEdge(state.diagram,connect.source,target.dataset.nodeId,{routing:'orthogonal',label:''});applyMutation('Connect nodes',()=>result);}else{const point=svgPoint(event),result=quickBranch(state.diagram,connect.source,{x:point.x,y:point.y,label:'New step'});if(result.node){applyMutation('Connect and create node',()=>result.diagram);state.selectedNodes=new Set([result.node.id]);}}render();}
function startWaypoint(event,edgeId,index) { const edge=state.diagram.edges.find(item=>item.id===edgeId);if(!edge||edge.lock)return;state.waypoint={edgeId,index,start:svgPoint(event),point:clone(edge.waypoints[index])};event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveWaypoint(event) { if(!state.waypoint)return;const point=snapPoint(svgPoint(event)),waypoint=state.waypoint,edge=state.diagram.edges.find(item=>item.id===waypoint.edgeId);if(edge)edge.waypoints[waypoint.index]=point;renderCanvas(); }
function finishWaypoint(cancel=false) { if(!state.waypoint)return;const waypoint=state.waypoint,edge=state.diagram.edges.find(item=>item.id===waypoint.edgeId),final=clone(edge?.waypoints[waypoint.index]);if(edge)edge.waypoints[waypoint.index]=waypoint.point;state.waypoint=null;if(!cancel)applyMutation('Move waypoint',current=>moveWaypointModel(current,waypoint.edgeId,waypoint.index,final));else renderCanvas();}
function distanceToSegment(point,start,end) { const dx=end.x-start.x,dy=end.y-start.y,length=dx*dx+dy*dy;const ratio=length?Math.max(0,Math.min(1,((point.x-start.x)*dx+(point.y-start.y)*dy)/length)):0;const closest={x:start.x+ratio*dx,y:start.y+ratio*dy};return {distance:Math.hypot(point.x-closest.x,point.y-closest.y),ratio}; }
function startRouteDrag(event,edgeId) { const edge=state.diagram.edges.find(item=>item.id===edgeId);if(!edge||edge.lock)return;event.currentTarget.setPointerCapture?.(event.pointerId);const point=svgPoint(event);state.routeDrag={edgeId,start:point,point,moved:false};selectEdge(edgeId,event.shiftKey||event.metaKey); }
function moveRouteDrag(event) { if(!state.routeDrag)return;const point=snapPoint(svgPoint(event));state.routeDrag={...state.routeDrag,point,moved:state.routeDrag.moved||Math.hypot(point.x-state.routeDrag.start.x,point.y-state.routeDrag.start.y)>3};renderCanvas(); }
function finishRouteDrag(cancel=false) { if(!state.routeDrag)return;const drag=state.routeDrag;state.routeDrag=null;if(cancel||!drag.moved)return renderCanvas();const edge=state.diagram.edges.find(item=>item.id===drag.edgeId);if(!edge)return renderCanvas();const points=routeEdge(state.diagram,edge);let best={distance:Infinity,index:0};for(let index=1;index<points.length;index+=1){const candidate=distanceToSegment(drag.point,points[index-1],points[index]);if(candidate.distance<best.distance)best={distance:candidate.distance,index:index-1};}applyMutation('Add connector waypoint',current=>addWaypoint(current,drag.edgeId,snapPoint(drag.point),best.index)); }
function startLabelDrag(event,edgeId,index) { const edge=state.diagram.edges.find(item=>item.id===edgeId),label=edge?.labels?.[index];if(!edge||!label||edge.lock)return;const point=svgPoint(event);state.labelDrag={edgeId,index,start:point,offset:finiteOffset(label.offset,0),moved:false};event.stopPropagation();event.currentTarget.setPointerCapture?.(event.pointerId); }
function moveLabelDrag(event) { if(!state.labelDrag)return;const point=svgPoint(event),drag=state.labelDrag,edge=state.diagram.edges.find(item=>item.id===drag.edgeId),label=edge?.labels?.[drag.index];if(!label)return;label.offset=drag.offset+point.x-drag.start.x;drag.moved=drag.moved||Math.hypot(point.x-drag.start.x,point.y-drag.start.y)>3;renderCanvas(); }
function finishLabelDrag(cancel=false) { if(!state.labelDrag)return;const drag=state.labelDrag,edge=state.diagram.edges.find(item=>item.id===drag.edgeId),label=edge?.labels?.[drag.index];if(label&&cancel)label.offset=drag.offset;const final=label?.offset;state.labelDrag=null;if(!cancel&&drag.moved)applyMutation('Move connector label',current=>{const value=normalizeDiagram(current),target=value.edges.find(item=>item.id===drag.edgeId);if(target?.labels?.[drag.index])target.labels[drag.index].offset=final;return value;});else renderCanvas(); }

function bind() {
  root.addEventListener('click',event=>{const action=event.target.closest('[data-action]')?.dataset.action;if(action)return execute(action,event.target.closest('.ds-shape-button[data-shape]')?.dataset.shape);const shape=event.target.closest('.ds-shape-button[data-shape]');if(shape)return execute('add-shape',shape.dataset.shape,shape.querySelector('b')?.textContent);const nodeTarget=event.target.closest('[data-node-id]');if(nodeTarget){const already=state.pointerSelectedNode===nodeTarget.dataset.nodeId;state.pointerSelectedNode=null;if(already)return;return selectNode(nodeTarget.dataset.nodeId,event.shiftKey||event.metaKey);}const edgeTarget=event.target.closest('[data-edge-id]');if(edgeTarget)return selectEdge(edgeTarget.dataset.edgeId,event.shiftKey||event.metaKey);const layerAction=event.target.closest('[data-layer-action]');if(layerAction){const id=layerAction.dataset.layerId,kind=layerAction.dataset.layerAction,layer=state.diagram.layers.find(item=>item.id===id);if(!layer)return;if(kind==='select'){state.selectedNodes=new Set(state.diagram.nodes.filter(node=>node.layer===id).map(node=>node.id));return render();}if(kind==='rename'){const name=window.prompt('Layer name',layer.name);if(name===null)return;return applyMutation('Rename layer',current=>updateLayer(current,id,{name}));}if(kind==='delete'){if(!window.confirm(`Delete layer “${layer.name}”? Its objects will move to Main diagram.`))return;return applyMutation('Delete layer',current=>removeLayer(current,id));}if(kind==='duplicate')return applyMutation('Duplicate layer',current=>duplicateLayer(current,id).diagram);if(kind==='up'||kind==='down')return applyMutation(`Move layer ${kind}`,current=>reorderLayer(current,id,kind==='up'?-1:1));return applyMutation(`${kind} layer`,current=>updateLayer(current,id,kind==='visibility'?{visible:!current.layers.find(item=>item.id===id)?.visible}:{lock:!current.layers.find(item=>item.id===id)?.lock}));}const laneAction=event.target.closest('[data-lane-action]');if(laneAction){const id=laneAction.dataset.laneId,kind=laneAction.dataset.laneAction,lane=state.diagram.swimlanes.find(item=>item.id===id);if(!lane)return;if(kind==='select'){state.selectedNodes=new Set(state.diagram.nodes.filter(node=>node.lane===id).map(node=>node.id));return render();}if(kind==='rename'){const name=window.prompt('Swimlane name',lane.label);if(name===null)return;return applyMutation('Rename swimlane',current=>updateLane(current,id,{label:name}));}if(kind==='delete'){if(!window.confirm(`Delete swimlane “${lane.label}”? Nodes will become unassigned.`))return;return applyMutation('Delete swimlane',current=>removeLane(current,id));}if(kind==='toggle-orientation')return applyMutation('Change swimlane orientation',current=>updateLane(current,id,{orientation:lane.orientation==='horizontal'?'vertical':'horizontal'}));if(kind==='grow'||kind==='shrink'){const amount=kind==='grow'?24:-24;const dimension=lane.orientation==='horizontal'?'height':'width';return applyMutation(`${kind} swimlane`,current=>updateLane(current,id,{[dimension]:Math.max(dimension==='height'?110:240,lane[dimension]+amount)}));}return applyMutation(`${kind} swimlane`,current=>reorderLane(current,id,kind==='up'?-1:1));}const subflow=event.target.closest('[data-subflow-index]');if(subflow){const value=state.subflows[Number(subflow.dataset.subflowIndex)];const result=insertSubflow(state.diagram,value,{x:80,y:80});const ok=applyMutation('Insert subflow',()=>result.diagram);if(ok)state.selectedNodes=new Set(result.ids);return render();}});
  root.addEventListener('change',event=>{if(event.target.matches('[data-inspect]'))onInspectChange(event);if(event.target.matches('[data-edge-inspect]'))onEdgeInspectChange(event);if(event.target.matches('[data-edge-label],[data-edge-position]'))onLabelChange(event);});
  root.addEventListener('dblclick',event=>{const node=event.target.closest('[data-node-id]');if(node)beginInlineNodeEdit(node.dataset.nodeId);});
  root.addEventListener('pointerdown',event=>{const label=event.target.closest('[data-edge-label-index]');if(label)return startLabelDrag(event,label.closest('[data-edge-id]')?.dataset.edgeId,Number(label.dataset.edgeLabelIndex));const port=event.target.closest('[data-port]');if(port)return startConnect(event,port.closest('[data-node-id]')?.dataset.nodeId,port.dataset.port);const resize=event.target.closest('[data-resize]');if(resize)return startResize(event,resize.dataset.resize);const waypoint=event.target.closest('[data-waypoint-index]');if(waypoint)return startWaypoint(event,waypoint.dataset.edgeId,Number(waypoint.dataset.waypointIndex));const group=event.target.closest('[data-group-id]');if(group)return beginGroupDrag(event,group.dataset.groupId);const node=event.target.closest('[data-node-id]');if(node){if(event.detail>=2){event.preventDefault();if(!state.selectedNodes.has(node.dataset.nodeId))selectNode(node.dataset.nodeId);return;}return startDrag(event,node.dataset.nodeId);}const edgePath=event.target.closest('.ds-edge');if(edgePath)return startRouteDrag(event,edgePath.closest('[data-edge-id]')?.dataset.edgeId);if(event.target.closest('[data-edge-id]')){selectEdge(event.target.closest('[data-edge-id]').dataset.edgeId,event.shiftKey||event.metaKey);return;}if(event.target.id==='ds-canvas-bg'||event.target.id==='ds-canvas')startLasso(event);});
  root.addEventListener('pointermove',event=>{moveDrag(event);moveGroupDrag(event);moveResize(event);moveLasso(event);moveConnect(event);moveWaypoint(event);moveRouteDrag(event);moveLabelDrag(event);});root.addEventListener('pointerup',event=>{if(state.drag)finishDrag();if(state.groupDrag)finishGroupDrag();if(state.resize)finishResize();if(state.lasso)finishLasso();if(state.connect)finishConnect(event);if(state.waypoint)finishWaypoint();if(state.routeDrag)finishRouteDrag();if(state.labelDrag)finishLabelDrag();});root.addEventListener('pointercancel',()=>{if(state.drag)finishDrag(true);if(state.groupDrag)finishGroupDrag(true);if(state.resize)finishResize(true);if(state.lasso){state.lasso=null;renderLasso();}if(state.connect)finishConnect(null,true);if(state.waypoint)finishWaypoint(true);if(state.routeDrag)finishRouteDrag(true);if(state.labelDrag)finishLabelDrag(true);});
  $('#ds-canvas-wrap')?.addEventListener('wheel',event=>{if(event.ctrlKey||event.metaKey||event.deltaY){event.preventDefault();state.zoom=clamp(state.zoom*(event.deltaY<0?1.1:.9),.25,2);const svg=$('#ds-canvas');svg.style.transform=`scale(${state.zoom})`;svg.style.transformOrigin='top left';notify(`Zoom ${Math.round(state.zoom*100)}%`);}}, {passive:false});
  root.addEventListener('keydown',event=>{const tag=event.target.tagName;if(['INPUT','TEXTAREA','SELECT'].includes(tag))return;if(event.key==='Escape'){if(state.drag)finishDrag(true);else if(state.connect)finishConnect(null,true);else clearSelection();return;}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?redo():undo();return;}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='y'){event.preventDefault();redo();return;}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='d'){event.preventDefault();return execute('duplicate');}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='c'){event.preventDefault();state.clipboard=createSubflow(state.diagram,selectedIds(),'Clipboard');return notify('Selection copied');}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='v'){event.preventDefault();if(state.clipboard){const result=insertSubflow(state.diagram,state.clipboard,{x:80,y:80});applyMutation('Paste selection',()=>result.diagram);state.selectedNodes=new Set(result.ids);render();}return;}if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();execute('delete');return;}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)&&state.selectedNodes.size){event.preventDefault();const delta={ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0},ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1}}[event.key],step=event.shiftKey?12:2;applyMutation('Nudge selection',current=>{const value=normalizeDiagram(current);value.nodes.forEach(node=>{if(state.selectedNodes.has(node.id)&&!node.lock){node.x=Math.max(0,node.x+delta.x*step);node.y=Math.max(0,node.y+delta.y*step);}});return value;});}});
  $('#ds-import-json')?.addEventListener('change',event=>{const file=event.target.files?.[0];if(file)loadImport(file);event.target.value='';});
}
function renderPalette() { const host=$('#ds-shape-palette');if(!host)return;let group='';host.innerHTML=SHAPE_CATALOG.map(shape=>{const heading=shape.group!==group?(group=shape.group,`<div class="ds-shape-group">${shape.group}</div>`):'';return `${heading}<button class="ds-shape-button" data-shape="${shape.id}" type="button" aria-label="Add ${escapeHtml(shape.label)}"><span class="ds-shape-icon">${shape.icon}</span><b>${escapeHtml(shape.label)}</b></button>`;}).join(''); }
function render() { renderCanvas();renderInspector();renderManagers(); }
function init() { if(!root)return;renderPalette();loadSubflows();bind();render();root.dataset.studioReady='true';notify('Ready'); }
init();
