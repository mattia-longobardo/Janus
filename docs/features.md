# Feature catalogue

Every feature Janus has, written from the code: what it does, the rules it follows, where it lives and which
tests guard it. Read the section of every feature you touch **before** changing code, and update it in the same
commit as the change. The design behind these features is in [design.md](design.md); operations (deploy, backup,
cutover) are in [operations.md](operations.md) and the variables in [configuration.md](configuration.md).

Conventions used below:

- **Entry points** list API routes (all under `/api`, all protected by the internal token except `/api/health`),
  background jobs, CLI commands and web pages.
- **Tests** are the safety net: `backend/tests/...` run with `scripts/test.sh`, frontend tests with `npm test` in
  `frontend/`. A feature with no test says so.
- **Invariants** are rules a change must not break. Several are guarded by tests; the others are guarded by this
  document only.
- **Open question** marks behaviour that the code makes ambiguous or that disagrees with a label in the UI or an
  older document. Do not "fix" one silently: ask, then update this file.

| # | Feature | # | Feature |
|---|---|---|---|
| [F1](#f1-device-inventory) | Device inventory | [F17](#f17-notifications) | Notifications |
| [F2](#f2-groups-and-the-ip-plan) | Groups and the IP plan | [F18](#f18-notification-channels-integrations) | Notification channels (Integrations) |
| [F3](#f3-lan-observation-sentinel) | LAN observation (sentinel) | [F19](#f19-maintenance-windows) | Maintenance windows |
| [F4](#f4-presence-and-offline-alerts) | Presence and offline alerts | [F20](#f20-network-and-general-settings) | Network and general settings |
| [F5](#f5-device-health-markers) | Device health markers | [F21](#f21-settings-store-and-secretbox) | Settings store and secretbox |
| [F6](#f6-approval-quarantine-and-blocking) | Approval, quarantine and blocking | [F22](#f22-optional-features-and-ui-gating) | Optional features and UI gating |
| [F7](#f7-reservation-sync-and-sync-modes) | Reservation sync and sync modes | [F23](#f23-network-map) | Network map |
| [F8](#f8-network-provider-framework) | Network provider framework | [F24](#f24-import-and-export) | Import and export |
| [F9](#f9-pi-hole-provider-and-dhcp-cutover) | Pi-hole provider and DHCP cutover | [F25](#f25-metrics) | Metrics |
| [F10](#f10-unifi-provider) | UniFi provider | [F26](#f26-health-checks-and-heartbeats) | Health checks and heartbeats |
| [F11](#f11-guests) | Guests | [F27](#f27-sign-in-and-users) | Sign-in and users |
| [F12](#f12-device-identification) | Device identification | [F28](#f28-api-trust-boundary) | API trust boundary |
| [F13](#f13-port-scanning-and-services) | Port scanning and services | [F29](#f29-cli) | CLI |
| [F14](#f14-dns-activity-and-analysis) | DNS activity and analysis | [F30](#f30-app-shell-live-refresh-and-theme) | App shell, live refresh and theme |
| [F15](#f15-dns-health-check) | DNS health check | [F31](#f31-test-and-repository-guards) | Test and repository guards |
| [F16](#f16-event-log) | Event log | [A](#appendix-traceability) | Appendix: traceability |

---

## F1. Device inventory

**Purpose.** One row per device Janus knows, identified by MAC, with a human name, a DNS-safe hostname, a group,
an optional static IP and an access level. Everything else (reservations, alerts, scans) hangs off this row.

**Behaviour.**

- `Access` (`models.py`) is one of `authorized` (full network), `lan_only`, `pending`, `guest`, `blocked`.
  "Approved" always means `authorized` or `lan_only` (`APPROVED` sets in several modules).
- MACs are stored normalised, upper case, colon separated (`net/mac.py::normalize_mac`); any separator
  (`:`, `-`, `.`, spaces) is accepted on input, anything else raises `ValueError`.
- A MAC is *private* (randomised) when the locally administered bit is set (`is_private_mac`); private MACs never
  get an OUI vendor.
- `hostname` is derived from `name` by `net/names.py::hostname_for`: ASCII-folded, lower case, `[a-z0-9-]`, at most
  63 characters, `device` when empty, and suffixed `-2`, `-3`, ... on collision. Renaming a device regenerates the
  hostname. `hostname`, `mac` and `static_ip` are unique in the database.
- A device may exist without a MAC (CSV import of a placeholder); such a device cannot be approved or be a guest.
- `GET /api/devices` hides guests unless `?access=guest`; it is sorted by static IP (devices without one last),
  then name, and each device is annotated with `issues`/`health` (F5).
- `PATCH /api/devices/{id}` edits name, group, static IP and access, with these rules:
  - a static IP is checked against the plan and the group range (`check_assignment`, see F2) whenever it or the
    group changes; a device without a group cannot get one (`422 device has no group: approve it first`);
  - `access=guest` is refused (`422`, use `/guest`); moving to `authorized`/`lan_only` from another access needs a
    MAC, a group and a static IP, otherwise `422 ... use /approve` (a pending device is approved only through F6);
  - every real change is logged as one `device.updated` event with `changes: {field: [old, new]}`;
  - a unique-constraint race becomes `409` (`api/conflicts.py::commit_or_409`).
  - The edit is not pushed to the DHCP provider at once: the next reconcile (F7) carries it.
- `DELETE /api/devices/{id}` logs `device.deleted` and removes the row (its links cascade, F23). The DHCP
  reservation is dropped by the next reconcile because Janus remembers the MACs it wrote (F7). A deleted device that
  is still connected comes back as `pending` (F3).

**Configure.** Nothing.

**Entry points.** `api/devices.py` (`GET/PATCH/DELETE /api/devices[/{id}]`); pages `/devices` (search, access
filter, group chips, "Needs attention" chip, Excel download), `/devices/[id]` (identity, network, open ports, DNS,
advice, events, edit form with "First free"), the approved-devices table on `/` (Overview); `components/device-table.tsx`
(sortable, paginated), `lib/filter.ts`, `lib/delete-device.ts`, `lib/format.ts`.

**Data.** `devices` (see [design.md](design.md#data-model)).

**Tests.** `test_api_devices.py`, `test_mac_names.py`, `test_models.py`; frontend `components/device-table.test.tsx`,
`lib/filter.test.ts`, `lib/format.test.ts`.

**Invariants.**

- Never store a MAC that did not go through `normalize_mac`; never compare raw MAC strings.
- `hostname` is always produced by `hostname_for` against the other devices' hostnames.
- Guests are never returned by the plain device list (their own page and counter exist).
- `access` reaches `authorized`/`lan_only` only with MAC + group + static IP.

---

## F2. Groups and the IP plan

**Purpose.** Groups split the subnet into ranges (People, Cameras, ...). A device's static IP always comes from its
group's range; groups also carry the look (colour, icon), the default access, the offline alert threshold and the
port-scan schedule.

**Behaviour.**

- `IpRange`, `NetworkPlan`, `check_assignment`, `check_group_range`, `next_free`, `infer_group_range` in
  `net/ipplan.py` are the only rules for addresses. An assignable address is inside the subnet, not the network or
  broadcast address, not the gateway, not in the quarantine pool, not in the guest pool, inside the group range and
  not already taken.
- Group ranges must be inside the subnet and overlap neither the quarantine pool, nor the guest pool, nor another
  group (`check_group_range`).
- `POST /api/groups`: name 1-64 chars and unique (`409`), colour `#RRGGBB`, icon 1-32 chars, `default_access` only
  `authorized` or `lan_only`, `offline_alert_hours >= 1` or null, `scan_interval_hours` 1-720 (default 168).
- `PATCH /api/groups/{id}`: required fields cannot be set to null (`422`); changing the range is refused with `409`
  when a member's static IP would fall outside it.
- `DELETE /api/groups/{id}` is refused (`409`) while the group has devices.
- `GET /api/groups/{id}/next-free-ip[?device_id=]`: lowest assignable address; `device_id` ignores that device's
  own address (used by "First free" in the device editor).
- `POST /api/groups/{id}/compact?dry_run=true|false` ("Close gaps"): renumbers the members with a static IP from the
  start of the range, keeping their order. The gateway and the providers' own IPs (`runtime.infrastructure_ips`)
  are *pinned* and never moved or handed out. With `dry_run=false` it writes the new addresses in two steps (clear,
  then set, to dodge the unique constraint) and logs `group.compacted`.
- The IP plan page draws the 256 addresses of the subnet as a grid with groups, devices, reserved slots, the
  quarantine pool (only with a provider that has `QUARANTINE`) and the guest pool (used = guests whose current
  address is inside it), and downloads `janus-ip-plan.csv` (`name,mac,static_ip,group`, pending devices excluded).
- The Groups page edits groups (custom colour picker, icon, range, default access, offline alert, scan schedule),
  shows a read-only quarantine row and a Guests row (F11).

**Configure.** Nothing beyond the network settings (F20).

**Entry points.** `api/groups.py`; pages `/groups`, `/ip-plan`; `components/compact-group.tsx`,
`components/custom-color.tsx`, `components/look-picker.tsx`, `components/hours-rule.tsx`,
`components/ip-plan-export.ts`, `lib/ipplan.ts`, `lib/group-icons.tsx`.

**Data.** `groups`; `devices.group_id`, `devices.static_ip`.

**Tests.** `test_ipplan.py`, `test_api_groups.py` (incl. `compact_closes_gaps_in_order_and_keeps_pinned_addresses`);
frontend `app/(app)/groups/groups-page.test.tsx`, `components/compact-group.test.tsx`,
`components/custom-color.test.tsx`, `components/ip-plan-export.test.ts`, `lib/ipplan.test.ts`.

**Invariants.**

- Every static IP Janus writes passed `check_assignment` with the current plan.
- The gateway and the providers' host IPs are never assigned to a device (compaction and planning).
- Ranges never overlap each other or the quarantine/guest pools.

**Open questions.**

- The Close-gaps preview says "The DHCP provider gets the new reservations at once", but `compact_group` only
  commits: the provider receives them at the next reconcile (up to `JANUS_RECONCILE_INTERVAL_S`, 300 s).
- `lib/ipplan.ts` indexes addresses by their last octet, so the IP plan grid assumes a `/24`, while the backend
  accepts subnets from `/16` to `/30` (F20).

---

## F3. LAN observation (sentinel)

**Purpose.** See every device on the LAN without being in the traffic path: passive sniffing plus a periodic ARP
sweep, turned into devices, sightings and security events.

**Behaviour.**

- `sentinel/main.py` runs on the host network with `cap_net_raw` (file capability on `janus-sniff`). BPF filter:
  ARP, UDP 67/68 (DHCP), 137 (NetBIOS), 1900 (SSDP) and mDNS **answers** only (`udp port 5353 and udp[10] & 0x80 != 0`).
- Packets go into a bounded queue (5000); a full queue drops packets and logs the count instead of blocking. Every
  ~2 s the batch is parsed and recorded; each observation is recorded in its own savepoint, so one bad packet
  never loses the others.
- Every `sweep_interval_s` (default 60, F20) the sentinel ARP-sweeps the subnet, writes the `sentinel.heartbeat`
  setting and touches `/tmp/janus-sentinel.heartbeat`; when the DNS provider can be probed it also probes it (F15).
- The process exits (Docker restarts it) when the sniffer thread dies or when a field it binds at start-up changes
  (`netconfig.RESTART_FIELDS`: subnet, gateway, quarantine pool, interface, sweep interval).
- `sentinel/observe.py` parses: ARP requests/replies (MAC + sender IP), DHCP client messages (DISCOVER, REQUEST,
  INFORM: requested or client IP, hostname option 12, vendor class, parameter list), mDNS answers (hostname from an
  A record of the sender's own address, `_service._tcp` PTRs, model from TXT `md=`/`model=`/`am=`/`ty=`/`usb_MDL=`;
  sleep-proxy answers for other hosts are ignored), NetBIOS own-name registrations, SSDP `NOTIFY`/`200` `SERVER`
  header. Order of precedence: DHCP, mDNS, NetBIOS, SSDP, ARP.
- `sentinel/record.py::record_observation`:
  - unknown MAC: the first MAC seen on the gateway IP while `gateway.mac` is unset becomes an `authorized` device
    named "Gateway" (`device.gateway` event); any other unknown MAC becomes `pending`, named after the DHCP hostname
    or `Unknown xx:xx:xx`, with a `device.new` event;
  - `device.private_mac`: a new private MAC whose DHCP hostname equals the hostname of an approved device with
    another MAC (the phone rotated its MAC);
  - every observation sets `online`, `last_seen`, `first_seen` (once) and, for DHCP, `dhcp_hostname`; `last_ip` is
    updated only for addresses inside the subnet (link-local and `0.0.0.0` blips are ignored);
  - `ip.conflict`: both MACs keep answering for the same IP within 2 minutes (a DHCP handover is not a conflict),
    at most once per IP per hour; the payload names `owner` (the reservation holder) and `claimant`;
  - `device.ip_mismatch`: an approved device with a static IP seen twice in a row on another in-subnet address that
    is not in the quarantine pool, at most once per device and address per 24 h;
  - sightings are thinned: DHCP always; mDNS/NetBIOS/SSDP when the IP or the announced data changed or 6 h passed;
    ARP when the IP changed or 10 minutes passed.
- Sightings older than `JANUS_SIGHTING_RETENTION_DAYS` (30) are purged by the worker (F4).

**Configure.** `JANUS_SENTINEL_INTERFACE`, Settings → Network (interface, subnet, gateway, quarantine, sweep).

**Entry points.** Container `janus-sentinel` (`entrypoint.sh sentinel`); `sentinel/main.py`, `observe.py`,
`record.py`.

**Data.** `devices`, `sightings`, `events`, settings `gateway.mac`, `sentinel.heartbeat`, `dns.last_ok`.

**Tests.** `test_observe.py`, `test_record.py`, `test_sentinel_main.py`.

**Invariants.**

- The sentinel never writes to the network except ARP sweeps (and the DNS probe); it never blocks on the database.
- A new MAC is always `pending` (except the first gateway MAC); nothing ever auto-approves.
- Alerts are rate-limited (conflict 1 h per IP, mismatch 24 h per device/IP); keep the windows when changing them.
- Only in-subnet IPv4 addresses become `last_ip`.

---

## F4. Presence and offline alerts

**Purpose.** Know which devices are online and alert when an important device has been away for too long.

**Behaviour** (`presence.py`, worker job `presence`, every `JANUS_PRESENCE_INTERVAL_S` = 60 s):

- First the worker tracks maintenance windows (`maintenance.start`/`maintenance.end` events and the
  `maintenance.active` setting, F19) and checks the sentinel heartbeat: older than 3 × sweep interval marks the
  sentinel down (`infra.down` with `service: sentinel`, rendered "Scanner"); fresh again marks it up.
- Only while the sentinel is healthy: devices unseen for `JANUS_PRESENCE_TIMEOUT_S` (300 s) go `online=false`, and
  `device.offline` is raised for approved devices whose group has `offline_alert_hours`, once the time offline
  *minus the time inside alert-muting maintenance windows* exceeds the threshold. One alert per outage (an event
  after the current `last_seen` already exists → none).
- Sightings older than the retention are deleted on every run.

**Configure.** Group "Alert when a member is offline for more than N hours"; `JANUS_PRESENCE_*`.

**Entry points.** `worker.py::presence_once`, `check_sentinel`, `track_maintenance`; `presence.py`.

**Data.** `devices.online/last_seen`, `events`, settings `sentinel.down_since`, `maintenance.active`.

**Tests.** `test_presence.py`, `test_worker.py` (`sentinel_heartbeat_outage_is_reported_once`,
`offline_alerts_wait_while_scanner_is_down`, `presence_once_purges_old_sightings`, `maintenance_start_and_end_are_logged`).

**Invariants.** No offline evaluation while the sentinel is down (otherwise every device would "go offline").
Maintenance time never counts toward the offline threshold.

---

## F5. Device health markers

**Purpose.** Flag devices that need attention, everywhere they are drawn.

**Behaviour** (`health.py::annotate`): each device gets `issues` (kind, severity, message) and the worst
`health` (`ok` < `warning` < `critical`):

- `ip_mismatch` (critical): approved, online, with a static IP, currently on another in-subnet address;
- `ip_conflict` (critical): another online device has the same in-subnet `last_ip`;
- `risk`: one per open, not muted, risky service (`high` → critical, `warning` → warning; F13).

The UI shows a coloured ring and icon (table, map), a banner on the device page, the "Needs attention" chip on
Overview and Devices, and the metric `janus_devices_health{health}` (F25).

**Entry points.** `health.py`; `components/health.tsx`; used by `api/devices.py`, `api/guests.py`, `metrics.py`.

**Tests.** `test_health.py`; frontend `components/health.test.tsx`, `components/device-table.test.tsx`.

**Invariants.** Muted services never make a device unhealthy. Health is computed on read, never stored.

---

## F6. Approval, quarantine and blocking

**Purpose.** Unknown devices wait in `pending` (with Pi-hole: in a quarantine pool without a gateway) until an
admin approves them with a name, group, access and static IP, admits them as guests (F11) or blocks them.

**Behaviour.**

- `POST /api/devices/{id}/approve {name, group_id, access?, static_ip?}` (`api/approval.py`, `approval.py`):
  - unknown group → `422`; `access` defaults to the group's `default_access` and must be `authorized`/`lan_only`;
  - the DHCP provider must support the policy (`authorized`→`FULL`, `lan_only`→`LAN_ONLY`), otherwise `409
    "<label> does not support <policy>"` *before* anything is saved;
  - a device without a MAC → `422`; the IP is the given one (checked, F2) or the next free one in the range (none
    left → `422`); name sets the hostname; event `device.approved` (with `previous_access`);
  - then enforcement (`_enforce`), whose result is returned as `enforcement`:
    `"no provider"` (no DHCP provider with reservations: Janus only records), `"dry-run"`, `"applied"` (sync applied
    now and, when the device's current IP is in the quarantine pool, its lease revoked with `FORCE_RENEW`) or
    `"failed: <error>"` (the approval is still saved).
- `POST /api/devices/{id}/block`: sets `blocked` (from any access), event `device.blocked`, then the same
  enforcement, revoking the device's current lease in `apply`. A blocked device has no reservation on Pi-hole
  (lands in the quarantine pool) and a block flag on UniFi (F9, F10).
- Quarantine is a *provider* behaviour (`Capability.QUARANTINE`, only Pi-hole): unknown devices lease from the
  quarantine pool (`.240-.254` by default) with no router option. The UI uses quarantine wording only when the DHCP
  provider has that capability, and "in quarantine" only in `apply`.
- Pages: `/pending` (one card per pending device with what is known, its last 10 events and the approve form),
  the pending strip and mobile quick-approve card on `/` (Overview), "Approve…" on the device page. The approve
  form needs an explicit group, proposes the next free IP, hides "LAN only" when the provider cannot enforce it
  (`lanOnlyAllowed`), and offers "Approve as guest" only when guests are enabled.

**Configure.** Group default access; Settings → Network quarantine pool (shown only with `QUARANTINE`).

**Entry points.** `api/approval.py`, `approval.py`, `api/roles.py::get_dhcp`; pages `/pending`, `/`, `/devices/[id]`;
`components/approve-form.tsx`, `components/overview-quick-approve.tsx`.

**Data.** `devices.access/static_ip/group_id/name/hostname`, `events`.

**Tests.** `test_approval.py`, `test_api_approval.py`; frontend `components/approve-form.test.tsx`,
`lib/provider-status.test.ts` (`offers LAN only when ...`).

**Invariants.**

- Never degrade an unsupported policy to `FULL`: refuse with `409` before saving.
- Approval and block are saved even when enforcement fails; the result string says so.
- Enforcement writes only in `apply`; a `dry-run` approval never touches the provider.

---

## F7. Reservation sync and sync modes

**Purpose.** Keep the DHCP provider's reservations equal to what Janus wants, safely: never touch what Janus does
not own, never write a configuration that breaks the provider, and write nothing at all until an admin says so.

**Behaviour.**

- Desired state (`enforcement/reservations.py::desired_reservations`): approved devices with MAC and static IP
  (policy `FULL` or `LAN_ONLY`), guests (`GUEST`, no IP) and blocked devices (`BLOCKED`, no IP), each only if the
  provider lists that policy.
- Diff (`diff_reservations`): entries the provider cannot read as reservations, or whose MAC is not *managed*, are
  `unmanaged` (reported, never removed). Managed MACs = every MAC Janus knows plus every MAC it has ever written to
  that provider (`provider.<kind>.written_macs`; on the very first run, the entries already in Janus' exact
  canonical format). Own entries that are not desired or not canonical are removed; missing desired ones added.
  An addition that would duplicate the IP or MAC of a kept or unmanaged entry is refused into `failed`.
- `apply_sync` removes first, then adds, one entry at a time. A 4xx from the provider (`ProviderError.rejected`)
  goes into `failed` and the sync continues; a transport error/5xx aborts. The progress is always recorded
  (`sync.applied` with added/removed, `sync.failed` with failures, written MACs) even when it aborts. Then the
  provider's optional `after_sync(db)` hook runs (Pi-hole guest range).
- Sync mode (`syncmode.py`): `dry-run` (default) or `apply`, stored in setting `sync.mode` (wins over
  `JANUS_SYNC_MODE`); every change logs `sync.mode` with `from`, `to`, `actor`.
- Worker job `reconcile` (every `JANUS_RECONCILE_INTERVAL_S` = 300 s): resolves the DHCP provider; none → clears an
  open DHCP outage silently; a configuration that cannot be resolved → `infra.down`; then plan (dry-run) or apply.
  A `ProviderError` marks the DHCP role down (`infra.down`, `dhcp.down_since`); success marks it up (`infra.up`).
- **DHCP identity** (`runtime.record_dhcp_identity`, setting `dhcp.identity` = kind plus URL): when the box holding
  DHCP changes (Settings or env), the worker forces `dry-run` (`actor: system`) before writing anything; switching
  to `apply` (API/CLI) records the reviewed box so the worker keeps the switch.
- Switching modes: `POST /api/sync/mode {"mode"}` (actor `web`), `janus sync-mode` (actor `cli`), Pi-hole
  `cutover`/`rollback` (F9). `apply` is refused (`409` / exit 2) without a DHCP provider taking reservations. The
  web switch (Settings → Access control → Enforcement) is shown to admins only and, before `apply`, shows the
  counts of `GET /api/sync/plan` and asks for confirmation. Changing the DHCP provider always returns to `dry-run`
  (F8).
- `GET /api/sync/plan` (404 without provider, 502 when unreachable) and `POST /api/sync/apply` (writes the diff
  **whatever the mode**: an explicit manual action; no page calls it) and `janus sync [--apply]` expose the engine.

**Configure.** `JANUS_SYNC_MODE` (initial), `JANUS_RECONCILE_INTERVAL_S`, `JANUS_RESERVATION_LEASE`.

**Entry points.** `enforcement/sync.py`, `enforcement/reservations.py`, `syncmode.py`, `api/sync.py`,
`worker.py::reconcile_once`, `cli.py` (`sync`, `sync-mode`); Settings → Access control
(`app/(app)/settings/sections/enforcement.tsx`); sidebar provider pill.

**Data.** Settings `sync.mode`, `dhcp.identity`, `provider.<kind>.written_macs`, `dhcp.down_since`; events
`sync.applied`, `sync.failed`, `sync.mode`, `infra.down`/`infra.up`.

**Tests.** `test_enforcement.py`, `test_api_sync.py`, `test_syncmode.py`, `test_worker.py` (reconcile_*, *identity*),
`test_cli.py`, `providers/test_contract.py`; frontend `app/(app)/settings/sections/enforcement.test.tsx`.

**Invariants.**

- Unmanaged entries are never removed; a provider entry Janus cannot interpret has `reservation=None`.
- Never write two reservations with the same IP or MAC (dnsmasq stops answering DNS on such a config).
- Remove before add, so a freed IP can be reused in the same run.
- Nothing is written in `dry-run` by the worker or by approve/block/guest actions.
- A new DHCP box is never written to before an admin switches to `apply` again.

**Open question.** The backend does not check the user's role for `POST /api/sync/mode` (any signed-in user can
call it through the proxy); the admin-only rule lives in the UI. This is documented as intended in
[configuration.md](configuration.md#other-settings); keep it in mind before adding roles to the API.

---

## F8. Network provider framework

**Purpose.** Janus talks to routers through plugins. The rest of the code asks for a *capability* in a *role*,
never for a provider name.

**Behaviour.**

- `providers/base.py`: `Role` (`dhcp`, `dns`), `Capability` (`RESERVATIONS`, `FORCE_RENEW`, `QUARANTINE`,
  `DHCP_SERVER`, `CLIENT_INVENTORY`, `DNS_QUERY_LOG`, `DNS_PROBE`, each bound to a role by `CAPABILITY_ROLE`),
  `Policy` (`FULL`, `LAN_ONLY`, `GUEST`, `BLOCKED`), `Reservation`, `CurrentEntry`, `DnsQuery`, `ProviderError`
  (`rejected` = 4xx), the protocols (`ReservationStore`, `LeaseControl`, `DnsQueryLog`, `DnsProbe`,
  `DhcpServerState`, `HealthCheck`) and `ProviderSpec`.
- `providers/registry.py` discovers every package under `app/providers/` that exports `SPEC` (folders starting
  with `_` are skipped; the folder name must equal `SPEC.kind`, else `RegistryError`). `registry.override` adds
  fakes in tests.
- `providers/config.py` (setting `providers.config`): per role `{"kind", "config": overrides}`, `null` (off) or,
  for DNS, `{"same_as": "dhcp"}` (one shared config and session). A missing role follows the env
  (`JANUS_DHCP_PROVIDER`/`JANUS_DNS_PROVIDER`; unset means Pi-hole for both when `JANUS_PIHOLE_PASSWORD` is set).
  Overrides equal to the env default are not stored; secret fields are sealed (F21) and a missing secret in a
  patch keeps the saved one. An invalid saved config falls back to the env defaults, and to "role off" if those are
  invalid too. `save_role`:
  - refuses a kind that is unknown or cannot hold the role (`422`);
  - when the DHCP kind changes away from a provider with `DHCP_SERVER`, asks the box whether it still serves DHCP
    (`dhcp_server_active`) **whatever the sync mode**; serving or unreachable → `409` (`ProviderInUse`, "run janus
    rollback first");
  - when DNS was `same_as` DHCP and the new DHCP provider cannot serve DNS, DNS is detached onto its own copy of
    the old config (`dns_detached`);
  - every DHCP kind change forces `dry-run` (`forced_dry_run` in the `settings.providers` event).
- `providers/runtime.py` answers: `reservation_provider` (DHCP with `RESERVATIONS`: kind, policies, opener),
  `dns_query_log`, `dns_probe_host`, `has_capability`, `policies`, `providers_feature` (per role kind, label,
  capabilities of that role only, `shared`, `down_since`, DHCP `policies`), `infrastructure_ips`.
- API: `GET /api/providers` (available kinds with JSON schema without secret defaults, current role views with
  secrets as booleans), `PUT /api/providers/{role}` (`{kind, config}` | `{kind: null}` | `{same_as: "dhcp"}`),
  `POST /api/providers/{role}/test` (calls `HealthCheck.check()`; `{ok, detail}`). Each spec's `router` is mounted at
  `/api/providers/<kind>` behind the internal token; each spec's `cli` registers `janus` subcommands.
- Frontend: Settings → Network providers (one row per role; "Same as DHCP" when the DHCP provider serves DNS;
  generic form from the JSON schema, or the provider's own `SettingsForm`; warning before switching DHCP; "Test
  connection" only on saved settings). `frontend/providers/registry.ts` maps kinds to pages, listed in the sidebar
  only while the provider holds the page's role and capability (`providerNav`) and guarded by `ProviderPageGate`.

**Configure.** Settings → Network providers; `JANUS_DHCP_PROVIDER`, `JANUS_DNS_PROVIDER` and each provider's env.

**Entry points.** `providers/base.py`, `registry.py`, `config.py`, `runtime.py`, `api/providers.py`, `api/roles.py`;
`app/(app)/settings/sections/providers.tsx`, `app/(app)/integrations/[kind]/[[...slug]]/page.tsx`,
`providers/registry.ts`, `providers/types.ts`, `providers/generic-config-form.tsx`,
`providers/provider-page-gate.tsx`, `lib/provider-status.ts`. Guide: [providers/adding-a-provider.md](providers/adding-a-provider.md).

**Data.** Settings `providers.config`, `dhcp.down_since`, `dns.down_since`.

**Tests.** `providers/test_contract.py`, `providers/test_registry.py`, `test_provider_config.py`,
`test_api_providers.py`, `test_api_features.py`; frontend `app/(app)/settings/sections/providers.test.tsx`,
`providers/generic-config-form.test.tsx`, `providers/provider-page-gate.test.tsx`,
`app/(app)/integrations/[kind]/[[...slug]]/page.test.tsx`, `lib/provider-status.test.ts`.

**Invariants.**

- Nothing outside `app/providers/` imports `app.providers.<kind>`; a provider never imports another (contract test).
- A DNS-only role never exposes DHCP capabilities (`role_capabilities`).
- The LAN never gets two DHCP servers through a Janus action: the live `dhcp_server_active` check stays.
- UI gating uses `features.providers` capabilities and policies, never provider names.

---

## F9. Pi-hole provider and DHCP cutover

**Purpose.** Pi-hole v6 holds DHCP and DNS: reservations, quarantine, LAN-only, guests, DNS query log and probe,
and the tooling to take over DHCP from the router and give it back.

**Behaviour.**

- Spec (`providers/pihole/__init__.py`): roles DHCP+DNS; capabilities `RESERVATIONS`, `FORCE_RENEW`,
  `QUARANTINE`, `DHCP_SERVER`, `DNS_QUERY_LOG`, `DNS_PROBE`; policies `FULL`, `LAN_ONLY`, `GUEST` (never `BLOCKED`:
  a blocked device simply has no line); config `url`, `password` (secret), `lease` (`^(\d+[smhdw]?|infinite)$`, so
  nothing can inject into dnsmasq lines). Env defaults `JANUS_PIHOLE_URL`, `JANUS_PIHOLE_PASSWORD`,
  `JANUS_RESERVATION_LEASE`.
- Client (`client.py`): one login per URL shared by all callers (`SharedSession`, Pi-hole refuses parallel
  logins), re-login once on 401, 10 s timeout, every failure a `PiholeError` (with status for HTTP errors).
- Codec (`codec.py`): `dhcp.hosts` lines `mac[,set:lanonly],ip,hostname,lease`; guests `mac,set:guest,hostname,lease`.
  A line is canonical when it carries the configured lease; lines Janus cannot read keep their MAC/IP for the
  duplicate guard. Output is byte-identical to the pre-plugin format (tests).
- `after_sync`: keeps exactly one `dhcp-range=tag:guest,<start>,<end>,<lease>` line in `misc.dnsmasq_lines` (other
  lines untouched; nothing written when already right; removed when the pool is cleared). Without `app_sudo`
  Pi-hole answers 403: recorded once per distinct reason as `sync.failed` (setting
  `provider.pihole.guest_range_error`), not a crash.
- `force_renew` revokes the lease by IP; `dhcp_server_active` reads `dhcp.active`; `query_log` reads
  `/api/queries` (on-disk database for windows over 24 h); `probe_host` is the URL host; `check` counts reservations.
- Cutover tooling (`cutover.py`, `cli.py`, `api.py`):
  - `preflight` (`GET /api/providers/pihole/preflight`, `janus preflight`, exit 1 while not ready): Pi-hole holds
    the DHCP role; API reachable; DHCP state (info); write access (info, or checks the admin password during the
    cutover); the two quarantine `dhcp-option` lines present; guest range (info, written by the cutover); quarantine
    range valid; approved devices complete (MAC + static IP, gateway excluded); no duplicate IP/MAC; sync plan
    counts (info); a backup younger than 24 h in `JANUS_BACKUP_DIR` (`/app/backups`).
  - `janus backup`: `<timestamp>/pihole-teleporter.zip` + `janus.json` (every table except `sightings` and
    `alembic_version`).
  - `janus cutover --pihole-password-env VAR`: refuses when another provider (or none) holds DHCP; re-runs preflight
    with the admin password; then `app_sudo=true` → apply all reservations (and the guest range) → DHCP on with the
    quarantine pool as range, gateway as router, lease, no IPv6 → `apply` mode.
  - `janus rollback --pihole-password-env VAR`: removes Janus' guest range first, then DHCP off and `dry-run`
    whatever happened; if the guest range could not be removed it fails and leaves `app_sudo` on so it can be re-run;
    otherwise turns `app_sudo` off.
  - The admin password is read from the named env variable for one command and never stored.
- Page `/integrations/pihole/cutover` (sidebar "DHCP cutover", only while Pi-hole holds DHCP with `DHCP_SERVER`):
  runs the read-only preflight and shows each check. The cutover itself runs from [runbooks/cutover.md](runbooks/cutover.md).

**Configure.** `JANUS_PIHOLE_URL` (compose), `JANUS_PIHOLE_PASSWORD`, `JANUS_RESERVATION_LEASE`, `JANUS_BACKUP_DIR`;
Settings → Network providers.

**Entry points.** `providers/pihole/*`; `frontend/providers/pihole/*`.

**Tests.** `providers/pihole/test_client.py`, `test_codec.py`, `test_provider.py`, `test_cutover.py`, `test_cli.py`;
frontend `providers/pihole/cutover-page.test.tsx`; `tests/spikes/dnsmasq_guest/` (manual dnsmasq spike, not in CI).

**Invariants.**

- Never break Pi-hole DNS: no duplicate lines, lease validated, only Janus' own lines removed.
- Cutover order: write permission → reservations → DHCP on → `apply`. Rollback order: guest range → DHCP off →
  `dry-run` → `app_sudo` off.
- Never persist the admin password.

**Open question.** Pool exhaustion: with a full guest pool dnsmasq may fall back to the untagged quarantine range
(no router); to be verified on real FTL ([architecture.md](architecture.md#guests)).

---

## F10. UniFi provider

**Purpose.** A UniFi Network controller holds DHCP: fixed IPs, guest and blocked clients, reconnect, live client list.

**Behaviour** (`providers/unifi/`):

- Spec: role DHCP only; capabilities `RESERVATIONS`, `FORCE_RENEW`, `CLIENT_INVENTORY`; policies `FULL`, `GUEST`,
  `BLOCKED` (no `LAN_ONLY`: approving with it answers 409 and the UI hides the option). Config `url`, `username`,
  `password` (secret), `site` (`default`), `unifi_os` (true), `verify_tls` (false by default, self-signed consoles),
  `network_id` (empty: the network whose subnet contains Janus' gateway, resolved lazily).
- Client: classic API (`/proxy/network` prefix on UniFi OS), cookie session, CSRF token on writes (rotated from
  responses), re-login once on 401, `meta.rc == "error"` is a rejection (400).
- Mapping on known clients (`rest/user`): `FULL` = fixed IP on the LAN network; `GUEST` = known client without fixed
  IP and with the guest note; `BLOCKED` = block flag (`block-sta`). Janus writes `note = "janus:<policy>"` on every
  client it reserves and reads only clients with a `janus:` note as its own; hand-set fixed IPs or blocks are
  unmanaged and never altered. Removal undoes the policy and clears the note; clients are never forgotten.
- `force_renew` kicks the station (`kick-sta`); an offline station is not an error.
- `GET /api/providers/unifi/clients`: known and connected clients with uplink (AP or switch port), SSID, signal,
  uptime and the matching Janus `device_id`; 404 when UniFi does not hold DHCP, 502 when unreachable. Page
  `/integrations/unifi/clients` (sidebar "UniFi clients"), refreshed every 15 s, links known clients.

**Configure.** `JANUS_UNIFI_URL`, `JANUS_UNIFI_USERNAME`, `JANUS_UNIFI_PASSWORD`, `JANUS_DHCP_PROVIDER=unifi` or Settings.

**Tests.** `providers/unifi/test_client.py`, `test_provider.py` (36 cases incl. end-to-end apply against a fake
controller), `test_api.py`; frontend `providers/unifi/clients-page.test.tsx`.

**Invariants.** An admin note on a managed client is overwritten (documented); a client without the note is never
changed. Never claim `LAN_ONLY`.

**Open question.** Hardware verification on a real controller is pending ([architecture.md](architecture.md#unifi)).

---

## F11. Guests

**Purpose.** Visitors' devices get internet through a dynamic address from a guest pool, optionally for a limited
time, without a group or static IP.

**Behaviour.**

- A guest is a device with `access = guest`, `static_ip = NULL`, `group_id = NULL`, `guest_since` and an optional
  `guest_expires_at` (`guests.py`).
- Guests are allowed when the DHCP provider supports `GUEST` or there is no DHCP provider (Janus only keeps the
  list); otherwise create/admit/patch answer `409`, while list and removal keep working.
- `POST /api/guests {mac, name, expiry?}`: creates the device (or admits an existing *pending* one with that MAC;
  any other access → `422`). `POST /api/devices/{id}/guest {name, expiry?}` admits a pending device. Both log
  `guest.added` and enforce (F6 rules, with lease revocation of the quarantine address on admit).
- Expiry input: exactly one of `expires_at` (naive = local time zone), `expires_in_hours` (≤ 87 600, finite),
  `expires_on` (that day 23:59:59 local); must be in the future. `PATCH /api/guests/{id}` changes name/expiry or
  `clear_expiry` (not combinable with a new expiry).
- Global rules (setting `guests.settings`, `GET/PUT /api/guests/settings`): `auto_remove_hours` (from
  `guest_since`) and `inactive_remove_hours` (from `max(last_seen, guest_since)`), each off or 1-8760; plus the
  guests' `color` (`#4FC3D9`) and `icon` (`guest`), validated like a group's (invalid stored values fall back).
  The effective expiry is the guest's own one, else the earliest rule; the API returns `effective_expires_at` and
  `expiry_source` (`device`, `global`, `inactive`).
- Worker job `guests` (`JANUS_GUESTS_INTERVAL_S`, 60 s): deletes expired guests (`guest.expired`) and commits
  first; then, in `apply`, syncs and revokes their leases; a provider error is left to the next reconcile. A guest
  still connected comes back as `pending`.
- `DELETE /api/guests/{id}` logs `guest.removed`, deletes, enforces and revokes the lease.
- The guest pool is `network.guest_start/guest_end` (F20); Pi-hole writes it as a tagged range (F9).
- UI: `/guests` (soonest expiry first, source of the expiry, change expiry, remove, add by MAC; a warning when no
  pool is set and the provider quarantines); the Guests row on `/groups` (look, pool, rules); "Approve as guest"
  in the approve form; sidebar entry and counter only while guests are enabled.

**Configure.** `JANUS_GUEST_START`/`JANUS_GUEST_END` or Groups → Guests; rules and look in Groups → Guests.

**Entry points.** `guests.py`, `api/guests.py`, `worker.py::guests_once`; pages `/guests`, `/groups`
(`guest-editor.tsx`); `components/guest-expiry.tsx`, `lib/guests.ts`.

**Data.** `devices.guest_since/guest_expires_at`, setting `guests.settings`, events `guest.*` (notifications off by
default, migration 0009).

**Tests.** `test_guests.py`, `test_api_guests.py`, `test_worker.py` (`guests_once_*`, `provider_down_does_not_undo_the_removal`),
`test_enforcement.py` (`guests_become_guest_reservations_only_when_supported`), `test_netconfig.py` (guest pool),
`test_migrations.py` (0009); frontend `app/(app)/guests/guests-page.test.tsx`, `app/(app)/groups/groups-page.test.tsx`,
`components/guest-expiry.test.tsx`, `components/approve-form.test.tsx`, `lib/guests.test.ts`, `lib/nav.test.ts`.

**Invariants.** Guests never get a static IP or a group, never appear on the map or in the IP plan (they are listed
on `/guests`). Expired guests are removed from Janus even when the provider is down. Activity before admission does
not count toward inactivity.

---

## F12. Device identification

**Purpose.** Tell what a device is (vendor, model, OS, type, hostname, services) from local data only.

**Behaviour.**

- Worker job `identity` (`JANUS_IDENTITY_INTERVAL_S`, 60 s, `intel/identity.py`) walks new DHCP/mDNS/NetBIOS/SSDP
  sightings after a cursor (`identity.cursor`, batches of 500) and upserts facts (`device_facts`, unique per
  mac/field/source; an older observation never overwrites a newer fact; mDNS `services` accumulate).
- Rules (`intel/rules.py`): DHCP vendor class and parameter-list fingerprints (Android, Windows, Linux, BusyBox,
  Apple, ESP-IDF), mDNS hostname/model/service types (Chromecast, AirPlay, printers, HomeKit, Hue, ...),
  NetBIOS hostname, SSDP server header (OS hints), OUI vendor type hints. Each fact has a confidence.
- Vendors come from the offline IEEE file (`intel/oui.py`, `JANUS_OUI_PATH`, Debian `ieee-data`); private MACs get
  none; a missing file means an empty registry.
- `GET /api/devices/{id}/facts`: every fact plus `summary` (per field the highest confidence, then the most recent).
  The device page shows the Identity card with the source of each value.

**Entry points.** `intel/identity.py`, `intel/rules.py`, `intel/oui.py`, `api/intel.py` (`/facts`); `/devices/[id]`.

**Data.** `device_facts`, `devices.vendor`, setting `identity.cursor`.

**Tests.** `test_identity.py`, `test_rules.py`, `test_oui.py`, `test_api_intel.py` (`facts_summary`).

**Invariants.** No external lookup service, ever. ARP sightings are not walked.

---

## F13. Port scanning and services

**Purpose.** Find open TCP ports and risky services on approved devices, on a schedule or on request.

**Behaviour.**

- Container `janus-scanner` (`intel/scanner.py`), polling every `JANUS_SCAN_POLL_S` (30 s), one host at a time:
  `nmap -sT -sV --version-light -T3 --top-ports 200 -Pn --host-timeout <JANUS_SCAN_HOST_TIMEOUT_S>s -oX -`
  (unprivileged connect scan).
- Choice (`intel/scanning.py::pick_next`): manual requests first (`POST /api/devices/{id}/scan` sets
  `scan_requested_at`; needs a known in-subnet IP, else `422`), at any time. Scheduled scans: online approved
  devices with MAC and in-subnet IP in groups with `scan_enabled`, never-scanned first, when the last scan is older
  than the group interval; skipped when *now or the end of the scan* falls in a maintenance window (any enabled
  window), in the notification quiet hours, or outside the scan window (`08:00-22:00`).
- Results (`apply_scan`): open ports upserted into `services` (`state`, service, version truncated, risk via
  `intel/nmap.py::classify`: telnet/r-services high; FTP, VNC, RDP, databases, UPnP warning); ports gone become
  `closed`. Events: `security.new_port` for a newly open port *after the baseline scan*; one
  `security.risky_service` per scan listing every newly open risky port; `scan.completed`. A failed, timed-out or
  incomplete scan records `scan.failed`, sets `last_scan_at` (no immediate retry) and keeps known ports.
- Muting (`PATCH /api/devices/{id}/services/{port}/{proto} {muted}`): a muted service raises no alerts and no health
  issue; logs `security.risk_muted`/`security.risk_unmuted`.
- Device page: Risk / Open ports / Risky services stats, ports table with mute buttons, "What to do" advice
  (`components/device-security.ts`), "Scan now".

**Configure.** Group "Scheduled port scans" and interval; Settings → Network scan window; `JANUS_SCAN_*`.

**Entry points.** `intel/scanner.py`, `intel/scanning.py`, `intel/nmap.py`, `api/intel.py` (`/services`, `/scan`),
`api/services.py`; `/devices/[id]`.

**Data.** `services`, `devices.last_scan_at/scan_requested_at`.

**Tests.** `test_scanner.py`, `test_scanning.py`, `test_nmap.py`, `test_api_services.py`, `test_api_intel.py`
(`services_open_by_default`, `scan_request`), `test_netconfig.py` (`scanner_uses_the_overridden_subnet`,
`scan_request_refuses_hosts_outside_the_overridden_subnet`); frontend `components/device-security.test.ts`.

**Invariants.** Never scan outside the subnet. Never run nmap with raw-socket options (the scanner has no
`NET_RAW`). The first scan of a device is a baseline: no `security.new_port` for it.

---

## F14. DNS activity and analysis

**Purpose.** Show which domains a device queries, from the DNS provider's query log.

**Behaviour.**

- Requires a DNS provider with `DNS_QUERY_LOG` (else `404`) and a device with a known IP (else `422`); provider
  errors → `502`. Period `hours` 1-168 (default 24); at most 5000 queries are sampled (`truncated` when the total is
  larger).
- `GET /api/devices/{id}/dns`: total, sampled, blocked, top 20 domains with blocked flag (device page DNS card,
  24 h / 3 d / 7 d).
- `GET /api/devices/{id}/dns/analysis` (`intel/dns.py::analyze`): timeline in 10-minute buckets up to 6 h, hourly
  above; totals with blocked percentage and unique domains; top 200 domains with base domain and last seen; top 50
  blocked domains; top 50 base domains (public-suffix shortcut for `co.uk`-style names); query types; statuses
  (blocked ones flagged); reply types. Page `/devices/[id]/dns` with period selector, sortable/filterable table.

**Entry points.** `api/intel.py`, `intel/dns.py`, `providers/pihole/dns.py` (status mapping); pages
`/devices/[id]`, `/devices/[id]/dns`; `lib/dns-types.ts`.

**Tests.** `test_api_intel.py` (`dns_activity`, `dns_reports_truncation_and_uses_disk_for_long_windows`,
`dns_routes_are_404_without_dns_provider`), `test_dns_analysis.py`; frontend `lib/dns-types.test.ts`.

**Invariants.** The UI shows DNS sections only when `features.providers.dns` has `dns_query_log`.

---

## F15. DNS health check

**Purpose.** Know whether the DNS provider answers the LAN, judged from the host network like any LAN device.

**Behaviour.** At every ARP sweep the sentinel sends a DNS query for `pi.hole` to the DNS provider's probe host
(`dnscheck.py::dns_answers`; any reply counts) and on success stores `dns.last_ok`. The worker job `dns` (60 s)
marks the DNS role down (`infra.down`, `service: dns`) after 3 minutes without an answer and up again on recovery.
Without a DNS provider with `DNS_PROBE` the check is off and an open outage is dropped silently; before the first
answer nothing is judged. The probe host is read when the sentinel starts (a new DNS provider is probed after a
restart).

**Entry points.** `dnscheck.py`, `sentinel/main.py::write_heartbeat`, `worker.py::dns_check_once`,
`runtime.dns_probe_host`.

**Tests.** `test_dnscheck.py`, `test_sentinel_main.py` (`dns_probe_host_comes_from_the_dns_provider`,
`heartbeat_without_probe_never_records_a_dns_answer`), `test_provider_config.py` (`dns_probe_host_*`).

**Invariant.** The probe runs from the sentinel (host network), not from a container network.

---

## F16. Event log

**Purpose.** Everything Janus noticed or changed, newest first; also the notification outbox (F17).

**Behaviour.** `events.py::record_event` adds a row (`type`, `mac`, `payload`, `ts`) in the caller's transaction.
`GET /api/events?type=&mac=&before_id=&limit=` (1-500, default 50; an invalid MAC returns `[]`) pages by id.
`/events` filters by type and MAC (clicking an event's MAC filters to that device) and loads older pages by id; `lib/events.ts` turns each
type into a sentence. Event types in use: `device.new|approved|blocked|updated|deleted|offline|ip_mismatch|private_mac|gateway`,
`ip.conflict`, `infra.down|up`, `sync.applied|failed|mode`, `security.new_port|risky_service|risk_muted|risk_unmuted`,
`scan.completed|failed`, `maintenance.start|end`, `notify.test|failed`, `import.csv`, `group.compacted`,
`settings.network|channels|providers`, `guest.added|expired|removed`.

**Entry points.** `events.py`, `api/events.py`; page `/events`; `components/event-list.tsx`,
`components/event-tone.ts`, `lib/events.ts`.

**Tests.** `test_api_events.py`, `test_models.py`; frontend `lib/events.test.ts`, `components/event-tone.test.ts`.

**Invariants.** Events are append-only (nothing deletes them). Secrets never go into payloads (`settings.channels`
lists field names only).

**Open question.** The type filter of `/events` (`EVENT_TYPES`) lacks `sync.mode`, `group.compacted` and the
`settings.*` types, which therefore cannot be selected (they still show, described by their raw type).

---

## F17. Notifications

**Purpose.** Turn events into Gotify pushes and e-mails, with per-event rules, priorities, quiet hours, maintenance
muting, debouncing and retries.

**Behaviour.**

- Catalogue (`notify/catalog.py`): the notifiable event types with label, default Gotify priority, `always`
  (ignores quiet hours and maintenance), `maintenance_muted`, default channels. Defaults are listed in
  [operations.md](operations.md#notifications). Types outside the catalogue are never notified.
- Rules (`notification_rules`, seeded by migrations 0002/0003/0009 from the catalogue): per event and channel on/off.
  Priorities (setting `notify.priorities`, 0-10): only overrides are stored. Settings (`notify.settings`): global
  on/off, quiet hours (`23:00-07:00` default; equal or empty = off), per-channel on/off, e-mail recipient
  (fallback `JANUS_NOTIFY_EMAIL`).
- Dispatcher (`notify/dispatcher.py`, worker job `dispatch`, every 15 s):
  - a Postgres advisory lock makes a second dispatcher skip its round;
  - the first run sets the cursor at the newest event (no backlog flood); events younger than 30 s wait (settle);
  - channels = catalogue known, notifications on, not suppressed by schedule, channel ready and enabled, rule on.
    `notify.test` goes to its one channel when ready, even when notifications are off;
  - quiet hours / maintenance: `infra.down`, `infra.up` and `device.offline` are *deferred* and sent when the window
    ends if still relevant (still down / still offline with the same `last_seen`); every other suppressed event is
    dropped;
  - `infra.up` is sent only if the matching `infra.down` was delivered (`notify.down_delivered`);
  - debounce: one notification per `type:subject` per hour (Redis db 3, `RedisDebouncer`; `notify.test` exempt);
  - delivery: permanent failures (4xx except 408/429, SMTP auth/refused) are not retried; transient ones are retried
    on the next rounds up to 5 attempts (pending entries kept in `notify.pending`, at most 200); errors become
    `notify.failed`.
- Rendering (`notify/render.py`): one title/body/link per type, local time, names the provider and service
  (`dhcp`/`dns`/legacy `pihole`), `device.new` wording depends on whether quarantine is active (`apply`).
- API: `GET /api/notifications` (settings + rules with effective/default priority), `PUT /settings`, `PUT /rules`
  (unknown type → 422; priority equal to the default drops the override), `POST /test/{channel}` (404 unknown,
  409 not configured).
- Page `/notifications` (listed only when a channel is ready): global switch, per-channel cards with "Send test",
  rules table (columns only for ready channels, priority column only with Gotify), quiet hours.

**Configure.** Settings → Integrations (F18); `/notifications`; `REDIS_PASSWORD` for debouncing.

**Entry points.** `notify/*`, `api/notifications.py`, `worker.py::dispatch_once`; pages `/notifications`
(`rules-table.tsx`).

**Data.** `events` (outbox), `notification_rules`, settings `notify.cursor`, `notify.pending`,
`notify.down_delivered`, `notify.settings`, `notify.priorities`.

**Tests.** `test_dispatcher.py`, `test_notify_policy.py`, `test_notify_render.py`, `test_notify_channels.py`,
`test_api_notifications.py`, `test_worker.py` (`dispatch_once_delivers`), `test_migrations.py`
(`migration_seeds_default_window_and_rules`); frontend `app/(app)/notifications/rules.test.tsx`, `lib/nav.test.ts`.

**Invariants.**

- `device.new` (and `notify.test`) are never muted.
- A recovery is never announced without its outage.
- New catalogue entries need seeded rules (migration) or they read as "off" in the dispatcher (`rules.get(..., False)`)
  while the API shows the catalogue default.

**Open question.** [operations.md](operations.md#notifications) says "quiet hours defer non-urgent messages"; in the
code only the three deferrable types are deferred and other suppressed events are dropped.

---

## F18. Notification channels (Integrations)

**Purpose.** Configure Gotify and e-mail from the web app, with env values as defaults.

**Behaviour.** `notify/config.py` defines two overlay stores (F21): `notify.gotify` (`url` http(s), `token`
secret) and `notify.email` (`host`, `port` 1-65535, `security` `ssl|starttls|none`, `user`, `password` secret,
`sender`). Senders are rebuilt on every dispatch, so a save applies without restarting the worker. Gotify is ready
with URL and token; e-mail with host, sender and recipient. `GET/PUT /api/notifications/channels` returns values
(secrets as booleans), source (`env`/`custom`) and readiness; a change logs `settings.channels` with field names only.
Settings → Integrations has one Save, sends only changed fields, secret inputs are write-only (empty clears).

**Configure.** `GOTIFY_HOST`, `JANUS_GOTIFY_TOKEN`, `SMTP_*`, `JANUS_SMTP_SECURITY`, `JANUS_NOTIFY_EMAIL`.

**Entry points.** `notify/config.py`, `notify/channels.py`, `api/notifications.py`; `app/(app)/settings/sections/integrations.tsx`,
`lib/secret-input.tsx`.

**Tests.** `test_notify_config.py`, `test_notify_channels.py`, `test_api_notifications.py` (`channels_*`);
frontend `app/(app)/settings/sections/integrations.test.tsx`.

**Invariant.** Secrets are never returned by the API.

---

## F19. Maintenance windows

**Purpose.** Recurring periods (the nightly router reboot) that mute offline and infrastructure alerts and pause
scheduled scans.

**Behaviour.** `maintenance_windows`: name, start (local `HH:MM`), duration 1-720 min, day mask (Monday = bit 0,
1-127), enabled, `mute_alerts`, `pause_isolation`. `maintenance.py::Window.occurrences` computes openings in UTC:
start in local wall-clock time, duration in real time (DST-safe, a start in the skipped hour opens once).
`alerts_muted`/`muted_seconds` feed F4 and F17; any enabled active window pauses scheduled scans (F13); the worker
logs `maintenance.start`/`.end`. Migration 0002 seeds "Router & modem daily reboot" (05:00, 15 min, every day). CRUD
at `/api/maintenance-windows`; Settings → Maintenance windows (name, start, duration, repeat presets or custom days,
the two flags, next run); the sidebar shows whether a window is active.

**Entry points.** `maintenance.py`, `api/maintenance.py`, `worker.py::track_maintenance`; Settings page;
`components/settings-schedule.ts`, `lib/days.ts`.

**Tests.** `test_maintenance.py`, `test_api_maintenance.py`, `test_worker.py`; frontend
`components/settings-schedule.test.ts`, `lib/days.test.ts`.

**Open question.** `pause_isolation` is stored and editable ("Pause ARP isolation while the gateway reboots") but
nothing reads it: ARP isolation is shown as "Planned" in Settings → Access control. Scans pause in every active
window regardless of the flags.

---

## F20. Network and general settings

**Purpose.** Change the managed network and the general preferences without a restart.

**Behaviour.**

- `netconfig.py` (setting `network.config`): subnet (`/16`-`/30`), gateway (inside), quarantine pool (inside, start ≤
  end, without the gateway, not overlapping groups), guest pool (both or neither, inside, without the gateway, not
  overlapping quarantine or groups), sentinel interface (`[A-Za-z0-9_.:-]{1,32}`), sweep interval 10-3600 s, scan
  window `HH:MM`. The whole candidate is validated against the group ranges; only values different from the env
  are stored; `null` resets a field; an invalid stored set falls back to the env defaults. Changes log
  `settings.network` and restart the sentinel (F3) when they touch its fields.
- `PUT /api/settings {timezone?, time_format?, network?}`: time zone validated with `zoneinfo` (setting
  `general.timezone`, fallback `JANUS_TIMEZONE`, then UTC), `time_format` `24h|12h` (`general.time_format`).
  `GET /api/settings` also returns sync mode, field sources, infrastructure status (DHCP/DNS/sentinel down since,
  last sweep, maintenance active) and the channel display values.
- Settings page: one Save for General, Network and Maintenance; per-field error from the backend message; warns
  before leaving with unsaved changes; quarantine fields hidden without `QUARANTINE`.

**Entry points.** `netconfig.py`, `general.py`, `api/settings.py`; `app/(app)/settings/page.tsx`,
`components/settings-network.ts`, `lib/settings-context.tsx`.

**Tests.** `test_netconfig.py`, `test_api_settings.py`, `test_maintenance.py` (`current_tz_*`); frontend
`app/(app)/settings/settings-page.test.tsx`, `components/settings-network.test.ts`.

**Invariant.** A stored network config is always one that validated together with the current groups.

---

## F21. Settings store and secretbox

**Purpose.** One pattern for every editable configuration: env values are defaults, the `settings` row stores only
overrides, secrets are encrypted at rest and never leave the API.

**Behaviour.** `settingsstore.py::OverlayStore(key, fields)`: `load` (env defaults + decoded overrides), `view`
(secrets as booleans), `sources` (`env`/`custom`), `update` (unknown fields refused; `None` drops an override; a
value equal to the default drops it; validators run on non-empty values; secrets sealed). `secretbox.py`: Fernet
with a key derived by HKDF-SHA256 (`info=janus-settings-v1`) from `JANUS_SECRET_KEY` or, when unset,
`JANUS_INTERNAL_TOKEN`; sealed values carry the `fernet:` prefix; a value that cannot be decrypted (key rotated)
reads as unset. Used by `notify.gotify`, `notify.email`, `guests.settings`; `providers.config` and `auth.config`
follow the same rules with their own code.

**Tests.** `test_settingsstore.py`, `test_provider_config.py` (`secret_is_encrypted_and_kept_when_omitted`),
`test_authconfig.py`.

**Invariants.** Never store a secret unsealed; never return a secret value; rotating the key orphans stored secrets
(documented in [configuration.md](configuration.md#secret-key)).

---

## F22. Optional features and UI gating

**Purpose.** Every optional area turns itself on from configuration; the frontend hides what is off.

**Behaviour.** `features.py::FEATURE_PROVIDERS` → `GET /api/features`: `notify` (readiness per channel),
`providers` (F8), `guests` (`enabled`, `pool`, `color`, `icon`). A failing feature provider returns `{}` and rolls
the session back so the others still answer. The frontend loads it in `FeaturesProvider` (every 30 s and after
writes); `lib/nav.ts` hides gated menu items until features load (Guests when enabled, Notifications when a channel
is ready); provider pages come from `providerNav`; Settings sections from `EXTRA_SECTIONS`.

**Entry points.** `features.py`, `api/features.py`; `lib/features.tsx`, `lib/nav.ts`, `lib/provider-status.ts`,
`app/(app)/settings/sections/index.ts`.

**Tests.** `test_api_features.py`; frontend `lib/nav.test.ts`, `lib/provider-status.test.ts`.

**Invariant.** Add a new optional area as one entry in `FEATURE_PROVIDERS` and gate the UI on it, never on env names.

---

## F23. Network map

**Purpose.** A topology view: modem, gateway, infrastructure tiers, group boxes, wired/Wi-Fi uplinks.

**Behaviour.** `GET /api/map` returns saved positions, links and `layout_version`; `PUT /api/map/positions`
(≤ 1000 items, finite coordinates within ±1e6) saves positions and stamps layout version 3; `POST /api/map/links`
(`wired|wifi`, label ≤ 64; self-link `422`, unknown device `404`, existing pair in either direction `409`, enforced
also by a unique index on the unordered pair); `DELETE /api/map/links/{id}`. Links are deleted with their device.
The page (`/map`, React Flow) auto-lays out with `lib/map-layout.ts`: gateway (device on the gateway IP),
infrastructure (groups with icon `wifi`, `router`, `server`) and devices reached from them through wired links
(up to depth 6) in tiers, members in group boxes (pending in a "Quarantine"/"Pending" box), dashed Wi-Fi bus.
Blocked devices are not drawn; guests are not in the device list. Drag to move, "Save layout", "Auto layout", draw
an uplink from a node's bottom edge, click a line to remove it, double-click a node to open it, "Export PNG",
show/hide IPs; saved positions are used only when their layout version matches.

**Entry points.** `api/map.py`; page `/map`; `lib/map-layout.ts`.

**Data.** `devices.map_x/map_y`, `links`, setting `map.layout_version`.

**Tests.** `test_api_map.py`; frontend `lib/map-layout.test.ts`.

**Invariant.** Bump `LAYOUT_VERSION` in both `api/map.py` and `app/(app)/map/page.tsx` when the auto-layout changes
meaning, so stale positions are ignored.

---

## F24. Import and export

**Purpose.** Bring an existing device list in; take the inventory out.

**Behaviour.**

- `janus import-csv <file> [--dry-run]` (`importer.py`): columns `Name`, `MAC Address`, `LAN IP`, `Category`
  (BOM tolerated). Categories become groups (missing ones created with a palette colour, icon `device`,
  `authorized`, range inferred in blocks of ten addresses around their IPs and checked against the plan); rows are
  matched by MAC (or by name for MAC-less rows), created or updated (name, hostname, group, IP); invalid rows are
  skipped with a reason; one `import.csv` event with the report. Idempotent.
- `GET /api/devices/export.xlsx?group_id=&access=`: the device list as an Excel sheet (`export.py`, local times,
  bold header, filters, frozen header), filename `janus-devices-<date>.xlsx`; "Download Excel" on `/devices`.
- IP plan CSV (F2) and map PNG (F23) are generated in the browser.

**Tests.** `test_importer.py` (fixture `tests/fixtures/sample.csv`), `test_api_devices.py`
(`export_devices_as_excel`); frontend `components/ip-plan-export.test.ts`.

**Open question.** The Excel `Access` column has no label for `guest` (raw value is written); guests only appear
with `access=guest`.

---

## F25. Metrics

**Purpose.** Prometheus metrics for dashboards and alerts.

**Behaviour.** The worker serves `:9108/metrics` (only that path; daemon thread; a bind failure is logged, not
fatal): `janus_devices{access,online}`, `janus_devices_pending`, `janus_devices_health{health}`,
`janus_last_sweep_timestamp_seconds`, `janus_last_port_scan_timestamp_seconds`, `janus_provider_up{role}` (only
for roles that are on), `janus_sentinel_up`, `janus_maintenance_active`, `janus_sync_mode_info{mode}`,
`janus_events_total{type}`.

**Entry points.** `metrics.py`, `worker.py::main`.

**Tests.** `test_metrics.py`.

**Invariant.** Renaming a metric breaks dashboards: note it in [operations.md](operations.md#metrics).

---

## F26. Health checks and heartbeats

**Purpose.** Docker (and autoheal) can tell each container is alive.

**Behaviour.** `GET /api/health` (no token) runs `SELECT 1` (503 when the database is down); Next.js
`/api/healthz` proxies it (`ok`/`degraded`/`down`). The worker touches `/tmp/janus-worker.heartbeat` every loop
(5 s sleep), the sentinel `/tmp/janus-sentinel.heartbeat` after each sweep, the scanner
`/tmp/janus-scanner.heartbeat` after each poll; the compose health checks read their age
([operations.md](operations.md#deploy-and-update)). A failing worker job is logged and retried at its next
interval, never killing the loop.

**Entry points.** `api/health.py`, `app/api/healthz/route.ts`, `worker.py`, `sentinel/main.py`, `intel/scanner.py`,
`docker-compose.yml`.

**Tests.** `test_sentinel_main.py` (`write_heartbeat`); the endpoints are exercised by the API test client. No
dedicated test for `/api/healthz`.

---

## F27. Sign-in and users

**Purpose.** Local username/password sign-in always works; OIDC (Authentik or any IdP) is optional; users and
roles are managed in the app.

**Behaviour.**

- better-auth (`frontend/lib/auth/server.ts`) with the `username`, `admin` (default role `user`) and
  `genericOAuth` plugins, tables in the Postgres schema `auth` (created by `scripts/migrate-auth.mjs` at container
  start, together with the optional `JANUS_ADMIN_USERNAME`/`JANUS_ADMIN_PASSWORD` admin when no user exists).
  Sessions last 12 h (refreshed hourly); sign-up is disabled; account linking is disabled (an IdP account never
  attaches to a local user). Users carry `source` (`local` or `oidc`, default `oidc`).
- First run: while no user exists every page (login included) redirects to `/setup` (`lib/auth/session-guard.ts`),
  which creates a local admin (username `[a-z0-9_.]{3,30}`, password ≥ 12, e-mail `<username>@local.invalid`) and
  signs in; configured OIDC buttons are offered too, and the first allowlisted OIDC user becomes admin. `/setup`
  closes once a user exists.
- OIDC providers and the allowlist come from the backend (`authconfig.py`, setting `auth.config`; env provider id
  `authentik` from `AUTH_AUTHENTIK_*`/`JANUS_OIDC_*`): ids `[a-z0-9-]{2,32}`, discovery `https` (or `http` to a
  private IP), scopes must include `openid`, secrets sealed, a provider identical to the env one is not stored, the
  env secret applies to a stored twin with the same client id. `GET /api/internal/auth-config` gives the Next.js
  server the enabled providers with a secret, the allowlist and a version hash; the frontend caches it 15 s and
  keeps the last good copy (or an offline config with no providers) when the backend is down.
- Discovery of every provider is probed with a 3 s timeout; a failing provider is left out of the better-auth
  instance and re-probed in the background every 15 s, so a hanging IdP never blocks password sign-in.
- Gate (`lib/auth/gate.ts`): local users pass unless banned; everyone else must be on the allowlist
  (case-insensitive) at every request (`getAllowedSession`), so removing an address takes effect within 15 s.
  New OIDC users are created only when allowlisted.
- Last admin (`lib/auth/last-admin.ts`, server middleware): the last usable (not banned) admin cannot be deleted,
  banned or demoted, whatever client calls the admin endpoints.
- Settings → Sign-in & users: admins manage users (create local, reset password, make admin/user, delete; not
  yourself, not the last admin) and OIDC providers/allowlist (one Save, callback URL shown); local users change
  their own password (other sessions revoked).
- Login page: username/password always, one button per configured provider (enabled, with a secret), safe
  `callbackUrl` (same-origin relative paths only), readable errors (`AccessDenied`). The button of a provider left
  out after a failed discovery probe still shows and answers "<name> is not reachable right now".

**Configure.** `AUTH_SECRET`, `AUTH_URL` (from `JANUS_HOST`), `AUTH_DATABASE_URL`, `AUTH_AUTHENTIK_*`,
`JANUS_OIDC_*`, `JANUS_ALLOWED_EMAILS`, `JANUS_ADMIN_*`; Settings → Sign-in & users.

**Entry points.** `frontend/lib/auth/*`, `frontend/lib/auth-actions.ts` (logout), `frontend/proxy.ts`,
`app/api/auth/[...all]/route.ts`, `app/login/*`, `app/setup/*`, `app/(app)/layout.tsx`,
`app/(app)/settings/sections/sign-in.tsx`, `scripts/migrate-auth.mjs`; backend `authconfig.py`,
`api/authconfig.py`, `api/internal.py`.

**Tests.** Backend `test_authconfig.py`; frontend `lib/auth/*.test.ts` (gate, last-admin, server, config,
discovery, has-users, session-guard, callback-url), `app/login/login-form.test.tsx`, `app/setup/*.test.ts*`,
`app/(app)/settings/sections/sign-in.test.tsx`.

**Open question.** [configuration.md](configuration.md#sign-in--users) says an unreachable provider "is left out
of the login page"; in the code it is left out of better-auth, while the login and setup pages still list its button
(which then reports it unreachable, see `app/setup/page.test.tsx`).

**Invariants.**

- Password sign-in never depends on the backend or an IdP being reachable.
- The allowlist is re-checked on every request; local users are not subject to it.
- Schema-affecting better-auth options in `lib/auth/server.ts` and `scripts/migrate-auth.mjs` stay identical.
- Backups must include the `auth` schema.

---

## F28. API trust boundary

**Purpose.** The FastAPI API is reachable only through the signed-in web app.

**Behaviour.** FastAPI listens on `127.0.0.1:8000` inside the `janus` container. Every router except `/api/health`
depends on `security.py::require_internal`: `503` while `JANUS_INTERNAL_TOKEN` is empty, `401` unless
`X-Janus-Internal-Token` matches (constant-time, non-ASCII safe). The Next.js catch-all `app/api/[...path]/route.ts`
→ `lib/proxy.ts::forward`: `401` when not signed in (allowlist included), `403` for cross-site writes
(`Sec-Fetch-Site`/`Origin` vs the app origin and `AUTH_URL`), `404` for `/api/internal/*` (judged on the raw and
the resolved path) or a path escaping `/api/`, `400` on malformed encoding, `413` for bodies over 1 MB; it forwards
only `content-type`/`accept` and returns only `content-type`, `cache-control`, `content-disposition`. Validation
errors are returned as `{detail: [{loc, msg, type}]}` (`main.py`). `next.config.ts` sets security headers
(`nosniff`, `DENY` framing, HSTS, same-origin referrer, permissions policy). `frontend/proxy.ts` (Next.js
middleware) redirects unsigned pages to `/login?callbackUrl=` and answers `401` JSON for API calls.

**Entry points.** `security.py`, `main.py`, `api/internal.py`; `app/api/[...path]/route.ts`, `lib/proxy.ts`,
`lib/backend.ts`, `proxy.ts`, `next.config.ts`.

**Tests.** `test_security.py`, `test_api_groups.py` (`requires_internal_token`, `closed_when_token_not_configured`),
`test_api_features.py` (`features_require_the_internal_token`), `test_api_providers.py`
(`provider_routes_require_the_internal_token`); frontend `lib/proxy.test.ts`, `lib/auth/session-guard.test.ts`.

**Invariants.** New routers are included with `dependencies=protected` in `main.py`. The browser never reaches
`/api/internal/*`. No role check exists in the API (see F7).

---

## F29. CLI

**Purpose.** Operator commands inside the `janus` container: `docker exec -it janus python -m app.cli <command>`.

**Behaviour** (`cli.py`): core commands `import-csv`, `sync [--apply]`, `sync-mode apply|dry-run`; provider
commands registered by each spec's `cli` hook (Pi-hole: `preflight`, `backup`, `cutover`, `rollback`). Exit codes:
0 ok, 1 provider error / preflight not ready, 2 configuration refusal. Details in
[operations.md](operations.md#cli).

**Tests.** `test_cli.py`, `providers/pihole/test_cli.py`, `providers/test_contract.py`
(`cli_commands_are_unique_and_do_not_shadow_core_commands`).

**Invariant.** Provider commands never shadow core commands and are unique across providers.

---

## F30. App shell, live refresh and theme

**Purpose.** A consistent, live web app on desktop and mobile.

**Behaviour.** `app/(app)/layout.tsx` requires an allowed session (else `/login?error=AccessDenied`) and renders
`components/shell.tsx` (sidebar with counters for devices, pending, guests; provider pill "<label> DHCP · active" /
"dry-run" / "unreachable" / "DNS down"; next ARP sweep countdown; maintenance status; sign-out; mobile menu).
`lib/use-resource.ts` reloads on an interval, on window focus, when the tab becomes visible and after every
successful write (`janus:changed` event from `lib/api.ts`); a `401` sends the browser to the login page. Times are
formatted in the configured zone and format (`lib/format.ts`). Theme: system/light/dark, stored in `localStorage`
(`janus.theme`), applied before paint by an inline script. Overview has a `/` keyboard shortcut for search.

**Entry points.** `app/layout.tsx`, `app/(app)/layout.tsx`, `components/shell.tsx`, `components/sidebar.tsx`,
`components/ui.tsx`, `components/theme-toggle.tsx`, `lib/api.ts`, `lib/use-resource.ts`, `lib/use-now.ts`,
`lib/theme.ts`, `lib/settings-context.tsx`, `app/globals.css`, `app/icon.svg`, `public/robots.txt`.

**Tests.** Frontend `lib/api.test.ts`, `lib/use-now.test.ts`, `components/theme-toggle.test.tsx`,
`lib/format.test.ts`. The sidebar has no dedicated test.

---

## F31. Test and repository guards

**Purpose.** Keep the suite hermetic and the repository free of real network identifiers.

**Behaviour.** `tests/conftest.py` blocks every non-loopback connection at the httpcore socket layer
(`_no_network`), recreates the `public` schema of the test database once per session and runs each test in a
rolled-back transaction. `test_repo_hygiene.py` fails when a tracked file contains a MAC outside the documentation
ranges `00:00:5E:00:53:xx` / `02:00:5E:00:53:xx`. `test_migrations.py` checks that migrations match the models.

**Tests.** `test_no_network.py`, `test_repo_hygiene.py`, `test_migrations.py`.

---

## Appendix: traceability

Every module of `backend/app/` and every route or page of `frontend/app/` maps to at least one feature.

### Backend (`backend/app/`)

| Module | Features |
|---|---|
| `__init__.py`, `api/__init__.py`, `enforcement/__init__.py`, `intel/__init__.py`, `net/__init__.py`, `notify/__init__.py`, `providers/__init__.py`, `sentinel/__init__.py` | package markers (empty) |
| `main.py` | F28 (app factory, router wiring, validation errors), F8 (provider routers) |
| `config.py` | all (env `Settings`, `JANUS_*`) |
| `db.py` | all (engine, session) |
| `models.py` | F1, F2, F3, F12, F13, F16, F17, F19, F23 (data model) |
| `security.py` | F28 |
| `events.py` | F16 |
| `general.py` | F20 (time zone) |
| `syncmode.py` | F7 |
| `secretbox.py` | F21 |
| `settingsstore.py` | F21 |
| `features.py` | F22 |
| `health.py` | F5 |
| `presence.py` | F4 |
| `approval.py` | F6 |
| `guests.py` | F11 |
| `netconfig.py` | F20, F2 (plan), F11 (guest pool) |
| `maintenance.py` | F19 |
| `metrics.py` | F25 |
| `importer.py` | F24 |
| `export.py` | F24 |
| `dnscheck.py` | F15 |
| `authconfig.py` | F27 |
| `cli.py` | F29, F7, F24 |
| `worker.py` | F7, F4, F15, F17, F12, F11, F19, F25, F26 |
| `api/approval.py` | F6 |
| `api/authconfig.py` | F27 |
| `api/conflicts.py` | F1, F2, F6, F11 (unique-race → 409) |
| `api/devices.py` | F1, F24 (Excel) |
| `api/events.py` | F16 |
| `api/features.py` | F22 |
| `api/groups.py` | F2 |
| `api/guests.py` | F11 |
| `api/health.py` | F26 |
| `api/intel.py` | F12, F13, F14 |
| `api/internal.py` | F27, F28 |
| `api/maintenance.py` | F19 |
| `api/map.py` | F23 |
| `api/notifications.py` | F17, F18 |
| `api/providers.py` | F8 |
| `api/roles.py` | F8 (DHCP/DNS dependencies) |
| `api/services.py` | F13 |
| `api/settings.py` | F20 |
| `api/sync.py` | F7 |
| `enforcement/reservations.py` | F7 |
| `enforcement/sync.py` | F7 |
| `intel/dns.py` | F14 |
| `intel/identity.py` | F12 |
| `intel/nmap.py` | F13 |
| `intel/oui.py` | F12 |
| `intel/rules.py` | F12 |
| `intel/scanner.py` | F13, F26 |
| `intel/scanning.py` | F13 |
| `net/ipplan.py` | F2 |
| `net/mac.py` | F1 |
| `net/names.py` | F1 |
| `notify/catalog.py` | F17 |
| `notify/channels.py` | F17, F18 |
| `notify/config.py` | F18 |
| `notify/debounce.py` | F17 |
| `notify/dispatcher.py` | F17 |
| `notify/policy.py` | F17, F13 (quiet hours for scans) |
| `notify/render.py` | F17 |
| `notify/store.py` | F17 |
| `providers/base.py` | F8 |
| `providers/config.py` | F8 |
| `providers/registry.py` | F8 |
| `providers/runtime.py` | F8, F7 (DHCP identity), F2 (infrastructure IPs), F15 |
| `providers/README.md` | F8 (pointer to the guide) |
| `providers/_template/*` | F8 (copyable skeleton, skipped by discovery) |
| `providers/pihole/__init__.py`, `provider.py`, `client.py`, `codec.py`, `dns.py` | F9, F14 |
| `providers/pihole/api.py`, `cli.py`, `cutover.py` | F9, F29 |
| `providers/unifi/__init__.py`, `provider.py`, `client.py`, `api.py` | F10 |
| `sentinel/main.py` | F3, F15, F26 |
| `sentinel/observe.py` | F3 |
| `sentinel/record.py` | F3 |
| `migrations/versions/0001`-`0009` | data model of every feature (see [design.md](design.md#data-model)) |

### Frontend routes and pages (`frontend/app/`)

| Route / file | Features |
|---|---|
| `layout.tsx`, `globals.css`, `icon.svg` | F30 |
| `(app)/layout.tsx` | F27, F30 |
| `(app)/page.tsx` (`/`, Overview) | F1, F5, F6 |
| `(app)/pending/page.tsx` (`/pending`) | F6, F11 |
| `(app)/devices/page.tsx` (`/devices`) | F1, F5, F24 |
| `(app)/devices/[id]/page.tsx` (`/devices/[id]`) | F1, F5, F6, F12, F13, F14, F16 |
| `(app)/devices/[id]/dns/page.tsx` | F14 |
| `(app)/events/page.tsx` (`/events`) | F16 |
| `(app)/groups/page.tsx`, `guest-editor.tsx` (`/groups`) | F2, F11 |
| `(app)/guests/page.tsx` (`/guests`) | F11 |
| `(app)/ip-plan/page.tsx` (`/ip-plan`) | F2, F24 |
| `(app)/map/page.tsx` (`/map`) | F23 |
| `(app)/notifications/page.tsx`, `rules-table.tsx` | F17 |
| `(app)/settings/page.tsx` (`/settings`) | F20, F19, F7 |
| `(app)/settings/sections/enforcement.tsx` | F7 |
| `(app)/settings/sections/providers.tsx` | F8 |
| `(app)/settings/sections/integrations.tsx` | F18 |
| `(app)/settings/sections/sign-in.tsx` | F27 |
| `(app)/settings/sections/index.ts`, `section-card.tsx` | F22, F30 |
| `(app)/integrations/[kind]/[[...slug]]/page.tsx` | F8 (provider pages: F9 cutover, F10 clients) |
| `login/page.tsx`, `login/login-form.tsx` | F27 |
| `setup/page.tsx`, `setup/setup-form.tsx`, `setup/actions.ts` | F27 |
| `api/[...path]/route.ts` | F28 |
| `api/auth/[...all]/route.ts` | F27 |
| `api/healthz/route.ts` | F26 |

Outside `frontend/app/`: `proxy.ts` (F27, F28), `next.config.ts` (F28), `scripts/migrate-auth.mjs` (F27),
`providers/*` (F8, F9, F10), `lib/auth/*` (F27), `lib/proxy.ts` and `lib/backend.ts` (F28), `lib/map-layout.ts` (F23),
`lib/guests.ts` (F11), `lib/ipplan.ts` (F2), `lib/dns-types.ts` (F14), `lib/events.ts` (F16), `lib/days.ts` (F19),
`lib/filter.ts`, `lib/delete-device.ts` (F1), `lib/features.tsx`, `lib/nav.ts`, `lib/provider-status.ts` (F22, F8),
`lib/group-icons.tsx` (F2, F11), `lib/secret-input.tsx` (F18, F8, F27), `lib/api.ts`, `lib/use-resource.ts`,
`lib/use-now.ts`, `lib/theme.ts`, `lib/format.ts`, `lib/settings-context.tsx`, `lib/types.ts` (F30),
`lib/test-data.ts` (test fixtures); `components/*` as listed under each feature.
