---
title: "Designing for Memory-Constrained Devices"
slug: "embedded-memory-constrained-design"
description: "Fit firmware into tight RAM and flash budgets: static allocation, pool allocators, stack sizing, PROGMEM patterns, and profiling with linker maps."
datePublished: "2025-11-25"
dateModified: "2025-11-25"
tags: ["IoT", "Embedded", "Firmware", "Optimization"]
keywords: "memory constrained embedded design, static allocation MCU, embedded stack sizing, linker map analysis, memory pool embedded, flash RAM optimization, PROGMEM"
faq:
  - q: "Should I use malloc on a microcontroller?"
    a: "Avoid heap allocation in production firmware unless you implement a fixed-size pool allocator with deterministic behavior. malloc fragments heap over long runtimes and failure modes are hard to test. Prefer static buffers, stack allocation for scoped use, and memory pools sized at compile time from peak concurrent usage."
  - q: "How do I determine task stack sizes in an RTOS?"
    a: "Start with vendor guidance, then fill stacks with a canary pattern (0xA5) and measure high-water mark under stress tests including worst-case interrupt nesting. Add 25–50% margin. Stack overflows corrupt adjacent memory and manifest as random faults far from the root cause."
  - q: "What is the fastest way to find RAM hogs in my firmware?"
    a: "Generate and read the linker map file (.map) after build. Sort .bss and .data sections by size. Look for large static arrays, unused library objects linked in, and debug strings left in release builds. GCC -fstack-usage per compilation unit helps estimate stack frames."
---

The spec sheet promised 128 KB RAM; after TLS, two RTOS tasks, and a JSON parser borrowed from the cloud codebase, you have eleven kilobytes headroom and a demo that crashes on the fourth MQTT reconnect. Memory on microcontrollers is not abundant — it is a hard ceiling where every static buffer, stack frame, and forgotten format string lives forever until you ship an OTA fix. Designing for constrained devices means choosing data structures at compile time, proving stack usage under load, and treating the heap as guilty until proven innocent.

## Know your memory map

Before optimizing, read the linker output:

```bash
arm-none-eabi-size -A -d firmware.elf
arm-none-eabi-nm --size-sort -S firmware.elf | tail -20
```

Typical regions:

| Region | Contents |
|--------|----------|
| `.text` / flash | Code and const data |
| `.data` | Initialized globals (copied to RAM at startup) |
| `.bss` | Zero-init globals |
| heap | Dynamic pool between `_end` and stack |
| stacks | Main + RTOS task stacks |

The `.map` file from GCC or IAR lists each symbol's size — sort by `Common` and `.bss` to find the elephants.

## Static allocation and memory pools

Replace unbounded heap use with fixed pools:

```c
#define MAX_PACKETS 8
#define PACKET_SIZE 256

typedef struct {
    uint8_t data[PACKET_SIZE];
    bool in_use;
} packet_slot_t;

static packet_slot_t pool[MAX_PACKETS];

uint8_t *packet_acquire(void) {
    for (int i = 0; i < MAX_PACKETS; i++) {
        if (!pool[i].in_use) {
            pool[i].in_use = true;
            return pool[i].data;
        }
    }
    return NULL;  // explicit backpressure — count these in metrics
}

void packet_release(uint8_t *p) {
    for (int i = 0; i < MAX_PACKETS; i++) {
        if (pool[i].data == p) {
            pool[i].in_use = false;
            return;
        }
    }
}
```

Peak usage is `MAX_PACKETS * PACKET_SIZE` — provable at compile time. When the pool is full, drop, block, or NACK — but never fragment.

## Stack sizing with canaries

FreeRTOS provides `uxTaskGetStackHighWaterMark`. Fill stacks at creation:

```c
#define STACK_CANARY 0xA5

void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcName) {
    // log pcName, halt or safe mode
}
```

Run worst-case scenarios: max protocol nesting, heaviest ISR chain, deepest call tree from JSON parse or crypto. If high-water is 780 bytes on a 1024-byte stack, you are too tight.

Main stack (`MSP`) on bare-metal needs the same discipline — linker script `__stack_size` is not a suggestion.

## Flash vs RAM trade-offs

Move immutable data to flash:

```c
static const char device_name[] = "sensor-node-v2";  // lives in .rodata

// AVR-style (concept applies: const in flash)
static const uint16_t lookup_table[512] PROGMEM = { /* ... */ };
```

Compute-vs-store: precompute CRC tables, font glyphs, and calibration curves at build time rather than runtime initialization that consumes `.data`.

Strip unused code:

```cmake
target_compile_options(firmware PRIVATE -ffunction-sections -fdata-sections)
target_link_options(firmware PRIVATE -Wl,--gc-sections)
```

Link only required printf float support — nano.specs vs full newlib makes measurable flash differences.

## Avoid accidental RAM multipliers

- **Large stack buffers** — `char buf[4096]` on the stack in a 2 KB stack task overflows immediately. Use static or pool.
- **Unicode and locale** — full printf with floats pulls kilobytes.
- **Debug strings in release** — gate with `#ifdef DEBUG` or move to structured logging levels compiled out.
- **Third-party JSON/XML** — DOM parsers allocate proportional to document size; use streaming SAX-style parsers on MCUs.

## Measurement in CI

Add a build step that fails if RAM usage exceeds threshold:

```bash
#!/bin/bash
USED=$(arm-none-eabi-size firmware.elf | awk '/^\.data/ {d=$2} /^\.bss/ {b=$2} END {print d+b}')
MAX=98304  # 96 KB budget
if [ "$USED" -gt "$MAX" ]; then
  echo "RAM $USED exceeds budget $MAX"
  exit 1
fi
```

Track trends per commit — regressions become visible before hardware test.

## Memory pool sizing worked example

Suppose an STM32F4 with 192 KB SRAM, FreeRTOS, three tasks:

| Task | Stack | Heap / pools | Notes |
|------|-------|--------------|-------|
| Network (lwIP) | 4 KB | 32 KB PBUF pool | Fixed at compile time |
| Sensor fusion | 2 KB | 8 KB static buffers | No malloc |
| UI / display | 3 KB | 16 KB frame buffer | Double-buffer optional |
| Idle + kernel | — | ~8 KB | Timer + queue overhead |

Total budget: ~73 KB application, remainder for `.bss`/`.data` and headroom. If `configTOTAL_HEAP_SIZE` is 48 KB but lwIP alone needs 32 KB, you have 16 KB for everything else — math fails before field test.

Size pools from **peak concurrent allocation**, not average. BLE connection burst + TLS handshake overlapping is the worst case, not steady-state telemetry.

## MPU and fault containment

On Cortex-M3/M4/M33, enable the Memory Protection Unit to catch overflows before silent corruption:

```c
// Example: mark task stack region no-access below stack base
void vConfigureMPU(void) {
    // Stack guard region: 32 bytes below stack limit, no access
    // Catches stack overflow as MemManage fault instead of random hard fault
}
```

Log fault status registers (`CFSR`, `HFSR`, `MMFAR`) over UART before reset. In production, persist fault context to flash sector for post-mortem — guessing which task overflowed from a watchdog reset alone wastes days.

## When to upgrade hardware vs optimize

Optimize first when:

- BOM increase exceeds $2 per unit at volume
- Flash headroom exists but RAM is tight (move tables to flash)
- Algorithm change reduces RAM 40% (streaming parser vs DOM)

Upgrade MCU when:

- Stack high-water consistently above 85% after optimization
- Feature roadmap needs TLS + OTA + display simultaneously
- Engineering time spent on memory hacks exceeds NRE of next-tier chip

Document the decision in an ADR — "we chose external PSRAM" vs "we rewrote JSON parser" tells the next firmware engineer why the schematic looks that way.

## Production checklist

- [ ] RAM budget enforced in CI with `arm-none-eabi-size`
- [ ] FreeRTOS stack high-water checked on worst-case paths
- [ ] Memory pools sized for peak concurrent allocation
- [ ] MPU enabled where Cortex-M3+ available
- [ ] `.map` file reviewed on every release candidate

## Resources

- [GNU linker map file documentation](https://sourceware.org/binutils/docs/ld/OUTPUT_002fINPUT_002fSEARCH-Linker-Scripts.html)
- [FreeRTOS stack overflow checking](https://www.freertos.org/Stacks-and-stack-overflow-checking.html)
- [Embedded Artistry memory pool pattern](https://embeddedartistry.com/blog/2017/05/17/creating-a-memory-pool/)
- [ARM Cortex-M memory protection (MPU)](https://developer.arm.com/documentation/dui0552/a/the-cortex-m3-processor/memory-protection-unit)
- [newlib nano specs (GCC ARM)](https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html)
