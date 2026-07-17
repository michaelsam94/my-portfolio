---
title: "Vertical Slice Architecture"
slug: "software-vertical-slice-architecture"
description: "Organize code by feature slices instead of technical layers. Vertical slice architecture keeps related handlers, validation, and persistence together so changes stay local and teams ship faster."
datePublished: "2025-09-01"
dateModified: "2026-07-17"
tags: ["Architecture", "Software Design", "Clean Code", "Backend"]
keywords: "vertical slice architecture, feature folders, CQRS handlers, MediatR, slice-based organization, avoid anemic domain, colocate feature code"
faq:
  - q: "How is vertical slice architecture different from layered architecture?"
    a: "Layered architecture groups code by technical role — all controllers in one folder, all repositories in another. Vertical slice architecture groups code by feature: everything for CreateOrder lives together. When you change order creation, you touch one slice instead of hunting across four layers. Layers optimize for separation of concerns; slices optimize for change locality."
  - q: "Does vertical slice architecture replace domain-driven design?"
    a: "No — they complement each other. DDD gives you bounded contexts and domain models; vertical slices give you a folder structure that respects those boundaries. A slice inside the Orders context contains its handler, validator, and mapping logic. You still model aggregates and domain events; you just stop scattering them across generic Infrastructure and Application folders."
  - q: "When should I avoid vertical slices?"
    a: "Skip slices when your codebase is tiny — a three-endpoint API doesn't need feature folders. Also avoid slicing shared infrastructure like authentication middleware or database connection setup; those belong in cross-cutting modules. The mistake is treating every line of code as a slice. Shared kernel code stays shared; business features get slices."
faqAnswers:
  - question: "When is software vertical slice architecture the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for software vertical slice architecture?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back software vertical slice architecture safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
A teammate once spent forty minutes tracing a single bug fix through our "clean" layered codebase: controller in WebApi, validation in Application, mapping in Infrastructure, repository interface in Domain, implementation back in Infrastructure. The bug was a missing null check in the validator. Forty minutes for one line, because the feature was scattered across five folders named after technical roles instead of business capabilities.

Vertical slice architecture flips that layout. Instead of grouping by layer (Controllers, Services, Repositories), you group by feature (CreateOrder, CancelSubscription, ExportReport). Each slice owns its endpoint, validation, business logic, and data access for one use case. When product asks to change how order creation handles discounts, you open one folder.

## The problem with horizontal layers

Layered architecture made sense when teams were small and applications were CRUD-heavy. You could hire a "database person" who lived in the Repository layer and never touched controllers. That model breaks down when features cross-cut every layer on every change.

The symptoms are familiar: pull requests that touch twelve files across four projects for a one-field addition; merge conflicts in shared service classes that every feature uses; integration tests that boot the entire application because no single class represents a complete feature. Layers optimize for *technical* separation. Product changes are *vertical* — they cut through every layer at once.

## Anatomy of a slice

A slice is a self-contained unit for one user action or command. In a .NET API using MediatR, a typical slice looks like this:

```
Features/
  Orders/
    CreateOrder/
      CreateOrderCommand.cs
      CreateOrderHandler.cs
      CreateOrderValidator.cs
      CreateOrderEndpoint.cs
    CancelOrder/
      CancelOrderCommand.cs
      ...
```

Each handler receives a request, validates it, executes business logic, and returns a response. Shared concerns — logging, authentication, database context — are injected via middleware or pipeline behaviors, not duplicated per slice.

```csharp
public record CreateOrderCommand(string CustomerId, List<LineItem> Items) : IRequest<Result<OrderId>>;

public class CreateOrderHandler : IRequestHandler<CreateOrderCommand, Result<OrderId>>
{
    public async Task<Result<OrderId>> Handle(CreateOrderCommand cmd, CancellationToken ct)
    {
        var customer = await _db.Customers.FindAsync(cmd.CustomerId, ct)
            ?? return Result.Fail("Customer not found");

        var order = Order.Create(customer, cmd.Items);
        _db.Orders.Add(order);
        await _db.SaveChangesAsync(ct);
        return Result.Ok(order.Id);
    }
}
```

The handler is the slice. It knows how to create an order. It doesn't delegate to a generic `OrderService` with forty methods that every feature shares.

## Shared code without shared god classes

The common objection: "Won't we duplicate code across slices?" Sometimes — and that's acceptable when the duplication is coincidental, not conceptual. Two slices validating email format the same way? Extract a shared validator. Two slices applying completely different discount rules that happen to use the same data type? Keep them separate.

What you must not do is preemptively extract a `BaseOrderService` because two handlers both call `_db.Orders`. That's how layered architecture sneaks back in through a side door. Share infrastructure (DbContext, message bus, auth context). Share domain primitives (Money, Email, OrderId value objects). Don't share feature logic until the third time you copy-paste identical business rules — then extract with a name that reflects the domain concept, not the technical layer.

## Slices and team boundaries

Vertical slices map cleanly to team ownership. The Payments team owns `Features/Payments/`. The Catalog team owns `Features/Catalog/`. Cross-team changes happen at bounded context boundaries — an event published by Catalog and consumed by Search — not through shared service classes both teams edit daily.

This reduces the "everyone touches OrderService" problem where three teams merge conflicting changes into the same 2,000-line class every sprint. Code review becomes faster too: a PR that adds `RefundOrder` only touches the RefundOrder slice, and reviewers can evaluate the complete feature in one diff.

## Testing becomes simpler

Unit tests target a single handler with mocked dependencies. Integration tests boot one slice's endpoint and verify the full request-response cycle without spinning up unrelated features. You stop writing tests like `OrderServiceTests` that cover twenty methods with two hundred test cases — most of which break when an unrelated method changes.

```csharp
[Fact]
public async Task CreateOrder_WithInvalidCustomer_ReturnsFailure()
{
    var handler = new CreateOrderHandler(_fakeDb);
    var result = await handler.Handle(new CreateOrderCommand("missing", []), default);
    Assert.False(result.IsSuccess);
}
```

The test reads like the feature: create order, bad customer, expect failure. No fixture hierarchy spanning four layers.

## Migration path from layers

You don't rewrite everything overnight. Pick the next feature you're building and create it as a slice. Leave existing layered code in place. Over time, when you touch a layered feature for a bug fix, extract its handler into a slice folder. Rename `OrderService.CreateOrder()` to `CreateOrderHandler.Handle()`. The layered folders shrink naturally as slices grow.

Avoid the trap of creating slice folders that still call the old god services internally — that's just reorganized layers without the benefit. The handler should own the logic, not delegate back to `OrderService`.

## Slice sizing heuristics

A slice should ship user-visible value in one to two weeks with one team. If the slice needs three services and a migration, split: first slice read-only UI on existing API, second slice write path. Slices are learning vehicles — oversized slices hide integration risk until month-end demos fail.

## Cross-slice shared kernel

Extract truly shared validation (Email, Money) to small kernel module — not a utils junk drawer. Slices depend on kernel; kernel depends on nothing. Resist shared/services becoming second monolith layer.

## Slice integration tests

One test hits HTTP endpoint through slice stack to database — replaces layered mock pyramid that never caught wrong repository wiring across slice boundary.

## Integration testing notes

Exercise the happy path plus three failure modes specific to software vertical slice architecture: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for software vertical slice architecture. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Name folders after user journeys — RegisterUser not Infrastructure. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

## Resources

- [Vertical Slice Architecture — Jimmy Bogard](https://jimmybogard.com/vertical-slice-architecture/)
- [MediatR library for CQRS-style handlers](https://github.com/jbogard/MediatR)
- [Organizing ASP.NET Core Minimal APIs by feature](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis)
- [Bounded contexts in domain-driven design](https://martinfowler.com/bliki/BoundedContext.html)
- [Colocation over separation — Dan Abramov](https://overreacted.io/goodbye-clean-code/)

## Field notes on software vertical slice architecture

Architecture work around software vertical slice architecture is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software vertical slice architecture:
- Prefer modular monolith seams you can extract later over premature microservices
- Encode ubiquitous language in types and test names, not slide decks
- Event contracts versioned; consumers tolerate additive changes only
- Feature toggles have owners and burn-down dates — permanent toggles are config debt

Workshop output should include a decision record: context, options, chosen path, and the metric that would force a revisit.

| Signal | Target | Alarm |
|--------|--------|-------|
| Latency p99 | Team-defined SLO | Page on burn rate |
| Error rate | Baseline − noise | Ticket if sustained |
| Cost per 1k ops | Budget cap | Weekly review |

## Migration path into software vertical slice architecture

Reviewers should challenge assumptions encoded in software vertical slice architecture: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for software vertical slice architecture: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for software vertical slice architecture: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for software vertical slice architecture: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Cross-team contracts for software vertical slice architecture

Roll out software vertical slice architecture behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Caching interactions with software vertical slice architecture

Detail 1 (551): for software vertical slice architecture, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with software vertical slice architecture becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software vertical slice architecture, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software vertical slice architecture: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in software vertical slice architecture

Detail 2 (180): for software vertical slice architecture, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in software vertical slice architecture becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software vertical slice architecture, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software vertical slice architecture: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.