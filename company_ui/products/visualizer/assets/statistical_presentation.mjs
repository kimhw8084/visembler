const STATISTICAL_RECIPES = new Set(['xbar-r-process-review','process-capability','doe-response-review']);

export function statisticalAnalysisError(entry = {}) {
  const explicit = String(entry.analysis_error || '').trim();
  if (explicit) return explicit;
  const semantic = entry.analysis_semantics;
  if (semantic?.ok === false) return String(semantic.errors?.[0]?.message || 'The statistical analysis could not be validated.');
  const authoritative = entry.authoritative_analysis;
  const recipe = String(entry.analysis_recipe?.id || '');
  if (authoritative && (STATISTICAL_RECIPES.has(recipe) || authoritative.analysis_type || authoritative.analysis_id || authoritative.population) && (authoritative.ok !== true || authoritative.population?.complete !== true)) {
    return String(authoritative.errors?.[0]?.message || 'The statistical analysis is invalid or incomplete.');
  }
  if (entry.statistical_result?.ok === false) return String(entry.statistical_result.errors?.[0]?.message || 'The statistical analysis could not be validated.');
  return '';
}

export function hasInvalidStatisticalAnalysis(entry = {}) {
  return Boolean(statisticalAnalysisError(entry));
}
