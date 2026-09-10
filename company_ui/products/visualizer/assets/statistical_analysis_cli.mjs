import fs from 'node:fs';
import { executeRecipeSemantics } from './analysis_semantics.mjs';

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));

function compactDataset(result, recipeId) {
  if (recipeId === 'xbar-r-process-review') return {
    fields: clone(result.dataset.fields || []),
    rows: clone(result.dataset.rows || []),
  };
  if (recipeId === 'process-capability') {
    const stats = result.primary?.stats || {};
    return {
      fields: clone(result.dataset.fields || []),
      // Capability renderers consume the governed histogram/box summaries;
      // one summary row keeps the browser payload bounded for large sources.
      rows: stats.mean === undefined ? [] : [[stats.mean, stats.lsl, stats.usl, stats.target, stats.cpk]],
    };
  }
  if (recipeId === 'doe-response-review') {
    const effects = result.primary?.effects || [];
    const interaction = result.primary?.interaction || {};
    const rows = [];
    for (const effect of effects) {
      for (const level of effect.levels || []) rows.push([effect.factor === 'factor_a' ? level.level : null, effect.factor === 'factor_b' ? level.level : null, level.mean]);
    }
    for (const row of interaction.cells || []) for (const cell of row || []) rows.push([cell.a, cell.b, cell.mean]);
    return { fields: clone(result.dataset.fields || []), rows };
  }
  return { fields: [], rows: [] };
}

function compactResult(result, request) {
  const recipeId = String(request.recipe_id || '');
  const primary = result.primary || {};
  let derivedStatistics = {};
  if (recipeId === 'xbar-r-process-review') derivedStatistics = { kind: primary.kind, stats: clone(primary.stats || {}), subgroups: clone(primary.subgroups || []), subgroup_labels: clone(primary.subgroup_labels || []) };
  if (recipeId === 'process-capability') derivedStatistics = { kind: primary.kind, stats: clone(primary.stats || {}) };
  if (recipeId === 'doe-response-review') derivedStatistics = { kind: primary.kind, effects: clone(primary.effects || []), interaction: clone(primary.interaction || {}) };
  const compact = compactDataset(result, recipeId);
  return {
    ok: result.ok === true,
    analysis_type: recipeId,
    statistical_semantic_version: result.version,
    derived_mapping: clone(result.mapping || {}),
    // Raw measurements never cross the governed boundary.  Only the
    // renderer-ready derived population is retained here.
    analysis_rows: clone(compact.rows || []),
    summary: clone(result.summary || {}),
    derived_statistics: derivedStatistics,
    renderer_ready: { dataset: compact },
    warnings: clone(result.warnings || []),
    errors: clone(result.errors || []),
    provenance_text: result.provenance || '',
  };
}

const requests = Array.isArray(input.analyses) ? input.analyses : [input];
const dataset = input.dataset || {};
const output = requests.map(request => compactResult(
  executeRecipeSemantics(request.recipe_id, dataset, request.mapping || {}, request.options || {}),
  request,
));
process.stdout.write(JSON.stringify(output));
