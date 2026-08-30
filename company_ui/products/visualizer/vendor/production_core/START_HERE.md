# Visualizer 97.1 Approval Package

**Evidence-backed score:** **97.1 / 100**  
**Previous authoritative baseline:** 77.0 / 100  
**Approval threshold:** 95+ — **passed**

## Phone review — recommended

1. Put this folder on the computer that your phone can reach over the same network.
2. On macOS, double-click `START_PHONE_PREVIEW.command`.
   - Or from Terminal: `./START_PHONE_PREVIEW.sh`
   - Or: `python3 PHONE_PREVIEW_SERVER.py`
3. The launcher prints two URLs. Open the **PHONE** URL on your phone.
4. Review these four surfaces in order:
   - **248 Gallery** — all 248 named elements across all 17 canonical engines.
   - **Dynamic Grid** — change slide size, rows, columns and gap; this is the template-independent middle-region layout compiler.
   - **100k Grid** — real 100,000-row retained-DOM data grid with typed sort/filter and keyboard navigation.
   - **PPT Region** — simulated insertion into the safe middle section while preserving the surrounding work template.
5. Send approval or screenshots/feedback of anything you want changed.

## Immediate desktop review

`APPROVAL_PREVIEW_STANDALONE.html` is a fully bundled HTML preview. If local-file pages are blocked by corporate browser policy, use the launcher above instead; it serves the exact same file over local HTTP.

## Evidence to inspect

- `qa/FINAL_95PLUS_AUDIT.md` — 77 → 97.1 audit delta and weighted dimensions.
- `qa/FINAL_95PLUS_SCORE.json` — machine-readable score.
- `qa/FINAL_248_REAUDIT.csv` / `.json` — all 248 element rows.
- `qa/release_suite.json` — 27/27 production release gates.
- `qa/release_248_browser.json` — desktop/tablet/phone 248-element regression.
- `qa/performance_200.json` — retained editor performance.
- `qa/property_fuzz.json` — deterministic 12,500-case corpus.
- `qa/diagram_connector_benchmark.json` — 100-node/90-edge Golden Connector v5 stress.
- `qa/ppt_middle_region_proof.pptx` — editable PowerPoint middle-region proof.
- `qa/ppt_template_adapter.json` — original template preservation evidence.

## PowerPoint architecture

No sanitized corporate PPTX is required for the core architecture. At work runtime, the adapter treats the existing company deck/template as an external container, detects or receives the usable middle rectangle, compiles the normalized Dynamic Grid into that region, and preserves the surrounding template objects. The proof deck in `qa/` demonstrates this using native editable chart/table/shapes.

## Scope note

97.1 certifies the internally controllable Visualizer production core and approval experience against the original 12 weighted audit dimensions. It does not claim certification of an unavailable external Golden NiceGUI shell. Exact confidential corporate-template appearance is intentionally handled at runtime by the template-independent middle-region adapter instead of being hard-coded.
