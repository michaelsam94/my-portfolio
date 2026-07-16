---
title: "Reliable OTA Firmware Updates for IoT"
slug: "ota-firmware-updates-iot"
description: "Reliable OTA firmware updates for IoT: A/B partitions, delta updates, secure boot, signing, staged rollouts, and how to never brick a fleet you can't physically reach."
datePublished: "2026-07-05"
dateModified: "2026-07-05"
tags: ["IoT", "Embedded", "Security", "Reliability"]
keywords: "OTA firmware, A/B partitions, delta updates, secure boot, rollback firmware, IoT device update, signing firmware"
faq:
  - q: "What is an OTA firmware update?"
    a: "An OTA (over-the-air) firmware update delivers new device software to IoT hardware remotely over a network, without physical access. A robust OTA system downloads a signed image, verifies its integrity and authenticity, flashes it to a spare partition, boots into it, and automatically rolls back if the new firmware fails to run correctly — so a fleet of unreachable devices can be updated safely at scale."
  - q: "Why use A/B partitions for firmware updates?"
    a: "A/B partitioning keeps two copies of the firmware: the device runs from slot A while the update is written to slot B, then boots into B. If B fails to start or fails a health check, the bootloader rolls back to the known-good A slot. This makes updates atomic and recoverable — a power loss or corrupt image during the update cannot brick the device."
  - q: "How do you secure OTA updates?"
    a: "You sign every firmware image with a private key and have the device verify the signature against a trusted public key before flashing, so only authentic images from you can run. Combine this with secure boot (each stage verifies the next), encrypted transport (TLS), and anti-rollback counters to prevent downgrading to a vulnerable version. Never trust an image just because it downloaded."
---

The nightmare scenario for anyone shipping connected hardware is simple to state: you push a firmware update, something goes wrong, and ten thousand devices you can't physically reach stop responding. Reliable OTA firmware updates are the discipline of making that outcome impossible — designing the update path so that a corrupt download, a power cut mid-flash, or a subtly broken build can never leave a device bricked. Get this right and you can iterate on deployed hardware like it's a web service. Get it wrong and every update is a coin flip with your fleet.

I've shipped OTA to devices in the field, and the mindset that matters most is pessimism: assume the download will be interrupted, assume power will drop at the worst moment, assume one build in fifty is bad. Design for those and the happy path takes care of itself.

## A/B partitions are non-negotiable

The single most important architectural decision is dual-slot (A/B) partitioning. The device keeps two firmware slots. It runs from A, downloads and writes the update to B while A keeps running, then flips the boot pointer to B on the next reboot. Crucially, the switch is atomic — a single flag the bootloader reads — so there's no window where the device is half-updated.

```text
Boot flow with A/B slots:

[Bootloader] --> read active slot flag
     |
     +--> Slot B marked "trial"?  --> boot B
     |         |
     |         +-- B sets "confirmed" within N boots? --> keep B
     |         +-- B fails health check / crashes?    --> revert to A
     |
     +--> else boot A (known good)
```

The magic is the **trial-then-confirm** step. When B first boots it's marked "trial." The application must actively confirm it's healthy — network up, sensors reading, watchdog happy — within a few boots. If it doesn't confirm (because it crash-loops or hangs), the bootloader automatically reverts to A. This means a broken build fixes itself without anyone touching the device. I consider this the line between a hobby OTA and a production one.

## Signing and secure boot come first

Before a device flashes anything, it must prove the image is genuinely yours and unmodified. That means signing every image with a private key held in your build system and verifying the signature on-device against a public key baked into read-only storage. An unsigned or tampered image is rejected before a single byte is committed to flash.

Layer that under secure boot, where each stage verifies the next — immutable ROM verifies the bootloader, the bootloader verifies the application — so there's an unbroken chain of trust from silicon to your code. And add an **anti-rollback counter**: a monotonic version number the device refuses to go below, so an attacker can't push an old, vulnerable-but-validly-signed image to reopen a patched hole. The clock-and-certificate discipline here rhymes with what I described for [ISO 15118 Plug and Charge](https://blog.michaelsam94.com/iso-15118-plug-and-charge/) — in both, cryptographic verification is only as good as your key management and your refusal to trust anything unverified.

## Delta updates when bandwidth costs money

Full-image updates are simple but expensive on metered or slow links — an NB-IoT device paying per kilobyte can't download a 2 MB image casually. Delta (differential) updates send only the binary diff between the current and target versions, often shrinking a payload by 90% or more. The device reconstructs the new image from the old one plus the patch.

The tradeoff is real complexity: you must know exactly which version each device runs to build the right delta, the patch/reconstruction step needs its own scratch space and can fail, and a corrupt delta is worse than a corrupt full image because it's harder to reason about. My rule: start with full images while your fleet is small, and only introduce deltas when bandwidth cost or update duration becomes a genuine constraint. Premature delta optimization has caused more outages than it's saved dollars in my experience.

## Staged rollouts, because your tests missed something

No matter how good your CI is, the field has hardware revisions, network conditions, and edge cases your lab doesn't. So never push to 100% at once. A sane rollout ladder:

1. **Canary (1%)** — a small, monitored cohort. Watch confirm rates and crash telemetry.
2. **Early (10%)** — broaden if canary holds for a defined window.
3. **Ramp (50%)** — continue only if error budgets are intact.
4. **Full (100%)** — the rest, with the ability to halt instantly.

The critical capability is the **kill switch**: the moment confirm rates dip or crash reports spike, you stop the rollout before the bad build spreads. Devices already on the new version that failed will have auto-reverted thanks to A/B; devices not yet updated simply never get the bad image. This is the same error-budget-driven caution that shows up across [reliability practices in DORA metrics](https://blog.michaelsam94.com/dora-metrics-that-matter/) — you're treating a firmware push like a production deploy, because it is one.

## Resumable, verified downloads

The transport layer needs its own resilience. Devices lose connectivity mid-download constantly, so downloads must be resumable — track byte offsets and continue rather than restarting a 2 MB fetch over a flaky link. And verify integrity at two levels: a checksum/hash on the downloaded bytes to catch corruption, and the cryptographic signature to catch tampering. Only after both pass does the image become a boot candidate.

A pattern I've relied on: write to the inactive slot as chunks arrive, keep a persistent record of progress, and treat the slot as invalid until the final verification succeeds. If power drops at chunk 400 of 500, the device resumes at 400 on reboot, the active slot A never having been touched.

## The failure modes that actually happen

The theoretical risks get all the attention; here are the ones that bit me:

- **Power loss during flash** — solved by A/B, fatal without it.
- **Clock wrong, certificate "expired"** — the device rejects a valid image because its clock drifted. Sync time or use anti-rollback counters rather than pure expiry.
- **Confirm step too strict or too lenient** — too strict and good updates revert; too lenient and a subtly broken build gets confirmed. Tune the health check to real signals.
- **Storage exhaustion** — the download fills flash and corrupts state. Reserve the inactive slot and reject if space is short.
- **Fleet version drift** — you lose track of what's deployed, and deltas or rollouts target the wrong baseline. Report version from every device, always.

OTA is one of those systems where the code is modest but the failure analysis is everything. Build on A/B partitions with automatic rollback, verify signatures before you ever write flash, roll out in stages with a kill switch, and make downloads resumable and integrity-checked. Do that and updating hardware you'll never physically touch becomes routine instead of terrifying — which, when your product is a device in someone's wall, is the whole point.

## Resources

- [RFC 9019 — A Firmware Update Architecture for IoT Devices](https://datatracker.ietf.org/doc/html/rfc9019)
- [SUIT — Software Updates for Internet of Things (IETF working group)](https://datatracker.ietf.org/wg/suit/about/)
- [Mender — open-source OTA update manager](https://github.com/mendersoftware/mender)
- [SWUpdate — embedded Linux update framework](https://sbabic.github.io/swupdate/)
- [ESP-IDF OTA update documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html)
- [The Update Framework (TUF) specification](https://theupdateframework.io/)
