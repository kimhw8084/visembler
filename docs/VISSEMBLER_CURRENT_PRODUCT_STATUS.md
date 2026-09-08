# Visembler current product status

This file is the current Visembler product-status authority.  The surrounding
Company UI package has its own framework release documents; those documents are
not Visembler release evidence.

## Application status

The source tree provides:

- `PASS_LOCAL_INTERNAL_PILOT` only for the existing local single-instance
  application contract;
- `READY_FOR_COMPANY_TARGET_CERTIFICATION` when the local governance,
  storage, migration, and security gates pass;
- `PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE` only when a strict, fresh receipt
  from the actual company-managed identity/proxy/storage/session environment
  is supplied to `run_company_production_readiness.py`.

The local command never treats a hand-written status field as target evidence.
It checks the candidate SHA, source manifest, dependency fingerprint, required
gate names, timestamps, and artifact hashes before accepting a target receipt.

## Initial company topology

The supported initial boundary is one managed Visembler process behind the
company identity gateway/reverse proxy using durable POSIX storage. Production
requires a trusted proxy identity assertion, secure session configuration, an
explicit migration owner for existing reports, and an operator-owned backup /
restore policy. Multi-replica operation remains rejected by the runtime unless
the Company UI shared-session and affinity requirements are explicitly met.

## Historical evidence

Older alpha, local-pilot, visual-crawler, and authoring-stage receipts remain
historical evidence. They must not be interpreted as company-managed target
certification. The release aggregator requires fresh receipts for every
designated company gate and returns `BLOCKED` when one is missing or stale.

## Commands

From this source directory:

```bash
python -m pytest
python scripts/release_checks/run_company_production_readiness.py \
  --output /tmp/visembler-company-readiness.json
python scripts/release_checks/run_company_user_acceptance.py \
  --output /tmp/visembler-company-users.json
python scripts/release_checks/run_company_user_browser_acceptance.py \
  --base-url http://127.0.0.1:8080 \
  --data-dir "$COMPANY_UI_VISUALIZER_DATA_DIR" \
  --output /tmp/visembler-company-users-browser.json
python scripts/release_checks/run_company_capacity.py \
  --output /tmp/visembler-company-capacity.json
python scripts/release_checks/run_company_source_stability.py \
  --output /tmp/visembler-company-source-stability.json
python scripts/release_checks/run_company_release_aggregator.py \
  --receipts /path/to/fresh-company-receipts \
  --output /tmp/visembler-company-release.json

The browser receipt requires a running production-mode instance and an isolated
fixture directory. It uses separate Playwright contexts for anonymous, owner,
viewer/editor, and unauthorized subjects; it does not delete reports outside
its unique run-owned fixture IDs.
```

The target environment supplies a separate validated target receipt through
`VISSEMBLER_COMPANY_TARGET_RECEIPT`; no SSO vendor, cloud service, or corporate
infrastructure command is assumed by this repository.
