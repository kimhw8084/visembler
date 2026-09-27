# Root cause and source authority

## Root boundary

`company_ui/products/visualizer/assets/chart_studio.mjs` is the canonical authoring authority; x-axis `auto` controls scale/domain. Before this fix, `company_ui/products/visualizer/ppt_service.py::_chart_label_layout` guessed label intent from deviations from defaults. That made a supported authored interval of 1 or rotation of 0 indistinguishable from untouched settings. Its automatic-fit decision also ignored authored rotation when estimating horizontal label width. As a result, a rotated chart could retain its angle but still be thinned using unrotated text width.

## Contract implemented

The optional `axes.x.labelPresentationIntent` object is backward-compatible and has the shape `{"mode":"authored","fields":["interval","rotation","tickCount"]}` (fields reflect what the author changed). Supported readable-axis presets, explicit interval/rotation/tick-count edits—including setting them to default-valued 1/0/6—record intent. The visible reset-to-automatic command clears intent and resets label interval, rotation and tick count while leaving scale auto independent. Old reports without the marker remain valid and retain the existing automatic path; existing non-default values remain explicit.

The exporter honors authored layout values exactly and prevents CHG-277 density fallback from replacing an authored interval. Untouched charts retain adaptive thinning. Four-or-fewer categories use bounded geometry/font/wrapping rather than routine identity loss. Fit uses projected rotated width; medium-density untouched labels may get modest automatic rotation before labels are dropped. Category strings, chart family, series/value semantics and y-domain remain in OOXML. An editable text-label overlay is used when the target preview needs visible category identities; semantic categories remain in chart caches.

## Change surface

- `company_ui/products/visualizer/assets/chart_studio.mjs`: provenance recording and reset action.
- `company_ui/products/visualizer/ppt_service.py`: optional provenance projection, intent-aware fit, rotation-aware footprint, bounded sparse-label behavior and editable label handling.
- `tests/test_visualizer_chg277_pptx_chart_label_layout.py`, `tests/test_visualizer_chart_studio.py`: deterministic export, backward-compatibility and persistence coverage.
- `scripts/release_checks/run_chart_studio_acceptance.py`: C104–C109 supported-authoring acceptance.
- `company_ui/certification/certification_manifest.json`: maintained test count updated to the collected count 1233.

Frozen `ppt_template_adapter.py` was not changed. No report composition, responsive CSS, data, category, series or y-domain semantics were changed.
