---
title: "CAN Diagnostics and OBD-II"
slug: "iot-can-opener-diagnostics"
description: "Read vehicle diagnostics over OBD-II and CAN: PID requests, DTC codes, ELM327 adapters, Mode 09 VIN, and building fleet diagnostic pipelines."
datePublished: "2025-07-13"
dateModified: "2025-07-13"
tags: ["IoT", "Embedded", "Automotive", "Architecture"]
keywords: "OBD-II diagnostics, CAN diagnostics, ELM327, DTC codes, OBD PID, vehicle telematics, fleet diagnostics"
faq:
  - q: "What is OBD-II and how does it relate to CAN?"
    a: "OBD-II (On-Board Diagnostics II) is a standard diagnostic interface mandated on vehicles since 1996 (US) and 2001 (EU). It defines a 16-pin connector, a protocol stack (often ISO 15765-4 which wraps CAN), and a set of standard Parameter IDs (PIDs) for reading engine data and Diagnostic Trouble Codes (DTCs). OBD-II is the gateway to CAN data for external devices."
  - q: "What are OBD-II PIDs?"
    a: "PIDs (Parameter IDs) are standardized data requests. Mode 01 PID 0x0C returns engine RPM, PID 0x0D returns vehicle speed, PID 0x05 returns coolant temperature. You send a request frame with the PID number and receive a response with the value. Not all PIDs are supported on all vehicles — you query supported PIDs first."
  - q: "Can I use a cheap ELM327 Bluetooth adapter for production?"
    a: "ELM327 clones work for prototyping and personal use but are unreliable for production fleet telematics — inconsistent timing, dropped connections, and clone chips that don't fully implement the protocol. For production, use proper CAN interfaces (PEAK, Kvaser, or embedded modems with direct CAN access) and implement ISO-TP yourself."
---

Plug an ELM327 adapter into the OBD-II port, open a terminal, type `010C`, and you get engine RPM. It feels like magic until you realize it's just a well-defined request-response protocol over CAN, standardized across every car sold in the last 25 years. For fleet telematics, EV charging diagnostics, or predictive maintenance, OBD-II is the front door to vehicle data.

## OBD-II physical layer

The OBD-II connector (SAE J1962) has 16 pins. The ones that matter:

| Pin | Signal |
|-----|--------|
| 4, 5 | Ground |
| 6 | CAN High (ISO 15765-4) |
| 14 | CAN Low |
| 16 | Battery (+12V) |

Most post-2008 vehicles use ISO 15765-4 (CAN-based OBD-II). Older vehicles may use ISO 9141 or KWP2000 — the ELM327 handles protocol detection automatically.

## OBD-II modes

| Mode | Purpose | Example |
|------|---------|---------|
| 01 | Current powertrain data | RPM, speed, temperature |
| 02 | Freeze frame data | Snapshot when DTC was set |
| 03 | Stored DTCs | P0301 (cylinder 1 misfire) |
| 04 | Clear DTCs | Reset check engine light |
| 09 | Vehicle info | VIN, calibration ID |

Mode 01 is what telematics uses most — continuous polling of live data.

## Request-response over ISO-TP

OBD-II over CAN uses ISO-TP (ISO 15765-2) for transport. A simple PID request:

```
Request:  CAN ID 0x7DF (broadcast) → Data: 02 01 0C 00 00 00 00 00
          │     │   └── PID 0x0C (RPM)
          │     └── Mode 01
          └── 2 bytes follow

Response: CAN ID 0x7E8 (ECU response) → Data: 04 41 0C 0F A0 00 00 00
          │      │   │   └── RPM = 0x0FA0 = 4000
          │      │   └── PID 0x0C
          │      └── Mode 01 + 0x40 (response offset)
          └── 4 bytes follow
```

RPM formula: `(A * 256 + B) / 4` → `(0x0F * 256 + 0xA0) / 4 = 1000 RPM`.

## Reading PIDs with python-OBD

```python
import obd

connection = obd.OBD()  # auto-detects port and protocol
if not connection.is_connected():
    raise ConnectionError("OBD adapter not found")

# Query supported PIDs
supported = connection.query(obd.commands.PIDS_A)

# Read live data
rpm = connection.query(obd.commands.RPM)
speed = connection.query(obd.commands.SPEED)
coolant = connection.query(obd.commands.COOLANT_TEMP)

print(f"RPM: {rpm.magnitude}, Speed: {speed.magnitude} km/h, Coolant: {coolant.magnitude}°C")
```

For custom PIDs not in the library:

```python
from obd import OBDCommand, OBDMode
from obd.decoders import unsigned

cmd = OBDCommand("CUSTOM_TEMP", "Custom temperature", b"\x01\x5B",
                 2, OBDMode.CURRENT, unsigned, True)
response = connection.query(cmd)
```

## DTC codes

Mode 03 returns stored trouble codes:

```
> 03
43 01 33 00 00 00 00 00
   │  └── DTC: 0x0133 → P0133 (O2 sensor slow response, bank 1)
   └── 1 DTC stored
```

DTC format: `[Type][System][Code]`
- **P** — Powertrain (P0xxx = standard, P1xxx = manufacturer)
- **C** — Chassis
- **B** — Body
- **U** — Network

Fleet use case: poll DTCs on ignition-on, alert fleet manager if new codes appear, include freeze frame data (Mode 02) for context.

## Building a diagnostic pipeline

For fleet telematics, the architecture:

```
Vehicle OBD-II port
    → CAN adapter (embedded or dongle)
    → Edge device (poll PIDs every 1-10s)
    → MQTT/HTTP → Cloud ingestion
    → Time-series DB + alert rules
```

Polling strategy:
- **Ignition-on burst** — read all supported PIDs + DTCs once
- **Driving interval** — RPM, speed, fuel level every 10s
- **Idle** — reduce to every 60s or stop polling
- **Ignition-off** — final DTC check, then sleep

Don't poll at 100ms — you'll flood the bus and drain the vehicle battery.

## ELM327 for prototyping

AT commands over serial/Bluetooth:

```
ATZ          → Reset
ATE0         → Echo off
0100         → Supported PIDs [01-20]
010C         → Engine RPM
03           → Read DTCs
04           → Clear DTCs
0902         → VIN (Mode 09)
```

Fine for a single-vehicle prototype. For a fleet of 500 vehicles, use direct CAN with proper error handling, reconnection logic, and ISO-TP implemented in your firmware.

## Fleet diagnostic alerting

Raw PID streams are useless without alert rules. Define thresholds per vehicle class:

| Signal | Warning | Critical | Action |
|--------|---------|----------|--------|
| Coolant temp (PID 0x05) | > 105°C | > 115°C | Dispatch maintenance |
| Engine RPM at idle | > 1200 sustained | > 1500 | Check idle air control |
| Fuel trim (STFT/LTFT) | ±15% | ±25% | Emissions / injector issue |
| Battery voltage (PID 0x42) | < 12.2V running | < 11.8V | Alternator failure imminent |
| New DTC (Mode 03) | Any P0xxx | P0300 misfire | Create work order |

Debounce alerts: coolant spike during hill climb differs from sustained overheat. Require three consecutive readings above threshold, or use a rolling 60-second window.

## Security and bus access

OBD-II ports are physically accessible — anyone with a dongle can read VIN, clear DTCs, or inject frames on some vehicles. For fleet deployments:

- **Authenticate dongles** — device certificate bound to vehicle ID
- **Read-only mode** — firmware rejects Mode 04 (clear DTCs) unless authenticated service session
- **Rate limit** — detect abnormal frame rates indicating bus flooding
- **Segment telematics** — separate CAN channel from safety-critical ECUs where architecture allows

Regulatory note: tampering with emissions-related DTCs has legal implications in many jurisdictions. Log every clear-DTC attempt with operator identity.

## Debugging common failures

**No response from ECU:** Check baud rate (500 kbps vs 250 kbps), confirm ignition on (some ECUs sleep), verify OBD pin 16 has 12V.

**Intermittent timeouts:** Loose dongle connector, EMI from alternator, or bus contention from another module polling aggressively.

**NRC 0x78 (response pending):** ECU needs more time — extend timeout to 5 seconds for Mode 09 VIN reads on some manufacturers.

**Wrong PID values:** Verify byte order and scaling formula — manufacturer-specific PIDs (Mode 22) differ from standard Mode 01.

Pair with [Android BLE for vehicle dongles](https://blog.michaelsam94.com/android-ble-bluetooth-low-energy/) when your edge device connects over Bluetooth rather than wired CAN.

## Production checklist

- [ ] Polling intervals respect vehicle battery (idle backoff)
- [ ] DTC alerts debounced with sustained-threshold logic
- [ ] Dongle firmware rejects unauthorized Mode 04 clears
- [ ] Fleet dashboard shows last-seen timestamp per vehicle
- [ ] ISO-TP timeout handling tested on target ECU brands

## Resources

- [SAE J1979 — E/E Diagnostic Test Modes](https://www.sae.org/standards/content/j1979_202102/) — the OBD-II standard defining modes and PIDs
- [python-OBD documentation](https://python-obd.readthedocs.io/) — Python library for OBD-II communication
- [ISO 15765-4 — CAN-based OBD-II](https://www.iso.org/standard/66574.html) — transport protocol specification
- [OBD-II PID codes reference (Wikipedia)](https://en.wikipedia.org/wiki/OBD-II_PIDs) — comprehensive PID list with formulas
