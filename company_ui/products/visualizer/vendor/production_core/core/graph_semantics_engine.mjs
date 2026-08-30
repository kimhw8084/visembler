/**
 * Visualizer graph semantics gate.
 *
 * Layout/routing engines consume only plans returned by validateGraph(). This
 * layer deliberately knows nothing about pixels: it proves semantic validity
 * before Golden Connector/layout code is allowed to run.
 */
export class GraphContractError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'GraphContractError';
    this.code = code;
    this.details = Object.freeze({ ...details });
  }
}

export const GRAPH_KINDS = Object.freeze(['dag', 'tree', 'network', 'flow', 'state_machine']);

const fail = (code, message, details = {}) => { throw new GraphContractError(code, message, details); };
const finite = (v) => typeof v === 'number' && Number.isFinite(v);

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  }
  return value;
}
function fingerprint(value) {
  const text = JSON.stringify(stableValue(value));
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `g1-${h.toString(16).padStart(8, '0')}`;
}
function requireId(value, what, index) {
  if (typeof value !== 'string' || !value.trim()) fail('GRAPH_ID', `${what} requires a non-empty string id.`, { index });
  return value;
}

function normalizeNodes(nodes) {
  if (!Array.isArray(nodes) || nodes.length === 0) fail('GRAPH_NODES', 'Graph requires at least one node.');
  const ids = new Set();
  return nodes.map((node, index) => {
    if (!node || typeof node !== 'object') fail('GRAPH_NODE', 'Each graph node must be an object.', { index });
    const id = requireId(node.id, 'Graph node', index);
    if (ids.has(id)) fail('GRAPH_DUPLICATE_NODE', `Duplicate graph node id: ${id}`, { id, index });
    ids.add(id);
    return Object.freeze({ ...node, id, label: String(node.label ?? id) });
  }).sort((a, b) => a.id.localeCompare(b.id));
}

function normalizeEdges(edges, nodeIds, kind) {
  if (!Array.isArray(edges)) fail('GRAPH_EDGES', 'Graph edges must be an array.');
  const explicitIds = new Set();
  const normalized = edges.map((edge, index) => {
    if (!edge || typeof edge !== 'object') fail('GRAPH_EDGE', 'Each graph edge must be an object.', { index });
    const source = requireId(edge.source, 'Graph edge source', index);
    const target = requireId(edge.target, 'Graph edge target', index);
    if (!nodeIds.has(source) || !nodeIds.has(target)) fail('GRAPH_UNKNOWN_NODE', 'Graph edge references an unknown node.', { index, source, target });
    const explicitId = edge.id == null ? null : requireId(edge.id, 'Graph edge', index);
    if (explicitId != null && explicitIds.has(explicitId)) fail('GRAPH_DUPLICATE_EDGE', `Duplicate graph edge id: ${explicitId}`, { id: explicitId, index });
    if (explicitId != null) explicitIds.add(explicitId);
    if (source === target && ['dag', 'tree', 'flow'].includes(kind)) fail('GRAPH_SELF_LOOP', `${kind} graph cannot contain a self-loop.`, { id: explicitId, source });
    const item = { ...edge, id: explicitId, source, target };
    if (kind === 'flow') {
      const weight = Number(edge.weight ?? edge.value);
      if (!finite(weight) || weight <= 0) fail('GRAPH_FLOW_WEIGHT', 'Flow edges require a finite weight > 0.', { id: explicitId, value: edge.weight ?? edge.value });
      item.weight = weight;
    }
    if (kind === 'state_machine') {
      if (typeof edge.event !== 'string' || !edge.event.trim()) fail('GRAPH_STATE_EVENT', 'State-machine transitions require a non-empty event.', { id: explicitId });
      item.event = edge.event;
    }
    return item;
  }).sort((a, b) => a.source.localeCompare(b.source)
    || a.target.localeCompare(b.target)
    || String(a.event ?? '').localeCompare(String(b.event ?? ''))
    || Number(a.weight ?? a.value ?? 0) - Number(b.weight ?? b.value ?? 0)
    || String(a.id ?? '').localeCompare(String(b.id ?? '')));

  let auto = 0;
  return normalized.map((edge) => Object.freeze({ ...edge, id: edge.id ?? `edge:auto:${auto++}:${edge.source}->${edge.target}` }));
}

function adjacency(nodes, edges) {
  const out = new Map(nodes.map((node) => [node.id, []]));
  const incoming = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    out.get(edge.source).push(edge);
    incoming.get(edge.target).push(edge);
  }
  for (const list of out.values()) list.sort((a, b) => a.target.localeCompare(b.target) || a.id.localeCompare(b.id));
  for (const list of incoming.values()) list.sort((a, b) => a.source.localeCompare(b.source) || a.id.localeCompare(b.id));
  return { out, incoming };
}

function topological(nodes, edges) {
  const { out, incoming } = adjacency(nodes, edges);
  const indegree = new Map(nodes.map((node) => [node.id, incoming.get(node.id).length]));
  const ready = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id).sort();
  const order = [];
  while (ready.length) {
    const id = ready.shift();
    order.push(id);
    for (const edge of out.get(id)) {
      const next = edge.target;
      indegree.set(next, indegree.get(next) - 1);
      if (indegree.get(next) === 0) {
        ready.push(next);
        ready.sort();
      }
    }
  }
  if (order.length !== nodes.length) {
    const cycleNodes = nodes.map((node) => node.id).filter((id) => indegree.get(id) > 0).sort();
    fail('GRAPH_CYCLE', 'Acyclic graph contains a directed cycle.', { cycleNodes });
  }
  return { order, out, incoming };
}

function validateTree(nodes, edges) {
  if (edges.length !== nodes.length - 1) fail('GRAPH_TREE_EDGE_COUNT', 'Directed tree requires exactly nodeCount - 1 edges.', { nodes: nodes.length, edges: edges.length });
  const topo = topological(nodes, edges);
  const roots = nodes.filter((node) => topo.incoming.get(node.id).length === 0).map((node) => node.id);
  if (roots.length !== 1) fail('GRAPH_TREE_ROOT', 'Directed tree requires exactly one root.', { roots });
  const invalidParents = nodes.filter((node) => node.id !== roots[0] && topo.incoming.get(node.id).length !== 1).map((node) => node.id);
  if (invalidParents.length) fail('GRAPH_TREE_PARENT', 'Every non-root tree node requires exactly one parent.', { nodes: invalidParents });
  const reached = new Set([roots[0]]); const queue = [roots[0]];
  while (queue.length) {
    const id = queue.shift();
    for (const edge of topo.out.get(id)) if (!reached.has(edge.target)) { reached.add(edge.target); queue.push(edge.target); }
  }
  if (reached.size !== nodes.length) fail('GRAPH_TREE_DISCONNECTED', 'Tree must be connected from its root.', { root: roots[0] });
  return { ...topo, root: roots[0] };
}

function validateStateMachine(nodes, edges, options) {
  const seen = new Map();
  for (const edge of edges) {
    const key = `${edge.source}\u0000${edge.event}`;
    if (seen.has(key)) fail('GRAPH_STATE_NONDETERMINISTIC', 'State machine has multiple transitions for the same source/event.', { source: edge.source, event: edge.event, edgeIds: [seen.get(key), edge.id] });
    seen.set(key, edge.id);
  }
  const declared = nodes.filter((node) => node.initial === true).map((node) => node.id);
  const initialId = options.initialId ?? (declared.length === 1 ? declared[0] : null);
  if (options.requireInitial !== false) {
    if (options.initialId != null && !nodes.some((node) => node.id === options.initialId)) fail('GRAPH_STATE_INITIAL', 'Declared initial state does not exist.', { initialId: options.initialId });
    if (options.initialId == null && declared.length !== 1) fail('GRAPH_STATE_INITIAL', 'State machine requires exactly one initial state.', { declared });
  }
  return { initialId };
}

export function validateGraph(kind, input = {}, options = {}) {
  if (!GRAPH_KINDS.includes(kind)) fail('GRAPH_KIND', `Unsupported graph kind: ${kind}`, { kind });
  const nodes = normalizeNodes(input.nodes);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = normalizeEdges(input.edges ?? [], nodeIds, kind);
  let semantic = {};
  if (kind === 'dag') semantic = topological(nodes, edges);
  else if (kind === 'tree') semantic = validateTree(nodes, edges);
  else if (kind === 'flow') semantic = options.acyclic === false ? adjacency(nodes, edges) : topological(nodes, edges);
  else if (kind === 'state_machine') semantic = { ...adjacency(nodes, edges), ...validateStateMachine(nodes, edges, options) };
  else semantic = adjacency(nodes, edges);

  const result = {
    schema_version: 1,
    kind,
    nodes,
    edges,
    metrics: Object.freeze({ nodeCount: nodes.length, edgeCount: edges.length }),
    topologicalOrder: semantic.order ? Object.freeze([...semantic.order]) : null,
    root: semantic.root ?? null,
    initialId: semantic.initialId ?? null,
  };
  result.fingerprint = fingerprint({ kind, nodes, edges, topologicalOrder: result.topologicalOrder, root: result.root, initialId: result.initialId });
  return Object.freeze(result);
}
