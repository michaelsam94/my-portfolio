---
title: "Interrupt Handling on Microcontrollers"
slug: "embedded-interrupt-handling"
description: "Design reliable ISR routines on ARM Cortex-M: NVIC priorities, deferred processing, volatile semantics, race conditions, and debugging spurious interrupts."
datePublished: "2025-11-22"
dateModified: "2025-11-22"
tags: ["IoT", "Embedded", "Firmware", "ARM"]
keywords: "microcontroller interrupt handling, ISR best practices, NVIC priority, Cortex-M interrupt, deferred interrupt processing, volatile embedded C, embedded race conditions"
faq:
  - q: "How long should an interrupt service routine be?"
    a: "Keep ISRs as short as possible — typically clear the interrupt flag, capture hardware state or timestamp, and signal a task via semaphore or flag. Heavy processing belongs in main loop or RTOS task context where interrupts can be re-enabled and stack usage is predictable. Long ISRs increase latency for all lower-priority interrupts."
  - q: "What NVIC priority scheme should I use on Cortex-M?"
    a: "Assign highest priority (lowest numeric value) to safety-critical, latency-bound ISRs like motor fault or communication timeout. Medium priority for periodic sampling. Lowest for soft events. Never call blocking RTOS APIs from ISRs unless using FromISR variants. Document the priority map — conflicts cause subtle starvation."
  - q: "Why do I need volatile for variables shared between ISR and main code?"
    a: "The compiler optimizes main-loop code assuming no concurrent modification. Without volatile, it may cache a flag in a register and miss ISR updates. Use volatile for simple flags and counters; for multi-byte structures use atomic operations or disable interrupts briefly in main code during reads."
---

The UART RX interrupt fired, set `packet_ready = 1`, and the main loop never noticed because the compiler kept the flag in a register across a tight polling loop. That bug took two days and a logic analyzer to find — and it is entirely preventable if you treat interrupt handling as a concurrency problem, not a hardware checkbox. On ARM Cortex-M and similar MCUs, interrupts preempt your main code unpredictably. ISRs that run too long, touch shared state without rules, or fight over NVIC priorities will corrupt data or miss deadlines long before your application logic gets blamed.

## NVIC and priority groups

Cortex-M uses the Nested Vectored Interrupt Controller. Each IRQ has a priority (lower number = higher urgency on most vendors). Configure in startup or HAL:

```c
// STM32 HAL example — set TIM2 lower priority number than UART
HAL_NVIC_SetPriority(TIM2_IRQn, 2, 0);
HAL_NVIC_EnableIRQ(TIM2_IRQn);

HAL_NVIC_SetPriority(USART1_IRQn, 3, 0);
HAL_NVIC_EnableIRQ(USART1_IRQn);
```

Priority grouping (preemption vs subpriority) varies by vendor reference manual — read it once and draw a table:

| IRQ | Preemption | Purpose |
|-----|------------|---------|
| EXTI fault | 0 | Emergency stop |
| ADC DMA complete | 1 | Control loop sample |
| USART1 | 2 | Command channel |
| SysTick | 3 | RTOS tick |

Never enable interrupts before priorities are configured. Default priorities after reset are often identical — tie-breaking by IRQ number is not a design.

## ISR structure: minimal and deterministic

```c
volatile uint8_t rx_byte;
volatile bool rx_pending = false;

void USART1_IRQHandler(void) {
    if (USART1->SR & USART_SR_RXNE) {
        rx_byte = (uint8_t)(USART1->DR & 0xFF);
        rx_pending = true;
        // Clear flags per reference manual — some status bits clear on read
    }
}
```

Do not `printf` in an ISR. Do not malloc. Do not wait on mutexes with indefinite timeout.

For multi-byte buffers, use a ring buffer written in ISR and read in main:

```c
typedef struct {
    uint8_t buf[256];
    volatile uint16_t head;
    volatile uint16_t tail;
} ring_t;

bool ring_push(ring_t *r, uint8_t b) {
    uint16_t next = (r->head + 1) % sizeof(r->buf);
    if (next == r->tail) return false;  // full — drop or count overflow
    r->buf[r->head] = b;
    r->head = next;
    return true;
}
```

On Cortex-M3+, aligned 16-bit reads of `head` and `tail` are often safe one-way (ISR produces, main consumes) if each index is updated by only one context. For both-direction sharing, use `__atomic` or critical sections.

## Deferred processing with RTOS

With FreeRTOS, defer work to a task:

```c
BaseType_t woken = pdFALSE;

void TIM2_IRQHandler(void) {
    if (__HAL_TIM_GET_FLAG(&htim2, TIM_FLAG_UPDATE)) {
        __HAL_TIM_CLEAR_FLAG(&htim2, TIM_FLAG_UPDATE);
        vTaskNotifyGiveFromISR(sensorTaskHandle, &woken);
        portYIELD_FROM_ISR(woken);
    }
}
```

The task waits on `ulTaskNotifyTake`, processes the sample batch with interrupts enabled, and can block on queues safely.

## Critical sections in main code

When main reads a multi-field snapshot that ISRs update:

```c
uint32_t enter_critical(void) {
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    return primask;
}

void exit_critical(uint32_t primask) {
    if (!primask) __enable_irq();
}

void read_snapshot(Snapshot *out) {
    uint32_t m = enter_critical();
    *out = shared;  // copy struct atomically w.r.t. ISRs
    exit_critical(m);
}
```

Alternatively raise BASEPRI to mask interrupts below a threshold — useful in RTOS when you must not block the SysTick.

## Debugging spurious and missed interrupts

- **Pending bits** — inspect `NVIC->ISPR` and peripheral status registers when stuck.
- **Clear sequence** — many UART/SPI flags require specific read order; half-cleared flags re-enter immediately.
- **Floating pins on EXTI** — enable pull-ups; unconnected EXTI lines storm interrupts.
- **Stack overflow in ISR** — ISRs use separate MSP on some configs; deep call chains in handlers corrupt memory silently.

Use GPIO toggle pins around ISR entry/exit for scope measurement. If ISR duration exceeds your control loop period, redesign deferral.

## Priority inversion on Cortex-M

NVIC priority groups matter when ISRs interact with RTOS:

```c
// Lower number = higher priority (ARM convention)
NVIC_SetPriority(UART_IRQn, 5);      // data acquisition — high
NVIC_SetPriority(SysTick_IRQn, 15);  // RTOS tick — lower
configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY = 5;  // FreeRTOS config
```

ISRs above `configMAX_SYSCALL_INTERRUPT_PRIORITY` cannot call FreeRTOS API — calling `xQueueSendFromISR` from a too-high-priority ISR corrupts the kernel. Chart ISR priorities on paper before wiring drivers.

## Zero-latency vs deferred tradeoff

| Pattern | Latency | Complexity | Use when |
|---------|---------|------------|----------|
| Full handling in ISR | Microseconds | Low | Single register flip |
| Flag + main loop | Milliseconds | Low | Non-critical sampling |
| RTOS deferred task | Milliseconds | Medium | Buffer processing, I/O |
| DMA + half-complete callback | Minimal CPU | High | Streaming ADC, UART |

Motor control and fast safety interlocks belong in ISR or hardware (comparator + timer break). Logging, JSON parsing, and network TX belong in deferred context — no exceptions.

## Testing interrupt behavior

- **Fault injection** — flood UART with data faster than handler processes
- **Scope timing** — measure ISR duration under worst-case nesting
- **Stack analysis** — `-fstack-usage` flag in GCC for ISR stack depth estimate
- **Long-run soak** — missed interrupt bugs appear after hours, not seconds

Pair with [embedded memory constrained design](https://blog.michaelsam94.com/embedded-memory-constrained-design/) when ISR stacks compete with heap budgets.

## Production checklist

- [ ] ISR priorities documented on schematic review checklist
- [ ] No FreeRTOS API calls from above max syscall priority
- [ ] ISR duration measured under worst-case nesting
- [ ] Deferred processing for anything > 50 µs handler work
- [ ] Fault status registers logged before watchdog reset

## Common production mistakes

Teams get interrupt handling wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of interrupt handling fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [ARM Cortex-M NVIC documentation](https://developer.arm.com/documentation/dui0497/a/the-cortex-m3-processor/nested-vectored-interrupt-controller)
- [STM32 Cortex-M interrupt priorities (application note)](https://www.st.com/resource/en/application_note/dm00051211.pdf)
- [FreeRTOS interrupt management](https://www.freertos.org/a00126.html)
- [Embedded C coding standard — ISR rules (Barr Group)](https://barrgroup.com/embedded-systems/books/embedded-c-coding-standard)
- [Joseph Yiu — The Definitive Guide to ARM Cortex-M3 and Cortex-M4 Processors](https://www.elsevier.com/books/the-definitive-guide-to-arm-cortex-m3-and-cortex-m4-processors/yiu/978-0-12-803777-0)
