# Company UI 3.0.0a1 — Source-Complete Application Platform Alpha

Company UI is a Company-owned NiceGUI application platform for internal engineering, data, monitoring and RCA products. `3.0.0a1` is the first v3 architecture line: it keeps the certified v2 rendering/design contracts as the compatibility floor while adding governed application runtime, data, workspace, interaction and extension layers above them.

## Release status

`3.0.0a1` is **source-complete alpha**, not stable `3.0.0`. Source-level non-regression is green across the complete inherited estate; live target/runtime/browser/human certification remains deliberately PENDING because NiceGUI and the supported browser matrix are unavailable in this build sandbox.

The authoritative parent is frozen `2.0.0rc5`. Existing v2 routes do **not** need to migrate to the v3 workspace/runtime model, and the established renderer, shell, control anatomy, DataTable behavior, chart stack, geometry and accessibility contracts remain the compatibility floor.

## What makes v3 a major architecture

- **Application runtime kernel** — `ApplicationRuntime` and `WorkspaceRuntime` own lifecycle scopes, typed state, commands, diagnostics and workspace resources.
- **Governed state + interaction history** — namespaced typed keys, atomic transactions, defensive reads, revision history, exact rollback, transaction-level undo/redo and stale-redo invalidation.
- **Unified data engine** — immutable datasets and shared data sessions drive table-like rows, grouped chart series and KPIs from one semantic filter authority.
- **Large-data query hardening** — exact row identity plus lazy equality/IN indexes accelerate repeated cross-filtering without changing data semantics.
- **Adaptive workspace engine** — deterministic collision-free panel placement, constrained move/resize, responsive derivation, compaction and exact snapshot restoration.
- **Whole-workspace persistence** — application/workspace snapshots serialize runtime state, panel geometry and shared data-session filters to JSON and rehydrate deterministically.
- **Semantic visualization planning** — visualization intent is mapped onto the existing certified chart renderers; v3 does not create an ungoverned second chart stack.
- **Governed extension API** — explicit registrations for components, data sources, commands, visualizations and workspace panels replace ad-hoc patching.
- **Runtime diagnostics** — lifecycle/task, command-performance, workspace-panel and extension ownership are inspectable as platform state.

## Zero-regression UI/UX rule

V3 capability is additive and opt-in. Existing v2 pages continue through the established renderer and design laws unless a page is explicitly migrated to a v3 workspace. A new v3 primitive must preserve the established visual constitution or provide a tested, measurably stronger contract; local route CSS, raw visual anatomy forks and ungoverned z-index/layout fixes remain forbidden.

RC4/RC5 performance and correctness fixes remain authoritative: one-primary-grid DataTable mounting, immediate-scroll behavior, lifecycle-scoped cleanup, async race/cancellation contracts, schema-aware table persistence, exact typed row identity, overlay focus/Escape/scroll ownership, stale-last-good refresh behavior, revision-owned editable saves, hidden-chart update coalescing, accessibility alternatives and pathological-data regressions are retained.

## Runtime contract

Production dependency:

```text
nicegui==3.15.0
```

Optional browser-certification dependencies:

```text
playwright==1.62.0
Pillow==12.3.0
```

Setup validates production runtime only and must not require browser-certification packages or a free fixed port. `run_lab` owns its configured lab port. Full browser certification remains strict.

## 3.0.0a1 source evidence

- Python/source regression estate: **670/670 PASS**
- governance: **PASS — 0 errors / 0 warnings**
- static/source certification: **12 PASS / 1 expected environment warning / 0 FAIL / 0 SKIP**
- public visual integrations mapped to the live lab: **183/183**
- public root API entries: **809**
- canonical live routes: **22**
- wheel RECORD verification: **391/391 hashes, 0 mismatches**
- isolated no-dependency wheel import: **PASS**
- expected warning: NiceGUI is unavailable in this build sandbox; target runtime/browser/human visual certification is therefore PENDING rather than inferred.

## Stable 3.0.0 promotion blockers

1. Install the v3 wheel in a supported target/company environment and pass the exact NiceGUI 3.15.0 runtime contract.
2. Pass real server smoke for all 22 canonical routes with no runtime error patterns.
3. Pass supported Chrome/Edge certification across the canonical responsive matrix, including console, geometry, interaction, overlay, table, chart and screenshot-regression gates.
4. Review and approve the hash-locked human visual baseline.
5. Capture required macOS/Linux company-target evidence and regenerate the stable `3.0.0` manifest/SBOM/provenance against the final wheel.

See `docs/V3_APPLICATION_PLATFORM.md`, `docs/V3_MIGRATION_GUIDE.md`, `PHASE_46_V300A1_APPLICATION_PLATFORM_REPORT.json`, `TEST_REPORT.json`, `CERTIFICATION_REPORT.json` and `LIVE_CERTIFICATION_READINESS.json`.
