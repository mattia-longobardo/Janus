# AGENTS.md — working on Janus

Guide for AI agents (and humans) changing this repository. Janus is a self-hosted control plane for a home LAN:
device inventory, DHCP reservations through network providers (Pi-hole v6, UniFi), quarantine and approval, guests,
local identification and port scans, notifications, better-auth sign-in. It never sits in the traffic path.

## Read first

1. [docs/features.md](docs/features.md): every feature with its rules, entry points, tests and invariants. **Read
   the section of each feature you will touch before writing code.**
2. [docs/design.md](docs/design.md): principles, end-to-end flows, data model, security model, extension points,
   design decisions.
3. [docs/architecture.md](docs/architecture.md), [docs/configuration.md](docs/configuration.md),
   [docs/operations.md](docs/operations.md): containers, variables, operations.
4. [docs/providers/adding-a-provider.md](docs/providers/adding-a-provider.md) before touching `backend/app/providers/`.

## Repository map

    backend/
      app/main.py            FastAPI app: routers, all protected by the internal token except /api/health
      app/api/               HTTP routes (one module per area)
      app/models.py          SQLAlchemy models; app/db.py engine and session
      app/config.py          env settings (JANUS_*)
      app/worker.py          periodic jobs + Prometheus metrics (app/metrics.py)
      app/sentinel/          packet capture, ARP sweep, observation recording
      app/intel/             identity facts, OUI, nmap scanner, DNS analysis
      app/enforcement/       provider-neutral reservation diff and sync
      app/providers/         network provider plugins (pihole/, unifi/, _template/) and their framework
      app/notify/            catalogue, policy, channels, dispatcher, rendering
      app/net/               MAC, hostnames, IP plan rules
      app/*.py               approval, guests, presence, health, netconfig, settings store, secretbox, import/export, CLI
      migrations/versions/   Alembic revisions 0001-0009 (hand-written)
      tests/                 pytest suite (fakes.py, fakes_provider.py, providers/, fixtures/, spikes/)
    frontend/
      app/                   Next.js App Router pages; app/api/[...path] proxies to FastAPI; app/api/auth better-auth
      components/            shared UI (ui.tsx primitives, device table, approve form, sidebar, ...)
      lib/                   API client, data hooks, auth (lib/auth/), proxy, formatting, map layout, ...
      providers/             frontend part of provider plugins (registry.ts, generic config form, pages)
      proxy.ts               Next.js middleware: session guard and /setup redirect
      scripts/migrate-auth.mjs  better-auth schema migration, run at container start
    docs/                    documentation, runbook, diagrams (docs/diagrams/*.json are the Archify sources)
    scripts/test.sh          backend test runner
    Dockerfile, entrypoint.sh, docker-compose.yml   one image, four roles (api, worker, sentinel, scanner)

## Run, test, lint

All commands from the repository root unless stated. Never print or commit the values in `.env`.

| What | Command | Notes |
|---|---|---|
| Backend tests | `scripts/test.sh` | Python 3.12 via `uv`, `requirements-dev.txt`. Needs a PostgreSQL reachable at `localhost:5432` with a `janus_test` database for the `janus` role; the script reads `DB_JANUS_PASSWORD` from `.env`, or set `JANUS_TEST_DATABASE_URL`. The suite drops and recreates the `public` schema of that test database. Pass pytest args: `scripts/test.sh tests/test_enforcement.py -q`, `scripts/test.sh tests/providers` |
| Backend lint | `cd backend && uv run --no-project --python 3.12 --with-requirements requirements-dev.txt ruff check .` | ruff rules `E,F,I,B,UP`, line length 130 (`backend/pyproject.toml`); `--fix` sorts imports |
| Frontend install | `cd frontend && npm ci` | Node 22 |
| Frontend tests | `cd frontend && npm test` | vitest + Testing Library, jsdom |
| Frontend type check | `cd frontend && npx tsc --noEmit` | there is no ESLint config: the type check is the lint |
| Frontend build | `cd frontend && npm run build` | Next.js standalone output |
| Compose check | `docker compose config -q` | only when `docker-compose.yml` changes |
| Image + deploy | `docker compose up -d --build` | migrations run at start in the `janus` container; see [docs/operations.md](docs/operations.md) |

Before handing over, run backend tests, ruff, frontend tests and the type check; run the build when frontend code
changed. Report the real results.

Local development without Docker is possible but not scripted: FastAPI with `uvicorn app.main:app` (from
`backend/`, with `JANUS_DATABASE_URL` and `JANUS_INTERNAL_TOKEN`) and `npm run dev` in `frontend/` with
`BACKEND_URL`, the same `JANUS_INTERNAL_TOKEN`, `AUTH_SECRET`, `AUTH_URL` and `JANUS_DATABASE_URL`/`AUTH_DATABASE_URL`
(run `node scripts/migrate-auth.mjs` once). The sentinel needs raw sockets on the host network; prefer the tests.

## Conventions

### Backend (Python 3.12, FastAPI, SQLAlchemy 2, pydantic v2)

- Modules are small and named after the domain (`guests.py`, `approval.py`); HTTP lives in `app/api/<area>.py`,
  rules in plain functions that take a `Session` and are tested without HTTP.
- Errors: `HTTPException` with one readable sentence; `422` invalid input, `409` conflict or unsupported by the
  provider, `404` unknown resource or feature off, `502` provider unreachable, `503` not configured. Use
  `api/conflicts.py::commit_or_409` where a unique constraint can race.
- Record every user-visible change with `events.record_event` (payload without secrets). New notifiable events
  follow "Add a notification" below.
- Provider calls raise `ProviderError` (`status=4xx` for a one-off refusal, anything else marks the role down). Core
  code asks `providers.runtime` for a capability; it never imports `app.providers.<kind>`.
- Editable settings use `settingsstore.OverlayStore` (env default + stored override, secrets sealed by
  `secretbox`); network fields go through `netconfig.validate`.
- MACs only through `net/mac.normalize_mac`; hostnames only through `net/names.hostname_for`; addresses only
  through `net/ipplan.check_assignment` / `next_free`.
- Jobs are `*_once(session_factory, ...)` functions, committed by the job, easy to call from tests with fakes.
- Comments explain *why* (a rule, a provider quirk), not what the next line does. Keep the existing density.

### Frontend (Next.js 16 App Router, React 19, Tailwind 4, better-auth)

- Next.js 16 differs from older versions: read the relevant guide in `frontend/node_modules/next/dist/docs/` before
  using an API you are not sure about (middleware is `proxy.ts`, route params are promises).
- Pages under `app/(app)/` are client components that load data with `lib/use-resource.ts` and write with
  `lib/api.ts` (`api.get/post/put/patch/del`); every successful write fires `janus:changed` so open resources reload.
- Use the primitives in `components/ui.tsx` (`Button`, `Card`, `Field`, `Notice`, `Chip`, ...) and the theme tokens
  of `app/globals.css` (`text-muted`, `bg-card`, `border-line`, `text-bad`, ...); no new colours inline except group
  colours.
- Gate optional UI on `useFeatures()` (`hasCapability`, `lanOnlyAllowed`, `features.guests`, `features.notify`),
  never on provider names or env variables.
- Types of API payloads live in `lib/types.ts`; keep them in step with the backend models.
- Tests sit next to the code as `*.test.ts(x)` and mock `fetch` / `authClient`; use `lib/test-data.ts` builders.

### Both

- Documentation and UI text in English, plain and short.
- Examples, fixtures and tests use only documentation MACs `00:00:5E:00:53:xx` / `02:00:5E:00:53:xx` and
  documentation-friendly IPs; `tests/test_repo_hygiene.py` fails on anything else.
- Tests never reach the network: use the fakes in `backend/tests/fakes.py` / `fakes_provider.py`, `respx`, or a
  loopback address (the `_no_network` fixture blocks everything else).

## Database migrations

- Models in `backend/app/models.py`; one hand-written Alembic revision per change in
  `backend/migrations/versions/`, named `00NN_<what>.py` with `revision = "00NN"` and `down_revision` the previous
  one; implement `downgrade()` too.
- Data migrations are allowed in the same revision (see `0008_provider_settings.py`, `0009_guests.py`); new event
  types in `notify/catalog.py` need their `notification_rules` rows seeded there.
- `tests/test_migrations.py` checks that the migrated schema matches the models and that seeds match
  `notify/store.default_rule_rows()`: run it after every model or migration change.
- Migrations run automatically when the `janus` container starts (`alembic upgrade head`). Never edit a revision
  that has been deployed; add a new one. The better-auth schema `auth` is migrated by `scripts/migrate-auth.mjs`
  (keep its options identical to `lib/auth/server.ts`).

## Do not break: checklist before and after a change

Before:

- [ ] Read the sections of [docs/features.md](docs/features.md) for every feature the change touches, including
      their **Invariants** and **Open questions**.
- [ ] Find the tests listed there and run them once to know the baseline.

While changing:

- [ ] Keep the safety rules of the sync engine: unmanaged entries never removed, no duplicate IP/MAC written,
      nothing written in `dry-run`, a new DHCP box always back to `dry-run` (F7).
- [ ] Keep the live "is it still serving DHCP?" check before switching providers (F8).
- [ ] Never degrade an unsupported policy silently; refuse with `409` (F6).
- [ ] Secrets stay sealed at rest, booleans in responses, out of events and logs (F21).
- [ ] Password sign-in must keep working without the backend or an IdP (F27); the browser must never reach
      `/api/internal/*` (F28).
- [ ] New routers are mounted with `dependencies=protected` in `main.py`.

After:

- [ ] Add or update tests for the changed behaviour (backend and/or frontend).
- [ ] Update the feature's section in [docs/features.md](docs/features.md) (behaviour, entry points, tests,
      invariants) and the traceability appendix when files are added or moved; update
      [docs/configuration.md](docs/configuration.md) for new variables and settings, [docs/operations.md](docs/operations.md)
      for new commands or metrics, [docs/design.md](docs/design.md) for a new decision.
- [ ] Run the commands of "Run, test, lint" and report the results.

## How to

### Add a feature

1. Write its section in `docs/features.md` first (purpose, rules, entry points, data, invariants).
2. Model + migration if it stores data; domain function(s) with a `Session`; route in `app/api/<area>.py`, included
   in `main.py` with the protected dependencies.
3. If it is optional, add an entry to `features.py::FEATURE_PROVIDERS` and gate the nav item in `lib/nav.ts` or the
   settings card in `app/(app)/settings/sections/index.ts`.
4. Page or component in `frontend/app/(app)/...`, types in `lib/types.ts`.
5. Tests on both sides; update the docs listed in the checklist.

### Add a network provider

Follow [docs/providers/adding-a-provider.md](docs/providers/adding-a-provider.md): copy
`backend/app/providers/_template/` to `backend/app/providers/<kind>/`, fill `SPEC`, implement the protocol of every
declared capability, add env fields to `app/config.py` and pass them in `docker-compose.yml` to `janus`,
`janus-worker` and `janus-sentinel`, test with respx; `scripts/test.sh tests/providers` runs the contract tests on it.
Frontend pages are optional (`frontend/providers/<kind>/index.ts` + one line in `providers/registry.ts`). Add a
feature section to `docs/features.md` like F9/F10.

### Add a notification

1. `record_event(db, "<area>.<what>", mac, payload)` where it happens (no secrets in the payload).
2. `EventSpec` in `backend/app/notify/catalog.py` (label, priority, `always`, `maintenance_muted`, default channels).
3. A branch in `backend/app/notify/render.py` (title, body, link) with a test in `tests/test_notify_render.py`.
4. A new migration seeding its two `notification_rules` rows (email, gotify) with the catalogue defaults.
5. A sentence in `frontend/lib/events.ts` (`describeEvent`, `EVENT_TYPES`), optionally a hint in
   `app/(app)/notifications/rules-table.tsx`.
6. Update the defaults table in `docs/operations.md#notifications` and F16/F17 in `docs/features.md`.

### Add a setting

- Network-related: a field in `netconfig.NetConfig` with its validation in `validate`, the env default in
  `config.py`, `NetworkPatch` in `api/settings.py`, `NetworkField`/`AppSettings` in `lib/types.ts`, the input in
  `app/(app)/settings/page.tsx` (`NET_LAYOUT`); add it to `RESTART_FIELDS` if the sentinel binds it at start-up.
- A group of options with env defaults (like a channel): an `OverlayStore` with `StoreField`s (validators,
  `secret=True` for secrets), routes `GET/PUT`, a settings card with `SecretInput` for secrets.
- Document it in [docs/configuration.md](docs/configuration.md) (variable and Settings sections).

## Git

- Work on a branch (`feat/...`, `fix/...`, `docs/...`, `chore/...`), Conventional Commits, small commits; open a PR
  to `main` on `mattia-longobardo/Janus`. Never commit `.env`, `janus/` (runtime data and backups) or real MACs.
