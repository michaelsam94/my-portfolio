---
title: "Error Handling in Rust"
slug: "rust-error-handling-result-anyhow"
description: "Handle errors idiomatically in Rust: Result, custom error enums, thiserror, anyhow, and when to panic versus propagate."
datePublished: "2025-04-29"
dateModified: "2026-07-17"
tags: ["Rust", "Error Handling", "Backend", "Best Practices"]
keywords: "Rust error handling, Result type, thiserror, anyhow crate, error propagation, custom error enum, ? operator Rust"
faq:
  - q: "When should I use anyhow versus thiserror?"
    a: "Use thiserror for library crates that expose typed errors consumers match on. Use anyhow in binaries and application layers where you log context and exit or map to HTTP status codes. Mixing them is normal: libraries return thiserror types; main wraps with anyhow::Context."
  - q: "Should I use Box<dyn Error> in public APIs?"
    a: "Avoid it in library public functions—callers cannot match on specific failures. Prefer a dedicated enum or a generic error type parameter bounded by std::error::Error. Box<dyn Error> remains acceptable for quick prototypes and private modules."
  - q: "When is unwrap or expect acceptable?"
    a: "Use expect with a message only for invariants guaranteed by prior logic or static initialization—Mutex poisoning after panic, parse of literal constants. Never unwrap on user input, network I/O, or file paths. Clippy lints can ban unwrap in lib targets while allowing it in tests."
---
Production Rust that panics on the first malformed header teaches users that "memory safe" does not mean "operationally safe." The language pushes you toward explicit `Result<T, E>` flows and the `?` operator for propagation. The design choice is not whether to handle errors but how to type them: granular enums at library boundaries, ergonomic context in binaries, and a clear line where panic means programmer bug rather than expected failure.

## Result and the ? operator

```rust
fn read_config(path: &Path) -> Result<Config, ConfigError> {
    let text = std::fs::read_to_string(path)?;
    let cfg: Config = toml::from_str(&text)?;
    cfg.validate()?;
    Ok(cfg)
}
```

Each `?` converts errors via `From` impls. Implement `From<io::Error>` and `From<toml::de::Error>` on your domain error or use `#[from]` with thiserror.

## Custom error enums with thiserror

```rust
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("missing field {0}")]
    MissingField(&'static str),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Parse(#[from] toml::de::Error),
}
```

Libraries export `ConfigError` so callers distinguish "file missing" from "invalid TOML." `#[error(transparent)]` preserves source chains for logging.

## anyhow for application context

```rust
use anyhow::{Context, Result};

fn run() -> Result<()> {
    let db = connect_db()
        .context("failed connecting to DATABASE_URL")?;
    migrate(&db).context("migration step failed")?;
    Ok(())
}
```

`.context()` attaches human-readable breadcrumbs without defining new enum variants for every call site. Map `anyhow::Error` to HTTP responses at the Axum layer:

```rust
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        match self.0.downcast_ref::<DbError>() {
            Some(_) => (StatusCode::SERVICE_UNAVAILABLE, "db unavailable").into_response(),
            None => (StatusCode::INTERNAL_SERVER_ERROR, "internal error").into_response(),
        }
    }
}
```

## Avoid stringly-typed errors

`Err("something went wrong".into())` loses structure. Prefer enums or `anyhow` with context. If you must expose messages to users, separate `display_message` from internal `debug_chain`.

## Panic boundaries

Use `catch_unwind` at FFI boundaries only when required. For async Tokio tasks, panics cancel the task—configure `Tower` layers to log and return 500 without killing the runtime. Document `#![deny(clippy::unwrap_used)]` on library crates.

## Error sources and tracing

```rust
error!(error = ?err, "request failed");
```

Printing `{}` alone drops cause chains. Use `{:?}` or `{:#}` for anyhow and enable `RUST_BACKTRACE=1` in staging. OpenTelemetry exporters map error types to span events.

```rust
#[test]
fn rejects_empty_name() {
    let err = validate_user("").unwrap_err();
    assert!(matches!(err, UserError::EmptyName));
}
```

Property tests for parsers should include malformed inputs. Integration tests assert HTTP problem types, not only 4xx status codes.

Library crates should deny clippy::unwrap_used while binaries map anyhow::Error to HTTP responses at the edge. The split keeps public APIs typed and application layers ergonomic.

OpenTelemetry exporters map error types to span events. Printing Display alone drops cause chains—use Debug formatting or {:#} for anyhow in logs. RUST_BACKTRACE=1 in staging accelerates triage without exposing stacks to end users.

Property tests for parsers include malformed inputs. Integration tests assert HTTP problem types, not only 4xx status codes. Error path coverage matters as much as happy path for payment and auth flows.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## A concrete playbook for rust error handling result anyhow

Rust topics like rust error handling result anyhow reward clarity about ownership, error types, and executor behavior. Prefer designs the borrow checker accepts without `clone()` spam — structure data so lifetimes are obvious.

### API guidance

Accept `&str` / trait bounds at boundaries; return owned types when creating data. For async, keep `.await` points short and move blocking work to `spawn_blocking`. Use `thiserror` in libraries and `anyhow` in binaries.

### Tooling

`cargo clippy -D warnings`, `cargo fmt`, Miri for unsafe, and loom for lock-free concurrency when relevant to rust error handling result anyhow. Enable tokio-console while chasing latency.

### Testing

`#[tokio::test]` for async units; integration tests against ephemeral ports. Prefer property tests for parsers involved in rust error handling result anyhow.

## Validation scenarios for rust error handling result anyhow

Before calling rust error handling result anyhow done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for rust error handling result anyhow.

## Ownership and interfaces

Name the producing and consuming teams for rust error handling result anyhow. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Resources

- [The Rust Programming Language: Error Handling](https://doc.rust-lang.org/book/ch09-00-error-handling.html)
- [thiserror crate documentation](https://docs.rs/thiserror/latest/thiserror/)
- [anyhow crate documentation](https://docs.rs/anyhow/latest/anyhow/)
- [Error Handling project group](https://github.com/rust-lang/error-handling)
- [RFC 2056: error_context](https://rust-lang.github.io/rfcs/2056-error-context.html)