---
title: "Task Scheduling in FreeRTOS"
slug: "embedded-rtos-freertos-tasks"
description: "Configure FreeRTOS tasks for predictable scheduling: priorities, preemption, time slicing, synchronization primitives, and common priority inversion traps."
datePublished: "2025-11-28"
dateModified: "2025-11-28"
tags: ["IoT", "Embedded", "FreeRTOS", "RTOS"]
keywords: "FreeRTOS task scheduling, RTOS priorities, FreeRTOS preemption, mutex priority inheritance, vTaskDelay, FreeRTOS queue semaphore, task stack FreeRTOS"
faq:
  - q: "How many priority levels should I use in FreeRTOS?"
    a: "Use as few as possible — typically three to six distinct priorities. One priority for idle/low housekeeping, one for communication stacks, one for control loops, and one for safety-critical tasks. Too many adjacent priorities make starvation analysis harder without improving responsiveness."
  - q: "What is the difference between vTaskDelay and vTaskDelayUntil?"
    a: "vTaskDelay sleeps for a relative tick count from the call time — drift accumulates if work duration varies. vTaskDelayUntil anchors to an absolute wake time, ideal for fixed-period control loops that must run every N milliseconds regardless of how long the previous iteration took."
  - q: "When should I use a mutex instead of a semaphore in FreeRTOS?"
    a: "Use a mutex for protecting shared mutable state between tasks, especially when the holder may block — enable priority inheritance to avoid inversion. Use counting semaphores for signaling events (data ready, buffer slots) where no single owner concept exists. Binary semaphores for ISR-to-task signaling."
---

Bare-metal superloops collapse when three subsystems need different cadences: a 1 kHz motor control loop, an MQTT publish every five seconds, and a UI refresh at 30 Hz. FreeRTOS turns each into a task with its own stack and a priority the preemptive scheduler respects. Misconfigure priorities, though, and the MQTT task starves the motor loop because someone set them equal and enabled time slicing. Task scheduling in FreeRTOS is not "create threads and hope" — it is assigning urgency correctly and picking synchronization primitives that do not invert priorities.

## Creating tasks and stacks

```c
void sensor_task(void *pvParameters) {
    TickType_t last_wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(10);  // 100 Hz

    for (;;) {
        read_sensors();
        apply_control();
        vTaskDelayUntil(&last_wake, period);
    }
}

xTaskCreate(
    sensor_task,
    "sensor",
    512,              // stack depth in words, not bytes on most ports
    NULL,
    tskIDLE_PRIORITY + 3,
    &sensorHandle
);
```

Stack depth is port-specific — verify whether `configSTACK_DEPTH_TYPE` counts bytes or StackType_t words. Size with high-water marks under load.

## Preemption and time slicing

With `configUSE_PREEMPTION` enabled, higher-priority ready tasks run immediately when they unblock. Equal-priority ready tasks round-robin if `configUSE_TIME_SLICING` is on — each gets one tick slice.

Implications:

- Never run a tight loop at high priority without blocking — you starve everything below.
- Blocking calls (`vTaskDelay`, `xQueueReceive` with timeout) yield CPU voluntarily.
- ISRs can unblock higher tasks via `portYIELD_FROM_ISR`.

## Priority design pattern

A template I use for IoT gateways:

| Priority | Task | Period / trigger |
|----------|------|------------------|
| +4 | Safety / watchdog feed | Event |
| +3 | Control / sampling | Fixed 1–10 ms |
| +2 | Protocol encode/decode | Event-driven |
| +1 | Logging, metrics | Best effort |
| 0 | Idle | — |

Document the map in firmware README. Changing one task's priority without reviewing neighbors causes regressions.

## Queues, semaphores, and mutexes

**Queue** — pass data between tasks (struct copies or pointers with clear ownership):

```c
xQueueSend(measurementQueue, &sample, pdMS_TO_TICKS(5));
```

**Binary semaphore** — ISR signals task:

```c
xSemaphoreGiveFromISR(dataReadySem, &woken);
portYIELD_FROM_ISR(woken);
```

**Mutex with priority inheritance**:

```c
SemaphoreHandle_t busMutex = xSemaphoreCreateMutex();

if (xSemaphoreTake(busMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
    spi_transfer(...);
    xSemaphoreGive(busMutex);
}
```

Priority inheritance raises a low-priority mutex holder temporarily when a high-priority task blocks on the same mutex — critical for shared SPI/I2C buses.

## Priority inversion scenario

Task H (high) waits on mutex held by Task L (low). Task M (medium) preempts L — H waits on M indirectly. **Fix:** mutex with `configUSE_MUTEXES` and inheritance, or reduce critical section in L, or dedicated gatekeeper task at priority H that serializes bus access.

Never hold mutex across blocking network calls.

## Software timers and deferred work

Timer service task runs callbacks at `configTIMER_TASK_PRIORITY`:

```c
TimerHandle_t hb = xTimerCreate("hb", pdMS_TO_TICKS(1000), pdTRUE, NULL, heartbeat_cb);
xTimerStart(hb, 0);
```

Timer callbacks run in timer task context — keep them short; defer to worker tasks via queues for heavy work.

## Debugging scheduling issues

- `vTaskList()` / `vTaskGetRunTimeStats()` — who consumes CPU (needs `configGENERATE_RUN_TIME_STATS`).
- Tracealyzer or SystemView — visual timeline of preemption.
- Assert `configCHECK_FOR_STACK_OVERFLOW` >= 2 in development builds.

If a task misses deadlines, log ready-blocked state transitions before blindly raising priority — often the fix is shorter critical sections, not higher numbers.

## Memory management in FreeRTOS

Static allocation avoids heap fragmentation on long-running embedded devices:

```c
// Static task creation — no dynamic allocation
StaticTask_t xTaskBuffer;
StackType_t xStack[configMINIMAL_STACK_SIZE * 4];

TaskHandle_t handle = xTaskCreateStatic(
    vSensorTask, "Sensor", configMINIMAL_STACK_SIZE * 4,
    NULL, tskIDLE_PRIORITY + 2,
    xStack, &xTaskBuffer
);
```

Prefer static allocation for tasks created at boot. Dynamic (`xTaskCreate`) acceptable for tasks created once during initialization, not repeatedly.

Stack sizing: start with `configMINIMAL_STACK_SIZE * N`, enable `configCHECK_FOR_STACK_OVERFLOW`, run worst-case workload, check high-water mark with `uxTaskGetStackHighWaterMark()`.

## Tickless idle and power management

Battery-powered devices use tickless idle to sleep between tasks:

```c
#define configUSE_TICKLESS_IDLE 1
#define configEXPECTED_IDLE_TIME_BEFORE_SLEEP 3
```

CPU sleeps until next timer or interrupt. Tradeoff: slightly less precise `vTaskDelay` timing. Essential for IoT sensors on battery — can extend battery life 10× vs busy-wait polling.

## Multi-core FreeRTOS (SMP)

FreeRTOS SMP on dual-core MCUs (ESP32, STM32H7):

```c
#define configNUMBER_OF_CORES 2
#define configRUN_MULTIPLE_PRIORITIES 0  // classic priority scheduling
```

Pin interrupt-heavy tasks (network stack) to one core, application logic to other. Avoid shared mutable state between cores — use queues for cross-core communication, same as inter-task.

## Failure modes

- **Stack overflow undetected** — silent corruption; enable overflow checking in dev builds
- **Priority inversion** — high task blocked by low task holding mutex; use priority inheritance
- **Blocking call in critical section** — holds mutex across network I/O; blocks all waiters
- **Dynamic task create/destroy in loop** — heap fragmentation on embedded heap
- **Tick interrupt too frequent** — CPU overhead; tune `configTICK_RATE_HZ` (100Hz often sufficient)

## Production checklist

- Stack overflow checking enabled in development builds
- Static allocation for long-lived tasks
- Stack high-water mark checked after stress testing
- Priority inheritance enabled for mutexes (`configUSE_MUTEXES`)
- No blocking I/O inside mutex critical sections
- Tickless idle enabled for battery-powered devices
- Tracealyzer or runtime stats configured for scheduling debug

## Common production mistakes

Teams get rtos freertos tasks wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of rtos freertos tasks fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When rtos freertos tasks misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [FreeRTOS task documentation](https://www.freertos.org/a00125.html)
- [FreeRTOS mutexes and priority inheritance](https://www.freertos.org/Real-time-embedded-RTOS-mutexes.html)
- [FreeRTOS queue API](https://www.freertos.org/Embedded-RTOS-Queues.html)
- [vTaskDelayUntil reference](https://www.freertos.org/vtaskdelayuntil.html)
- [Percepio Tracealyzer for FreeRTOS](https://percepio.com/tracealyzer/)
