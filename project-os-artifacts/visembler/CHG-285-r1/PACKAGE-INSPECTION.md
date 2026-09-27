# Package, visual and semantic inspection

For A/F/E and both untouched holdouts, `evidence/package-comparison.json` records the source and candidate axis settings, intent marker, chart family, full ordered series names/categories/values, category/value caches, category text shapes, `catAx tickLblSkip`, text rotation, `valAx min/max`, and legend position. Individual full `chart.xml` parts and package facts are in each case directory.

The semantic comparison asserts exact equality between base and candidate for chart family, ordered series identity, all category/value series data and caches, value-axis bounds and legend position. It passes for A, F and E. Candidate intent changes the presentation only. Candidate PowerPoint import round-trip succeeds for every captured case and retains the optional marker.

Rotation geometry is covered by `test_chg285_rotation_aware_footprint_drives_automatic_fit`: identical long labels at 0° and 35° produce different projected horizontal footprints; the required automatic skip is computed from the projected footprint, not the unrotated width. The deterministic unit assertions are retained in the candidate source.

The A and F candidate package retains every category in chart caches and exposes every authored identity as editable slide text. F's four long destination identities are all present and visible in the Quick Look capture. A's eight quarter identities are all distinct and visible in its Quick Look capture. These are previews only, not Office certification.
