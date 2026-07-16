---
title: "Error Handling in Rust"
slug: "rust-error-handling-result-anyhow"
description: "Handle errors idiomatically in Rust: Result, custom error enums, thiserror, anyhow, and when to panic versus propagate."
datePublished: "2025-04-29"
dateModified: "2025-04-29"
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Avoid stringly-typed errors

`Err("something went wrong".into())` loses structure. Prefer enums or `anyhow` with context. If you must expose messages to users, separate `display_message` from internal `debug_chain`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Panic boundaries

Use `catch_unwind` at FFI boundaries only when required. For async Tokio tasks, panics cancel the task—configure `Tower` layers to log and return 500 without killing the runtime. Document `#![deny(clippy::unwrap_used)]` on library crates.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Error sources and tracing

```rust
error!(error = ?err, "request failed");
```

Printing `{}` alone drops cause chains. Use `{:?}` or `{:#}` for anyhow and enable `RUST_BACKTRACE=1` in staging. OpenTelemetry exporters map error types to span events.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


## Resources

- [The Rust Programming Language: Error Handling](https://doc.rust-lang.org/book/ch09-00-error-handling.html)
- [thiserror crate documentation](https://docs.rs/thiserror/latest/thiserror/)
- [anyhow crate documentation](https://docs.rs/anyhow/latest/anyhow/)
- [Error Handling project group](https://github.com/rust-lang/error-handling)
- [RFC 2056: error_context](https://rust-lang.github.io/rfcs/2056-error-context.html)
