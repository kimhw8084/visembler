# CHG-293 R1 independent review carrier

This carrier records the shared Process Flow report-reading FIX for the CHG-173 R6 connector/readability defect. Candidate `a095fa229c657a75a136520089194998377c66eb` is based on exact `main` commit `28d47acbaab8b493044120f6be4c32a225de4143`.

## Review map

- `identity.json`: request, base/candidate/tree identity and unchanged-main/clean-worktree assertions.
- `reproduction/before/`: exact-base whole-report browser reproduction and full screenshots.
- `candidate/`: candidate browser geometry receipt and full-report screenshots.
- `geometry/`: per-connector shaft/arrowhead clearance and text bounds, intersections, breakpoint decisions, and holdout matrix.
- `semantic-save-reload.json`: graph identity, direct editing, canonical Diagram Studio round trip, and native repository reload receipt.
- `source/`: candidate authority snapshots and exact base-to-candidate patch.
- `regressions/`: focused regression JUnit, full pytest JUnit, and test summary.
- `quality/`: maintained native release report, gate summary, checks, archive, and CHG-181 acceptance receipt.
- `MANIFEST.json` and `MANIFEST.sha256`: immutable carrier file inventory and digest sidecar.

## Observed result

The exact-base reproduction measures 2.32 CSS px clearance at 1440, six connector/text intersections at each of 520, 390, and 361 CSS px, and safe single-column clearance at 360 and 320 CSS px. Candidate R6-like geometry has zero text intersections and at least 4 CSS px clearance at 1440, 520, 390, 361, 360, and 320 CSS px. Candidate four-stage holdout also passes at 390; five/six-stage and edge/secondary-label cases deterministically use a safe stacked projection.

The maintained repository-native release is `PASS_LOCAL_INTERNAL_PILOT`; all required local gates pass. CHG-21 managed target certification remains separate and PENDING. This FIX does not claim CHG-173 final outcome, PPTX A–F re-import completion, a main integration, or Production Gold.
