---
title: "The OCPP 2.0.1 Device Model"
slug: "ocpp-2-0-1-device-model"
description: "Understand the OCPP 2.0.1 Device Model: components, variables, monitoring, and how it replaces the OCPP 1.6 configuration key approach."
datePublished: "2025-10-21"
dateModified: "2025-10-21"
tags: ["IoT", "EV Charging", "OCPP", "Protocols"]
keywords: "OCPP 2.0.1 device model, OCPP components variables, EV charging protocol, OCPP configuration, charging station management, OCPP monitoring"
faq:
  - q: "How is the OCPP 2.0.1 Device Model different from OCPP 1.6 configuration keys?"
    a: "OCPP 1.6 uses flat key-value configuration (e.g., MeterValueSampleInterval). OCPP 2.0.1 organizes settings into a hierarchy of components (Controller, EVSE, Connector) and variables (AvailabilityState, SupplyPhases), enabling standardized monitoring, reporting, and firmware management across vendors."
  - q: "What are the main component types in the Device Model?"
    a: "ChargingStation (root), EVSE (charging point with connectors), Connector (physical plug), and sub-components like Controller, PowerContactor, and Metering. Each component has variables describing its state and configuration."
  - q: "Do I need the Device Model if I only use basic charging?"
    a: "Yes. Even simple Start/Stop transactions in OCPP 2.0.1 reference Device Model variables for connector availability and authorization. Skipping the model means you cannot interoperate with CSMS platforms expecting standard component reporting."
---

Your CSMS integration worked with OCPP 1.6 by reading configuration keys like `MeterValueSampleInterval` and `ConnectionTimeOut`. The new charger fleet ships with OCPP 2.0.1, and the configuration screen is gone—replaced by a tree of components and variables. The connector is not "available" anymore; `Connector.AvailabilityState` is `Available` on `EVSE 1 / Connector 1`. The Device Model is the structural foundation of OCPP 2.0.1, and every other feature—smart charging, monitoring, firmware updates—builds on it.

## Component hierarchy

```
ChargingStation
├── Controller
│   ├── Clock
│   └── PowerContactor
├── EVSE (id=1)
│   ├── Connector (id=1)
│   │   ├── AvailabilityState
│   │   └── ConnectorType
│   └── Metering
│       ├── Energy.Active.Import.Register
│       └── Power.Active.Import
└── EVSE (id=2)
    └── Connector (id=1)
```

Each node is a **component** identified by `(name, instance)`. Each property is a **variable** with attributes (actual value, target value, mutability).

## Variable attributes

| Attribute | Meaning |
|-----------|---------|
| Actual | Current measured or reported value |
| Target | Desired value (set by CSMS) |
| MinLimit / MaxLimit | Allowed range |
| Mutability | ReadOnly, WriteOnly, ReadWrite |

```json
{
  "component": { "name": "Connector", "evse": { "id": 1 }, "connectorId": 1 },
  "variable": { "name": "AvailabilityState" },
  "variableAttribute": [{
    "type": "Actual",
    "value": "Available",
    "mutability": "ReadOnly"
  }]
}
```

## GetVariables and SetVariables

**CSMS reads a variable:**

```json
// Request
[{
  "component": { "name": "Metering", "evse": { "id": 1 } },
  "variable": { "name": "Energy.Active.Import.Register" }
}]

// Response
[{
  "attributeStatus": "Accepted",
  "variableAttribute": [{ "type": "Actual", "value": "45230.5" }]
}]
```

**CSMS sets a variable:**

```json
// Request
[{
  "component": { "name": "Controller" },
  "variable": { "name": "MeterValueSampleInterval" },
  "variableAttribute": [{ "type": "Actual", "value": "60" }]
}]
```

SetVariables replaces OCPP 1.6 `ChangeConfiguration`.

## Monitoring with NotifyMonitoringReport

OCPP 2.0.1 supports proactive monitoring:

```
CSMS → SetMonitoringBase (component, variable, severity, threshold)
Charger → NotifyMonitoringEvent (when threshold breached)
```

```json
{
  "eventData": [{
    "component": { "name": "Metering", "evse": { "id": 1 } },
    "variable": { "name": "Power.Active.Import" },
    "variableMonitoringId": 1,
    "type": "UpperThreshold",
    "severity": 3,
    "actualValue": "22000",
    "thresholdValue": "20000"
  }]
}
```

Configure monitors for power draw, temperature, and communication health without polling.

## Standardized component catalog

OCPP 2.0.1 Part 2 Appendix defines required components:

| Component | Required variables |
|-----------|-------------------|
| ChargingStation | AvailabilityState, Problem |
| EVSE | AvailabilityState, AllowedEnergyTransfer |
| Connector | AvailabilityState, ConnectorType |
| Metering | Energy.Active.Import.Register, Power.Active.Import |

Vendor-specific components extend the model under a custom namespace. Your CSMS should handle unknown components gracefully.

## Implementation approach

**Charger firmware:**

```c
typedef struct {
    char name[64];
    int evse_id;
    int connector_id;
} Component;

typedef struct {
    char name[64];
    char actual_value[256];
    Mutability mutability;
} Variable;

int get_variable(Component *comp, Variable *var, char *value);
int set_variable(Component *comp, Variable *var, const char *value);
```

Maintain an in-memory registry mapping component paths to hardware state. Update Actual values on hardware events; validate Target values on SetVariables.

**CSMS side:** Cache the Device Model per charging station. On connect, send `GetBaseReport` (ConfigurationInventory or FullInventory) to discover available components.

## Migration from OCPP 1.6

| OCPP 1.6 | OCPP 2.0.1 Device Model |
|----------|------------------------|
| `GetConfiguration` | `GetVariables` / `GetBaseReport` |
| `ChangeConfiguration` | `SetVariables` |
| `MeterValueSampleInterval` key | `Controller.MeterValueSampleInterval` variable |
| `ConnectorPhaseRotation` key | `EVSE.PowerContactor.SupplyPhases` variable |

Map your 1.6 keys to 2.0.1 component paths during migration.

## Monitoring and reporting in OCPP 2.0.1

Device Model enables structured monitoring beyond 1.6's flat configuration:

```json
{
  "setMonitoringLevel": {
    "severity": 3,
    "transactionId": 1
  }
}
```

Set monitoring levels per component — severity 0 (debug) to 9 (critical). CSMS receives `NotifyEvent` when monitored variables cross thresholds:

```json
{
  "notifyEvent": {
    "generatedAt": "2024-12-27T10:00:00Z",
    "eventData": [{
      "component": {"name": "EVSE", "evse": {"id": 1}},
      "variable": {"name": "Temperature"},
      "actualValue": "85",
      "trigger": "Alerting",
      "severity": 7
    }]
  }
}
```

Map NotifyEvent severity to your alerting system — severity ≥7 → PagerDuty, ≥4 → Slack.

## Custom components and variables

Beyond the standardized catalog, define vendor-specific components:

```json
{
  "component": {"name": "DisplayUnit", "instance": "1"},
  "variable": {"name": "Brightness"},
  "attributes": [
    {"type": "Actual", "value": "80"},
    {"type": "MinSet", "value": "10"},
    {"type": "MaxSet", "value": "100"}
  ]
}
```

Custom components extend the model without breaking CSMS compatibility — CSMS ignores unknown components gracefully. Document custom components in your OCPP implementation guide for CSMS partners.

## Dual-stack migration strategy

Run OCPP 1.6 and 2.0.1 simultaneously during migration:

```
Phase 1: OCPP 1.6 production + 2.0.1 pilot on new stations
Phase 2: CSMS supports both protocols; 1.6 stations migrated firmware-by-firmware
Phase 3: 1.6 deprecated; all stations on 2.0.1 Device Model
```

Maintain a mapping table during dual-stack:

```python
CONFIG_MAP = {
    "MeterValueSampleInterval": "Controller.MeterValueSampleInterval",
    "ConnectorPhaseRotation": "EVSE.PowerContactor.SupplyPhases",
    "HeartbeatInterval": "OCPPCommCtrlr.HeartbeatInterval",
}
```

Translate 1.6 GetConfiguration responses from 2.0.1 Device Model state — CSMS sees consistent values regardless of protocol version.

## Failure modes

- **1.6 keys hardcoded in CSMS** — migration breaks existing integrations
- **Custom components not documented** — CSMS can't display vendor-specific state
- **Monitoring not configured** — hardware faults discovered only on user report
- **Variable Actual not updated on hardware events** — CSMS shows stale state
- **SetVariables without validation** — invalid Target values sent to hardware

## Production checklist

- 1.6 → 2.0.1 configuration key mapping documented
- Device Model registry maintained in firmware
- NotifyEvent severity mapped to alerting tiers
- Custom components documented for CSMS partners
- Dual-stack support during migration period
- GetBaseReport on every station connect for inventory sync

## Common production mistakes

Teams get ocpp 2 0 1 device model wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of ocpp 2 0 1 device model fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OCPP 2.0.1 Part 2 Specification](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — official Device Model definition
- [OCPP 2.0.1 Part 2 Appendix (Component/Variable catalog)](https://www.openchargealliance.org/) — standardized component list
- [Open Charge Alliance](https://www.openchargealliance.org/) — protocol governance and test tools
- [OCPP 2.0.1 JSON schemas](https://github.com/OpenChargingCloud/WOCPI) — message validation schemas
- [EV charging protocol comparison (IEA)](https://www.iea.org/reports/global-ev-outlook-2024) — industry context
