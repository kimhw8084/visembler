// Pure diagram-authoring helpers.
// Keep node/edge edits valid after every individual inspector action.

const clean = value => String(value ?? '').trim();

export function parseDiagramNodes(text) {
  const seen = new Set();
  const nodes = [];
  for (const raw of String(text ?? '').split(/\r?\n/)) {
    const node = clean(raw);
    if (!node || seen.has(node)) continue;
    seen.add(node);
    nodes.push(node);
  }
  return nodes;
}

export function parseDiagramEdges(text) {
  const seen = new Set();
  const edges = [];
  for (const raw of String(text ?? '').split(/\r?\n/)) {
    const parts = raw.split(/\s*->\s*/).map(clean);
    if (parts.length !== 2 || !parts[0] || !parts[1] || parts[0] === parts[1]) continue;
    const key = `${parts[0]}\u0000${parts[1]}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push(parts);
  }
  return edges;
}

export function reconcileDiagramEdges(previousNodes, nextNodes, edges) {
  const before = Array.isArray(previousNodes) ? previousNodes.map(clean).filter(Boolean) : [];
  const after = Array.isArray(nextNodes) ? nextNodes.map(clean).filter(Boolean) : [];
  const beforeSet = new Set(before);
  const afterSet = new Set(after);

  const pureReorder =
    before.length === after.length
    && beforeSet.size === afterSet.size
    && [...beforeSet].every(node => afterSet.has(node));

  const rename = new Map();
  if (!pureReorder) {
    const max = Math.min(before.length, after.length);
    for (let index = 0; index < max; index += 1) {
      const oldNode = before[index];
      const newNode = after[index];
      if (
        oldNode
        && newNode
        && oldNode !== newNode
        && !afterSet.has(oldNode)
        && !beforeSet.has(newNode)
      ) {
        rename.set(oldNode, newNode);
      }
    }
  }

  const seen = new Set();
  const result = [];
  for (const edge of Array.isArray(edges) ? edges : []) {
    if (!Array.isArray(edge) || edge.length !== 2) continue;
    const source = rename.get(clean(edge[0])) || clean(edge[0]);
    const target = rename.get(clean(edge[1])) || clean(edge[1]);
    if (!source || !target || source === target) continue;
    if (!afterSet.has(source) || !afterSet.has(target)) continue;
    const key = `${source}\u0000${target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push([source, target]);
  }
  return result;
}

export function validateDiagramEdges(nodes, edges) {
  const allowed = new Set((Array.isArray(nodes) ? nodes : []).map(clean).filter(Boolean));
  const unknown = [];
  for (const edge of Array.isArray(edges) ? edges : []) {
    if (!Array.isArray(edge) || edge.length !== 2) continue;
    for (const endpoint of edge) {
      const node = clean(endpoint);
      if (node && !allowed.has(node) && !unknown.includes(node)) unknown.push(node);
    }
  }
  return {valid: unknown.length === 0, unknown};
}
