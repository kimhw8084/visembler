// Transient production preview authority. The incoming ID is only an HTML
// identity for renderer references; no report item or saved ID is allocated.
import { renderIntegratedElement } from './element_renderer.mjs';
import { projectDataEntry } from './authoring_projection.mjs';

const typeForEngine = Object.freeze({ CoreChartEngine: 'chart', TableEngine: 'table', TimelineEngine: 'timeline', DiagramEngine: 'diagram', EngineeringChartEngine: 'engineering', WaferFabEngine: 'wafer' });

export function transientProductionEntry({ id = '__data-first-preview__', target, view = '', mapping = {}, dataset = {} } = {}) {
  if (!target?.engine || !target?.element) return null;
  const previewDataset = { ...dataset, id: dataset.id || '__data-first-preview-dataset__' };
  const entry = { id: id || '__data-first-preview__', type: typeForEngine[target.engine] || 'chart', engine: target.engine, element: target.element, title: target.element, showTitle: false, dataset_id: previewDataset.id, view_type: target.view || view, mapping: structuredClone(mapping || {}) };
  const patch = projectDataEntry(entry, previewDataset, entry.mapping);
  return { ...entry, ...patch, _resolved_dataset: patch._resolved_dataset || previewDataset };
}

export function renderDataFirstPreview(options = {}) {
  const entry = transientProductionEntry(options);
  return entry ? renderIntegratedElement(entry) : '';
}
