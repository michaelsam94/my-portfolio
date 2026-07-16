---
title: "Embedded Rust with no_std"
slug: "embedded-rust-no-std"
description: "Write bare-metal Rust firmware with no_std: panic handlers, embedded-hal traits, cortex-m-rt startup, memory layout, and interop with C drivers."
datePublished: "2025-12-01"
dateModified: "2025-12-01"
tags: ["IoT", "Embedded", "Rust", "Firmware"]
keywords: "embedded Rust no_std, cortex-m-rt, embedded-hal, bare metal Rust, #![no_std] panic handler, STM32 Rust, embedded Rust allocator"
faq:
  - q: "What does #![no_std] mean in embedded Rust?"
    a: "It disables Rust's standard library (std), which depends on OS facilities like filesystem and networking. Embedded firmware uses core and alloc optionally, plus crates like embedded-hal for hardware abstractions. You provide panic handler, memory layout via linker script, and startup code — often via cortex-m-rt for ARM."
  - q: "Can I use the heap in no_std Rust?"
    a: "Only if you link an allocator crate (embedded-alloc) and define a global allocator backed by a static pool or linked heap region. Many safety-critical projects forbid heap entirely. StaticVec, heapless collections, and fixed buffers are common."
  - q: "How do I call existing C HAL libraries from Rust?"
    a: "Use bindgen to generate Rust FFI bindings from C headers, link the C static library in build.rs, and wrap raw pointers in safe abstractions that enforce invariants. Keep unsafe blocks small and documented. Many chip crates (stm32xx-hal) reimplement drivers in idiomatic Rust instead."
---

Rust on embedded targets is not "install Rust and `println!` debug prints." There is no OS, no default allocator, and no standard library unless you opt in to `std` on platforms that support it (some RTOS or Linux targets). `#![no_std]` firmware runs on the metal: you own reset vectors, panic behavior, and every byte of `.bss`. The payoff is memory safety without garbage collection, zero-cost abstractions over registers, and type-state APIs that make "forget to enable clock gate" a compile error instead of a silent peripheral.

## Project skeleton

```toml
# Cargo.toml
[package]
name = "sensor-node"
version = "0.1.0"
edition = "2021"

[dependencies]
cortex-m = "0.7"
cortex-m-rt = "0.7"
panic-halt = "0.2"
stm32f4xx-hal = { version = "0.21", features = ["stm32f407"] }
embedded-hal = "1.0"
nb = "1.1"

[profile.release]
codegen-units = 1
lto = true
debug = true  # keep symbols for probe-rs
```

```rust
// src/main.rs
#![no_std]
#![no_main]

use cortex_m_rt::entry;
use panic_halt as _;
use stm32f4xx_hal::{pac, prelude::*};

#[entry]
fn main() -> ! {
    let dp = pac::Peripherals::take().unwrap();
    let rcc = dp.RCC.constrain();
    let mut clocks = rcc.cfgr.use_hse(8.MHz()).sysclk(168.MHz()).freeze();

    let gpioc = dp.GPIOC.split();
    let mut led = gpioc.pc13.into_push_pull_output();

    loop {
        led.set_high();
        cortex_m::asm::delay(clocks.sysclk().raw() / 8);
        led.set_low();
        cortex_m::asm::delay(clocks.sysclk().raw() / 8);
    }
}
```

`#[entry]` replaces `main`; returning is forbidden (`-> !`). `panic-halt` stops on panic — swap for `panic-probe` during development for RTT logging.

## embedded-hal and portability

Traits in `embedded-hal` define GPIO, SPI, I2C, delay:

```rust
use embedded_hal::digital::OutputPin;

fn blink<P: OutputPin>(pin: &mut P) -> Result<(), P::Error> {
    pin.set_high()?;
    pin.set_low()?;
    Ok(())
}
```

Driver crates accept generic pins and buses — test on host with `embedded-hal-mock` or swap MCU families without rewriting application logic.

## Memory layout and linker scripts

`cortex-m-rt` includes `memory.x` you customize:

```text
MEMORY
{
  FLASH : ORIGIN = 0x08000000, LENGTH = 512K
  RAM   : ORIGIN = 0x20000000, LENGTH = 128K
}
```

Place vector table, `.text`, `.data` load/copy regions correctly. `build.rs` can `println!("cargo:rustc-link-arg=-Tlink.x")` for custom layouts.

Stack pointer initialized in vector table first word — must point to valid RAM top.

## Concurrency without OS

Bare-metal Rust uses interrupt handlers as `#[interrupt]` functions:

```rust
#[interrupt]
fn TIM2() {
    // clear flag, update static with critical_section
    critical_section::with(|cs| {
        COUNTER.borrow(cs).replace_with(|c| Some(c.wrapping_add(1)));
    });
}
```

With RTOS (` embassy`, `rtic`, FreeRTOS bindings), async executors or lock-free structures replace superloop state machines. RTIC framework statically allocates resources at compile time — excellent for proving absence of priority inversion at compile time.

## Optional heap and collections

```rust
use embedded_alloc::Heap;

#[global_allocator]
static HEAP: Heap = Heap::empty();

// in main before use:
const HEAP_SIZE: usize = 8192;
static mut HEAP_MEM: [u8; HEAP_SIZE] = [0; HEAP_SIZE];
unsafe { HEAP.init(HEAP_MEM.as_ptr() as usize, HEAP_SIZE) }
```

Prefer `heapless::Vec` and `heapless::String` with fixed capacity when possible.

## Flash and debug workflow

```bash
cargo embed --release   # probe-rs flash + RTT
cargo size --release -- -A
```

Clippy with `#![deny(warnings)]` in CI catches unused `unsafe`. Compare `.map` equivalent via `cargo-size` against C baseline — Rust monomorphization can inflate flash if you genericize over dozens of pin types; type-erased HAL or dynamic dispatch trades runtime for size.

## Interrupt handling patterns

Bare-metal Rust uses `cortex-m-rt` for vector table and interrupt handlers:

```rust
use cortex_m::interrupt;

#[interrupt]
fn TIM2() {
    // Clear interrupt flag first
    pac::TIM2.sr.modify(|_, w| w.uif().clear_bit());
    // Handle timer tick — keep ISR short
    TICK_COUNT.fetch_add(1, Ordering::Relaxed);
}
```

Rules for ISRs in no_std:
- No heap allocation in interrupt context
- No blocking operations (mutex lock, I/O wait)
- Use `AtomicU32` or lock-free queues to defer work to main loop
- Clear interrupt flag before processing to avoid re-entry

For complex ISR logic, set a flag and process in main loop or RTIC task.

## Error handling without std

`no_std` has no `std::error::Error` trait ecosystem — use typed errors:

```rust
#[derive(Debug)]
enum SensorError {
    I2cTimeout,
    InvalidReading,
    CalibrationFailed,
}

type Result<T> = core::result::Result<T, SensorError>;

fn read_temperature() -> Result<f32> {
    let raw = i2c_read(REG_TEMP).map_err(|_| SensorError::I2cTimeout)?;
    if raw == 0xFFFF { return Err(SensorError::InvalidReading); }
    Ok(convert(raw))
}
```

Use `thiserror` with `default-features = false` for derive macros, or manual `Debug` impls. Panic on unrecoverable errors via `panic-halt` or custom panic handler that triggers watchdog reset.

## Testing embedded Rust

Unit tests run on host with mocked HAL:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    // Mock I2C for host-side testing
    struct MockI2c { data: Vec<u8> }
    impl embedded_hal::i2c::I2c for MockI2c { ... }

    #[test]
    fn read_temperature_valid() {
        let mut mock = MockI2c { data: vec![0x19, 0x00] };
        assert_eq!(read_temp(&mut mock).unwrap(), 25.0);
    }
}
```

Integration tests require hardware — use `probe-rs` for on-target testing in CI with hardware-in-the-loop runners.

## Failure modes

- **Heap allocation in ISR** — undefined behavior or hard fault
- **Blocking mutex in interrupt** — deadlock if main loop holds lock
- **Monomorphization bloat** — generic over every pin type inflates flash 2-3×
- **Missing panic handler** — linker error or silent hang on panic
- **Unsafe without documentation** — next maintainer breaks invariants

## Production checklist

- `#![no_std]` with explicit panic handler (watchdog reset)
- ISRs defer work via atomics or lock-free queues
- `heapless` collections preferred over heap allocator
- `cargo clippy` with `#![deny(warnings)]` in CI
- `cargo size --release` tracked against flash budget
- Host-side unit tests with mocked HAL traits

## Common production mistakes

Teams get rust no std wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of rust no std fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [The Embedded Rust Book](https://docs.rust-embedded.org/book/)
- [embedded-hal trait documentation](https://docs.rs/embedded-hal/latest/embedded_hal/)
- [cortex-m-rt crate](https://docs.rs/cortex-m-rt/latest/cortex_m_rt/)
- [probe-rs — flash and debug](https://probe.rs/)
- [RTIC real-time framework](https://rtic.rs/)
