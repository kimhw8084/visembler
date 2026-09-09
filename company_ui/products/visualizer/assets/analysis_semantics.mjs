// Value-level contracts for executable semiconductor analyses.
//
// This module is deliberately pure. It is the semantic authority between a
// recipe mapping and a visual projection; renderers must not infer engineering
// meaning from row order, first/last values, or presentation metadata.

export const ANALYSIS_SEMANTICS_VERSION = 'v2';

const numericTypes = new Set(['integer', 'number']);
const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const finite = value => typeof value === 'number' && Number.isFinite(value);
const numberValue = value => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
};
const fieldIndex = (dataset, id) => (dataset?.fields || []).findIndex(field => field.id === id);
const field = (dataset, id) => (dataset?.fields || []).find(value => value.id === id) || null;
const error = (code, message, details = {}) => ({code, message, ...details});
const warning = (code, message, details = {}) => ({code, message, ...details});
const text = value => String(value ?? '').trim();
const titleCase = value => text(value).replace(/[_-]+/g, ' ').replace(/\b\w/g, character => character.toUpperCase());

const CONTRACTS = Object.freeze({
  'yield-pareto': {version: 'v2', role_sets: [['category', 'value']]},
  'spc-excursion': {version: 'v2', role_sets: [['time', 'value']]},
  'tool-chamber-matching': {version: 'v2', role_sets: [['tool', 'chamber', 'value']]},
  'golden-affected': {version: 'v2', role_sets: [['x', 'reference_value', 'affected_value'], ['x', 'cohort', 'value']]},
  'wafer-difference': {version: 'v2', role_sets: [['die_x', 'die_y', 'reference_value', 'affected_value']]},
  'pre-post-change': {version: 'v2', role_sets: [['cohort', 'value']]},
  'distribution-review': {version: 'v1', role_sets: [['value']]},
  'distribution-comparison': {version: 'v2', role_sets: [['cohort', 'value']]},
});

export function recipeRoleContract(recipeId) {
  const contract = CONTRACTS[recipeId];
  if (!contract) return {recipe_id: recipeId, version: ANALYSIS_SEMANTICS_VERSION, required_roles: [], consumed_roles: [], role_sets: []};
  const roles = [...new Set(contract.role_sets.flat())].sort();
  return {recipe_id: recipeId, version: contract.version, required_roles: roles, consumed_roles: roles, role_sets: clone(contract.role_sets)};
}

function emptyResult(recipeId, dataset, mapping, contract) {
  return {
    ok: false,
    recipe_id: recipeId,
    version: contract?.version || ANALYSIS_SEMANTICS_VERSION,
    dataset: derivedDataset(dataset, recipeId, [], []),
    rows: [],
    mapping: clone(mapping || {}),
    summary: {},
    primary: {},
    provenance: '',
    warnings: [],
    errors: [],
  };
}

function derivedField(id, name, type = 'string', semantic_tags = []) {
  return {id, name, type, nullable: true, semantic_tags};
}

function derivedDataset(source, recipeId, fields, rows, metadata = {}) {
  return {
    ...clone(source || {}),
    fields,
    rows,
    metadata: {...clone(source?.metadata || {}), ...metadata, analysis_recipe: recipeId, semantic_version: ANALYSIS_SEMANTICS_VERSION},
  };
}

function valueAt(dataset, row, role) {
  const index = fieldIndex(dataset, role);
  return index < 0 ? undefined : row[index];
}

function validMapping(dataset, mapping, roles) {
  const errors = [];
  roles.forEach(role => {
    if (fieldIndex(dataset, mapping?.[role]) < 0) errors.push(error('MISSING_FIELD', `Map ${role} before applying this analysis.`, {role}));
  });
  return errors;
}

function sortValue(value) {
  const numeric = numberValue(value);
  if (numeric !== null) return {kind: 0, value: numeric};
  const date = Date.parse(text(value));
  if (Number.isFinite(date)) return {kind: 1, value: date};
  return {kind: 2, value: text(value)};
}

function compareOrdered(a, b) {
  const left = sortValue(a), right = sortValue(b);
  if (left.kind !== right.kind) return left.kind - right.kind;
  if (left.value < right.value) return -1;
  if (left.value > right.value) return 1;
  return 0;
}

function numericRows(dataset, mapping, valueRole, rows = dataset?.rows || []) {
  const warnings = [], accepted = [];
  rows.forEach((sourceRow, sourceIndex) => {
    const value = numberValue(valueAt(dataset, sourceRow, valueRole));
    if (value === null) {
      warnings.push(warning('INVALID_NUMERIC', `Ignored row ${sourceIndex + 1}: ${valueRole} is not finite.`, {source_index: sourceIndex, role: valueRole}));
      return;
    }
    accepted.push({sourceRow, sourceIndex, value});
  });
  return {accepted, warnings};
}

function executePareto(dataset, mapping) {
  const result = emptyResult('yield-pareto', dataset, mapping, CONTRACTS['yield-pareto']);
  result.errors = validMapping(dataset, mapping, ['category', 'value']);
  if (result.errors.length) return result;
  const groups = new Map();
  const {accepted, warnings} = numericRows(dataset, mapping, mapping.value);
  result.warnings = warnings;
  accepted.forEach(({sourceRow, sourceIndex, value}) => {
    const category = text(valueAt(dataset, sourceRow, mapping.category));
    if (!category) {
      result.warnings.push(warning('MISSING_CATEGORY', `Ignored row ${sourceIndex + 1}: category is empty.`, {source_index: sourceIndex}));
      return;
    }
    if (value < 0) result.errors.push(error('NEGATIVE_CONTRIBUTION', `Yield Pareto contribution must be non-negative; row ${sourceIndex + 1} is ${value}.`, {source_index: sourceIndex, value}));
    if (!groups.has(category)) groups.set(category, {category, contribution: 0, count: 0});
    const group = groups.get(category);
    group.contribution += value;
    group.count += 1;
  });
  if (result.errors.length) return result;
  const rows = [...groups.values()].sort((a, b) => b.contribution - a.contribution || a.category.localeCompare(b.category));
  const total = rows.reduce((sum, row) => sum + row.contribution, 0);
  let cumulative = 0;
  rows.forEach(row => { cumulative += row.contribution; row.cumulative_percent = total > 0 ? cumulative / total * 100 : 0; row.share_percent = total > 0 ? row.contribution / total * 100 : 0; });
  const top = rows[0] || null;
  const fields = [derivedField('__category', 'Category', 'categorical', ['category']), derivedField('__contribution', 'Contribution', 'number', ['value', 'weight']), derivedField('__cumulative_percent', 'Cumulative contribution %', 'number', ['percent'])];
  result.rows = rows;
  result.dataset = derivedDataset(dataset, 'yield-pareto', fields, rows.map(row => [row.category, row.contribution, row.cumulative_percent]), {total, top_contributor: top ? {category: top.category, value: top.contribution, share_percent: top.share_percent} : null});
  result.mapping = {category: '__category', value: '__contribution', cumulative_percent: '__cumulative_percent'};
  result.summary = {total, categories: rows.length, top_contributor: top ? {category: top.category, value: top.contribution, share_percent: top.share_percent} : null};
  result.primary = {kind: 'pareto', top_contributor: result.summary.top_contributor};
  result.provenance = 'group category; sum contribution; sort descending; cumulative percent';
  result.ok = true;
  return result;
}

function executeSpc(dataset, mapping) {
  const result = emptyResult('spc-excursion', dataset, mapping, CONTRACTS['spc-excursion']);
  result.errors = validMapping(dataset, mapping, ['time', 'value']);
  if (result.errors.length) return result;
  const {accepted, warnings} = numericRows(dataset, mapping, mapping.value);
  result.warnings = warnings;
  const rows = accepted.map(item => ({time: valueAt(dataset, item.sourceRow, mapping.time), value: item.value, source_index: item.sourceIndex}));
  rows.sort((a, b) => compareOrdered(a.time, b.time) || a.source_index - b.source_index);
  const low = mapping.specification_low ? numberValue(valueAt(dataset, dataset.rows.find(row => numberValue(valueAt(dataset, row, mapping.specification_low)) !== null) || [], mapping.specification_low)) : null;
  const high = mapping.specification_high ? numberValue(valueAt(dataset, dataset.rows.find(row => numberValue(valueAt(dataset, row, mapping.specification_high)) !== null) || [], mapping.specification_high)) : null;
  const fields = [derivedField('__time', 'Ordered time', 'string', ['time']), derivedField('__value', 'Measurement', 'number', ['value'])];
  result.rows = rows;
  result.dataset = derivedDataset(dataset, 'spc-excursion', fields, rows.map(row => [row.time, row.value]), {specification_low: low, specification_high: high});
  result.mapping = {time: '__time', value: '__value', specification_low: low === null ? null : '__specification_low', specification_high: high === null ? null : '__specification_high'};
  result.summary = {ordered: true, count: rows.length, specification_low: low, specification_high: high};
  result.primary = {kind: 'spc', observations: rows, specification_low: low, specification_high: high};
  result.provenance = 'sort time ascending (stable for equal timestamps); preserve supplied specification limits';
  result.ok = true;
  return result;
}

function executeToolChamber(dataset, mapping, options = {}) {
  const result = emptyResult('tool-chamber-matching', dataset, mapping, CONTRACTS['tool-chamber-matching']);
  result.errors = validMapping(dataset, mapping, ['tool', 'chamber', 'value']);
  if (result.errors.length) return result;
  const aggregation = options.aggregation || 'mean';
  if (!['mean', 'count', 'min', 'max'].includes(aggregation)) result.errors.push(error('AGGREGATION_UNSUPPORTED', `Unsupported tool/chamber aggregation: ${aggregation}.`));
  if (result.errors.length) return result;
  const groups = new Map(), warnings = [];
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const tool = text(valueAt(dataset, sourceRow, mapping.tool)), chamber = text(valueAt(dataset, sourceRow, mapping.chamber)), value = numberValue(valueAt(dataset, sourceRow, mapping.value));
    if (!tool || !chamber) { warnings.push(warning('MISSING_DIMENSION', `Ignored row ${sourceIndex + 1}: tool and chamber are required.`, {source_index: sourceIndex})); return; }
    if (aggregation !== 'count' && value === null) { warnings.push(warning('INVALID_NUMERIC', `Ignored row ${sourceIndex + 1}: measurement is not finite.`, {source_index: sourceIndex})); return; }
    const key = `${tool}\u0000${chamber}`;
    if (!groups.has(key)) groups.set(key, {tool, chamber, values: []});
    groups.get(key).values.push(value === null ? 1 : value);
  });
  const rows = [...groups.values()].map(group => {
    const values = group.values, value = aggregation === 'count' ? values.length : aggregation === 'min' ? Math.min(...values) : aggregation === 'max' ? Math.max(...values) : values.reduce((sum, item) => sum + item, 0) / values.length;
    return {tool: group.tool, chamber: group.chamber, label: `${group.tool} · ${group.chamber}`, value, count: values.length};
  }).sort((a, b) => a.tool.localeCompare(b.tool) || a.chamber.localeCompare(b.chamber));
  const fields = [derivedField('__tool', 'Tool', 'categorical', ['tool']), derivedField('__chamber', 'Chamber', 'categorical', ['chamber']), derivedField('__tool_chamber', 'Tool · Chamber', 'categorical', ['category']), derivedField('__value', aggregation[0].toUpperCase() + aggregation.slice(1), 'number', ['value']), derivedField('__count', 'Observations', 'integer', ['count'])];
  result.rows = rows;
  result.warnings = warnings;
  result.dataset = derivedDataset(dataset, 'tool-chamber-matching', fields, rows.map(row => [row.tool, row.chamber, row.label, row.value, row.count]), {aggregation});
  result.mapping = {tool: '__tool', chamber: '__chamber', category: '__tool_chamber', value: '__value', count: '__count'};
  result.summary = {aggregation, cells: rows.length, missing_cells_are_absent: true};
  result.primary = {kind: 'tool-chamber-matrix', aggregation, rows};
  result.provenance = `group tool × chamber; ${aggregation} measurement; preserve missing combinations as absent`;
  result.ok = true;
  return result;
}

function normalizeCohort(value) {
  const normalized = text(value).toLowerCase();
  if (/^(golden|reference|control|baseline|ref)$/.test(normalized)) return 'Golden';
  if (/^(affected|test|actual|failed|exposed|post)$/.test(normalized)) return 'Affected';
  return titleCase(value);
}

function executeGoldenAffected(dataset, mapping) {
  const result = emptyResult('golden-affected', dataset, mapping, CONTRACTS['golden-affected']);
  const wide = mapping?.x && mapping?.reference_value && mapping?.affected_value;
  const long = mapping?.x && mapping?.cohort && mapping?.value;
  if (!wide && !long) { result.errors.push(error('SCHEMA_UNRESOLVED', 'Golden vs Affected requires either position + reference/affected fields or position + cohort + value.')); return result; }
  result.errors = validMapping(dataset, mapping, wide ? ['x', 'reference_value', 'affected_value'] : ['x', 'cohort', 'value']);
  if (result.errors.length) return result;
  const rows = [], warnings = [];
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const x = valueAt(dataset, sourceRow, mapping.x);
    if (wide) {
      const reference = numberValue(valueAt(dataset, sourceRow, mapping.reference_value)), affected = numberValue(valueAt(dataset, sourceRow, mapping.affected_value));
      if (reference !== null) rows.push({x, cohort: 'Golden', value: reference, source_index: sourceIndex});
      else warnings.push(warning('MISSING_REFERENCE', `Ignored reference at row ${sourceIndex + 1}.`, {source_index: sourceIndex}));
      if (affected !== null) rows.push({x, cohort: 'Affected', value: affected, source_index: sourceIndex});
      else warnings.push(warning('MISSING_AFFECTED', `Ignored affected value at row ${sourceIndex + 1}.`, {source_index: sourceIndex}));
    } else {
      const value = numberValue(valueAt(dataset, sourceRow, mapping.value)), cohort = normalizeCohort(valueAt(dataset, sourceRow, mapping.cohort));
      if (value === null || !cohort) { warnings.push(warning('INVALID_COHORT_VALUE', `Ignored row ${sourceIndex + 1}: cohort/value is not usable.`, {source_index: sourceIndex})); return; }
      rows.push({x, cohort, value, source_index: sourceIndex});
    }
  });
  const cohortOrder = {Golden: 0, Affected: 1};
  rows.sort((a, b) => compareOrdered(a.x, b.x) || (cohortOrder[a.cohort] ?? 9) - (cohortOrder[b.cohort] ?? 9) || a.source_index - b.source_index);
  const cohorts = [...new Set(rows.map(row => row.cohort))].sort();
  if (!cohorts.includes('Golden') || !cohorts.includes('Affected')) result.errors.push(error('MISSING_COHORT', 'Both Golden and Affected populations are required.', {cohorts}));
  if (result.errors.length) return result;
  const fields = [derivedField('__x', 'Process position', 'string', ['x']), derivedField('__cohort', 'Cohort', 'categorical', ['cohort']), derivedField('__value', 'Measurement', 'number', ['value'])];
  result.rows = rows;
  result.warnings = warnings;
  result.dataset = derivedDataset(dataset, 'golden-affected', fields, rows.map(row => [row.x, row.cohort, row.value]), {cohorts});
  result.mapping = {x: '__x', value: '__value', series: '__cohort', category: '__cohort'};
  result.summary = {cohorts, counts: Object.fromEntries(cohorts.map(cohort => [cohort, rows.filter(row => row.cohort === cohort).length]))};
  result.primary = {kind: 'golden-affected-profile', cohorts};
  result.provenance = wide ? 'construct Golden and Affected series from wide reference/affected fields; order by process position' : 'normalize cohort/value rows; order by process position';
  result.ok = true;
  return result;
}

function executeWaferDifference(dataset, mapping) {
  const result = emptyResult('wafer-difference', dataset, mapping, CONTRACTS['wafer-difference']);
  result.errors = validMapping(dataset, mapping, ['die_x', 'die_y', 'reference_value', 'affected_value']);
  if (result.errors.length) return result;
  const byDie = new Map(), warnings = [];
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const x = numberValue(valueAt(dataset, sourceRow, mapping.die_x)), y = numberValue(valueAt(dataset, sourceRow, mapping.die_y)), reference = numberValue(valueAt(dataset, sourceRow, mapping.reference_value)), affected = numberValue(valueAt(dataset, sourceRow, mapping.affected_value));
    if (x === null || y === null || reference === null || affected === null) { warnings.push(warning('INVALID_DIE_ROW', `Ignored row ${sourceIndex + 1}: die coordinates and both values are required.`, {source_index: sourceIndex})); return; }
    const key = `${x}\u0000${y}`;
    if (!byDie.has(key)) byDie.set(key, {x, y, references: [], affecteds: [], source_index: sourceIndex});
    byDie.get(key).references.push(reference); byDie.get(key).affecteds.push(affected);
  });
  const rows = [...byDie.values()].map(group => {
    const reference = group.references.reduce((sum, value) => sum + value, 0) / group.references.length, affected = group.affecteds.reduce((sum, value) => sum + value, 0) / group.affecteds.length;
    return {x: group.x, y: group.y, reference, affected, delta: affected - reference, duplicate_count: group.references.length};
  }).sort((a, b) => a.y - b.y || a.x - b.x);
  if ([...byDie.values()].some(group => group.references.length > 1)) warnings.push(warning('DUPLICATE_DIE_COORDINATE', 'Duplicate die coordinates were combined by arithmetic mean.', {policy: 'mean'}));
  const maxAbs = rows.reduce((max, row) => Math.max(max, Math.abs(row.delta)), 0);
  const fields = [derivedField('__die_x', 'Die X', 'number', ['die_x']), derivedField('__die_y', 'Die Y', 'number', ['die_y']), derivedField('__reference', 'Reference', 'number', ['reference_value']), derivedField('__affected', 'Affected', 'number', ['affected_value']), derivedField('__delta', 'Delta (Affected − Reference)', 'number', ['value', 'delta'])];
  result.rows = rows;
  result.warnings = warnings;
  result.dataset = derivedDataset(dataset, 'wafer-difference', fields, rows.map(row => [row.x, row.y, row.reference, row.affected, row.delta]), {max_abs_delta: maxAbs});
  result.mapping = {die_x: '__die_x', die_y: '__die_y', value: '__delta', reference_value: '__reference', affected_value: '__affected'};
  result.summary = {cells: rows.length, max_abs_delta: maxAbs, zero_delta: rows.filter(row => row.delta === 0).length};
  result.primary = {kind: 'wafer-difference', rows, max_abs_delta: maxAbs};
  result.provenance = 'match die coordinates; delta = affected − reference; duplicate coordinates combine by mean; center scale at zero';
  result.ok = true;
  return result;
}

function executePrePost(dataset, mapping) {
  const result = emptyResult('pre-post-change', dataset, mapping, CONTRACTS['pre-post-change']);
  result.errors = validMapping(dataset, mapping, ['cohort', 'value']);
  if (result.errors.length) return result;
  const groups = new Map(), warnings = [];
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const rawCohort = text(valueAt(dataset, sourceRow, mapping.cohort)).toLowerCase(), value = numberValue(valueAt(dataset, sourceRow, mapping.value));
    const cohort = /^(pre|before|baseline)$/.test(rawCohort) ? 'Pre' : /^(post|after|affected)$/.test(rawCohort) ? 'Post' : null;
    if (!cohort) { result.errors.push(error('UNSUPPORTED_COMPARISON_COHORT', `Row ${sourceIndex + 1} uses ${rawCohort || 'an empty cohort'}; Pre/Post analysis requires only Pre and Post.`, {source_index: sourceIndex, cohort: rawCohort})); return; }
    if (value === null) { warnings.push(warning('INVALID_COMPARISON_ROW', `Ignored row ${sourceIndex + 1}: measurement is not finite.`, {source_index: sourceIndex})); return; }
    if (!groups.has(cohort)) groups.set(cohort, []); groups.get(cohort).push(value);
  });
  result.warnings = warnings;
  if (result.errors.length || !groups.has('Pre') || !groups.has('Post')) { result.errors.push(error('MISSING_COMPARISON_COHORT', 'Both Pre and Post populations are required.', {cohorts: [...groups.keys()]})); return result; }
  const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length, before = mean(groups.get('Pre')), after = mean(groups.get('Post'));
  const rows = [{cohort: 'Pre', mean: before, count: groups.get('Pre').length}, {cohort: 'Post', mean: after, count: groups.get('Post').length}];
  const fields = [derivedField('__cohort', 'Cohort', 'categorical', ['cohort']), derivedField('__mean', 'Mean measurement', 'number', ['value']), derivedField('__count', 'Observations', 'integer', ['count'])];
  result.rows = rows;
  result.dataset = derivedDataset(dataset, 'pre-post-change', fields, rows.map(row => [row.cohort, row.mean, row.count]), {aggregation: 'mean'});
  result.mapping = {x: '__cohort', y: '__mean', value: '__mean', category: '__cohort'};
  result.summary = {aggregation: 'mean', before, after, delta: after - before, counts: {Pre: groups.get('Pre').length, Post: groups.get('Post').length}};
  result.primary = {kind: 'pre-post', aggregation: 'mean', before, after, delta: after - before};
  result.provenance = 'group cohort; mean measurement for Pre and Post; change = Post mean − Pre mean';
  result.ok = true;
  return result;
}

function executeDistribution(dataset, mapping, recipeId) {
  const result = emptyResult(recipeId, dataset, mapping, CONTRACTS[recipeId]);
  result.errors = validMapping(dataset, mapping, ['value']);
  if (recipeId === 'distribution-comparison' && fieldIndex(dataset, mapping?.cohort) < 0) result.errors.push(error('MISSING_COHORT', 'Distribution Comparison requires a cohort field so both populations are represented.', {role: 'cohort'}));
  if (result.errors.length) return result;
  const rows = [], warnings = [], cohorts = new Set();
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const value = numberValue(valueAt(dataset, sourceRow, mapping.value));
    if (value === null) { warnings.push(warning('INVALID_NUMERIC', `Ignored row ${sourceIndex + 1}: measurement is not finite.`, {source_index: sourceIndex})); return; }
    const cohort = recipeId === 'distribution-comparison' ? titleCase(valueAt(dataset, sourceRow, mapping.cohort)) : 'All';
    cohorts.add(cohort); rows.push({cohort, value, source_index: sourceIndex});
  });
  if (recipeId === 'distribution-comparison' && cohorts.size < 2) { result.errors.push(error('MISSING_COHORT', 'Distribution Comparison requires at least two cohorts.', {cohorts: [...cohorts]})); return result; }
  const fields = recipeId === 'distribution-comparison' ? [derivedField('__cohort', 'Cohort', 'categorical', ['cohort']), derivedField('__value', 'Measurement', 'number', ['value'])] : [derivedField('__value', 'Measurement', 'number', ['value'])];
  result.rows = rows;
  result.warnings = warnings;
  result.dataset = derivedDataset(dataset, recipeId, fields, rows.map(row => recipeId === 'distribution-comparison' ? [row.cohort, row.value] : [row.value]), {cohorts: [...cohorts].sort()});
  result.mapping = recipeId === 'distribution-comparison' ? {category: '__cohort', value: '__value'} : {value: '__value'};
  result.summary = recipeId === 'distribution-comparison' ? {cohorts: [...cohorts].sort(), cohort_counts: Object.fromEntries([...cohorts].sort().map(cohort => [cohort, rows.filter(row => row.cohort === cohort).length]))} : {cohorts: ['All'], count: rows.length};
  result.primary = {kind: recipeId, cohorts: [...cohorts].sort()};
  result.provenance = recipeId === 'distribution-comparison' ? 'group cohort; preserve shared measurement scale; no significance claim' : 'review one numeric population; no capability claim without specification limits';
  result.ok = true;
  return result;
}

export function executeRecipeSemantics(recipeId, dataset = {}, mapping = {}, options = {}) {
  const id = String(recipeId || '');
  if (!CONTRACTS[id]) {
    const result = emptyResult(id, dataset, mapping, null);
    result.errors.push(error('UNKNOWN_RECIPE', `Unknown analysis recipe: ${id}.`));
    return result;
  }
  if (id === 'yield-pareto') return executePareto(dataset, mapping);
  if (id === 'spc-excursion') return executeSpc(dataset, mapping);
  if (id === 'tool-chamber-matching') return executeToolChamber(dataset, mapping, options);
  if (id === 'golden-affected') return executeGoldenAffected(dataset, mapping);
  if (id === 'wafer-difference') return executeWaferDifference(dataset, mapping);
  if (id === 'pre-post-change') return executePrePost(dataset, mapping);
  return executeDistribution(dataset, mapping, id);
}

export function semanticDatasetForEntry(entry, dataset, options = {}) {
  const recipe = entry?.analysis_recipe;
  if (!recipe || String(recipe.version || '') !== ANALYSIS_SEMANTICS_VERSION && recipe.id !== 'distribution-review') return null;
  return executeRecipeSemantics(recipe.id, dataset, recipe.mapping || {}, options);
}
