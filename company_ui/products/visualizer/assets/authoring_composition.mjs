// Shared report-level composition authority for Smart layout, templates and
// named composition recipes. Roles are additive metadata; legacy reports are
// interpreted deterministically without requiring a schema migration.
export const COMPOSITION_VERSION = 1;

export const COMPOSITION_ROLES = Object.freeze([
  'report_headline', 'context', 'hero_metric', 'primary_analysis',
  'supporting_analysis', 'narrative_interpretation', 'detailed_evidence',
  'causal_evidence', 'decision_risk', 'action_status', 'conclusion',
]);

export const COMPOSITION_SECTIONS = Object.freeze({
  opening: 'Overview',
  performance: 'Performance',
  analysis: 'Analysis',
  evidence: 'Evidence',
  decision: 'Decision',
  delivery: 'Next steps',
});

const ROLE_RANK = Object.freeze(Object.fromEntries(COMPOSITION_ROLES.map((role, index) => [role, index])));
const LEGACY_ROLE = Object.freeze({
  report_headline: 'Headline', context: 'Context', hero_metric: 'Supporting Evidence',
  primary_analysis: 'Primary Evidence', supporting_analysis: 'Supporting Evidence',
  narrative_interpretation: 'Context', detailed_evidence: 'Primary Evidence',
  causal_evidence: 'Primary Evidence', decision_risk: 'Risk', action_status: 'Action',
  conclusion: 'Action',
});

const ROLE_SECTIONS = Object.freeze({
  report_headline: 'opening', context: 'opening', hero_metric: 'performance',
  primary_analysis: 'analysis', supporting_analysis: 'analysis',
  narrative_interpretation: 'analysis', detailed_evidence: 'evidence',
  causal_evidence: 'evidence', decision_risk: 'decision', action_status: 'delivery',
  conclusion: 'delivery',
});

const RECIPE_ROLES = Object.freeze({
  editorial: ['report_headline','context','hero_metric','primary_analysis','supporting_analysis','narrative_interpretation','detailed_evidence','causal_evidence','decision_risk','action_status','conclusion'],
  executive: ['report_headline','context','hero_metric','primary_analysis','supporting_analysis','narrative_interpretation','detailed_evidence','causal_evidence','decision_risk','action_status','conclusion'],
  technical: ['report_headline','context','hero_metric','primary_analysis','causal_evidence','supporting_analysis','detailed_evidence','narrative_interpretation','decision_risk','action_status','conclusion'],
  scorecard: ['report_headline','hero_metric','primary_analysis','supporting_analysis','detailed_evidence','narrative_interpretation','decision_risk','action_status','conclusion','context','causal_evidence'],
  narrative: ['report_headline','context','narrative_interpretation','primary_analysis','supporting_analysis','causal_evidence','detailed_evidence','hero_metric','decision_risk','action_status','conclusion'],
  review: ['report_headline','hero_metric','primary_analysis','detailed_evidence','supporting_analysis','narrative_interpretation','decision_risk','action_status','conclusion','context','causal_evidence'],
  investigation: ['report_headline','context','hero_metric','primary_analysis','detailed_evidence','causal_evidence','supporting_analysis','narrative_interpretation','decision_risk','action_status','conclusion'],
  manufacturing: ['report_headline','hero_metric','primary_analysis','causal_evidence','supporting_analysis','detailed_evidence','narrative_interpretation','decision_risk','action_status','conclusion','context'],
  roadmap: ['report_headline','context','action_status','decision_risk','primary_analysis','supporting_analysis','detailed_evidence','narrative_interpretation','hero_metric','conclusion','causal_evidence'],
  comparison: ['report_headline','hero_metric','primary_analysis','supporting_analysis','detailed_evidence','narrative_interpretation','decision_risk','action_status','conclusion','context','causal_evidence'],
  showcase: ['report_headline','hero_metric','decision_risk','primary_analysis','detailed_evidence','supporting_analysis','narrative_interpretation','action_status','conclusion','context','causal_evidence'],
});

const RECIPE_PROMINENCE = Object.freeze({
  editorial: {},
  executive: { report_headline: 1.12, hero_metric: 1.18, decision_risk: 1.08, conclusion: 1.05 },
  technical: { primary_analysis: 1.24, causal_evidence: 1.2, detailed_evidence: 1.16, supporting_analysis: 1.06 },
  scorecard: { hero_metric: 1.24, detailed_evidence: 1.1, decision_risk: 1.08 },
  narrative: { narrative_interpretation: 1.24, context: 1.1, conclusion: 1.12 },
  review: { primary_analysis: 1.14, detailed_evidence: 1.1, decision_risk: 1.12 },
  investigation: { causal_evidence: 1.22, detailed_evidence: 1.18, narrative_interpretation: 1.08 },
  manufacturing: { hero_metric: 1.1, primary_analysis: 1.12, causal_evidence: 1.22, detailed_evidence: 1.12, action_status: 1.08 },
  roadmap: { action_status: 1.22, decision_risk: 1.15, context: 1.08 },
  comparison: { primary_analysis: 1.12, supporting_analysis: 1.14, hero_metric: 1.08 },
  showcase: { report_headline: 1.18, hero_metric: 1.16, detailed_evidence: 1.12 },
});

const low = value => String(value ?? '').trim().toLowerCase();

function explicitOrNameRole(entry = {}) {
  const name = low(`${entry.element || ''} ${entry.title || ''}`);
  if (/conclusion|next step|recommendation|key takeaway|finding/.test(name)) return 'conclusion';
  if (/headline|hero title|executive statement|report title/.test(name)) return 'report_headline';
  if (/risk|decision|trade.?off|disposition/.test(name)) return 'decision_risk';
  if (/corrective|action|project|roadmap|milestone|status/.test(name)) return 'action_status';
  if (/process flow|cause|causal|fishbone|mechanism/.test(name) || entry.engine === 'DiagramEngine') return 'causal_evidence';
  if (/table|matrix|evidence|wafer|image|screenshot|distribution|histogram|box plot/.test(name) || entry.engine === 'TableEngine' || entry.engine === 'WaferFabEngine' || entry.engine === 'ImageMediaEngine') return 'detailed_evidence';
  if (entry.engine === 'MetricEngine') return 'hero_metric';
  if (entry.engine === 'ComparisonEngine') return 'hero_metric';
  if (/narrative|interpretation|commentary/.test(name)) return 'narrative_interpretation';
  if (/context|scope|hypothesis|metadata|footnote|background/.test(name)) return 'context';
  if (/analysis|trend|chart|spc/.test(name) || entry.engine === 'CoreChartEngine' || entry.engine === 'EngineeringChartEngine') return 'primary_analysis';
  if (entry.message_role === 'Headline') return 'report_headline';
  if (entry.message_role === 'Risk') return 'decision_risk';
  if (entry.message_role === 'Action') return 'action_status';
  if (entry.message_role === 'Context') return 'context';
  if (entry.message_role === 'Primary Evidence') return 'primary_analysis';
  return 'supporting_analysis';
}

export function compositionRole(entry = {}) {
  return COMPOSITION_ROLES.includes(entry.composition_role) ? entry.composition_role : explicitOrNameRole(entry);
}

export function legacyMessageRole(role) {
  return LEGACY_ROLE[role] || 'Supporting Evidence';
}

export function compositionSection(entry = {}, role = compositionRole(entry)) {
  const id = String(entry.section_id || ROLE_SECTIONS[role] || 'analysis');
  return { id, title: String(entry.section_title || COMPOSITION_SECTIONS[id] || 'Analysis') };
}

export function compositionProminence(entry = {}, preset = 'editorial') {
  const scale = Number(RECIPE_PROMINENCE[preset]?.[compositionRole(entry)] ?? 1);
  return Number.isFinite(scale) ? Math.max(1, Math.min(1.3, scale)) : 1;
}

export function compositionOrder(items = [], preset = 'editorial') {
  const roles = RECIPE_ROLES[preset] || RECIPE_ROLES.editorial;
  const rank = new Map(roles.map((role, index) => [role, index]));
  const sectionRank = new Map(Object.keys(COMPOSITION_SECTIONS).map(section => [section, Math.min(...roles.map((role,index)=>ROLE_SECTIONS[role]===section?index:99))]));
  const customSectionRank = new Map();
  for (const entry of items) {
    const role = compositionRole(entry), section = compositionSection(entry, role).id;
    if (!sectionRank.has(section)) customSectionRank.set(section, Math.min(customSectionRank.get(section) ?? 99, sectionRank.get(ROLE_SECTIONS[role]) ?? 99));
  }
  return [...items].sort((a, b) => {
    const ar = compositionRole(a), br = compositionRole(b);
    const as = compositionSection(a, ar).id, bs = compositionSection(b, br).id;
    const hasSectionOrderA = a.section_order !== undefined && a.section_order !== null && a.section_order !== '' && Number.isFinite(Number(a.section_order));
    const hasSectionOrderB = b.section_order !== undefined && b.section_order !== null && b.section_order !== '' && Number.isFinite(Number(b.section_order));
    const sectionOrderA = hasSectionOrderA ? Number(a.section_order) : sectionRank.get(as) ?? customSectionRank.get(as) ?? 99;
    const sectionOrderB = hasSectionOrderB ? Number(b.section_order) : sectionRank.get(bs) ?? customSectionRank.get(bs) ?? 99;
    return sectionOrderA - sectionOrderB || (rank.get(ar) ?? 99) - (rank.get(br) ?? 99) || Number(a.order || 0) - Number(b.order || 0) || String(a.id).localeCompare(String(b.id));
  });
}

export function composeReportModel(model = {}, preset = model.layoutPreset || 'editorial') {
  const next = structuredClone(model || {});
  const ranked = compositionOrder(next.items || [], preset);
  const orderById = new Map(ranked.map((entry, index) => [String(entry.id), index]));
  next.mode = 'smart';
  next.layoutPreset = preset;
  next.items = (next.items || []).map(entry => {
    const role = compositionRole(entry);
    const section = compositionSection(entry, role);
    return {
      ...entry,
      composition_role: role,
      section_id: section.id,
      section_title: section.title,
      message_role: entry.message_role || legacyMessageRole(role),
      order: orderById.get(String(entry.id)) ?? entry.order,
    };
  });
  return next;
}

export function compositionRecipe(preset = 'editorial') {
  return { id: preset, version: COMPOSITION_VERSION, roles: [...(RECIPE_ROLES[preset] || RECIPE_ROLES.editorial)], prominence: structuredClone(RECIPE_PROMINENCE[preset] || RECIPE_PROMINENCE.editorial) };
}
