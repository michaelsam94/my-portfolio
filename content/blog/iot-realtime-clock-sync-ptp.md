---
title: "Clock Sync with PTP and NTP"
slug: "iot-realtime-clock-sync-ptp"
description: "Synchronize clocks across IoT and edge systems with NTP and PTP: stratum hierarchy, IEEE 1588 profiles, holdover, and practical deployment on constrained devices."
datePublished: "2025-09-08"
dateModified: "2025-09-08"
tags: ["IoT", "Edge Computing", "Networking", "Industrial"]
keywords: "PTP clock sync IoT, NTP vs PTP, IEEE 1588, time synchronization edge, grandmaster clock, stratum NTP"
faq:
  - q: "When should IoT devices use PTP instead of NTP?"
    a: "Use PTP when you need sub-millisecond synchronization across a local network — industrial control, power grid PMUs, synchronized sensor fusion, or TSN Ethernet. Use NTP when millisecond-to-tens-of-milliseconds accuracy is enough and devices reach the internet or a local NTP server. PTP requires network hardware support or careful software timestamping; NTP works almost everywhere."
  - q: "What happens when the time source is unreachable?"
    a: "Devices enter holdover — they free-run using their local oscillator (TCXO, OCXO) and drift according to crystal spec, often tens of ppm. Log holdover state, alert when offset exceeds threshold, and queue timestamped events with uncertainty flags. When sync returns, slew clock gradually rather than stepping abruptly to avoid confusing downstream systems."
  - q: "How do I verify clock sync is working in production?"
    a: "Monitor offset and jitter metrics from chrony, ptp4l, or vendor daemons. Compare master and slave timestamps on known events (GPIO pulse, PPS line). Alert on sustained offset above SLA, stratum changes, and leap-second handling. Graph frequency adjustment — runaway disciplining indicates network asymmetry or bad hardware timestamping."
---

Two vibration sensors on the same machine reported peaks 8 milliseconds apart — enough to misalign a predictive maintenance model that fused their readings. Both claimed NTP sync, but one polled a distant stratum-3 server over Wi-Fi while the other used a local grandmaster over Ethernet. Clock sync in IoT is not cosmetic timestamp decoration; it determines whether distributed measurements can be correlated, whether event ordering is trustworthy, and whether compliance logs hold up in audit. NTP and PTP solve different accuracy tiers on different networks.

## NTP: good enough for most IoT

Network Time Protocol synchronizes clocks over UDP port 123 using a stratum hierarchy. Stratum 0 is the reference (GPS, atomic clock); stratum 1 servers attach directly; each hop adds stratum count and typically error.

Typical accuracy:

- **LAN to local NTP server** — 1–5 ms
- **Internet NTP** — 10–100+ ms depending on path
- **Cellular IoT** — highly variable; budget 50–200 ms unless you control the path

On Linux gateways, use **chrony** instead of legacy ntpd — faster convergence after sleep/wake and better handling of intermittent connectivity:

```
# /etc/chrony/chrony.conf
pool time.google.com iburst
makestep 1.0 3
rtcsync
```

`makestep` allows an initial step if offset exceeds 1 second during first three updates — common after devices boot without RTC battery.

Embedded RTOS devices often run SNTP — a minimal NTP client sufficient for periodic sync:

```c
// ESP-IDF SNTP example pattern
void sync_time(void) {
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_init();
    // Wait for sync callback, then set timezone with setenv("TZ", ...)
}
```

Always store and transmit **UTC** internally; apply timezones only at display.

## PTP: sub-millisecond on the factory floor

IEEE 1588 Precision Time Protocol exchanges timestamped Sync, Follow_Up, Delay_Req, and Delay_Resp messages to estimate offset and path delay. Hardware timestamping at the PHY/MAC eliminates OS jitter and achieves **< 1 µs** on supported switches and NICs.

Key roles:

- **Grandmaster (GM)** — authoritative clock, often GPS-disciplined
- **Boundary clock** — switch that terminates and re-originates PTP on each port
- **Transparent clock** — switch that measures and corrects residence time
- **Slave** — end device disciplining its clock to the GM

Linux slaves typically run `ptp4l` with a PHC (PTP Hardware Clock):

```bash
ptp4l -i eth0 -m -s  # slave, log to stdout
phc2sys -s eth0 -w   # discipline system clock from PHC
```

Profile matters. **IEEE 1588 default** vs **power profile (IEEE C37.238)** vs **automotive** — each specifies message rates, BMC algorithm options, and acceptable jitter. Mismatch between GM and slave profiles causes silent poor sync.

## Choosing NTP vs PTP

| Requirement | NTP | PTP |
|-------------|-----|-----|
| Accuracy | ms | µs–ns (with HW) |
| Network | Any IP | L2/L3, often dedicated |
| Switch support | None needed | TC/BC for best results |
| Edge gateway | Yes | Yes, as boundary |
| Coin-cell sensor | SNTP | Rarely — cost/complexity |

Hybrid deployments are normal: PTP on the plant Ethernet backbone; gateways translate to NTP for Wi-Fi sensor subnets that cannot run PTP.

## Holdover, leap seconds, and clock steps

When sync is lost, oscillators drift. A 20 ppm TCXO drifts ~1.7 seconds per day. Log `sync_state` alongside every measurement so downstream analytics can down-weight or reject holdover data during critical calculations.

Leap seconds and manual clock steps break monotonic assumptions. Use **CLOCK_MONOTONIC** for intervals and **CLOCK_REALTIME** only when wall time is required. Libraries like Google's `absl::Time` or careful `clock_gettime` usage prevent negative durations after steps.

chrony **slews** small offsets and **steps** large ones — configure thresholds explicitly for your application. SCADA systems often forbid backward steps entirely; in that case, halt and alert rather than step.

## Timestamping at the source

Sync the clock, then timestamp **at capture**, not at cloud ingest:

```python
# Bad: server time at receive
event = {"value": reading, "ts": datetime.utcnow().isoformat()}

# Good: device monotonic + synced UTC at sample
event = {
    "value": reading,
    "ts_utc": sample_utc_ns,
    "seq": local_sequence,
    "sync_quality": sync_state,
}
```

Include sequence numbers so consumers can detect reordering even when clocks agree.

## Deployment checklist

1. **One authoritative source per island** — multiple GMs fighting produces churn.
2. **Redundant GM with BMC** — best master clock election, not manual failover hacks.
3. **Monitor offset continuously** — do not wait for correlation bugs in ML pipelines.
4. **Document asymmetry** — asymmetric routes inflate PTP error; use peer delay mechanism where needed.
5. **Test reboot and power loss** — RTC-less devices boot at epoch without SNTP; reject pre-sync publishes.

## Common production mistakes

Teams get realtime clock sync ptp wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of realtime clock sync ptp fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When realtime clock sync ptp misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [RFC 5905 — NTP Version 4](https://www.rfc-editor.org/rfc/rfc5905)
- [IEEE 1588-2019 overview](https://standards.ieee.org/standard/1588-2019.html)
- [chrony documentation](https://chrony-project.org/documentation.html)
- [linuxptp (ptp4l) project](https://linuxptp.sourceforge.net/)
- [PTP on ESP32 / embedded considerations (Espressif)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/system_time.html)
