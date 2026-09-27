# Exact-base reproduction and candidate verification

The exact base was checked out detached in a clean worktree. Each chart was opened in the real integrated Visembler report and edited through visible Chart Studio controls, then saved/reloaded and exported using the report's supported editable-PowerPoint action. The before evidence includes the saved model, visible action/provenance record, geometry, source report screenshot, Chart Studio screenshot, PPTX, chart XML, package inspection and semantic import round-trip. Candidate evidence repeats these captures against the committed candidate.

| Case | Authoring / control | Exact-base export | Candidate export |
|---|---|---|---|
| A, executive renewal | 8 ordered quarters; Best readable axes; authored rotation 45°; scale auto remains true | `tickLblSkip=5`; OOXML rotation `-2700000`; Quick Look shows only two labels | interval 1; no `tickLblSkip`; rotation retained; all 8 identities in editable text and visibly present |
| F, cold-chain destinations | 4 destinations; Best readable axes; explicit interval 1 / rotation 0°; scale auto true | `tickLblSkip=2`; Quick Look shows two labels | no `tickLblSkip`; all four identities visibly present as editable text |
| E, dense control | 16 categories × 3 series; authored interval 6 / rotation 35° | `tickLblSkip=6` | `tickLblSkip=6`; interval remains exactly 6 |
| Untouched dense holdout | 16 × 3; no label-intent marker | automatic `tickLblSkip=7` | automatic `tickLblSkip=7` remains |
| Untouched low-density holdout | 4 categories; no marker | automatic `tickLblSkip=2` | no skip; all four identities visible |

All chart source models, saved models and action records, geometry, PPTX, XML, package facts, semantic round-trip facts and source/preview pixels are under `evidence/before-exact/` and `evidence/candidate-exact/`. `evidence/package-comparison.json` contains full category/value caches and package semantics for both revisions.

The previews are Quick Look preview-only. LibreOffice/soffice was unavailable, so this evidence does not claim Office rasterization or certification.
