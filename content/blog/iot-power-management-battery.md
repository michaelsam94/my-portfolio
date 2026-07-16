---
title: "Power Management for Battery Devices"
slug: "iot-power-management-battery"
description: "Design power management for battery-powered IoT devices: sleep modes, duty cycling, wake sources, energy profiling, and firmware patterns that stretch months of life from a coin cell."
datePublished: "2025-09-05"
dateModified: "2025-09-05"
tags: ["IoT", "Embedded", "Firmware", "Edge Computing"]
keywords: "IoT power management, battery IoT device, sleep mode firmware, duty cycling sensor, ESP32 deep sleep, coin cell battery life"
faq:
  - q: "How do I estimate battery life for an IoT sensor?"
    a: "Model average current draw as the weighted sum of active and sleep states: I_avg = (I_active × t_active + I_sleep × t_sleep) / period. Divide battery capacity (mAh) by I_avg to get hours. Include radio TX/RX bursts, sensor warm-up, and self-discharge. Measure on hardware with a shunt ammeter — spreadsheet estimates miss leakage and peripheral quiescent current."
  - q: "Deep sleep vs light sleep — when to use each?"
    a: "Deep sleep powers down RAM and most peripherals, drawing microamps but requiring full wake and re-init. Use it when the device wakes rarely (minutes to hours). Light sleep keeps RAM and RTC, wakes faster, but draws more current — suitable for sub-second response requirements or when reconnection latency matters. Match sleep depth to wake frequency and acceptable boot time."
  - q: "What wakes a battery device reliably?"
    a: "RTC timer for periodic telemetry, GPIO interrupt for door/motion events, and radio preamble detection for on-demand polls. Avoid polling sensors in a tight loop. Configure wake sources before entering sleep, validate wake cause on boot, and debounce GPIO interrupts to prevent wake storms from noisy lines."
---

A temperature sensor deployed in a walk-in freezer was supposed to run two years on a CR2032. It died in eleven weeks because firmware left the radio listening between uploads, the accelerometer stayed on "just in case," and nobody measured actual sleep current until field returns started. Battery-powered IoT is a budgeting problem: every millisecond awake and every microamp quiescent draws from a fixed pool you cannot recharge without a truck roll. The hardware datasheet numbers lie politely; your firmware decides whether the device lasts a season or a month.

## Measure before you optimize

You cannot optimize what you do not measure. Use a Nordic Power Profiler Kit, Joulescope, or even a precision shunt with an oscilloscope to capture:

- **Active burst** — sensor read + encode + radio TX
- **Idle between bursts** — CPU waiting, peripherals on
- **Sleep** — target state with wake sources armed
- **Leakage** — unintended current from floating GPIO, pull-ups, or regulator quiescent draw

Log energy per event, not just average current. A device that sleeps at 5 µA but TXes a 2 KB JSON packet every 30 seconds will still drain fast if the radio peak is poorly scheduled.

## Sleep hierarchy on typical MCUs

Most ARM Cortex-M and ESP32-class chips offer layered sleep:

| Mode | Typical current | RAM retained | Wake latency |
|------|-----------------|--------------|--------------|
| Run | mA | Yes | — |
| Idle / WFI | hundreds of µA | Yes | µs |
| Light sleep | tens of µA | Yes | ms |
| Deep sleep | single-digit µA | partial/none | tens of ms |

Enter the deepest sleep your wake latency budget allows. A freezer sensor reporting every 15 minutes has no reason to stay in light sleep between readings.

```c
// ESP-IDF pattern: deep sleep with RTC timer wake
void enter_deep_sleep_us(uint64_t us) {
    esp_sleep_enable_timer_wakeup(us);
    esp_deep_sleep_start();  // does not return
}

void app_main(void) {
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    if (cause == ESP_SLEEP_WAKEUP_TIMER) {
        read_and_transmit();
    }
    enter_deep_sleep_us(15 * 60 * 1e6);  // 15 minutes
}
```

On first boot (`ESP_SLEEP_WAKEUP_UNDEFINED`), run provisioning, then schedule the first sleep.

## Duty cycling the radio

The radio dominates energy on most sensor nodes. Rules:

1. **Batch telemetry** — one packet with ten readings beats ten packets with one reading.
2. **Match PHY to payload** — LoRa SF7 for short range saves TX time vs SF12; BLE connection intervals matter on coin cells.
3. **Connect, send, disconnect** — do not maintain MQTT keepalive on a battery node unless the product requires sub-minute downlink.
4. **Compress before TX** — Protobuf or CBOR reduces air time; see dedicated posts on telemetry encoding.

For Wi-Fi devices, prefer `esp_wifi_set_ps(WIFI_PS_MAX_MODEM)` between bursts, understanding it adds latency to the next association.

## Peripheral and GPIO hygiene

Floating GPIO pins leak current through input buffers. Before sleep:

```c
// Configure unused pins as input with pull-down (or pull-up per schematic)
for (int pin = UNUSED_START; pin <= UNUSED_END; pin++) {
    gpio_set_direction(pin, GPIO_MODE_INPUT);
    gpio_pullup_dis(pin);
    gpio_pulldown_en(pin);
}
```

Power down sensors explicitly — I2C devices often have a sleep register. Remove power from subsystems via load switch MOSFET when the schematic allows it; software sleep bits are not always enough.

Disable debug UART in production firmware. A floating TX line or always-on USB-serial bridge can cost hundreds of microamps.

## Wake sources and event-driven design

Replace polling loops with interrupts:

```c
void IRAM_ATTR motion_isr(void *arg) {
    // Set flag only — no I2C in ISR
    xSemaphoreGiveFromISR(wake_sem, NULL);
}

void sensor_task(void *arg) {
    for (;;) {
        xSemaphoreTake(wake_sem, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(50));  // debounce
        if (motion_still_active()) {
            capture_event();
        }
    }
}
```

RTC alarms handle periodic heartbeats. Combine: motion wakes immediately; RTC ensures at least one daily check-in even if no events occur.

## Firmware architecture for low power

Structure firmware as a state machine, not a `while(1)` loop:

```
BOOT → PROVISION (once) → SLEEP
         ↑                    ↓
         └── EVENT / TIMER → SAMPLE → TX → SLEEP
```

Each state has an explicit entry action and maximum duration. Watchdog-reset if TX hangs — a stuck association attempt drains the battery overnight.

Store configuration in NVS, not SD cards. Wear-level flash writes sparingly; batch config changes.

## Battery chemistry and deployment reality

Coin cells deliver less capacity at cold temperatures — critical for outdoor and cold-chain sensors. Size for worst-case temperature, not room-temp datasheet mAh.

Account for self-discharge: primary lithium cells lose a few percent per year; alkalines lose more. Rechargeable chemistries add cycle count limits.

Design for **replaceable** or **serviceable** batteries when product lifetime exceeds cell life. Firmware should report voltage trend so ops can schedule replacement before cliff-edge failure.

## Common production mistakes

Teams get power management battery wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of power management battery fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When power management battery misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [ESP-IDF Sleep Modes documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/sleep_modes.html)
- [Nordic Power Profiler Kit](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-II)
- [STM32 Low-Power modes application note](https://www.st.com/resource/en/application_note/an4365-stm32-microcontroller-system-memory-boot-mode-stmicroelectronics.pdf)
- [Zephyr PM subsystem](https://docs.zephyrproject.org/latest/services/pm/device.html)
- [TI CC13xx/CC26xx Power Management](https://dev.ti.com/tirex/explore/node?node=AKlB__c__j__zTI__DOT__com__Products__CC13x2__CC26x2__TechnicalReference)
