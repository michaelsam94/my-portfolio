---
title: "Firmware Updates over OCPP"
slug: "ocpp-firmware-update-management"
description: "Manage EV charger firmware updates over OCPP: UpdateFirmware messages, download monitoring, rollback strategies, and fleet-wide deployment."
datePublished: "2025-10-24"
dateModified: "2026-07-17"
tags: ["IoT", "EV Charging", "OCPP", "Operations"]
keywords: "OCPP firmware update, UpdateFirmware OCPP, EV charger firmware, OCPP 2.0.1 firmware, charging station updates, fleet firmware management"
faq:
  - q: "How does OCPP firmware update differ from OTA updates in consumer IoT?"
    a: "OCPP firmware updates are CSMS-initiated with explicit download URLs, retry logic, and status reporting back to the central system. The charger must continue serving vehicles during download (unless using idle-only scheduling) and report each phase: downloading, downloaded, installing, installed, or failed."
  - q: "Can a charger roll back firmware after a failed update?"
    a: "OCPP does not define automatic rollback. Implement dual-bank firmware (A/B partitions) in charger hardware so a failed boot loads the previous image. Report InstallRebooting and InstallationFailed statuses so the CSMS knows to retry or halt the rollout."
  - q: "How do I update 500 chargers without overwhelming my CDN?"
    a: "Stagger updates by site, region, or percentage. OCPP 2.0.1 supports firmware update scheduling (install after timestamp). Start with 5% canary, monitor for 48 hours, then expand. Rate-limit download URLs at the CDN level."
---

A security patch needs to reach 800 chargers across 120 sites. USB drives at each location is not an option. OCPP defines a standardized firmware update flow: the CSMS sends a download URL, the charger downloads the image, installs it during idle periods, and reports status at every step. Done right, you patch the fleet from a dashboard. Done wrong, you brick 40 chargers on a Monday morning because the rollout had no canary and no rollback partition.

## OCPP 1.6 firmware flow

```
CSMS → UpdateFirmware(location, retrieveDate, retries)
Charger → DownloadFirmwareStatusNotification(Downloading)
Charger → DownloadFirmwareStatusNotification(Downloaded)
Charger → (install at retrieveDate or immediately)
Charger → FirmwareStatusNotification(Installing)
Charger → FirmwareStatusNotification(Installed) + reboot
```

**UpdateFirmware message:**

```json
{
  "location": "https://cdn.example.com/firmware/v2.4.1/charger-model-x.bin",
  "retrieveDate": "2025-10-25T02:00:00Z",
  "retries": 3,
  "retryInterval": 300
}
```

`retrieveDate` schedules installation during off-peak hours. The charger downloads immediately but installs at the scheduled time.

## OCPP 2.0.1 improvements

OCPP 2.0.1 adds:

- **PublishFirmware** — CSMS hosts firmware; charger pulls via signed URL.
- **UnpublishFirmware** — revoke a firmware version.
- **FirmwareStatusNotification** with detailed `statusInfo`.
- **Device Model variables** — `FirmwareVersion` on `Controller` component.

```json
{
  "requestId": 42,
  "firmware": {
    "location": "https://cdn.example.com/firmware/v2.4.1/",
    "retrieveDateTime": "2025-10-25T02:00:00Z",
    "installDateTime": "2025-10-25T03:00:00Z",
    "signingCertificate": "-----BEGIN CERTIFICATE-----\n...",
    "signature": "base64-signature"
  }
}
```

Signed firmware prevents tampered images from installing.

## Status monitoring

Track every charger through the state machine:

```
Idle → DownloadScheduled → Downloading → Downloaded
     → InstallScheduled → Installing → InstallRebooting → Installed
     → (or) DownloadFailed / InstallationFailed
```

**CSMS dashboard query:**

```sql
SELECT station_id, firmware_status, firmware_version, last_updated
FROM charger_firmware
WHERE firmware_status NOT IN ('Installed', 'Idle')
ORDER BY last_updated DESC;
```

Alert when any charger stays in `Downloading` for > 30 minutes or `InstallationFailed` count exceeds 2% of the rollout cohort.

## Rollout strategy

**Phase 1 — Canary (5%):**
- Select 5% of chargers across different sites and models.
- Push firmware, monitor for 48 hours.
- Check: successful installs, post-update error rate, charging session success rate.

**Phase 2 — Staged (25%, 50%, 100%):**
- Expand in 25% increments with 24-hour pauses.
- Pause rollout if failure rate exceeds 1%.

**Phase 3 — Stragglers:**
- Chargers that failed download get retried with extended `retryInterval`.
- Offline chargers receive firmware on next WebSocket reconnect.

```python
async def rollout_firmware(version: str, cohort_pct: float):
    chargers = await db.get_chargers_eligible_for_update(version)
    cohort = chargers[:int(len(chargers) * cohort_pct)]

    for charger in cohort:
        await csms.send_update_firmware(
            charger_id=charger.id,
            location=f"https://cdn.example.com/firmware/{version}/",
            retrieve_date=next_off_peak(charger.timezone),
            request_id=generate_request_id(),
        )
```

## Hardware requirements

| Feature | Why |
|---------|-----|
| Dual-bank flash (A/B) | Rollback on failed boot |
| Signed image verification | Reject tampered firmware |
| Resume partial downloads | Survive network interruptions |
| Idle-only installation | Don't interrupt active charging sessions |
| Post-install health check | Verify OCPP reconnect before marking success |

## Failure handling

| Status | Action |
|--------|--------|
| `DownloadFailed` | Retry with exponential backoff (3 attempts) |
| `InstallationFailed` | Rollback to previous bank; alert ops |
| `Installed` but no reconnect within 10 min | Flag for manual intervention |
| Wrong model firmware pushed | Reject at signature verification |

Never auto-retry `InstallationFailed` without human review—repeated install attempts on corrupted flash worsens the situation.

## OCPP 2.0.1 signed firmware

OCPP 2.0.1 adds mandatory firmware signing:

```json
{
  "requestId": 42,
  "firmware": {
    "location": "https://fw.example.com/charger-v2.3.1.signed.bin",
    "retrieveDateTime": "2024-12-28T02:00:00Z",
    "signingCertificate": "base64-signing-cert",
    "signature": "base64-rsa-signature"
  }
}
```

Charger verifies signature against trusted signing certificate before installation. Reject unsigned or tampered firmware at verification stage — before flash write.

Maintain signing certificate chain separately from TLS certificates — firmware signing key compromise is more severe than TLS cert expiry.

## Staged rollout strategy

Never push firmware to entire fleet simultaneously:

```
Stage 1: 5% of fleet (canary) — monitor 48 hours
Stage 2: 25% — monitor 24 hours
Stage 3: 100% — only after zero InstallationFailed in Stage 2
```

```python
def select_firmware_targets(firmware_version, stage_pct):
    eligible = Charger.objects.filter(
        model=firmware_version.compatible_model,
        current_fw__lt=firmware_version.version,
        last_install_failed=False,
    )
    return eligible.order_by('?')[:int(len(eligible) * stage_pct / 100)]
```

Exclude chargers with recent `InstallationFailed` from rollout until manually reviewed.

## Firmware update during active sessions

OCPP firmware update must not interrupt active charging sessions:

```
UpdateFirmware request received:
  1. Download firmware in background (non-blocking)
  2. Wait for all active transactions to complete
  3. Wait for connector to be Available (no cable connected)
  4. Install firmware (charger reboots)
  5. Verify OCPP reconnect within 10 minutes
  6. Report Installed or InstallationFailed
```

Schedule updates for off-peak hours (2–4 AM local time) via `retrieveDateTime`. Chargers in active markets may need regional scheduling.

## Failure modes

- **Firmware pushed to wrong model** — signature verification fails; charger unaffected
- **Install during active session** — session interrupted; driver complaint
- **No dual-bank flash** — failed install bricks charger; requires physical intervention
- **100% simultaneous rollout** — fleet-wide outage if firmware bug
- **InstallationFailed auto-retried** — corrupted flash worsens with each attempt

## Production checklist

- Firmware signed with dedicated signing certificate
- Staged rollout: 5% → 25% → 100% with monitoring between stages
- Updates scheduled for off-peak hours only
- Dual-bank flash (A/B) for rollback capability
- InstallationFailed excluded from auto-retry; manual review required
- OCPP reconnect verified within 10 minutes post-install

## Fleet operations war stories worth rehearsing

- **Timezone bugs in `retrieveDateTime`** — chargers in DST boundaries install at wrong local hour; use UTC internally, display local only in UI.
- **CDN cache poisoning** — stale firmware URL served from edge; version URLs must be immutable (`/v2.4.1/` never overwritten).
- **Parallel rollouts** — ops runs manual update while automated rollout also targets same site; dedupe by `requestId` and freeze manual tools during fleet jobs.

## Delta updates and bandwidth math

Full images for AC chargers range 50–200 MB. Updating 800 units on cellular SIMs can exhaust data pools in hours. Where vendor tooling supports binary deltas, prefer diff packages — a 120 MB full image may reduce to 8–15 MB delta when jumping one minor version.

```python
def choose_firmware_package(charger, target_version):
    current = charger.firmware_version
    delta = find_delta(current, target_version)
    if delta and delta.size_mb < 0.25 * full_image_size(target_version):
        return delta
    return full_image(target_version)
```

Log download duration and bytes per charger. Spikes in `DownloadFailed` on cellular sites often trace to MTU issues or proxy timeouts, not corrupt images — configure CDN range requests and extend HTTP client timeouts on charger firmware.

## Post-install verification beyond OCPP reconnect

Reconnecting to CSMS is necessary but insufficient. Define a **health checklist** before marking rollout success:

1. `BootNotification` with new `firmwareVersion`
2. Test `Authorize` + short `StartTransaction` on one connector (canary session)
3. Verify `MeterValues` measurands match pre-update baseline
4. Confirm Security Profile unchanged (Profile 3 cert still valid)

Automate canary sessions in staging; in production, run them only on explicit canary cohort chargers to avoid billing noise. If health check fails after `Installed`, trigger automatic rollback on dual-bank hardware before ops gets paged.

## RequestId deduplication across retries

OCPP 2.0.1 ties firmware status to `requestId`. CSMS must treat duplicate `FirmwareStatusNotification` with same `requestId` and status as idempotent — chargers retry on flaky WebSocket. Store `(station_id, request_id, status)` unique constraint; ignore exact duplicates, alert on conflicting status transitions for same request.

## Vendor-specific status quirks

Some chargers report `Downloaded` but delay `Installing` until local maintenance window despite `installDateTime` passed — document vendor matrix. Others reboot twice during install; only mark success after second `BootNotification` with matching version. Field ops runbooks need per-model notes, not generic OCPP state diagram.

## Resources

- [OCPP 1.6 Firmware Management](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — UpdateFirmware specification
- [OCPP 2.0.1 Part 1 Firmware Update](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — signed firmware and scheduling
- [IEC 61851 EV charging standard](https://webstore.iec.ch/en/publication/6029) — hardware safety context
- [OWASP IoT Firmware Security](https://owasp.org/www-project-iot-security/) — signing and verification practices
- [Open Charge Alliance test toolkit](https://www.openchargealliance.org/test-tool/) — firmware update conformance testing