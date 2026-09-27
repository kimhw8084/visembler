# CHG-173 R6 evidence index

**Outcome:** NO_GO, awaiting independent audit. Six populated report authoring runs and the reuse challenge completed. Verification stopped when final RCA Preview showed Process Flow connectors crossing node labels (VIS-R6-001). No Product/source change was made.

## Identity and release

- `identity/source-and-run.json` records exact source, tree, branch, target, runtime and Fabric job.
- `identity/native-release-summary.json` records `PASS_LOCAL_INTERNAL_PILOT`; complete retained outputs are in `native-release/`. Managed CHG-21 certification remains separate and pending.

## Whole-report benchmark

- `benchmark/brief.md` describes A–F and the two fresh holdouts.
- `benchmark/reports/` contains saved report models and data.
- `benchmark/actions/` contains deterministic action logs, including the final supported B label edit.
- `screenshots/` contains populated Preview captures at 1440 and 390, narrow captures and contact sheets. B's 320 capture is explicitly historical, before the final concise-label edit.
- `visual-director/review.md` is six-report task-grounded triage; detailed outcome review stopped at B.
- `benchmark/responsive/` retains measured diagnostics and the FAIL receipt.

## Reuse and lifecycle

`benchmark/reuse/comparison-summary.json` compares source-to-remix with a blank build for the same East/West revenue target. Reuse required 43 actions versus 79, avoided nine component inserts and six composition setup steps, and avoided twelve context switches. It opened two more modals. Raw authoring, saved reports and conflict receipts are included.

## Exports and blocked proof

- `exports/pptx/` contains six editable exports and reuse exports; `exports/svg/` contains A–F SVGs.
- `pptx/inspection/chart-studio-label-cases.json` records fresh authored/automatic Chart Studio state; XML proof is BLOCKED.
- `pptx/roundtrip/A-F-import-receipt.json` marks canonical import/round-trip BLOCKED by the stop rule.
- `exports/provenance/preview-and-export.json` distinguishes in-app Preview from an exported PPTX render.
- `exports/boxplot/statistics-from-report-model.json` is model-only; PPTX geometry validation is blocked.

## Finding and integrity

- `findings/findings-register.json` contains the single confirmed P1.
- `decision/final-decision.json` records the producer self-verdict; independent review owns any final verdict.
- `manifest/sha256.json` plus its sidecar hash the package.
- `.codex-fabric/audit.json` is the canonical Fabric receipt.
