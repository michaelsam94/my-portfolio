---
title: "Efficient Telemetry with Protobuf"
slug: "iot-telemetry-protobuf-compression"
description: "Encode IoT telemetry efficiently with Protocol Buffers: schema design, nanopb on MCUs, delta encoding, batching, and bandwidth math that keeps cellular bills predictable."
datePublished: "2025-09-14"
dateModified: "2025-09-14"
tags: ["IoT", "Edge Computing", "Protobuf", "Networking"]
keywords: "IoT protobuf telemetry, nanopb embedded, protobuf vs JSON IoT, telemetry compression, schema evolution protobuf"
faq:
  - q: "Why use Protobuf instead of JSON for IoT telemetry?"
    a: "Protobuf is binary, typed, and typically 3–10× smaller than JSON for numeric sensor data — no field names repeated on every message, compact varint encoding for integers. Parsing is faster and allocation-free with generated code. JSON wins for human debugging and ad-hoc tools; Protobuf wins for bandwidth-constrained links and high-frequency streams."
  - q: "Can I use Protobuf on memory-constrained MCUs?"
    a: "Yes, with nanopb — a small Protobuf implementation for embedded C. Define .proto files, generate static structs with size limits, and encode/decode without malloc. Keep messages small, avoid strings where enums suffice, and use fixed32/fixed64 for floats if varint savings do not apply."
  - q: "How do I evolve Protobuf schemas without breaking deployed devices?"
    a: "Follow protobuf wire compatibility rules: never change field numbers, add new fields with new numbers (old firmware ignores them), reserve removed field numbers, and use optional/default semantics carefully. Deploy gateway translation layers when breaking changes are unavoidable — do not OTA-flash every sensor simultaneously."
---

The cellular bill spiked because firmware shipped temperature readings as JSON — `"device_id": "sensor-a1b2c3d4e5f6", "temperature_celsius": 23.4, "humidity_percent": 41.2` — forty-seven bytes of field names on every 30-second uplink across ten thousand devices. Switching to Protobuf dropped average payload size from 180 bytes to 28, without changing what the cloud stored. Efficient telemetry is not about exotic compression algorithms; it is about choosing a wire format that matches how sensors actually produce data.

## Size comparison on real sensor payloads

Same reading, three encodings:

**JSON (minified):** ~85 bytes
```json
{"id":"a1b2","ts":1718452800,"t":234,"h":412,"batt":87}
```

**Protobuf (encoded):** ~18–24 bytes depending on field numbers and varint packing

**CBOR:** ~25–35 bytes — middle ground, schema-less

Protobuf wins when you send thousands of structurally identical messages. JSON wins for one-off debugging — use both: Protobuf on the wire, decode to JSON at the gateway for logs.

## Schema design for sensors

```protobuf
syntax = "proto3";

message TelemetryReading {
  fixed32 device_id = 1;      // 4 bytes, not a string UUID
  fixed32 ts_epoch = 2;       // unix seconds
  sint32 temp_centi = 3;        // 23.4°C → 234, zigzag varint
  uint32 humidity_deci = 4;   // 41.2% → 412
  uint32 battery_pct = 5;       // 0-100
}
```

Design choices:

- **Avoid string device IDs on-device** — map to `fixed32` or `uint64` factory-programmed IDs; resolve names in the cloud.
- **Use fixed-point integers** — `sint32 temp_centi` avoids float portability issues and often encodes smaller than `float`.
- **Batch readings** — `repeated TelemetryReading readings = 1` amortizes MQTT/TCP overhead.

```protobuf
message TelemetryBatch {
  repeated TelemetryReading readings = 1;
  uint32 batch_seq = 2;
}
```

Send batches every N seconds or M samples, whichever comes first.

## nanopb on embedded targets

Generate C structs with size limits:

```bash
python nanopb/generator/nanopb_generator.py telemetry.proto
```

```c
#include "telemetry.pb.h"
#include "pb_encode.h"

bool encode_reading(uint8_t *buf, size_t buf_size, size_t *written) {
    TelemetryReading msg = TelemetryReading_init_zero;
    msg.device_id = device_id;
    msg.ts_epoch = (uint32_t)time(NULL);
    msg.temp_centi = (int32_t)(temp * 100);
    msg.humidity_deci = (uint32_t)(rh * 10);
    msg.battery_pct = battery;

    pb_ostream_t stream = pb_ostream_from_buffer(buf, buf_size);
    if (!pb_encode(&stream, TelemetryReading_fields, &msg)) {
        return false;
    }
    *written = stream.bytes_written;
    return true;
}
```

Set `max_size` on repeated fields in `.options` to bound stack usage:

```
TelemetryBatch.readings max_count:16
```

## Delta and changed-field encoding

When values change slowly, send deltas:

```protobuf
message TelemetryDelta {
  fixed32 device_id = 1;
  fixed32 ts_epoch = 2;
  optional sint32 temp_centi = 3;   // omitted if unchanged
  optional uint32 humidity_deci = 4;
}
```

Protobuf proto3 `optional` presence tracking omits unset fields on the wire — natural delta encoding. Firmware tracks last-sent values and only sets fields that moved beyond a deadband (e.g., temperature change > 0.2°C).

## Compression layers

Protobuf is not a compressor. Add gzip or LZ4 at the transport layer for batches:

| Layer | Best for |
|-------|----------|
| Protobuf alone | Single small messages |
| Protobuf + LZ4 | Gateway batches, low CPU |
| Protobuf + gzip | HTTP uploads, larger archives |

Do not gzip individual 20-byte MQTT payloads — header overhead exceeds savings. Batch first, then compress.

## Gateway decode and schema evolution

Gateways decode Protobuf and emit Avro/Parquet/JSON for analytics:

```python
from telemetry_pb2 import TelemetryBatch

def handle_mqtt(topic: bytes, payload: bytes):
    batch = TelemetryBatch()
    batch.ParseFromString(payload)
    for r in batch.readings:
        publish_to_kafka({
            "device_id": resolve_id(r.device_id),
            "ts": r.ts_epoch,
            "temp_c": r.temp_centi / 100.0,
            "humidity": r.humidity_deci / 10.0,
        })
```

When adding `pressure_pa = 6`, old firmware omits it — consumers must treat missing fields as null. Never reuse field number 5 for a different meaning.

## Bandwidth budgeting

Calculate monthly bytes per device:

```
bytes/month = (payload + overhead) × rate × 86400/interval × 30
```

Example: 30-byte payload + 20-byte MQTT overhead, every 60 s:
`(50) × (86400/60) × 30 = 2.16 MB/month/device`

At 10,000 devices on LTE-M, that is 21.6 TB — pricing makes encoding choice a finance decision, not just engineering elegance.

Compare against JSON on the same link before committing — a week of shadow-mode dual encoding on a representative device cohort usually reveals whether savings justify schema tooling. If payloads stay under 200 bytes and uplink is Wi-Fi, JSON may be fine. If payloads repeat field names hundreds of times per hour over cellular, Protobuf typically pays back within one billing cycle.

## Debugging without giving up binary wire format

Protobuf is opaque on the wire, which frustrates field debugging. Mitigations that work in production:

- Decode at the gateway and log JSON at `DEBUG` level only, redacting sensitive fields.
- Attach a `schema_version` uint32 field (field number 100+) so consumers detect mismatches before parse exceptions.
- Keep `.proto` files in version control and generate code in CI — drift between firmware and cloud schema is the most common decode failure in the field.

When decode fails, return a structured error to the device (`BAD_PAYLOAD`) rather than silently dropping — firmware teams need signal to distinguish corruption from schema skew.

## Common production mistakes

Teams get telemetry protobuf compression wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of telemetry protobuf compression fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When telemetry protobuf compression misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Protocol Buffers documentation](https://protobuf.dev/programming-guides/proto3/)
- [nanopb — Protocol Buffers for embedded C](https://jpa.kapsi.fi/nanopb/)
- [Protobuf encoding reference (wire format)](https://protobuf.dev/programming-guides/encoding/)
- [MQTT payload best practices (HiveMQ)](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/)
- [CloudEvents with Protobuf bindings](https://cloudevents.io/)
