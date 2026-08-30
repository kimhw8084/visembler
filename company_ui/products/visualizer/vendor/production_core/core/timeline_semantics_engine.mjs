import { GraphContractError, validateGraph } from './graph_semantics_engine.mjs';

export class TimelineContractError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'TimelineContractError';
    this.code = code;
    this.details = Object.freeze({ ...details });
  }
}

export const TIMELINE_MODES = Object.freeze(['dated', 'sequence']);
export const DEPENDENCY_TYPES = Object.freeze(['FS', 'SS', 'FF', 'SF']);
const DAY_MS = 86400000;
const fail = (code, message, details = {}) => { throw new TimelineContractError(code, message, details); };

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map((k) => [k, stable(value[k])]));
  return value;
}
function fp(value) {
  const text = JSON.stringify(stable(value)); let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return `t1-${h.toString(16).padStart(8, '0')}`;
}
function id(value, what, index) {
  if (typeof value !== 'string' || !value.trim()) fail('TIMELINE_ID', `${what} requires a non-empty string id.`, { index });
  return value;
}
function parseIsoDate(value, field, taskId) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) fail('TIMELINE_DATE', `${field} must be an explicit ISO YYYY-MM-DD date.`, { taskId, field, value });
  const [y,m,d] = value.split('-').map(Number);
  const ms = Date.UTC(y, m - 1, d);
  const check = new Date(ms);
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== m - 1 || check.getUTCDate() !== d) fail('TIMELINE_DATE', `${field} is not a valid calendar date.`, { taskId, field, value });
  return { iso: value, day: Math.floor(ms / DAY_MS) };
}
function toIsoDay(day) { return new Date(day * DAY_MS).toISOString().slice(0, 10); }
function integer(value, field, details = {}) {
  if (!Number.isInteger(value)) fail('TIMELINE_INTEGER', `${field} must be an integer.`, { ...details, value });
  return value;
}

function normalizeDependencies(deps, taskIds, mode) {
  if (deps == null) return [];
  if (!Array.isArray(deps)) fail('TIMELINE_DEPENDENCIES', 'Dependencies must be an array.');
  return deps.map((dep, index) => {
    if (!dep || typeof dep !== 'object') fail('TIMELINE_DEPENDENCY', 'Each dependency must be an object.', { index });
    const source = id(dep.source, 'Dependency source', index), target = id(dep.target, 'Dependency target', index);
    if (!taskIds.has(source) || !taskIds.has(target)) fail('TIMELINE_DEPENDENCY_NODE', 'Dependency references an unknown task.', { index, source, target });
    if (source === target) fail('TIMELINE_DEPENDENCY_SELF', 'Task cannot depend on itself.', { source });
    if (mode === 'sequence') {
      if (dep.type != null && dep.type !== 'sequence') fail('TIMELINE_SEQUENCE_DEPENDENCY', 'Sequence-only timeline cannot claim dated dependency semantics.', { index, type: dep.type });
      if (dep.lagDays != null && dep.lagDays !== 0) fail('TIMELINE_SEQUENCE_LAG', 'Sequence-only timeline cannot carry date lag.', { index, lagDays: dep.lagDays });
      return Object.freeze({ id: String(dep.id ?? `dep:${source}->${target}`), source, target, type: 'sequence', lagDays: 0 });
    }
    const type = dep.type ?? 'FS';
    if (!DEPENDENCY_TYPES.includes(type)) fail('TIMELINE_DEPENDENCY_TYPE', `Unsupported dependency type: ${type}`, { index });
    const lagDays = dep.lagDays == null ? 0 : integer(dep.lagDays, 'lagDays', { index });
    return Object.freeze({ id: String(dep.id ?? `dep:${source}->${target}:${type}:${lagDays}`), source, target, type, lagDays });
  }).sort((a,b)=>a.source.localeCompare(b.source)||a.target.localeCompare(b.target)||a.type.localeCompare(b.type)||a.lagDays-b.lagDays||a.id.localeCompare(b.id));
}

function validateDatedDependency(dep, taskMap) {
  const a = taskMap.get(dep.source), b = taskMap.get(dep.target), lag = dep.lagDays;
  const rules = {
    FS: { lhs: b.startDay, rhs: a.endDay + lag, target: 'target.start', source: 'source.end' },
    SS: { lhs: b.startDay, rhs: a.startDay + lag, target: 'target.start', source: 'source.start' },
    FF: { lhs: b.endDay, rhs: a.endDay + lag, target: 'target.end', source: 'source.end' },
    SF: { lhs: b.endDay, rhs: a.startDay + lag, target: 'target.end', source: 'source.start' },
  };
  const rule = rules[dep.type];
  if (rule.lhs < rule.rhs) fail('TIMELINE_DEPENDENCY_VIOLATION', `${dep.type} dependency is violated by the explicit schedule.`, { dependency: dep.id, source: dep.source, target: dep.target, lagDays: lag, requiredDay: toIsoDay(rule.rhs), actualDay: toIsoDay(rule.lhs), sourceAnchor: rule.source, targetAnchor: rule.target });
}

export function prepareTimeline(mode, input = {}, options = {}) {
  if (!TIMELINE_MODES.includes(mode)) fail('TIMELINE_MODE', `Unsupported timeline mode: ${mode}`, { mode });
  if (!Array.isArray(input.tasks) || input.tasks.length === 0) fail('TIMELINE_TASKS', 'Timeline requires at least one task.');
  const seen = new Set();
  const tasks = input.tasks.map((task, index) => {
    if (!task || typeof task !== 'object') fail('TIMELINE_TASK', 'Each task must be an object.', { index });
    const taskId = id(task.id, 'Task', index);
    if (seen.has(taskId)) fail('TIMELINE_DUPLICATE_TASK', `Duplicate task id: ${taskId}`, { taskId, index });
    seen.add(taskId);
    const base = { id: taskId, label: String(task.label ?? taskId), milestone: task.milestone === true };
    if (mode === 'sequence') {
      if (task.start != null || task.end != null || task.durationDays != null) fail('TIMELINE_SEQUENCE_DATE', 'Sequence-only task must not contain dates/durations.', { taskId });
      const order = task.order == null ? index : integer(task.order, 'order', { taskId });
      return Object.freeze({ ...base, order, orderSource: task.order == null ? 'input_position' : 'explicit' });
    }
    const start = parseIsoDate(task.start, 'start', taskId);
    let end = null; let provenance = 'explicit_end';
    if (task.end != null) end = parseIsoDate(task.end, 'end', taskId);
    const declaredDuration = task.durationDays == null ? null : integer(task.durationDays, 'durationDays', { taskId });
    if (declaredDuration != null && declaredDuration < 0) fail('TIMELINE_DURATION', 'durationDays cannot be negative.', { taskId, durationDays: declaredDuration });
    if (end == null && declaredDuration == null) {
      if (!base.milestone) fail('TIMELINE_END_REQUIRED', 'Dated non-milestone task requires explicit end or durationDays.', { taskId });
      end = start; provenance = 'milestone_same_day';
    } else if (end == null) {
      end = { day: start.day + declaredDuration, iso: toIsoDay(start.day + declaredDuration) }; provenance = 'derived_from_duration';
    }
    if (end.day < start.day) fail('TIMELINE_RANGE', 'Task end cannot precede start.', { taskId, start: start.iso, end: end.iso });
    const durationDays = end.day - start.day;
    if (declaredDuration != null && task.end != null && declaredDuration !== durationDays) fail('TIMELINE_DURATION_MISMATCH', 'Explicit end and durationDays disagree.', { taskId, declaredDuration, calculatedDuration: durationDays });
    if (base.milestone && durationDays !== 0) fail('TIMELINE_MILESTONE_DURATION', 'Milestone must have zero duration.', { taskId, durationDays });
    return Object.freeze({ ...base, start: start.iso, end: end.iso, startDay: start.day, endDay: end.day, durationDays, dateProvenance: Object.freeze({ start: 'explicit', end: provenance }) });
  }).sort((a,b)=>mode==='sequence'?(a.order-b.order||a.id.localeCompare(b.id)):(a.startDay-b.startDay||a.endDay-b.endDay||a.id.localeCompare(b.id)));

  if (mode === 'sequence') {
    const orders = tasks.map((t)=>t.order);
    if (new Set(orders).size !== orders.length) fail('TIMELINE_SEQUENCE_ORDER', 'Sequence order values must be unique.', { orders });
  }
  const taskIds = new Set(tasks.map((t)=>t.id));
  const dependencies = normalizeDependencies(input.dependencies, taskIds, mode);
  let graph;
  try {
    graph = validateGraph('dag', { nodes: tasks.map((t)=>({id:t.id,label:t.label})), edges: dependencies.map((d)=>({id:d.id,source:d.source,target:d.target})) });
  } catch (error) {
    if (error instanceof GraphContractError) fail('TIMELINE_DEPENDENCY_CYCLE', 'Timeline dependencies must be acyclic.', { graphCode: error.code, ...error.details });
    throw error;
  }
  if (mode === 'dated' && options.validateSchedule !== false) {
    const map = new Map(tasks.map((t)=>[t.id,t]));
    dependencies.forEach((dep)=>validateDatedDependency(dep,map));
  }
  const plan = {
    schema_version: 1,
    mode,
    calendar: mode === 'dated' ? (options.calendar ?? 'calendar_days') : null,
    tasks,
    dependencies,
    topologicalOrder: graph.topologicalOrder,
    dateSemantics: mode === 'dated' ? 'explicit_or_declared_duration_only' : 'none',
  };
  plan.fingerprint = fp(plan);
  return Object.freeze(plan);
}
