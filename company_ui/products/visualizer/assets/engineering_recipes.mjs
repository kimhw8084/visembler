// Deterministic semiconductor analysis recipes.
// Compatibility and mapping review live here. Value-level execution is kept
// in analysis_semantics.mjs so renderers cannot accidentally define meaning.

import { ANALYSIS_SEMANTICS_VERSION, recipeRoleContract } from './analysis_semantics.mjs';

const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const numericTypes = new Set(['integer', 'number']);
const tagsOf = fields => new Set((fields || []).flatMap(field => Array.isArray(field.semantic_tags) ? field.semantic_tags : []));
const fieldByTag = (fields, tag) => (fields || []).find(field => (field.semantic_tags || []).includes(tag));
const fieldByName = (fields, pattern) => (fields || []).find(field => pattern.test(String(field.name || '').toLowerCase()));
const fieldId = field => field?.id || null;

export const RECIPE_VERSION = ANALYSIS_SEMANTICS_VERSION;
export const RECIPE_VERSIONS = Object.freeze({
  'yield-pareto': 'v2', 'spc-excursion': 'v2', 'tool-chamber-matching': 'v2',
  'golden-affected': 'v2', 'wafer-difference': 'v2', 'pre-post-change': 'v2',
  'distribution-comparison': 'v2', 'distribution-review': 'v1',
});

// Public recipes only target elements already approved by the production
// library. Hidden fab renderers stay hidden until their own gates pass.
export const RECIPE_TARGETS = Object.freeze({
  'yield-pareto': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Pareto', view: 'pareto', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
    {engine: 'MetricEngine', element: 'Hero KPI', view: 'metric', role: 'summary'},
  ]),
  'spc-excursion': Object.freeze([
    {engine: 'EngineeringChartEngine', element: 'SPC Control Chart', view: 'engineering', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'tool-chamber-matching': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Horizontal Bar', view: 'bar', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'golden-affected': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Line Chart', view: 'line', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'wafer-difference': Object.freeze([
    {engine: 'WaferFabEngine', element: 'Wafer Map', view: 'wafer', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'pre-post-change': Object.freeze([
    {engine: 'ComparisonEngine', element: 'Before/After KPI', view: 'comparison', role: 'summary'},
    {engine: 'CoreChartEngine', element: 'Line Chart', view: 'line', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'distribution-comparison': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Histogram', view: 'histogram', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'distribution-review': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Histogram', view: 'histogram', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
});

const ROLE_LABELS = Object.freeze({
  category: 'Cause / category', value: 'Contribution / measurement', time: 'Ordered time',
  tool: 'Tool', chamber: 'Chamber', cohort: 'Cohort / condition', x: 'Process position',
  die_x: 'Die X', die_y: 'Die Y', reference_value: 'Reference / golden value',
  affected_value: 'Affected value', subgroup: 'Subgroup',
});

const recipe = (id, name, reason, visuals, role_sets) => Object.freeze({id, version: RECIPE_VERSIONS[id], name, reason, visuals, roles: [...new Set(role_sets.flat())], role_sets});

export const ENGINEERING_RECIPES = Object.freeze([
  recipe('yield-pareto', 'Yield Pareto', 'Grouped contribution ranked with cumulative loss makes the largest yield drivers obvious.', ['Pareto', 'Clean Table', 'Hero KPI'], [['category', 'value']]),
  recipe('spc-excursion', 'SPC Excursion Review', 'Ordered measurements can be reviewed without relying on clipboard row order.', ['SPC Control Chart', 'Clean Table'], [['time', 'value']]),
  recipe('tool-chamber-matching', 'Tool / Chamber Matching', 'Tool, chamber, and a governed aggregation make cell-level equipment differences visible.', ['Horizontal Bar', 'Clean Table'], [['tool', 'chamber', 'value']]),
  recipe('golden-affected', 'Golden vs Affected', 'A wide reference/affected pair or long cohort schema creates two aligned populations.', ['Line Chart', 'Box Plot', 'Clean Table'], [['x', 'reference_value', 'affected_value'], ['x', 'cohort', 'value']]),
  recipe('wafer-difference', 'Wafer Difference Investigation', 'Matched die coordinates compute signed affected-minus-reference deltas on a zero-centered scale.', ['Wafer Map', 'Clean Table'], [['die_x', 'die_y', 'reference_value', 'affected_value']]),
  recipe('pre-post-change', 'Pre / Post Process Change', 'Pre and Post populations are compared using explicit cohort means.', ['Before/After KPI', 'Line Chart', 'Clean Table'], [['cohort', 'value']]),
  recipe('distribution-comparison', 'Distribution Comparison', 'Two or more cohorts are compared on one shared measurement scale without an implied significance claim.', ['Box Plot', 'Histogram', 'Clean Table'], [['cohort', 'value']]),
  recipe('distribution-review', 'Distribution Review', 'One numeric population is profiled for spread, outliers, and distribution shape.', ['Box Plot', 'Histogram', 'Clean Table'], [['value']]),
]);

function resolve(fields, role) {
  const tagged = fieldByTag(fields, role); if (tagged) return tagged;
  if (role === 'category') { const category = fieldByTag(fields, 'category'); if (category) return category; }
  if (role === 'value') { const value = fieldByTag(fields, 'value') || fieldByTag(fields, 'weight'); if (value) return value; }
  if (role === 'time') { const time = fieldByTag(fields, 'time'); if (time) return time; }
  if (role === 'cohort') { const cohort = fieldByTag(fields, 'cohort') || fieldByTag(fields, 'status'); if (cohort) return cohort; }
  if (role === 'x') { const axis = fieldByTag(fields, 'x') || fieldByTag(fields, 'time') || fieldByTag(fields, 'process'); if (axis) return axis; }
  const patterns = {
    category: /(defect|cause|failure|alarm|category|reason|bin)/,
    value: /(yield|measure|value|count|loss|defect|rate|metric)/,
    time: /(timestamp|time|date|sequence|order|step)/,
    cohort: /(cohort|status|condition|population|group|golden|affected|control|reference)/,
    x: /(position|process|time|sequence|order|step)/,
    reference_value: /(reference|golden|baseline|control)/,
    affected_value: /(affected|actual|test|failed|exposed)/,
    tool: /tool/, chamber: /chamber/, die_x: /die.?x|wafer.?x/, die_y: /die.?y|wafer.?y/,
    specification_low: /spec(ification)?.?(low|lower)|lsl|lower.?limit/,
    specification_high: /spec(ification)?.?(high|upper)|usl|upper.?limit/,
  };
  const named = patterns[role] ? fieldByName(fields, patterns[role]) : null;
  if (['value', 'reference_value', 'affected_value'].includes(role)) {
    if (named && numericTypes.has(named.type)) return named;
    return (fields || []).find(field => numericTypes.has(field.type)) || null;
  }
  return named;
}

function inferMapping(fields) {
  const list = Array.isArray(fields) ? fields : [], numeric = list.filter(field => numericTypes.has(field.type));
  const mapping = {};
  for (const role of ['category', 'value', 'time', 'tool', 'chamber', 'cohort', 'x', 'die_x', 'die_y', 'reference_value', 'affected_value', 'subgroup', 'specification_low', 'specification_high']) {
    const value = resolve(list, role); if (value) mapping[role] = fieldId(value);
  }
  if (!mapping.value && numeric[0]) mapping.value = numeric[0].id;
  if (!mapping.x) mapping.x = mapping.time || numeric[0]?.id;
  if (!mapping.y && numeric[1]) mapping.y = numeric[1].id;
  return mapping;
}

function mappingFor(recipeDefinition, fields, overrides = {}) {
  const list = Array.isArray(fields) ? fields : [], byId = new Set(list.map(field => field.id)), mapping = {...inferMapping(list)};
  for (const role of recipeDefinition.roles || []) if (Object.prototype.hasOwnProperty.call(overrides, role)) mapping[role] = overrides[role] || null;
  for (const role of Object.keys(mapping)) if (mapping[role] && !byId.has(mapping[role])) mapping[role] = null;
  return mapping;
}

function roleStatus(recipeDefinition, fields, mapping) {
  const byId = new Map((fields || []).map(field => [field.id, field])), roleSets = recipeDefinition.role_sets || [recipeDefinition.roles || []];
  const setResults = roleSets.map(roleSet => {
    const unresolved = [], incompatible = [];
    roleSet.forEach(role => {
      const current = mapping[role] ? byId.get(mapping[role]) : null;
      if (!current) { unresolved.push(role); return; }
      if (['value', 'reference_value', 'affected_value'].includes(role) && !numericTypes.has(current.type)) incompatible.push(role);
      if (role === 'cohort' && numericTypes.has(current.type)) incompatible.push(role);
      if (role === 'time' && !['date', 'datetime', 'integer', 'number', 'string'].includes(current.type)) incompatible.push(role);
    });
    return {role_set: roleSet, unresolved, incompatible, valid: !unresolved.length && !incompatible.length};
  });
  if (recipeDefinition.id === 'golden-affected' && mapping.reference_value && mapping.reference_value === mapping.affected_value) {
    const wide = setResults.find(value => value.role_set.includes('reference_value') && value.role_set.includes('affected_value'));
    if (wide) { wide.valid = false; wide.incompatible = [...wide.incompatible, 'reference_value', 'affected_value']; }
  }
  const active = setResults.find(value => value.valid) || setResults[0] || {role_set: [], unresolved: [], incompatible: [], valid: false};
  return {...active, alternatives: setResults, valid: setResults.some(value => value.valid), active_roles: active.role_set};
}

function transformPlan(recipeDefinition, mapping) {
  const id = recipeDefinition.id;
  if (id === 'yield-pareto') return {steps:[
    {type: 'group', field: mapping.category, aggregation: 'sum', source_field: mapping.value},
    {type: 'sort', field: mapping.value, direction: 'desc'},
    {type: 'cumulative_percent', source_field: mapping.value, name: 'Cumulative contribution %'},
  ], summary: 'group category · sum contribution · rank descending · cumulative percent'};
  if (id === 'spc-excursion') return {steps:[{type: 'sort', field: mapping.time, direction: 'asc', stable: true}], summary: 'sort time ascending · preserve supplied specification limits'};
  if (id === 'tool-chamber-matching') return {steps:[{type: 'group', fields: [mapping.tool, mapping.chamber], aggregation: 'mean', missing: 'absent'}], summary: 'group tool × chamber · mean measurement · missing cells absent'};
  if (id === 'golden-affected') return {steps:[{type: 'normalize_cohorts', reference: mapping.reference_value, affected: mapping.affected_value}, {type: 'sort', field: mapping.x, direction: 'asc', stable: true}], summary: 'construct Golden and Affected series · shared ordered domain'};
  if (id === 'wafer-difference') return {steps:[{type: 'match', fields: [mapping.die_x, mapping.die_y]}, {type: 'derive', expression: 'affected - reference', name: 'Delta'}], summary: 'match die coordinates · affected − reference · center scale at zero'};
  if (id === 'pre-post-change') return {steps:[{type: 'group', field: mapping.cohort, aggregation: 'mean'}], summary: 'group cohort · mean measurement · Post mean − Pre mean'};
  if (id === 'distribution-comparison') return {steps:[{type: 'group', field: mapping.cohort, preserve: true}], summary: 'group cohorts · shared measurement scale · no significance claim'};
  return {steps: [], summary: 'review one numeric population · no capability claim'};
}

function targetMapping(recipeId, target, mapping) {
  if (target.view === 'table') return {};
  if (recipeId === 'yield-pareto') {
    if (target.view === 'pareto') return {category: '__category', value: '__contribution'};
    if (target.view === 'metric') return {value: '__contribution', category: '__category'};
  }
  if (recipeId === 'tool-chamber-matching' && target.view === 'bar') return {category: '__tool_chamber', value: '__value', tool: '__tool', chamber: '__chamber'};
  if (recipeId === 'golden-affected' && target.view === 'line') return {x: '__x', y: '__value', value: '__value', series: '__cohort'};
  if (recipeId === 'golden-affected' && (target.view === 'box' || target.view === 'histogram')) return {value: '__value', category: '__cohort'};
  if (recipeId === 'wafer-difference' && target.view === 'wafer') return {die_x: '__die_x', die_y: '__die_y', value: '__delta', reference_value: '__reference', affected_value: '__affected'};
  if (recipeId === 'pre-post-change' && target.view === 'comparison') return {before: '__pre_mean', after: '__post_mean'};
  if (recipeId === 'pre-post-change' && target.view === 'line') return {x: '__cohort', y: '__mean', value: '__mean', category: '__cohort'};
  if ((recipeId === 'distribution-comparison' || recipeId === 'distribution-review') && (target.view === 'box' || target.view === 'histogram')) return {value: '__value', category: recipeId === 'distribution-comparison' ? '__cohort' : undefined};
  if (target.view === 'bar') return {category: mapping.category || mapping.tool || mapping.chamber, value: mapping.value, series: mapping.chamber || mapping.tool};
  if (target.view === 'line') return {x: mapping.x || mapping.time, y: mapping.value, series: mapping.cohort};
  if (target.view === 'box' || target.view === 'histogram') return {value: mapping.value || mapping.affected_value || mapping.reference_value, category: mapping.cohort};
  if (target.view === 'wafer') return {die_x: mapping.die_x, die_y: mapping.die_y, value: mapping.affected_value || mapping.reference_value, reference_value: mapping.reference_value, affected_value: mapping.affected_value};
  if (target.view === 'engineering') return {time: mapping.time || mapping.x, value: mapping.value, subgroup: mapping.subgroup, specification_low: mapping.specification_low, specification_high: mapping.specification_high};
  return {...mapping};
}

function instantiated(recipeDefinition, fields, overrides = {}) {
  const mapping = mappingFor(recipeDefinition, fields, overrides), status = roleStatus(recipeDefinition, fields, mapping), targets = RECIPE_TARGETS[recipeDefinition.id] || [], activeRoles = status.active_roles || recipeDefinition.roles || [], numeric = (fields || []).filter(field => numericTypes.has(field.type));
  const resolvedCount = activeRoles.filter(role => mapping[role]).length;
  return {...clone(recipeDefinition), mapping, missing: status.unresolved, incompatible: status.incompatible, ready: status.valid, compatible: status.valid || resolvedCount > 0 || numeric.length > 0, confidence: activeRoles.length ? resolvedCount / activeRoles.length : 0, active_roles: activeRoles, role_sets: clone(recipeDefinition.role_sets), alternatives: status.alternatives, semantic_tags: [...tagsOf(fields)], targets: clone(targets)};
}

export function instantiateRecipe(recipeValue, fields = [], overrides = {}) {
  const source = typeof recipeValue === 'string' ? ENGINEERING_RECIPES.find(value => value.id === recipeValue) : recipeValue;
  if (!source) return {id: String(recipeValue || ''), name: 'Unknown analysis', ready: false, missing: ['recipe'], incompatible: [], mapping: {}, targets: []};
  return instantiated(source, fields, overrides);
}

export function engineeringRecipeCandidates(fields = []) {
  return ENGINEERING_RECIPES.map(value => instantiateRecipe(value, fields)).filter(value => value.compatible).sort((a, b) => Number(b.ready) - Number(a.ready) || b.confidence - a.confidence || a.name.localeCompare(b.name));
}

export function recommendEngineeringRecipes(fields = []) {
  const list = Array.isArray(fields) ? fields : [], tags = tagsOf(list), numeric = list.filter(field => numericTypes.has(field.type));
  return engineeringRecipeCandidates(list).filter(recipeValue => {
    if (!recipeValue.ready) return false;
    if (recipeValue.id === 'yield-pareto') return tags.has('weight') || /defect|cause|loss|scrap|failure|alarm/i.test(String(list.find(field => field.id === recipeValue.mapping.value)?.name || ''));
    if (recipeValue.id === 'golden-affected') return Boolean((recipeValue.mapping.reference_value && recipeValue.mapping.affected_value) || (recipeValue.mapping.cohort && recipeValue.mapping.value));
    if (recipeValue.id === 'wafer-difference') return Boolean(recipeValue.mapping.reference_value && recipeValue.mapping.affected_value && recipeValue.mapping.die_x && recipeValue.mapping.die_y);
    if (recipeValue.id === 'pre-post-change') return Boolean(recipeValue.mapping.cohort);
    if (recipeValue.id === 'distribution-comparison') return Boolean(recipeValue.mapping.cohort && recipeValue.mapping.value);
    return numeric.length > 0;
  }).sort((a, b) => b.confidence - a.confidence || a.name.localeCompare(b.name));
}

export function recipeExecutionPlan(recipeValue, fields = [], overrides = {}) {
  const instantiatedRecipe = instantiateRecipe(recipeValue, fields, overrides), targets = instantiatedRecipe.targets || [], transform = transformPlan(instantiatedRecipe, instantiatedRecipe.mapping), visuals = targets.map(target => ({...target, mapping: targetMapping(instantiatedRecipe.id, target, instantiatedRecipe.mapping), production: true})), activeRoles = instantiatedRecipe.active_roles || instantiatedRecipe.roles || [];
  return {
    valid: Boolean(instantiatedRecipe.ready && visuals.length),
    status: instantiatedRecipe.ready ? 'ready' : instantiatedRecipe.incompatible.length ? 'incompatible' : 'needs-mapping',
    recipe_id: instantiatedRecipe.id, recipe_version: instantiatedRecipe.version || RECIPE_VERSION, recipe: instantiatedRecipe,
    source_dataset: null, required_roles: clone(activeRoles), role_sets: clone(instantiatedRecipe.role_sets || []), mappings: clone(instantiatedRecipe.mapping || {}), unresolved: clone(instantiatedRecipe.missing || []), incompatible: clone(instantiatedRecipe.incompatible || []), transform_plan: transform, visuals,
    message_roles: visuals.map((visual, index) => ({element: visual.element, role: visual.role || (index === 0 ? 'Primary Evidence' : 'Supporting Evidence')})),
    provenance: {recipe_id: instantiatedRecipe.id, recipe_version: instantiatedRecipe.version || RECIPE_VERSION, mapping: clone(instantiatedRecipe.mapping || {}), transform_summary: transform.summary, required_roles: clone(activeRoles), active_role_set: clone(activeRoles)},
    error: instantiatedRecipe.incompatible.length ? `Choose compatible fields for ${instantiatedRecipe.incompatible.join(', ')}.` : instantiatedRecipe.missing.length ? `Map ${instantiatedRecipe.missing.join(', ')} before applying this analysis.` : null,
  };
}

export function recipePlan(recipeValue, fields = [], overrides = {}) { return recipeExecutionPlan(recipeValue, fields, overrides); }
export function recipeRoleLabel(role) { return ROLE_LABELS[role] || String(role || '').replaceAll('_', ' '); }
export { recipeRoleContract };
