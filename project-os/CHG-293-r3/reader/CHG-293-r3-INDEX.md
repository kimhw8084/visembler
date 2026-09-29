# CHG-293 R3 verification carrier

## Outcome

The exact R2 candidate was verified in native mode. The maintained verifier exited 1 with release_status=BLOCKED and checks_status=INCOMPLETE_OR_FAILED. It observed 31 required gates; 30 passed and chart-studio failed. This is a blocked verification result, not a Product fix disposition.

## Read in this order

1. identity.json — exact request, Fabric job, target/candidate/tree, command, timestamps, runtime, gate outcome.
2. quality/CHG-293-r3/maintained-release/report.json and progress.json — actual maintained verifier output.
3. quality/CHG-293-r3/maintained-release/failure-detail/chart-studio-acceptance.json and failure-detail/stage-a/stage-a-acceptance.json — top-level and nested failure receipts, including the exact locator timeout.
4. quality/CHG-293-r3/maintained-release/logs/chart-studio.log — raw required non-PASS gate log. logs/ contains raw logs for all gates.
5. quality/CHG-293-r3/maintained-release/full-tests.xml — raw JUnit receipt for 1,235 passing tests. The full-test raw log is beside it.
6. quality/CHG-293-r3/maintained-release/operations-drill.json and operations-drill/ — operations drill passed; its report and raw logs are retained.
7. source-immutability.json and quality/CHG-293-r3/maintained-release/source-manifest.json — source-stability PASS and equal 645-entry manifest.
8. r2-quality.json — GitHub Quality run 36449891032 / #323 completed successfully on the exact candidate.
9. r2-acceptance-carry-forward.json — R2 focused 2/2 and full pytest 1,235/1,235 PASS; R1 substantive product evidence remains authoritative.
10. quality/CHG-293-r3/maintained-release/verifier-output.zip and artifact-sha256.json — complete actual verifier output bundle and its native artifact hashes.

## Gate failure classification

The only required non-PASS is a single 5-second wait for .q-menu:visible in the nested report-hub lifecycle case. The browser-error gate passed and the reports contain no unexpected console/page/network errors. One run does not establish whether this is product behavior or timing/test synchronization. No source or harness changes were made. See failure-classification.json for the narrow next scope.
