// Value-level contracts for executable semiconductor analyses.
//
// This module is deliberately pure. It is the semantic authority between a
// recipe mapping and a visual projection; renderers must not infer engineering
// meaning from row order, first/last values, or presentation metadata.

import { doeInteraction, doeMainEffects, processCapability, xbarR } from '../vendor/production_core/core/statistics_engine.mjs';

export const ANALYSIS_SEMANTICS_VERSION = 'v2';
export const STATISTICAL_ANALYSIS_VERSION = 'statistical-v1';
export const STATISTICAL_RECIPE_IDS = Object.freeze(['xbar-r-process-review', 'process-capability', 'doe-response-review']);

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
  'xbar-r-process-review': {version: STATISTICAL_ANALYSIS_VERSION, role_sets: [['subgroup', 'value']], optional_roles: ['order', 'specification_low', 'specification_high']},
  'process-capability': {version: STATISTICAL_ANALYSIS_VERSION, role_sets: [['value', 'specification_low'], ['value', 'specification_high'], ['value', 'specification_low', 'specification_high']], optional_roles: ['target', 'cohort']},
  'doe-response-review': {version: STATISTICAL_ANALYSIS_VERSION, role_sets: [['factor_a', 'factor_b', 'response']], optional_roles: ['factor_c']},
});

export function recipeRoleContract(recipeId) {
  const contract = CONTRACTS[recipeId];
  if (!contract) return {recipe_id: recipeId, version: ANALYSIS_SEMANTICS_VERSION, required_roles: [], consumed_roles: [], role_sets: []};
  const roles = [...new Set(contract.role_sets.flat())].sort();
  return {recipe_id: recipeId, version: contract.version, required_roles: roles, consumed_roles: roles, optional_roles: clone(contract.optional_roles || []), role_sets: clone(contract.role_sets)};
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
    metadata: {...clone(source?.metadata || {}), ...metadata, analysis_recipe: recipeId, semantic_version: metadata.semantic_version || ANALYSIS_SEMANTICS_VERSION},
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

function mappedNumberValues(dataset, fieldId) {
  const index = fieldIndex(dataset, fieldId);
  if (index < 0) return [];
  return (dataset.rows || []).map(row => numberValue(row[index])).filter(value => value !== null);
}

function consistentSpecification(dataset, fieldId, label, explicitValue = null) {
  if (explicitValue !== null && explicitValue !== undefined) {
    const value = numberValue(explicitValue);
    return value === null ? {error: error('INVALID_SPECIFICATION', `${label} must be finite.`)} : {value, source: 'explicit-analysis'};
  }
  if (!fieldId) return {value: null, source: null};
  const values = mappedNumberValues(dataset, fieldId);
  if (!values.length) return {error: error('MISSING_SPECIFICATION', `${label} does not contain a finite value.`)};
  const unique = [...new Set(values)];
  if (unique.length > 1) return {error: error('CONFLICTING_SPECIFICATION', `${label} contains conflicting values; filter the dataset or configure one explicit value.`, {values: unique})};
  return {value: unique[0], source: 'dataset-column'};
}

function executeXbarR(dataset, mapping) {
  const result = emptyResult('xbar-r-process-review', dataset, mapping, CONTRACTS['xbar-r-process-review']);
  result.errors = validMapping(dataset, mapping, ['subgroup', 'value']);
  if (result.errors.length) return result;
  const subgroupIndex = fieldIndex(dataset, mapping.subgroup), valueIndex = fieldIndex(dataset, mapping.value), orderIndex = fieldIndex(dataset, mapping.order);
  const groups = new Map();
  (dataset.rows || []).forEach((sourceRow, sourceIndex) => {
    const subgroup = text(sourceRow[subgroupIndex]), value = numberValue(sourceRow[valueIndex]);
    if (!subgroup) { result.errors.push(error('MISSING_SUBGROUP', `Row ${sourceIndex + 1} is missing its subgroup identity.`, {source_index: sourceIndex})); return; }
    if (value === null) { result.errors.push(error('INVALID_MEASUREMENT', `Row ${sourceIndex + 1} has a non-finite measurement.`, {source_index: sourceIndex})); return; }
    const rawOrder = orderIndex >= 0 ? sourceRow[orderIndex] : null;
    if (!groups.has(subgroup)) groups.set(subgroup, {subgroup, values: [], order: rawOrder, source_index: sourceIndex});
    groups.get(subgroup).values.push(value);
  });
  if (result.errors.length) return result;
  const ordered = [...groups.values()].sort((a, b) => orderIndex >= 0 ? compareOrdered(a.order, b.order) || a.source_index - b.source_index : a.source_index - b.source_index);
  if (ordered.length < 2) { result.errors.push(error('SUBGROUPS', 'Xbar-R requires at least two subgroups.', {subgroups: ordered.length})); return result; }
  const low = consistentSpecification(dataset, mapping.specification_low, 'LSL');
  const high = consistentSpecification(dataset, mapping.specification_high, 'USL');
  if (low.error) result.errors.push(low.error); if (high.error) result.errors.push(high.error);
  if (result.errors.length) return result;
  let stats;
  try { stats = xbarR(ordered.map(group => group.values)); } catch (cause) { result.errors.push(error(cause.code || 'XBAR_R_INVALID', cause.message, cause.details || {})); return result; }
  const fields = [derivedField('__subgroup', 'Subgroup', 'categorical', ['subgroup']), derivedField('__sequence', 'Subgroup sequence', 'integer', ['order']), derivedField('__mean', 'X̄ subgroup mean', 'number', ['value']), derivedField('__range', 'R subgroup range', 'number', ['range'])];
  const rows = ordered.map((group, index) => [group.subgroup, index + 1, stats.means[index], stats.ranges[index]]);
  result.rows = ordered.map((group, index) => ({subgroup: group.subgroup, sequence: index + 1, mean: stats.means[index], range: stats.ranges[index], n: stats.n}));
  result.dataset = derivedDataset(dataset, 'xbar-r-process-review', fields, rows, {semantic_version: STATISTICAL_ANALYSIS_VERSION, xbar_r: stats});
  result.mapping = {subgroup: '__subgroup', order: '__sequence', value: '__mean', range: '__range'};
  result.summary = {subgroup_count: stats.subgroupCount, subgroup_size: stats.n, xbarbar: stats.xbarbar, rbar: stats.rbar, sigma: stats.sigma, xbar_limits: stats.xbarLimits, r_limits: stats.rLimits, signals: stats.rules.signals, specification: {lsl: low.value, usl: high.value, lsl_source: low.source, usl_source: high.source}};
  result.primary = {kind: 'xbar-r', stats, subgroups: ordered.map(group => group.values), subgroup_labels: ordered.map(group => group.subgroup)};
  result.provenance = 'group by mapped subgroup; order by mapped order when provided; compute X̄/R with validated constants; apply Western Electric signals to X̄ only';
  result.dataset.metadata.analysis_provenance = result.provenance;
  result.dataset.metadata.statistical_summary = result.summary;
  result.ok = true;
  return result;
}

function executeCapability(dataset, mapping, options = {}) {
  const result = emptyResult('process-capability', dataset, mapping, CONTRACTS['process-capability']);
  const hasLow = Boolean(mapping?.specification_low) || options.lsl !== null && options.lsl !== undefined;
  const hasHigh = Boolean(mapping?.specification_high) || options.usl !== null && options.usl !== undefined;
  result.errors = validMapping(dataset, mapping, ['value']);
  if (!hasLow && !hasHigh) result.errors.push(error('SPEC_LIMITS', 'Process Capability requires LSL, USL, or both.'));
  if (result.errors.length) return result;
  const {accepted, warnings} = numericRows(dataset, mapping, mapping.value);
  result.warnings = warnings;
  const low = consistentSpecification(dataset, mapping.specification_low, 'LSL', options.lsl);
  const high = consistentSpecification(dataset, mapping.specification_high, 'USL', options.usl);
  const targetSpec = consistentSpecification(dataset, mapping.target, 'Target', options.target);
  if (low.error) result.errors.push(low.error); if (high.error) result.errors.push(high.error); if (targetSpec.error) result.errors.push(targetSpec.error);
  if (result.errors.length) return result;
  let stats;
  try { stats = processCapability(accepted.map(item => item.value), {lsl: low.value, usl: high.value, target: targetSpec.value}); } catch (cause) { result.errors.push(error(cause.code || 'CAPABILITY_INVALID', cause.message, cause.details || {})); return result; }
  const fields = [derivedField('__value', 'Measurement', 'number', ['value']), derivedField('__lsl', 'LSL', 'number', ['specification_low']), derivedField('__usl', 'USL', 'number', ['specification_high']), derivedField('__target', 'Target', 'number', ['target']), derivedField('__cpk', 'Cpk', 'number', ['capability'])];
  result.rows = accepted.map(item => ({value: item.value, lsl: stats.lsl, usl: stats.usl, target: stats.target, cpk: stats.cpk, source_index: item.sourceIndex}));
  result.dataset = derivedDataset(dataset, 'process-capability', fields, result.rows.map(row => [row.value, row.lsl, row.usl, row.target, row.cpk]), {semantic_version: STATISTICAL_ANALYSIS_VERSION, capability: stats, specification_sources: {lsl: low.source, usl: high.source, target: targetSpec.source}});
  result.mapping = {value: '__value', specification_low: '__lsl', specification_high: '__usl', target: '__target'};
  result.summary = {...stats, specification_sources: {lsl: low.source, usl: high.source, target: targetSpec.source}};
  result.primary = {kind: 'process-capability', stats};
  result.provenance = `compute capability from sample standard deviation; ${stats.lsl === null ? 'USL-only' : stats.usl === null ? 'LSL-only' : 'LSL/USL'} specification`;
  result.dataset.metadata.analysis_provenance = result.provenance;
  result.dataset.metadata.statistical_summary = result.summary;
  result.ok = true;
  return result;
}

function executeDoe(dataset, mapping) {
  const result = emptyResult('doe-response-review', dataset, mapping, CONTRACTS['doe-response-review']);
  result.errors = validMapping(dataset, mapping, ['factor_a', 'factor_b', 'response']);
  if (result.errors.length) return result;
  const rows = (dataset.rows || []).map(row => ({factor_a: row[fieldIndex(dataset, mapping.factor_a)], factor_b: row[fieldIndex(dataset, mapping.factor_b)], response: row[fieldIndex(dataset, mapping.response)]}));
  let effects, interaction;
  try { effects = doeMainEffects(rows, {factors: ['factor_a', 'factor_b'], response: 'response'}); interaction = doeInteraction(rows, {factorA: 'factor_a', factorB: 'factor_b', response: 'response'}); } catch (cause) { result.errors.push(error(cause.code || 'DOE_INVALID', cause.message, cause.details || {})); return result; }
  const fields = [derivedField('__factor_a', 'Factor A', 'categorical', ['factor']), derivedField('__factor_b', 'Factor B', 'categorical', ['factor']), derivedField('__response', 'Response', 'number', ['response'])];
  result.rows = rows.map((row, index) => ({...row, source_index: index}));
  result.dataset = derivedDataset(dataset, 'doe-response-review', fields, rows.map(row => [row.factor_a, row.factor_b, row.response]), {semantic_version: STATISTICAL_ANALYSIS_VERSION, doe: {effects, interaction}});
  result.mapping = {factor_a: '__factor_a', factor_b: '__factor_b', response: '__response', value: '__response'};
  result.summary = {factors: effects.map(effect => ({factor: effect.factor, levels: effect.levels.map(level => level.level)})), interaction_effect: interaction.interactionEffect};
  result.primary = {kind: 'doe-response-review', effects, interaction};
  result.provenance = 'compute observed response means by factor level and factor-cell; descriptive interaction only; no significance or causal claim';
  result.dataset.metadata.analysis_provenance = result.provenance;
  result.dataset.metadata.statistical_summary = result.summary;
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
  if (id === 'xbar-r-process-review') return executeXbarR(dataset, mapping, options);
  if (id === 'process-capability') return executeCapability(dataset, mapping, options);
  if (id === 'doe-response-review') return executeDoe(dataset, mapping, options);
  return executeDistribution(dataset, mapping, id);
}

export function semanticDatasetForEntry(entry, dataset, options = {}) {
  const recipe = entry?.analysis_recipe;
  if (!recipe || (String(recipe.version || '') !== ANALYSIS_SEMANTICS_VERSION && recipe.id !== 'distribution-review' && !STATISTICAL_RECIPE_IDS.includes(recipe.id))) return null;
  return executeRecipeSemantics(recipe.id, dataset, recipe.mapping || {}, options);
}
