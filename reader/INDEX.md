# CHG-209 R1 evidence reader

This carrier is bound to candidate `9be45ba677875a54f1e9a3d488e53c483e879336` (tree `08719bb4afbe3c508cb296a4505001e36141cd4e`), sole parent `9719125bf253c2e79ef87d983c10fae324292af1`. The exact comparison base is `57967b84084140e30b06276469a1beedd322ec67`.

## Suggested review order

1. `identity.json` and `direction/rule-profile-inventory.json` establish candidate identity and the semantic rule/profile vocabulary.
2. `direction/anti-special-case-proof.json` and the CHG-209 test in `tests/full-tests.xml` document title, fixture and coordinate independence.
3. `scenes/per-scene-decisions.json` records person, context, task, decision, current truth, profile and observed section plan for all six scenes.
4. Compare `visual/contact-sheets/desktop-1440-base-v-candidate.png`, `narrow-390-base-v-candidate.png` and `narrow-320-dense-base-v-candidate.png`; inspect full canvases under `visual/{base,candidate}/scenes/`.
5. `browser/dom-geometry-accessibility.json` carries measured DOM geometry, document widths and direction-control focus evidence. `user-control/reversibility.json` records override, undo/redo, save/reload and Free-mode geometry.
6. `semantics/source-data-reuse-immutability.json` and `exports/export-regression-summary.json` cover unchanged report inputs/reuse bindings and editable PPTX regression checks.
7. `tests/focused-and-native-summary.json` and `native-release/binding.json` bind the complete test/release result to the exact candidate.

The matrix uses populated synthetic reports with long content and uncertainty states. E and F are holdouts created after the production classifier was implemented; their identifiers and titles are not production classifier inputs. Desktop and 390px captures exist for all scenes; 320px captures exist for the dense D and E scenes.

This evidence is staged for independent Project OS visual review. It does not claim human preference, universal aesthetic superiority, native-device accessibility, or company-managed Production Gold. No integration or main mutation was performed.
