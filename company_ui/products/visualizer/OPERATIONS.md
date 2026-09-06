# Visembler local/internal-pilot operation

Visembler is supported for one local/internal-pilot instance. It is not a claim
of shared-network readiness: a shared deployment needs an organization-managed
identity, authorization, durable backup, and hosting/session boundary.

Install the pinned runtime in an isolated Python environment with
`python -m pip install -r requirements.txt`, then start on loopback with:

```bash
python scripts/launch_visembler.py --data-dir /absolute/path/to/visembler-data --port 8080
```

The launcher checks the requested port and never stops another process. Network
exposure is explicit: pass a non-loopback `--host` only after the deployment
prerequisites above have been verified.

## Data inventory and backup drill

The selected data directory contains `reports/` (active reports),
`reports/_history/`, `reports/_trash/`, `reports/_assets/`, and the local
`.storage_secret`. User preferences are NiceGUI user storage and must be backed
up with the deployment's application-state mechanism; they are not report JSON.

Stop the local instance, copy the complete selected data directory to a new
location, then start Visembler with that copy using `--data-dir`. Verify a
report, its history, and an image asset before treating the backup as valid.
Rollback means stop the candidate, retain the original directory unchanged, and
restart with the verified backup directory. This procedure does not change
history retention or delete source data.

## Final local/internal-pilot verification

Run the maintained verifier against a new evidence directory after source or
runtime changes:

```bash
python scripts/verify_release.py --host-mode native \
  --output "$HOME/Downloads/visembler-final-$(date +%Y%m%d_%H%M%S)"
```

A bounded local/internal-pilot candidate is accepted only when `report.json`
records `PASS_LOCAL_INTERNAL_PILOT`. The verifier executes the full test suite,
39 production-element workflows, data/portability checks, performance timing,
native disconnect/restart recovery, real browser module-worker failure/retry,
the backup/restore drill, and responsive/keyboard visual acceptance on one
stable source manifest. Missing or failed gates keep the result blocked.
