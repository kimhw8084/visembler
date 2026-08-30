import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import {
  TableContractError, buildPivot, projectVisibleRows, projectVisibleColumns,
  virtualWindow, projectVirtualRows, cellValue, pivotFingerprint, TABLE_PIVOT_CONSTANTS,
} from '../core/table_pivot_engine.mjs';

const rows = [
  { region: 'East', fab: 'F1', quarter: 'Q1', product: 'A', revenue: 10, defects: 2, lot: 'L1' },
  { region: 'East', fab: 'F1', quarter: 'Q1', product: 'B', revenue: 20, defects: 1, lot: 'L2' },
  { region: 'East', fab: 'F2', quarter: 'Q2', product: 'A', revenue: 30, defects: 3, lot: 'L1' },
  { region: 'West', fab: 'F3', quarter: 'Q1', product: 'A', revenue: 40, defects: 0, lot: 'L3' },
  { region: 'West', fab: 'F3', quarter: 'Q2', product: 'B', revenue: 50, defects: 4, lot: 'L4' },
];
const config = {
  rows: ['region', 'fab'], columns: ['quarter', 'product'],
  measures: [
    { id: 'rev', field: 'revenue', aggregator: 'sum' },
    { id: 'avg_def', field: 'defects', aggregator: 'avg' },
    { id: 'lots', field: 'lot', aggregator: 'distinct_count' },
    { id: 'n', field: 'revenue', aggregator: 'count' },
  ],
};
const m = buildPivot(rows, config);
assert.equal(m.sourceRowCount, 5);
assert.equal(Object.keys(m.rowsById).length, 6); // root + East/F1/F2 + West/F3
assert.equal(Object.keys(m.columnsById).length, 7); // grand + Q1/A/B + Q2/A/B

const east = Object.values(m.rowsById).find((r) => r.depth === 1 && r.rawValue === 'East');
const west = Object.values(m.rowsById).find((r) => r.depth === 1 && r.rawValue === 'West');
const q1 = Object.values(m.columnsById).find((c) => c.depth === 1 && c.rawValue === 'Q1');
const q2b = Object.values(m.columnsById).find((c) => c.depth === 2 && c.path[0] === 'Q2' && c.rawValue === 'B');
assert.equal(cellValue(m, east.id, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'rev'), 60);
assert.equal(cellValue(m, west.id, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'rev'), 90);
assert.equal(cellValue(m, TABLE_PIVOT_CONSTANTS.ROOT_ROW_ID, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'rev'), 150);
assert.equal(cellValue(m, east.id, q1.id, 'rev'), 30);
assert.equal(cellValue(m, west.id, q2b.id, 'rev'), 50);
assert.equal(cellValue(m, east.id, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'lots'), 2);
assert.equal(cellValue(m, east.id, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'avg_def'), 2);
assert.equal(cellValue(m, west.id, TABLE_PIVOT_CONSTANTS.ALL_COLUMN_ID, 'n'), 2);

const collapsed = projectVisibleRows(m, { expandedIds: new Set(), includeGrandTotal: true });
assert.deepEqual(collapsed.map((x) => x.rawValue), ['East', 'West', null]);
const eastExpanded = projectVisibleRows(m, { expandedIds: new Set([east.id]), includeGrandTotal: false });
assert.deepEqual(eastExpanded.map((x) => x.path.join('/')), ['East', 'East/F1', 'East/F2', 'West']);
const allRows = projectVisibleRows(m, { expandedIds: 'all' });
assert.equal(allRows.length, 6);
const leafColumns = projectVisibleColumns(m, { expandedIds: 'all', includeGrandTotal: true, leavesOnly: true });
assert.equal(leafColumns.length, 5); // 4 leaf combinations + grand total

const vw = virtualWindow(100000, { scrollTop: 64000, viewportHeight: 640, rowHeight: 32, overscan: 8 });
assert.deepEqual(vw, { start: 1992, end: 2028, offsetTop: 63744, totalHeight: 3200000, count: 36 });
const projected = projectVirtualRows(allRows, { scrollTop: 32, viewportHeight: 64, rowHeight: 32, overscan: 1 });
assert.equal(projected.start, 0); assert.equal(projected.end, 4); assert.equal(projected.rows.length, 4);

// Type identity: numeric 1 must not collide with string "1"; null/undefined are distinct.
const typed = buildPivot([
  { k: 1, v: 1 }, { k: '1', v: 2 }, { k: null, v: 3 }, { k: undefined, v: 4 },
], { rows: ['k'], measures: [{ field: 'v', aggregator: 'sum', id: 'v' }] });
assert.equal(typed.rowsById[typed.rowRootId].childIds.length, 4);
assert.equal(cellValue(typed, typed.rowRootId, typed.columnRootId, 'v'), 10);

// Determinism across equivalent input order when grouping sort is canonical.
const fp1 = pivotFingerprint(buildPivot(rows, config));
const fp2 = pivotFingerprint(buildPivot([...rows].reverse(), config));
assert.equal(fp1, fp2);

// Invalid numeric assumptions must block rather than emit misleading values.
assert.throws(() => buildPivot([{ k: 'x', v: Infinity }], { rows: ['k'], measures: [{ field: 'v', aggregator: 'sum' }] }), TableContractError);
assert.throws(() => buildPivot([], { rows: [], columns: [], measures: [{ field: 'v', aggregator: 'sum' }] }), TableContractError);
assert.throws(() => virtualWindow(10, { viewportHeight: 100, rowHeight: 0 }), TableContractError);

// 100k-row production stress: aggregation plus hierarchy creation, then O(1) virtual window.
const N = 100000;
const big = Array.from({ length: N }, (_, i) => ({
  site: `S${i % 8}`, tool: `T${i % 40}`, quarter: `Q${(i % 4) + 1}`,
  amount: (i % 997) / 10, defects: i % 11, lot: `L${i % 5000}`,
}));
const t0 = performance.now();
const stress = buildPivot(big, {
  rows: ['site', 'tool'], columns: ['quarter'],
  measures: [
    { id: 'sum', field: 'amount', aggregator: 'sum' },
    { id: 'avg', field: 'defects', aggregator: 'avg' },
    { id: 'distinct', field: 'lot', aggregator: 'distinct_count' },
  ],
});
const buildMs = performance.now() - t0;
const visible = projectVisibleRows(stress, { expandedIds: 'all' });
const t1 = performance.now();
for (let i = 0; i < 10000; i += 1) virtualWindow(visible.length, { scrollTop: (i % 1000) * 17, viewportHeight: 700, rowHeight: 32, overscan: 8 });
const virtual10kMs = performance.now() - t1;
assert.equal(cellValue(stress, stress.rowRootId, stress.columnRootId, 'sum'), big.reduce((s, r) => s + r.amount, 0));
assert.ok(buildMs < 5000, `100k pivot build exceeded 5s hard ceiling: ${buildMs.toFixed(1)}ms`);
assert.ok(virtual10kMs < 250, `10k virtual-window calculations exceeded 250ms: ${virtual10kMs.toFixed(1)}ms`);

console.log(JSON.stringify({
  pass: true, typedAggregation: true, rowSubtotals: true, columnSubtotals: true, grandTotals: true,
  expandCollapse: true, deterministicFingerprint: true, invalidInputBlocking: true,
  stress: { rows: N, buildMs: +buildMs.toFixed(2), visibleRows: visible.length, virtual10kMs: +virtual10kMs.toFixed(2) },
}, null, 2));
