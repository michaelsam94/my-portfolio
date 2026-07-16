---
title: "The Actor Model, Explained"
slug: "concurrency-actor-model"
description: "Understand the actor model for concurrent systems: isolated state, message mailboxes, supervision, and when actors beat shared-memory locks."
datePublished: "2025-04-21"
dateModified: "2025-04-21"
tags: ["Career", "Engineering"]
keywords: "actor model, message passing concurrency, Akka actors, Erlang OTP, isolated state, concurrent systems"
faq:
  - q: "What is an actor in concurrent programming?"
    a: "An actor is a unit of computation with private state, a mailbox queue, and a behavior function that processes one message at a time. External code sends messages asynchronously; the actor handles them sequentially, eliminating locks on internal state. Actors communicate only via messages—no shared mutable variables between actors."
  - q: "When should I use the actor model?"
    a: "Actors fit event-driven systems with many independent entities—chat sessions, game entities, IoT device handlers, or sharded workers. They simplify reasoning about concurrency when shared-memory locks become error-prone. They are less ideal for CPU-bound parallel numeric work better served by structured fork-join or SIMD."
  - q: "How does actor supervision work?"
    a: "Supervisors are actors that spawn child actors and define restart strategies—restart on failure, escalate to parent, or stop. Erlang OTP popularized 'let it crash': isolate failure to one actor, restart with clean state, preserve system availability. Akka and Orleans provide similar hierarchy models."
---

Shared mutable state plus locks is the default concurrency model—and the default source of heisenbugs. The actor model offers a different contract: no shared state between workers, only asynchronous messages. Each actor processes its mailbox one message at a time, like a single-threaded event loop with an address. It is not magic parallelism; it is disciplined isolation that scales mentally when your system has thousands of independent sessions.

## Core principles

1. **Isolation** — actor state is private; nothing else reads or writes it directly
2. **Message passing** — communication via immutable messages sent to an address
3. **Sequential processing** — one message handler runs at a time per actor
4. **Location transparency** — senders do not care if the actor is local or remote

No locks inside the actor because no concurrent access to its state exists.

## Minimal actor pseudocode

```kotlin
// Conceptual—not a production framework API
class CounterActor : Actor {
    private var count = 0

    override fun receive(msg: Message) = when (msg) {
        is Increment -> count++
        is GetCount -> sender.reply(count)
        is Reset -> count = 0
    }
}

// Usage
actorRef.send(Increment)
val future = actorRef.ask(GetCount)  // async reply
```

`receive` runs to completion before the next message—no interleaved mutations.

## Mailboxes and backpressure

Messages queue in the mailbox. Unbounded mailboxes risk OOM under overload—production systems use bounded mailboxes with drop, block, or sender-side backpressure strategies (see separate article).

Priority mailboxes exist but complicate fairness—default FIFO is predictable.

## Erlang/OTP: the reference implementation

Erlang processes are lightweight actors (kilobytes each, millions per node):

```erlang
-module(counter).
-export([start/0, loop/1]).

start() ->
    spawn(?MODULE, loop, [0]).

loop(Count) ->
    receive
        increment -> loop(Count + 1);
        {get, From} -> From ! Count, loop(Count)
    end.
```

OTP adds supervision trees:

```erlang
init([]) ->
    {ok, {{one_for_one, 5, 10}, [
        {worker1, {worker, start_link, []}, permanent, 5000, worker, []}
    ]}}.
```

`one_for_one` restarts only the crashed child; `5 in 10` limits restart storms.

## Akka on the JVM

```scala
class Counter extends Actor {
  var count = 0
  def receive = {
    case Increment => count += 1
    case GetCount    => sender() ! count
  }
}

val counter = system.actorOf(Props[Counter](), "counter")
counter ! Increment
```

Akka Cluster shards actors across nodes by key—useful for stateful entities at scale (bank accounts, user sessions).

## Actors vs threads vs coroutines

| Model | Isolation | Overhead | Best for |
|-------|-----------|----------|----------|
| Threads + locks | Manual | OS thread cost | Shared mutable caches |
| Coroutines | Cooperative | Low | Async I/O, structured concurrency |
| Actors | Message-only | Medium | Stateful entities, fault domains |

Kotlin coroutines are not actors unless you enforce single-threaded dispatchers per entity. Pattern:

```kotlin
class EntityActor(scope: CoroutineScope) {
    private val channel = Channel<Event>(Channel.UNLIMITED)

    init {
        scope.launch(Dispatchers.Default.limitedParallelism(1)) {
            for (event in channel) handle(event)
        }
    }

    fun send(event: Event) { channel.trySend(event) }
}
```

One coroutine, one mailbox—actor discipline with coroutine syntax.

## When actors hurt

**CPU parallel pipelines.** Splitting numeric work across actors adds message overhead without gaining isolation benefits. Use parallel streams or worker pools.

**Request-response hot paths.** Synchronous ask patterns with timeouts add latency vs direct calls. Actors excel at async fire-and-forget and long-lived state.

**Distributed tracing complexity.** Message chains across actors require correlation IDs in every message for observability.

## Design guidelines

Keep messages small and immutable—send IDs, not object graphs.

One concern per actor—god actors with giant `when` blocks become unmaintainable.

Document message contracts like API schemas—version messages for evolution.

Prefer tell over ask; ask only when reply is required and handle timeout.

## Actor supervision hierarchies

Supervisors restart failed actors without crashing the system:

```
/userService          ← top-level supervisor
  ├── /sessionManager ← restarts on SessionActor failure
  │     ├── /session-abc123
  │     └── /session-def456
  └── /paymentGateway ← restarts on PaymentActor failure
```

```kotlin
// Akka-style supervision in Kotlin (conceptual)
sealed class SupervisorStrategy {
    object Restart extends SupervisorStrategy()   // restart actor, clear state
    object Resume extends SupervisorStrategy()    // continue with current state
    object Stop extends SupervisorStrategy()      // terminate permanently
    object Escalate extends SupervisorStrategy()  // propagate to parent supervisor
}
```

One actor crash shouldn't cascade. Session actor failure restarts that session — not the entire user service.

## Message mailbox backpressure

Unbounded mailboxes cause OOM when producer outpaces consumer:

```kotlin
// Bounded mailbox with backpressure
class BoundedActor<T>(capacity: Int = 1000, handler: suspend (T) -> Unit) {
    private val mailbox = Channel<T>(capacity)

    suspend fun send(msg: T) {
        mailbox.send(msg)  // suspends when full — backpressure
    }

    init {
        CoroutineScope(Dispatchers.Default).launch {
            for (msg in mailbox) handler(msg)
        }
    }
}
```

Bounded channel as mailbox — producer suspends when mailbox full. Prefer tell (fire-and-forget) over ask (request-reply) to avoid reply mailbox buildup.

## Distributed actors with Orleans

Virtual actors (grains) for cloud-native actor model:

```csharp
// Microsoft Orleans grain
public interface IUserGrain : IGrainWithStringKey {
    Task<OrderHistory> GetOrderHistory();
    Task AddOrder(Order order);
}

public class UserGrain : Grain, IUserGrain {
    private List<Order> _orders = new();

    public Task AddOrder(Order order) {
        _orders.Add(order);  // state persisted automatically
        return Task.CompletedTask;
    }
}
```

Orleans handles activation, deactivation, placement, and persistence. Actor location transparent — no manual shard routing.

## Failure modes

- **God actor** — single actor handles all concerns; becomes bottleneck and unmaintainable
- **Ask without timeout** — caller blocks indefinitely if actor crashed
- **Unbounded mailbox** — OOM when message production exceeds consumption rate
- **Mutable message payloads** — sender and receiver race on same object
- **No supervision strategy** — one actor crash terminates entire system

## Production checklist

- One concern per actor — no god actors
- Tell (fire-and-forget) preferred over ask (request-reply)
- Ask patterns include timeout (typically 5–30 seconds)
- Bounded mailbox with backpressure on high-throughput actors
- Messages immutable — send IDs, not mutable object references
- Supervision strategy defined per actor hierarchy level

## Resources

- [Akka actor model documentation](https://doc.akka.io/docs/akka/current/typed/guide/actors-intro.html)
- [Erlang OTP design principles](https://www.erlang.org/doc/design_principles/des_princ.html)
- [Hewitt, Bishop, Steiger — Actor model original paper](https://dl.acm.org/doi/10.1145/1624775.1624804)
- [Microsoft Orleans virtual actors](https://learn.microsoft.com/en-us/dotnet/orleans/overview)
