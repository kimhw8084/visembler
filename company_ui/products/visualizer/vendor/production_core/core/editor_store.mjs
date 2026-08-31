const MODEL_KEYS = ['schema_version', 'authoring_schema', 'datasets', 'items', 'groups', 'mode', 'layoutPreset', 'crossFilter', 'canvas', 'nextId'];
const ALLOWED_MODES = new Set(['smart', 'guided', 'free']);
const DEFAULT_CANVAS = Object.freeze({ width: 1600, height: 900 });

export class RevisionConflictError extends Error {
  constructor(expected, received) {
    super(`Stale base_revision: expected ${expected}, received ${received}`);
    this.name = 'RevisionConflictError';
    this.expected = expected;
    this.received = received;
  }
}

export class CommandValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CommandValidationError';
  }
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function clone(value) {
  return value == null ? value : structuredClone(value);
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const child of Object.values(value)) deepFreeze(child);
  return value;
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (!isPlainObject(value)) return value;
  return Object.keys(value).sort().reduce((out, key) => {
    out[key] = stable(value[key]);
    return out;
  }, {});
}

export function stableStringify(value, space = 0) {
  return JSON.stringify(stable(value), null, space);
}

export function canonicalModel(input = {}) {
  const items = Array.isArray(input.items) ? clone(input.items) : [];
  const groups = isPlainObject(input.groups) ? clone(input.groups) : {};
  const model = {
    schema_version: Number.isInteger(input.schema_version) ? input.schema_version : 1,
    authoring_schema: input.authoring_schema === 'authoring-p0-v1' ? input.authoring_schema : 'authoring-p0-v1',
    datasets: Array.isArray(input.datasets) ? clone(input.datasets) : [],
    items,
    groups,
    mode: ALLOWED_MODES.has(input.mode) ? input.mode : 'smart',
    layoutPreset: typeof input.layoutPreset === 'string' ? input.layoutPreset : 'editorial',
    crossFilter: input.crossFilter ?? null,
    canvas: canonicalCanvas(input.canvas),
    nextId: Number.isInteger(input.nextId) ? input.nextId : inferNextId(items),
  };
  validateModel(model);
  return model;
}

function canonicalCanvas(value) {
  const source = isPlainObject(value) ? value : {};
  const width = Number(source.width ?? DEFAULT_CANVAS.width);
  const height = Number(source.height ?? DEFAULT_CANVAS.height);
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 640 || width > 3840 || height < 360 || height > 4800) {
    throw new CommandValidationError('Canvas must be 640-3840px wide and 360-4800px high.');
  }
  return { width, height };
}

function inferNextId(items) {
  const ids = items
    .map((item) => /^c(\d+)$/.exec(String(item.id || '')))
    .filter(Boolean)
    .map((m) => Number(m[1]));
  return Math.max(20, ids.length ? Math.max(...ids) + 1 : 20);
}

export function validateModel(model) {
  if (!isPlainObject(model)) throw new CommandValidationError('Model must be an object.');
  for (const key of MODEL_KEYS) {
    if (!(key in model)) throw new CommandValidationError(`Missing model field: ${key}`);
  }
  if (!Array.isArray(model.items)) throw new CommandValidationError('items must be an array.');
  if (!Array.isArray(model.datasets)) throw new CommandValidationError('datasets must be an array.');
  const datasetIds = new Set();
  for (const dataset of model.datasets) {
    if (!isPlainObject(dataset) || typeof dataset.id !== 'string' || !dataset.id || !Array.isArray(dataset.fields) || !Array.isArray(dataset.rows)) throw new CommandValidationError('Every dataset requires id, fields, and rows.');
    if (datasetIds.has(dataset.id)) throw new CommandValidationError(`Duplicate dataset id: ${dataset.id}`);
    datasetIds.add(dataset.id);
  }
  if (!isPlainObject(model.groups)) throw new CommandValidationError('groups must be an object.');
  if (!ALLOWED_MODES.has(model.mode)) throw new CommandValidationError(`Unsupported mode: ${model.mode}`);
  canonicalCanvas(model.canvas);
  if (!Number.isInteger(model.nextId) || model.nextId < 1) throw new CommandValidationError('nextId must be a positive integer.');

  const ids = new Set();
  for (const entry of model.items) {
    if (!isPlainObject(entry)) throw new CommandValidationError('Every item must be an object.');
    if (typeof entry.id !== 'string' || !entry.id) throw new CommandValidationError('Every item requires a semantic id.');
    if (ids.has(entry.id)) throw new CommandValidationError(`Duplicate item id: ${entry.id}`);
    ids.add(entry.id);
    if (typeof entry.type !== 'string' || !entry.type) throw new CommandValidationError(`Item ${entry.id} requires a type.`);
    if (!Number.isFinite(entry.order)) throw new CommandValidationError(`Item ${entry.id} requires numeric order.`);
    if (entry.dataset_id != null && (!datasetIds.has(entry.dataset_id) || !isPlainObject(entry.mapping))) throw new CommandValidationError(`Item ${entry.id} has an invalid dataset binding.`);
    for (const key of ['x', 'y', 'w', 'h', 'weight', 'z']) {
      if (entry[key] != null && !Number.isFinite(entry[key])) throw new CommandValidationError(`Item ${entry.id}.${key} must be numeric when present.`);
    }
  }

  const itemById = new Map(model.items.map((entry) => [entry.id, entry]));
  for (const [gid, group] of Object.entries(model.groups)) {
    if (!isPlainObject(group) || !Array.isArray(group.items)) throw new CommandValidationError(`Group ${gid} is malformed.`);
    const memberIds = new Set();
    for (const id of group.items) {
      if (!ids.has(id)) throw new CommandValidationError(`Group ${gid} references missing item ${id}.`);
      if (memberIds.has(id)) throw new CommandValidationError(`Group ${gid} contains duplicate member ${id}.`);
      memberIds.add(id);
      if (itemById.get(id).groupId !== gid) throw new CommandValidationError(`Group ${gid} membership disagrees with item ${id}.groupId.`);
    }
  }
  for (const entry of model.items) {
    if (entry.groupId == null) continue;
    if (typeof entry.groupId !== 'string' || !entry.groupId) throw new CommandValidationError(`Item ${entry.id}.groupId must be null or a non-empty string.`);
    const group = model.groups[entry.groupId];
    if (!group) throw new CommandValidationError(`Item ${entry.id} references missing group ${entry.groupId}.`);
    if (!group.items.includes(entry.id)) throw new CommandValidationError(`Item ${entry.id} is not listed by group ${entry.groupId}.`);
  }
  return true;
}

export function serializeCanonical(model, space = 0) {
  return stableStringify(canonicalModel(model), space);
}

export function parseCanonical(serialized) {
  const parsed = typeof serialized === 'string' ? JSON.parse(serialized) : clone(serialized);
  const source = parsed?.model && isPlainObject(parsed.model) ? parsed.model : parsed;
  return canonicalModel(source);
}

function ensureCommand(command, revision) {
  if (!isPlainObject(command)) throw new CommandValidationError('EditorCommand must be an object.');
  if (command.type !== 'editor.transaction') throw new CommandValidationError(`Unsupported EditorCommand type: ${command.type}`);
  if (command.base_revision !== revision) throw new RevisionConflictError(revision, command.base_revision);
  if (!isPlainObject(command.payload) || !Array.isArray(command.payload.ops) || !command.payload.ops.length) {
    throw new CommandValidationError('EditorCommand payload.ops must be a non-empty array.');
  }
  if (typeof command.id !== 'string' || !command.id) throw new CommandValidationError('EditorCommand requires an id.');
}

function requireItem(model, id) {
  const index = model.items.findIndex((item) => item.id === id);
  if (index < 0) throw new CommandValidationError(`Unknown item id: ${id}`);
  return { item: model.items[index], index };
}

function applyOp(model, op) {
  if (!isPlainObject(op) || typeof op.op !== 'string') throw new CommandValidationError('Every transaction operation requires op.');

  if (op.op === 'item.add') {
    if (!isPlainObject(op.item)) throw new CommandValidationError('item.add requires item.');
    if (model.items.some((item) => item.id === op.item.id)) throw new CommandValidationError(`Duplicate item id: ${op.item.id}`);
    const index = Math.max(0, Math.min(Number.isInteger(op.index) ? op.index : model.items.length, model.items.length));
    model.items.splice(index, 0, clone(op.item));
    return [{ op: 'item.remove', id: op.item.id }];
  }

  if (op.op === 'item.remove') {
    const { item, index } = requireItem(model, op.id);
    const memberships = Object.entries(model.groups)
      .filter(([, group]) => group.items.includes(op.id))
      .map(([id, group]) => ({ id, value: clone(group) }));
    model.items.splice(index, 1);
    for (const group of Object.values(model.groups)) group.items = group.items.filter((id) => id !== op.id);
    return [
      { op: 'item.add', item: clone(item), index },
      ...memberships.map(({ id, value }) => ({ op: 'group.set', id, value })),
    ];
  }

  if (op.op === 'item.patch') {
    const { item } = requireItem(model, op.id);
    if (!isPlainObject(op.patch)) throw new CommandValidationError('item.patch requires patch object.');
    const before = {};
    for (const [key, value] of Object.entries(op.patch)) {
      before[key] = clone(item[key]);
      item[key] = clone(value);
    }
    return [{ op: 'item.patch', id: op.id, patch: before }];
  }

  if (op.op === 'group.set') {
    if (typeof op.id !== 'string' || !op.id || !isPlainObject(op.value)) throw new CommandValidationError('group.set requires id/value.');
    const existed = Object.prototype.hasOwnProperty.call(model.groups, op.id);
    const before = existed ? clone(model.groups[op.id]) : null;
    model.groups[op.id] = clone(op.value);
    return existed ? [{ op: 'group.set', id: op.id, value: before }] : [{ op: 'group.delete', id: op.id }];
  }

  if (op.op === 'group.delete') {
    if (typeof op.id !== 'string' || !op.id) throw new CommandValidationError('group.delete requires id.');
    if (!Object.prototype.hasOwnProperty.call(model.groups, op.id)) return [];
    const before = clone(model.groups[op.id]);
    const memberPatches = [];
    for (const id of before.items) {
      const found = model.items.find((entry) => entry.id === id);
      if (found?.groupId === op.id) {
        memberPatches.push({ op: 'item.patch', id, patch: { groupId: op.id } });
        found.groupId = null;
      }
    }
    delete model.groups[op.id];
    return [{ op: 'group.set', id: op.id, value: before }, ...memberPatches];
  }

  if (op.op === 'model.patch') {
    if (!isPlainObject(op.patch)) throw new CommandValidationError('model.patch requires patch object.');
    const allowed = new Set(['mode', 'layoutPreset', 'crossFilter', 'canvas', 'nextId', 'datasets', 'authoring_schema']);
    const before = {};
    for (const [key, value] of Object.entries(op.patch)) {
      if (!allowed.has(key)) throw new CommandValidationError(`model.patch cannot modify ${key}`);
      before[key] = clone(model[key]);
      model[key] = clone(value);
    }
    return [{ op: 'model.patch', patch: before }];
  }

  if (op.op === 'model.replace') {
    const before = canonicalModel(model);
    const next = canonicalModel(op.value);
    for (const key of MODEL_KEYS) model[key] = clone(next[key]);
    return [{ op: 'model.replace', value: before }];
  }

  throw new CommandValidationError(`Unsupported transaction operation: ${op.op}`);
}

function applyOps(current, ops) {
  const next = canonicalModel(current);
  const inverse = [];
  for (const op of ops) {
    const inv = applyOp(next, op);
    if (inv.length) inverse.unshift(...inv);
  }
  validateModel(next);
  return { next, inverse };
}

export function makeEditorCommand(baseRevision, ops, label = 'Edit', id = null) {
  return {
    id: id || `cmd-${baseRevision + 1}-${Math.random().toString(36).slice(2, 10)}`,
    type: 'editor.transaction',
    base_revision: baseRevision,
    payload: { ops: clone(ops) },
    meta: { label, created_at: new Date().toISOString() },
  };
}

export class EditorStore {
  constructor(initialModel, { revision = 1, historyLimit = 120 } = {}) {
    this._model = deepFreeze(canonicalModel(initialModel));
    this._revision = revision;
    this._history = [];
    this._future = [];
    this._historyLimit = historyLimit;
    this._listeners = new Set();
  }

  get model() { return this._model; }
  get revision() { return this._revision; }
  get canUndo() { return this._history.length > 0; }
  get canRedo() { return this._future.length > 0; }

  subscribe(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  _emit(event) {
    for (const listener of this._listeners) listener(event);
  }

  command(ops, label = 'Edit') {
    return makeEditorCommand(this._revision, ops, label);
  }

  commit(command) {
    ensureCommand(command, this._revision);
    const beforeCanonical = serializeCanonical(this._model);
    const { next, inverse } = applyOps(this._model, command.payload.ops);
    const afterCanonical = serializeCanonical(next);
    const accepted = {
      ...clone(command),
      inverse: { ops: clone(inverse) },
      redo: { ops: clone(command.payload.ops) },
      accepted_revision: this._revision + 1,
      canonical_before: beforeCanonical,
      canonical_after: afterCanonical,
    };
    this._history.push(accepted);
    if (this._history.length > this._historyLimit) this._history.shift();
    this._future = [];
    this._model = deepFreeze(next);
    this._revision += 1;
    this._emit({ kind: 'commit', command: accepted, revision: this._revision, model: this._model });
    return accepted;
  }

  undo(baseRevision = this._revision) {
    if (baseRevision !== this._revision) throw new RevisionConflictError(this._revision, baseRevision);
    const entry = this._history.pop();
    if (!entry) return null;
    const { next } = applyOps(this._model, entry.inverse.ops);
    this._model = deepFreeze(next);
    this._revision += 1;
    this._future.push(entry);
    this._emit({ kind: 'undo', command: entry, revision: this._revision, model: this._model });
    return entry;
  }

  redo(baseRevision = this._revision) {
    if (baseRevision !== this._revision) throw new RevisionConflictError(this._revision, baseRevision);
    const entry = this._future.pop();
    if (!entry) return null;
    const { next } = applyOps(this._model, entry.redo.ops);
    this._model = deepFreeze(next);
    this._revision += 1;
    this._history.push(entry);
    this._emit({ kind: 'redo', command: entry, revision: this._revision, model: this._model });
    return entry;
  }

  replaceModel(nextModel, label = 'Load model') {
    return this.commit(this.command([{ op: 'model.replace', value: canonicalModel(nextModel) }], label));
  }

  serialize(space = 0) {
    return serializeCanonical(this._model, space);
  }

  exportEnvelope(space = 0) {
    return stableStringify({
      schema_version: 1,
      revision: this._revision,
      model: canonicalModel(this._model),
    }, space);
  }
}
