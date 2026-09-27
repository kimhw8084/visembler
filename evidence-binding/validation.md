# CHG-277 R2 evidence-binding validation

- Project/request/operation/job: `visembler` / `CHG-277-r2` / `VERIFY` / `CF-9e31767aa01cb930895fe46a`.
- The protected target was fetched and read as `main@f1a3cd5c5fa4e6eb5f2d51c38555a34f85f5fee3`, tree `ab98bfbd27bcf7da147e15f70c6c50ef27d8bae4`.
- The accepted R1 head is `602552a4b121f0f722542ea5cefe419b1cb292c4`, tree `59f0a884910c7b26a27ad45b2ac49a5a648e7f88`, direct parent the protected base.
- The R2 work branch is exactly the accepted head locally and remotely. The comparison from accepted head to R2 work-branch HEAD contains zero commits and zero Product files.
- R1 artifact and native-evidence refs and their sole-parent commits were read and preserved. The retained R1 audit lacks the canonical project/job/operation/git integration binding; RC3 attempt 1 failed closed with `EVIDENCE_PROJECT_MISMATCH`, without a PR or merge.
- Main was observed at the protected base before R2 remote writes and again after R2 work-branch publication. The postflight remote read after artifact publication is required to confirm the same target state.
- R2 source changes: `false`. Browser capture launched: `false`. Product commits: `0`. Product changed files: `0`.
- No PowerPoint, Office, Quick Look, screenshot, browser, server, test, quality, or release qualification was run. No source or Product files were edited.
- This compact package is staged in the current Fabric job's `results/CF-9e31767aa01cb930895fe46a/artifact-output/evidence-binding/` output. The R2 native `.codex-fabric/audit.json` and deterministic native-evidence ref remain exclusively owned by the normal Fabric postprocessor; neither was authored or repointed here.
