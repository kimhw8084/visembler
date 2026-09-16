# Visembler CHG-40 R2 verification evidence

This is an evidence-only verification package for exact integrated main `4701410c79d9803b0d156d6e0b2a568992387dbc`. The CHG-70 accepted head `afd2b60b89e27ecd90f33949bd85d9181d4b3a05` is in its ancestry. No product, runtime, test, or release source was changed; all new artifacts are under this directory.

## Baseline and comparable coverage

R1 authority is the evidence-only branch `verify/visembler-chg40-ui-perfection-benchmark-r1` at `5ee3ffae1d0ed5a4844510a8807c3fef3ea1491f`, located at `evidence/ui-perfection/CHG-40-r1/`. Its manifest, diagnostics, findings, performance, contact sheet, state inventory, and commands were read before execution. All 103 R1 state IDs are retained in `state-matrix.json` and mapped in `manifest.json` as re-executed comparable. Sixteen supplemental browser-audit states and six reserved holdouts are additional R2 coverage.

## Commands executed

Commands were run with the repository RTK wrapper:

- `rtk python scripts/verify_release.py --host-mode native --output /tmp/visembler-chg40-r2-release`
- `rtk python -m company_ui.validate .`
- `rtk company-ui runtime-contract` (the installed command is `company-ui runtime-contract`)
- `rtk company-ui runtime-smoke`
- `rtk python scripts/release_checks/run_final_visual_remediation_acceptance.py --output /tmp/visembler-chg40-r2-final-remediation`
- `rtk python scripts/release_checks/run_final_visual_cleanup_acceptance.py --output /tmp/visembler-chg40-r2-final-cleanup`
- `rtk python scripts/release_checks/run_diagram_studio_acceptance.py --output /tmp/visembler-chg40-r2-diagram`
- `rtk python scripts/release_checks/run_stage_d_benchmark.py --output /tmp/visembler-chg40-r2-stage-d`
- `rtk python commands-r2-browser-audit.py` (captured as `commands-r2-browser-audit.py.txt`; native Playwright audit, 16 states)
- `rtk python commands-r2-editor-repeat.py` (5 warmups, 7 measured iterations, 2 cold samples; counts 1/20/100)
- `rtk python company capacity equivalent` (three raw repetitions at 10/100/1000 reports; raw JSON retained)
- `rtk python commands-r2-memory.py` (noninvasive psutil RSS)
- `rtk python commands-r2-datafirst-trace.py` (fixture → profile → normalized model → renderer DOM)
- `rtk python commands-r2-holdout.py` (six holdouts executed after comparison)

The exact command snapshots and maintained raw receipts are retained beside the artifacts. `performance.json` preserves raw R2 editor/capacity/memory observations and matching deltas against R1. The quick-add contrast probe is repeated at 1440px and 390px in both themes; its R1/R2 raw receipts are in `browser-audit/quickadd-narrow-r1.json` and `browser-audit/quickadd-narrow-r2.json`.

## Findings and qualification

R1 malformed SVG viewBox is closed: R2 VR055 passes and the supplemental audit found zero malformed viewBoxes/browser events. R1 editor/reportbar contrast is closed in the comparable bounded sample: 9 desktop and 3 narrow R1 failures became 0 and 0 in R2. The report hub remains an objective contrast finding: dark KPI thumbnail text is 1.089:1 against its white thumbnail fill and Duplicate is 3.063:1; the light report-hub Duplicate action is also 3.063:1. Data First Process Health is resolved as a verifier defect: four typed rows and four rendered fab-matrix cells exist, while the maintained wafer-die selector counts zero. Generic WaferFab utilization remains a fixture/probe coverage issue. See `findings.json` and `regression-comparison.json`.

The package therefore does **not** award UI-excellence GO. Classification is **objective qualification failed; independent visual review pending**. Review hierarchy, salience, grouping, whitespace, typography, density, affordance, scanning, recovery clarity, responsive prioritization, target ergonomics, motion restraint, expert efficiency, and perceived craftsmanship from the full-resolution screenshots still require independent review.

## Accessibility evidence

- Light/dark, desktop, narrow/mobile, keyboard/focus, semantic names, reduced motion, and page overflow were exercised in the browser.
- Forced colors used standards-defined Playwright Chromium `forced_colors=active` browser emulation (`matchMedia('(forced-colors: active)') == true`), not native macOS high contrast.
- 200% reflow used CDP `Emulation.setDeviceMetricsOverride` at effective CSS viewport 720x500. This changes layout/reflow conditions; it is labeled a 200% equivalent because headless browser UI zoom did not change CSS layout.
- Report Hub dark was browser DOM theme emulation (`html[data-theme=dark]`) because the shell has no visible theme switch.

## Retrieval

- `manifest.json`, `state-matrix.json`: exact source/environment and complete R1↔R2 mapping.
- `findings.json`, `diagnostics.json`, `regression-comparison.json`: objective results and limitations.
- `performance.json`: raw R2 observations, R1 matching samples, deltas, variance notes, and RSS.
- `screenshots/`: 125 full decisive state PNGs.
- `review-pack/`: curated full-resolution PNGs grouped by workflow/state.
- `contact-sheet.html` / `contact-sheet.png`: readable visual index.
- `data-first/`: fixture and model-to-renderer trace.
- `holdout/`: reserved scenario results and screenshots.

## Limitations

Native OS high contrast, native browser UI zoom, complete WCAG conformance, and subjective visual quality are not claimed. RSS excludes the browser renderer process. Capacity/editor timings are descriptive observations from fresh native processes; no SLA or causal performance claim is made. Evidence remains repository artifact only and is not an integration candidate.
