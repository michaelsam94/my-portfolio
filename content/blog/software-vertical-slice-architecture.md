---
title: "Vertical Slice Architecture"
slug: "software-vertical-slice-architecture"
description: "Organize code by feature slices instead of technical layers. Vertical slice architecture keeps related handlers, validation, and persistence together so changes stay local and teams ship faster."
datePublished: "2025-09-01"
dateModified: "2025-09-01"
tags: ["Architecture", "Software Design", "Clean Code", "Backend"]
keywords: "vertical slice architecture, feature folders, CQRS handlers, MediatR, slice-based organization, avoid anemic domain, colocate feature code"
faq:
  - q: "How is vertical slice architecture different from layered architecture?"
    a: "Layered architecture groups code by technical role — all controllers in one folder, all repositories in another. Vertical slice architecture groups code by feature: everything for CreateOrder lives together. When you change order creation, you touch one slice instead of hunting across four layers. Layers optimize for separation of concerns; slices optimize for change locality."
  - q: "Does vertical slice architecture replace domain-driven design?"
    a: "No — they complement each other. DDD gives you bounded contexts and domain models; vertical slices give you a folder structure that respects those boundaries. A slice inside the Orders context contains its handler, validator, and mapping logic. You still model aggregates and domain events; you just stop scattering them across generic Infrastructure and Application folders."
  - q: "When should I avoid vertical slices?"
    a: "Skip slices when your codebase is tiny — a three-endpoint API doesn't need feature folders. Also avoid slicing shared infrastructure like authentication middleware or database connection setup; those belong in cross-cutting modules. The mistake is treating every line of code as a slice. Shared kernel code stays shared; business features get slices."
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

## Common production mistakes

Teams get software vertical slice architecture wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of software vertical slice architecture fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Vertical Slice Architecture — Jimmy Bogard](https://jimmybogard.com/vertical-slice-architecture/)
- [MediatR library for CQRS-style handlers](https://github.com/jbogard/MediatR)
- [Organizing ASP.NET Core Minimal APIs by feature](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis)
- [Bounded contexts in domain-driven design](https://martinfowler.com/bliki/BoundedContext.html)
- [Colocation over separation — Dan Abramov](https://overreacted.io/goodbye-clean-code/)
