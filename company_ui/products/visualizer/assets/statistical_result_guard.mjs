// Pure transport guard for asynchronous dataset-backed statistical results.
// Numerical meaning stays in analysis_semantics/statistical_analysis; this
// module only decides whether a reply still belongs to the active report,
// dataset/session, revision, and request generation.
export function resultKey(reportId = '', datasetId = '', sessionId = '') {
  return JSON.stringify([String(reportId || ''), String(datasetId || ''), String(sessionId || '')]);
}

export function nextRequestId(registry, key) {
  if (!registry || !key) return 1;
  const previous = registry[key];
  const current = typeof previous === 'object' ? Number(previous.current || 0) : Number(previous || 0);
  const next = Number.isFinite(current) && current >= 0 ? Math.floor(current) + 1 : 1;
  registry[key] = typeof previous === 'object' ? {...previous, current: next} : next;
  return next;
}

function sameIdentity(expected, actual) {
  if (expected == null || expected === '') return true;
  return actual != null && actual !== '' && String(expected) === String(actual);
}

function sameList(expected, actual) {
  if (!Array.isArray(expected)) return true;
  if (!Array.isArray(actual)) return false;
  return JSON.stringify(expected) === JSON.stringify(actual);
}

export function acceptsStatisticalResult({
  expectedReportId = null,
  resultReportId = null,
  expectedDatasetId = null,
  resultDatasetId = null,
  expectedSessionId = null,
  resultSessionId = null,
  expectedFilters = null,
  resultFilters = null,
  expectedRevision = 0,
  resultRevision = 0,
  activeRequestId = null,
  resultRequestId = null,
} = {}) {
  if (!sameIdentity(expectedReportId, resultReportId)) return false;
  if (!sameIdentity(expectedDatasetId, resultDatasetId)) return false;
  if (!sameIdentity(expectedSessionId, resultSessionId)) return false;
  if (!sameList(expectedFilters, resultFilters)) return false;
  const expected = Number(expectedRevision || 0);
  const actual = Number(resultRevision || 0);
  if (expected > 0 && actual !== expected) return false;
  if (activeRequestId != null && String(activeRequestId) !== '') {
    if (resultRequestId == null || String(resultRequestId) === '' || String(activeRequestId) !== String(resultRequestId)) return false;
  }
  return true;
}
