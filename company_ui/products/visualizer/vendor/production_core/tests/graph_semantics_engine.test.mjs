import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { GraphContractError, validateGraph } from '../core/graph_semantics_engine.mjs';

const dag = validateGraph('dag', {
  nodes: [{ id: 'c' }, { id: 'a' }, { id: 'b' }, { id: 'd' }],
  edges: [{ source: 'a', target: 'b' }, { source: 'a', target: 'c' }, { source: 'b', target: 'd' }, { source: 'c', target: 'd' }],
});
assert.deepEqual(dag.topologicalOrder, ['a', 'b', 'c', 'd']);
assert.equal(dag.fingerprint, validateGraph('dag', { nodes: [{ id: 'd' }, { id: 'b' }, { id: 'a' }, { id: 'c' }], edges: [{ source: 'c', target: 'd' }, { source: 'a', target: 'c' }, { source: 'b', target: 'd' }, { source: 'a', target: 'b' }] }).fingerprint);
assert.throws(() => validateGraph('dag', { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b' }, { source: 'b', target: 'a' }] }), (e) => e instanceof GraphContractError && e.code === 'GRAPH_CYCLE');

const tree = validateGraph('tree', { nodes: [{ id: 'root' }, { id: 'l' }, { id: 'r' }], edges: [{ source: 'root', target: 'l' }, { source: 'root', target: 'r' }] });
assert.equal(tree.root, 'root');
assert.throws(() => validateGraph('tree', { nodes: [{ id: 'a' }, { id: 'b' }, { id: 'c' }], edges: [{ source: 'a', target: 'c' }, { source: 'b', target: 'c' }] }), GraphContractError);

const flow = validateGraph('flow', { nodes: [{ id: 'source' }, { id: 'sink' }], edges: [{ source: 'source', target: 'sink', value: 4.5 }] });
assert.equal(flow.edges[0].weight, 4.5);
assert.throws(() => validateGraph('flow', { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', value: 0 }] }), (e) => e.code === 'GRAPH_FLOW_WEIGHT');

const sm = validateGraph('state_machine', {
  nodes: [{ id: 'idle', initial: true }, { id: 'run' }],
  edges: [{ source: 'idle', target: 'run', event: 'start' }, { source: 'run', target: 'idle', event: 'stop' }],
});
assert.equal(sm.initialId, 'idle');
assert.throws(() => validateGraph('state_machine', {
  nodes: [{ id: 'idle', initial: true }, { id: 'a' }, { id: 'b' }],
  edges: [{ source: 'idle', target: 'a', event: 'go' }, { source: 'idle', target: 'b', event: 'go' }],
}), (e) => e.code === 'GRAPH_STATE_NONDETERMINISTIC');

assert.throws(() => validateGraph('network', { nodes: [{ id: 'a' }, { id: 'a' }], edges: [] }), (e) => e.code === 'GRAPH_DUPLICATE_NODE');
assert.throws(() => validateGraph('network', { nodes: [{ id: 'a' }], edges: [{ source: 'a', target: 'missing' }] }), (e) => e.code === 'GRAPH_UNKNOWN_NODE');

const nodes = Array.from({ length: 100 }, (_, i) => ({ id: `n${String(i).padStart(3, '0')}` }));
const edges = [];
for (let i = 0; i < 99; i += 1) edges.push({ source: nodes[i].id, target: nodes[i + 1].id });
for (let i = 0; i < 94; i += 5) edges.push({ source: nodes[i].id, target: nodes[i + 5].id });
const t0 = performance.now();
let last;
for (let i = 0; i < 1000; i += 1) last = validateGraph('dag', { nodes, edges });
const elapsed = performance.now() - t0;
assert.equal(last.metrics.nodeCount, 100);
assert.equal(last.topologicalOrder.length, 100);
assert.ok(elapsed < 3000, `100-node semantic validation budget exceeded: ${elapsed.toFixed(1)}ms`);

console.log(JSON.stringify({ pass: true, kinds: 5, deterministic: true, invalidGraphBlocking: true, hundredNodeIterations: 1000, elapsedMs: +elapsed.toFixed(3), fingerprint: last.fingerprint }, null, 2));
