---
title: "Firmware Signing and Secure Boot"
slug: "iot-firmware-signing-secure-boot"
description: "Secure IoT firmware with code signing and secure boot chains: generate signing keys, verify signatures on boot, anti-rollback counters, and OTA update security."
datePublished: "2025-08-09"
dateModified: "2025-08-09"
tags: ["IoT", "Embedded", "Security", "Architecture"]
keywords: "firmware signing, secure boot IoT, code signing embedded, anti-rollback firmware, OTA update security, MCUboot secure boot"
faq:
  - q: "What is secure boot for IoT devices?"
    a: "Secure boot verifies firmware authenticity before execution. The bootloader checks a cryptographic signature on the firmware image against a trusted public key burned into the device. If the signature is invalid or missing, the bootloader refuses to run the firmware. This prevents attackers from flashing malicious code."
  - q: "How does firmware signing work?"
    a: "Build produces a firmware binary. A signing server computes a hash (SHA-256) of the binary and signs it with a private key (ECDSA P-256 or RSA-2048). The signature is appended to the firmware image or stored in a metadata header. On boot, the device verifies the signature using the corresponding public key before executing the code."
  - q: "What is anti-rollback protection?"
    a: "Anti-rollback prevents downgrading to older firmware with known vulnerabilities. A monotonic security counter (eFuse, flash-based, or TPM NV counter) stores the minimum acceptable firmware version. Bootloader rejects any firmware with a version below the counter. Each legitimate update increments the counter."
---

An unsigned bootloader will run any code you flash to it. That's convenient during development and catastrophic in production — an attacker with physical access (or a compromised OTA channel) can replace your firmware with a version that exfiltrates data, joins a botnet, or silently disables safety interlocks. Secure boot and firmware signing aren't paranoia. They're the minimum bar for any IoT device that can't be physically guarded.

## Secure boot chain

```
ROM bootloader (immutable, factory burned)
    │ verifies signature
    ▼
Secondary bootloader (MCUboot, U-Boot)
    │ verifies signature
    ▼
Application firmware
    │ verifies signature (optional)
    ▼
Runtime integrity checks
```

Each stage verifies the next before handing control. The root of trust is hardware — a public key hash in eFuse (ESP32), OTP (STM32), or ROM (ARM TrustZone).

## Signing workflow

```bash
# Generate signing key pair (once, store private key in HSM/Vault)
openssl ecparam -genkey -name prime256v1 -out fw-signing-key.pem
openssl ec -in fw-signing-key.pem -pubout -out fw-signing-key.pub

# Build firmware
idf.py build  # produces build/app.bin

# Sign firmware
espsecure.py sign_data --keyfile fw-signing-key.pem \
  --output build/app-signed.bin build/app.bin

# Or with MCUboot imgtool
imgtool sign --key fw-signing-key.pem --align 8 \
  --version 1.2.3 --slot-size 0x70000 \
  build/app.bin build/app-signed.bin
```

The private key never touches the device. Only the public key (or its hash) is embedded in firmware or eFuse.

## MCUboot on ARM Cortex-M

MCUboot is the standard secure bootloader for Zephyr, Mbed, and many RTOS platforms:

```
Flash layout:
┌──────────────┬──────────────┬──────────────┐
│  MCUboot     │  Primary     │  Secondary   │
│  (bootloader)│  slot (app)  │  slot (OTA)  │
│  32 KB       │  448 KB      │  448 KB      │
└──────────────┴──────────────┴──────────────┘
```

Boot sequence:

```c
// MCUboot pseudocode
int main(void) {
    struct image_header primary_hdr, secondary_hdr;

    if (boot_read_image_header(PRIMARY_SLOT, &primary_hdr) == 0) {
        if (bootutil_img_validate(&primary_hdr, PRIMARY_SLOT) == 0) {
            boot_jump_to_image(PRIMARY_SLOT);
        }
    }

    // Primary invalid — try secondary (OTA update)
    if (boot_read_image_header(SECONDARY_SLOT, &secondary_hdr) == 0) {
        if (bootutil_img_validate(&secondary_hdr, SECONDARY_SLOT) == 0) {
            boot_swap_images();  // promote secondary to primary
            boot_jump_to_image(PRIMARY_SLOT);
        }
    }

    // Both invalid — enter recovery mode
    enter_serial_recovery();
}
```

Image validation checks:
1. Magic number and header structure
2. SHA-256 hash of image body
3. ECDSA/RSA signature over the hash
4. Version >= anti-rollback counter

## Anti-rollback

```c
#define MIN_VERSION 0x00010203  // stored in eFuse or flash config

bool check_rollback(struct image_version *ver) {
    uint32_t current = (ver->iv_major << 16) | (ver->iv_minor << 8) | ver->iv_revision;
    if (current < MIN_VERSION) {
        return false;  // reject downgrade
    }
    return true;
}

void update_rollback_counter(struct image_version *ver) {
    uint32_t new_min = (ver->iv_major << 16) | (ver->iv_minor << 8) | ver->iv_revision;
    if (new_min > MIN_VERSION) {
        write_efuse_rollback_counter(new_min);  // one-way, irreversible
    }
}
```

eFuse counters can only increment — perfect for monotonic version enforcement.

## OTA update security

Signed OTA flow:

```
Cloud → signed firmware blob → device downloads to secondary slot
    → MCUboot validates signature on secondary
    → swap primary ↔ secondary
    → reboot into new primary
    → new primary validates on boot
    → if validation fails, MCUboot reverts to old primary
```

Critical rules:
- **Always download to secondary slot** — never overwrite running firmware
- **Verify before swap** — signature check happens before the swap, not after
- **Test boot** — new firmware must confirm successful boot within N seconds or MCUboot reverts
- **Encrypt in transit** — TLS for download; optionally encrypt firmware at rest (AES-256 with device-unique key)

## Key management

| Key | Storage | Access |
|-----|---------|--------|
| Signing private key | HSM / HashiCorp Vault / AWS KMS | CI pipeline only |
| Signing public key | Device eFuse or flash | Read-only |
| Encryption key (optional) | Device secure element | Never exported |
| OTA TLS cert | Device flash | Standard TLS |

Rotate signing keys annually. Support dual-key verification during rotation (bootloader accepts signatures from old or new key for one release cycle).

## Development vs production

Development: unsigned flashing over USB/UART for fast iteration.

Production: secure boot enforced, debug ports disabled, eFuses blown:

```bash
# ESP32: disable UART download, enable secure boot
espefuse.py burn_key secure_boot_v2 build/secure_boot_signing_key.pem
espefuse.py burn_efuse UART_DOWNLOAD_MODE 0
```

Blowing eFuses is irreversible. Test the entire signed boot chain on multiple devices before production programming.

## Secure boot chain verification

```c
// Bootloader verifies application signature before jump
if (!verify_ecdsa_signature(firmware_image, embedded_pubkey)) {
    enter_recovery_mode();
}
```

Root of trust in OTP/eFuse — factory provisioning burns public key hash. OTA updates signed with offline HSM key, verified before flash write.

## Common production mistakes

Teams get firmware signing secure boot wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of firmware signing secure boot fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When firmware signing secure boot misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MCUboot documentation](https://docs.mcuboot.com/) — secure bootloader design and imgtool signing
- [ESP-IDF Secure Boot V2](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/security/secure-boot-v2.html) — Espressif's secure boot implementation
- [ARM Trusted Firmware-M (TF-M)](https://www.trustedfirmware.org/projects/trusted-firmware-m/) — secure boot and runtime isolation for Cortex-M
- [NIST SP 800-147 — BIOS Protection Guidelines](https://csrc.nist.gov/publications/detail/sp/800-147/final) — firmware integrity principles applicable to IoT
