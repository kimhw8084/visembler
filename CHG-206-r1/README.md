# CHG-206 R1 PowerPoint visible-text evidence

**Identity:** project `visembler` · request `CHG-206-r1` · operation `FIX` · Fabric job `CF-335e326a4b753e8a2e6d9e08`.

**Source:** `47a988064deac544dfdca360e046a9cb20f5c282` / tree `d36220e2cf7bd93116765b4f0f1bba19ed682747`.

**Candidate:** `7011308605d1d2158849efdbc8aa30a8840cb17e` / tree `d932f22966508ba6fdb630b6f66e1a01818b7b03`, one commit directly on the requested source. The five changed source files are listed in `candidate.json` and `MANIFEST.json`.

## Start here

- `candidate.json` — source/candidate identity, parent and bounded scope.
- `reproduction-root-cause.json` — exact CHG-173 R2 reproduction and XML/pixel cause.
- `visible-text-findings.json` — role-by-role exact-text and pixel-review findings for all five report genres.
- `structural-inspection.json` — editable PPTX text inventory, role metadata, font/color facts, text-frame geometry/margins/wrap/anchor/fit, browser-assigned rectangles, slide bounds, chart/table/spatial structure.
- `renderer-provenance.json` — signed LibreOffice and Poppler paths, hashes, versions, signatures, exact per-report conversion and raster commands.
- `powerpoint-acceptance/acceptance-receipt.json` — complete native export, structural, render, baseline comparison, root-cause and manual pixel-review receipt.
- `checks-summary.json` — maintained gate list and statuses.

## Actual exported bytes and raster review

The real UI action used for every report was `#exportBtn → #exportPptAction (Editable PowerPoint)`. The actual editable PPTX files are in `powerpoint-acceptance/exports/`; the corresponding PDF conversions are in `powerpoint-acceptance/pptx-review/pdf/`; the 144 dpi Poppler images reviewed at full resolution are in `powerpoint-acceptance/pptx-review/rasters/`. Per-report LibreOffice profile state is ephemeral and excluded from the Git carrier/archive; renderer provenance, profile scope and exact commands remain recorded.

Reports: Executive Business Review, Semiconductor RCA, Experiment Decision, Dense Technical Status Review, and the fresh Supply Chain/Capacity holdout. Every generated PPTX has exact expected strings, role metadata and text-frame XML inspected; every report has zero missing/misplaced strings, off-slide shapes, element-boundary errors or overlaps. The Executive Business Review is compared against its exact CHG-173 R2 failing raster in `powerpoint-acceptance/before-after-failing-raster-contact-sheet.png`; original R2 raster files are preserved under `r2-baseline/rasters/` with hashes in `r2-baseline/provenance.json`. The RCA raster was reviewed for Wafer Map, signed Wafer Difference Map and Process Flow fidelity.

## Regression and maintained release checks

- `checks/focused-export-tests.log` — CHG-206 regression plus CHG-179/180 focused Python tests.
- `checks/company-ui-validate.log` — validator result: 272 files, 0 errors, 136 warnings.
- `checks/repository-contracts.json` — manifest count, source and API contracts; PASS.
- `checks/chg179/` — semantic precision/prefix/suffix/unit, negative/zero/missing values and parity receipt.
- `checks/chg180/` — native Process Flow and wafer spatial PowerPoint acceptance.
- `checks/chg181/` — full authoring/composition/reuse acceptance, four genres plus 12 holdout cases.
- `checks/verify-release/report.json` — full `python scripts/verify_release.py --host-mode native` receipt and individual logs/artifacts. Result: `PASS_LOCAL_INTERNAL_PILOT`; company-managed target status remains `PENDING`.

The certification manifest count was updated from 1,197 to 1,202 in its five matching summary fields, because the five focused pytest cases increased collected tests by five. No release gate was weakened or skipped.

## Artifact staging and publication

The session exposes no callable Artifact Bridge application/MCP adapter. The local Fabric CLI exposes `publish-evidence`, but its evidence publisher is terminal-job gated; this job reports `RUNNING` while work is in progress. The exact limitation is recorded in `artifact-bridge-status.json`. The complete deterministic bundle and all decisive individual receipts are preserved here and on `refs/heads/project-os-artifacts/visembler/CHG-206-r1`. The Fabric runtime-owned audit evidence ref is `refs/heads/codex-fabric/evidence/visembler/CHG-206-r1`; terminal publication is handled by the runtime.

## Bundle verification

`MANIFEST.json` inventories SHA-256 and byte size for each evidence file except the manifest/checksum/archive itself. `MANIFEST.json.sha256` covers the manifest. `deterministic-bundle.zip` uses sorted member paths, fixed timestamps and fixed permissions; `deterministic-bundle.zip.sha256` covers the archive.

## Scope

This Change repairs exported report-text rendering (F-EXP-01). CHG-207, CHG-208, CHG-209, CHG-173 final outcome verification and CHG-21 company-managed target certification remain separate and are not claimed.
