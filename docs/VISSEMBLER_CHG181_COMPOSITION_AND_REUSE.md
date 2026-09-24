# CHG-181 report composition and analytical reuse

CHG-181 adds two authoring capabilities to the existing Visembler report model.
Smart composition and reusable data remapping share the existing report, preset,
mapping, renderer, history and persistence paths. They do not create a parallel
report format or a second data-mapping authority.

## Semantic composition

Composition metadata is optional and backward-compatible. An item may carry
`composition_role`, `section_id`, `section_title` and `section_order`. Roles
identify what the item contributes to the report; sections establish the
reading sequence. The default section and legacy `message_role` are derived
from the role when absent. Reports created before this metadata existed remain
readable and receive deterministic role defaults from their semantic element,
engine, title and message role.

The shared composition module (`authoring_composition.mjs`) owns the canonical
role vocabulary and the named recipes. Templates assign explicit roles and
sections, while Smart layout, template application and named recipes use the
same ordering authority. Smart recomposition is a single governed report edit,
so normal undo, redo, revision history and save/reload behavior apply. Guided
and Free authoring continue to use the existing manual geometry; choosing Smart
is the explicit request to compose the report again.

Canonical roles are `report_headline`, `context`, `hero_metric`,
`primary_analysis`, `supporting_analysis`, `narrative_interpretation`,
`detailed_evidence`, `causal_evidence`, `decision_risk`, `action_status` and
`conclusion`. Built-in recipes change semantic ordering and grouping; they are
not element-type sort lists. Existing renderers and content-fit logic continue
to own component visuals and export geometry.

## Reusable analytical binding contract

Personal report and section assets may include
`binding_contract: {version: 1, kind: "analytical-bindings", slots: [...]}`.
Each slot represents one intentionally shared source dataset. It records a
stable logical slot identity and name, source schema signature and human-facing
field names/types/tags, required mapping roles, item bindings, field references,
transform and analysis/statistical/engineering recipe identities, and which
items depend on the slot. It intentionally contains no report-scoped dataset
identity. Preference storage normalizes old records and rejects malformed,
oversized, or identity-bearing contracts without changing report authorization
or dataset revisions.

Unbound manual metrics, comparisons and evidence-table rows are listed as
`manual_value_items`. Structure reuse clears those source values while keeping
their presentation and meaning; the remap review names them before commit so
the author knows which values need destination-specific entry. Explicit source
data copy keeps the complete saved values.

In structure-reuse mode, the saved structure and analytical recipes are kept,
while source datasets, mappings and cached source-derived values are omitted.
When applied, compatible exact field-name/type matches are suggested. Multiple
possible data sources, ambiguous fields, missing required roles or incompatible
types remain unresolved and prevent commit. The guided remap surface shows what
each slot drives, the selected destination, field roles and compatibility
problems before the user commits. A user can select an existing data source;
new or pasted data first enters through the existing Data First intake. Explicit
source-data copy mode remains available for users who want the original data.

Saved analysis identities are checked with the existing analysis semantics
against the destination rows before the plan becomes ready. A chart whose roles
map but whose analysis has no usable destination observations remains blocked
with an explanation. Role labels in the workflow use product terms such as
Category, Measurement, Reference, and Affected. Bar summaries likewise report
Category and Value from their canonical mapping roles. Wafer and wafer
difference marks are clipped to their Company-owned circular SVG geometry.

Successful remapping translates field references and applies all item bindings
for a shared slot together. The resulting report edit is committed once through
the normal governed update path; the saved asset and source dataset are not
modified. Undo/redo and report history therefore continue to describe one
atomic change.

## Verification

The focused module suite is `tests/test_visualizer_chg181_semantic_reuse.py`.
The maintained native browser journey is
`scripts/release_checks/run_chg181_authoring_acceptance.py`; it exercises
Report Hub, Data First, Inspector, reusable presets, remapping, Preview and
PowerPoint export. Its mixed-report fixtures include a complete circular die
population and mapped engineering measurements so spatial and control-chart
states are reviewed as report content. The full release authority remains
`python scripts/verify_release.py --host-mode native` and binds its receipts to
one stable source manifest.

This BUILD produces R1 product and evidence candidates only. CHG-173 remains the
separate independent whole-report outcome audit.
