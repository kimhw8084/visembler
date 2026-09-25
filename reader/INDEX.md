# Visembler CHG-208-r1 — reader index

This compact carrier records the remap field-identity and truthful wrong-type diagnostic fix for candidate `09ee0bea69a1c957e07b1bb88e846db471827e9b` (tree `54bed4c474db5da055eae508fbb5a302f97a0334`), based on exact main `63569c1e8d7f6e73650d66572c054c8108b02e96`. It addresses only the CHG-173 R2 Pareto remap failure class and preserves the existing fail-closed binding rules.

## Start here

- [Exact source and candidate identity](../identity.json)
- [Structured wrong-type, missing, ambiguous, unavailable, and shared-slot receipt](../diagnostics/focused-remap-diagnostics.json)
- [Native browser acceptance receipt](../browser/remap-acceptance.json)
- [Report, source, and preset immutability receipt](../immutability/report-source-preset.json)
- [Focused and full native test summary](../tests/focused-and-native-summary.json)
- [Native release binding and archive digest](../native-release/binding.json)
- [Maintained native release report](../native-release/report.json)

## Browser evidence

- [CHG-173 Pareto wrong-type dialog](../browser/screenshots/incompatible-pareto.png): Cycle and Failure count headers are visible; Failure count remains categorical; Apply is disabled; the explanation names the observed Category type and numeric Measurement requirement.
- [Ambiguous compatible remap dialog](../browser/screenshots/ambiguous-compatible.png): Service week and SERVICE WEEK are listed as separate compatible choices; Apply remains disabled before a choice.

The acceptance also verifies explicit-choice focus retention, Escape focus restoration, semantically disabled Apply, cancellation immutability, and source/preset preservation.

## Exact evidence provenance

The immutable reproduction comes from CHG-173 R2 / AR-73 at commit `7224c0815142557e2362e2ca4e6201e67006126c`, receipt `CHG-173-r2-evidence/authoring/remap-compatibility-history-conflict.json`, blob `d52795ac1b579f1540f11dcb1545762f8bf65464`. Fixture digest: `a26e761f247cf1c3c242d85acb51e37fe2bd7b3daada6ed393c4922709044525`.

The maintained native release verifier passed all required local gates as `PASS_LOCAL_INTERNAL_PILOT`, including the full test suite, CHG-181 browser reuse acceptance, and this CHG-208 browser acceptance. This does not claim managed company-target certification or Gold promotion. The standard Fabric audit ref is `refs/heads/codex-fabric/evidence/visembler/CHG-208-r1` and is parented to the exact candidate above.

No PR or main/integration mutation was performed.
