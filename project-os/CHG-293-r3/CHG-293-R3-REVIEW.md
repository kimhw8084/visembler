# CHG-293 R3 — maintained-release verification

Request CHG-293-r3; operation VERIFY; Fabric job CF-1bd4471ee0df00aca061894a.

The exact unchanged R2 candidate fc7917b937b2772b7eadcd4f80f969b8913ec53c (tree 685f1041f6184bd4a9fcbad80e7ff319633240a3) was checked with the maintained native release verifier. It exited 1: 30/31 required gates passed, with chart-studio as the only required non-PASS. The generated report says release_status=BLOCKED and checks_status=INCOMPLETE_OR_FAILED. Actual reports and receipts are under quality/CHG-293-r3/maintained-release/; use reader/CHG-293-r3-INDEX.md as the compact map.

This run made no source, test, harness, config, workflow, or manifest changes. The generated source-stability check passed and the 645-entry source manifest is byte-for-byte equal after verification. CHG-293 R1 visual/product evidence and R2 shallow-checkout acceptance remain carried forward unchanged. The one chart-studio timeout is insufficient to classify as a Product defect or transient. Stop for independent Project OS audit; do not integrate.
