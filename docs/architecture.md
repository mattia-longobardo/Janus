# Architecture

Interactive diagrams (open in a browser, with dark/light theme, search and export):

- [diagrams/architecture.html](diagrams/architecture.html) — containers and their connections
- [diagrams/device-access.html](diagrams/device-access.html) — how a device moves between `pending`, `authorized`, `lan_only` and `blocked`

The `.json` file next to each diagram is its source; regenerate with [Archify](https://github.com/tt-a1i/archify) (`archify finalize <type> <file>.json <file>.html`).

## Containers

One image (`Dockerfile`) runs in four containers; `entrypoint.sh` picks the role from the command.

| Container | Command | Network | What it does |
|---|---|---|---|
| `janus` | `api` | `proxy_public`, `db_internal` | Runs `alembic upgrade head`, then FastAPI on `127.0.0.1:8000` and the Next.js server on `:3000`. Traefik routes `https://${JANUS_HOST}` to port 3000. |
| `janus-worker` | `worker` | `db_internal`, `mail_internal`, `metrics_internal` | Periodic jobs (below) and Prometheus metrics on `:9108/metrics`. |
| `janus-sentinel` | `sentinel` | host | Sniffs ARP, DHCP, NetBIOS, SSDP and mDNS answers on `enp5s0`, sweeps the subnet with ARP every 60 s, probes Pi-hole DNS. Stays user 1000 through a `cap_net_raw` file capability on `/usr/local/bin/janus-sniff`. |
| `janus-scanner` | `scanner` | `db_internal` | Unprivileged `nmap -sT -sV --top-ports 200`, one host at a time, inside the scan window. |

All four share the PostgreSQL database; they talk to each other only through it (settings, heartbeats, events).

## Request path

1. The browser reaches Traefik over HTTPS; Traefik forwards to Next.js on `:3000`.
2. Auth.js signs the user in through Authentik (OIDC). Only e-mails in `JANUS_ALLOWED_EMAILS` count as signed in; the check runs on every request, so removing an address takes effect at once.
3. The catch-all route `frontend/app/api/[...path]/route.ts` forwards `/api/*` to FastAPI on `127.0.0.1:8000`. It refuses unsigned (401) and cross-site (403) requests and bodies over 1 MB, and adds the `X-Janus-Internal-Token` header.
4. FastAPI accepts every route except `/api/health` only with that token (`backend/app/security.py`), compared in constant time. The API is bound to loopback, so nothing outside the container reaches it.

## Background jobs

### Worker (`backend/app/worker.py`)

A single loop that runs each job when it is due and touches `/tmp/janus-worker.heartbeat` for the Docker health check.

| Job | Interval | Effect |
|---|---|---|
| `reconcile` | 300 s | Compares the desired reservations with Pi-hole's `dhcp.hosts`. In `dry-run` it only logs the diff; in `apply` it removes stale lines and adds missing ones, one line at a time. Marks Pi-hole down/up (`infra.down` / `infra.up`). |
| `presence` | 60 s | Tracks maintenance windows, checks the sentinel heartbeat, marks devices offline after 300 s without a sighting (offline alerts per group, muted during maintenance), purges sightings older than 30 days. |
| `dns` | 60 s | Pi-hole DNS is down if the sentinel has had no DNS answer for 3 minutes. |
| `dispatch` | 15 s | Sends pending events as Gotify / e-mail notifications according to the rules, quiet hours, maintenance windows and debouncing (Redis db 3). |
| `identity` | 60 s | Turns DHCP, mDNS, NetBIOS, SSDP announcements and the offline IEEE OUI file into device facts (vendor, model, OS hints). |

### Sentinel (`backend/app/sentinel/`)

- `observe.py` parses packets into observations (MAC, IP, source, hostname and announcement data).
- `record.py` turns observations into devices, sightings and events: a new MAC becomes a `pending` device (`device.new`); the gateway is recorded as authorized; it also raises `ip.conflict` (two MACs claim one address), `device.ip_mismatch` (an approved device outside its reservation) and `device.private_mac`.
- A full packet queue drops packets instead of blocking; a dead sniffer or a change of network settings makes the process exit so Docker restarts it.

### Scanner (`backend/app/intel/`)

`scanning.py` picks the next device: manual scan requests first (`POST /api/devices/{id}/scan`), then online approved devices in groups with `scan_enabled` whose last scan is older than the group interval. Manual requests run at any time; scheduled scans are skipped during quiet hours, maintenance windows and outside the scan window (08:00–22:00 by default). New open ports raise `security.new_port`; services in `rules.py`'s risky list raise `security.risky_service` (mutable per service).

## Pi-hole integration

Janus talks to the Pi-hole v6 REST API (`backend/app/pihole/client.py`) with an app password; one login is shared across requests because Pi-hole refuses parallel logins.

- **Reservations.** Every approved device with a MAC and a static IP becomes a `dhcp.hosts` line `mac[,set:lanonly],ip,hostname,24h`. Janus remembers which lines it wrote and only removes those, so hand-written lines survive. Duplicate IPs or MACs are refused rather than written, so Pi-hole's DNS never breaks on a bad config.
- **Quarantine.** Pi-hole's DHCP range is the quarantine pool `.240–.254`; unknown devices get an address there without a gateway, so they reach only the LAN until approved.
- **LAN only.** `lan_only` devices get a reservation tagged `set:lanonly`; the Pi-hole `dhcp-option` tag rules (in the network stack) withhold the gateway from them.
- **Immediate enforcement.** In `apply` mode, approve and block write to Pi-hole at once instead of waiting for the next reconcile. Approve revokes the device's quarantine lease, block revokes its current lease, so the device asks for a new address.
- **DNS activity.** The device page reads Pi-hole's query log for the device's IP (`/api/devices/{id}/dns`, `/dns/analysis`).

## Data model

PostgreSQL, migrations in `backend/migrations/versions/` (applied at container start).

| Table | Holds |
|---|---|
| `groups` | Name, colour, icon, IP range, default access, offline alert hours, scan settings |
| `devices` | MAC, name, hostname, group, static IP, last IP, access (`authorized`, `lan_only`, `pending`, `blocked`), presence, scan state |
| `sightings` | Who was seen at which IP, from which source (30-day retention) |
| `device_facts` | Identity facts from DHCP/mDNS/NetBIOS/SSDP/OUI |
| `services` | Open ports from nmap, risk level, mute flag |
| `events` | Event log and notification outbox |
| `notification_rules` | Per-event channel and Gotify priority |
| `maintenance_windows` | Recurring windows that mute offline and infra alerts |
| `links` | Wired uplinks drawn on the network map |
| `settings` | Key/value: network overrides, sync mode, heartbeats, down-since markers, map positions |

## Security model

- Single trust boundary at the web app: Authentik sign-in plus e-mail allowlist, same-origin check, then a shared secret to the loopback-only API.
- Everything runs as user 1000. Only the sentinel needs raw sockets, granted to one binary via a file capability; the other containers drop `NET_RAW`.
- Device identification uses only local data (OUI file, LAN announcements, Pi-hole log); no external lookup services.
- The Pi-hole admin password is never stored: cutover and rollback read it from an environment variable for one command.
