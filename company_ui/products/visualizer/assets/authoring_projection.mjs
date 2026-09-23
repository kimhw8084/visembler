// Shared dataset projection for committed and transient production renders.
// The input dataset and mapping are treated as model truth; this helper only
// returns a derived entry patch and never writes to the canonical report.
import { applyRecipe } from './authoring_transforms.mjs';
import { PERFORMANCE_LIMITS, sampledRows } from './authoring_performance.mjs';

function fieldById(dataset, id) { return (dataset.fields || []).find(field => field.id === id); }
function fieldIndex(dataset, id) { return (dataset.fields || []).findIndex(field => field.id === id); }
function valuesFor(dataset, id) {
  const index = fieldIndex(dataset, id);
  return index < 0 ? [] : (dataset.rows || []).map(row => row[index]);
}

export function projectDataEntry(entry = {}, sourceDataset = {}, mapping = {}) {
  const dataset = applyRecipe(sourceDataset, entry.transform_recipe);
  const pick = role => valuesFor(dataset, mapping[role]);
  const names = role => fieldById(dataset, mapping[role])?.name || role;
  const resolved = { _resolved_dataset: dataset };
  if (entry.engine === 'TableEngine' || entry.type === 'table') {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.tableRows);
    return { ...resolved, customTable: { headers: dataset.fields.map(field => field.name), rows }, rows, source_row_count: dataset.rows.length };
  }
  if (entry.engine === 'MatrixEngine') {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.tableRows);
    const rowIndex = fieldIndex(dataset, mapping.category || mapping.y);
    const columnIndex = fieldIndex(dataset, mapping.series || mapping.x);
    const valueIndex = fieldIndex(dataset, mapping.value);
    if (rowIndex >= 0 && columnIndex >= 0 && valueIndex >= 0) {
      return { ...resolved, matrix_long: rows.map(row => ({ row: row[rowIndex], column: row[columnIndex], value: row[valueIndex] })), source_row_count: dataset.rows.length };
    }
    return { ...resolved, matrix: [dataset.fields.map(field => field.name), ...rows], source_row_count: dataset.rows.length };
  }
  if (entry.engine === 'DiagramEngine' && mapping.source && mapping.target) {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.diagramEdges);
    const sourceIndex = fieldIndex(dataset, mapping.source), targetIndex = fieldIndex(dataset, mapping.target);
    const edges = rows.map(row => [String(row[sourceIndex] ?? ''), String(row[targetIndex] ?? '')]).filter(edge => edge[0] && edge[1]);
    return { ...resolved, nodes: [...new Set(edges.flat())], edges, source_row_count: dataset.rows.length };
  }
  if (entry.engine === 'WaferFabEngine') {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.waferRows);
    const at = (row, role) => { const index = fieldIndex(dataset, mapping[role]); return index < 0 ? null : row[index] ?? null; };
    const first = role => { const index = fieldIndex(dataset, mapping[role]); return index < 0 ? null : dataset.rows.find(row => row[index] !== null && row[index] !== undefined && String(row[index]).trim() !== '')?.[index] ?? null; };
    return {
      ...resolved,
      observations: rows.map(row => ({ x: at(row, 'die_x') ?? at(row, 'x'), y: at(row, 'die_y') ?? at(row, 'y'), value: at(row, 'value'), lot_id: at(row, 'lot_id'), wafer_id: at(row, 'wafer_id'), tool: at(row, 'tool'), chamber: at(row, 'chamber'), recipe: at(row, 'recipe'), process: at(row, 'process'), route: at(row, 'route'), product: at(row, 'product'), bin: at(row, 'bin'), status: at(row, 'status') })),
      wafer_id: first('wafer_id'), lot: first('lot_id'), tool: first('tool'), chamber: first('chamber'), recipe: first('recipe'), process: first('process'), route: first('route'), product: first('product'), bin: first('bin'), status: first('status'),
      fab_rows: rows.map(row => Object.fromEntries(dataset.fields.map((field, index) => [field.name, row[index]]))),
      fab_fields: dataset.fields.map(field => ({ id: field.id, name: field.name, type: field.type })), fab_mapping: mapping, source_row_count: dataset.rows.length,
    };
  }
  if (entry.engine === 'TimelineEngine') {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.chartRows);
    const labelId = mapping.category || mapping.label || mapping.time || mapping.x || dataset.fields.find(field => ['string', 'categorical', 'identifier', 'date', 'datetime'].includes(field.type))?.id;
    const labelIndex = fieldIndex(dataset, labelId), dateIndex = fieldIndex(dataset, mapping.time);
    return { ...resolved, milestones: rows.map(row => ({ label: String(labelIndex < 0 ? '' : row[labelIndex] ?? ''), date: dateIndex < 0 ? null : row[dateIndex] ?? null })), source_row_count: dataset.rows.length };
  }
  if (entry.engine === 'EngineeringChartEngine') {
    const rows = sampledRows(dataset.rows, PERFORMANCE_LIMITS.engineeringRows);
    const valueIndex = fieldIndex(dataset, mapping.value), labelId = mapping.time || mapping.category || mapping.x || mapping.label || dataset.fields.find(field => ['string', 'categorical', 'identifier', 'date', 'datetime'].includes(field.type))?.id, labelIndex = fieldIndex(dataset, labelId), subgroupIndex = fieldIndex(dataset, mapping.subgroup);
    const grouped = new Map();
    rows.forEach(row => { const key = subgroupIndex < 0 ? null : String(row[subgroupIndex] ?? ''); if (key !== null) { if (!grouped.has(key)) grouped.set(key, []); grouped.get(key).push(row[valueIndex]); } });
    const first = role => { const index = fieldIndex(dataset, mapping[role]); return index < 0 ? null : dataset.rows.find(row => row[index] !== null && row[index] !== undefined)?.[index] ?? null; };
    return { ...resolved, observations: rows.map(row => ({ label: String(labelIndex < 0 ? '' : row[labelIndex] ?? ''), value: valueIndex < 0 ? null : row[valueIndex] ?? null })), subgroups: [...grouped.values()], specification_low: first('specification_low'), specification_high: first('specification_high'), analysis_rows: rows.map(row => Object.fromEntries(dataset.fields.map((field, index) => [field.name, row[index]]))), analysis_fields: dataset.fields.map(field => ({ id: field.id, name: field.name, type: field.type })), analysis_mapping: mapping, source_row_count: dataset.rows.length };
  }
  const labelId = mapping.category || mapping.label || mapping.time || mapping.x || dataset.fields.find(field => ['string', 'categorical', 'identifier', 'date', 'datetime'].includes(field.type))?.id;
  const valueId = mapping.value || mapping.y || dataset.fields.find(field => ['integer', 'number'].includes(field.type))?.id;
  const labels = valuesFor(dataset, labelId);
  const values = valuesFor(dataset, valueId);
  const firstValue = values.find(value => value !== null && value !== undefined), lastValue = [...values].reverse().find(value => value !== null && value !== undefined);
  if (entry.engine === 'MetricEngine') {
    const metricField = fieldById(dataset, valueId);
    const unit = metricField && Object.prototype.hasOwnProperty.call(metricField, 'unit') ? metricField.unit : entry.unit;
    return { ...resolved, value: lastValue ?? null, unit: unit ?? '' };
  }
  if (entry.engine === 'ComparisonEngine') return { ...resolved, before: firstValue ?? null, after: lastValue ?? null };
  if (['TextEngine', 'EvidenceCompositeEngine', 'DecisionCompositeEngine', 'ProjectCompositeEngine'].includes(entry.engine)) return { ...resolved, text: String(lastValue ?? labels.at(-1) ?? ''), body: String(lastValue ?? labels.at(-1) ?? ''), statement: String(lastValue ?? labels.at(-1) ?? ''), detail: `Mapped from ${fieldById(dataset, valueId)?.name || 'data'}` };
  const indexes = sampledRows(dataset.rows.map((_, index) => index), PERFORMANCE_LIMITS.chartRows);
  const data = indexes.map(index => [String(labels[index] ?? ''), values[index]]);
  return { ...resolved, data, rows: data.map(([label, value]) => ({ label, value })), brush: [0, Math.max(0, data.length - 1)], cross: null, drill: null, subtitle: `Mapped ${names(labelId)} to ${names(valueId)}`, source_row_count: dataset.rows.length };
}
