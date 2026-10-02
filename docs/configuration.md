# Configuration

## `.env` (compose)

Copy `.env.example` to `.env`. `docker-compose.yml` turns these into the container variables below.

| Variable | Used for |
|---|---|
| `DB_JANUS_PASSWORD` | Password of the `janus` role on the shared PostgreSQL |
| `JANUS_INTERNAL_TOKEN` | Shared secret between the Next.js proxy and FastAPI (long random string) |
| `JANUS_PIHOLE_PASSWORD` | Pi-hole **app** password (reads always; writes only after the cutover enables `app_sudo`) |
| `REDIS_PASSWORD` | Shared Redis, db 3 holds the notification debounce keys |
| `GOTIFY_HOST`, `JANUS_GOTIFY_TOKEN` | Gotify server and application token |
| `SMTP_HOST`, `SMTP_NOREPLY_USER`, `SMTP_NOREPLY_PASSWORD` | SMTP over SSL (port 465); the user is also the sender |
| `JANUS_NOTIFY_EMAIL` | Recipient of e-mail alerts |
| `JANUS_HOST` | Public host name served by Traefik; also `AUTH_URL` |
| `AUTHENTIK_HOST`, `AUTH_AUTHENTIK_ID`, `AUTH_AUTHENTIK_SECRET` | Authentik OIDC application `janus` |
| `AUTH_SECRET` | Auth.js session encryption key (`openssl rand -base64 32`) |
| `JANUS_ALLOWED_EMAILS` | Comma-separated e-mails allowed to use the app; empty means nobody |

## Backend variables (`JANUS_*`)

Read by `backend/app/config.py`. Defaults in brackets; compose sets the ones marked *.

| Variable | Default | Meaning |
|---|---|---|
| `JANUS_DATABASE_URL`* | local `janus` db | SQLAlchemy URL (`postgresql+psycopg://…`) |
| `JANUS_INTERNAL_TOKEN`* | empty | API refuses every protected route with 503 while empty |
| `JANUS_PIHOLE_URL`* | `http://192.168.1.220:1000` | Pi-hole v6 web/API |
| `JANUS_PIHOLE_PASSWORD`* | empty | Pi-hole app password |
| `JANUS_SYNC_MODE`* | `dry-run` | Initial mode; the stored mode (set by cutover/rollback) wins |
| `JANUS_SUBNET`, `JANUS_GATEWAY` | `192.168.1.0/24`, `192.168.1.1` | Managed network |
| `JANUS_QUARANTINE_START`, `JANUS_QUARANTINE_END` | `.240`, `.254` | Pi-hole DHCP pool for unknown devices |
| `JANUS_RESERVATION_LEASE` | `24h` | Lease time written into each reservation |
| `JANUS_RECONCILE_INTERVAL_S` | `300` | Pi-hole reconcile period |
| `JANUS_PRESENCE_TIMEOUT_S`, `JANUS_PRESENCE_INTERVAL_S` | `300`, `60` | Offline after this long unseen; check period |
| `JANUS_DISPATCH_INTERVAL_S` | `15` | Notification dispatch period |
| `JANUS_IDENTITY_INTERVAL_S` | `60` | Identity enrichment period |
| `JANUS_SENTINEL_INTERFACE`* | `enp5s0` | Interface the sentinel sniffs |
| `JANUS_SWEEP_INTERVAL_S` | `60` | ARP sweep period |
| `JANUS_SIGHTING_RETENTION_DAYS` | `30` | Sighting history kept |
| `JANUS_SCAN_POLL_S`, `JANUS_SCAN_HOST_TIMEOUT_S` | `30`, `180` | Scanner poll period and per-host nmap timeout |
| `JANUS_SCAN_WINDOW_START`, `JANUS_SCAN_WINDOW_END` | `08:00`, `22:00` | Scheduled scans only inside this window |
| `JANUS_TIMEZONE` | `Europe/Rome` | Default time zone for quiet hours and windows |
| `JANUS_REDIS_URL`* | `redis://localhost:6379/3` | Debounce store |
| `JANUS_GOTIFY_URL`*, `JANUS_GOTIFY_TOKEN`* | empty | Gotify channel (off while empty) |
| `JANUS_SMTP_HOST`*, `JANUS_SMTP_PORT`*, `JANUS_SMTP_USER`*, `JANUS_SMTP_PASSWORD`*, `JANUS_SMTP_SENDER`* | | E-mail channel |
| `JANUS_NOTIFY_EMAIL`* | empty | Alert recipient |
| `JANUS_BASE_URL` | `https://janus.longobardo.me` | Links inside notifications |
| `JANUS_OUI_PATH` | `/usr/share/ieee-data/oui.csv` | Offline vendor registry (Debian `ieee-data`) |

## Frontend variables

| Variable | Meaning |
|---|---|
| `BACKEND_URL` | FastAPI base URL, `http://127.0.0.1:8000` inside the container |
| `JANUS_INTERNAL_TOKEN` | Sent to the API as `X-Janus-Internal-Token` |
| `AUTH_SECRET`, `AUTH_URL`, `AUTH_TRUST_HOST` | Auth.js |
| `AUTH_AUTHENTIK_ID`, `AUTH_AUTHENTIK_SECRET`, `AUTH_AUTHENTIK_ISSUER` | Authentik provider (`https://${AUTHENTIK_HOST}/application/o/janus/`) |
| `JANUS_ALLOWED_EMAILS` | Allowlist, checked on every request |

## Settings stored in the database

Editable from the web app (**Settings**) without a restart; they override the environment defaults.

- **Network:** subnet, gateway, quarantine pool, Pi-hole URL, sentinel interface, sweep interval, scan window. Values are validated against each other and against the group ranges. The sentinel restarts itself when one of its settings changes.
- **Notifications:** per-event channel (Gotify, e-mail) and Gotify priority, quiet hours, time zone, test messages.
- **Maintenance windows:** recurring periods that mute offline and infrastructure alerts and pause scheduled scans.
- **Groups:** IP range, default access, offline alert threshold, port scan on/off and interval.
- **Sync mode:** `dry-run` / `apply`, changed only by the `cutover` and `rollback` commands.
