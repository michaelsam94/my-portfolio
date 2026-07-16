---
title: "Ownership and Borrowing, Explained"
slug: "rust-ownership-borrowing-explained"
description: "Understand Rust ownership, moves, borrows, and lifetimes with practical patterns for strings, collections, and API design."
datePublished: "2025-05-03"
dateModified: "2025-05-03"
tags: ["Rust", "Ownership", "Memory Safety", "Programming"]
keywords: "Rust ownership, borrowing rules, lifetimes, move semantics, references Rust, borrow checker, String vs str"
faq:
  - q: "Why does Rust have ownership instead of a garbage collector?"
    a: "Ownership determines at compile time who frees memory and when, eliminating GC pauses and whole classes of use-after-free bugs. Each value has exactly one owner; when the owner goes out of scope, drop runs automatically. References let you read or mutate without transferring ownership, with rules enforced statically."
  - q: "When should I use &str instead of String in function parameters?"
    a: "Accept impl AsRef<str> or &str when the function only needs to read text and should accept both literals and owned strings. Return String when creating new text. Use String parameters only when you need to store or mutate into owned buffers and want callers to explicitly transfer ownership."
  - q: "How do I share data between threads?"
    a: "Prefer message passing with channels or Arc<Mutex<T>> for shared mutable state. Clone Arc to increment reference count, not the inner data. Read-only sharing uses Arc alone; interior mutability needs Mutex, RwLock, or atomics depending on contention and access pattern."
---

The borrow checker rejected your function for the fourth time and you reached for `clone()` everywhere. Ownership is not a ceremony—it is a contract about who destroys data and how long references stay valid. Once moves, borrows, and lifetimes click, APIs get clearer: you stop fighting duplicated string copies and start designing functions that say precisely whether they consume, read, or mutate inputs.


## The three rules

1. Each value has exactly one owner at a time.
2. When the owner goes out of scope, the value is dropped.
3. At any moment, either one mutable reference *or* any number of immutable references—never both.

Violations are compile errors, not runtime segfaults.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Move versus copy

```rust
let a = String::from("hello");
let b = a;           // move: a is invalid now
// println!("{a}");  // compile error

let x = 42;
let y = x;           // copy: i32 implements Copy
println!("{x}");     // fine
```

Types with heap allocation (`String`, `Vec`, `HashMap`) move by default. Stack-only types implementing `Copy` duplicate bits cheaply.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Borrowing in practice

```rust
fn greet(name: &str) -> String {
    format!("Hello, {name}")
}

let owned = String::from("Ada");
greet(&owned);       // borrow immutably
// owned still valid
```

Mutable borrow for in-place updates:

```rust
fn push_exclaim(s: &mut String) {
    s.push('!');
}
```

Only one `&mut` at a time prevents data races at compile time.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Structs and ownership

```rust
struct User {
    email: String,
}

impl User {
    fn email_domain(&self) -> &str {
        self.email.split('@').nth(1).unwrap_or("")
    }
}
```

Returning `&str` tied to `self.email` works—the lifetime elision rules connect them. Returning a slice into local data requires owning the buffer in the return type (`String`).

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Lifetimes when the compiler asks

Explicit annotations appear when multiple references interact:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```

`'a` means "returned reference lives no longer than both inputs." Most application code rarely writes lifetimes thanks to elision on `&self` methods.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Smart pointers

- `Box<T>`: heap single ownership, useful for recursive types.
- `Rc<T>` / `Arc<T>`: shared ownership (Arc for threads).
- `RefCell<T>` / `Mutex<T>`: interior mutability with runtime or lock checks.

Combine `Arc<Mutex<Cache>>` for concurrent maps; do not nest unnecessary layers.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


| Caller has | Function needs read | Function needs own | Function mutates |
|------------|--------------------|--------------------|------------------|
| `String` | `&str` param | `String` param (move) | `&mut String` |
| `&String` | `&str` | clone or accept `String` | `&mut String` |
| literal | `&str` | `String` return | N/A |

Prefer borrowing at boundaries; clone deliberately where ownership transfer is the semantics you want.

ArchUnit or module tests can enforce that domain packages never import infrastructure—ownership discipline extends to crate boundaries. Public functions accepting &str instead of String reduce unnecessary clones at API edges.

Arc<Mutex<T>> is not free—measure contention before wrapping everything. Message passing with channels often simplifies reasoning when shared mutable state is not truly required.

Reading the borrow checker errors literally saves time: the compiler points at the conflicting borrow. Fight the design (split borrows, restructure loops) before reaching for Rc everywhere—reference cycles and hidden clones accumulate silently.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Resources

- [The Rust Book: Ownership](https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html)
- [Rust by Example: Ownership](https://doc.rust-lang.org/rust-by-example/scope.html)
- [Standard library: std::borrow::Borrow](https://doc.rust-lang.org/std/borrow/trait.Borrow.html)
- [Nomicon: Ownership and lifetimes](https://doc.rust-lang.org/nomicon/ownership.html)
- [Rust RFC: Non-lexical lifetimes](https://rust-lang.github.io/rfcs/2094-nll.html)
