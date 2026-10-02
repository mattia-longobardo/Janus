# Operations

## Deploy and update

    docker compose up -d --build

The `janus` container applies database migrations at start. The worker, sentinel and scanner wait for `janus` to be healthy. Every container has a health check and the `autoheal=true` label:

| Container | Healthy when |
|---|---|
| `janus` | `/api/health` (FastAPI) and `/api/healthz` (Next.js) answer |
| `janus-worker` | heartbeat file younger than 15 min |
| `janus-sentinel` | heartbeat file younger than 5 min (written after each ARP sweep) |
| `janus-scanner` | heartbeat file younger than 10 min |

Logs: `docker logs -f janus-worker` (same for the others). Rotation is 3 × 10 MB per container.

## Sync modes

| Mode | Behaviour |
|---|---|
| `dry-run` | Janus computes and logs the reservation diff; Pi-hole is never written. Approve/block answer `enforcement: dry-run`. |
| `apply` | Reconcile writes the diff every 5 minutes; approve/block write at once and revoke leases. |

The switch happens only through the cutover procedure: see [runbooks/cutover.md](runbooks/cutover.md).

## CLI

Inside the `janus` container:

    docker exec -it janus python -m app.cli <command>

| Command | Purpose |
|---|---|
| `import-csv <file> [--dry-run]` | Import devices from a CSV export and infer group ranges |
| `sync [--apply]` | Show (or apply) the Pi-hole reservation diff now |
| `preflight` | Check that the DHCP cutover can start; non-zero exit while something blocks |
| `backup` | Save a Pi-hole Teleporter export and a Janus data dump to `janus/backups/<timestamp>/` |
| `cutover --pihole-password-env VAR` | Enable Pi-hole DHCP with the quarantine pool and switch Janus to `apply` |
| `rollback --pihole-password-env VAR` | Turn Pi-hole DHCP off and switch Janus back to `dry-run` |

## Metrics

The worker serves Prometheus metrics on `janus-worker:9108/metrics` (network `metrics_internal`):

| Metric | Type |
|---|---|
| `janus_devices{access,online}` | gauge |
| `janus_devices_pending` | gauge |
| `janus_devices_health{health}` | gauge (`ok`, `warning`, `critical`) |
| `janus_last_sweep_timestamp_seconds` | gauge |
| `janus_last_port_scan_timestamp_seconds` | gauge |
| `janus_pihole_up`, `janus_sentinel_up`, `janus_maintenance_active` | gauge |
| `janus_sync_mode_info{mode}` | gauge |
| `janus_events_total{type}` | counter |

## Notifications

Events are written to the `events` table and dispatched every 15 s. Defaults (editable per event in **Notifications**):

| Event | Default |
|---|---|
| `device.new` | Gotify priority 8 + e-mail, never muted |
| `ip.conflict`, `security.risky_service` | Gotify priority 8 + e-mail |
| `infra.down` | Gotify priority 8 + e-mail, muted during maintenance |
| `security.new_port` | Gotify priority 6 |
| `device.approved`, `device.blocked` | Gotify priority 4 |
| `infra.up` | Gotify priority 4 + e-mail, muted during maintenance |
| `device.offline` | Gotify priority 5, muted during maintenance |
| `device.private_mac` | Gotify priority 5 |
| `device.ip_mismatch` | e-mail only |

Quiet hours defer non-urgent messages; Redis debouncing collapses bursts of the same alert.

## Tests

Backend (needs a reachable PostgreSQL database `janus_test`; the script reads `.env`):

    scripts/test.sh

Frontend:

    cd frontend && npm ci && npm test

`backend/tests/test_repo_hygiene.py` fails if a real MAC address is about to be committed: use the documentation ranges `00:00:5E:00:53:xx` / `02:00:5E:00:53:xx` in examples and fixtures.
