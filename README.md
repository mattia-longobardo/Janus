# Janus

Self-hosted control for a home LAN: device inventory, static IPs through Pi-hole v6 DHCP, new-device quarantine and approval, alerts via email and Gotify.

- Design spec: `docs/specs/2026-09-30-janus-design.md`
- Roadmap: `docs/plans/2026-09-30-janus-roadmap.md`

## Tests

    scripts/test.sh

Needs a reachable Postgres database `janus_test` (see `.env.example`).
