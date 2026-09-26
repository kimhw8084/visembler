# Independent review index — CHG-173 R4

- Request: `CHG-173-r4`, operation `VERIFY`.
- Exact source: `f1a3cd5c5fa4e6eb5f2d51c38555a34f85f5fee3` (tree `ab98bfbd27bcf7da147e15f70c6c50ef27d8bae4`).
- Fabric job: `CF-c5985db500183ce3f3a9e6ef`.
- Six supported-flow reports: A–F; two fresh R4 holdouts: E and F.
- Producer self-verdict: **NO_GO**, based on two bounded findings in `benchmark/findings/findings-register.json`; Project OS / ChatGPT owns the independent verdict.

## Where to review

1. `identity/source-runtime.json` — exact source, runtime, local release status and separate CHG-21 state.
2. `benchmark/brief.md` and `benchmark/report-index.json` — task-specific brief and all report IDs, roles, composition facts, and evidence paths.
3. `benchmark/action-logs/` and `benchmark/reuse/reuse-vs-blank.json` — observed authoring counts and reuse leverage.
4. `benchmark/screenshots/` — full 1440 and 390 captures, required 320/360 captures, and contact sheets.
5. `benchmark/visual-director/review.json` — qualitative per-report task review, without aesthetic scoring.
6. `benchmark/responsive/diagnostics.json` — rendered DOM/geometry summary and image-reader probe.
7. `benchmark/exports/pptx/`, `svg/`, `inspection/`, `package-xml/`, `roundtrip/`, and `quicklook/` — actual exports, OOXML facts, semantic import proof, and preview pixels/provenance.
8. `benchmark/lifecycle/`, `remap/`, and `release/` — lifecycle, conflicts, remap diagnostics, maintained release proof and `release/regression/gate-matrix.json`.
9. `final/outcome-decision.json` — concise producer decision.
10. `manifest.json` and `manifest.sha256` — file hashes and manifest digest.

## Limits and result

Quick Look was the only installed PowerPoint preview renderer; this is not a PowerPoint/LibreOffice or company-target certification. Chart package semantics are independently recorded. Native release status is `PASS_LOCAL_INTERNAL_PILOT`; managed company target certification remains `PENDING` under CHG-21. The maintained full verifier had two transient UI gate failures in earlier attempts; both gates passed in isolated retries and the final full verifier passed every gate. Manual pointer drag/reorder/resize/alignment/group gestures were not independently exercised and are identified as a coverage limitation.
