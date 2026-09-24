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

const ROLE_FEATURE_WEIGHT = Object.freeze({
  report_headline: 12, hero_metric: 11, primary_analysis: 10, causal_evidence: 10,
  decision_risk: 9, narrative_interpretation: 8, detailed_evidence: 7,
  conclusion: 7, supporting_analysis: 6, action_status: 5, context: 3,
});
const EMPHASIS_WEIGHT = Object.freeze({ compact: .72, standard: 1, prominent: 1.35, hero: 1.8 });
const VISUAL_ENGINES = new Set(['CoreChartEngine','EngineeringChartEngine','TableEngine','DiagramEngine','WaferFabEngine','ImageMediaEngine','MatrixEngine','TimelineEngine']);

function densityHint(entry = {}, profile = {}) {
  const rows = entry.customTable?.rows || entry.rows || entry.data || [];
  const copy = String(entry.text || entry.body || entry.content || '').trim();
  const sourceCount = Array.isArray(rows) ? rows.length : 0;
  return Math.min(2.5, Math.log2(1 + sourceCount) * .25 + Math.min(1.25, copy.length / 480) + Math.min(.75, Number(profile.minH || 0) / 600));
}

function featureScore(entry, preset, profile = {}) {
  const role = compositionRole(entry);
  const explicit = Object.hasOwn(EMPHASIS_WEIGHT, entry.emphasis);
  const explicitEmphasis = explicit ? ({compact:.68,standard:1,prominent:1.48,hero:2.65}[entry.emphasis]||1) : 1;
  const automaticEmphasis = explicit ? 1 : role === 'report_headline' || role === 'hero_metric' ? 1.35
    : ['primary_analysis','causal_evidence','decision_risk','conclusion'].includes(role) ? 1.18 : 1;
  const recipeIntent = compositionProminence(entry, preset);
  const infoDensity = densityHint(entry, profile);
  return (ROLE_FEATURE_WEIGHT[role] || 5) * explicitEmphasis * automaticEmphasis * recipeIntent + infoDensity;
}

function visualEntry(entry) { return VISUAL_ENGINES.has(entry.engine); }
function relatedComparisonPair(entries) {
  if (entries.length !== 2) return false;
  const names = entries.map(entry => `${entry.element || ''} ${entry.title || ''}`.toLowerCase());
  const has = pattern => names.some(value => pattern.test(value));
  return entries.some(entry => entry.engine === 'ComparisonEngine') ||
    (has(/before|baseline|reference|control/) && has(/after|current|affected|treatment/));
}
function usableInOneRow(ids, profiles, pageWidth, gap = 14) {
  const minimum = ids.reduce((sum, id) => sum + Math.max(1, Number(profiles[id]?.minW) || 280), 0);
  return minimum + gap * Math.max(0, ids.length - 1) <= Math.max(1, pageWidth - 28);
}
const row = (ids, ratios = null) => ({ ids: [...ids], ratios: ratios ? [...ratios] : null });

function sectionPattern(section, preset, profiles, pageWidth) {
  const entries = section.items, roles = entries.map(compositionRole), visuals = entries.filter(visualEntry);
  const metrics = entries.filter(entry => ['hero_metric'].includes(compositionRole(entry)) || entry.engine === 'ComparisonEngine');
  const narrative = entries.filter(entry => compositionRole(entry) === 'narrative_interpretation' || entry.engine === 'TextEngine' && compositionRole(entry) === 'context');
  const headline = entries.find(entry => compositionRole(entry) === 'report_headline');
  const hasEvidence = entries.some(entry => ['detailed_evidence','causal_evidence'].includes(compositionRole(entry)) || visualEntry(entry));
  if (section.id === 'delivery' && entries.some(entry => ['conclusion','action_status'].includes(compositionRole(entry)))) return 'closing-next-step';
  if (section.id === 'decision' && entries.some(entry => ['decision_risk','conclusion','action_status'].includes(compositionRole(entry)))) return 'compact-decision-band';
  if (entries.some(entry => entry.engine === 'DiagramEngine' || compositionRole(entry) === 'causal_evidence')) return 'causal-flow-feature';
  if (headline) return 'hero-opening-band';
  if (metrics.length >= 2 && (section.id === 'performance' || metrics.length === entries.length)) return 'compact-kpi-strip';
  if (visuals.length >= 2 && relatedComparisonPair(visuals)) return 'balanced-analytical-pair';
  if (visuals.length >= 3) return 'feature-support-analysis';
  if (narrative.length && hasEvidence) return 'narrative-evidence-split';
  if (entries.filter(entry => compositionRole(entry) === 'detailed_evidence').length >= 1) return 'evidence-detail-grid';
  if (visuals.length >= 2 && roles.some(role => ['primary_analysis','supporting_analysis'].includes(role))) return 'feature-support-analysis';
  if (section.id === 'analysis' && visuals.length === 1 && roles.includes('primary_analysis')) return 'analytical-feature';
  if (visuals.length >= 2 && !usableInOneRow(visuals.map(entry => String(entry.id)), profiles, pageWidth)) return 'feature-support-analysis';
  return 'editorial-flow';
}

function rowsForSection(section, pattern, profiles, pageWidth, featureId) {
  const ids = section.items.map(entry => String(entry.id));
  const byId = new Map(section.items.map(entry => [String(entry.id), entry]));
  const supports = ids.filter(id => id !== featureId);
  const fits = values => usableInOneRow(values, profiles, pageWidth);
  const featureRow = (featureRatio = .64) => {
    if (!featureId) return [];
    const firstSupport = supports[0];
    if (firstSupport && fits([featureId, firstSupport])) return [row([featureId, firstSupport], [featureRatio, 1 - featureRatio])];
    return [row([featureId])];
  };
  if (pattern === 'hero-opening-band') {
    const title = section.items.find(entry => compositionRole(entry) === 'report_headline');
    const titleId = title ? String(title.id) : null;
    const remainder = ids.filter(id => id !== titleId);
    const metrics = remainder.filter(id => compositionRole(byId.get(id)) === 'hero_metric');
    const context = remainder.filter(id => !metrics.includes(id));
    const leadSupport = context[0] || metrics[0];
    const splitLead = titleId && leadSupport && fits([titleId,leadSupport]);
    const result = titleId ? [splitLead ? row([titleId,leadSupport],[.68,.32]) : row([titleId])] : [];
    const usedLead = new Set(splitLead ? [titleId,leadSupport] : titleId ? [titleId] : []);
    const remainingMetrics = metrics.filter(id=>!usedLead.has(id));
    if(remainingMetrics.length)result.push(row(remainingMetrics));
    const remainingContext = context.filter(id=>!usedLead.has(id));
    for (let index=0; index<remainingContext.length;) {
      const pair=remainingContext.slice(index,index+2);
      if(pair.length===2&&fits(pair)){result.push(row(pair));index+=2;}
      else {result.push(row([pair[0]]));index+=1;}
    }
    const used = new Set(result.flatMap(value => value.ids));
    return [...result, ...ids.filter(id => !used.has(id)).map(id => row([id]))];
  }
  if (pattern === 'compact-kpi-strip') {
    const kpis = section.items.filter(entry => compositionRole(entry) === 'hero_metric' || entry.engine === 'ComparisonEngine').map(entry => String(entry.id));
    const orderedKpis = featureId && kpis.includes(featureId) ? [featureId,...kpis.filter(id=>id!==featureId)] : kpis;
    const rest = ids.filter(id => !kpis.includes(id)), max = pageWidth >= 1280 ? 4 : 3, result = [];
    for (let index = 0; index < orderedKpis.length; index += max) {
      const group=orderedKpis.slice(index,index+max);
      const ratios=group.length>1&&index===0?group.map((_,position)=>position===0?({2:.56,3:.42,4:.34}[group.length]||.3):(group.length===2?.44:group.length===3?.29:.22)):null;
      result.push(row(group,ratios));
    }
    return [...result, ...rest.map(id => row([id]))];
  }
  if (pattern === 'causal-flow-feature') {
    const diagram = section.items.find(entry => entry.engine === 'DiagramEngine') || section.items.find(entry => compositionRole(entry) === 'causal_evidence');
    const id = String(diagram?.id || featureId || ids[0]), prose = section.items.find(entry => String(entry.id) !== id && ['TextEngine','DecisionCompositeEngine'].includes(entry.engine));
    const evidence = section.items.find(entry => String(entry.id) !== id && visualEntry(entry) && entry.engine !== 'TableEngine');
    const support = prose || evidence;
    const shortProse = !prose || String(prose.text || prose.body || prose.content || '').length <= 360;
    const result = support && shortProse && fits([id, String(support.id)]) ? [row([id, String(support.id)], [.62,.38])] : [row([id])];
    const used = new Set(result.flatMap(value => value.ids));
    return [...result, ...ids.filter(value => !used.has(value)).map(value => row([value]))];
  }
  if (pattern === 'narrative-evidence-split') {
    const prose = section.items.find(entry => ['narrative_interpretation','context'].includes(compositionRole(entry)) && entry.engine === 'TextEngine');
    const evidence = section.items.find(entry => String(entry.id) !== String(prose?.id) && visualEntry(entry));
    const shortProse = String(prose?.text || prose?.body || prose?.content || '').length <= 360;
    const pair = prose && evidence && shortProse && fits([String(prose.id),String(evidence.id)]);
    const result = pair ? [row([String(prose.id),String(evidence.id)],[.48,.52])] : prose ? [row([String(prose.id)])] : [];
    const used = new Set(result.flatMap(value => value.ids));
    return [...result, ...ids.filter(value => !used.has(value)).map(value => row([value]))];
  }
  if (pattern === 'analytical-feature') {
    const result = featureId ? [row([featureId])] : [];
    const used = new Set(result.flatMap(value => value.ids));
    return [...result, ...ids.filter(id => !used.has(id)).map(id => row([id]))];
  }
  if (pattern === 'balanced-analytical-pair') {
    const pair = section.items.filter(visualEntry).slice(0, 2).map(entry => String(entry.id));
    if (pair.length === 2 && fits(pair)) return [row(pair,[.5,.5]), ...ids.filter(id => !pair.includes(id)).map(id => row([id]))];
  }
  if (pattern === 'evidence-detail-grid') {
    const evidence = section.items.filter(entry => compositionRole(entry) === 'detailed_evidence').map(entry => String(entry.id));
    const result = [];
    for (let index = 0; index < evidence.length;) {
      const pair = evidence.slice(index,index+2);
      if (pair.length === 2 && fits(pair)) { result.push(row(pair)); index += 2; }
      else { result.push(row([pair[0]])); index += 1; }
    }
    return [...result, ...ids.filter(id => !evidence.includes(id)).map(id => row([id]))];
  }
  if (pattern === 'compact-decision-band' || pattern === 'closing-next-step') {
    if (fits(ids)) return [row(ids)];
    return featureRow(.62).concat(supports.slice(featureRow(.62)[0]?.ids.length ? 1 : 0).map(id => row([id])));
  }
  if (pattern === 'feature-support-analysis') {
    const visualIds=section.items.filter(visualEntry).map(entry=>String(entry.id));
    if(visualIds.length>=3){
      const featureVisual=featureId&&visualIds.includes(featureId)?featureId:visualIds[0];
      const orderedVisuals=[featureVisual,...visualIds.filter(id=>id!==featureVisual)],result=[],used=new Set();
      const first=orderedVisuals.slice(0,3);
      if(first.length===3&&fits(first)){
        result.push(row(first,[.39,.33,.28]));first.forEach(id=>used.add(id));
      }else{
        const support=orderedVisuals[1];
        if(support&&fits([featureVisual,support])){result.push(row([featureVisual,support],[.64,.36]));used.add(featureVisual);used.add(support);}
        else {result.push(row([featureVisual]));used.add(featureVisual);}
      }
      const remainingVisuals=orderedVisuals.filter(id=>!used.has(id));
      for(let index=0;index<remainingVisuals.length;){
        const pair=remainingVisuals.slice(index,index+2);
        if(pair.length===2&&fits(pair)){result.push(row(pair,[.64,.36]));index+=2;}
        else {result.push(row([pair[0]]));index+=1;}
      }
      return [...result,...ids.filter(id=>!visualIds.includes(id)).map(id=>row([id]))];
    }
    const result = featureRow(.64), used = new Set(result.flatMap(value => value.ids));
    const remaining = supports.filter(id => !used.has(id));
    for (let index = 0; index < remaining.length;) {
      const pair = remaining.slice(index,index+2);
      if (pair.length === 2 && fits(pair)) { result.push(row(pair)); index += 2; }
      else { result.push(row([pair[0]])); index += 1; }
    }
    return result;
  }
  // Editorial flow packs short, compatible content together without turning
  // a semantic section into an unbroken full-width column.
  const result = []; let current = [];
  for (const id of ids) {
    const role = compositionRole(byId.get(id)), forceOwn = ['report_headline','narrative_interpretation','conclusion'].includes(role) || byId.get(id)?.engine === 'DiagramEngine';
    if (forceOwn && current.length) { result.push(row(current)); current = []; }
    const next = [...current,id];
    if (current.length && !fits(next)) { result.push(row(current)); current = [id]; }
    else current = next;
    if (forceOwn) { result.push(row(current)); current = []; }
  }
  if (current.length) result.push(row(current));
  return result;
}

export function sectionCompositionPlan(items = [], preset = 'editorial', pageWidth = 1440, profiles = {}) {
  const grouped = new Map();
  for (const entry of compositionOrder(items, preset)) {
    const role = compositionRole(entry), section = compositionSection(entry, role);
    if (!grouped.has(section.id)) grouped.set(section.id, { id: section.id, title: section.title, items: [], order: entry.section_order });
    grouped.get(section.id).items.push(entry);
  }
  return [...grouped.values()].map((section,index) => {
    const pattern = sectionPattern(section, preset, profiles, pageWidth);
    const feature = [...section.items].sort((a,b) => featureScore(b,preset,profiles[String(b.id)]||{})-featureScore(a,preset,profiles[String(a.id)]||{}) || Number(a.order||0)-Number(b.order||0) || String(a.id).localeCompare(String(b.id)))[0];
    const featureId = feature ? String(feature.id) : null;
    const rows = rowsForSection(section, pattern, profiles, pageWidth, featureId);
    return { id:section.id, title:section.title, order:index, pattern, featureId,
      supportIds:section.items.map(entry=>String(entry.id)).filter(id=>id!==featureId),
      rows:rows.map((value,rowIndex)=>({ ...value, section:section.id, title:section.title, pattern, featureId, rowIndex, sectionStart:rowIndex===0 })) };
  });
}

export function compositionSpacing({ density = 'comfortable', itemCount = 1 } = {}) {
  const scale = density === 'dense' ? -3 : density === 'compact' ? -1 : density === 'comfortable' ? 2 : 0;
  const stackGap = Math.max(12,Math.min(20,16+scale));
  const sectionGap = Math.max(20,Math.min(34,24+scale+Math.min(6,Math.floor(Math.max(0,itemCount-2)/2))));
  return { stackGap, sectionGap, headingHeight:26, rowGap:Math.max(12,Math.min(18,14+Math.round(scale/2))) };
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
