# CHG-253 R1 — Sparse narrow reading evidence

This carrier documents the shared Preview content-fit repair on candidate `3777fa759c96355888ea3a39715693ab4f306667`. It is prepared for independent Project OS audit; no main integration or CHG-254 work is included.

## Review order

1. `identity-base-candidate.json` — request, exact base/current main, candidate, and R3 root receipt.
2. `reader/source-authority.json` — root cause and the shared sizing authority.
3. `screenshots/before/r3-reading-390.png` and `screenshots/candidate/sparse-390-full-page.png` — R3 clipped view and candidate equivalent-shape reading at 390px. Candidate 320px and 360px scenes are alongside them.
4. `diagnostics/dom-geometry-accessibility-diagnostics.json` and `diagnostics/breakpoint-matrix.json` — body/content overflow, viewport geometry, status/context visibility, and continuity at 320, 359–361, 389–391, and 1440px.
5. `diagnostics/table-keyboard-touch-reachability.json` — 3-row vertical reachability, retained horizontal cue, keyboard, wheel, touch, focus, and ARIA results.
6. `diagnostics/source-data-geometry-immutability.json` — unchanged preview model, fixtures, mappings, Visual Director and manual-geometry sources.
7. `tests/focused-test-summary.json`, `regression/chg181-authoring-composition-reuse.json`, `regression/chg207-narrow-reading.json`, `regression/chg209-visual-director-reversibility.json`, and `regression/chg206-visible-powerpoint-text.json`.
8. `release/report.json`, `release/binding.json`, and `release/raw-junit/full-tests.xml` — maintained native verifier output for this exact candidate.

## Candidate result

At 390px the decision card body is `163/163px` and the risk statement/detail body is `156/156px`; the metric card body is `75/75px`. All 3 table rows fit vertically (`135/135px` frame) while horizontal overflow stays discoverable (`586/344px`). ArrowRight/End/ArrowLeft/Home, wheel scroll and touch swipe were exercised. The same content-fit assertions pass at 320px and nearby widths; no heading collisions or document/body horizontal spill were measured.

The 390px candidate screenshot uses renamed equivalent-shape content. It verifies the policy is shape/engine based, not keyed to the Bridge title or copy. The detailed 390px layer geometry is in `diagnostics/dom-geometry-accessibility-diagnostics.json`; `diagnostics/breakpoint-matrix.json` has compact browser measurements for every tested width.
