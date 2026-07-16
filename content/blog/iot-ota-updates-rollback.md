---
title: "OTA Updates with Safe Rollback"
slug: "iot-ota-updates-rollback"
description: "Deploy over-the-air firmware updates with safe rollback: A/B partitions, boot verification, delta updates, staged rollouts, and recovery from failed updates."
datePublished: "2025-09-02"
dateModified: "2025-09-02"
tags: ["IoT", "Embedded", "Security", "Architecture"]
keywords: "OTA firmware update, safe rollback IoT, A/B partition firmware, MCUboot OTA, delta firmware update, staged rollout IoT"
faq:
  - q: "What is A/B partitioning for OTA updates?"
    a: "Flash is divided into two app slots: Slot A (running) and Slot B (staging). New firmware downloads to the inactive slot. After verification, the bootloader switches to the new slot. If the new firmware fails boot verification, the bootloader reverts to the previous slot automatically."
  - q: "How does boot verification prevent bricked devices?"
    a: "After swapping to new firmware, a hardware watchdog or boot counter tracks successful boots. If the new firmware doesn't confirm within 60-120 seconds (by writing a 'boot OK' flag), the bootloader assumes failure and reverts to the previous slot. The device never stays on broken firmware."
  - q: "Should I roll out OTA updates to the entire fleet at once?"
    a: "Never. Use staged rollouts: 1% canary → 10% → 50% → 100%, with automated health checks between stages. Monitor crash rates, connectivity, and battery metrics. Pause or rollback if error rates exceed baseline. A bad OTA to 10,000 devices simultaneously is a product recall."
---

A bad firmware update bricking 5,000 devices in the field isn't a thought experiment — it's a quarterly industry event. The firmware was fine. The update mechanism wasn't: no rollback partition, no boot verification, no staged rollout. The device downloaded, flashed, rebooted into a crash loop, and had no way back. OTA with safe rollback means assuming every update will fail for someone, and designing the path back to working firmware as carefully as the path forward.

## A/B partition layout

```
Flash (1 MB example):
┌────────────┬──────────────┬──────────────┬──────────┐
│ Bootloader │  Slot A      │  Slot B      │ Config   │
│ (32 KB)    │  (480 KB)    │  (480 KB)    │ (8 KB)   │
│ MCUboot    │  v1.2.3 RUN  │  v1.3.0 NEW  │ boot_cfg │
└────────────┴──────────────┴──────────────┴──────────┘
```

Boot config (in dedicated flash sector):

```c
struct boot_config {
    uint32_t magic;           // 0xB007C0DE
    uint8_t active_slot;      // 0 = A, 1 = B
    uint8_t boot_attempts;    // increments each boot, reset on confirm
    uint8_t max_attempts;     // 3 → revert after 3 failed boots
    uint32_t confirmed_version;
};
```

## Update flow

```
1. Device checks for update (MQTT/HTTPS)
2. Downloads firmware to inactive slot (B)
3. Verifies: SHA-256 hash + ECDSA signature
4. Sets boot_config: active_slot = B, boot_attempts = 0
5. Reboots
6. MCUboot validates signature on Slot B
7. Jumps to new firmware
8. New firmware has 120s to call confirm_boot()
9. confirm_boot() sets boot_attempts = max (permanent)
10. If step 8 fails → MCUboot reverts to Slot A on next reboot
```

```c
void confirm_boot(void) {
    struct boot_config cfg;
    read_boot_config(&cfg);
    cfg.boot_attempts = cfg.max_attempts;  // prevent revert
    cfg.confirmed_version = CURRENT_VERSION;
    write_boot_config(&cfg);
}

// Call within 120 seconds of boot
void app_main(void) {
    init_hardware();
    connect_cloud();
    confirm_boot();  // we're running OK
    // ... normal operation
}
```

## Delta (binary diff) updates

For bandwidth-constrained devices, send a patch instead of full firmware:

```bash
# Generate delta on server
bsdiff old_firmware.bin new_firmware.bin patch.bin

# Device applies patch
bspatch slot_a_firmware.bin patched.bin patch.bin
# Then verify signature on patched.bin before swapping
```

Delta updates reduce download size by 70-90% but add complexity. Always verify the patched result against the expected hash before swapping. Keep full-image updates as fallback.

## Staged rollout implementation

```python
def get_update_eligibility(device_id: str, current_version: str) -> UpdateDecision:
    rollout = db.get_active_rollout(current_version)
    if not rollout:
        return UpdateDecision(eligible=False)

    device = db.get_device(device_id)

    # Stage progression
    if rollout.stage == "canary":
        if device_id not in rollout.canary_devices:
            return UpdateDecision(eligible=False)
    elif rollout.stage == "partial":
        if hash(device_id) % 100 >= rollout.percentage:
            return UpdateDecision(eligible=False)

    # Health gate: don't update unhealthy devices
    if device.crash_count_24h > rollout.max_crash_rate:
        return UpdateDecision(eligible=False, reason="high_crash_rate")

    return UpdateDecision(
        eligible=True,
        firmware_url=rollout.firmware_url,
        firmware_hash=rollout.sha256,
        firmware_signature=rollout.signature,
    )
```

Automated stage promotion:

```python
def check_rollout_health(rollout_id: str):
    stats = db.query("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            COUNT(*) FILTER (WHERE status = 'reverted') AS reverted
        FROM ota_attempts
        WHERE rollout_id = %s AND created_at > NOW() - INTERVAL '24 hours'
    """, rollout_id)

    failure_rate = stats.failed / (stats.confirmed + stats.failed)
    if failure_rate > 0.05:  # 5% failure threshold
        pause_rollout(rollout_id)
        alert_oncall(f"OTA rollout {rollout_id} paused: {failure_rate:.1%} failure rate")
    elif stats.confirmed > 100 and failure_rate < 0.01:
        promote_rollout(rollout_id)  # canary → 10% → 50% → 100%
```

## Device-side download with resume

```c
typedef struct {
    uint32_t total_size;
    uint32_t downloaded;
    uint8_t  sha256[32];
    uint8_t  active_slot;
} ota_state_t;

esp_err_t ota_download(const char *url, ota_state_t *state) {
    esp_http_client_config_t config = {
        .url = url,
        .cert_pem = server_cert,
    };

    // Resume from last downloaded byte
    if (state->downloaded > 0) {
        char range[32];
        snprintf(range, sizeof(range), "bytes=%u-", state->downloaded);
        esp_http_client_set_header(client, "Range", range);
    }

    // Stream to inactive slot with SHA-256 verification
    mbedtls_sha256_context sha_ctx;
    mbedtls_sha256_init(&sha_ctx);
    mbedtls_sha256_starts(&sha_ctx, 0);

    // ... download loop, write to flash, update sha256

    if (memcmp(computed_hash, state->sha256, 32) != 0) {
        return ESP_ERR_OTA_VALIDATE_FAILED;
    }
    return ESP_OK;
}
```

Support HTTP Range requests for resume after connectivity drops. Verify hash before swap.

## Monitoring OTA health

Track per rollout:
- Download success/failure rate
- Boot confirmation rate (confirmed vs reverted)
- Time-to-confirm (p50, p99)
- Post-update crash rate (compare 24h before vs after)
- Connectivity recovery time

Dashboard alert: if reverted > 2% of attempts, auto-pause rollout.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get ota updates rollback wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of ota updates rollback fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When ota updates rollback misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MCUboot design documentation](https://docs.mcuboot.com/design.html) — swap algorithms, boot verification, and revert logic
- [ESP-IDF OTA Updates](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html) — Espressif's A/B OTA implementation
- [bsdiff/bspatch](https://www.daemonology.net/bsdiff/) — binary diff tool for delta updates
- [AWS IoT Jobs for OTA](https://docs.aws.amazon.com/iot/latest/developerguide/iot-jobs.html) — managed OTA deployment with staged rollout
