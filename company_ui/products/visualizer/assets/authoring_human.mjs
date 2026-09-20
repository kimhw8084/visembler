// Shared human-facing authoring vocabulary and presentation helpers.
// Canonical dataset fields, mapping keys, and transform objects remain model truth;
// this module is the translation layer used by the editor and Chart Studio.
import { contractFor } from './authoring_contracts.mjs';
import { applyRecipe } from './authoring_transforms.mjs';

export const HUMAN_ROLE_VOCABULARY = Object.freeze({
  category: { label: 'Category', meaning: 'A dimension used to group or compare records.' },
  x: { label: 'X', meaning: 'The horizontal position, order, or time axis.' },
  y: { label: 'Y / Measure', meaning: 'The numeric measure plotted on the vertical axis.' },
  value: { label: 'Measurement', meaning: 'The numeric value represented by the visual.' },
  series: { label: 'Series', meaning: 'A field that creates separate lines, groups, or runs.' },
  color: { label: 'Color', meaning: 'A field used to distinguish categories or series.' },
  size: { label: 'Size', meaning: 'A numeric field that controls mark size.' },
  label: { label: 'Label', meaning: 'Text shown next to a mark or record.' },
  tooltip: { label: 'Tooltip', meaning: 'Extra detail shown when a mark is inspected.' },
  secondaryY: { label: 'Secondary axis', meaning: 'A second numeric scale for a related measure.' },
  time: { label: 'Time', meaning: 'A date, time, or ordered event axis.' },
  source: { label: 'Source', meaning: 'The starting node in a flow or relationship.' },
  target: { label: 'Destination', meaning: 'The ending node in a flow or relationship.' },
  die_x: { label: 'Die X', meaning: 'The wafer die horizontal coordinate.' },
  die_y: { label: 'Die Y', meaning: 'The wafer die vertical coordinate.' },
  lot_id: { label: 'Lot', meaning: 'The manufacturing lot identifier.' },
  wafer_id: { label: 'Wafer', meaning: 'The wafer identifier.' },
  tool: { label: 'Tool', meaning: 'The equipment or tool identifier.' },
  chamber: { label: 'Chamber', meaning: 'The equipment chamber or module.' },
  recipe: { label: 'Recipe', meaning: 'The process recipe identifier.' },
  process: { label: 'Process step', meaning: 'The manufacturing process or operation.' },
  product: { label: 'Product', meaning: 'The product, device, or part family.' },
  route: { label: 'Route', meaning: 'The process route or flow path.' },
  bin: { label: 'Bin', meaning: 'A categorical die or result classification.' },
  cohort: { label: 'Cohort', meaning: 'The population or condition used for comparison.' },
  subgroup: { label: 'Subgroup', meaning: 'The subgroup used for process analysis.' },
  reference_value: { label: 'Reference / Golden', meaning: 'The baseline or golden measurement.' },
  affected_value: { label: 'Affected', meaning: 'The measurement from the affected population.' },
  specification_low: { label: 'Lower specification', meaning: 'The lower requirement boundary.' },
  specification_high: { label: 'Upper specification', meaning: 'The upper requirement boundary.' },
  lower_limit: { label: 'Lower limit', meaning: 'The lower bound supplied for an error or interval.' },
  upper_limit: { label: 'Upper limit', meaning: 'The upper bound supplied for an error or interval.' },
  factor_a: { label: 'Factor A', meaning: 'The first explanatory factor in a DOE view.' },
  factor_b: { label: 'Factor B', meaning: 'The second explanatory factor in a DOE view.' },
  response: { label: 'Response', meaning: 'The measured response in a DOE view.' },
  order: { label: 'Order', meaning: 'The sequence used to arrange observations.' },
  weight: { label: 'Weight', meaning: 'The amount or count carried by a flow or mark.' },
});

export const HUMAN_TRANSFORM_TYPES = Object.freeze([
  'filter', 'sort', 'top_n', 'rename', 'derive', 'calculated', 'conditional',
  'aggregate', 'group', 'unpivot', 'pivot', 'bin', 'rank', 'cumulative',
  'cumulative_percent', 'difference', 'percent_change', 'rolling_mean',
  'rolling_stddev', 'z_score', 'date_extract',
]);

const NUMERIC_TYPES = new Set(['integer', 'number']);
const TEMPORAL_TYPES = new Set(['date', 'datetime', 'time', 'timestamp']);
const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const text = value => String(value ?? '');
const escapeHtml = value => text(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));

export function humanRoleDefinition(role, { view = '' } = {}) {
  const definition = HUMAN_ROLE_VOCABULARY[role] || { label: 'Field', meaning: 'A field used by this visual.' };
  if (role === 'value' && ['engineering', 'distribution', 'control_affected_distribution'].includes(view)) {
    return { ...definition, label: 'Measurement' };
  }
  if (role === 'x' && ['wafer', 'wafer_difference'].includes(view)) return { ...definition, label: 'Die X' };
  if (role === 'y' && ['wafer', 'wafer_difference'].includes(view)) return { ...definition, label: 'Die Y' };
  if (role === 'value' && view === 'pareto') return { ...definition, label: 'Contribution' };
  if (role === 'category' && view === 'timeline') return { ...definition, label: 'Event' };
  return definition;
}

export function humanRoleLabel(role, options = {}) {
  return humanRoleDefinition(role, options).label;
}

export function humanFieldTypeLabel(type) {
  return ({ number: 'Number', integer: 'Whole number', categorical: 'Category', identifier: 'Identifier', string: 'Text', date: 'Date', datetime: 'Date and time', boolean: 'True / false', unknown: 'Needs review' }[type] || 'Field');
}

export function humanFieldMeaning(field) {
  const tag = field?.semantic_tags?.find(value => HUMAN_ROLE_VOCABULARY[value]);
  if (tag) return humanRoleLabel(tag);
  if (NUMERIC_TYPES.has(field?.type)) return 'Numeric measure';
  if (TEMPORAL_TYPES.has(field?.type)) return 'Time or date';
  if (field?.type === 'identifier') return 'Identifier or label';
  if (field?.type === 'categorical') return 'Category or group';
  return 'Text value';
}

function fieldValues(field, rows) {
  const index = Math.max(0, (rows || []).length && rows[0] ? (field.__index ?? -1) : -1);
  return index < 0 ? [] : rows.map(row => row?.[index]);
}

export function fieldBrowserModel(fields = [], rows = [], query = '') {
  const needle = text(query).trim().toLowerCase();
  return fields.map((field, index) => {
    const values = rows.map(row => row?.[index]);
    const present = values.filter(value => value !== null && value !== undefined && value !== '');
    const numeric = present.filter(value => typeof value === 'number' && Number.isFinite(value));
    const distinct = new Set(present.map(value => JSON.stringify(value))).size;
    const item = {
      ...field,
      __index: index,
      typeLabel: humanFieldTypeLabel(field.type),
      meaning: humanFieldMeaning(field),
      missing: field.profile?.missing ?? values.length - present.length,
      distinct: field.profile?.distinct ?? distinct,
      min: field.profile?.min ?? (numeric.length ? Math.min(...numeric) : null),
      max: field.profile?.max ?? (numeric.length ? Math.max(...numeric) : null),
      tags: (field.semantic_tags || []).map(humanRoleLabel),
    };
    item.searchText = [item.name, item.typeLabel, item.meaning, item.tags.join(' ')].join(' ').toLowerCase();
    return item;
  }).filter(item => !needle || item.searchText.includes(needle));
}

export function humanFieldOptionMarkup(fields = [], selected = '', { view = '', role = '' } = {}) {
  return `<option value="">Not assigned</option>${fields.map(field => {
    const compatible = role ? isHumanRoleCompatible(role, field, view) : true;
    return `<option value="${escapeHtml(field.id)}" ${selected === field.id ? 'selected' : ''} ${compatible ? '' : 'disabled'}>${escapeHtml(field.name)} · ${escapeHtml(humanFieldTypeLabel(field.type))}</option>`;
  }).join('')}`;
}

export function isHumanRoleCompatible(role, field, view = '') {
  if (!field?.id) return false;
  const validation = contractFor(view || 'table').validate({ [role]: field.id }, [field]);
  return !validation.incompatible.includes(role);
}

export function compatibilityExplanation(role, field, view = '') {
  const definition = humanRoleDefinition(role, { view });
  if (!field) return `${definition.label} needs a compatible field.`;
  if (isHumanRoleCompatible(role, field, view)) return `${field.name} fits ${definition.label}.`;
  if (['x', 'y', 'value', 'size', 'weight', 'die_x', 'die_y', 'reference_value', 'affected_value', 'specification_low', 'specification_high', 'response'].includes(role)) {
    return `${definition.label} needs a number${role === 'x' ? ' or date/time' : ''}; ${field.name} is ${humanFieldTypeLabel(field.type).toLowerCase()}.`;
  }
  return `${field.name} cannot be used for ${definition.label} in this visual.`;
}

export function humanFieldBrowserMarkup({ fields = [], rows = [], query = '', compact = false } = {}) {
  const visible = fieldBrowserModel(fields, rows, query);
  const cards = visible.length ? visible.map(field => `<button type="button" class="human-field-card" draggable="true" data-human-field="${escapeHtml(field.id)}" data-field-id="${escapeHtml(field.id)}" aria-label="${escapeHtml(`${field.name}, ${field.typeLabel}, ${field.meaning}`)}"><span class="human-field-card-heading"><b>${escapeHtml(field.name)}</b><small>${escapeHtml(field.typeLabel)}</small></span><span class="human-field-card-meaning">${escapeHtml(field.meaning)}${field.tags.length ? ` · ${escapeHtml(field.tags.join(' · '))}` : ''}</span><small>${field.missing.toLocaleString()} missing · ${field.distinct.toLocaleString()} distinct${field.min !== null ? ` · ${escapeHtml(field.min)}–${escapeHtml(field.max)}` : ''}</small></button>`).join('') : '<p class="human-empty">No fields match this search.</p>';
  const clear = text(query).trim() ? '<button type="button" class="link-button" data-human-field-search-clear aria-label="Clear field search">Clear</button>' : '';
  return `<section class="human-field-browser${compact ? ' human-field-browser-compact' : ''}" aria-label="Fields and data understanding"><div class="human-section-heading"><div><b>Fields</b><small>Search, inspect, and choose a field without exposing model keys.</small></div><span>${visible.length}/${fields.length}</span></div><div class="human-field-search"><label><span class="sr-only">Search fields</span><input type="search" data-human-field-search value="${escapeHtml(query)}" placeholder="Search fields by name, type, or meaning" aria-label="Search fields"></label>${clear}</div><div class="human-field-list">${cards}</div></section>`;
}

export function humanEncodingShelvesMarkup({ fields = [], mapping = {}, view = '', selectAttribute = 'data-dataset-role', compact = false } = {}) {
  const contract = contractFor(view || 'table');
  const roles = [...new Set([...(contract.required_roles || []), ...(contract.optional_roles || [])])];
  const shelves = roles.map(role => {
    const definition = humanRoleDefinition(role, { view });
    const selected = fields.find(field => field.id === mapping[role]);
    const required = contract.required_roles?.includes(role);
    const selectAttrs = `${selectAttribute}="${escapeHtml(role)}" data-role="${escapeHtml(role)}"`;
    const explanation = selected && !isHumanRoleCompatible(role, selected, view) ? compatibilityExplanation(role, selected, view) : definition.meaning;
    return `<div class="human-encoding-shelf${selected ? ' is-filled' : ''}" data-role-drop="${escapeHtml(role)}" data-human-role="${escapeHtml(role)}"><div class="human-shelf-heading"><b>${escapeHtml(definition.label)}</b><span>${required ? 'Required' : 'Optional'}</span></div><select ${selectAttrs} aria-label="${escapeHtml(`${definition.label}${required ? ', required' : ''}`)}">${humanFieldOptionMarkup(fields, mapping[role], { view, role })}</select><small>${escapeHtml(explanation)}</small></div>`;
  }).join('');
  return `<section class="human-encoding-shelves${compact ? ' human-encoding-shelves-compact' : ''}" aria-label="Encodings"><div class="human-section-heading"><div><b>Encodings</b><small>Choose a field or drag one from Fields. The live visual updates immediately.</small></div><span>${roles.filter(role => mapping[role]).length}/${roles.length}</span></div><div class="human-shelf-list">${shelves || '<p class="human-empty">This visual has no field encodings.</p>'}</div></section>`;
}

export function multiFieldPickerMarkup(fields = [], selected = [], { key = 'source_fields', label = 'Fields used', help = 'Choose one or more fields. Use Shift or Ctrl/Cmd for keyboard multi-select.' } = {}) {
  const selectedIds = new Set(selected || []);
  const chips = [...selectedIds].map(id => fields.find(field => field.id === id)).filter(Boolean).map(field => `<button type="button" class="human-field-chip" data-multi-field-remove="${escapeHtml(key)}" data-field-id="${escapeHtml(field.id)}" aria-label="Remove ${escapeHtml(field.name)}">${escapeHtml(field.name)} <span aria-hidden="true">×</span></button>`).join('');
  return `<div class="human-multi-field-picker" data-multi-field-picker="${escapeHtml(key)}"><label><span>${escapeHtml(label)}</span><select multiple size="${Math.min(6, Math.max(3, fields.length))}" data-multi-field="${escapeHtml(key)}" aria-label="${escapeHtml(label)}">${fields.map(field => `<option value="${escapeHtml(field.id)}" ${selectedIds.has(field.id) ? 'selected' : ''}>${escapeHtml(field.name)} · ${escapeHtml(humanFieldTypeLabel(field.type))}</option>`).join('')}</select></label><div class="human-field-chips" aria-live="polite">${chips || '<small>No fields selected.</small>'}</div><small>${escapeHtml(help)}</small></div>`;
}

export function selectedMultiFieldIds(host, key) {
  return [...(host?.querySelectorAll?.(`[data-multi-field="${key}"] option:checked`) || [])].map(option => option.value);
}

export function humanMappingAssignment(mapping = {}, role = '', field, fields = [], view = '') {
  const current = clone(mapping || {});
  if (!role) return { ok: false, mapping: current, error: 'Choose an encoding shelf before choosing a field.' };
  if (!field?.id) { delete current[role]; return { ok: true, mapping: current, error: '' }; }
  const validation = contractFor(view || 'table').validate({ [role]: field.id }, fields);
  if (validation.incompatible.includes(role)) return { ok: false, mapping: current, error: compatibilityExplanation(role, field, view) };
  current[role] = field.id;
  return { ok: true, mapping: current, error: '' };
}

export function transformRecipeWithDraft(recipe = {}, draft = null, index = null) {
  const next = clone(recipe || {}), steps = Array.isArray(next.steps) ? next.steps : [];
  next.steps = steps;
  if (draft) {
    if (Number.isInteger(index)) next.steps[index] = clone(draft);
    else next.steps.push(clone(draft));
  }
  return next;
}

export function readHumanTransformStep(type, panel, fields = [], existing = {}) {
  const aliases = { '[data-transform-field]': '#cs-transform-field', '[data-transform-source-field]': '#cs-transform-field', '[data-transform-ranking-field]': '#cs-transform-field', '[data-transform-value]': '#cs-transform-value', '[data-transform-name]': '#cs-transform-value', '[data-transform-n]': '#cs-transform-count', '[data-transform-window]': '#cs-transform-count', '[data-transform-direction]': '#cs-transform-direction', '[data-transform-operation]': '#cs-transform-operation', '[data-transform-operator]': '#cs-transform-operator', '[data-transform-conditional-operator]': '#cs-transform-operator', '[data-transform-compare]': '#cs-transform-value', '[data-transform-new-name]': '#cs-transform-value', '[data-transform-multiplier]': '#cs-transform-multiplier', '[data-transform-offset]': '#cs-transform-offset' };
  const value = selector => { const primary = panel?.querySelector?.(selector); if (primary) return primary.value ?? ''; const fallback = aliases[selector] ? panel?.querySelector?.(aliases[selector]) : null; return fallback?.value ?? ''; };
  const number = (raw, fallback = null) => { if (raw === '') return fallback; const parsed = Number(raw); return Number.isFinite(parsed) ? parsed : fallback; };
  const field = value('[data-transform-field]'), source = value('[data-transform-source-field]'), name = value('[data-transform-name]'), step = { ...existing, type };
  if (type === 'filter') return { ...step, field, operator: value('[data-transform-operator]') || 'contains', value: value('[data-transform-value]') };
  if (type === 'sort') return { ...step, field, direction: value('[data-transform-direction]') || 'asc' };
  if (type === 'top_n') return { ...step, ranking_field: value('[data-transform-ranking-field]'), n: number(value('[data-transform-n]'), 10), direction: value('[data-transform-direction]') || 'desc' };
  if (type === 'rename') return { ...step, field: value('[data-transform-old-field]'), name: value('[data-transform-new-name]').trim() };
  if (type === 'derive') return { ...step, source_field: source, name: name.trim(), multiplier: number(value('[data-transform-multiplier]'), 1), offset: number(value('[data-transform-offset]'), 0) };
  if (['difference', 'percent_change', 'rolling_mean', 'rolling_stddev', 'z_score', 'cumulative_percent'].includes(type)) return { ...step, source_field: source, name: name.trim(), ...(type === 'difference' || type === 'percent_change' ? { periods: number(value('[data-transform-window]'), 1) } : { window: number(value('[data-transform-window]'), 3) }) };
  if (type === 'calculated') return { ...step, source_fields: selectedMultiFieldIds(panel, 'source_fields'), operation: value('[data-transform-operation]') || 'add', name: name.trim() };
  if (type === 'conditional') return { ...step, when_field: source, operator: value('[data-transform-conditional-operator]') || 'equals', compare_value: value('[data-transform-compare]'), then_value: value('[data-transform-then]'), else_value: value('[data-transform-else]'), name: name.trim() };
  if (type === 'aggregate' || type === 'group') return { ...step, by: value('[data-transform-group-field]'), field: value('[data-transform-group-field]'), value_field: value('[data-transform-value-field]'), aggregation: value('[data-transform-aggregation]') || 'sum' };
  if (type === 'date_extract') return { ...step, field, part: value('[data-transform-part]') || 'date' };
  if (type === 'unpivot') return { ...step, keep_fields: selectedMultiFieldIds(panel, 'keep_fields') };
  if (type === 'pivot') return { ...step, field, index_fields: [field], column_field: value('[data-transform-column-field]'), value_field: value('[data-transform-value-field]'), aggregation: value('[data-transform-aggregation]') || 'sum' };
  if (type === 'bin') return { ...step, field, size: number(value('[data-transform-value]'), 1) };
  return { ...step, field, value: value('[data-transform-value]') };
}

export function humanTransformTypeLabel(type) {
  return ({ top_n: 'Top N', cumulative_percent: 'Cumulative percent', rolling_mean: 'Rolling mean', rolling_stddev: 'Rolling standard deviation', z_score: 'Z-score', date_extract: 'Extract date part' }[type] || text(type).replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase()));
}

function fieldName(fields, id) { return fields.find(field => field.id === id)?.name || text(id) || 'field'; }
function quoted(value) { return value === null || value === undefined || value === '' ? 'blank' : `“${text(value)}”`; }

export function transformOutcomeSummary(step = {}, fields = []) {
  const name = id => fieldName(fields, id);
  if (step.type === 'filter') return `Keep rows where ${name(step.field)} ${step.operator === 'equals' ? 'equals' : 'contains'} ${quoted(step.value)}`;
  if (step.type === 'sort') return `Sort ${name(step.field)} ${step.direction === 'desc' ? 'descending' : 'ascending'}`;
  if (step.type === 'top_n') return `Top ${step.n || 'N'} by ${name(step.ranking_field || step.field)}`;
  if (step.type === 'rename') return `Rename ${name(step.field || step.old_field)} to ${step.name || step.new_name || 'new field'}`;
  if (step.type === 'derive') return `Create ${step.name || 'a derived field'} from ${name(step.source_field || step.field)}`;
  if (step.type === 'calculated') {
    const sources = (step.source_fields || []).map(name);
    const joiner = step.operation === 'subtract' ? ' − ' : step.operation === 'multiply' ? ' × ' : step.operation === 'divide' ? ' ÷ ' : ' + ';
    return `Create ${step.name || 'a calculated field'} from ${sources.join(joiner) || 'selected fields'}`;
  }
  if (step.type === 'conditional') return `Create ${step.name || 'a flag'} when ${name(step.when_field || step.field)} ${step.operator || 'equals'} ${quoted(step.compare_value)}`;
  if (step.type === 'aggregate' || step.type === 'group') return `Group by ${name(step.by || step.field)} · ${step.aggregation || 'sum'} ${name(step.value_field)}`;
  if (step.type === 'unpivot') return `Unpivot measures, keeping ${(step.keep_fields || []).map(name).join(' · ') || 'selected identifier fields'}`;
  if (step.type === 'pivot') return `Pivot ${name(step.column_field)} into columns using ${name(step.value_field)}`;
  if (step.type === 'bin') return `Bin ${name(step.field)} into groups of ${step.size || 1}`;
  if (step.type === 'rank') return `Rank ${name(step.field || step.source_field)} from highest to lowest`;
  if (step.type === 'cumulative') return `Create cumulative ${name(step.field || step.source_field)}`;
  if (step.type === 'cumulative_percent') return `Create cumulative percent of ${name(step.field || step.source_field)}`;
  if (step.type === 'difference') return `Create ${step.name || 'difference'} from ${name(step.source_field || step.field)} across ${step.periods || 1} row`;
  if (step.type === 'percent_change') return `Create ${step.name || 'percent change'} from ${name(step.source_field || step.field)}`;
  if (step.type === 'rolling_mean') return `Create rolling mean of ${name(step.source_field || step.field)} over ${step.window || 3} rows`;
  if (step.type === 'rolling_stddev') return `Create rolling spread of ${name(step.source_field || step.field)} over ${step.window || 3} rows`;
  if (step.type === 'z_score') return `Standardize ${name(step.source_field || step.field)} as a z-score`;
  if (step.type === 'date_extract') return `Extract ${step.part || 'date'} from ${name(step.field)}`;
  return `Apply ${humanTransformTypeLabel(step.type || 'transform')}`;
}

function transformIssue(step, fields) {
  const byId = new Set(fields.map(field => field.id));
  const numericTypes = new Set(['number', 'integer', 'float', 'decimal', 'currency', 'percent']);
  const fieldById = id => fields.find(field => field.id === id);
  const required = (id, label) => id && byId.has(id) ? null : `${label} is missing or no longer exists.`;
  const numeric = (id, label) => {
    const missing = required(id, label);
    if (missing) return missing;
    const field = fieldById(id);
    return numericTypes.has(field?.type) ? null : `${label} “${field?.name || id}” is ${field?.type || 'not numeric'}; choose a numeric field.`;
  };
  if (['filter', 'sort', 'rename', 'bin', 'date_extract'].includes(step.type)) return required(step.field || step.old_field, 'The selected field');
  if (step.type === 'top_n') return required(step.ranking_field || step.field, 'The ranking field');
  if (['derive', 'difference', 'percent_change', 'rolling_mean', 'rolling_stddev', 'z_score', 'cumulative', 'cumulative_percent'].includes(step.type)) return numeric(step.source_field || step.field, 'The source field');
  if (step.type === 'calculated') {
    if ((step.source_fields || []).length < 2) return 'Choose at least two fields for this calculation.';
    if ((step.source_fields || []).some(id => !byId.has(id))) return 'One calculated field is missing or no longer exists.';
    const incompatible = (step.source_fields || []).find(id => !numericTypes.has(fieldById(id)?.type));
    return incompatible ? `Calculated field “${fieldById(incompatible)?.name || incompatible}” is not numeric; choose numeric fields for ${step.operation || 'this operation'}.` : null;
  }
  if (step.type === 'conditional') return required(step.when_field || step.field, 'The condition field');
  if (step.type === 'aggregate' || step.type === 'group') return required(step.by || step.field, 'The group field');
  if (step.type === 'unpivot') return (step.keep_fields || []).some(id => !byId.has(id)) ? 'One keep field is missing or no longer exists.' : null;
  if (step.type === 'pivot') return required(step.column_field, 'The column field') || required(step.value_field, 'The value field');
  return null;
}

export function previewTransformPipeline(dataset = {}, recipe = {}) {
  const source = clone(dataset);
  let current = clone(dataset);
  const steps = Array.isArray(recipe?.steps) ? recipe.steps : [];
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index];
    const issue = transformIssue(step, current.fields || []);
    if (issue) return { ok: false, stepIndex: index, step: clone(step), error: `Step ${index + 1} · ${transformOutcomeSummary(step, current.fields || [])}: ${issue}`, before: source, after: current, rowCountBefore: source.rows?.length || 0, rowCountAfter: current.rows?.length || 0 };
    current = applyRecipe(current, { steps: [step] });
  }
  const beforeFields = source.fields || [], afterFields = current.fields || [];
  const beforeById = new Map(beforeFields.map(field => [field.id, field]));
  const afterById = new Map(afterFields.map(field => [field.id, field]));
  const columnsAdded = afterFields.filter(field => !beforeById.has(field.id)).map(field => field.name);
  const columnsRemoved = beforeFields.filter(field => !afterById.has(field.id)).map(field => field.name);
  const sampleChanges = [];
  const rows = Math.min(source.rows?.length || 0, current.rows?.length || 0, 3);
  for (let row = 0; row < rows; row += 1) {
    const width = Math.min(source.fields?.length || 0, current.fields?.length || 0);
    for (let column = 0; column < width; column += 1) {
      if (JSON.stringify(source.rows[row]?.[column]) !== JSON.stringify(current.rows[row]?.[column])) {
        sampleChanges.push({ row: row + 1, field: current.fields[column]?.name || source.fields[column]?.name || 'field', before: source.rows[row]?.[column], after: current.rows[row]?.[column] });
      }
    }
  }
  return { ok: true, before: source, after: current, rowCountBefore: source.rows?.length || 0, rowCountAfter: current.rows?.length || 0, columnsAdded, columnsRemoved, sampleChanges: sampleChanges.slice(0, 6), warning: current.rows?.length !== source.rows?.length ? 'Row count changes are shown before the recipe is committed.' : '' };
}

export function transformPreviewMarkup(preview) {
  if (!preview) return '';
  if (!preview.ok) return `<div class="human-transform-preview is-error" role="alert"><b>Transform preview blocked</b><span>${escapeHtml(preview.error)}</span></div>`;
  const changed = preview.sampleChanges?.length ? preview.sampleChanges.map(change => `<li>Row ${change.row} · ${escapeHtml(change.field)}: ${escapeHtml(change.before ?? 'blank')} → ${escapeHtml(change.after ?? 'blank')}</li>`).join('') : '<li>No representative values changed.</li>';
  return `<div class="human-transform-preview" aria-live="polite"><b>Before / after preview</b><span>${preview.rowCountBefore.toLocaleString()} → ${preview.rowCountAfter.toLocaleString()} rows${preview.columnsAdded?.length ? ` · added ${escapeHtml(preview.columnsAdded.join(', '))}` : ''}${preview.columnsRemoved?.length ? ` · removed ${escapeHtml(preview.columnsRemoved.join(', '))}` : ''}</span><ul>${changed}</ul>${preview.warning ? `<small>${escapeHtml(preview.warning)}</small>` : ''}</div>`;
}

export function datasetConsequenceSummary(dataset = {}, consumers = [], selectedId = '') {
  const linked = consumers.filter(Boolean);
  const locked = linked.filter(entry => entry.locked);
  return {
    count: linked.length,
    names: linked.map(entry => entry.element || entry.title || 'Visual'),
    lockedNames: locked.map(entry => entry.element || entry.title || 'Visual'),
    shared: linked.length > 1,
    refreshLabel: linked.length > 1 ? `Refresh shared dataset · update ${linked.length} linked visuals` : 'Refresh shared dataset',
    detachLabel: linked.length > 1 ? 'Replace this visual only · detach its data' : 'Replace data for this visual',
    warning: locked.length ? `Locked linked visual${locked.length === 1 ? '' : 's'} block shared data changes: ${locked.map(entry => entry.element || entry.title || 'Visual').join(', ')}.` : '',
    selectedIsLinked: linked.some(entry => entry.id === selectedId),
    resourceLabel: dataset.resource_id ? 'Governed shared resource · revisioned' : 'Report-local dataset',
  };
}

export { escapeHtml as humanEscapeHtml };
