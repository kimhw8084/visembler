# Visembler CHG-181-r1 — reader index

This Git carrier preserves the bounded local/native recovery evidence for the exact source candidate below. Start with the five completed report reviews, then follow the reuse/remap journey.

## Five complete report reviews

| Report | Full editor | Full Preview | Mobile Preview | PowerPoint | SVG |
|---|---|---|---|---|---|
| Executive Business Review | [editor](whole-report/executive-business-review-editor-desktop-final.png) | [Preview](whole-report/executive-business-review-preview-desktop.png) | [mobile](whole-report/executive-business-review-preview-mobile.png) | [PPTX](whole-report/executive-business-review.pptx) | [SVG](whole-report/executive-business-review.svg) |
| Experiment Decision | [editor](whole-report/experiment-decision-editor-desktop-final.png) | [Preview](whole-report/experiment-decision-preview-desktop.png) | [mobile](whole-report/experiment-decision-preview-mobile.png) | [PPTX](whole-report/experiment-decision.pptx) | [SVG](whole-report/experiment-decision.svg) |
| Holdout Order Returns | [editor](whole-report/holdout-order-returns-editor-desktop.png) | [Preview](whole-report/holdout-order-returns-preview-desktop.png) | [mobile](whole-report/holdout-order-returns-preview-mobile.png) | [PPTX](whole-report/holdout-order-returns.pptx) | [SVG](whole-report/holdout-order-returns.svg) |
| Semiconductor RCA | [editor](whole-report/semiconductor-rca-editor-desktop-final.png) | [Preview](whole-report/semiconductor-rca-preview-desktop.png) | [mobile](whole-report/semiconductor-rca-preview-mobile.png) | [PPTX](whole-report/semiconductor-rca.pptx) | [SVG](whole-report/semiconductor-rca.svg) |
| Technical Status Review | [editor](whole-report/technical-status-review-editor-desktop-final.png) | [Preview](whole-report/technical-status-review-preview-desktop.png) | [mobile](whole-report/technical-status-review-preview-mobile.png) | [PPTX](whole-report/technical-status-review.pptx) | [SVG](whole-report/technical-status-review.svg) |

Each report also has a desktop workspace viewport and a 390px mobile Preview capture under whole-report/. The full-page editor and Preview PNGs above are individually linked. The complete set is summarized in the [contact sheet](whole-report/whole-report-contact-sheet.png), with the [whole-report PDF review](whole-report/whole-report-review.pdf).

## Reuse and remap journey

- Start with the [source report editor](whole-report/reuse-source-report-editor-desktop.png), [source Preview](whole-report/reuse-source-report-preview-desktop.png), and [source PPTX](whole-report/reuse-source-report.pptx).
- Continue to the [remapped report editor](whole-report/reuse-remapped-report-editor-desktop.png), [remapped Preview](whole-report/reuse-remapped-report-preview-desktop.png), [mobile Preview](whole-report/reuse-remapped-report-preview-mobile.png), and [remapped PPTX](whole-report/reuse-remapped-report.pptx).
- Inspect [section reuse editor](whole-report/reuse-remapped-section-editor-desktop.png), [guided remap](whole-report/reuse-remap-guided-dialog.png), [ambiguous mapping](whole-report/reuse-remap-ambiguous-dialog.png), [incompatible mapping](whole-report/reuse-remap-incompatible-dialog.png), and [conflict recovery](whole-report/reuse-remap-conflict-recovery.png).
- The [reuse versus blank rebuild action comparison](reuse-vs-blank-action-comparison.json) and [remap compatibility/history receipts](remap-compatibility-history.json) are extracted with the original [full CHG-181 native acceptance receipt](whole-report/chg181-native-acceptance.json) and its SHA-256 sidecar.

## Test and native release evidence

- [Fresh native release report](native-release/reports/report.json): all maintained local/native gates PASS, with no remaining checks.
- [Exact fresh native release ZIP](native-release/CHG-181-r1-fresh-native-20260924-r2.zip).
- [Source evidence summary](native-release/reports/source-evidence-summary.json), [full test JUnit report](native-release/reports/full-tests.xml), and [delivery JUnit report](native-release/reports/delivery-tests.xml).
- [Release manifest](native-release/reports/release-manifest.json), [source manifest](native-release/reports/source-manifest.json), and [native artifact hash list](native-release/reports/artifact-sha256.json).
- Relevant [lifecycle](native-release/key-gates/receipt.json), [chart](native-release/key-gates/chart-studio-acceptance.json), [data](native-release/key-gates/data-workflows.json), [performance](native-release/key-gates/performance.json), and [operations](native-release/key-gates/operations-drill.json) receipts are individually available.

## Source, runtime, and Fabric identity

- [Identity record](identity.json) binds the failed Fabric job, accepted base, recovered candidate, tree, editor SHA-256, native runtime, and fresh release report.
- Exact candidate: 14d9c80efe3daccdf0fe4ff59a108d4f66e718bf; tree: 4de38b5e788db659064c2e8bd9351c0f56505ba1.
- Fresh native evidence used the same integrated editor SHA-256 as the recovered evidence: bf0ab956a6b80f244decb209d7038a6a8ebec573818b260a5cf1eb83da944be5.
- Artifact Bridge staging was unavailable in this session. This artifact is published through the Git carrier ref; Fabric owns publication of its new-request audit evidence.

## Scope

This is local/internal-pilot native evidence. It does not claim company target certification, Production Gold, or CHG-173 GO.
