# CHG-293 R4 independent review carrier

Request: CHG-293-r4 · Operation: VERIFY · Fabric job: CF-37c537f0f0e6acab4f56e5ae

Candidate: fc7917b937b2772b7eadcd4f80f969b8913ec53c  
Candidate tree: 685f1041f6184bd4a9fcbad80e7ff319633240a3  
Base: main@28d47acbaab8b493044120f6be4c32a225de4143

## Review order

1. identity/source-immutability.json
2. classification/classification.json
3. focused-stage-a/focused-summary.json, then inspect the three attempt receipts, traces, screenshots, HTML, and state observations under focused-stage-a/attempt-1 through attempt-3.
4. verification/maintained-verification-summary.json; full verifier output, report.json, progress.json, JUnit, logs, and operations drill are under full-maintained/.
5. carry-forward/R3-stage-a-timeout.json
6. carry-forward/R2-quality-run.json and carry-forward/R2-test-results.json
7. carry-forward/R1-product-acceptance.json

The R4 focused attempts passed 3/3 with no unexpected browser errors. The unchanged native verifier passed all 31 required gates. No integration PR was created or merged. Hashes for all carrier payload files are in MANIFEST.json; MANIFEST.sha256 hashes that manifest.
