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

## Whole-report section grammar (R2)

Smart composition derives one deterministic pattern for each semantic section
from its roles, engines, item count, content requirements, available page width
and selected recipe. The supported patterns are hero/opening band, compact KPI
strip, analytical feature, feature/support analysis, balanced analytical pair,
evidence/detail grid, narrative/evidence split, causal-flow feature, compact
decision band, closing next step, and an editorial flow for content that does
not match a specialized pattern. A single analysis visual uses the
analytical-feature pattern; it does not reserve an empty support column.
Causal flow may pair with short interpretation or compatible visual evidence
when the section's content fits, while dense evidence tables keep their
available width. Patterns describe placement only; chart view, mapping, data,
transformation, analysis recipe and source values are never rewritten to
manufacture visual variety.

Every section identifies its feature and supporting entries from composition
role, explicit emphasis, recipe prominence and available content density.
Feature/support rows use bounded width ratios only when the item minimums fit;
otherwise the feature leads in its own row. Related before/current or
reference/affected comparisons can use a balanced pair. Other paired analyses
favor a feature/support hierarchy. Evidence grids and KPI strips break into
readable rows when page width requires it.

The row gap, section gap and heading height come from the shared
`compositionSpacing` authority and have explicit minimum and maximum bounds.
Item heights remain content-driven, and Smart canvas height follows the
resulting content instead of stretching components to fill a saved blank page.
An individually authored visual uses the available content hull for its
standalone Smart canvas; multi-item reports retain intrinsic component heights.
Stage A occupancy checks use that live Smart hull while keeping their existing
area thresholds, since the persisted page height remains user-authored.
The section heading and any section surface are derived browser state. No new
section-layout field is required in report JSON. Older reports therefore get
the same stable defaults; custom `section_id`, `section_title`,
`section_order`, `composition_role` and emphasis continue to take effect.
Guided and Free keep their stored manual geometry. Smart reflow remains one
normal governed report edit with undo/redo and revision history.

The narrow Preview uses the exact derived row order, including feature/support
order, and collapses each section to one readable column. Browser acceptance
checks section patterns, feature assignment, canvas bounds, overlap, accessible
section headings, mobile ordering and unchanged chart/data semantics.

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

## Shared-slot remap presentation (R2)

The reusable-binding contract and planner stay unchanged. In the dialog,
equivalent requirements such as chart `x` plus table `category`, or chart `y`
plus table `value`, share one field selector when their source field identity,
type and semantic tags match. Selecting it applies the same field to each
underlying visual role in that slot. The slot shows its dependent visuals once,
using human labels and concise chips. Different source requirements stay
separate. Ambiguous and incompatible mappings remain visible as one concise
diagnostic per distinct requirement, with field-level guidance; Apply stays
disabled until the existing compatibility plan is ready. Focus restoration,
Escape return, source-data copy, source immutability and atomic commit continue
through the existing workflow.

## Verification

The focused module suites are
`tests/test_visualizer_chg181_semantic_reuse.py` and
`tests/test_visualizer_chg181_section_composition.py`.
The maintained native browser journey is
`scripts/release_checks/run_chg181_authoring_acceptance.py`; it exercises
Report Hub, Data First, Inspector, reusable presets, remapping, Preview and
PowerPoint export. Its mixed-report fixtures include a complete circular die
population and mapped engineering measurements so spatial and control-chart
states are reviewed as report content. The full release authority remains
`python scripts/verify_release.py --host-mode native` and binds its receipts to
one stable source manifest.

R2 completes the bounded CHG-181 composition and remap-presentation repair.
It is not a CHG-173 promotion or a company-managed target certification.
