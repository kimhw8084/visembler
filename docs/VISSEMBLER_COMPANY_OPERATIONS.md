# Visembler company-managed operations boundary

## Supported topology

The initial supported topology is one Visembler process behind the company
identity gateway/reverse proxy with durable POSIX storage. The application
uses Company UI's trusted-proxy identity adapter and file locks/atomic writes.
The runtime rejects an unsafe multi-replica configuration instead of claiming
that local file locking is shared-storage proof.

Production requires:

- `COMPANY_UI_ENVIRONMENT=prod`
- `COMPANY_UI_STORAGE_SECRET` with at least 32 characters
- `COMPANY_UI_AUTH_MODE=trusted_proxy`
- `COMPANY_UI_TRUSTED_IDENTITY_PROXIES` containing the gateway networks
- `COMPANY_UI_MIGRATION_OWNER_SUBJECT` for first migration of legacy reports
- secure cookies and TLS termination at the managed proxy

Identity headers are accepted only from the configured trusted proxy (or a
configured validated assertion secret). Display name and email are advisory;
the stable subject is the ACL identity.

## Run and verify

```bash
python -m company_ui.products.visualizer.cli
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
```

`/healthz` is cheap liveness. `/readyz` includes bounded storage writability,
atomic rename, readback, lock, governance reconciliation, and cleanup probes.
Diagnostics require an authenticated principal with `diagnostics.read`.

## Data protection

Report JSON, immutable history, trash, validated assets, governance ACLs, and
the append-only audit log are all part of the backup set. Restore to an
isolated directory first, run the readiness and reconciliation checks, then
promote the restored directory according to the company change process. This
repository does not invent RPO/RTO values or a cloud backup vendor.

The governance catalog is security-critical metadata. It can be structurally
validated/rebuilt only with an explicit migration owner; historical ownership
and grants must not be guessed from report JSON.

The catalog also carries a rebuildable lightweight report summary projection for
selectors and scoped listing. Report JSON remains canonical; startup rebuilds
the projection from active/trash records, and governed create/edit/rename
operations update it. A stale or missing projection is an operational repair
condition, never an authorization source.

## Failure and recovery

Interrupted create/trash/delete operations leave an immutable resource identity
and are reconciled deterministically. Active/trash identity reuse is rejected.
An orphan or ambiguous governance state is blocked rather than exposed. Stale
report saves are rejected by the existing revision contract and retain the
client recovery draft in the editor.

## Release authority

`PASS_LOCAL_INTERNAL_PILOT` remains the local single-instance status. The local
readiness command may emit `READY_FOR_COMPANY_TARGET_CERTIFICATION`; it emits
the managed-production candidate status only after a strict fresh target
receipt matches the exact source/dependency/artifact hashes and every required
company gate passes. Missing company identity, proxy, session, storage, or
recovery evidence is a target-environment blocker, not a local pass.
