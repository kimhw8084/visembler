# Company UI — Gemma/OpenCode Construction Contract

This repository is an application platform, not a loose NiceGUI starter. In normal application work, treat `company_ui/` as stable framework code and build features in the application layer.

## Required workflow

1. Read `company_ui/ai/construction_manifest.json` and this file.
2. Resolve the business/data requirement before choosing UI.
3. Inspect `docs/APP_PATTERNS.md`; select the closest registered page pattern.
4. Inspect `docs/COMPONENT_CATALOG.md` and the relevant registry before creating a component.
5. Use semantic framework APIs; do not recreate visual behavior.
6. Keep database/API work in services/repositories, not page callbacks.
7. Use Phase 8 async/state primitives for cancellation, refresh, persistence, shortcuts and stale-response control.
8. Use Phase 10 security/runtime primitives for authentication, permissions, uploads, proxy identity, logging and health.
9. Run `python -m company_ui.validate <app-root>` after meaningful modifications.
10. Run unit/startup tests. Fix validator errors before completion.

## Normal import rule

Prefer `from company_ui import ...`. Do not import `nicegui.ui` directly in normal application modules. Raw NiceGUI is an explicit escape hatch only.

## UI decision hierarchy

**Page pattern → semantic layout → framework component → controlled extension.**

Never reverse this order by starting with CSS or raw NiceGUI primitives.

## Framework invariants

- Light/dark/system theme behavior is framework-owned.
- Spacing, radius, typography, surfaces, motion and breakpoints are framework-owned.
- `DataTable` owns normal enterprise tabular behavior; do not instantiate AG Grid directly.
- Company visualization wrappers own ECharts grammar, palette and linked filtering.
- `Icons.*` / `Illustrations.*` own standard visual resources.
- Drawers, dialogs, menus, popovers, toasts and durable states follow Phase 4 interaction laws.
- Spec limits and control limits are distinct.
- Evidence/commonality ranking is not causal probability.
- Authorization must be server-side and fail closed.

## Escape hatch

If no registered framework primitive can satisfy a legitimate requirement, isolate the custom implementation and preserve framework tokens, accessibility, state and error semantics. An intentional validator exemption must be documented immediately above the line using `# company-ui: allow-<rule-id>`.

Do not add an escape hatch merely because raw NiceGUI is quicker.

## Phase 13 performance laws
- Do not optimize by adding raw JavaScript or bypassing Company UI.
- For rapid analytical filters/search, prefer `AnalyticalDataController`.
- For repeated local table queries over stable rows, prefer `TableQueryEngine`.
- Cache only deterministic reads with a bounded TTL; never cache mutations or authorization-variant data under a shared key.
- Prefer `LazyResource` for expensive hidden content.
- Bound fan-out with `ConcurrencyGate`; move unavoidable blocking work with `run_blocking`.
- Use retries only for idempotent transient failures.
- Prefer `ApplicationServices` for standard service setup and `WorkspacePreferenceService` for resumable analytical workspaces.
- Measure hot paths with `PerformanceMonitor`; do not keep speculative optimizations.
## v1.2 production-completion laws
- Use `CONTENT_REGISTRY` components for metrics, detail/property presentation, hierarchy, viewers, workflow, comparison, commands and activity surfaces before creating custom equivalents.
- Preserve field ARIA relationships, keyboard/focus behavior and the skip-to-main-content path.
- Use the completed Company UI table/dialog/state/chart runtime controls rather than recreating them with raw NiceGUI.
- Use `DurableJobAdapter` for restart-survivable long-running work; `InProcessJobAdapter` does not survive process restart.
- Keep Markdown sanitized and visual assets local by default.


## Historical v1.4.0 Gold promotion laws
- Production Gold Candidate is not Company Production Gold until the company-environment harness is green.
- Run `company-ui-gold-certify <deployed-url>` against the real proxy/base path.
- Require browser probes for final promotion; do not waive browser failures for Gold.
- Treat health/readiness, security headers, WebSocket upgrade and required load thresholds as release gates.
- Never store certification credentials in source, command transcripts, or evidence; inject ephemeral values and rely on evidence redaction.
- Preserve `GOLD_CERTIFICATION_EVIDENCE.json` and its SHA-256 sidecar with the promoted release.

## v1.3 zero-stock-visual laws
- NiceGUI and Quasar are runtime implementation details; Company UI owns every visible surface.
- A recognizable stock NiceGUI/Quasar appearance is a release-blocking defect.
- Never use `ui.notify`, `ui.menu_item` or raw `ui.icon` in canonical Company UI integrations.
- Complex Quasar controls are allowed only inside an approved Company wrapper with a complete normalization layer.
- `DataTable` must render inside the Company AG Grid theme; never rely on AG Grid defaults.
- Every `var(--cui-*)` reference must resolve to a declared Company token.
- The live browser stock-leak audit is mandatory before Production Gold promotion.

## v1.4 Mac live-certification law

The framework includes a 22-route real NiceGUI reference laboratory. Before claiming local visual certification, run `company-ui-mac-certify`, manually review its screenshots, explicitly approve them with `company-ui-mac-approve-baseline`, then rerun certification with the approved baseline. The live browser stock-leak count must remain zero. Static/offline success alone is not visual certification.

## v1.5 design reconstruction laws

- Historical v1.5 geometry remains compatible, but new work must obey `DESIGN_CONSTITUTION_V1_6.md`.
- Use Company layout/composition primitives instead of ad-hoc margins, gaps, radii or page offsets.
- Visible rounded rectangles are limited to control (10px), surface (14px), overlay (18px), plus true pill semantics.
- Density must use the framework geometry tokens; do not implement app-specific compact/dense CSS.
- The shell owns header/sidebar/main offsets, title/subtitle, greeting, settings and user actions.
- Analytical charts use Company chart wrappers; wafer/spatial views use the purpose-built Company spatial renderers.
- `company-ui doctor`, `company-ui lab` and `company-ui certify` are the primary live-environment commands. Linux is the primary work-environment target.
- Browser geometry violations and stock-framework visual leakage are release blockers.

## v1.6 rendered-product hardening laws

- A component is complete only when it renders, aligns, spaces **and behaves** correctly in the browser.
- Read `DESIGN_CONSTITUTION_V1_6.md`; it supersedes v1.5 for new application work.
- The outer application canvas always spans the entire width available beside the desktop sidebar; do not introduce outer `max-width` or asymmetric page margins.
- Reading-width constraints belong to `ContentColumn`/inner content, never the outer `.cui-page`.
- The shell owns application title, subordinate page title, one desktop collapse control, responsive navigation and the frozen support/VOC footer.
- Select/combobox behavior must preserve NiceGUI's native option model; do not add low-level Quasar choice props unless the framework contract explicitly requires them.
- Visible overlay actions must be functional and viewport-contained. Analytical drawers must not dismiss during normal internal interaction.
- DataTable density/row changes should preserve AG Grid's fast path and avoid full remounts where possible.
- Analytical charts must expose real zoom where useful; semiconductor spatial signatures should prefer Company-owned custom renderers.
- Live certification geometry/behavior failures are release blockers, including canvas-width mismatch, asymmetric gutters, insufficient gaps, off-screen overlays, broken field append geometry, dialog misalignment and nonfunctional tested interactions.
- Manual `company-ui lab` must not require Chrome/Chromium; browser discovery gates `company-ui certify` only.


## RUNTIME COMPATIBILITY LAW — v1.7.2
- The supported runtime is exactly `nicegui==3.15.0`.
- Never assume a NiceGUI method from Quasar naming or another NiceGUI release.
- `company-ui runtime-contract` must pass against the installed runtime.
- `company-ui runtime-smoke` must pass all 22 live routes before setup or release is considered successful.
- Synthetic component construction is not runtime certification.


## v1.7 overlay architecture law
- Use the canonical `OverlayLayer` ordering; never solve overlay conflicts with arbitrary local z-index values.
- Canonical Company integrations must use `Tooltip(...).attach(...)`, never raw `.tooltip(...)`.
- Dismissible dialogs/drawers must not be forced `persistent`; non-dismissible semantics must be explicit.
- Close, cancel, confirm, destructive confirmation, X and Escape behavior are release contracts, not optional polish.
- Table/chart/image toolbars remain local-layer controls and must never render above popovers or modals.
- Toasts require Company-owned close/lifetime behavior and must not fall back to stock `ui.notify`.

## DATATABLE PLATFORM LAW — v1.7 Phase 4
- Keep AG Grid as the virtualization engine; Company UI owns visible search/tool/view/action anatomy.
- Never call `element.update()` for normal DataTable search, density, refresh, row replacement, server replacement, or rollback paths.
- Table density is exactly 44/38/34 px (Comfortable/Compact/Dense); do not introduce local row-height variants.
- Quick filter and density changes must preserve the AG Grid root and stay within the browser certification budgets.
- Saved views and column controls must remain mutually synchronized.

## ANALYTICAL VISUALIZATION LAW — v1.7 Phase 5
- Applicable analytical charts must support discoverable direct manipulation; never hide essential axis control behind an undocumented modifier gesture.
- Company UI owns visible heatmap scale/legend anatomy. ECharts may perform mapping but must not float uncontrolled visualMap UI over the plot.
- Semiconductor spatial geometry must be rendered/clipped by Company-owned SVG geometry; die/cell content may never escape the visible wafer/grid boundary.
- Prefer a purpose-built Company engineering renderer when a generic chart obscures wafer, chamber, commonality, or RCA semantics.

## v1.7 PHASE 6 — CONTENT / WORKFLOW / RCA LAW
- Workflow progress markers use a dedicated rail; connectors never participate in marker/text centering geometry.
- Image evidence must be real/testable in the certification lab and expose observable zoom/pan/fit state.
- RCA identity surfaces must retain investigation orientation: ID/hypothesis, owner, stage and freshness remain visible via `InvestigationContextBar`.
- Engineering metadata cards own strict containment. Inner property cells may wrap/reflow but may never escape the outer rounded surface.
- Browser certification must exercise image zoom, pan and fit and measure workflow/RCA containment; presence alone is insufficient.

## V1.7 PHASE 7 — CANONICAL REFERENCE APPLICATION LAW
- The ten canonical patterns are production composition references, not lab component galleries.
- Reference routes must not render the Theme/Density/Motion certification toolbar above product content.
- Use the governed 12-column PatternPage grid and `PatternSurface`; do not introduce local page-width, grid-area, gap, radius or sidebar CSS.
- Dashboard/Explorer/Monitoring use an 8/4 analytical split; Master/Detail 7/5; Search/Settings 3/9; Wizard centered 8 columns; Analysis 8/4 workspace/inspector.
- Below the tablet breakpoint every semantic pattern slot collapses to a single full-width ordered column.
- Reference-app visible actions must exercise real product surfaces; toast-only placeholders are not acceptable for primary CRUD, search, wizard, comparison or analysis flows.

## V1.7.2 RELEASE FREEZE LAW
- Company UI 1.7.2 is the frozen output of the v1.7 design-revamp program; Phase 8 adds certification/package evidence, not new product behavior.
- Production external dependencies are defined only by `requirements.txt` and resolve through the company-approved Python index. Never add a public-PyPI fallback or silently vendor NiceGUI.
- Browser-certification dependencies belong only in `requirements-certification.txt` / the certification extra.
- A source/unit-test pass is not target runtime certification. `company-ui runtime-contract` and the real 22-route `company-ui runtime-smoke` must pass in the installed company environment.
- A runtime smoke pass is not rendered-product certification. The supported-browser geometry/interaction matrix and explicit human screenshot-baseline approval remain separate required gates.
- Do not bypass Company primitives with route-local CSS, raw Quasar visual anatomy, or ad-hoc z-index/layout rules.
## V1.7.2 SETUP GATE LAW
- `setup.sh` validates production runtime only: Playwright/Pillow are certification-only and MUST NOT fail setup.
- Setup MUST NOT require port 8080 because `runtime-smoke` selects an ephemeral free port.
- `run_lab.sh` may require its configured lab port because it binds that port.
- Full browser certification remains strict and requires Playwright 1.62.0, Pillow 12.3.0, browser discovery, and a free certification port.



## V1.7.3 CONTRACT & EVIDENCE HARDENING LAW
- v1.7.3 inherits all established v1.7.2 product/runtime contracts; it does not authorize a redesign.
- Root machine-readable authority copies must be semantically identical to their packaged counterparts.
- Historical certification evidence must be explicitly historical; generic current-looking evidence must never imply target certification before it is executed.
- Screenshot-backed fixes must use the v1.6 radius families: control 10px, surface 14px, overlay 18px (through tokens).
- Structural browser checks are insufficient where the defect intent is contrast, geometry, hierarchy, continuity, or containment; certification must measure the intent directly.
