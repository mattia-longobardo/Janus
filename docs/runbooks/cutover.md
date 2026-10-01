# Runbook — DHCP cutover to Pi-hole

Pi-hole (on the server, 192.168.1.220) takes over DHCP from the QHora-301W and Janus switches from `dry-run` to `apply`: every approved device gets its reservation, unknown devices land in the quarantine pool without a gateway.

Allow about 30 minutes, in the evening, with the owner at home and logged in to the QHora-301W web panel. Keep a phone on mobile data in case the Wi-Fi misbehaves.

All Janus commands run inside the `janus` container:

```bash
docker exec -it janus python -m app.cli <command>
```

## 0. The day before

- Nothing changes on the network. Check the Janus **Settings → Access control → Cutover readiness** panel: everything except "Quarantine rules", "Backup" and "Write access" should already be green.
- Fix any device listed under "Approved devices" (missing MAC or static IP) or "Duplicates".
- **Open DHCP in the server firewall.** Pi-hole runs with host networking, so the host's ufw filters its traffic. DNS (53) already works; DHCP requests arrive on UDP 67 and are dropped unless allowed. On the server:

  ```bash
  sudo ufw allow in on enp5s0 to any port 67 proto udp comment 'Pi-hole DHCP'
  sudo ufw status | grep -E '53|67'
  ```

  Nothing needs opening inside Pi-hole itself; the cutover command enables its DHCP server. IPv6 DHCP stays off, so UDP 547 is not needed.

## 1. Load the quarantine rules into Pi-hole

The two `dhcp-option` tag lines are already in `network/docker-compose.yml` but Pi-hole only reads them when it is recreated. They do nothing while Pi-hole's DHCP is off.

```bash
cd ~/docker/network && docker compose up -d pihole
```

## 2. Preflight and backup

```bash
docker exec -it janus python -m app.cli backup
docker exec -it janus python -m app.cli preflight
```

`preflight` exits non-zero and lists what is wrong until every blocking check is green. The backup (Pi-hole Teleporter zip + Janus data dump) lands in `projects/Janus/janus/backups/<timestamp>/`.

## 3. Cutover

The cutover needs Pi-hole's **admin** password (the one in `network/.env`, `PIHOLE_PASSWORD`). Janus reads it from an environment variable for this one command and never stores it:

```bash
read -rs PIHOLE_ADMIN && export PIHOLE_ADMIN
docker exec -it -e PIHOLE_ADMIN janus python -m app.cli cutover --pihole-password-env PIHOLE_ADMIN
unset PIHOLE_ADMIN
```

It re-runs the preflight with the admin password, then in this order:

1. allows Janus' app password to write (`webserver.api.app_sudo = true`);
2. writes every reservation to Pi-hole;
3. turns Pi-hole DHCP on: range = quarantine pool (`.240–.254`), router = `192.168.1.1`, lease 24 h, no IPv6;
4. switches Janus to `apply` (logged as a `sync.mode` event).

## 4. Owner: turn the QHora DHCP off

In the QHora-301W web panel (QuRouter), open the LAN / DHCP server settings of the home network and **disable the DHCP server**, then apply. Leave everything else (Wi-Fi, gateway address 192.168.1.1, port forwarding) untouched.

Do this right after step 3: two DHCP servers must not answer at the same time for long.

Choose **off**, not **DHCP relay**. Relay is for a DHCP server on a different subnet or VLAN: the router would forward every request to Pi-hole even though Pi-hole already hears the same broadcast directly on 192.168.1.0/24, so each request reaches it twice, and the router stays in the path. If the QHora has other networks (guest Wi-Fi or a separate VLAN with its own subnet), leave the router's DHCP **on for those**: Janus manages only 192.168.1.0/24.

## 5. Verify

- [ ] On a phone: forget the Wi-Fi network, join again → it gets its reserved address (check in Janus, device page).
- [ ] Pi-hole admin → Settings → DHCP shows active leases.
- [ ] Reboot or reconnect the devices Janus marks in red: CAMERA_BEDROOM and RELE_COFFE_MACHINE should move to their reservations and turn green.
- [ ] A device Janus does not know gets an address in `.240–.254` and no internet; it shows up in **Pending**.
- [ ] Approving it from **Pending** gives it its reservation (the approval notice says `applied`).
- [ ] Janus sidebar shows "Pi-hole DHCP · active".

Devices keep their old router lease until they renew it (up to the QHora lease time). Rebooting them, or the router's Wi-Fi, speeds this up.

## 6. Rollback

If something is wrong, in this order:

1. Owner: **re-enable the DHCP server on the QHora-301W**.
2. Turn Pi-hole DHCP off and Janus back to `dry-run` (also removes the write permission from Janus' app password):

   ```bash
   read -rs PIHOLE_ADMIN && export PIHOLE_ADMIN
   docker exec -it -e PIHOLE_ADMIN janus python -m app.cli rollback --pihole-password-env PIHOLE_ADMIN
   unset PIHOLE_ADMIN
   ```

3. Reconnect the devices that misbehave so they renew with the router.

The reservations Janus wrote stay in Pi-hole but are inactive while its DHCP is off. If needed, the Pi-hole Teleporter zip from step 2 restores Pi-hole exactly (Pi-hole admin → Settings → Teleporter → Restore).
