// Wave 2 production-facing library.
//
// The authoritative runtime registry intentionally remains much broader.
// Hidden entries are not deleted; existing reports remain compatible.

const freezeItems = items => Object.freeze(items.map(item => Object.freeze(item)));

export const PRODUCTION_LIBRARY = Object.freeze({
  TextEngine: freezeItems([
    {element:'Hero Title', description:'Primary report title or headline.'},
    {element:'Section Heading', description:'Clear section hierarchy and report structure.'},
    {element:'Executive Statement', description:'Prominent conclusion or recommendation.'},
    {element:'Body Narrative', description:'Long-form explanation or supporting context.'},
    {element:'Key Takeaway', description:'Concise highlighted insight.'},
  ]),
  MetricEngine: freezeItems([
    {element:'Hero KPI', description:'Single headline metric with comparison context.'},
    {element:'Metric + Delta', description:'Metric with period-over-period change.'},
    {element:'Target vs Actual', description:'Actual performance against an explicit target.'},
    {element:'Progress Metric', description:'Progress toward a bounded goal.'},
    {element:'Status Metric', description:'Metric paired with an operating state.'},
    {element:'Capacity Metric', description:'Current usage versus available capacity.'},
    {element:'Rate Metric', description:'Numerator/denominator or per-period rate.'},
    {element:'Threshold Metric', description:'Value against warning and critical thresholds.'},
    {element:'Metric with Sparkline', description:'KPI with compact trend context.'},
    {element:'Metric Ring', description:'Bounded value rendered against an explicit maximum.'},
  ]),
  ComparisonEngine: freezeItems([
    {element:'As-Is → To-Be', description:'Current state compared with the intended future state.'},
    {element:'Before/After KPI', description:'Direct before-versus-after KPI comparison.'},
    {element:'Time Compression', description:'Cycle-time reduction with explicit before/after values.'},
  ]),
  CoreChartEngine: freezeItems([
    {element:'Vertical Bar', description:'Compare values across categories.'},
    {element:'Horizontal Bar', description:'Rank or compare categories with longer labels.'},
    {element:'Line Chart', description:'Show an ordered trend over categories or time.'},
    {element:'Area Chart', description:'Show an ordered trend with magnitude emphasis.'},
  ]),
  TableEngine: freezeItems([
    {element:'Clean Table', description:'Fully editable pasted or manually entered data grid.'},
  ]),
  TimelineEngine: freezeItems([
    {element:'Event Timeline', description:'Ordered events with editable labels and dates.'},
    {element:'Milestone Rail', description:'Compact milestone progression.'},
    {element:'Sequence Strip', description:'Simple ordered process or validation sequence.'},
  ]),
  DiagramEngine: freezeItems([
    {element:'Process Flow', description:'Editable nodes and connectors for a process.'},
    {element:'Data Flow', description:'Editable nodes and connectors for data movement.'},
  ]),
  ImageMediaEngine: freezeItems([
    {element:'Image', description:'Paste or upload an image with fit and focal controls.'},
    {element:'Image + Caption', description:'Image with editable caption and accessibility text.'},
    {element:'Screenshot Frame', description:'Application screenshot presentation frame.'},
  ]),
  EvidenceCompositeEngine: freezeItems([
    {element:'Evidence Card', description:'Evidence statement, supporting detail, and status.'},
  ]),
  DecisionCompositeEngine: freezeItems([
    {element:'Risk Callout', description:'Editable decision risk statement, detail, and status.'},
  ]),
  ProjectCompositeEngine: freezeItems([
    {element:'Project Card', description:'Project statement, detail, and current status.'},
  ]),
  EngineeringChartEngine: freezeItems([
    {element:'SPC Control Chart', description:'Process behavior with explicit control/specification limits.'},
    {element:'I-MR Chart', description:'Individuals and moving-range process monitoring.'},
    {element:'CUSUM Chart', description:'Cumulative-sum monitoring for sustained process shifts.'},
    {element:'EWMA Chart', description:'Exponentially weighted monitoring for smaller shifts.'},
  ]),
  WaferFabEngine: freezeItems([
    {element:'Wafer Map', description:'Spatial wafer measurements with fab identity context.'},
  ]),
});

export const PRODUCTION_RECOMMENDED = Object.freeze([
  'MetricEngine::Hero KPI',
  'TextEngine::Key Takeaway',
  'CoreChartEngine::Line Chart',
  'TableEngine::Clean Table',
  'TimelineEngine::Event Timeline',
  'ImageMediaEngine::Image',
  'DiagramEngine::Process Flow',
  'EngineeringChartEngine::SPC Control Chart',
  'WaferFabEngine::Wafer Map',
]);

export function productionEntries() {
  return Object.entries(PRODUCTION_LIBRARY).flatMap(([engine, items]) =>
    items.map(item => ({engine, element:item.element, description:item.description}))
  );
}

export const PRODUCTION_LIBRARY_COUNT = productionEntries().length;

export function isProductionElement(engine, element) {
  return Boolean(PRODUCTION_LIBRARY[engine]?.some(item => item.element === element));
}
