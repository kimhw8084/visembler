// Deterministic semiconductor analysis recipes.
// Compatibility and mapping review live here. Value-level execution is kept
// in analysis_semantics.mjs so renderers cannot accidentally define meaning.

import { ANALYSIS_SEMANTICS_VERSION, STATISTICAL_ANALYSIS_VERSION, isStrictFiniteNumber, recipeRoleContract } from './analysis_semantics.mjs';

const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
const numericTypes = new Set(['integer', 'number']);
const tagsOf = fields => new Set((fields || []).flatMap(field => Array.isArray(field.semantic_tags) ? field.semantic_tags : []));
const fieldByTag = (fields, tag) => (fields || []).find(field => (field.semantic_tags || []).includes(tag));
const fieldByName = (fields, pattern) => (fields || []).find(field => pattern.test(String(field.name || '').toLowerCase()));
const fieldId = field => field?.id || null;
function xbarStructureCompatible(fields, mapping, rows) {
  if (!Array.isArray(rows)) return true;
  const subgroupIndex = (fields || []).findIndex(field => field.id === mapping?.subgroup);
  const valueIndex = (fields || []).findIndex(field => field.id === mapping?.value);
  if (subgroupIndex < 0 || valueIndex < 0) return false;
  const groups = new Map();
  for (const row of rows) {
    const subgroup = String(row?.[subgroupIndex] ?? '').trim();
    const value = row?.[valueIndex];
    if (!subgroup || !isStrictFiniteNumber(value)) return false;
    groups.set(subgroup, (groups.get(subgroup) || 0) + 1);
  }
  const sizes = [...groups.values()];
  return sizes.length >= 2 && sizes.every(size => size >= 2 && size <= 10) && new Set(sizes).size === 1;
}

function capabilityStructureCompatible(fields, mapping, rows) {
  if (!Array.isArray(rows)) return true;
  const valueIndex = (fields || []).findIndex(field => field.id === mapping?.value);
  const lowIndex = (fields || []).findIndex(field => field.id === mapping?.specification_low);
  const highIndex = (fields || []).findIndex(field => field.id === mapping?.specification_high);
  if (valueIndex < 0 || (lowIndex < 0 && highIndex < 0) || rows.length < 2) return false;
  const values = [];
  let low = null, high = null;
  for (const row of rows) {
    const value = row?.[valueIndex];
    if (!isStrictFiniteNumber(value)) return false;
    values.push(Number(value));
    for (const [index, target] of [[lowIndex, 'low'], [highIndex, 'high']]) {
      if (index < 0) continue;
      const candidate = row?.[index];
      if (!isStrictFiniteNumber(candidate)) return false;
      const numeric = Number(candidate);
      if (target === 'low' && low !== null && low !== numeric) return false;
      if (target === 'high' && high !== null && high !== numeric) return false;
      if (target === 'low') low = numeric;
      if (target === 'high') high = numeric;
    }
  }
  if (low !== null && high !== null && !(high > low)) return false;
  return new Set(values).size > 1;
}

function doeStructureCompatible(fields, mapping, rows) {
  if (!Array.isArray(rows)) return true;
  const factorAIndex = (fields || []).findIndex(field => field.id === mapping?.factor_a);
  const factorBIndex = (fields || []).findIndex(field => field.id === mapping?.factor_b);
  const responseIndex = (fields || []).findIndex(field => field.id === mapping?.response);
  if (factorAIndex < 0 || factorBIndex < 0 || responseIndex < 0 || !rows.length) return false;
  const levelsA = new Set(), levelsB = new Set(), cells = new Set();
  for (const row of rows) {
    const a = String(row?.[factorAIndex] ?? '').trim();
    const b = String(row?.[factorBIndex] ?? '').trim();
    if (!a || !b || !isStrictFiniteNumber(row?.[responseIndex])) return false;
    levelsA.add(a); levelsB.add(b); cells.add(`${a}\u0000${b}`);
  }
  if (levelsA.size < 2 || levelsB.size < 2) return false;
  for (const a of levelsA) for (const b of levelsB) if (!cells.has(`${a}\u0000${b}`)) return false;
  return true;
}

function strongDoeSemantics(fields) {
  const tagged = tagsOf(fields);
  if (tagged.has('factor_a') && tagged.has('factor_b') && tagged.has('response')) return true;
  return Boolean(fieldByName(fields, /factor\s*(a|1)|factor.?a/) && fieldByName(fields, /factor\s*(b|2)|factor.?b/) && fieldByName(fields, /response|output/));
}

export const RECIPE_VERSION = ANALYSIS_SEMANTICS_VERSION;
export const RECIPE_VERSIONS = Object.freeze({
  'yield-pareto': 'v2', 'spc-excursion': 'v2', 'tool-chamber-matching': 'v2',
  'golden-affected': 'v2', 'wafer-difference': 'v2', 'pre-post-change': 'v2',
  'distribution-comparison': 'v2', 'distribution-review': 'v1',
  'xbar-r-process-review': STATISTICAL_ANALYSIS_VERSION, 'process-capability': STATISTICAL_ANALYSIS_VERSION, 'doe-response-review': STATISTICAL_ANALYSIS_VERSION,
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
    {engine: 'WaferFabEngine', element: 'Tool × Chamber Matrix', view: 'tool_chamber_matrix', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'golden-affected': Object.freeze([
    {engine: 'WaferFabEngine', element: 'Golden vs Affected Profile', view: 'golden_affected_profile', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'wafer-difference': Object.freeze([
    {engine: 'WaferFabEngine', element: 'Wafer Difference Map', view: 'wafer_difference', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'pre-post-change': Object.freeze([
    {engine: 'ComparisonEngine', element: 'Before/After KPI', view: 'comparison', role: 'summary'},
    {engine: 'CoreChartEngine', element: 'Line Chart', view: 'line', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'distribution-comparison': Object.freeze([
    {engine: 'WaferFabEngine', element: 'Control vs Affected Distribution', view: 'control_affected_distribution', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Histogram', view: 'histogram', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'distribution-review': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Histogram', view: 'histogram', role: 'distribution'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'xbar-r-process-review': Object.freeze([
    {engine: 'EngineeringChartEngine', element: 'Xbar-R Chart', view: 'xbarr', role: 'primary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
    {engine: 'MetricEngine', element: 'Hero KPI', view: 'metric', role: 'summary'},
  ]),
  'process-capability': Object.freeze([
    {engine: 'CoreChartEngine', element: 'Histogram', view: 'histogram', role: 'primary'},
    {engine: 'CoreChartEngine', element: 'Box Plot', view: 'box', role: 'distribution'},
    {engine: 'MetricEngine', element: 'Hero KPI', view: 'metric', role: 'summary'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'evidence'},
  ]),
  'doe-response-review': Object.freeze([
    {engine: 'EngineeringChartEngine', element: 'DOE Main Effects', view: 'doe_main', role: 'primary'},
    {engine: 'EngineeringChartEngine', element: 'DOE Interaction Plot', view: 'doe_interaction', role: 'evidence'},
    {engine: 'TableEngine', element: 'Clean Table', view: 'table', role: 'supporting'},
  ]),
});

const ROLE_LABELS = Object.freeze({
  category: 'Cause / category', value: 'Contribution / measurement', time: 'Ordered time',
  tool: 'Tool', chamber: 'Chamber', cohort: 'Cohort / condition', x: 'Process position',
  die_x: 'Die X', die_y: 'Die Y', reference_value: 'Reference / golden value',
  affected_value: 'Affected value', subgroup: 'Subgroup', order: 'Subgroup order', measurement: 'Measurement',
  specification_low: 'LSL', specification_high: 'USL', target: 'Target', factor_a: 'Factor A', factor_b: 'Factor B', response: 'Response',
});

const recipe = (id, name, reason, visuals, role_sets, optional_roles = []) => Object.freeze({id, version: RECIPE_VERSIONS[id], name, reason, visuals, roles: [...new Set(role_sets.flat())], role_sets, optional_roles});

export const ENGINEERING_RECIPES = Object.freeze([
  recipe('yield-pareto', 'Yield Pareto', 'Grouped contribution ranked with cumulative loss makes the largest yield drivers obvious.', ['Pareto', 'Clean Table', 'Hero KPI'], [['category', 'value']]),
  recipe('spc-excursion', 'SPC Excursion Review', 'Ordered measurements can be reviewed without relying on clipboard row order.', ['SPC Control Chart', 'Clean Table'], [['time', 'value']]),
  recipe('tool-chamber-matching', 'Tool / Chamber Matching', 'Tool, chamber, and a governed aggregation make cell-level equipment differences visible.', ['Tool × Chamber Matrix', 'Clean Table'], [['tool', 'chamber', 'value']]),
  recipe('golden-affected', 'Golden vs Affected', 'A wide reference/affected pair or long cohort schema creates two aligned populations.', ['Golden vs Affected Profile', 'Box Plot', 'Clean Table'], [['x', 'reference_value', 'affected_value'], ['x', 'cohort', 'value']]),
  recipe('wafer-difference', 'Wafer Difference Investigation', 'Matched die coordinates compute signed affected-minus-reference deltas on a zero-centered scale.', ['Wafer Difference Map', 'Clean Table'], [['die_x', 'die_y', 'reference_value', 'affected_value']]),
  recipe('pre-post-change', 'Pre / Post Process Change', 'Pre and Post populations are compared using explicit cohort means.', ['Before/After KPI', 'Line Chart', 'Clean Table'], [['cohort', 'value']]),
  recipe('distribution-comparison', 'Distribution Comparison', 'Two or more cohorts are compared on one shared measurement scale without an implied significance claim.', ['Control vs Affected Distribution', 'Histogram', 'Clean Table'], [['cohort', 'value']]),
  recipe('distribution-review', 'Distribution Review', 'One numeric population is profiled for spread, outliers, and distribution shape.', ['Box Plot', 'Histogram', 'Clean Table'], [['value']]),
  recipe('xbar-r-process-review', 'Xbar-R Process Review', 'Constant-size repeated-measurement subgroups support X̄/R monitoring; signals describe unusual behavior, not root cause.', ['Xbar-R Chart', 'Clean Table', 'Hero KPI'], [['subgroup', 'value']], ['order', 'specification_low', 'specification_high']),
  recipe('process-capability', 'Process Capability', 'A measurement with at least one explicit specification limit supports Cp/Cpk capability statistics using sample variation.', ['Histogram', 'Box Plot', 'Hero KPI', 'Clean Table'], [['value', 'specification_low'], ['value', 'specification_high'], ['value', 'specification_low', 'specification_high']], ['target', 'cohort']),
  recipe('doe-response-review', 'DOE Response Review', 'Observed factor-level and cell means provide a descriptive DOE response review without significance or causal claims.', ['DOE Main Effects', 'DOE Interaction Plot', 'Clean Table'], [['factor_a', 'factor_b', 'response']], ['factor_c']),
]);

function resolve(fields, role) {
  const tagged = fieldByTag(fields, role); if (tagged) return tagged;
  if (role === 'category') { const category = fieldByTag(fields, 'category'); if (category) return category; }
  if (role === 'value') { const value = fieldByTag(fields, 'value') || fieldByTag(fields, 'weight'); if (value) return value; }
  if (role === 'time') { const time = fieldByTag(fields, 'time'); if (time) return time; }
  if (role === 'cohort') { const cohort = fieldByTag(fields, 'cohort') || fieldByTag(fields, 'status'); if (cohort) return cohort; }
  if (role === 'x') { const axis = fieldByTag(fields, 'x') || fieldByTag(fields, 'time') || fieldByTag(fields, 'process'); if (axis) return axis; }
  if (role === 'subgroup') { const subgroup = fieldByTag(fields, 'subgroup'); if (subgroup) return subgroup; }
  if (role === 'order') { const order = fieldByTag(fields, 'time') || fieldByTag(fields, 'order') || fieldByName(fields, /(timestamp|time|date|sequence|order|run)/); if (order) return order; }
  if (role === 'factor_a' || role === 'factor_b' || role === 'factor_c') {
    const categorical = (fields || []).filter(field => !numericTypes.has(field.type) && !['subgroup', 'cohort', 'status'].some(tag => (field.semantic_tags || []).includes(tag)));
    const index = role === 'factor_a' ? 0 : role === 'factor_b' ? 1 : 2;
    if (categorical[index]) return categorical[index];
  }
  if (role === 'response') { const response = fieldByTag(fields, 'response') || fieldByTag(fields, 'value'); if (response) return response; }
  const patterns = {
    category: /(defect|cause|failure|alarm|category|reason|bin)/,
    value: /(yield|measure|value|count|loss|defect|rate|metric)/,
    time: /(timestamp|time|date|sequence|order|step)/,
    cohort: /(cohort|status|condition|population|group|golden|affected|control|reference)/,
    x: /(position|process|time|sequence|order|step)/,
    reference_value: /(reference|golden|baseline|control)/,
    affected_value: /(affected|actual|test|failed|exposed)/,
    subgroup: /(subgroup|sample.?group|sample|group)/, order: /(timestamp|time|date|sequence|order|run)/,
    factor_a: /(factor.?a|factor.?1|factor1)/, factor_b: /(factor.?b|factor.?2|factor2)/, factor_c: /(factor.?c|factor.?3|factor3)/,
    response: /(response|outcome|result|yield)/, target: /(^|_)(target|nominal)(_|$)/,
    tool: /tool/, chamber: /chamber/, die_x: /die.?x|wafer.?x/, die_y: /die.?y|wafer.?y/,
    specification_low: /spec(ification)?.?(low|lower)|lsl|lower.?limit/,
    specification_high: /spec(ification)?.?(high|upper)|usl|upper.?limit/,
  };
  const named = patterns[role] ? fieldByName(fields, patterns[role]) : null;
  if (['value', 'reference_value', 'affected_value', 'response', 'specification_low', 'specification_high', 'target'].includes(role)) {
    if (named && numericTypes.has(named.type)) return named;
    if (['specification_low', 'specification_high', 'target'].includes(role)) return null;
    return (fields || []).find(field => numericTypes.has(field.type)) || null;
  }
  return named;
}

function inferMapping(fields) {
  const list = Array.isArray(fields) ? fields : [], numeric = list.filter(field => numericTypes.has(field.type));
  const mapping = {};
  for (const role of ['category', 'value', 'time', 'tool', 'chamber', 'cohort', 'x', 'die_x', 'die_y', 'reference_value', 'affected_value', 'subgroup', 'order', 'specification_low', 'specification_high', 'target', 'factor_a', 'factor_b', 'factor_c', 'response']) {
    const value = resolve(list, role); if (value) mapping[role] = fieldId(value);
  }
  if (!mapping.value && numeric[0]) mapping.value = numeric[0].id;
  if (!mapping.x) mapping.x = mapping.time || numeric[0]?.id;
  if (!mapping.y && numeric[1]) mapping.y = numeric[1].id;
  return mapping;
}

function mappingFor(recipeDefinition, fields, overrides = {}) {
  const list = Array.isArray(fields) ? fields : [], byId = new Set(list.map(field => field.id)), mapping = {...inferMapping(list)};
  for (const role of [...(recipeDefinition.roles || []), ...(recipeDefinition.optional_roles || [])]) if (Object.prototype.hasOwnProperty.call(overrides, role)) mapping[role] = overrides[role] || null;
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
      if (['value', 'reference_value', 'affected_value', 'response', 'specification_low', 'specification_high', 'target'].includes(role) && !numericTypes.has(current.type)) incompatible.push(role);
      if (role === 'cohort' && numericTypes.has(current.type)) incompatible.push(role);
      if (role === 'time' && !['date', 'datetime', 'integer', 'number', 'string'].includes(current.type)) incompatible.push(role);
    });
    return {role_set: roleSet, unresolved, incompatible, valid: !unresolved.length && !incompatible.length};
  });
  if (recipeDefinition.id === 'golden-affected' && mapping.reference_value && mapping.reference_value === mapping.affected_value) {
    const wide = setResults.find(value => value.role_set.includes('reference_value') && value.role_set.includes('affected_value'));
    if (wide) { wide.valid = false; wide.incompatible = [...wide.incompatible, 'reference_value', 'affected_value']; }
  }
  if (recipeDefinition.id === 'process-capability') {
    setResults.forEach((setResult) => {
      if (setResult.role_set.includes('specification_low') && mapping.specification_low === mapping.value) { setResult.valid = false; setResult.incompatible.push('specification_low'); }
      if (setResult.role_set.includes('specification_high') && mapping.specification_high === mapping.value) { setResult.valid = false; setResult.incompatible.push('specification_high'); }
    });
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
  if (id === 'xbar-r-process-review') return {steps:[{type: 'group', field: mapping.subgroup, preserve: true}, ...(mapping.order ? [{type: 'sort', field: mapping.order, direction: 'asc', stable: true}] : []), {type: 'xbar_r', subgroup_field: mapping.subgroup, value_field: mapping.value}], summary: 'group constant-size subgroups · order deterministically · compute X̄/R control limits'};
  if (id === 'process-capability') return {steps:[{type: 'capability', value_field: mapping.value, specification_low: mapping.specification_low || null, specification_high: mapping.specification_high || null, target: mapping.target || null}], summary: 'compute sample sigma · Cp/Cpu/Cpl/Cpk · preserve specification provenance'};
  if (id === 'doe-response-review') return {steps:[{type: 'doe_main_effects', factors: [mapping.factor_a, mapping.factor_b], response: mapping.response}, {type: 'doe_interaction', factor_a: mapping.factor_a, factor_b: mapping.factor_b, response: mapping.response}], summary: 'mean response by factor level and cell · descriptive interaction only'};
  return {steps: [], summary: 'review one numeric population · no capability claim'};
}

function targetMapping(recipeId, target, mapping) {
  if (target.view === 'table') return {};
  if (recipeId === 'yield-pareto') {
    if (target.view === 'pareto') return {category: '__category', value: '__contribution'};
    if (target.view === 'metric') return {value: '__contribution', category: '__category'};
  }
  if (recipeId === 'tool-chamber-matching' && target.view === 'tool_chamber_matrix') return {tool: '__tool', chamber: '__chamber', value: '__value'};
  if (recipeId === 'golden-affected' && target.view === 'line') return {x: '__x', y: '__value', value: '__value', series: '__cohort'};
  if (recipeId === 'golden-affected' && target.view === 'golden_affected_profile') return {x: '__x', cohort: '__cohort', value: '__value'};
  if (recipeId === 'golden-affected' && (target.view === 'box' || target.view === 'histogram')) return {value: '__value', category: '__cohort'};
  if (recipeId === 'wafer-difference' && target.view === 'wafer_difference') return {die_x: '__die_x', die_y: '__die_y', value: '__delta', delta: '__delta', reference_value: '__reference', affected_value: '__affected'};
  if (recipeId === 'pre-post-change' && target.view === 'comparison') return {before: '__pre_mean', after: '__post_mean'};
  if (recipeId === 'pre-post-change' && target.view === 'line') return {x: '__cohort', y: '__mean', value: '__mean', category: '__cohort'};
  if ((recipeId === 'distribution-comparison' || recipeId === 'distribution-review') && (target.view === 'box' || target.view === 'histogram')) return {value: '__value', category: recipeId === 'distribution-comparison' ? '__cohort' : undefined};
  if (recipeId === 'distribution-comparison' && target.view === 'control_affected_distribution') return {cohort: '__cohort', value: '__value'};
  if (recipeId === 'xbar-r-process-review' && target.view === 'xbarr') return {subgroup: '__subgroup', order: '__sequence', value: '__mean', range: '__range'};
  if (recipeId === 'process-capability' && ['histogram', 'box'].includes(target.view)) return {value: '__value', specification_low: '__lsl', specification_high: '__usl', target: '__target'};
  if (recipeId === 'process-capability' && target.view === 'metric') return {value: '__cpk'};
  if (recipeId === 'doe-response-review' && target.view === 'doe_main') return {factor_a: '__factor_a', factor_b: '__factor_b', response: '__response'};
  if (recipeId === 'doe-response-review' && target.view === 'doe_interaction') return {factor_a: '__factor_a', factor_b: '__factor_b', response: '__response'};
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
  const optional = (recipeDefinition.optional_roles || []).filter(role => mapping[role]);
  return {...clone(recipeDefinition), mapping, missing: status.unresolved, incompatible: status.incompatible, ready: status.valid, compatible: status.valid || resolvedCount > 0 || numeric.length > 0, confidence: activeRoles.length ? resolvedCount / activeRoles.length : 0, active_roles: activeRoles, optional_roles: optional, role_sets: clone(recipeDefinition.role_sets), alternatives: status.alternatives, semantic_tags: [...tagsOf(fields)], targets: clone(targets)};
}

export function instantiateRecipe(recipeValue, fields = [], overrides = {}) {
  const source = typeof recipeValue === 'string' ? ENGINEERING_RECIPES.find(value => value.id === recipeValue) : recipeValue;
  if (!source) return {id: String(recipeValue || ''), name: 'Unknown analysis', ready: false, missing: ['recipe'], incompatible: [], mapping: {}, targets: []};
  return instantiated(source, fields, overrides);
}

export function engineeringRecipeCandidates(fields = []) {
  const list = fields || [];
  const tags = tagsOf(list);
  const priority = recipeValue => {
    if (recipeValue.id === 'xbar-r-process-review' && tags.has('subgroup')) return 30;
    if (recipeValue.id === 'process-capability' && (tags.has('specification_low') || tags.has('specification_high'))) return 30;
    if (recipeValue.id === 'doe-response-review' && tags.has('factor_a') && tags.has('factor_b') && tags.has('response')) return 30;
    if (recipeValue.id === 'wafer-difference' && tags.has('die_x') && tags.has('die_y')) return 30;
    if (recipeValue.id === 'tool-chamber-matching' && tags.has('tool') && tags.has('chamber')) return 30;
    if (recipeValue.id === 'golden-affected' && (tags.has('reference_value') || tags.has('affected_value') || tags.has('cohort'))) return 30;
    return 0;
  };
  return ENGINEERING_RECIPES.map(value => instantiateRecipe(value, list)).filter(value => value.compatible).sort((a, b) => priority(b) - priority(a) || Number(b.ready) - Number(a.ready) || b.confidence - a.confidence || a.name.localeCompare(b.name));
}

export function recommendEngineeringRecipes(fields = [], rows = null) {
  const list = Array.isArray(fields) ? fields : [], tags = tagsOf(list), numeric = list.filter(field => numericTypes.has(field.type));
  return engineeringRecipeCandidates(list).filter(recipeValue => {
    if (!recipeValue.ready) return false;
    if (recipeValue.id === 'yield-pareto') return tags.has('weight') || /defect|cause|loss|scrap|failure|alarm/i.test(String(list.find(field => field.id === recipeValue.mapping.value)?.name || ''));
    if (recipeValue.id === 'golden-affected') return Boolean((recipeValue.mapping.reference_value && recipeValue.mapping.affected_value) || (recipeValue.mapping.cohort && recipeValue.mapping.value));
    if (recipeValue.id === 'wafer-difference') return Boolean(recipeValue.mapping.reference_value && recipeValue.mapping.affected_value && recipeValue.mapping.die_x && recipeValue.mapping.die_y);
    if (recipeValue.id === 'pre-post-change') return Boolean(recipeValue.mapping.cohort);
    if (recipeValue.id === 'distribution-comparison') return Boolean(recipeValue.mapping.cohort && recipeValue.mapping.value);
    if (recipeValue.id === 'xbar-r-process-review') return Boolean(recipeValue.mapping.subgroup && recipeValue.mapping.value && xbarStructureCompatible(list, recipeValue.mapping, rows));
    if (recipeValue.id === 'process-capability') return Boolean(recipeValue.mapping.value && (recipeValue.mapping.specification_low || recipeValue.mapping.specification_high) && capabilityStructureCompatible(list, recipeValue.mapping, rows));
    if (recipeValue.id === 'doe-response-review') return Boolean(strongDoeSemantics(list) && recipeValue.mapping.factor_a && recipeValue.mapping.factor_b && recipeValue.mapping.response && doeStructureCompatible(list, recipeValue.mapping, rows));
    return numeric.length > 0;
  }).sort((a, b) => b.confidence - a.confidence || a.name.localeCompare(b.name));
}

export function recipeExecutionPlan(recipeValue, fields = [], overrides = {}) {
  const instantiatedRecipe = instantiateRecipe(recipeValue, fields, overrides), targets = instantiatedRecipe.targets || [], transform = transformPlan(instantiatedRecipe, instantiatedRecipe.mapping), visuals = targets.map(target => ({...target, mapping: targetMapping(instantiatedRecipe.id, target, instantiatedRecipe.mapping), production: true})), activeRoles = instantiatedRecipe.active_roles || instantiatedRecipe.roles || [];
  return {
    valid: Boolean(instantiatedRecipe.ready && visuals.length),
    status: instantiatedRecipe.ready ? 'ready' : instantiatedRecipe.incompatible.length ? 'incompatible' : 'needs-mapping',
    recipe_id: instantiatedRecipe.id, recipe_version: instantiatedRecipe.version || RECIPE_VERSION, recipe: instantiatedRecipe,
    source_dataset: null, required_roles: clone(activeRoles), optional_roles: clone(instantiatedRecipe.optional_roles || []), role_sets: clone(instantiatedRecipe.role_sets || []), mappings: clone(instantiatedRecipe.mapping || {}), unresolved: clone(instantiatedRecipe.missing || []), incompatible: clone(instantiatedRecipe.incompatible || []), transform_plan: transform, visuals,
    message_roles: visuals.map((visual, index) => ({element: visual.element, role: visual.role || (index === 0 ? 'Primary Evidence' : 'Supporting Evidence')})),
    provenance: {recipe_id: instantiatedRecipe.id, recipe_version: instantiatedRecipe.version || RECIPE_VERSION, mapping: clone(instantiatedRecipe.mapping || {}), transform_summary: transform.summary, required_roles: clone(activeRoles), optional_roles: clone(instantiatedRecipe.optional_roles || []), active_role_set: clone(activeRoles)},
    error: instantiatedRecipe.incompatible.length ? `Choose compatible fields for ${instantiatedRecipe.incompatible.join(', ')}.` : instantiatedRecipe.missing.length ? `Map ${instantiatedRecipe.missing.join(', ')} before applying this analysis.` : null,
  };
}

export function recipePlan(recipeValue, fields = [], overrides = {}) { return recipeExecutionPlan(recipeValue, fields, overrides); }
export function recipeRoleLabel(role) { return ROLE_LABELS[role] || String(role || '').replaceAll('_', ' '); }
export { recipeRoleContract };
