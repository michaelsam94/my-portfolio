---
title: "Device Shadows and Digital Twins"
slug: "iot-device-shadow-twin"
description: "Use device shadows and digital twins for IoT state management: desired vs reported state, offline sync, conflict resolution, and AWS IoT Shadow vs Azure Digital Twins."
datePublished: "2025-07-25"
dateModified: "2025-07-25"
tags: ["IoT", "Embedded", "Architecture", "Backend"]
keywords: "device shadow IoT, digital twin, desired reported state, AWS IoT Shadow, offline sync IoT, IoT state management"
faq:
  - q: "What is a device shadow?"
    a: "A device shadow is a cloud-side JSON document that stores the last known state of a device — both what the device reports (reported state) and what the cloud wants it to be (desired state). When a device reconnects after being offline, it reads the shadow to get commands it missed and publishes its current state to update the reported side."
  - q: "What's the difference between a device shadow and a digital twin?"
    a: "A device shadow is a lightweight state document (typically JSON with desired/reported/metadata sections) focused on command-and-control sync. A digital twin is a richer model — it includes relationships, spatial context, simulation capabilities, and historical telemetry. Shadows solve sync; twins solve modeling and analytics."
  - q: "How do shadows handle conflicts when both cloud and device update state?"
    a: "Shadows use version numbers. Each update increments the version. If the device publishes a reported state with a stale version, the update is rejected. For desired state, the cloud always wins — the device reads the latest desired state on reconnect and applies it. Merge conflicts in individual fields are resolved by timestamp (latest wins) or by explicit priority rules."
---

Your app sets a thermostat to 22°C. The command goes to the cloud. The thermostat is offline — it's on a weak Wi-Fi link and drops every few hours. Without a shadow, the command is lost and the user thinks the app is broken. With a shadow, the desired state sits in the cloud document. When the thermostat reconnects, it reads `{ "desired": { "targetTemp": 22 } }`, applies it, and reports back `{ "reported": { "targetTemp": 22 } }`. The user never knows there was an outage.

## Shadow document structure

```json
{
  "state": {
    "desired": {
      "targetTemp": 22,
      "mode": "heat",
      "fanSpeed": "auto"
    },
    "reported": {
      "targetTemp": 20,
      "mode": "heat",
      "fanSpeed": "auto",
      "currentTemp": 19.5,
      "humidity": 45
    },
    "delta": {
      "targetTemp": 22
    }
  },
  "metadata": {
    "desired": {
      "targetTemp": { "timestamp": 1721900000 }
    },
    "reported": {
      "targetTemp": { "timestamp": 1721890000 },
      "currentTemp": { "timestamp": 1721900100 }
    }
  },
  "version": 47,
  "timestamp": 1721900200
}
```

Key concepts:
- **desired** — what the cloud/app wants. Written by the backend or app.
- **reported** — what the device actually is. Written by the device.
- **delta** — computed diff (desired minus reported). Tells the device what to change.
- **version** — monotonically increasing. Prevents stale updates.

## Device-side shadow sync

```python
def on_connect(client):
    client.subscribe(f"$aws/things/{THING_NAME}/shadow/update/delta")
    client.subscribe(f"$aws/things/{THING_NAME}/shadow/get/accepted")
    client.publish(f"$aws/things/{THING_NAME}/shadow/get", "")

def on_delta(client, delta):
    if "targetTemp" in delta:
        set_thermostat_temp(delta["targetTemp"])
    if "mode" in delta:
        set_mode(delta["mode"])

    report_state(client, {
        "targetTemp": get_current_target(),
        "mode": get_current_mode(),
        "currentTemp": read_sensor(),
    })

def report_state(client, state):
    client.publish(
        f"$aws/things/{THING_NAME}/shadow/update",
        json.dumps({"state": {"reported": state}}),
    )
```

Flow:
1. Device connects → requests current shadow
2. Cloud sends shadow → device computes local delta
3. Device applies changes → reports new state
4. Cloud clears delta when desired == reported

## App-side interaction

The mobile app never talks to the device directly — it updates the shadow:

```javascript
async function setTemperature(thingName, temp) {
  await iotData.updateThingShadow({
    thingName,
    payload: JSON.stringify({
      state: { desired: { targetTemp: temp } },
    }),
  }).promise();
}

async function getDeviceState(thingName) {
  const shadow = await iotData.getThingShadow({ thingName }).promise();
  return JSON.parse(shadow.payload).state;
}
```

The app reads `reported` for current state and writes `desired` for commands. It can show a "pending" indicator when desired != reported.

## Named shadows

AWS IoT supports multiple shadows per device:

```
$aws/things/{name}/shadow/name/{shadowName}/update
```

Use cases:
- **Classic shadow** — primary operational state (temperature, mode)
- **Config shadow** — firmware version, reporting interval, thresholds
- **Diagnostics shadow** — error codes, uptime, last reboot reason

Separating concerns prevents a config update from racing with an operational command.

## Digital twins for complex assets

When shadows aren't enough — you need relationships, spatial models, or simulation — use a digital twin platform:

```json
{
  "@id": "dtmi:com:acme:ChargingStation;1",
  "@type": "ChargingStation",
  "serialNumber": "CS-0042817",
  "location": { "@id": "dtmi:com:acme:Site;1", "name": "Downtown Garage L2" },
  "connectors": [
    { "@type": "Connector", "id": 1, "status": "Available", "maxPowerKW": 22 },
    { "@type": "Connector", "id": 2, "status": "Charging", "maxPowerKW": 22 }
  ],
  "relationships": {
    "locatedAt": "dtmi:com:acme:Site;downtown-garage",
    "connectedTo": "dtmi:com:acme:EnergyMeter;em-0042"
  }
}
```

Twins model **relationships** (this charger is at this site, fed by this meter) that shadows can't express. Use twins for fleet topology, asset management, and simulation. Use shadows for real-time command sync.

## Conflict resolution patterns

| Scenario | Resolution |
|----------|-----------|
| App sets temp to 22, device still reports 20 | Normal — delta triggers device update |
| Device offline for days, desired changed 5 times | Device reads latest desired on reconnect (last write wins) |
| Device reports field not in desired | Allowed — reported can have extra fields |
| Simultaneous desired updates | Version increment — latest timestamp wins |
| Device rejects a desired value (out of range) | Device reports error in reported state; cloud alerts |

```json
{
  "state": {
    "reported": {
      "targetTemp": 20,
      "lastCommandError": "targetTemp 35 exceeds max 30"
    }
  }
}
```

Resolve shadow conflicts with version numbers, not timestamps — clock skew on IoT devices makes timestamp merge unreliable.

## Shadow document size limits

AWS IoT shadows limit document size to 8 KB — design reported state carefully:

```json
{
  "reported": {
    "firmwareVersion": "2.1.0",
    "status": "online",
    "metrics": { "temp": 22.5, "humidity": 45 }
  }
}
```

Store historical telemetry in Timestream or DynamoDB, not shadow reported state. Shadow is current state sync, not time-series database.

## Offline device behavior

When device reconnects after outage:

1. Device receives full desired state delta
2. Applies changes in order
3. Reports updated state
4. Cloud clears delta

Test with simulated 72-hour offline — desired state may have changed multiple times. Device must apply latest desired, not replay every intermediate value.

## MQTT topic conventions

```
$aws/things/{thingName}/shadow/update/accepted
$aws/things/{thingName}/shadow/update/delta
$aws/things/{thingName}/shadow/get
```

Subscribe to `/delta` for changes only — polling full shadow wastes bandwidth on cellular-connected devices.

Pair with [MQTT topic design patterns](https://blog.michaelsam94.com/mqtt-topic-design-patterns/) for fleet-wide topic hierarchy alongside per-device shadow topics.

## Common production mistakes

Teams get device shadow twin wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of device shadow twin fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Resources

- [AWS IoT Device Shadow service](https://docs.aws.amazon.com/iot/latest/developerguide/iot-device-shadows.html) — shadow document format and MQTT topics
- [Azure Digital Twins documentation](https://learn.microsoft.com/en-us/azure/digital-twins/) — DTDL modeling and twin graph queries
- [AWS IoT Named Shadows](https://docs.aws.amazon.com/iot/latest/developerguide/device-shadow-combined-naming.html) — multiple shadows per device
- [Digital Twin Consortium definition](https://www.digitaltwinconsortium.org/initiatives/the-definition-of-a-digital-twin/) — industry definition and use cases
