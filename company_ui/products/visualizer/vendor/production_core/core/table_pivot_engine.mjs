/**
 * Visualizer TableEngine production pivot / hierarchy / virtualization core.
 *
 * Goals:
 * - deterministic typed aggregation with no string-coercion collisions
 * - exact source values remain untouched; renderer receives derived cells only
 * - row + column subtotals and grand totals are first-class semantic nodes
 * - expand/collapse is a projection over the immutable pivot model
 * - virtualization is O(1) window math over the visible projection
 * - no DOM/browser dependency and no network/runtime dependency
 */

export class TableContractError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'TableContractError';
    this.code = code;
    this.details = details;
  }
}

const ALL_COLUMN_ID = 'column:grand-total';
const ROOT_ROW_ID = 'row:grand-total';
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const fail = (code, message, details = {}) => { throw new TableContractError(code, message, details); };

function stableScalar(value) {
  if (value === null) return ['null', null];
  if (value === undefined) return ['undefined', null];
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) fail('INVALID_DATE', 'Invalid Date cannot be used as a pivot key.');
    return ['date', value.toISOString()];
  }
  const t = typeof value;
  if (t === 'number') {
    if (!Number.isFinite(value)) fail('NON_FINITE_DIMENSION', 'Dimension values must be finite when numeric.', { value });
    return ['number', Object.is(value, -0) ? 0 : value];
  }
  if (t === 'string' || t === 'boolean' || t === 'bigint') return [t, t === 'bigint' ? value.toString() : value];
  fail('UNSUPPORTED_DIMENSION_TYPE', 'Pivot dimensions must be primitive values, Date, null, or undefined.', { type: t });
}

function scalarKey(value) { return JSON.stringify(stableScalar(value)); }
function tupleKey(values) { return JSON.stringify(values.map(stableScalar)); }
function cloneDisplayValue(value) { return value instanceof Date ? new Date(value.getTime()) : value; }

function compareScalar(a, b) {
  const [ta, va] = stableScalar(a); const [tb, vb] = stableScalar(b);
  const order = { null: 0, undefined: 1, boolean: 2, number: 3, bigint: 4, date: 5, string: 6 };
  if (ta !== tb) return (order[ta] ?? 99) - (order[tb] ?? 99);
  if (va === vb) return 0;
  if (ta === 'number') return va - vb;
  if (ta === 'boolean') return va ? 1 : -1;
  return String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: 'base' });
}

function pathId(prefix, values) {
  return `${prefix}:${values.map((v) => encodeURIComponent(scalarKey(v))).join('/')}`;
}

function normalizeMeasures(measures) {
  if (!Array.isArray(measures) || !measures.length) fail('MEASURES_REQUIRED', 'At least one pivot measure is required.');
  const ids = new Set();
  return measures.map((m, i) => {
    if (!m || typeof m !== 'object') fail('MEASURE_SHAPE', `Measure ${i} must be an object.`);
    const field = m.field;
    const aggregator = m.aggregator ?? 'sum';
    if (typeof field !== 'string' || !field) fail('MEASURE_FIELD', `Measure ${i} requires a field name.`);
    if (!['sum', 'count', 'avg', 'min', 'max', 'distinct_count'].includes(aggregator)) fail('AGGREGATOR', `Unsupported aggregator: ${aggregator}.`, { aggregator });
    const id = m.id ?? `${field}:${aggregator}`;
    if (typeof id !== 'string' || !id || ids.has(id)) fail('MEASURE_ID', 'Measure IDs must be unique non-empty strings.', { id });
    ids.add(id);
    return Object.freeze({ id, field, aggregator, label: m.label ?? field, nullPolicy: m.nullPolicy ?? 'skip' });
  });
}

function normalizeDimensions(value, name) {
  if (value == null) return [];
  if (!Array.isArray(value) || value.some((x) => typeof x !== 'string' || !x)) fail('DIMENSION_SHAPE', `${name} dimensions must be an array of non-empty field names.`);
  if (new Set(value).size !== value.length) fail('DIMENSION_DUPLICATE', `${name} dimensions cannot contain duplicates.`);
  return [...value];
}

function createAggState(measure) {
  switch (measure.aggregator) {
    case 'sum': return { sum: 0, correction: 0, count: 0 };
    case 'count': return { count: 0 };
    case 'avg': return { sum: 0, correction: 0, count: 0 };
    case 'min': return { value: null, count: 0 };
    case 'max': return { value: null, count: 0 };
    case 'distinct_count': return { values: new Set(), count: 0 };
    default: fail('AGGREGATOR', `Unsupported aggregator: ${measure.aggregator}.`);
  }
}

function kahanAdd(state, value) {
  const y = value - state.correction;
  const t = state.sum + y;
  state.correction = (t - state.sum) - y;
  state.sum = t;
}

function numericMeasureValue(raw, measure, rowIndex) {
  if (raw === null || raw === undefined || raw === '') {
    if (measure.nullPolicy === 'zero') return 0;
    if (measure.nullPolicy === 'skip') return null;
    fail('NULL_POLICY', `Unsupported null policy ${measure.nullPolicy}.`, { measure: measure.id });
  }
  const n = typeof raw === 'number' ? raw : Number(raw);
  if (!finite(n)) fail('NON_FINITE_MEASURE', `Measure ${measure.field} contains a non-finite value.`, { rowIndex, field: measure.field, value: raw });
  return n;
}

function updateAgg(state, measure, raw, rowIndex) {
  if (measure.aggregator === 'count') {
    if (raw !== null && raw !== undefined && raw !== '') state.count += 1;
    return;
  }
  if (measure.aggregator === 'distinct_count') {
    if (raw !== null && raw !== undefined && raw !== '') state.values.add(scalarKey(raw));
    return;
  }
  const n = numericMeasureValue(raw, measure, rowIndex);
  if (n === null) return;
  if (measure.aggregator === 'sum' || measure.aggregator === 'avg') { kahanAdd(state, n); state.count += 1; return; }
  if (measure.aggregator === 'min') { state.value = state.count ? Math.min(state.value, n) : n; state.count += 1; return; }
  if (measure.aggregator === 'max') { state.value = state.count ? Math.max(state.value, n) : n; state.count += 1; }
}

function finalizeAgg(state, measure) {
  switch (measure.aggregator) {
    case 'sum': return state.count ? state.sum : null;
    case 'count': return state.count;
    case 'avg': return state.count ? state.sum / state.count : null;
    case 'min':
    case 'max': return state.count ? state.value : null;
    case 'distinct_count': return state.values.size;
    default: return null;
  }
}

function ensureCellState(node, columnId, measures) {
  let state = node._cellStates.get(columnId);
  if (!state) {
    state = new Map(measures.map((m) => [m.id, createAggState(m)]));
    node._cellStates.set(columnId, state);
  }
  return state;
}

function createNode({ id, depth, dimension, rawValue, path, parentId }) {
  return {
    id, depth, dimension, rawValue: cloneDisplayValue(rawValue), path: path.map(cloneDisplayValue), parentId,
    childIds: [], _children: new Map(), _cellStates: new Map(), sourceCount: 0,
  };
}

function makeColumnPrefixes(row, columns) {
  const out = [{ id: ALL_COLUMN_ID, path: [], depth: 0, dimension: null, rawValue: null, parentId: null }];
  const values = [];
  for (let i = 0; i < columns.length; i += 1) {
    values.push(row[columns[i]]);
    out.push({
      id: pathId('column', values), path: [...values], depth: i + 1, dimension: columns[i], rawValue: row[columns[i]],
      parentId: i === 0 ? ALL_COLUMN_ID : pathId('column', values.slice(0, -1)),
    });
  }
  return out;
}

function finalizeNode(node, measures) {
  const cells = {};
  for (const [columnId, states] of node._cellStates) {
    cells[columnId] = Object.fromEntries(measures.map((m) => [m.id, finalizeAgg(states.get(m.id), m)]));
  }
  return Object.freeze({
    id: node.id,
    depth: node.depth,
    dimension: node.dimension,
    rawValue: cloneDisplayValue(node.rawValue),
    path: Object.freeze(node.path.map(cloneDisplayValue)),
    parentId: node.parentId,
    childIds: Object.freeze([...node.childIds]),
    sourceCount: node.sourceCount,
    cells: Object.freeze(cells),
    isGrandTotal: node.id === ROOT_ROW_ID,
    isSubtotal: node.id !== ROOT_ROW_ID && node.childIds.length > 0,
    isLeafGroup: node.childIds.length === 0,
  });
}

function sortTree(node, nodes, sortDirections) {
  node.childIds.sort((aId, bId) => {
    const a = nodes.get(aId); const b = nodes.get(bId);
    const direction = sortDirections[a.depth - 1] === 'desc' ? -1 : 1;
    const cmp = compareScalar(a.rawValue, b.rawValue);
    return cmp === 0 ? a.id.localeCompare(b.id) : cmp * direction;
  });
  for (const id of node.childIds) sortTree(nodes.get(id), nodes, sortDirections);
}

function sortColumnTree(node, columnsById, sortDirections) {
  node.childIds.sort((aId, bId) => {
    const a = columnsById.get(aId); const b = columnsById.get(bId);
    const direction = sortDirections[a.depth - 1] === 'desc' ? -1 : 1;
    const cmp = compareScalar(a.rawValue, b.rawValue);
    return cmp === 0 ? a.id.localeCompare(b.id) : cmp * direction;
  });
  for (const id of node.childIds) sortColumnTree(columnsById.get(id), columnsById, sortDirections);
}

export function buildPivot(rows, config = {}) {
  if (!Array.isArray(rows)) fail('ROWS_SHAPE', 'Pivot input must be an array of row objects.');
  const rowDimensions = normalizeDimensions(config.rows, 'row');
  const columnDimensions = normalizeDimensions(config.columns, 'column');
  if (!rowDimensions.length && !columnDimensions.length) fail('DIMENSIONS_REQUIRED', 'At least one row or column dimension is required.');
  const measures = normalizeMeasures(config.measures);
  const rowSort = config.rowSort ?? rowDimensions.map(() => 'asc');
  const columnSort = config.columnSort ?? columnDimensions.map(() => 'asc');
  if (!Array.isArray(rowSort) || rowSort.some((v) => !['asc', 'desc'].includes(v))) fail('SORT_CONFIG', 'rowSort values must be asc or desc.');
  if (!Array.isArray(columnSort) || columnSort.some((v) => !['asc', 'desc'].includes(v))) fail('SORT_CONFIG', 'columnSort values must be asc or desc.');

  const root = createNode({ id: ROOT_ROW_ID, depth: 0, dimension: null, rawValue: null, path: [], parentId: null });
  const nodes = new Map([[root.id, root]]);
  const columnRoot = { id: ALL_COLUMN_ID, depth: 0, dimension: null, rawValue: null, path: [], parentId: null, childIds: [], _children: new Map() };
  const columnsById = new Map([[ALL_COLUMN_ID, columnRoot]]);

  rows.forEach((row, rowIndex) => {
    if (!row || typeof row !== 'object' || Array.isArray(row)) fail('ROW_SHAPE', `Row ${rowIndex} must be an object.`, { rowIndex });
    const colPrefixes = makeColumnPrefixes(row, columnDimensions);
    // Materialize the column hierarchy once using typed tuple identity.
    let colParent = columnRoot;
    for (let i = 1; i < colPrefixes.length; i += 1) {
      const spec = colPrefixes[i]; const sk = scalarKey(spec.rawValue);
      let colNode = colParent._children.get(sk);
      if (!colNode) {
        colNode = { ...spec, rawValue: cloneDisplayValue(spec.rawValue), path: spec.path.map(cloneDisplayValue), childIds: [], _children: new Map() };
        colParent._children.set(sk, colNode); colParent.childIds.push(colNode.id); columnsById.set(colNode.id, colNode);
      }
      colParent = colNode;
    }

    const rowNodes = [root]; let parent = root; const path = [];
    for (let depth = 0; depth < rowDimensions.length; depth += 1) {
      const dimension = rowDimensions[depth]; const rawValue = row[dimension]; const sk = scalarKey(rawValue); path.push(rawValue);
      let node = parent._children.get(sk);
      if (!node) {
        const id = pathId('row', path);
        node = createNode({ id, depth: depth + 1, dimension, rawValue, path, parentId: parent.id });
        parent._children.set(sk, node); parent.childIds.push(id); nodes.set(id, node);
      }
      rowNodes.push(node); parent = node;
    }

    for (const node of rowNodes) {
      node.sourceCount += 1;
      for (const col of colPrefixes) {
        const state = ensureCellState(node, col.id, measures);
        for (const measure of measures) updateAgg(state.get(measure.id), measure, row[measure.field], rowIndex);
      }
    }
  });

  sortTree(root, nodes, rowSort);
  sortColumnTree(columnRoot, columnsById, columnSort);

  const frozenNodes = {};
  for (const [id, node] of nodes) frozenNodes[id] = finalizeNode(node, measures);
  const frozenColumns = {};
  for (const [id, node] of columnsById) {
    frozenColumns[id] = Object.freeze({
      id, depth: node.depth, dimension: node.dimension, rawValue: cloneDisplayValue(node.rawValue),
      path: Object.freeze(node.path.map(cloneDisplayValue)), parentId: node.parentId,
      childIds: Object.freeze([...node.childIds]), isGrandTotal: id === ALL_COLUMN_ID,
      isSubtotal: id !== ALL_COLUMN_ID && node.childIds.length > 0, isLeafGroup: node.childIds.length === 0,
    });
  }

  const model = {
    schemaVersion: 1,
    rowDimensions: Object.freeze(rowDimensions),
    columnDimensions: Object.freeze(columnDimensions),
    measures: Object.freeze(measures),
    sourceRowCount: rows.length,
    rowRootId: ROOT_ROW_ID,
    columnRootId: ALL_COLUMN_ID,
    rowsById: Object.freeze(frozenNodes),
    columnsById: Object.freeze(frozenColumns),
  };
  return Object.freeze(model);
}

function normalizeExpanded(expandedIds) {
  if (expandedIds === 'all') return 'all';
  if (expandedIds == null) return new Set();
  return expandedIds instanceof Set ? expandedIds : new Set(expandedIds);
}

export function projectVisibleRows(model, { expandedIds = 'all', includeGrandTotal = true } = {}) {
  if (!model?.rowsById?.[model.rowRootId]) fail('PIVOT_MODEL', 'Invalid pivot model.');
  const expanded = normalizeExpanded(expandedIds); const out = [];
  const root = model.rowsById[model.rowRootId];
  const visit = (id) => {
    const node = model.rowsById[id]; out.push(node);
    if (node.childIds.length && (expanded === 'all' || expanded.has(id))) for (const childId of node.childIds) visit(childId);
  };
  for (const id of root.childIds) visit(id);
  if (includeGrandTotal) out.push(root);
  return out;
}

export function projectVisibleColumns(model, { expandedIds = 'all', includeGrandTotal = true, leavesOnly = false } = {}) {
  if (!model?.columnsById?.[model.columnRootId]) fail('PIVOT_MODEL', 'Invalid pivot model.');
  const expanded = normalizeExpanded(expandedIds); const out = []; const root = model.columnsById[model.columnRootId];
  const visit = (id) => {
    const node = model.columnsById[id];
    if (!leavesOnly || !node.childIds.length) out.push(node);
    if (node.childIds.length && (expanded === 'all' || expanded.has(id))) for (const childId of node.childIds) visit(childId);
  };
  for (const id of root.childIds) visit(id);
  if (includeGrandTotal) out.push(root);
  return out;
}

export function virtualWindow(totalRows, { scrollTop = 0, viewportHeight, rowHeight = 32, overscan = 6 } = {}) {
  if (!Number.isInteger(totalRows) || totalRows < 0) fail('VIRTUAL_TOTAL', 'totalRows must be a non-negative integer.', { totalRows });
  if (!finite(scrollTop) || scrollTop < 0) fail('VIRTUAL_SCROLL', 'scrollTop must be finite and non-negative.', { scrollTop });
  if (!finite(viewportHeight) || viewportHeight < 0) fail('VIRTUAL_VIEWPORT', 'viewportHeight must be finite and non-negative.', { viewportHeight });
  if (!finite(rowHeight) || rowHeight <= 0) fail('VIRTUAL_ROW_HEIGHT', 'rowHeight must be finite and > 0.', { rowHeight });
  if (!Number.isInteger(overscan) || overscan < 0) fail('VIRTUAL_OVERSCAN', 'overscan must be a non-negative integer.', { overscan });
  if (!totalRows) return Object.freeze({ start: 0, end: 0, offsetTop: 0, totalHeight: 0, count: 0 });
  const first = Math.min(totalRows - 1, Math.floor(scrollTop / rowHeight));
  const visibleCount = Math.max(1, Math.ceil(viewportHeight / rowHeight));
  const start = Math.max(0, first - overscan);
  const end = Math.min(totalRows, first + visibleCount + overscan);
  return Object.freeze({ start, end, offsetTop: start * rowHeight, totalHeight: totalRows * rowHeight, count: end - start });
}

export function projectVirtualRows(visibleRows, options) {
  if (!Array.isArray(visibleRows)) fail('VISIBLE_ROWS', 'visibleRows must be an array.');
  const window = virtualWindow(visibleRows.length, options);
  return Object.freeze({ ...window, rows: Object.freeze(visibleRows.slice(window.start, window.end)) });
}

export function cellValue(model, rowId, columnId, measureId) {
  const row = model?.rowsById?.[rowId];
  if (!row) fail('ROW_ID', `Unknown pivot row: ${rowId}.`, { rowId });
  if (!model?.columnsById?.[columnId]) fail('COLUMN_ID', `Unknown pivot column: ${columnId}.`, { columnId });
  if (!model.measures.some((m) => m.id === measureId)) fail('MEASURE_ID', `Unknown pivot measure: ${measureId}.`, { measureId });
  return row.cells[columnId]?.[measureId] ?? null;
}

export function pivotFingerprint(model) {
  if (!model?.rowsById || !model?.columnsById) fail('PIVOT_MODEL', 'Invalid pivot model.');
  const normalize = (value) => value instanceof Date ? { $date: value.toISOString() } : value;
  const rows = Object.keys(model.rowsById).sort().map((id) => {
    const n = model.rowsById[id];
    return [id, n.depth, n.dimension, normalize(n.rawValue), n.path.map(normalize), n.parentId, [...n.childIds], n.sourceCount,
      Object.keys(n.cells).sort().map((cid) => [cid, model.measures.map((m) => [m.id, n.cells[cid]?.[m.id] ?? null])])];
  });
  const columns = Object.keys(model.columnsById).sort().map((id) => {
    const n = model.columnsById[id]; return [id, n.depth, n.dimension, normalize(n.rawValue), n.path.map(normalize), n.parentId, [...n.childIds]];
  });
  return JSON.stringify({ schemaVersion: model.schemaVersion, rowDimensions: model.rowDimensions, columnDimensions: model.columnDimensions, measures: model.measures, sourceRowCount: model.sourceRowCount, rows, columns });
}

export const TABLE_PIVOT_CONSTANTS = Object.freeze({ ALL_COLUMN_ID, ROOT_ROW_ID });
