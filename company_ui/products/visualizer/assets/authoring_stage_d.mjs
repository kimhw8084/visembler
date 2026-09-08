// Stage D authoring primitives.  This module owns deterministic product-layer
// decisions; the report model and the existing P0-P3 studios remain the
// persistence and rendering authorities.
import { productionTargetForView } from './authoring_data.mjs';

export const STAGE_D_VERSION = 1;
export const MESSAGE_ROLES = Object.freeze([
  'Headline', 'Primary Evidence', 'Supporting Evidence', 'Context', 'Risk', 'Action',
]);

const ROLE_ORDER = Object.freeze({
  Headline: 0,
  'Primary Evidence': 1,
  'Supporting Evidence': 2,
  Context: 3,
  Risk: 4,
  Action: 5,
});

const ROLE_POLICY = Object.freeze({
  Headline: Object.freeze({ weight: 1.25, width: 1, minHeight: 132, emphasis: 'hero' }),
  'Primary Evidence': Object.freeze({ weight: 1.15, width: 1, minHeight: 210, emphasis: 'prominent' }),
  'Supporting Evidence': Object.freeze({ weight: 1, width: 0.5, minHeight: 156, emphasis: 'standard' }),
  Context: Object.freeze({ weight: 0.8, width: 0.5, minHeight: 124, emphasis: 'compact' }),
  Risk: Object.freeze({ weight: 1, width: 0.5, minHeight: 150, emphasis: 'prominent' }),
  Action: Object.freeze({ weight: 0.95, width: 0.5, minHeight: 144, emphasis: 'standard' }),
});

const roleForName = name => {
  const value = String(name || '').toLowerCase();
  if (value.includes('hero') || value.includes('executive statement') || value.includes('section heading')) return 'Headline';
  if (value.includes('risk') || value.includes('decision')) return 'Risk';
  if (value.includes('action') || value.includes('project') || value.includes('corrective')) return 'Action';
  if (value.includes('context') || value.includes('metadata') || value.includes('footnote')) return 'Context';
  if (value.includes('table') || value.includes('chart') || value.includes('spc') || value.includes('wafer') || value.includes('evidence')) return 'Primary Evidence';
  if (value.includes('timeline') || value.includes('metric') || value.includes('diagram')) return 'Supporting Evidence';
  return 'Supporting Evidence';
};

export function suggestMessageRole(entry = {}) {
  return MESSAGE_ROLES.includes(entry.message_role) ? entry.message_role : roleForName(entry.element || entry.title);
}

export function rolePolicy(role) {
  return { ...(ROLE_POLICY[role] || ROLE_POLICY['Supporting Evidence']) };
}

export function withSuggestedRoles(model = {}) {
  const value = structuredClone(model || {});
  value.items = (value.items || []).map(entry => ({ ...entry, message_role: suggestMessageRole(entry) }));
  return value;
}

function looksTabular(text) {
  const lines = String(text || '').trim().split(/\r?\n/).filter(line => line.trim());
  return lines.length >= 2 && (lines.some(line => line.includes('\t')) || lines.filter(line => line.includes(',')).length >= 2 || lines.filter(line => line.includes('|')).length >= 2);
}

function nonEmptyLines(text) { return String(text || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean); }

function normalizedHeader(value) { return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_'); }

function textSuggestion(text) {
  const trimmed = String(text || '').trim();
  const headline = trimmed.length <= 96 && nonEmptyLines(trimmed).length === 1;
  return headline
    ? { kind: 'text', defaultRole: 'Headline', best: { engine: 'TextEngine', element: 'Hero Title', title: 'Hero Title' }, alternatives: [{ engine: 'TextEngine', element: 'Section Heading', title: 'Section Heading' }, { engine: 'TextEngine', element: 'Executive Statement', title: 'Executive Statement' }], recommendations: [{ engine: 'TextEngine', element: 'Hero Title', title: 'Hero Title', reason: 'Short text reads best as the report headline.' }, { engine: 'TextEngine', element: 'Section Heading', title: 'Section Heading', reason: 'Use this as a concise section label.' }, { engine: 'TextEngine', element: 'Executive Statement', title: 'Executive Statement', reason: 'Use this when the headline should carry a decision.' }] }
    : { kind: 'text', defaultRole: 'Context', best: { engine: 'TextEngine', element: 'Body Narrative', title: 'Body Narrative' }, alternatives: [{ engine: 'TextEngine', element: 'Executive Statement', title: 'Executive Statement' }, { engine: 'TextEngine', element: 'Key Takeaway', title: 'Key Takeaway' }], recommendations: [{ engine: 'TextEngine', element: 'Body Narrative', title: 'Body Narrative', reason: 'Longer text is easier to scan as narrative.' }, { engine: 'TextEngine', element: 'Executive Statement', title: 'Executive Statement', reason: 'Use this for a concise finding and implication.' }, { engine: 'TextEngine', element: 'Key Takeaway', title: 'Key Takeaway', reason: 'Use this to state the most important takeaway.' }] };
}

export function contentIntakePlan(text, { imageMime = '' } = {}) {
  if (imageMime) return { kind: 'image', recommendations: [
    { engine: 'ImageMediaEngine', element: 'Image', title: 'Image', reason: 'Keep the original evidence visible.' },
    { engine: 'ImageMediaEngine', element: 'Image + Caption', title: 'Image + Caption', reason: 'Add a concise evidence caption.' },
    { engine: 'ImageMediaEngine', element: 'Screenshot Frame', title: 'Screenshot Frame', reason: 'Preserve a screenshot with its source context.' },
  ], requires: ['alt text'], defaultRole: 'Primary Evidence' };
  const source = String(text || '').trim();
  if (!source) return { kind: 'empty', recommendations: [], defaultRole: 'Context' };
  const lines = nonEmptyLines(source);
  const processWords = new Set(['detect', 'analyze', 'verify', 'release', 'inspect', 'measure', 'hold', 'approve', 'contain', 'review', 'close']);
  if (lines.length >= 2 && lines.length <= 20 && lines.every(line => processWords.has(normalizedHeader(line)) || /^[0-9]+[.)-]\s+/.test(line))) {
    return { kind: 'process', defaultRole: 'Primary Evidence', recommendations: [{ view: 'diagram', engine: 'DiagramEngine', element: 'Process Flow', title: 'Process Flow', reason: 'Ordered process steps can become a connected flow.' }, { view: 'timeline', engine: 'TimelineEngine', element: 'Event Timeline', title: 'Event Timeline', reason: 'Keep the steps as a chronological sequence.' }] };
  }
  if (!looksTabular(source)) return textSuggestion(source);
  const rows = source.split(/\r?\n/).filter(line => line.trim());
  const headers = rows[0].split(/[\t,|]/).map(normalizedHeader);
  const has = (...names) => names.some(name => headers.includes(name));
  const numericLike = rows.slice(1).some(line => line.split(/[\t,|]/).some(value => /^\s*[-+]?\d+(?:\.\d+)?\s*$/.test(value)));
  const recommendations = [];
  if (has('source', 'from') && has('target', 'to')) recommendations.push({ view: 'diagram', ...productionTargetForView('diagram'), reason: 'Source and target columns define a connected flow.' });
  if (has('die_x', 'x_coord', 'wafer_x', 'x') && has('die_y', 'y_coord', 'wafer_y', 'y') && has('value', 'measurement', 'result')) recommendations.push({ view: 'wafer', ...productionTargetForView('wafer'), reason: 'Die coordinates and a measured value define a wafer map.' });
  if (has('timestamp', 'time', 'datetime', 'date') && numericLike) recommendations.push({ view: 'line', ...productionTargetForView('line'), reason: 'Time and numeric measurements define a trend.' });
  if (has('timestamp', 'time', 'datetime', 'date') && !numericLike) recommendations.push({ view: 'timeline', ...productionTargetForView('timeline'), reason: 'Dates and event labels define a timeline.' });
  if (has('measurement', 'value', 'result', 'yield', 'metric') && (has('target', 'status', 'unit') || numericLike)) recommendations.push({ view: 'engineering', ...productionTargetForView('engineering'), reason: 'Measurement-like fields support a process-health visual.' });
  if (!recommendations.length && numericLike) recommendations.push({ view: 'bar', ...productionTargetForView('bar'), reason: 'A category and numeric field support comparison.' });
  recommendations.push({ view: 'table', ...productionTargetForView('table'), reason: 'Keep every source column available as evidence.' });
  return { kind: 'table', headers, recommendations: recommendations.filter(candidate => candidate.engine), defaultRole: 'Primary Evidence', profile: { columns: headers.length, rows: rows.length - 1 } };
}

export function applyMessageRole(model, ids, role) {
  if (!MESSAGE_ROLES.includes(role)) throw new Error(`Unsupported message role: ${role}`);
  const selected = new Set((ids || []).map(String));
  return {
    ops: (model?.items || []).filter(entry => selected.has(String(entry.id)) && !entry.locked).map(entry => ({ op: 'item.patch', id: entry.id, patch: { message_role: role, emphasis: rolePolicy(role).emphasis, weight: rolePolicy(role).weight } })),
  };
}

function canvasFor(model) {
  const width = Math.max(640, Math.min(3840, Number(model?.canvas?.width) || 1600));
  const height = Math.max(360, Math.min(4800, Number(model?.canvas?.height) || 900));
  return { width, height };
}

function validSize(entry, canvas) {
  const roleName=suggestMessageRole(entry),role=rolePolicy(roleName),engine=String(entry?.engine||''),name=String(entry?.element||entry?.title||'').toLowerCase(),available=canvas.width-28;
  let width=role.width===1?available:Math.min(560,Math.max(320,available*.46)),height=Math.max(116,role.minHeight);
  if(engine==='CoreChartEngine'||engine==='EngineeringChartEngine'){width=Math.min(available,720);height=360;}
  else if(engine==='WaferFabEngine'&&!/(matrix|timeline|profile|distribution|route)/.test(name)){const side=Math.min(540,available,canvas.height*.62);width=side;height=side;}
  else if(engine==='DiagramEngine'){
    const vertical=String(entry?.direction||'right').toLowerCase()==='down';width=Math.min(available,vertical?430:760);height=vertical?500:280;
  }
  else if(engine==='TimelineEngine'){const vertical=name.includes('vertical');width=Math.min(available,vertical?430:760);height=vertical?460:250;}
  else if(engine==='TableEngine'){width=Math.min(available,760);height=340;}
  else if(engine==='ImageMediaEngine'){width=Math.min(available,600);height=360;}
  else if(engine==='MetricEngine'){width=Math.min(available,roleName==='Headline'?620:420);height=name.includes('ring')?Math.min(width,300):Math.max(role.minHeight,190);}
  else if(engine==='TextEngine'||['EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine','ComparisonEngine'].includes(engine)){width=Math.min(available,role.width===1?available:580);height=Math.max(role.minHeight,name.includes('body narrative')?220:150);}
  return {width:Math.max(160,width),height:Math.min(Math.max(role.minHeight,height),canvas.height-28)};
}

export function layoutOperations(model = {}, { action = 'clean', mode = model.mode } = {}) {
  if (mode === 'free' || model.mode === 'free') return [];
  const canvas = canvasFor(model);
  const entries = (model.items || []).filter(entry => !entry.locked && !entry.pinned && !entry.pinned_layout);
  const ordered = entries.slice().sort((a, b) => ROLE_ORDER[suggestMessageRole(a)] - ROLE_ORDER[suggestMessageRole(b)] || Number(a.order || 0) - Number(b.order || 0) || String(a.id).localeCompare(String(b.id)));
  const gap = 14;
  const patches = [];
  let x = gap, y = gap, rowHeight = 0, column = 0;
  ordered.forEach((entry, index) => {
    const role = suggestMessageRole(entry);
    const policy = rolePolicy(role);
    const size = validSize(entry, canvas);
    const squareEvidence=entry.engine==='WaferFabEngine'&&!/(matrix|timeline|profile|distribution|route)/i.test(entry.element||'');
    const full = !squareEvidence&&(policy.width === 1 || role === 'Headline' || role === 'Primary Evidence');
    const width = full ? Math.min(canvas.width - gap * 2, Math.max(size.width, canvas.width - gap * 2)) : Math.min(size.width, Math.floor((canvas.width - gap * 3) / 2));
    const height = action === 'fit' ? Math.max(policy.minHeight, Math.min(size.height, 420)) : size.height;
    if (full) { if (column) { x = gap; y += rowHeight + gap; column = 0; rowHeight = 0; } patches.push({ op: 'item.patch', id: entry.id, patch: { x: gap, y, w: width, h: height, order: index, message_role: role } }); y += height + gap; }
    else { if (column >= 2 || x + width > canvas.width - gap) { x = gap; y += rowHeight + gap; column = 0; rowHeight = 0; } patches.push({ op: 'item.patch', id: entry.id, patch: { x, y, w: width, h: height, order: index, message_role: role } }); x += width + gap; column += 1; rowHeight = Math.max(rowHeight, height); }
  });
  if (action === 'balance') {
    const yMax = Math.max(...patches.map(op => Number(op.patch.y) + Number(op.patch.h)), 0);
    const scale = yMax > canvas.height - gap ? (canvas.height - gap * 2) / yMax : 1;
    patches.forEach(op => { op.patch.y = Math.round(op.patch.y * scale); op.patch.h = Math.max(116, Math.round(op.patch.h * scale)); });
  }
  return patches;
}

export function contentFitSummary(model = {}) {
  const items = (model.items || []).map(entry => ({ id: entry.id, role: suggestMessageRole(entry), governed: true, minUseful: rolePolicy(suggestMessageRole(entry)).minHeight }));
  return { version: STAGE_D_VERSION, items, freeModeUserOwned: model.mode === 'free' };
}

export function createReusableAsset({ name, description = '', type, payload, compatibility = {} } = {}) {
  const now = new Date().toISOString();
  return { version: 1, id: `${String(type || 'asset').toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${Date.now().toString(36)}`, name: String(name || 'Untitled asset').trim().slice(0, 120), description: String(description || '').trim().slice(0, 500), type: String(type || 'reusable'), preview: null, created: now, modified: now, compatibility: structuredClone(compatibility), payload: structuredClone(payload ?? null) };
}

export function updateReusableAsset(asset, patch = {}) {
  return { ...structuredClone(asset), ...structuredClone(patch), modified: new Date().toISOString(), version: Number(asset?.version || 1) + (patch.payload ? 1 : 0) };
}

export function assetCompatibility(asset, context = {}) {
  const expected = asset?.compatibility || {};
  if (expected.schema_signature && context.schema_signature && expected.schema_signature !== context.schema_signature) return { kind: 'incompatible', reason: 'The current dataset schema does not match this asset.' };
  if (expected.element && context.element && expected.element !== context.element) return { kind: 'incompatible', reason: `This asset is for ${expected.element}.` };
  return { kind: 'compatible', reason: 'Compatible with the current context.' };
}

export function datasetSummary(dataset = {}, usedBy = []) {
  const schema = (dataset.fields || []).map(field => ({ name: field.name, type: field.type, semantic_tags: field.semantic_tags || [] }));
  return { id: dataset.id, name: dataset.name || 'Untitled dataset', description: dataset.description || '', schema, schema_signature: schema.map(field => `${String(field.name).trim().toLowerCase()}:${field.type}`).sort().join('|'), row_count: (dataset.rows || []).length, last_updated: dataset.updated_at || dataset.source?.imported_at || null, provenance: dataset.source?.label || dataset.provenance || 'Local report data', used_by: [...usedBy] };
}

export function mediaSummary(asset = {}, usedBy = []) {
  return { id: asset.id || asset.asset_id, name: asset.name || 'Untitled media', alt: asset.alt || '', description: asset.description || '', created: asset.created || null, modified: asset.modified || null, usage_count: usedBy.length, used_by: [...usedBy] };
}

export const BLUEPRINTS = Object.freeze([
  { id: 'executive-review', name: 'Executive Review', description: 'Headline, primary evidence, trend, context, and action.', roles: ['Headline', 'Primary Evidence', 'Supporting Evidence', 'Action'] },
  { id: 'operations-review', name: 'Operations Review', description: 'Scorecard, trend, operating evidence, risks, and actions.', roles: ['Headline', 'Primary Evidence', 'Risk', 'Action'] },
  { id: 'spc-process-health', name: 'SPC / Process Health', description: 'Measurement health, limits, trend, and next action.', roles: ['Headline', 'Primary Evidence', 'Context', 'Action'] },
  { id: 'wafer-yield-investigation', name: 'Wafer / Yield Investigation', description: 'Spatial evidence, KPI, trend, and investigation context.', roles: ['Headline', 'Primary Evidence', 'Supporting Evidence', 'Context'] },
  { id: 'rca-corrective-action', name: 'RCA / Corrective Action', description: 'Problem, evidence, process, and corrective action.', roles: ['Headline', 'Primary Evidence', 'Risk', 'Action'] },
  { id: 'project-risk-review', name: 'Project / Risk Review', description: 'Status, evidence, risk, and decision path.', roles: ['Headline', 'Primary Evidence', 'Risk', 'Action'] },
]);

export function blueprintById(id) { return BLUEPRINTS.find(blueprint => blueprint.id === id) || BLUEPRINTS[0]; }

export function deliveryFindings(model = {}) {
  const items = model.items || [];
  const findings = [];
  const hasHeadline = items.some(entry => suggestMessageRole(entry) === 'Headline');
  if (!hasHeadline && items.length) findings.push({ id: 'missing-headline', severity: 'warning', message: 'Add a headline to establish the report message.', action: 'add-headline', element_id: null });
  items.forEach(entry => {
    const name = String(entry.element || '').toLowerCase();
    if ((name.includes('chart') || entry.engine === 'EngineeringChartEngine') && !entry.axis_title && !entry.axes?.x?.title && !entry.axes?.y?.title) findings.push({ id: 'axis-title', severity: 'info', message: 'Add an axis title so the measurement is self-explanatory.', action: 'focus-element', element_id: entry.id });
    if (entry.engine === 'ImageMediaEngine' && !String(entry.alt || '').trim()) findings.push({ id: 'missing-alt', severity: 'warning', message: 'Add alt text for image evidence.', action: 'focus-element', element_id: entry.id });
    if (entry.engine === 'CoreChartEngine' && entry.series?.length > 1 && entry.legend?.show === false) findings.push({ id: 'missing-legend', severity: 'info', message: 'Show a legend to distinguish chart series.', action: 'focus-element', element_id: entry.id });
    if (entry.w && entry.h && entry.w > 0 && entry.h > 720) findings.push({ id: 'excess-space', severity: 'info', message: 'Reduce empty space in this card.', action: 'fit-element', element_id: entry.id });
  });
  return findings;
}

export const STAGE_D_COMMANDS = Object.freeze([
  ['Paste content', 'Recommend a visual from text, data, or image evidence', 'intake'],
  ['Add element…', 'Open the production element library', 'library'],
  ['Clean Layout', 'Apply message hierarchy and content-aware Smart layout', 'clean-layout'],
  ['Fit Report', 'Fit the complete report in the workspace', 'fit-report'],
  ['Balance Whitespace', 'Reduce unused space while preserving locked content', 'balance-space'],
  ['Replace Visual', 'Choose a compatible production visual for the selection', 'replace-visual'],
  ['Duplicate with Style/Data', 'Duplicate selection while preserving reusable content', 'duplicate-linked'],
  ['Copy/Paste Style', 'Reuse presentation styling without changing content', 'style'],
  ['Save Checkpoint', 'Name the current report state', 'checkpoint'],
  ['Open Report Hub', 'Manage reports outside the editing canvas', 'report-hub'],
  ['Open Dataset Library', 'Reuse report-independent datasets', 'dataset-library'],
  ['Open Reusable Assets', 'Manage presets, recipes, subflows, and sections', 'asset-library'],
  ['Refresh report data', 'Review and refresh a selected linked dataset', 'refresh-data'],
  ['Duplicate selected', 'Duplicate the current selection', 'duplicate'],
  ['Focus selected', 'Center the selected content in the workspace', 'focus'],
  ['Export JSON', 'Download the canonical editable report', 'export-json'],
  ['Export SVG', 'Download a standalone visual report', 'export-svg'],
]);

export function revisionDiff(before = {}, after = {}) {
  const beforeItems = new Map((before.items || []).map(entry => [String(entry.id), entry]));
  const afterItems = new Map((after.items || []).map(entry => [String(entry.id), entry]));
  const added = [...afterItems.keys()].filter(id => !beforeItems.has(id));
  const removed = [...beforeItems.keys()].filter(id => !afterItems.has(id));
  const changed = [...afterItems.keys()].filter(id => beforeItems.has(id) && JSON.stringify(beforeItems.get(id)) !== JSON.stringify(afterItems.get(id)));
  return { added, removed, changed, data_changed: JSON.stringify(before.datasets || []) !== JSON.stringify(after.datasets || []), mapping_changed: changed.some(id => JSON.stringify(beforeItems.get(id)?.mapping) !== JSON.stringify(afterItems.get(id)?.mapping)), style_changed: changed.some(id => JSON.stringify(beforeItems.get(id)?.style) !== JSON.stringify(afterItems.get(id)?.style)) };
}
