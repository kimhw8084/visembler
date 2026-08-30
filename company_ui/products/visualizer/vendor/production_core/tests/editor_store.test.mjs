import assert from 'node:assert/strict';
import { EditorStore, RevisionConflictError, parseCanonical, serializeCanonical } from '../core/editor_store.mjs';

const initial = {
  schema_version: 1,
  items: [
    { id: 'c1', type: 'metric', title: 'A', order: 0, weight: 1, locked: false, z: 1 },
    { id: 'c2', type: 'chart', title: 'B', order: 1, weight: 1.5, locked: false, z: 2, data: [['x', 1]], brush: [0, 0] },
  ],
  groups: {},
  mode: 'smart',
  layoutPreset: 'editorial',
  crossFilter: null,
  nextId: 3,
};

const store = new EditorStore(initial);
const start = store.serialize();
const accepted = [];

for (let i = 0; i < 100; i += 1) {
  const id = i % 2 ? 'c1' : 'c2';
  const cmd = store.command([
    { op: 'item.patch', id, patch: { z: (store.model.items.find((x) => x.id === id).z || 0) + 1 } },
    { op: 'model.patch', patch: { layoutPreset: i % 3 === 0 ? 'executive' : i % 3 === 1 ? 'technical' : 'editorial' } },
  ], `mixed-${i}`);
  accepted.push(store.commit(cmd));
}

const after100 = store.serialize();
assert.notEqual(after100, start);
assert.equal(store.revision, 101);
assert.equal(accepted.every((x) => Array.isArray(x.inverse.ops) && Array.isArray(x.redo.ops)), true);

const stale = store.command([{ op: 'model.patch', patch: { layoutPreset: 'editorial' } }], 'stale-test');
store.commit(stale);
assert.throws(() => store.commit({ ...stale, id: `${stale.id}-again` }), RevisionConflictError);
store.undo(store.revision);
assert.equal(store.serialize(), after100);

for (let i = 0; i < 100; i += 1) store.undo(store.revision);
assert.equal(store.serialize(), start, '100-command undo must restore byte-identical canonical state');
for (let i = 0; i < 100; i += 1) store.redo(store.revision);
assert.equal(store.serialize(), after100, '100-command redo must restore byte-identical canonical state');

const roundTrip = serializeCanonical(parseCanonical(store.serialize()));
assert.equal(roundTrip, store.serialize(), 'save-load-save must be deterministic');

const beforeAtomic = store.serialize();
assert.throws(() => store.commit(store.command([
  { op: 'item.patch', id: 'c1', patch: { title: 'would-change' } },
  { op: 'item.patch', id: 'missing', patch: { title: 'boom' } },
], 'atomic-failure')));
assert.equal(store.serialize(), beforeAtomic, 'failed command must be atomic');

assert.throws(() => { store.model.items[0].title = 'illegal direct mutation'; }, TypeError);
assert.equal(store.model.items[0].title, 'A');

// Universal undo/redo must preserve group membership even when a caller uses
// the primitive item.remove/group.delete operations directly.
const grouped = new EditorStore({
  schema_version: 1,
  items: [
    { id: 'c1', type: 'metric', title: 'Grouped A', order: 0, groupId: 'g1' },
    { id: 'c2', type: 'text', title: 'Grouped B', order: 1, groupId: 'g1' },
  ],
  groups: { g1: { id: 'g1', items: ['c1', 'c2'] } },
  mode: 'smart', layoutPreset: 'editorial', crossFilter: null, nextId: 3,
});
const groupedStart = grouped.serialize();
grouped.commit(grouped.command([{ op: 'item.remove', id: 'c1' }], 'remove grouped item'));
assert.deepEqual(grouped.model.groups.g1.items, ['c2']);
grouped.undo(grouped.revision);
assert.equal(grouped.serialize(), groupedStart, 'undo item.remove must restore exact group membership');
grouped.redo(grouped.revision);
assert.deepEqual(grouped.model.groups.g1.items, ['c2']);
grouped.undo(grouped.revision);
assert.equal(grouped.serialize(), groupedStart);

grouped.commit(grouped.command([{ op: 'group.delete', id: 'g1' }], 'delete group primitive'));
assert.equal(grouped.model.groups.g1, undefined);
assert.equal(grouped.model.items.every((entry) => entry.groupId == null), true);
grouped.undo(grouped.revision);
assert.equal(grouped.serialize(), groupedStart, 'undo group.delete must restore exact bidirectional membership');

assert.throws(() => new EditorStore({
  schema_version: 1,
  items: [{ id: 'c1', type: 'metric', title: 'Broken', order: 0, groupId: 'ghost' }],
  groups: {}, mode: 'smart', layoutPreset: 'editorial', crossFilter: null, nextId: 2,
}), /missing group/);

console.log(JSON.stringify({ pass: true, commands: 100, revision: store.revision, deterministic: true, atomic: true, frozenModel: true, groupedUndoExact: true }, null, 2));
