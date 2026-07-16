---
title: "MeterValues and Sampled Data"
slug: "ocpp-metervalues-sampled-data"
description: "Configure OCPP MeterValues and sampled data: measurands, sampling intervals, clock-aligned reporting, and billing-grade energy measurement."
datePublished: "2025-11-02"
dateModified: "2025-11-02"
tags: ["IoT", "EV Charging", "OCPP", "Energy"]
keywords: "OCPP MeterValues, sampled data OCPP, measurands OCPP, energy metering EV charging, clock-aligned MeterValues, OCPP billing data"
faq:
  - q: "What is the difference between MeterValues and a meter reading?"
    a: "A meter reading is the cumulative energy register value at a point in time (like an odometer). MeterValues in OCPP are sampled data points sent during a transaction, each containing one or more measurands (energy, power, voltage, current) with timestamps. Billing uses the difference between start and stop register readings."
  - q: "How often should MeterValues be sampled?"
    a: "Every 60 seconds during active transactions is standard for billing and load management. Every 300 seconds suffices for analytics-only use. During off-peak with no active sessions, clock-aligned samples every 15 minutes provide grid monitoring data without excessive message volume."
  - q: "Which measurands are required for billing?"
    a: "Energy.Active.Import.Register (cumulative kWh) is the billing measurand. Power.Active.Import provides real-time load data. Voltage and Current per phase help diagnose installation issues but are not billing requirements."
---

The energy bill for a fleet charging site does not match the CSMS reports. Investigation finds MeterValues sent every 5 minutes with only power readings—no cumulative energy register. Billing needs the odometer-style register value at transaction start and stop, not instantaneous power snapshots. OCPP MeterValues carry sampled measurands during transactions and at clock-aligned intervals. Configure them wrong and your revenue data is useless.

## Measurands

| Measurand | Unit | Purpose |
|-----------|------|---------|
| `Energy.Active.Import.Register` | Wh | Billing (cumulative) |
| `Power.Active.Import` | W | Load management |
| `Voltage` | V | Installation diagnostics |
| `Current.Import` | A | Cable/connector monitoring |
| `SoC` | Percent | Vehicle state (if available) |
| `Temperature` | Celsius | Hardware health |

Request only the measurands you need. Each adds message size and processing cost.

## Sampled MeterValues during transactions

Sent via `MeterValues` message during active charging:

```json
{
  "connectorId": 1,
  "transactionId": 42,
  "meterValue": [{
    "timestamp": "2025-11-02T14:30:00Z",
    "sampledValue": [
      {
        "value": "45230.5",
        "measurand": "Energy.Active.Import.Register",
        "unit": "Wh",
        "context": "Sample.Periodic"
      },
      {
        "value": "7200",
        "measurand": "Power.Active.Import",
        "unit": "W",
        "context": "Sample.Periodic"
      }
    ]
  }]
}
```

Configure sampling interval via Device Model variable:

```
Controller.MeterValueSampleInterval = 60  (seconds)
```

Or OCPP 1.6: `ChangeConfiguration(MeterValueSampleInterval, 60)`.

## Clock-aligned MeterValues

Sent at fixed intervals regardless of transaction state:

```json
{
  "connectorId": 0,
  "meterValue": [{
    "timestamp": "2025-11-02T15:00:00Z",
    "sampledValue": [{
      "value": "128500.0",
      "measurand": "Energy.Active.Import.Register",
      "unit": "Wh",
      "context": "Sample.Clock"
    }]
  }]
}
```

```
Controller.ClockAlignedDataInterval = 900  (15 minutes)
```

Clock-aligned data supports grid monitoring and daily energy reconciliation without parsing transaction-level data.

## Billing calculation

```
energy_delivered = meter_stop - meter_start
cost = energy_delivered × tariff_rate
```

```python
def calculate_billing(start_tx: Transaction, stop_tx: Transaction, tariff) -> Bill:
    energy_wh = stop_tx.meter_stop - start_tx.meter_start
    energy_kwh = energy_wh / 1000

    duration = stop_tx.timestamp - start_tx.timestamp
    cost = tariff.calculate(energy_kwh, duration, stop_tx.timestamp)

    return Bill(
        transaction_id=start_tx.id,
        energy_kwh=energy_kwh,
        duration_minutes=duration.total_seconds() / 60,
        cost=cost,
    )
```

Validate: if `meter_stop < meter_start`, flag as meter rollover or data error.

## SampledValue context field

| Context | Meaning |
|---------|---------|
| `Sample.Periodic` | Regular interval during transaction |
| `Sample.Clock` | Clock-aligned interval |
| `Transaction.Begin` | Meter reading at transaction start |
| `Transaction.End` | Meter reading at transaction stop |
| `Interruption.Begin` | Power loss during session |
| `Interruption.End` | Power restored during session |

Store `Transaction.Begin` and `Transaction.End` readings separately from periodic samples. Billing uses these, not interpolated periodic values.

## Storage schema

```sql
CREATE TABLE meter_values (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(64) NOT NULL,
    connector_id INT NOT NULL,
    transaction_id INT,
    timestamp TIMESTAMPTZ NOT NULL,
    measurand VARCHAR(64) NOT NULL,
    value NUMERIC NOT NULL,
    unit VARCHAR(16) NOT NULL,
    context VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mv_station_time ON meter_values (station_id, timestamp);
CREATE INDEX idx_mv_transaction ON meter_values (transaction_id);
```

At 60-second sampling with 4 measurands across 100 chargers: ~576,000 rows/day. Partition by month.

## Data quality checks

```python
def validate_meter_values(tx_id: int, values: list[MeterValue]) -> list[str]:
    errors = []
    energy_readings = [v for v in values
                       if v.measurand == "Energy.Active.Import.Register"]

    for i in range(1, len(energy_readings)):
        if energy_readings[i].value < energy_readings[i-1].value:
            errors.append(f"Register decreased at {energy_readings[i].timestamp}")

    power_readings = [v for v in values if v.measurand == "Power.Active.Import"]
    for p in power_readings:
        if p.value < 0:
            errors.append(f"Negative power at {p.timestamp}")
        if p.value > 50000:  # 50 kW — adjust for your hardware
            errors.append(f"Power exceeds hardware max at {p.timestamp}")

    return errors
```

Alert on validation failures. A decreasing register indicates meter replacement or communication corruption.

## SampledValue data model

Each MeterValues message contains one or more SampledValue entries:

```json
{
  "connectorId": 1,
  "transactionId": 42,
  "meterValue": [{
    "timestamp": "2024-12-27T10:05:00Z",
    "sampledValue": [
      {
        "value": "15420",
        "context": "Sample.Periodic",
        "measurand": "Energy.Active.Import.Register",
        "unit": "Wh",
        "location": "Outlet"
      },
      {
        "value": "7400",
        "context": "Sample.Periodic",
        "measurand": "Power.Active.Import",
        "unit": "W",
        "location": "Outlet"
      }
    ]
  }]
}
```

Store each SampledValue as separate time-series row — not the raw JSON blob. Enables querying by measurand and aggregation.

## Billing-grade vs diagnostic sampling

Different measurands serve different purposes:

| Measurand | Purpose | Sample interval | Billing use |
|---|---|---|---|
| Energy.Active.Import.Register | Total energy delivered | 60s | Primary billing |
| Power.Active.Import | Instantaneous power | 15s | Load management |
| Current.Import | Current draw | 60s | Diagnostic |
| Voltage | Supply voltage | 300s | Diagnostic |
| SoC | Vehicle battery level | 60s | Smart charging |

Billing uses Register (cumulative Wh). Load management uses Power (instantaneous W). Don't bill on Power samples — integrate Power over time instead.

## Time-series storage schema

```sql
CREATE TABLE meter_values (
    transaction_id  INT NOT NULL,
    connector_id    INT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    measurand       TEXT NOT NULL,
    value           NUMERIC NOT NULL,
    unit            TEXT NOT NULL,
    context         TEXT,
    PRIMARY KEY (transaction_id, timestamp, measurand)
);

-- Billing query: energy delivered in session
SELECT MAX(value) - MIN(value) AS energy_wh
FROM meter_values
WHERE transaction_id = 42
  AND measurand = 'Energy.Active.Import.Register';
```

Partition by month on timestamp. Index on (transaction_id, measurand, timestamp).

## Failure modes

- **Billing on Power samples** — inaccurate; integrate Register instead
- **Raw JSON storage** — can't query by measurand; store normalized rows
- **No monotonicity validation** — decreasing Register undetected; billing errors
- **Sample interval too long for billing** — missed energy during gaps
- **Clock skew in timestamps** — session ordering breaks; enforce UTC

## Production checklist

- SampledValue stored as normalized time-series rows (not raw JSON)
- Register used for billing; Power for load management only
- Monotonicity validation on Register values (alert on decrease)
- Sample interval ≤60s for billing-grade Register measurements
- UTC timestamps enforced on all MeterValues
- Partition and index strategy for time-series query performance

## Resources

- [OCPP 1.6 MeterValues](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — message format and measurands
- [OCPP 2.0.1 Metering component](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — Device Model metering variables
- [IEC 62053 electricity metering](https://webstore.iec.ch/en/publication/57366) — meter accuracy standards
- [Eichrecht compliance (Germany)](https://www.bmwi.de/) — calibrated billing requirements
- [OCPI energy transfer](https://evroaming.org/ocpi-downloads/) — roaming billing data exchange
