# CHG-254 R1 — PowerPoint chart semantics

This carrier binds the fix and its evidence to candidate commit `26abd6e30a348f34bdb4d72caf3c4822e76e7dcb` (`ab98bfbd27bcf7da147e15f70c6c50ef27d8bae4`). It addresses only the integrated Visembler PowerPoint export projection; canonical Chart Studio authoring/rendering authority is unchanged.

## Read first

- [`../identity.json`](../identity.json) — exact request/base/candidate, branch, source-authority identity, and managed-target status.
- [`../exports/reproduction/pre-fix/reproduction-receipt.json`](../exports/reproduction/pre-fix/reproduction-receipt.json) and package inspection — exact-base reproduction before mutation.
- [`../exports/source-authority-and-projection.json`](../exports/source-authority-and-projection.json) — R3 B/C source mappings and Chart Studio authority projected into actual PPTX package facts, plus renamed multi-series holdout.
- [`../exports/compositions/B-semiconductor-rca/package-inspection.json`](../exports/compositions/B-semiconductor-rca/package-inspection.json) and [`../exports/compositions/C-experiment-decision/package-inspection.json`](../exports/compositions/C-experiment-decision/package-inspection.json) — chart XML family, `c:ser` names/count, category/value caches, axis domain, legend, editable Box Plot primitives, and semantic IDs. Raw chart XML is alongside each inspection.
- [`../exports/boxplot-statistics.json`](../exports/boxplot-statistics.json) and [`../exports/round-trip.json`](../exports/round-trip.json) — quartile/whisker facts and exact canonical report recovery.
- [`../exports/rendered-preview-provenance.json`](../exports/rendered-preview-provenance.json) — reviewed Quick Look previews; PowerPoint/LibreOffice were unavailable, so previews are clearly labeled and XML remains decisive.
- [`../tests/test-release-receipt.json`](../tests/test-release-receipt.json) — clean full pytest, focused CHG regressions, validator and native release result. Raw JUnit files are included.
- [`../native-release/report.json`](../native-release/report.json) and [`../native-release/candidate-binding.json`](../native-release/candidate-binding.json) — maintained native release binding and report.

## Acceptance facts

- Experiment weekly chart is a native editable line chart with W1–W4 once, Control then Treatment as separate series, aligned values, visible legend, and y-domain 7.91–9.89.
- Experiment Box Plot is editable PowerPoint vector geometry with distinct Control/Treatment quartile boxes, observed min/max whiskers, median marks, and no chart XML surrogate.
- Semiconductor RCA SPC/time chart remains an editable line/time chart with 93.865–99.035 domain. Reference/Affected is an editable box comparison and has no false line chart.
- An unrelated North/South holdout remains two distinct series. Sparse cells are gaps; explicit axis bounds and zero-baseline bars are tested; unsupported advanced families fail without governed statistical results.
- Candidate pytest: 1223 passed, no failures/errors. Native release: `PASS_LOCAL_INTERNAL_PILOT with no remaining local gates. Managed target certification remains pending under CHG-21.
