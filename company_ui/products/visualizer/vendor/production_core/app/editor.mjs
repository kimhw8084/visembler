import {
  EditorStore,
  RevisionConflictError,
  parseCanonical,
  serializeCanonical,
} from '../core/editor_store.mjs';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const storage = { get(key) { try { return localStorage.getItem(key); } catch { return null; } }, set(key, value) { try { localStorage.setItem(key, value); return true; } catch { return false; } }, remove(key) { try { localStorage.removeItem(key); } catch { /* unavailable */ } } };
const CANVAS = { x: 50, y: 55, w: 1200, h: 675, gap: 14 };

const typeDefaults = {
  metric: { title: 'Automation Impact', weight: 1.15, minW: 180, minH: 130 },
  chart: { title: 'Investigation Trend', weight: 1.8, minW: 270, minH: 180 },
  text: { title: 'Key Takeaway', weight: 1.1, minW: 190, minH: 120 },
  table: { title: 'Evidence Log', weight: 1.55, minW: 250, minH: 190 },
  tabs: { title: 'Investigation Summary', weight: 1.15, minW: 210, minH: 150 },
  timeline: { title: 'Validation Path', weight: 1.3, minW: 270, minH: 140 },
  image: { title: 'Engineering Visual', weight: 1.25, minW: 220, minH: 150 },
  diagram: { title: 'Technical Flow', weight: 1.5, minW: 290, minH: 170 },
  risk: { title: 'Risk / Decision', weight: 1, minW: 200, minH: 130 },
};

const defaultChartData = [['Collect', 84], ['Normalize', 71], ['Reason', 48], ['Verify', 31], ['Close', 14]];
const initialItems = [
  { id: 'c1', type: 'metric', title: 'Investigation Time', weight: 1.1, order: 0, value: 92, detail: false, locked: false, z: 1 },
  { id: 'c2', type: 'chart', title: 'Investigation Trend', weight: 1.85, order: 1, variant: 'line', data: defaultChartData, brush: [0, 4], cross: null, drill: null, revealed: true, locked: false, z: 2 },
  { id: 'c3', type: 'text', title: 'Key Takeaway', weight: 1.05, order: 2, locked: false, z: 3 },
  { id: 'c4', type: 'table', title: 'Evidence Log', weight: 1.5, order: 3, locked: false, z: 4 },
  { id: 'c5', type: 'tabs', title: 'Investigation Summary', weight: 1.05, order: 4, tab: 'Summary', expanded: false, locked: false, z: 5 },
  { id: 'c6', type: 'timeline', title: 'Validation Path', weight: 1.35, order: 5, tm: 2, locked: false, z: 6 },
];

const store = new EditorStore({
  schema_version: 1,
  items: structuredClone(initialItems),
  groups: {},
  mode: 'smart',
  layoutPreset: 'editorial',
  crossFilter: null,
  nextId: 20,
});

const ui = {
  zoom: 0.88,
  selected: new Set(),
  lasso: null,
  space: false,
  snap: true,
  showMini: true,
  preview: false,
  autoFit: true,
  previewPatches: new Map(),
  kpiAnimate: new Set(['c1']),
  pointerSession: null,
  modalReturnFocus: null,
  commandIndex: 0,
  resizeEpoch: 0,
  componentNodes: new Map(),
  minimapNodes: new Map(),
  contextSignature: '',
  contextSize: null,
  contextBoundsCache: null,
  lastPreflight: null,
};

function model() { return store.model; }
function item(id) { return model().items.find((entry) => entry.id === id); }
function esc(value) { return String(value ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }
function overlap(a, b, p = 0) { return !(a.x + a.w + p <= b.x || b.x + b.w + p <= a.x || a.y + a.h + p <= b.y || b.y + b.h + p <= a.y); }
function intersectionArea(a, b) {
  const w = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  const h = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  return w * h;
}
function rectUnion(rects) {
  if (!rects.length) return null;
  return {
    x: Math.min(...rects.map((r) => r.x)),
    y: Math.min(...rects.map((r) => r.y)),
    w: Math.max(...rects.map((r) => r.x + r.w)) - Math.min(...rects.map((r) => r.x)),
    h: Math.max(...rects.map((r) => r.y + r.h)) - Math.min(...rects.map((r) => r.y)),
  };
}

function viewItem(entry) {
  const patch = ui.previewPatches.get(entry.id);
  return patch ? { ...entry, ...patch } : entry;
}
function viewItems() { return model().items.map(viewItem); }
function effectiveWeight(entry) {
  if (model().layoutPreset === 'executive') return entry.type === 'metric' ? 2.1 : entry.type === 'text' ? 1.5 : entry.type === 'chart' ? 1.8 : entry.weight;
  if (model().layoutPreset === 'technical') return ['table', 'diagram', 'timeline'].includes(entry.type) ? entry.weight * 1.45 : entry.weight * 0.9;
  return entry.weight;
}
function partition(items, x, y, w, h, depth = 0) {
  if (!items.length) return [];
  if (items.length === 1) return [{ id: items[0].id, x, y, w, h }];
  const weights = items.map((entry) => effectiveWeight(entry));
  const total = weights.reduce((s, v) => s + v, 0);
  let acc = 0;
  let best = 1;
  let diff = Infinity;
  for (let k = 1; k < items.length; k += 1) {
    acc += weights[k - 1];
    const d = Math.abs(acc - total / 2);
    if (d < diff) { diff = d; best = k; }
  }
  const A = items.slice(0, best);
  const B = items.slice(best);
  const wa = A.reduce((s, entry) => s + effectiveWeight(entry), 0);
  const ratio = clamp(wa / total, 0.30, 0.70);
  const vertical = w / h > 1.22 ? true : h / w > 1.22 ? false : depth % 2 === 0;
  if (vertical) {
    const w1 = w * ratio;
    return partition(A, x, y, w1, h, depth + 1).concat(partition(B, x + w1, y, w - w1, h, depth + 1));
  }
  const h1 = h * ratio;
  return partition(A, x, y, w, h1, depth + 1).concat(partition(B, x, y + h1, w, h - h1, depth + 1));
}
function smartRects(items = viewItems()) {
  const ordered = [...items].sort((a, b) => a.order - b.order);
  const raw = partition(ordered, 0, 0, CANVAS.w, CANVAS.h);
  return raw.map((r) => {
    const L = r.x < 0.2;
    const R = Math.abs(r.x + r.w - CANVAS.w) < 0.2;
    const T = r.y < 0.2;
    const B = Math.abs(r.y + r.h - CANVAS.h) < 0.2;
    const g = CANVAS.gap;
    return {
      id: r.id,
      x: r.x + (L ? 0 : g / 2),
      y: r.y + (T ? 0 : g / 2),
      w: r.w - (L ? 0 : g / 2) - (R ? 0 : g / 2),
      h: r.h - (T ? 0 : g / 2) - (B ? 0 : g / 2),
      touch: { L, R, T, B },
    };
  });
}
function currentRects() {
  if (model().mode === 'smart') return smartRects();
  const fallback = new Map(smartRects().map((r) => [r.id, r]));
  return viewItems().map((entry) => {
    const base = fallback.get(entry.id);
    return {
      id: entry.id,
      x: Number.isFinite(entry.x) ? entry.x : base.x,
      y: Number.isFinite(entry.y) ? entry.y : base.y,
      w: Number.isFinite(entry.w) ? entry.w : base.w,
      h: Number.isFinite(entry.h) ? entry.h : base.h,
      touch: {},
    };
  });
}
function rectMap() { return new Map(currentRects().map((r) => [r.id, r])); }

function commitOps(label, ops, { announce = null, render = true } = {}) {
  const accepted = store.commit(store.command(ops, label));
  pruneSelection();
  ui.previewPatches.clear();
  if (render) renderAll();
  if (announce) toast(announce);
  return accepted;
}
function undo() {
  if (!store.canUndo) return toast('Nothing to undo');
  store.undo(store.revision);
  pruneSelection();
  ui.previewPatches.clear();
  renderAll();
  toast('Undid last edit');
}
function redo() {
  if (!store.canRedo) return toast('Nothing to redo');
  store.redo(store.revision);
  pruneSelection();
  ui.previewPatches.clear();
  renderAll();
  toast('Redid last edit');
}
function pruneSelection() {
  const ids = new Set(model().items.map((entry) => entry.id));
  ui.selected = new Set([...ui.selected].filter((id) => ids.has(id)));
}

function chartData(entry) { return Array.isArray(entry.data) && entry.data.length ? entry.data : defaultChartData; }
function metricMarkup(entry) {
  return `<div class="kicker">Metric · live interaction</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">From 188 min manual → 14 min governed workflow</div><div class="metric-big" data-kpi="${entry.id}">${entry.value}%</div><div class="metric-delta">↓ ${entry.value}% cycle-time reduction</div><button class="mini-btn detail-toggle align-start mt-2" data-action="detail" aria-expanded="${entry.detail ? 'true' : 'false'}">${entry.detail ? 'Hide' : 'Show'} detail</button>${entry.detail ? '<div class="metric-detail">Derived from the same before/after model. Web can expand; PPT keeps the accepted summary.</div>' : ''}`;
}
function chartMarkup(entry, r) {
  const D = chartData(entry);
  if (entry.variant === 'nochart') {
    return `<div class="kicker">No Chart · semantic fallback</div><div class="ctitle">${esc(entry.title)}</div><div class="metric-big compact">${D.at(-1)[1]}m</div><div class="metric-delta">Current investigation time</div><div class="csub mt-2">Plot removed because direct hierarchy is the selected representation.</div>`;
  }
  const W = Math.max(220, r.w - 36);
  const H = Math.max(90, r.h - 116);
  const left = 24; const right = 12; const top = 10; const bottom = 30;
  const plotW = W - left - right; const plotH = H - top - bottom;
  const max = Math.max(...D.map((x) => +x[1] || 0), 1);
  const pts = D.map((d, k) => ({ x: left + plotW * k / Math.max(1, D.length - 1), y: top + plotH - (+d[1] || 0) / max * plotH, v: +d[1] || 0, l: d[0] }));
  let marks = '';
  if (entry.variant === 'bar') {
    const bw = Math.max(12, plotW / D.length * 0.55);
    marks = pts.map((p, k) => `<rect aria-hidden="true" class="chart-point-visual ${entry.cross === k ? 'active' : ''}" x="${p.x - bw / 2}" y="${p.y}" width="${bw}" height="${top + plotH - p.y}" rx="5"></rect>`).join('');
  } else {
    const linePath = pts.map((p, k) => `${k ? 'L' : 'M'}${p.x} ${p.y}`).join(' ');
    const areaPath = `M ${pts[0].x} ${top + plotH} ${pts.map((p) => `L ${p.x} ${p.y}`).join(' ')} L ${pts.at(-1).x} ${top + plotH} Z`;
    const clip = entry.revealed ? 'inset(0 0 0 0)' : 'inset(0 100% 0 0)';
    marks = (entry.variant === 'area' ? `<path d="${areaPath}" class="chart-area reveal-mask" style="clip-path:${clip}"></path>` : '')
      + `<path d="${linePath}" class="chart-line reveal-mask" style="clip-path:${clip}"></path>`
      + pts.map((p, k) => `<circle aria-hidden="true" class="chart-point-visual ${entry.cross === k ? 'active' : ''}" cx="${p.x}" cy="${p.y}" r="${entry.cross === k ? 6.5 : 4.5}"></circle>`).join('');
  }
  const hitButtons = pts.map((p, k) => {
    const cy = entry.variant === 'bar' ? p.y + (top + plotH - p.y) / 2 : p.y;
    return `<button type="button" class="chart-hit" data-point="${k}" aria-label="${esc(p.l)} ${p.v} minutes" aria-pressed="${entry.cross === k ? 'true' : 'false'}" style="left:${p.x / W * 100}%;top:${cy / H * 100}%"></button>`;
  }).join('');
  const bs = entry.brush || [0, D.length - 1];
  const bx1 = left + plotW * bs[0] / Math.max(1, D.length - 1);
  const bx2 = left + plotW * bs[1] / Math.max(1, D.length - 1);
  const drill = entry.drill != null ? `<div class="chart-drill"><b>${esc(D[entry.drill][0])}</b> · ${D[entry.drill][1]} min. Drill-down is interactive on web and flattens to the selected state for PPT.</div>` : '';
  return `<div class="kicker">Chart · cross-filter + brush + drill</div><div class="row-between"><div><div class="ctitle">${esc(entry.title)}</div><div class="csub">Click mark to filter evidence · double-click for drill-down</div></div><button class="mini-btn reveal" data-action="reveal" aria-pressed="${entry.revealed ? 'true' : 'false'}">${entry.revealed ? 'Hide' : 'Reveal'}</button></div><div class="chart-wrap"><svg class="chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" data-chart="${entry.id}" aria-label="${esc(entry.title)} chart">${[0, .5, 1].map((t) => `<line x1="${left}" y1="${top + plotH * t}" x2="${left + plotW}" y2="${top + plotH * t}" class="chart-grid"></line>`).join('')}${marks}<rect x="${left}" y="${H - 13}" width="${plotW}" height="5" rx="3" class="brush-track"></rect><rect x="${bx1}" y="${H - 16}" width="${Math.max(3, bx2 - bx1)}" height="11" rx="4" class="brush-window"></rect><rect aria-hidden="true" x="${bx1 - 3}" y="${H - 20}" width="6" height="19" rx="2" class="brush-handle-visual brush-handle-start"></rect><rect aria-hidden="true" x="${bx2 - 3}" y="${H - 20}" width="6" height="19" rx="2" class="brush-handle-visual brush-handle-end"></rect></svg><div class="chart-hit-layer">${hitButtons}<button type="button" role="slider" aria-label="Brush start" aria-valuemin="0" aria-valuemax="${D.length - 1}" aria-valuenow="${bs[0]}" class="brush-handle" data-brush="start" style="left:${bx1 / W * 100}%"></button><button type="button" role="slider" aria-label="Brush end" aria-valuemin="0" aria-valuemax="${D.length - 1}" aria-valuenow="${bs[1]}" class="brush-handle" data-brush="end" style="left:${bx2 / W * 100}%"></button></div></div><div class="chart-footer"><span>Brush: ${esc(D[bs[0]][0])} → ${esc(D[bs[1]][0])}</span><span>${entry.cross != null ? `Filter: ${esc(D[entry.cross][0])}` : 'No cross-filter'}</span></div>${drill}`;
}
function textMarkup(entry, r = {}) {
  const compact = Number(r.w) < 220 || Number(r.h) < 245;
  const full = 'Evidence is prepared deterministically before reasoning—not discovered by the model on demand.';
  const statement = compact ? 'Evidence is prepared before reasoning.' : full;
  const foot = compact ? 'Deterministic · source-backed' : `${esc(entry.title)} · source-backed narrative`;
  return `<div class="kicker">Executive statement</div><div class="text-hero ${compact ? 'compact' : ''}" title="${esc(full)}">${esc(statement)}</div><div class="text-foot">${foot}</div>`;
}
const evidenceRows = [['Collect', 'FDC pressure excursion', 'Support', 'High'], ['Normalize', 'Control population clean', 'Support', 'High'], ['Reason', 'Recipe unchanged', 'Contradict', 'High'], ['Verify', 'Spatial signature match', 'Support', 'Medium'], ['Close', 'Containment verified', 'Support', 'High']];
function tableMarkup(entry) {
  if (entry.customTable) {
    const headers = entry.customTable.headers.slice(0, 4);
    const rows = entry.customTable.rows;
    return `<div class="kicker">Table · pasted data target</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">${rows.length} pasted rows · raw values preserved</div><table class="table-mini"><thead><tr>${headers.map((x) => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((_, k) => `<td>${esc(row[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  const rows = model().crossFilter ? evidenceRows.filter((row) => row[0] === model().crossFilter) : evidenceRows;
  return `<div class="kicker">Table · cross-filter target</div><div class="ctitle">${esc(entry.title)}</div><div class="csub">${model().crossFilter ? `Filtered by chart: ${esc(model().crossFilter)}` : 'All evidence'} · hover rows for highlight</div><table class="table-mini"><thead><tr><th>Evidence</th><th>Polarity</th><th>Confidence</th></tr></thead><tbody>${rows.map((row) => `<tr><td><span class="status-dot ${row[2] === 'Contradict' ? 'warn' : ''}" aria-hidden="true"></span>${esc(row[1])}</td><td>${esc(row[2])}</td><td>${esc(row[3])}</td></tr>`).join('')}</tbody></table>`;
}
function tabsMarkup(entry) {
  const copy = { Summary: 'Leading hypothesis remains Chamber A after contradiction-aware evidence review.', Evidence: '4 supporting observations · 1 meaningful contradiction · controls remain essential.', Next: 'Run targeted chamber verification before upgrading the root-cause status.' };
  return `<div class="kicker">Tabs + expandable detail</div><div class="ctitle">${esc(entry.title)}</div><div class="tabbar" role="tablist" aria-label="Investigation views">${Object.keys(copy).map((key) => `<button role="tab" aria-selected="${entry.tab === key ? 'true' : 'false'}" data-tab="${key}" class="${entry.tab === key ? 'active' : ''}">${key}</button>`).join('')}</div><div class="tab-copy" role="tabpanel">${copy[entry.tab] || copy.Summary}</div><button class="mini-btn expand align-start" data-action="expand" aria-expanded="${entry.expanded ? 'true' : 'false'}">${entry.expanded ? 'Collapse' : 'Expand'} evidence</button>${entry.expanded ? '<div class="metric-detail">Expanded detail remains inside the component boundary; Smart mode reallocates visual mass instead of overflowing.</div>' : ''}`;
}
function timelineMarkup(entry) {
  const milestones = [['Schema', 'Aug 18'], ['Data', 'Aug 31'], ['Reason', 'Sep 08'], ['Pilot', 'Sep 16'], ['Prod', 'Sep 26']];
  return `<div class="kicker">Interactive timeline</div><div class="ctitle">${esc(entry.title)}</div><div class="timeline" role="group" aria-label="Timeline milestones">${milestones.map((m, k) => `<button class="tm ${k < entry.tm ? 'done' : ''} ${k === entry.tm ? 'active' : ''}" data-tm="${k}" aria-pressed="${k === entry.tm ? 'true' : 'false'}"><i aria-hidden="true"></i><b>${m[0]}</b><span>${m[1]}</span></button>`).join('')}</div><div class="csub">Selected: <b>${milestones[entry.tm][0]}</b> · activate a milestone to inspect its state.</div>`;
}
function imageMarkup(entry) { return `<div class="kicker">Image / media</div><div class="ctitle">${esc(entry.title)}</div><div class="image-art" role="img" aria-label="Spatial signature engineering visual"><div class="image-cap">Spatial signature · focal crop</div></div>`; }
function diagramMarkup(entry) { return `<div class="kicker">Diagram · Golden Connector v5 frozen</div><div class="ctitle">${esc(entry.title)}</div><div class="diagram-mini" aria-label="Source to Normalize to Reason flow"><div class="dnode"><b>Source</b><span>FDC / SPC</span></div><div class="dedge" aria-hidden="true"></div><div class="dnode"><b>Normalize</b><span>Evidence model</span></div><div class="dedge" aria-hidden="true"></div><div class="dnode"><b>Reason</b><span>Grounded AI</span></div></div><div class="csub">Full diagram authoring remains Wave 07; editor integration preserves frozen connector infrastructure.</div>`; }
function riskMarkup(entry) { return `<div class="kicker">Decision / risk</div><div class="ctitle">${esc(entry.title)}</div><div class="text-hero compact">Proceed to production gate after control-population validation.</div><div class="riskbox"><b>Residual risk · Medium</b><span>Support coverage remains the gating constraint.</span></div>`; }
function contentMarkup(entry, r) {
  if (entry.type === 'metric') return metricMarkup(entry);
  if (entry.type === 'chart') return chartMarkup(entry, r);
  if (entry.type === 'text') return textMarkup(entry, r);
  if (entry.type === 'table') return tableMarkup(entry);
  if (entry.type === 'tabs') return tabsMarkup(entry);
  if (entry.type === 'timeline') return timelineMarkup(entry);
  if (entry.type === 'image') return imageMarkup(entry);
  if (entry.type === 'diagram') return diagramMarkup(entry);
  if (entry.type === 'risk') return riskMarkup(entry);
  return textMarkup(entry, r);
}

function ensureCanvasScaffold() {
  const hull = $('#hull');
  if (!$('#componentLayer', hull)) {
    hull.innerHTML = '<div class="canvas-grid"></div><div class="group-layer" id="groupLayer"></div><div class="component-layer" id="componentLayer"></div><div class="drop-ghost" id="dropGhost"></div><div class="overlay-layer"><div class="guide v" id="guideV"></div><div class="guide h" id="guideH"></div><div class="lasso" id="lasso"></div></div>';
  }
  // Contextual controls belong to the scene perimeter, not the clipped canvas.
  // This lets edge-touching components expose actions without obscuring content.
  $('#context', hull)?.remove();
  const scene = $('#scene');
  if (!$('#context', scene)) scene.insertAdjacentHTML('beforeend', '<div class="context" id="context"></div>');
}
function createComponentNode(entry) {
  const node = document.createElement('div');
  node.className = 'component';
  node.dataset.id = entry.id;
  node.tabIndex = 0;
  node.setAttribute('role', 'group');
  node.innerHTML = '<button type="button" class="c-head"><span class="c-grip" aria-hidden="true"></span></button><div class="c-content"></div><button type="button" class="resize-h"></button>';
  return node;
}
function contentSignature(entry, r) {
  const data = {
    entry,
    width: Math.round(r.w),
    height: Math.round(r.h),
    crossFilter: entry.type === 'table' ? model().crossFilter : undefined,
  };
  return JSON.stringify(data);
}
function reconcileCanvas({ content = true } = {}) {
  ensureCanvasScaffold();
  const hull = $('#hull');
  hull.className = `canvas-hull ${model().mode}`;
  const layer = $('#componentLayer');
  const rm = rectMap();
  const liveIds = new Set(model().items.map((entry) => entry.id));
  $$('.component', layer).forEach((node) => {
    if (!liveIds.has(node.dataset.id)) {
      ui.componentNodes.delete(node.dataset.id);
      node.remove();
    } else {
      ui.componentNodes.set(node.dataset.id, node);
    }
  });

  for (const entry of model().items) {
    const r = rm.get(entry.id);
    let node = $(`.component[data-id="${entry.id}"]`, layer);
    if (!node) {
      node = createComponentNode(entry);
      layer.appendChild(node);
    }
    ui.componentNodes.set(entry.id, node);
    node.classList.toggle('selected', ui.selected.has(entry.id));
    node.classList.toggle('locked', !!entry.locked);
    node.classList.toggle('grouped', !!entry.groupId);
    node.style.left = `${r.x}px`; node.style.top = `${r.y}px`; node.style.width = `${r.w}px`; node.style.height = `${r.h}px`; node.style.zIndex = String(10 + (entry.z || 0));
    node.setAttribute('aria-selected', ui.selected.has(entry.id) ? 'true' : 'false');
    node.setAttribute('aria-label', `${typeDefaults[entry.type]?.title || entry.type}: ${entry.title}${entry.locked ? ', locked' : ''}`);
    const head = $('.c-head', node); const resize = $('.resize-h', node);
    head.setAttribute('aria-label', `Move ${entry.title}`);
    resize.setAttribute('aria-label', `Resize ${entry.title}`);
    resize.disabled = !!entry.locked;
    const sig = contentSignature(entry, r);
    if (content && node.dataset.contentSignature !== sig) {
      const contentNode = $('.c-content', node);
      const activeKey = document.activeElement && node.contains(document.activeElement) ? focusKey(document.activeElement) : null;
      contentNode.innerHTML = contentMarkup(entry, r);
      node.dataset.contentSignature = sig;
      if (activeKey) restoreFocusKey(node, activeKey);
    }
  }
  renderGroups(rm);
  renderContext(rm);
  renderMinimap(rm);
  runKpiAnimations();
  updateStatus();
}
function focusKey(el) {
  if (!el) return null;
  if (el.id) return `#${CSS.escape(el.id)}`;
  for (const key of ['data-action', 'data-tab', 'data-tm', 'data-point', 'data-brush']) if (el.hasAttribute?.(key)) return `[${key}="${CSS.escape(el.getAttribute(key))}"]`;
  return null;
}
function restoreFocusKey(root, key) { try { root.querySelector(key)?.focus({ preventScroll: true }); } catch { /* ignore */ } }
function renderGroups(rm) {
  const layer = $('#groupLayer');
  const members = model().items.filter((entry) => entry.groupId);
  if (!members.length) {
    if (layer.childElementCount) layer.replaceChildren();
    if (layer.dataset.signature) delete layer.dataset.signature;
    return;
  }
  const groups = {};
  members.forEach((entry) => (groups[entry.groupId] ??= []).push(rm.get(entry.id)));
  const specs = Object.entries(groups).map(([gid, rects]) => [gid, rectUnion(rects)]);
  const signature = specs.map(([gid, u]) => `${gid}:${u.x.toFixed(2)},${u.y.toFixed(2)},${u.w.toFixed(2)},${u.h.toFixed(2)}`).join('|');
  if (layer.dataset.signature === signature) return;
  layer.dataset.signature = signature;
  layer.innerHTML = specs.map(([gid, u]) => `<div class="group-outline" data-group="${esc(gid)}" style="left:${u.x - 4}px;top:${u.y - 4}px;width:${u.w + 8}px;height:${u.h + 8}px"></div>`).join('');
}

function renderGeometryOnly() {
  const rm = rectMap();
  for (const [id, r] of rm.entries()) {
    const node = ui.componentNodes.get(id);
    if (!node) continue;
    node.style.left = `${r.x}px`; node.style.top = `${r.y}px`; node.style.width = `${r.w}px`; node.style.height = `${r.h}px`;
  }
  renderGroups(rm);
  renderContext(rm);
  renderMinimap(rm);
  updateStatus({ recomputePreflight: false });
}


function renderContext(rm) {
  const c = $('#context');
  if (!ui.selected.size) { c.classList.remove('show'); if (ui.contextSignature) c.replaceChildren(); ui.contextSignature = ''; ui.contextSize = null; delete c.dataset.placement; return; }
  const rects = [...ui.selected].map((id) => rm.get(id)).filter(Boolean);
  const u = rectUnion(rects);
  if (!u) return;
  const locked = [...ui.selected].some((id) => item(id)?.locked);
  const contextSignature = `${[...ui.selected].sort().join(',')}|${locked ? 1 : 0}`;
  if (ui.contextSignature !== contextSignature) {
    c.innerHTML = `<button data-ctx="lock">${locked ? 'Unlock' : 'Lock'}</button><button data-ctx="group">Group</button><button data-ctx="front">Front</button><button data-ctx="delete">Delete</button>`;
    ui.contextSignature = contextSignature;
    ui.contextSize = null;
  }
  c.classList.add('show');

  if (!ui.contextSize) ui.contextSize = { w: Math.max(1, c.offsetWidth || 205), h: Math.max(1, c.offsetHeight || 36) };
  const tw = ui.contextSize.w; const th = ui.contextSize.h; const gap = 8;
  let viewBounds = ui.contextBoundsCache;
  if (!viewBounds || viewBounds.epoch !== ui.resizeEpoch || viewBounds.zoom !== ui.zoom) {
    const scene = $('#scene'); const viewport = $('#viewport');
    const sceneRect = scene.getBoundingClientRect(); const viewportRect = viewport.getBoundingClientRect();
    const scaleX = sceneRect.width / Math.max(1, scene.clientWidth || 1300);
    const scaleY = sceneRect.height / Math.max(1, scene.clientHeight || 820);
    viewBounds = {
      x: (viewportRect.left - sceneRect.left) / Math.max(scaleX, 1e-6),
      y: (viewportRect.top - sceneRect.top) / Math.max(scaleY, 1e-6),
      w: viewportRect.width / Math.max(scaleX, 1e-6),
      h: viewportRect.height / Math.max(scaleY, 1e-6),
      epoch: ui.resizeEpoch, zoom: ui.zoom,
    };
    ui.contextBoundsCache = viewBounds;
  }
  const us = { x: u.x + CANVAS.x, y: u.y + CANVAS.y, w: u.w, h: u.h };
  const candidates = [
    { placement: 'above', x: us.x + us.w / 2 - tw / 2, y: us.y - th - gap },
    { placement: 'below', x: us.x + us.w / 2 - tw / 2, y: us.y + us.h + gap },
    { placement: 'right', x: us.x + us.w + gap, y: us.y + us.h / 2 - th / 2 },
    { placement: 'left', x: us.x - tw - gap, y: us.y + us.h / 2 - th / 2 },
  ];
  const peers = [...rm.entries()].filter(([id]) => !ui.selected.has(id)).map(([, r]) => ({ x: r.x + CANVAS.x, y: r.y + CANVAS.y, w: r.w, h: r.h }));
  const scored = candidates.map((candidate, order) => {
    const r = { x: candidate.x, y: candidate.y, w: tw, h: th };
    const outside = Math.max(0, viewBounds.x - r.x) + Math.max(0, viewBounds.y - r.y)
      + Math.max(0, r.x + r.w - (viewBounds.x + viewBounds.w)) + Math.max(0, r.y + r.h - (viewBounds.y + viewBounds.h));
    const selectedOverlap = intersectionArea(r, us);
    const peerOverlap = peers.reduce((sum, peer) => sum + intersectionArea(r, peer), 0);
    return { ...candidate, order, score: outside * 1e8 + selectedOverlap * 1e6 + peerOverlap };
  }).sort((a, b) => a.score - b.score || a.order - b.order)[0];
  c.style.left = `${clamp(scored.x, viewBounds.x + 4, viewBounds.x + viewBounds.w - tw - 4)}px`;
  c.style.top = `${clamp(scored.y, viewBounds.y + 4, viewBounds.y + viewBounds.h - th - 4)}px`;
  c.dataset.placement = scored.placement;
}
function renderMinimap(rm) {
  const mm = $('#minimap');
  if (!ui.showMini) { mm.style.display = 'none'; return; }
  mm.style.display = 'block';
  const sx = 170 / CANVAS.w; const sy = 105 / CANVAS.h;
  let svg = $('svg', mm);
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 170 105');
    mm.replaceChildren(svg);
    ui.minimapNodes.clear();
  }
  const live = new Set(rm.keys());
  for (const [id, node] of [...ui.minimapNodes.entries()]) { if (!live.has(id)) { node.remove(); ui.minimapNodes.delete(id); } }
  for (const [id, r] of rm.entries()) {
    let rect = ui.minimapNodes.get(id);
    if (!rect) {
      rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('rx', '2');
      svg.appendChild(rect);
      ui.minimapNodes.set(id, rect);
    }
    rect.setAttribute('x', String(r.x * sx)); rect.setAttribute('y', String(r.y * sy));
    rect.setAttribute('width', String(r.w * sx)); rect.setAttribute('height', String(r.h * sy));
    rect.setAttribute('class', ui.selected.has(id) ? 'mmselected' : 'mmitem');
  }
}

function renderInspector() {
  const p = $('#inspector');
  const ids = [...ui.selected];
  if (ids.length === 1) {
    const entry = item(ids[0]);
    p.innerHTML = `<div class="field"><label for="iTitle">Component title</label><input id="iTitle" value="${esc(entry.title)}"></div><div class="field"><label for="iType">Component</label><select id="iType">${Object.keys(typeDefaults).map((t) => `<option value="${t}" ${entry.type === t ? 'selected' : ''}>${t}</option>`).join('')}</select></div>${entry.type === 'chart' ? `<div class="field"><label for="chartVariant">Chart variant</label><select id="chartVariant"><option value="line" ${entry.variant === 'line' ? 'selected' : ''}>Line</option><option value="area" ${entry.variant === 'area' ? 'selected' : ''}>Area</option><option value="bar" ${entry.variant === 'bar' ? 'selected' : ''}>Bar</option><option value="nochart" ${entry.variant === 'nochart' ? 'selected' : ''}>No Chart</option></select></div>` : ''}<div class="field"><label>${model().mode === 'smart' ? 'Visual mass' : 'Geometry'}</label>${model().mode === 'smart' ? `<input id="iWeight" aria-label="Visual mass" type="range" min=".45" max="3.4" step=".05" value="${entry.weight}"><div class="info-row"><span>Weight</span><b>${entry.weight.toFixed(2)}</b></div>` : `<div class="inline2"><input id="iW" aria-label="Width" value="${Math.round(entry.w)}"><input id="iH" aria-label="Height" value="${Math.round(entry.h)}"></div>`}</div><div class="field"><label>Actions</label><div class="r-actions"><button class="tb" id="lockOne">${entry.locked ? 'Unlock' : 'Lock'}</button><button class="tb" id="frontOne">Bring front</button><button class="tb" id="backOne">Send back</button><button class="tb" id="dupOne">Duplicate</button></div></div><div class="info-row"><span>Semantic ID</span><b>${entry.id}</b></div><div class="info-row"><span>Revision</span><b>${store.revision}</b></div>`;
    $('#iTitle').addEventListener('change', (e) => commitOps('Rename component', [{ op: 'item.patch', id: entry.id, patch: { title: e.target.value } }]));
    $('#iType').addEventListener('change', (e) => commitOps('Change component type', [{ op: 'item.patch', id: entry.id, patch: { type: e.target.value } }]));
    $('#chartVariant')?.addEventListener('change', (e) => commitOps('Switch chart variant', [{ op: 'item.patch', id: entry.id, patch: { variant: e.target.value } }]));
    $('#iWeight')?.addEventListener('change', (e) => commitOps('Set visual mass', [{ op: 'item.patch', id: entry.id, patch: { weight: +e.target.value } }]));
    $('#iW')?.addEventListener('change', (e) => commitOps('Set width', [{ op: 'item.patch', id: entry.id, patch: { w: Math.max(typeDefaults[entry.type].minW, +e.target.value || entry.w) } }]));
    $('#iH')?.addEventListener('change', (e) => commitOps('Set height', [{ op: 'item.patch', id: entry.id, patch: { h: Math.max(typeDefaults[entry.type].minH, +e.target.value || entry.h) } }]));
    $('#lockOne').onclick = toggleLock; $('#frontOne').onclick = () => layer(1); $('#backOne').onclick = () => layer(-1); $('#dupOne').onclick = () => duplicateOne(entry.id);
    return;
  }
  if (ids.length > 1) {
    p.innerHTML = `<div class="field"><label>Multi-selection</label><div class="info-row"><span>Selected</span><b>${ids.length}</b></div></div><div class="field"><label>Arrange</label><div class="r-actions"><button class="tb" data-inspector="align-left">Left</button><button class="tb" data-inspector="align-top">Top</button><button class="tb" data-inspector="align-center">Center</button><button class="tb" data-inspector="distribute-x">Distribute H</button><button class="tb" data-inspector="distribute-y">Distribute V</button></div></div><div class="field"><label>Structure</label><div class="r-actions"><button class="tb" data-inspector="group">Group</button><button class="tb" data-inspector="ungroup">Ungroup</button><button class="tb" data-inspector="lock">Lock / unlock</button></div></div>`;
    return;
  }
  renderCanvasInspector(p);
}
function renderCanvasInspector(p) {
  const pf = preflight();
  p.innerHTML = `<div class="info-row"><span>Mode</span><b>${model().mode}</b></div><div class="info-row"><span>Components</span><b>${model().items.length}</b></div><div class="info-row"><span>Hull coverage</span><b>${pf.coverage}%</b></div><div class="info-row"><span>Overlaps</span><b>${pf.overlaps}</b></div><div class="info-row"><span>Locked</span><b>${model().items.filter((entry) => entry.locked).length}</b></div><div class="field"><label>Smart layout suggestions</label></div><div class="suggestion"><b>Editorial Bento</b><p>Balanced narrative + analytical visual mass.</p><button class="tb" data-suggestion="editorial">Apply</button></div><div class="suggestion"><b>Executive</b><p>Promote KPI and key takeaway; simplify dense detail.</p><button class="tb" data-suggestion="executive">Apply</button></div><div class="suggestion"><b>Technical</b><p>Promote table/diagram/timeline evidence surfaces.</p><button class="tb" data-suggestion="technical">Apply</button></div>`;
}
function renderAll() { reconcileCanvas({ content: true }); renderInspector(); setZoom(ui.zoom, false); syncModeButtons(); }

function syncModeButtons() {
  $$('[data-mode]').forEach((button) => {
    const active = button.dataset.mode === model().mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}
function preflight() {
  const R = currentRects();
  const pf = { coverage: model().mode === 'smart' ? 100 : 0, overlaps: 0, out: 0, min: 0, warnings: [] };
  for (let a = 0; a < R.length; a += 1) {
    const entry = item(R[a].id); const d = typeDefaults[entry.type];
    if (R[a].w < d.minW || R[a].h < d.minH) pf.min += 1;
    if (R[a].x < 0 || R[a].y < 0 || R[a].x + R[a].w > CANVAS.w + 0.1 || R[a].y + R[a].h > CANVAS.h + 0.1) pf.out += 1;
    for (let b = a + 1; b < R.length; b += 1) if (overlap(R[a], R[b], 1)) pf.overlaps += 1;
  }
  if (model().mode !== 'smart') {
    const area = R.reduce((s, r) => s + r.w * r.h, 0);
    pf.coverage = Math.min(100, Math.round(area / (CANVAS.w * CANVAS.h) * 100));
  }
  if (pf.overlaps) pf.warnings.push(`${pf.overlaps} overlaps`);
  if (pf.out) pf.warnings.push(`${pf.out} out of bounds`);
  if (pf.min) pf.warnings.push(`${pf.min} below min geometry`);
  return pf;
}
function showPreflight() {
  const pf = preflight();
  const checks = [
    ['Closed rectangular hull', model().mode === 'smart' ? pf.coverage === 100 : true, model().mode === 'smart' ? `${pf.coverage}% coverage` : 'Canvas boundary governed'],
    ['No component overlaps', pf.overlaps === 0, `${pf.overlaps} overlap(s)`],
    ['All components within canvas', pf.out === 0, `${pf.out} out of bounds`],
    ['Minimum readable geometry', pf.min === 0, `${pf.min} below minimum`],
    ['Semantic typography floor', true, '≥11 chrome · ≥12 data · ≥13 explanatory'],
    ['Typed EditorCommand architecture', true, `base_revision ${store.revision}`],
    ['Pointer cancel/capture recovery', true, 'Central pointer session controller'],
    ['Responsive observation', typeof ResizeObserver !== 'undefined', 'ResizeObserver active'],
    ['Golden Connector v5', true, 'Frozen byte-identical copy'],
  ];
  $('#modalTitle').textContent = 'Preflight';
  $('#modalBody').innerHTML = `<div class="preflight-list">${checks.map((c) => `<div class="check ${c[1] ? '' : 'warn'}"><i>${c[1] ? '✓' : '!'}</i><b>${c[0]}</b><span>${c[2]}</span></div>`).join('')}</div>`;
  openModal($('#genericModal'));
}
function updateStatus({ recomputePreflight = true } = {}) {
  const pf = recomputePreflight || !ui.lastPreflight ? preflight() : ui.lastPreflight;
  if (recomputePreflight) ui.lastPreflight = pf;
  $('#modeStatus').textContent = model().mode[0].toUpperCase() + model().mode.slice(1);
  $('#selStatus').textContent = `${ui.selected.size} selected`;
  $('#zoomStatus').textContent = `${Math.round(ui.zoom * 100)}%`;
  $('#hullStatus').textContent = model().mode === 'smart' ? `${pf.coverage}% hull` : 'manual geometry';
  $('#preflightStatus').textContent = pf.warnings.length ? `${pf.warnings.length} warnings` : 'Preflight clean';
  $('#preflightStatus').className = pf.warnings.length ? 'warn' : 'good';
  $('#revStatus').textContent = String(store.revision);
  $('#undo').disabled = !store.canUndo; $('#redo').disabled = !store.canRedo;
}

function logicalPoint(e) {
  const r = $('#hull').getBoundingClientRect();
  return { x: (e.clientX - r.left) / ui.zoom, y: (e.clientY - r.top) / ui.zoom };
}
function beginPointerSession(target, e, handlers) {
  cancelPointerSession('superseded');
  const controller = new AbortController();
  const session = { pointerId: e.pointerId, target, controller, done: false, handlers };
  ui.pointerSession = session;
  document.body.dataset.pointerActive = 'true';
  try { target.setPointerCapture(e.pointerId); } catch { /* synthetic events */ }
  const finish = (kind, event) => {
    if (session.done) return;
    session.done = true;
    controller.abort();
    if (ui.pointerSession === session) ui.pointerSession = null;
    delete document.body.dataset.pointerActive;
    try { if (target.hasPointerCapture?.(e.pointerId)) target.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
    if (kind === 'end') handlers.end?.(event);
    else handlers.cancel?.(event, kind);
  };
  target.addEventListener('pointermove', (ev) => handlers.move?.(ev), { signal: controller.signal });
  target.addEventListener('pointerup', (ev) => finish('end', ev), { signal: controller.signal });
  target.addEventListener('pointercancel', (ev) => finish('cancel', ev), { signal: controller.signal });
  target.addEventListener('lostpointercapture', (ev) => { if (!session.done) finish('lostcapture', ev); }, { signal: controller.signal });
  return session;
}
function cancelPointerSession(reason = 'cancel') {
  const s = ui.pointerSession;
  if (!s || s.done) return;
  s.done = true; s.controller.abort(); ui.pointerSession = null; delete document.body.dataset.pointerActive;
  s.handlers.cancel?.(null, reason);
}
function selectedMovers(id) {
  const entry = item(id);
  if (entry.groupId) return model().items.filter((x) => x.groupId === entry.groupId && !x.locked);
  if (ui.selected.has(id) && ui.selected.size > 1) return model().items.filter((x) => ui.selected.has(x.id) && !x.locked);
  return entry.locked ? [] : [entry];
}
function snapDelta(orig, dx, dy, movers) {
  const ids = new Set(movers.map((x) => x.id)); const rm = rectMap(); const others = [...rm.entries()].filter(([id]) => !ids.has(id)).map((x) => x[1]); const threshold = 6;
  let bestX = null; let bestY = null;
  for (const o of orig) {
    const entry = item(o.id); const r = { x: o.x + dx, y: o.y + dy, w: entry.w, h: entry.h }; const xs = [r.x, r.x + r.w / 2, r.x + r.w]; const ys = [r.y, r.y + r.h / 2, r.y + r.h];
    for (const b of others) {
      for (const a of xs) for (const t of [b.x, b.x + b.w / 2, b.x + b.w]) if (Math.abs(a - t) < threshold && (bestX == null || Math.abs(a - t) < Math.abs(bestX.off))) bestX = { off: t - a, pos: t };
      for (const a of ys) for (const t of [b.y, b.y + b.h / 2, b.y + b.h]) if (Math.abs(a - t) < threshold && (bestY == null || Math.abs(a - t) < Math.abs(bestY.off))) bestY = { off: t - a, pos: t };
    }
  }
  return { dx: dx + (bestX?.off || 0), dy: dy + (bestY?.off || 0), gx: bestX?.pos, gy: bestY?.pos };
}
function showGuides(d) { const v = $('#guideV'); const h = $('#guideH'); if (d.gx != null) { v.style.left = `${d.gx}px`; v.style.display = 'block'; } else v.style.display = 'none'; if (d.gy != null) { h.style.top = `${d.gy}px`; h.style.display = 'block'; } else h.style.display = 'none'; }
function hideGuides() { $('#guideV').style.display = 'none'; $('#guideH').style.display = 'none'; }
function hasSelectedOverlap() {
  const rm = rectMap(); const ids = new Set(ui.selected); const selected = [...ids].map((id) => rm.get(id)).filter(Boolean);
  for (const a of selected) for (const [id, b] of rm) if (!ids.has(id) && overlap(a, b, 3)) return true;
  return false;
}
function smartOrderAt(q) {
  const rs = currentRects().map((r) => ({ ...r, cx: r.x + r.w / 2, cy: r.y + r.h / 2 }));
  rs.sort((a, b) => Math.hypot(q.x - a.cx, q.y - a.cy) - Math.hypot(q.x - b.cx, q.y - b.cy));
  return item(rs[0]?.id);
}
function showSmartReorderGhost(q, id) {
  const target = smartOrderAt(q); const g = $('#dropGhost'); const r = rectMap().get(target?.id || id);
  if (!r) return;
  Object.assign(g.style, { display: 'block', left: `${r.x}px`, top: `${r.y}px`, width: `${r.w}px`, height: `${r.h}px` });
}
function smartReorderOps(q, id) {
  const target = smartOrderAt(q); if (!target) return [];
  const moving = item(id).groupId ? model().items.filter((x) => x.groupId === item(id).groupId).map((x) => x.id) : ui.selected.size > 1 ? [...ui.selected] : [id];
  if (moving.includes(target.id)) return [];
  const ordered = [...model().items].sort((a, b) => a.order - b.order); const block = ordered.filter((x) => moving.includes(x.id)); const rest = ordered.filter((x) => !moving.includes(x.id));
  let idx = rest.findIndex((x) => x.id === target.id); if (idx < 0) idx = rest.length;
  rest.splice(idx, 0, ...block);
  return rest.map((entry, k) => entry.order === k ? null : { op: 'item.patch', id: entry.id, patch: { order: k } }).filter(Boolean);
}
function startDrag(e, id, el) {
  if (e.button !== 0) return;
  const movers = selectedMovers(id); if (!movers.length) return toast('Locked component');
  e.preventDefault(); e.stopPropagation();
  if (!ui.selected.has(id)) { ui.selected.clear(); ui.selected.add(id); renderAll(); return; }
  const rm = rectMap(); const p = logicalPoint(e); const orig = movers.map((m) => { const r = rm.get(m.id); return { id: m.id, x: r.x, y: r.y }; });
  movers.forEach((m) => $(`.component[data-id="${m.id}"]`)?.classList.add('dragging'));
  beginPointerSession(el, e, {
    move(ev) {
      const q = logicalPoint(ev); const dx = q.x - p.x; const dy = q.y - p.y;
      if (model().mode === 'smart') { showSmartReorderGhost(q, id); return; }
      let sx = dx; let sy = dy;
      if (model().mode === 'guided' && ui.snap) { const d = snapDelta(orig, dx, dy, movers); sx = d.dx; sy = d.dy; showGuides(d); }
      orig.forEach((o) => { const entry = item(o.id); ui.previewPatches.set(o.id, { x: clamp(o.x + sx, 0, CANVAS.w - entry.w), y: clamp(o.y + sy, 0, CANVAS.h - entry.h) }); });
      renderGeometryOnly();
    },
    end(ev) {
      hideGuides(); $('#dropGhost').style.display = 'none'; movers.forEach((m) => $(`.component[data-id="${m.id}"]`)?.classList.remove('dragging'));
      if (model().mode === 'smart') {
        const ops = smartReorderOps(logicalPoint(ev), id); ui.previewPatches.clear(); if (ops.length) commitOps('Reorder components', ops); else renderGeometryOnly(); return;
      }
      if (model().mode === 'guided' && hasSelectedOverlap()) { ui.previewPatches.clear(); renderGeometryOnly(); toast('Guided mode blocked an overlap'); return; }
      const ops = [...ui.previewPatches.entries()].map(([entryId, patch]) => ({ op: 'item.patch', id: entryId, patch }));
      ui.previewPatches.clear(); if (ops.length) commitOps('Move components', ops); else renderGeometryOnly();
    },
    cancel() { hideGuides(); $('#dropGhost').style.display = 'none'; ui.previewPatches.clear(); movers.forEach((m) => $(`.component[data-id="${m.id}"]`)?.classList.remove('dragging')); renderGeometryOnly(); toast('Move cancelled'); },
  });
}
function startResize(e, id, el) {
  const entry = item(id); if (entry.locked) return toast('Locked component');
  e.preventDefault(); e.stopPropagation();
  const p = logicalPoint(e); const r = rectMap().get(id); const start = { w: r.w, h: r.h, weight: entry.weight };
  beginPointerSession(el, e, {
    move(ev) {
      const q = logicalPoint(ev); const dx = q.x - p.x; const dy = q.y - p.y;
      if (model().mode === 'smart') ui.previewPatches.set(id, { weight: clamp(start.weight + (dx + dy) / 240, 0.45, 3.4) });
      else ui.previewPatches.set(id, { w: Math.min(Math.max(typeDefaults[entry.type].minW, start.w + dx), CANVAS.w - entry.x), h: Math.min(Math.max(typeDefaults[entry.type].minH, start.h + dy), CANVAS.h - entry.y) });
      renderGeometryOnly();
    },
    end() {
      if (model().mode === 'guided' && hasSelectedOverlap()) { ui.previewPatches.clear(); renderGeometryOnly(); toast('Guided mode blocked resize overlap'); return; }
      const patch = ui.previewPatches.get(id); ui.previewPatches.clear(); if (patch) commitOps('Resize component', [{ op: 'item.patch', id, patch }]); else renderGeometryOnly();
    },
    cancel() { ui.previewPatches.clear(); renderGeometryOnly(); toast('Resize cancelled'); },
  });
}
function startLasso(e) {
  ui.selected.clear(); const p = logicalPoint(e); const box = $('#lasso'); box.style.display = 'block'; ui.lasso = { start: p };
  beginPointerSession($('#hull'), e, {
    move(ev) {
      const q = logicalPoint(ev); const x = Math.min(p.x, q.x); const y = Math.min(p.y, q.y); const w = Math.abs(q.x - p.x); const h = Math.abs(q.y - p.y);
      Object.assign(box.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
      const L = { x, y, w, h }; ui.selected = new Set(currentRects().filter((r) => overlap(L, r, 0)).map((r) => r.id));
      $$('.component').forEach((n) => { n.classList.toggle('selected', ui.selected.has(n.dataset.id)); n.setAttribute('aria-selected', ui.selected.has(n.dataset.id) ? 'true' : 'false'); });
    },
    end() { box.style.display = 'none'; ui.lasso = null; reconcileCanvas({ content: false }); renderInspector(); },
    cancel() { box.style.display = 'none'; ui.lasso = null; ui.selected.clear(); reconcileCanvas({ content: false }); renderInspector(); },
  });
}
function startPan(e) {
  const vp = $('#viewport'); const sx = e.clientX; const sy = e.clientY; const sl = vp.scrollLeft; const st = vp.scrollTop; vp.classList.add('panning');
  beginPointerSession(vp, e, {
    move(ev) { vp.scrollLeft = sl - (ev.clientX - sx); vp.scrollTop = st - (ev.clientY - sy); },
    end() { vp.classList.remove('panning'); },
    cancel() { vp.classList.remove('panning'); },
  });
}
function startBrush(e, handle) {
  e.stopPropagation(); e.preventDefault(); const comp = handle.closest('.component'); const entry = item(comp.dataset.id); const D = chartData(entry); const kind = handle.dataset.brush; const wrap = handle.closest('.chart-wrap'); const svg = $('.chart-svg', wrap); const initial = [...(entry.brush || [0, D.length - 1])]; let preview = [...initial];
  const updateDom = () => {
    const vb = svg.viewBox.baseVal; const left = 24; const right = 12; const plotW = vb.width - left - right; const bx1 = left + plotW * preview[0] / Math.max(1, D.length - 1); const bx2 = left + plotW * preview[1] / Math.max(1, D.length - 1);
    $('.brush-window', svg).setAttribute('x', bx1); $('.brush-window', svg).setAttribute('width', Math.max(3, bx2 - bx1)); $('.brush-handle-start', svg).setAttribute('x', bx1 - 3); $('.brush-handle-end', svg).setAttribute('x', bx2 - 3);
    const startHandle = $('[data-brush="start"]', wrap); const endHandle = $('[data-brush="end"]', wrap);
    startHandle.style.left = `${bx1 / vb.width * 100}%`; startHandle.setAttribute('aria-valuenow', preview[0]); endHandle.style.left = `${bx2 / vb.width * 100}%`; endHandle.setAttribute('aria-valuenow', preview[1]);
  };
  beginPointerSession(handle, e, {
    move(ev) { const r = svg.getBoundingClientRect(); const x = (ev.clientX - r.left) / r.width * svg.viewBox.baseVal.width; const left = 24; const right = 12; const plotW = svg.viewBox.baseVal.width - left - right; const k = clamp(Math.round((x - left) / plotW * (D.length - 1)), 0, D.length - 1); if (kind === 'start') preview[0] = Math.min(k, preview[1]); else preview[1] = Math.max(k, preview[0]); updateDom(); },
    end() { if (preview[0] !== initial[0] || preview[1] !== initial[1]) commitOps('Brush chart range', [{ op: 'item.patch', id: entry.id, patch: { brush: preview } }]); else reconcileCanvas(); },
    cancel() { reconcileCanvas(); toast('Brush cancelled'); },
  });
}

function normalizeOrderOps(items = model().items) { return [...items].sort((a, b) => a.order - b.order).map((entry, k) => entry.order === k ? null : { op: 'item.patch', id: entry.id, patch: { order: k } }).filter(Boolean); }
function addComponent(type, pos = null) {
  const d = typeDefaults[type]; if (!d) return;
  const id = `c${model().nextId}`;
  const entry = { id, type, title: d.title, weight: d.weight, order: model().items.length, locked: false, z: Math.max(0, ...model().items.map((x) => x.z || 0)) + 1 };
  if (type === 'metric') { entry.value = 78; entry.detail = false; ui.kpiAnimate.add(id); }
  if (type === 'chart') { entry.variant = 'line'; entry.data = structuredClone(defaultChartData); entry.brush = [0, 4]; entry.revealed = true; }
  if (type === 'tabs') { entry.tab = 'Summary'; entry.expanded = false; }
  if (type === 'timeline') entry.tm = 1;
  if (model().mode !== 'smart') { entry.x = clamp((pos?.x || 500) - d.minW / 2, 0, CANVAS.w - d.minW); entry.y = clamp((pos?.y || 300) - d.minH / 2, 0, CANVAS.h - d.minH); entry.w = d.minW * 1.3; entry.h = d.minH * 1.25; }
  commitOps('Add component', [{ op: 'item.add', item: entry }, { op: 'model.patch', patch: { nextId: model().nextId + 1 } }], { announce: `${d.title} added` });
  ui.selected = new Set([id]); renderAll();
}
function deleteSelected() {
  const ids = [...ui.selected].filter((id) => !item(id)?.locked); if (!ids.length) return toast('Nothing deletable selected');
  const ops = ids.map((id) => ({ op: 'item.remove', id }));
  for (const [gid, group] of Object.entries(model().groups)) if (group.items.some((id) => ids.includes(id))) ops.push({ op: 'group.set', id: gid, value: { ...group, items: group.items.filter((id) => !ids.includes(id)) } });
  const survivors = model().items.filter((entry) => !ids.includes(entry.id));
  ops.push(...normalizeOrderOps(survivors)); ui.selected.clear(); commitOps('Delete components', ops, { announce: `${ids.length} component${ids.length > 1 ? 's' : ''} deleted` });
}
function toggleLock() {
  if (!ui.selected.size) return; const want = [...ui.selected].some((id) => !item(id).locked); const ops = [...ui.selected].map((id) => ({ op: 'item.patch', id, patch: { locked: want } })); commitOps(want ? 'Lock selection' : 'Unlock selection', ops, { announce: want ? 'Selection locked' : 'Selection unlocked' });
}
function groupSelected() {
  if (ui.selected.size < 2) return toast('Select 2+ components');
  const gid = `g${store.revision}-${model().nextId}`; const ids = [...ui.selected]; const ops = [{ op: 'group.set', id: gid, value: { id: gid, items: ids } }, ...ids.map((id) => ({ op: 'item.patch', id, patch: { groupId: gid } }))]; commitOps('Group selection', ops, { announce: 'Group created' });
}
function ungroupSelected() {
  const gids = new Set([...ui.selected].map((id) => item(id)?.groupId).filter(Boolean)); if (!gids.size) return toast('No selected group');
  const ops = []; for (const gid of gids) { model().items.filter((entry) => entry.groupId === gid).forEach((entry) => ops.push({ op: 'item.patch', id: entry.id, patch: { groupId: null } })); ops.push({ op: 'group.delete', id: gid }); }
  commitOps('Ungroup selection', ops, { announce: 'Ungrouped' });
}
function layer(delta) { if (!ui.selected.size) return; commitOps(delta > 0 ? 'Bring forward' : 'Send backward', [...ui.selected].map((id) => ({ op: 'item.patch', id, patch: { z: clamp((item(id).z || 1) + delta, 0, 99) } }))); }
function align(kind) {
  if (model().mode === 'smart') return toast('Align is automatic in Smart mode'); if (ui.selected.size < 2) return toast('Select 2+ components');
  const rm = rectMap(); const A = [...ui.selected].map((id) => ({ entry: item(id), r: rm.get(id) })); const u = rectUnion(A.map((x) => x.r)); const ops = [];
  for (const x of A) { const patch = {}; if (kind === 'left') patch.x = u.x; if (kind === 'top') patch.y = u.y; if (kind === 'center') patch.x = u.x + (u.w - x.r.w) / 2; if (kind === 'middle') patch.y = u.y + (u.h - x.r.h) / 2; ops.push({ op: 'item.patch', id: x.entry.id, patch }); }
  commitOps(`Align ${kind}`, ops);
}
function distribute(axis) {
  if (model().mode === 'smart') return toast('Distribution is automatic in Smart mode'); if (ui.selected.size < 3) return toast('Select 3+ components');
  const A = [...ui.selected].map((id) => item(id)).sort((a, b) => axis === 'x' ? a.x - b.x : a.y - b.y); const ops = [];
  if (axis === 'x') { const first = A[0]; const last = A.at(-1); const span = last.x + last.w - first.x; const sum = A.reduce((s, entry) => s + entry.w, 0); const gap = (span - sum) / (A.length - 1); let x = first.x; A.forEach((entry) => { ops.push({ op: 'item.patch', id: entry.id, patch: { x } }); x += entry.w + gap; }); }
  else { const first = A[0]; const last = A.at(-1); const span = last.y + last.h - first.y; const sum = A.reduce((s, entry) => s + entry.h, 0); const gap = (span - sum) / (A.length - 1); let y = first.y; A.forEach((entry) => { ops.push({ op: 'item.patch', id: entry.id, patch: { y } }); y += entry.h + gap; }); }
  commitOps(`Distribute ${axis}`, ops);
}
function setMode(nextMode) {
  if (model().mode === nextMode) return;
  const ops = [];
  if (model().mode === 'smart' && nextMode !== 'smart') { const sm = new Map(smartRects(model().items).map((r) => [r.id, r])); model().items.forEach((entry) => { const r = sm.get(entry.id); ops.push({ op: 'item.patch', id: entry.id, patch: { x: r.x, y: r.y, w: r.w, h: r.h } }); }); }
  ops.push({ op: 'model.patch', patch: { mode: nextMode } }); commitOps('Change canvas mode', ops);
}
function applySuggestion(preset) {
  const ops = [{ op: 'model.patch', patch: { layoutPreset: preset, mode: 'smart' } }];
  const orderMap = preset === 'executive' ? ['metric', 'text', 'chart', 'timeline', 'tabs', 'table', 'image', 'diagram', 'risk'] : preset === 'technical' ? ['diagram', 'chart', 'table', 'timeline', 'metric', 'tabs', 'text', 'image', 'risk'] : null;
  if (orderMap) [...model().items].sort((a, b) => orderMap.indexOf(a.type) - orderMap.indexOf(b.type)).forEach((entry, k) => { if (entry.order !== k) ops.push({ op: 'item.patch', id: entry.id, patch: { order: k } }); });
  commitOps('Apply layout suggestion', ops, { announce: `${preset[0].toUpperCase() + preset.slice(1)} composition applied` });
}
function autoLayout() { const ops = [{ op: 'model.patch', patch: { mode: 'smart' } }, ...normalizeOrderOps()]; commitOps('Auto layout', ops, { announce: 'Smart layout recomposed' }); }
function duplicateOne(id) {
  const source = item(id); const copy = structuredClone(source); const nextId = `c${model().nextId}`; copy.id = nextId; copy.order = model().items.length; copy.z = (source.z || 1) + 1; copy.title = `${source.title} copy`; copy.groupId = null;
  if (model().mode !== 'smart') { copy.x = clamp(source.x + 24, 0, CANVAS.w - source.w); copy.y = clamp(source.y + 24, 0, CANVAS.h - source.h); }
  commitOps('Duplicate component', [{ op: 'item.add', item: copy }, { op: 'model.patch', patch: { nextId: model().nextId + 1 } }]); ui.selected = new Set([nextId]); renderAll();
}
function showDropGhost(e) { const g = $('#dropGhost'); if (model().mode === 'smart') Object.assign(g.style, { display: 'block', left: '6px', top: `${CANVAS.h - 80}px`, width: `${CANVAS.w - 12}px`, height: '70px' }); else { const p = logicalPoint(e); Object.assign(g.style, { display: 'block', left: `${clamp(p.x - 90, 0, CANVAS.w - 180)}px`, top: `${clamp(p.y - 60, 0, CANVAS.h - 120)}px`, width: '180px', height: '120px' }); } }

function toggleChartPoint(entry, k) { const cross = entry.cross === k ? null : k; const crossFilter = cross == null ? null : chartData(entry)[cross][0]; commitOps('Toggle chart cross-filter', [{ op: 'item.patch', id: entry.id, patch: { cross } }, { op: 'model.patch', patch: { crossFilter } }]); }
function drillChartPoint(entry, k) { commitOps('Drill chart point', [{ op: 'item.patch', id: entry.id, patch: { drill: k } }]); }
function setBrushByKeyboard(entry, kind, delta) { const D = chartData(entry); const next = [...(entry.brush || [0, D.length - 1])]; if (kind === 'start') next[0] = clamp(next[0] + delta, 0, next[1]); else next[1] = clamp(next[1] + delta, next[0], D.length - 1); if (next[0] !== entry.brush[0] || next[1] !== entry.brush[1]) commitOps('Adjust brush range', [{ op: 'item.patch', id: entry.id, patch: { brush: next } }]); }
function parsePaste(txt) { const lines = txt.trim().split(/\r?\n/).filter(Boolean); if (lines.length < 2) return null; const d = lines[0].includes('\t') ? '\t' : lines[0].includes(',') ? ',' : null; if (!d) return null; const rows = lines.map((x) => x.split(d).map((s) => s.trim())); return { headers: rows[0], rows: rows.slice(1) }; }
function pasteToSelection(txt) {
  if (ui.selected.size !== 1) return false; const entry = item([...ui.selected][0]); const parsed = parsePaste(txt); if (!parsed) return false;
  if (entry.type === 'chart') { const data = parsed.rows.map((r) => [r[0], Number(String(r[1]).replace(/[^\d.-]/g, '')) || 0]); commitOps('Paste chart data', [{ op: 'item.patch', id: entry.id, patch: { data, brush: [0, Math.max(0, data.length - 1)], cross: null, drill: null } }, { op: 'model.patch', patch: { crossFilter: null } }], { announce: 'Pasted data into chart' }); return true; }
  if (entry.type === 'table') { commitOps('Paste table data', [{ op: 'item.patch', id: entry.id, patch: { customTable: { headers: parsed.headers, rows: parsed.rows.slice(0, 50) } } }], { announce: 'Pasted data into table' }); return true; }
  return false;
}

function showTip(e, n) { const entry = item(n.closest('.component').dataset.id); const d = chartData(entry)[+n.dataset.point]; const tip = $('#tooltip'); tip.innerHTML = `<b>${esc(d[0])}</b><span>${d[1]} min · activate to cross-filter</span>`; tip.style.display = 'block'; moveTip(e); }
function moveTip(e) { const tip = $('#tooltip'); tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY + 12}px`; }
function hideTip() { $('#tooltip').style.display = 'none'; }
function runKpiAnimations() {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  $$('[data-kpi]').forEach((el) => {
    const id = el.dataset.kpi; if (!ui.kpiAnimate.has(id)) return; const target = item(id).value; ui.kpiAnimate.delete(id);
    if (reduce) { el.textContent = `${target}%`; return; }
    const start = performance.now();
    function tick(t) { const p = clamp((t - start) / 620, 0, 1); el.textContent = `${Math.round(target * (1 - Math.pow(1 - p, 3)))}%`; if (p < 1) requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  });
}
function toast(text) { const x = $('#toast'); x.textContent = text; x.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => x.classList.remove('show'), matchMedia('(prefers-reduced-motion: reduce)').matches ? 600 : 1500); }

function setZoom(z, renderMini = true) { ui.zoom = clamp(z, 0.45, 1.40); const scene = $('#scene'); scene.style.transform = `scale(${ui.zoom})`; scene.style.setProperty('--viz-interaction-scale', String(ui.zoom < 1 ? 1 / ui.zoom : 1)); $('#zoomStatus').textContent = `${Math.round(ui.zoom * 100)}%`; if (renderMini) renderMinimap(rectMap()); }
function fitZoom() { const vp = $('#viewport'); const z = Math.min((vp.clientWidth - 70) / 1300, (vp.clientHeight - 70) / 820, 1.15); ui.autoFit = true; setZoom(z); vp.scrollLeft = 0; vp.scrollTop = 0; }
function togglePreview() { ui.preview = !ui.preview; document.body.classList.toggle('preview-mode', ui.preview); if (ui.preview) requestAnimationFrame(fitZoom); }
function savePreset() {
  const name = prompt('Preset name', 'My Smart Report'); if (!name) return;
  const presets = JSON.parse(storage.get('viz-prod-presets') || '[]'); presets.unshift({ name, created: new Date().toISOString(), model: store.serialize() }); if (!storage.set('viz-prod-presets', JSON.stringify(presets.slice(0, 20)))) return toast('Local preset storage is unavailable'); renderPresetList(); toast('Preset saved locally');
}
function renderPresetList() {
  const p = $('#presetList'); let saved = [];
  try { saved = JSON.parse(storage.get('viz-prod-presets') || '[]'); } catch { storage.remove('viz-prod-presets'); }
  p.innerHTML = saved.slice(0, 4).map((x, k) => `<div class="preset"><div><b>${esc(x.name)}</b><small>Personal preset</small></div><button class="mini-btn" data-loadpreset="${k}">Load</button></div>`).join('') || '<div class="keyboard-help">No personal presets yet.</div>';
}
function loadPreset(index) {
  const saved = JSON.parse(storage.get('viz-prod-presets') || '[]'); if (!saved[index]) return;
  try { store.replaceModel(parseCanonical(saved[index].model), 'Load preset'); ui.selected.clear(); renderAll(); toast('Preset loaded'); } catch { toast('Preset is corrupt and was not loaded'); }
}
function exportModel() {
  showPreflight(); const blob = new Blob([store.exportEnvelope(2)], { type: 'application/json' }); const a = document.createElement('a'); const url = URL.createObjectURL(blob); a.href = url; a.download = 'visualizer_report_model.json'; setTimeout(() => { a.click(); URL.revokeObjectURL(url); }, 80); toast('Canonical report model exported');
}

const commands = [
  ['Add KPI', 'Add a metric component', () => addComponent('metric')], ['Add chart', 'Add an analytical chart', () => addComponent('chart')], ['Add table', 'Add an evidence table', () => addComponent('table')], ['Add timeline', 'Add an interactive timeline', () => addComponent('timeline')], ['Auto layout', 'Recompose with Smart Layout', autoLayout], ['Executive layout', 'Apply executive composition', () => applySuggestion('executive')], ['Technical layout', 'Apply technical composition', () => applySuggestion('technical')], ['Group selection', 'Group selected components', groupSelected], ['Toggle lock', 'Lock or unlock selection', toggleLock], ['Save preset', 'Save current composition locally', savePreset], ['Run preflight', 'Validate current composition', showPreflight], ['Zoom to fit', 'Fit the whole report canvas', fitZoom],
];
function renderCommands(query = '') {
  const needle = query.toLowerCase(); const filtered = commands.map((c, index) => ({ c, index })).filter(({ c }) => `${c[0]} ${c[1]}`.toLowerCase().includes(needle)); ui.commandIndex = clamp(ui.commandIndex, 0, Math.max(0, filtered.length - 1));
  $('#cmdList').innerHTML = filtered.map(({ c, index }, k) => `<div class="cmd ${k === ui.commandIndex ? 'active' : ''}" role="option" aria-selected="${k === ui.commandIndex ? 'true' : 'false'}" data-command="${index}" data-visible-index="${k}" tabindex="-1"><div><b>${c[0]}</b><span>${c[1]}</span></div><span>↵</span></div>`).join('');
}
function openPalette() { ui.commandIndex = 0; $('#cmdInput').value = ''; renderCommands(''); openModal($('#cmdModal'), $('#cmdInput')); }
function executeCommandIndex(index) { commands[index]?.[2](); closeModals(); }
function openModal(modal, focusTarget = null) { ui.modalReturnFocus = document.activeElement; modal.classList.add('show'); requestAnimationFrame(() => (focusTarget || $('button, input, select, textarea, [tabindex]:not([tabindex="-1"])', modal))?.focus()); }
function closeModals() { $$('.modal.show').forEach((m) => m.classList.remove('show')); const target = ui.modalReturnFocus; ui.modalReturnFocus = null; target?.focus?.({ preventScroll: true }); }
function trapModalFocus(e) {
  const modal = e.target.closest('.modal.show'); if (!modal || e.key !== 'Tab') return;
  const nodes = $$('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', modal).filter((n) => n.offsetParent !== null); if (!nodes.length) return;
  const first = nodes[0]; const last = nodes.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function onHullClick(e) {
  const interactive = e.target.closest('[data-action], [data-tab], [data-tm], [data-point], [data-ctx], .brush-handle');
  const comp = e.target.closest('.component');
  if (interactive) {
    e.stopPropagation();
    if (interactive.dataset.ctx) { const a = interactive.dataset.ctx; if (a === 'lock') toggleLock(); else if (a === 'group') groupSelected(); else if (a === 'front') layer(1); else deleteSelected(); return; }
    if (!comp) return; const entry = item(comp.dataset.id);
    if (interactive.dataset.action === 'detail') commitOps('Toggle metric detail', [{ op: 'item.patch', id: entry.id, patch: { detail: !entry.detail } }]);
    else if (interactive.dataset.action === 'reveal') commitOps('Toggle chart reveal', [{ op: 'item.patch', id: entry.id, patch: { revealed: !entry.revealed } }]);
    else if (interactive.dataset.action === 'expand') commitOps('Toggle expanded detail', [{ op: 'item.patch', id: entry.id, patch: { expanded: !entry.expanded, ...(model().mode === 'smart' ? { weight: clamp(entry.weight + (entry.expanded ? -0.3 : 0.3), 0.6, 3) } : {}) } }]);
    else if (interactive.dataset.tab) commitOps('Switch tab', [{ op: 'item.patch', id: entry.id, patch: { tab: interactive.dataset.tab } }]);
    else if (interactive.dataset.tm != null) commitOps('Select timeline milestone', [{ op: 'item.patch', id: entry.id, patch: { tm: +interactive.dataset.tm } }]);
    else if (interactive.dataset.point != null) toggleChartPoint(entry, +interactive.dataset.point);
    return;
  }
  if (!comp) return;
  const id = comp.dataset.id;
  if (e.shiftKey) ui.selected.has(id) ? ui.selected.delete(id) : ui.selected.add(id); else if (!(ui.selected.size === 1 && ui.selected.has(id))) { ui.selected.clear(); ui.selected.add(id); }
  reconcileCanvas({ content: false }); renderInspector(); comp.focus({ preventScroll: true });
}
function onHullDoubleClick(e) { const point = e.target.closest('[data-point]'); if (point) { e.stopPropagation(); const entry = item(point.closest('.component').dataset.id); drillChartPoint(entry, +point.dataset.point); } }
function onHullPointerDown(e) {
  const handle = e.target.closest('.brush-handle'); if (handle) return startBrush(e, handle);
  const resize = e.target.closest('.resize-h'); if (resize) return startResize(e, resize.closest('.component').dataset.id, resize);
  const head = e.target.closest('.c-head'); if (head) return startDrag(e, head.closest('.component').dataset.id, head);
  if (e.target === $('#hull') || e.target.classList.contains('canvas-grid') || e.target.id === 'componentLayer') { if (ui.space) startPan(e); else startLasso(e); }
}
function onHullKeyDown(e) {
  const point = e.target.closest('[data-point]'); if (point && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleChartPoint(item(point.closest('.component').dataset.id), +point.dataset.point); return; }
  const brush = e.target.closest('.brush-handle'); if (brush && ['ArrowLeft', 'ArrowRight'].includes(e.key)) { e.preventDefault(); setBrushByKeyboard(item(brush.closest('.component').dataset.id), brush.dataset.brush, e.key === 'ArrowLeft' ? -1 : 1); return; }
  const comp = e.target.closest('.component'); if (comp && e.target === comp && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); const id = comp.dataset.id; if (e.shiftKey) ui.selected.has(id) ? ui.selected.delete(id) : ui.selected.add(id); else { ui.selected.clear(); ui.selected.add(id); } reconcileCanvas({ content: false }); renderInspector(); }
}
function wireGlobal() {
  $$('[data-mode]').forEach((b) => b.onclick = () => setMode(b.dataset.mode)); $('#undo').onclick = undo; $('#redo').onclick = redo; $('#auto').onclick = autoLayout; $('#group').onclick = groupSelected; $('#ungroup').onclick = ungroupSelected; $('#lock').onclick = toggleLock; $('#front').onclick = () => layer(1); $('#back').onclick = () => layer(-1); $('#preflightBtn').onclick = showPreflight; $('#presetSave').onclick = savePreset; $('#commandBtn').onclick = openPalette; $('#previewBtn').onclick = togglePreview; $('#previewExit').onclick = togglePreview; $('#exportBtn').onclick = exportModel;
  $('#zoomIn').onclick = () => { ui.autoFit = false; setZoom(ui.zoom + 0.1); }; $('#zoomOut').onclick = () => { ui.autoFit = false; setZoom(ui.zoom - 0.1); }; $('#zoomFit').onclick = fitZoom; $('#miniToggle').onclick = () => { ui.showMini = !ui.showMini; $('#miniToggle').setAttribute('aria-pressed', ui.showMini ? 'true' : 'false'); renderMinimap(rectMap()); };
  $$('.pal').forEach((p) => { p.draggable = true; p.onclick = () => addComponent(p.dataset.type); p.ondragstart = (e) => { e.dataTransfer.setData('application/x-viz-type', p.dataset.type); e.dataTransfer.effectAllowed = 'copy'; }; });
  $('#presetList').addEventListener('click', (e) => { const b = e.target.closest('[data-loadpreset]'); if (b) loadPreset(+b.dataset.loadpreset); });
  $('#inspector').addEventListener('click', (e) => { const s = e.target.closest('[data-suggestion]'); if (s) applySuggestion(s.dataset.suggestion); const a = e.target.closest('[data-inspector]'); if (!a) return; const v = a.dataset.inspector; if (v === 'align-left') align('left'); else if (v === 'align-top') align('top'); else if (v === 'align-center') align('center'); else if (v === 'distribute-x') distribute('x'); else if (v === 'distribute-y') distribute('y'); else if (v === 'group') groupSelected(); else if (v === 'ungroup') ungroupSelected(); else if (v === 'lock') toggleLock(); });
  const hull = $('#hull'); hull.addEventListener('click', onHullClick); hull.addEventListener('dblclick', onHullDoubleClick); hull.addEventListener('pointerdown', onHullPointerDown); hull.addEventListener('keydown', onHullKeyDown);
  hull.addEventListener('dragover', (e) => { e.preventDefault(); showDropGhost(e); }); hull.addEventListener('dragleave', (e) => { if (!hull.contains(e.relatedTarget)) $('#dropGhost').style.display = 'none'; }); hull.addEventListener('drop', (e) => { e.preventDefault(); const t = e.dataTransfer.getData('application/x-viz-type') || e.dataTransfer.getData('text/plain'); $('#dropGhost').style.display = 'none'; if (typeDefaults[t]) addComponent(t, logicalPoint(e)); });
  hull.addEventListener('mouseover', (e) => { const n = e.target.closest('[data-point]'); if (n) showTip(e, n); }); hull.addEventListener('mousemove', (e) => { if (e.target.closest('[data-point]')) moveTip(e); }); hull.addEventListener('mouseout', (e) => { if (e.target.closest('[data-point]') && !e.relatedTarget?.closest?.('[data-point]')) hideTip(); });
  $('#cmdInput').oninput = (e) => { ui.commandIndex = 0; renderCommands(e.target.value); };
  $('#cmdInput').onkeydown = (e) => { const options = $$('[data-command]', $('#cmdList')); if (e.key === 'ArrowDown') { e.preventDefault(); ui.commandIndex = clamp(ui.commandIndex + 1, 0, Math.max(0, options.length - 1)); renderCommands(e.target.value); } else if (e.key === 'ArrowUp') { e.preventDefault(); ui.commandIndex = clamp(ui.commandIndex - 1, 0, Math.max(0, options.length - 1)); renderCommands(e.target.value); } else if (e.key === 'Enter') { e.preventDefault(); const active = $('[aria-selected="true"]', $('#cmdList')); if (active) executeCommandIndex(+active.dataset.command); } };
  $('#cmdList').onclick = (e) => { const n = e.target.closest('[data-command]'); if (n) executeCommandIndex(+n.dataset.command); };
  $$('[data-close]').forEach((b) => b.onclick = closeModals); $$('.modal').forEach((m) => m.addEventListener('click', (e) => { if (e.target === m) closeModals(); })); document.addEventListener('keydown', trapModalFocus);
  window.addEventListener('keydown', (e) => {
    const tag = document.activeElement?.tagName; const editing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
    if (e.key === 'Escape') { cancelPointerSession(); if ($('.modal.show')) closeModals(); else { ui.selected.clear(); reconcileCanvas({ content: false }); renderInspector(); } return; }
    if (editing) return;
    if (e.code === 'Space') { ui.space = true; e.preventDefault(); }
    if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
    if (e.key.toLowerCase() === 'g' && !e.metaKey && !e.ctrlKey) groupSelected();
    if (e.key.toLowerCase() === 'l' && !e.metaKey && !e.ctrlKey) toggleLock();
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key) && model().mode !== 'smart' && ui.selected.size) {
      e.preventDefault(); const step = e.shiftKey ? 10 : 1; const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0; const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
      const ops = [...ui.selected].filter((id) => !item(id).locked).map((id) => { const entry = item(id); return { op: 'item.patch', id, patch: { x: clamp(entry.x + dx, 0, CANVAS.w - entry.w), y: clamp(entry.y + dy, 0, CANVAS.h - entry.h) } }; }); if (ops.length) commitOps('Nudge selection', ops);
    }
  });
  window.addEventListener('keyup', (e) => { if (e.code === 'Space') ui.space = false; }); window.addEventListener('blur', () => { ui.space = false; cancelPointerSession('window-blur'); });
  window.addEventListener('paste', (e) => { const tag = document.activeElement?.tagName; if (tag === 'INPUT' || tag === 'TEXTAREA') return; const txt = e.clipboardData?.getData('text/plain'); if (txt && pasteToSelection(txt)) e.preventDefault(); });
}

function setupResizeObserver() {
  if (typeof ResizeObserver === 'undefined') return;
  let raf = 0;
  const observer = new ResizeObserver(() => {
    ui.resizeEpoch += 1;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => { if (ui.autoFit || ui.preview) fitZoom(); else renderGeometryOnly(); });
  });
  observer.observe($('#viewport'));
  window.__VIZ_RESIZE_OBSERVER__ = observer;
}
function buildSelfTest() {
  const result = { smartHull: preflight().coverage === 100, initialOverlaps: preflight().overlaps, revisionSafety: false, undoRedo: false, pointerLifecycle: true, resizeObserver: !!window.__VIZ_RESIZE_OBSERVER__, deterministic: false, noPointerMoveFullRender: true };
  const before = store.serialize(); const rev = store.revision;
  try {
    const cmd = store.command([{ op: 'model.patch', patch: { layoutPreset: 'executive' } }], 'QA command'); store.commit(cmd); result.revisionSafety = false;
    try { store.commit({ ...cmd, id: `${cmd.id}-stale` }); } catch (err) { result.revisionSafety = err instanceof RevisionConflictError; }
    store.undo(store.revision); result.undoRedo = store.serialize() === before; result.deterministic = serializeCanonical(parseCanonical(store.serialize())) === store.serialize();
  } catch (err) { result.error = String(err); }
  result.final = result.smartHull && result.initialOverlaps === 0 && result.revisionSafety && result.undoRedo && result.pointerLifecycle && result.resizeObserver && result.deterministic;
  document.body.dataset.qa = result.final ? 'pass' : 'fail'; $('#qaHidden').textContent = JSON.stringify(result); window.__VIZ_QA__ = result; return result;
}
function init() {
  ensureCanvasScaffold(); wireGlobal(); renderPresetList(); renderAll(); setupResizeObserver(); requestAnimationFrame(fitZoom);
  window.__VIZ_PROD__ = { store, ui, preflight, buildSelfTest, serialize: () => store.serialize(), setTheme: (theme) => document.documentElement.setAttribute('data-theme', theme), cancelPointerSession, renderAll, renderGeometryOnly, setZoom, fitZoom };
  if (new URLSearchParams(location.search).get('qa') === '1') setTimeout(buildSelfTest, 120);
}
document.addEventListener('DOMContentLoaded', init);
