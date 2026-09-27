# Verification and release evidence

See `evidence/test-and-release-summary.json` for the structured result and `evidence/native-release/` for native release receipts.

- Focused CHG-285 / CHG-254 / CHG-277 / Chart Studio pytest: 20 passed.
- Full clean pytest: PASS; exact collected count 1233; zero failures/errors.
- Repository-native GitHub Quality: completed/success, all nine jobs green at candidate head. Run: https://github.com/kimhw8084/visembler/actions/runs/36330158205
- Maintained native release: `PASS_LOCAL_INTERNAL_PILOT`; checks `PASS`; all required gates passed and no remaining release validation. Managed target status remains PENDING by design. The receipt includes repository contracts, CHG-181 authoring/composition/reuse, CHG-208 remap diagnostics, Chart Studio, lifecycle/history, performance, accessibility/authoring, source stability and frozen connector results.
- CHG-180 native acceptance: 2/2 cases PASS on candidate. Its headless PPTX rasterizer is marked MISSING because LibreOffice/soffice is unavailable; no Office render claim is made.
- CHG-209 Visual Director/reuse matrix: base and candidate each PASS all six scenes; candidate includes exercised user controls.
- CHG-206 visible-text unit tests pass in full pytest. Its original acceptance executable is branch/parent-bound to its historical candidate and requires a trusted LibreOffice+Poppler renderer; it was not bypassed or represented as a CHG-285 run.
- CHG-207/253 repository regression tests pass in full pytest. Their maintained native acceptance scripts reject execution on a different parent/branch; original branch-bound certification was not bypassed.
- `python -m company_ui.validate company_ui/products/visualizer --format json`: exact-base and candidate counts are identical (57 errors and 1204 warnings; errors AI004=6 and AI005=51 all in `page.py`). Candidate adds none.

No browser-responsive UI or frozen adapter files were changed. No main update, PR, managed target certification, or CHG-173 final outcome is part of this FIX.
