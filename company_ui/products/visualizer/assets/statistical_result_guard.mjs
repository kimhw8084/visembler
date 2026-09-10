// Pure transport guard for asynchronous dataset-backed statistical results.
// Numerical meaning stays in analysis_semantics/statistical_analysis; this
// module only decides whether a reply still belongs to the active revision.
export function acceptsStatisticalResult({expectedRevision = 0, resultRevision = 0, activeRequestId = null, resultRequestId = null} = {}) {
  const expected = Number(expectedRevision || 0);
  const actual = Number(resultRevision || 0);
  if (expected > 0 && actual > 0 && expected !== actual) return false;
  if (activeRequestId && resultRequestId && String(activeRequestId) !== String(resultRequestId)) return false;
  return true;
}
