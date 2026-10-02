# Janus

Self-hosted control plane for a home LAN (192.168.1.0/24): device inventory, static IPs through Pi-hole v6 DHCP reservations, quarantine and approval of new devices, local device identification and port scanning, alerts via Gotify and e-mail.

Janus never sits in the traffic path. It watches the LAN (ARP, DHCP, mDNS, NetBIOS, SSDP), keeps the inventory in PostgreSQL and tells Pi-hole which reservations to hold. The router (QHora-301W) stays the gateway; after the cutover Pi-hole is the only DHCP server.

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Containers, data flow, background jobs, data model, security model |
| [docs/configuration.md](docs/configuration.md) | Every environment variable and the settings editable from the web app |
| [docs/operations.md](docs/operations.md) | Deploy, sync modes, CLI, metrics, backups, tests |
| [docs/runbooks/cutover.md](docs/runbooks/cutover.md) | Moving DHCP from the router to Pi-hole, and rolling back |
| [docs/diagrams/architecture.html](docs/diagrams/architecture.html) | Interactive architecture diagram (open in a browser) |
| [docs/diagrams/device-access.html](docs/diagrams/device-access.html) | Interactive device access lifecycle |

## Quick start

    cp .env.example .env      # fill in the secrets, see docs/configuration.md
    docker compose up -d --build

The stack joins the external networks `proxy_public`, `db_internal`, `mail_internal` and `metrics_internal`, and expects the shared PostgreSQL (database `janus`), Redis, Traefik, Authentik, Gotify and SMTP services of the homelab.

Janus starts in `dry-run`: it computes the Pi-hole reservation diff and never writes to Pi-hole until the cutover switches it to `apply`.

## Layout

    backend/     FastAPI API, worker, sentinel, scanner, Alembic migrations, tests
    frontend/    Next.js web app (Auth.js + Authentik), proxy to the API, tests
    docs/        documentation, runbook and diagrams
    Dockerfile   one image for all four containers (entrypoint.sh picks the role)
