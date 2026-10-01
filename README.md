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
`janus-sentinel` runs on the host network to see ARP and DHCP traffic (see the AGENTS.md exception); it stays user 1000 through a `cap_net_raw` file capability.

`janus-scanner` runs unprivileged `nmap -sT -sV` one host at a time on groups with `scan_enabled` (or on request via `POST /api/devices/{id}/scan`). Identity comes only from local data: the offline IEEE OUI file, DHCP/mDNS/NetBIOS/SSDP announcements, and the local Pi-hole query log.
