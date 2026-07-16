---
title: "Lock-Free Data Structures"
slug: "concurrency-lock-free-data-structures"
description: "How lock-free queues and atomic operations work: compare-and-swap, memory ordering, ABA problem, and when lock-free beats mutexes."
datePublished: "2025-04-27"
dateModified: "2025-04-27"
tags: ["Career", "Engineering"]
keywords: "lock-free data structures, compare and swap, atomic operations, concurrent queue, memory ordering, ABA problem"
faq:
  - q: "What does lock-free mean?"
    a: "A lock-free algorithm guarantees system-wide progress: at least one thread completes an operation in a finite number of steps, even if others are suspended. Wait-free is stronger—every thread completes in bounded steps. Lock-free structures use atomic compare-and-swap (CAS) instead of mutexes, avoiding deadlock and reducing priority inversion in latency-sensitive paths."
  - q: "When should I use lock-free structures?"
    a: "Use them in high-contention hot paths where mutex profiling shows lock overhead—job queues, reference counting, metrics counters, SPSC/MPSC queues between threads. For most application code, std::mutex or synchronized blocks are simpler and fast enough. Lock-free code is harder to verify and debug."
  - q: "What is the ABA problem?"
    a: "CAS succeeds when memory equals expected value A, but A was removed and re-added—state changed yet pointer looks identical. Solutions include tagged pointers (version stamps), hazard pointers, epoch-based reclamation, or garbage-collected languages where objects aren't reused immediately. Ignoring ABA corrupts lock-free stacks and freelists."
---

Mutex contention shows up as flat CPU profiles where threads spend thirty percent waiting on a lock guarding a work queue. Lock-free structures trade mutex waits for retry loops on atomic compare-and-swap—sometimes faster, always trickier. They appear in JVM `ConcurrentLinkedQueue`, C++ `std::atomic`, Rust crossbeam queues, and every high-frequency trading stack. Understanding CAS and its footguns separates informed use from copy-paste hazard.

## Compare-and-swap (CAS)

Atomic operation: if location == expected, set to new; return success/failure.

```java
// Java VarHandle / AtomicReference pattern
boolean cas(AtomicReference<Node> ref, Node expected, Node update) {
    return ref.compareAndSet(expected, update);
}
```

Failed CAS means another thread won—retry the logic.

Lock-free increment:

```java
AtomicInteger counter = new AtomicInteger();
counter.incrementAndGet();  // CAS loop inside
```

## Lock-free stack (conceptual)

```cpp
void push(Node* node) {
    Node* head = head_.load(std::memory_order_relaxed);
    do {
        node->next = head;
    } while (!head_.compare_exchange_weak(head, node,
              std::memory_order_release,
              std::memory_order_relaxed));
}
```

Pop symmetrically. Multiple concurrent push/pop retry until CAS succeeds.

## Memory ordering matters

Weak memory models (ARM, not just x86) reorder loads/stores. Use:

- `memory_order_acquire` on read side
- `memory_order_release` on write side
- `memory_order_seq_cst` when unsure (slower, simpler)

Incorrect ordering causes "it works on x86" bugs that explode on ARM servers and Apple Silicon.

## ABA problem illustrated

Thread 1 reads head A. Thread 2 pops A, pops B, pushes A back. Thread 1 CAS(head, A, newNode) succeeds—stack changed (B gone) but CAS thinks nothing happened.

Fix: tagged pointers pack version counter with address:

```cpp
struct TaggedPtr {
    Node* ptr;
    uint64_t tag;
};
```

Increment tag on every pop. CAS compares tag + ptr.

## Epoch-based reclamation

Lock-free pop cannot `delete` immediately—other threads may still read the node. Epoch reclamation:

1. Reader enters epoch
2. Pop moves node to retired list
3. When all threads pass epoch, free retired nodes

Used in Folly, userspace RCU variants.

## SPSC vs MPSC queues

**Single-producer single-consumer (SPSC)** — simplest, often wait-free, ring buffer with atomic head/tail:

```rust
// crossbeam::queue::ArrayQueue
let q = ArrayQueue::new(1024);
q.push(item)?;  // producer
q.pop();        // consumer
```

**Multi-producer** needs CAS on tail—more retries, more complex.

Pick the narrowest queue type matching your threading model.

## Lock-free vs lock-based

| Factor | Mutex | Lock-free |
|--------|-------|-----------|
| Contention low | Fast | CAS overhead wasted |
| Contention high | Serializes threads | Retries but progresses |
| Complexity | Low | High |
| Priority inversion | Possible | Avoided |
| Debugging | Stack traces | Heisenbugs |

Profile first. `synchronized` on uncontended Java methods is often optimized to biased locking—free performance.

## JVM practical choices

- `ConcurrentLinkedQueue` — lock-free MPMC linked queue
- `LongAdder` — striped counters vs `AtomicLong` under write contention
- `java.util.concurrent` before rolling your own

```java
LongAdder requests = new LongAdder();
requests.increment();
long total = requests.sum();
```

## Testing lock-free code

Stress tests with many threads, `-DCMAKE_BUILD_TYPE=RelWithDebInfo`, ThreadSanitizer, and literal hours of fuzzing. Model check with CDSChecker or similar for academic confidence.

Never ship custom lock-free code without domain expert review.

## Practical lock-free patterns in application code

Most application developers encounter lock-free code through libraries, not custom implementations:

**Reference counting (Rust Arc, C++ shared_ptr internals):**
Atomic increment/decrement with CAS. When count reaches zero, deallocate. Lock-free but ABA-safe due to GC or versioned pointers.

**Work-stealing deque (ForkJoinPool, Tokio):**
Each thread has a local deque. Push/pop locally without contention. Steal from other threads' deques when idle. Used in parallel stream processing and async runtimes.

**Ring buffer (Disruptor, LMAX):**
Pre-allocated array with sequence numbers. Producers and consumers track separate cursors. Wait-free for SPSC case. Powers high-frequency trading systems handling millions of events/sec.

**Metrics counters (LongAdder, HdrHistogram):**
Striped atomic counters reduce contention vs single AtomicLong. Each thread writes to its own cell; sum on read.

```java
// Prefer LongAdder over AtomicLong for write-heavy counters
LongAdder requestCount = new LongAdder();
LongAdder errorCount = new LongAdder();

// In request handler
requestCount.increment();
if (failed) errorCount.increment();

// In metrics export
registry.gauge("requests.total", requestCount::sum);
```

## When NOT to use lock-free

- **Low contention** — mutex is faster when threads rarely compete
- **Complex invariants** — lock-free structures protect single variables well; multi-variable invariants need locks
- **Team lacks expertise** — custom lock-free code is a maintenance liability
- **Debugging priority** — lock-free Heisenbugs take weeks to reproduce
- **GC languages with short object lifetimes** — ABA less problematic but still possible with object pools

Default to mutex. Profile. Switch to lock-free library (ConcurrentHashMap, LongAdder, crossbeam) before writing custom CAS loops.

## Failure modes

- **ABA without version tags** — stack/list corruption on pop/push
- **Wrong memory ordering** — works on x86, fails on ARM
- **Premature memory deallocation** — use-after-free in lock-free pop
- **CAS retry storms** — high contention makes lock-free slower than mutex
- **Custom lock-free without formal verification** — subtle bugs in production

## Production checklist

- Profile before switching from mutex to lock-free
- Use library implementations (JUC, crossbeam, Folly) over custom code
- Memory ordering explicitly specified (not default seq_cst everywhere)
- ABA mitigation in place for pointer-based structures
- ThreadSanitizer and stress tests for custom lock-free code
- Domain expert review for any custom lock-free implementation

## Common production mistakes

Teams get lock free data structures wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of lock free data structures fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Herlihy & Shavit — The Art of Multiprocessor Programming](https://www.elsevier.com/books/the-art-of-multiprocessor-programming/herlihy/978-0-12-415950-1)
- [Java VarHandle documentation](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/invoke/VarHandle.html)
- [C++ atomic memory orders](https://en.cppreference.com/w/cpp/atomic/memory_order)
- [Crossbeam lock-free queues](https://docs.rs/crossbeam/latest/crossbeam/queue/index.html)
