// Selection-aware spreadsheet operations shared by Clean Table and Data Dock.
// The values are copied, never parsed, so typed scalar intent survives every operation.

const integer = (value, fallback) => Number.isInteger(value) ? value : fallback;

function cellPosition(value, fallbackRow, fallbackColumn) {
  const [row, column] = String(value ?? '').split(':').map(Number);
  return {
    row: Number.isInteger(row) ? row : fallbackRow,
    column: Number.isInteger(column) ? column : fallbackColumn,
  };
}

export function gridSelection(range, rowCount, columnCount) {
  const rows = Math.max(0, integer(rowCount, 0));
  const columns = Math.max(0, integer(columnCount, 0));
  const fallbackRow = Math.max(0, rows - 1);
  const fallbackColumn = Math.max(0, columns - 1);
  const anchor = cellPosition(range?.anchor, fallbackRow, fallbackColumn);
  const focus = cellPosition(range?.focus, anchor.row, anchor.column);
  const clampRow = (value) => rows ? Math.max(0, Math.min(rows - 1, value)) : 0;
  const clampColumn = (value) => columns ? Math.max(0, Math.min(columns - 1, value)) : 0;
  const firstRow = clampRow(Math.min(anchor.row, focus.row));
  const lastRow = clampRow(Math.max(anchor.row, focus.row));
  const firstColumn = clampColumn(Math.min(anchor.column, focus.column));
  const lastColumn = clampColumn(Math.max(anchor.column, focus.column));
  return {
    firstRow,
    lastRow,
    firstColumn,
    lastColumn,
    rowCount: Math.max(1, lastRow - firstRow + 1),
    columnCount: Math.max(1, lastColumn - firstColumn + 1),
  };
}

function normalizedGrid(source) {
  const headers = Array.isArray(source?.headers) ? [...source.headers] : [];
  const rows = Array.isArray(source?.rows) ? source.rows.map(row => Array.isArray(row) ? [...row] : []) : [];
  const columnCount = Math.max(headers.length, ...rows.map(row => row.length), 0);
  while (headers.length < columnCount) headers.push(`Column ${headers.length + 1}`);
  rows.forEach(row => { while (row.length < columnCount) row.push(null); });
  return {headers, rows};
}

export function applyGridAction(source, action, range = null) {
  const grid = normalizedGrid(source);
  const selection = gridSelection(range, grid.rows.length, grid.headers.length);
  if (action === 'insert-row-above' || action === 'insert-row-below') {
    const count = selection.rowCount;
    const index = action === 'insert-row-above' ? selection.firstRow : selection.lastRow + 1;
    grid.rows.splice(index, 0, ...Array.from({length: count}, () => Array(grid.headers.length).fill(null)));
    return grid;
  }
  if (action === 'delete-rows') {
    if (!grid.rows.length) return grid;
    grid.rows.splice(selection.firstRow, selection.rowCount);
    return grid;
  }
  if (action === 'insert-column-left' || action === 'insert-column-right') {
    const count = selection.columnCount;
    const index = action === 'insert-column-left' ? selection.firstColumn : selection.lastColumn + 1;
    grid.headers.splice(index, 0, ...Array.from({length: count}, (_, offset) => `Column ${index + offset + 1}`));
    grid.rows.forEach(row => row.splice(index, 0, ...Array(count).fill(null)));
    return grid;
  }
  if (action === 'delete-columns') {
    if (grid.headers.length <= 1) return grid;
    const count = Math.min(selection.columnCount, grid.headers.length - 1);
    grid.headers.splice(selection.firstColumn, count);
    grid.rows.forEach(row => row.splice(selection.firstColumn, count));
    return grid;
  }
  return grid;
}
