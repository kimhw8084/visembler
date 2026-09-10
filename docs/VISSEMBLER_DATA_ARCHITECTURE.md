# Visembler data architecture

Visembler uses two deliberate data paths.

## Inline report data

Small, portable datasets remain in the canonical report JSON. This preserves
editable JSON exchange, existing reports, copy/paste, history, and the current
52-element contract (the original 39-element set remains backward-compatible).

## Bound dataset resources

Recurring or larger datasets can be promoted from the Data Dock into the
file-backed resource store under the configured Visualizer data directory:

```text
<data-dir>/
  reports/
  _datasets/
    catalog.json
    <dataset-id>/r1.json
    <dataset-id>/r2.json
```

The report stores a governed reference (`resource_id` plus the active
revision) and only a bounded preview. The row source is immutable per
revision, written atomically with fsync, and queried through the existing
`company_ui.data_engine` `Dataset`/`DataSession` primitives. A failed report
commit cannot make a new resource revision the active report binding.

Startup reconciliation blocks an active resource whose current revision is
missing and reports untracked revision directories instead of guessing
ownership. Tombstoned resources may be garbage-collected only when the caller
supplies references from active, trash, and historical reports; tombstones
remain to prevent dataset-ID reuse.

The resource identity is not an access grant. Every read, query, refresh, and
delete goes through `ScopedDatasetRepository`, which first checks the report's
server-side capability and reference. Direct dataset IDs therefore do not
provide enumeration or cross-report access.

## Refresh and filters

Refreshing a bound dataset creates the next immutable resource revision and
commits the report's reference change as one report operation. If that report
commit is rejected, the previous report binding remains authoritative and the
new revision is available only for deterministic operator recovery.

Chart selection on a bound dataset sends a report-scoped filter to the server
`DataSession`. The resulting rows are used as a transient projection for all
compatible visuals; canonical source rows are not mutated. Reset clears the
session filters. The filter projection is intentionally transient and is not
persisted in report history.

## Catalog and asset lookup

Governance summaries contain lightweight dataset and asset references. Report
Hub search/sort and protected asset authorization use those summaries; full
report hydration is reserved for opening a report, rendering a selected
thumbnail, or inspecting history. The report JSON and history remain the
canonical sources of truth. Summaries are rebuildable during application
startup.

## Reusable authoring content

Personal reusable sections, saved datasets, and mapping/preset definitions
are stored through the user-preference service. Browser `localStorage` is a
best-effort cache only. A failed browser cache write is surfaced to the
developer console, while the governed server copy remains authoritative.
