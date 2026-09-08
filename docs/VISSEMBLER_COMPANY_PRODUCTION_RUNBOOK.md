# Visembler company-managed production runbook

This document is the company-readiness boundary for Visembler. The existing
[`OPERATIONS.md`](../company_ui/products/visualizer/OPERATIONS.md) remains the
authoritative local/internal-pilot procedure. A company deployment is not
certified by a laptop run: it must provide the external identity, durable
storage, proxy, session, backup, and browser evidence listed below.

## Supported initial topology

The smallest supported company topology is one Visembler process behind the
company identity gateway and reverse proxy, using a durable POSIX-backed data
directory with exclusive ownership by the service account. This preserves the
existing atomic report repository, file locks, revision conflicts, quarantine,
history, checkpoints, trash, and content-addressed assets.

Multiple application replicas are not claimed by this repository alone. The
Company UI runtime requires shared NiceGUI session state and confirmed session
affinity for `COMPANY_UI_EXPECTED_REPLICAS > 1`; the company must also prove
that the selected shared filesystem provides the repository lock and atomic
rename guarantees. A database/object-store migration is intentionally deferred
until measured company requirements justify it.

## Required production configuration

Use a company-approved Python 3.11–3.13 runtime and install the pinned
`requirements.txt`. Set the following values before starting `app.py`:

```bash
export COMPANY_UI_ENVIRONMENT=prod
export COMPANY_UI_HOST=0.0.0.0
export COMPANY_UI_PORT=8080
export COMPANY_UI_STORAGE_SECRET='a-company-managed-secret-at-least-32-characters'
export COMPANY_UI_VISUALIZER_DATA_DIR=/srv/visembler/data

# The gateway/proxy is the only identity assertion source.
export COMPANY_UI_AUTH_MODE=header
export COMPANY_UI_PROXY_ENABLED=true
export COMPANY_UI_TRUSTED_PROXIES='10.20.0.0/16,10.30.0.0/16'
export COMPANY_UI_ROOT_PATH=''

# Required only when active reports need explicit first-time ownership migration.
export COMPANY_UI_MIGRATION_OWNER_SUBJECT='visembler-migration-owner'
```

The gateway must remove client-supplied identity headers and set the validated
headers below. Subjects are stable opaque identifiers, not display names or
email addresses:

```text
x-auth-user
x-auth-name
x-auth-email
x-auth-roles       (visembler.user, visembler.editor, visembler.admin, or visembler.support)
x-auth-permissions (optional explicit capabilities)
x-auth-groups      (optional stable group IDs)
```

`COMPANY_UI_AUTH_ASSERTION_SECRET` may be used instead of trusted proxy source
validation only when the gateway supplies the matching validated assertion and
the secret is managed outside the repository. Never put it in a report, log,
receipt, or shell history.

Production fails closed if header authentication is not selected, storage
secret is missing, the proxy boundary is not trusted, multi-replica session
requirements are incomplete, or an existing report has no owner and no
explicit migration owner is configured. Dev/test use an explicit deterministic
`local-dev` principal only; that identity is never selected in production.

## Resource model

Each report has one owner and optional subject/group grants stored atomically in
`reports/_governance/access/`. Report JSON, history, trash, and assets remain
backward-compatible. The capabilities are enforced at the scoped repository
boundary and therefore apply to page loads, bridge commits, history, export,
trash, restore, duplicate, and asset reads—not only to visible controls.

| Role | Capabilities |
|---|---|
| Owner | read, edit, rename, duplicate, share, delete, restore, history read/restore, export |
| Editor | read, edit, rename, duplicate, history read/restore, export |
| Viewer | read, history read, export |

Report Hub shows My/accessible reports, owner/access context, and a compact
share surface. Revocation is checked on the next request and direct report IDs,
history IDs, and asset IDs do not bypass the resource check.

## Storage, backup, restore, and retention

Back up the complete `COMPANY_UI_VISUALIZER_DATA_DIR`, including:

- `reports/*.json`;
- `reports/_history/` and `reports/_trash/`;
- `reports/_assets/`;
- `reports/_governance/access/` and `reports/_governance/audit.jsonl`;
- the NiceGUI storage-secret file or the company-managed equivalent.

Restore into a stopped, clean candidate directory, run the readiness and
company gate, open representative reports, verify history/ACL/assets, and only
then switch the service to the restored directory. Preserve the source backup
until the verification is complete. The repository does not silently purge
history, trash, ACLs, or audit records; retention and backup ownership remain
company policy decisions.

## Health, readiness, diagnostics, and logs

- `/healthz` is a lightweight process/storage health response.
- `/readyz` includes report storage and governance-catalog readiness and returns
  `503` when a critical check fails.
- `/diagnostics` is disabled by default and, when enabled, requires the
  authenticated support/admin policy. It returns runtime facts, not report
  contents.
- `reports/_governance/audit.jsonl` records safe security/resource events with
  actor subject, action, resource ID, revision where relevant, outcome, and a
  correlation ID. It never records report models, clipboard data, image bytes,
  secrets, or session tokens.

## Verification commands

Local/internal pilot, preserving the existing status meaning:

```bash
python scripts/verify_release.py --host-mode native \
  --output "$HOME/Downloads/visembler-local-$(date +%Y%m%d_%H%M%S)"
```

Company application-boundary gate:

```bash
python scripts/release_checks/run_company_production_readiness.py \
  --output "$HOME/Downloads/visembler-company-readiness-$(date +%Y%m%d_%H%M%S)"
```

Without target-environment evidence, the company gate can only emit
`READY_FOR_COMPANY_TARGET_CERTIFICATION`. It emits
`PASS_COMPANY_MANAGED_PRODUCTION_CANDIDATE` only when an external evidence
document for the exact source SHA proves the company identity/proxy/storage/
session/browser/recovery boundary.

## Incident and upgrade procedure

1. Capture the correlation/reference ID and safe runtime logs.
2. Check `/readyz` and the recent governance audit outcome.
3. Stop the candidate before restore or rollback; do not edit report files by hand.
4. Restore a verified complete data-directory backup into a new path.
5. Run the company gate and representative browser checks against the restored path.
6. Switch the service to the verified path and retain the failed source for investigation.
7. For upgrades, run migration dry-run/evidence first, preserve the previous
   package and data path, and roll back by stopping the candidate and restarting
   the previous verified package against the retained data path.

