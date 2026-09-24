# Visembler CHG-181 R2 evidence

**Candidate:** `b3ecb221986e51a712fea82adf5339a32d6b72b7` (`d36220e2cf7bd93116765b4f0f1bba19ed682747`)  
**Source branch:** `fix/visembler-chg181-section-composition-r2`  
**Request / operation:** `CHG-181-r2` / `FIX`  
**Runtime:** Python 3.11.7 · NiceGUI 3.15.0 · Chromium 151.0.7922.34 · native host

## R1 versus R2 complete-report review

Start with the five-page [whole-report comparison PDF](whole-report/comparison/visembler-r1-vs-r2-complete-reports.pdf) and [R2 whole-report contact sheet](whole-report/r2/whole-report-contact-sheet.png). The comparison places each original R1 Preview beside the same genre from the final R2 candidate. Screenshots are untouched native captures. R1 images are preserved unchanged and their hashes are in [the baseline hash receipt](whole-report/comparison/r1-baseline-hashes.json). The original R1 and R2 review contact sheets/PDFs remain available alongside this comparison.

## Final five reports

Each report folder contains full editor and Preview captures, narrow/mobile states, the report observation receipt, and actual PPTX and SVG exports.

| Genre | Evidence |
|---|---|
| Executive Business Review | [report folder](whole-report/r2/reports/executive-business-review/) |
| Experiment Decision | [report folder](whole-report/r2/reports/experiment-decision/) |
| Semiconductor RCA | [report folder](whole-report/r2/reports/semiconductor-rca/) |
| Dense Technical Status / Operating Review | [report folder](whole-report/r2/reports/technical-status-review/) |
| Independent Order / Returns holdout | [report folder](whole-report/r2/reports/holdout-order-returns/) |

[Browser, geometry, mobile and accessibility diagnostics](whole-report/r2/browser-accessibility-diagnostics.json) include zero browser errors, per-report preflight results, overlap/clipping data and narrow reading measurements. The candidate-bound [CHG-181 acceptance receipt](whole-report/r2/chg181-native-acceptance.json) records all five genres and 15 generated reports.

## Remap and reuse

The final candidate retains R1 leverage: follow-up assembly used **43 actions, 5 context switches, 0 manual component inserts**; blank rebuild used **79 actions, 17 context switches, 9 inserts, 7 repeated composition setup steps**. The [action comparison](whole-report/r2/reuse-remap/reuse-vs-blank-action-comparison.json), [compatibility/history receipt](whole-report/r2/reuse-remap/remap-compatibility-history.json), and full dialog/editor/Preview evidence cover shared-slot remap, ambiguous and incompatible mappings, source-data-copy mode, destination dataset identity, immutability, undo/redo, reload, history and conflict recovery.

Actual reuse, blank-build, section-reuse, and remap images/exports are in [reuse-remap evidence](whole-report/r2/reuse-remap/).

## Composition and remap documentation

The [composition grammar and remap behavior contract](documentation/VISSEMBLER_CHG181_COMPOSITION_AND_REUSE.md) describes deterministic section patterns, feature/support hierarchy, bounded density and gaps, user overrides, reversible Smart composition, and shared-slot field presentation.

## Release and maintained gates

- [Fresh native release report and evidence](evidence/native-release/report/report.json): `PASS_LOCAL_INTERNAL_PILOT`, all maintained checks `PASS`, no remaining checks.
- [CHG-179 semantic parity receipt](evidence/maintained-gates/chg179-semantic-parity/chg179-semantic-parity.json): PASS.
- [CHG-180 export/PPTX receipt](evidence/maintained-gates/chg180-export-pptx/acceptance-receipt.json): PASS; actual editable exports included. Its optional headless PPTX rasterizer is marked missing because LibreOffice/`soffice` is unavailable.
- [Focused composition/reuse tests](evidence/focused-tests.json): 21 passed. [Company UI validation](evidence/company-ui-validator.json): 270 files, zero errors, 136 warnings.

## Source chain and publication status

The source chain preserves the exact base and both R1 commits, then adds three R2 commits: `aaf9ab371c19cffb726a2826047bd22b98bf8544`, `5ae930a9d42c51f8de5daacffef0b96c68111dc0`, `b3ecb221986e51a712fea82adf5339a32d6b72b7`. See [commit chain](source/commit-chain.txt), [changed files](source/changed-files.json), and [source patch](source/r2.patch).

This Git-first carrier is available at `refs/heads/project-os-artifacts/visembler/CHG-181-r2` because Artifact Bridge is not available. The required Fabric audit remains **not published**: this runtime exposes no Fabric audit publisher or evidence workflow. The exact status and endpoint probe are recorded in [identity](identity.json) and [the Fabric endpoint probe](evidence/fabric-audit-endpoint-probe.json); local receipts are not represented as Fabric evidence. No CHG-173 GO, company-managed target certification, or Production Gold claim is made.

`visembler-chg181-r2.zip` is a deterministic ZIP of this package payload (excluding itself and its detached hash sidecar). `MANIFEST.json` lists the path, size, and SHA-256 for each payload file; its detached SHA-256 and the ZIP hash are provided beside it.
