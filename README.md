# Janus

Self-hosted control for a home LAN: device inventory, static IPs through Pi-hole v6 DHCP, new-device quarantine and approval, alerts via email and Gotify.

- Design spec: `docs/specs/2026-09-30-janus-design.md`
- Roadmap: `docs/plans/2026-09-30-janus-roadmap.md`

## Tests

    scripts/test.sh

Needs a reachable Postgres database `janus_test` (see `.env.example`).

## Deploy (homelab)

    cp .env.example .env   # fill DB_JANUS_PASSWORD, JANUS_INTERNAL_TOKEN, JANUS_PIHOLE_PASSWORD
    docker compose up -d --build

The worker starts in `JANUS_SYNC_MODE=dry-run`: it logs the reservation diff and never writes to Pi-hole.
