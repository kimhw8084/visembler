import { ELEMENTS_BY_ENGINE } from '../vendor/production_core/core/runtime_registry.mjs';

const tierByEngine=Object.freeze({
  TextEngine:'A', CoreChartEngine:'B', EngineeringChartEngine:'B', TableEngine:'B', MetricEngine:'B', ComparisonEngine:'B',
  TimelineEngine:'B', DiagramEngine:'B', WaferFabEngine:'B', MatrixEngine:'C', ImageMediaEngine:'B',
  EvidenceCompositeEngine:'C', DecisionCompositeEngine:'C', ProjectCompositeEngine:'C', SmartLayoutEngine:'B',
  InteractionLayer:'D', EditorInfrastructure:'D',
});
const dataDriven=new Set(['TextEngine','CoreChartEngine','EngineeringChartEngine','TableEngine','MetricEngine','ComparisonEngine','TimelineEngine','DiagramEngine','WaferFabEngine']);
const highFidelityExport=new Set(['TextEngine','CoreChartEngine','EngineeringChartEngine','TableEngine','MetricEngine','ComparisonEngine','TimelineEngine','DiagramEngine','ImageMediaEngine','MatrixEngine']);
const directEdit=new Set(['TextEngine','MetricEngine','TableEngine','TimelineEngine','DiagramEngine','ImageMediaEngine','CoreChartEngine','EngineeringChartEngine','WaferFabEngine']);

export const ELEMENT_MATURITY_AUDIT=Object.freeze(Object.entries(ELEMENTS_BY_ENGINE).flatMap(([engine,elements])=>elements.map(element=>Object.freeze({
  engine, element, tier:tierByEngine[engine]||'C',
  semantic_data:dataDriven.has(engine), direct_edit:directEdit.has(engine), inspector:directEdit.has(engine)?'specific':'generic',
  data_binding:dataDriven.has(engine), empty_state:dataDriven.has(engine), layout_modes:engine!=='InteractionLayer'&&engine!=='EditorInfrastructure',
  undo_redo:engine!=='InteractionLayer'&&engine!=='EditorInfrastructure', accessibility:engine!=='InteractionLayer'&&engine!=='EditorInfrastructure',
  export_eligibility:highFidelityExport.has(engine)?'high_fidelity':'semantic_text_only',
  hardcoded_risk:['MatrixEngine','EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine','InteractionLayer','EditorInfrastructure'].includes(engine)?'high':engine==='MetricEngine'||engine==='ComparisonEngine'?'medium':'low',
  duplicate_family:engine==='InteractionLayer'||engine==='EditorInfrastructure'?'internal-authoring-control':null,
}))));

export const MATURITY_COUNTS=Object.freeze(['A','B','C','D'].reduce((counts,tier)=>({...counts,[tier]:ELEMENT_MATURITY_AUDIT.filter(entry=>entry.tier===tier).length}),{}));
// Baseline measured with the same contract before semantic table/metric/comparison renderer upgrades.
export const BASELINE_MATURITY_COUNTS=Object.freeze({A:15,B:143,C:57,D:33});
