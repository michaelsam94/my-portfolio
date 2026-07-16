---
title: "Clean Architecture, Pragmatically"
slug: "clean-architecture-pragmatically"
description: "Clean Architecture without the dogma: the dependency rule that matters, when layers earn their keep, and how to apply it pragmatically in real code."
datePublished: "2026-05-26"
dateModified: "2026-05-26"
tags: ["Clean Architecture", "Software Design", "Architecture", "Mobile"]
keywords: "Clean Architecture, software architecture, layered architecture, use cases, dependency rule, hexagonal"
faq:
  - q: "What is the core idea of Clean Architecture?"
    a: "The core idea is the dependency rule: source code dependencies point inward, toward business logic. Your domain and use cases know nothing about frameworks, databases, or UI, so those outer details can change without touching the code that holds your business value."
  - q: "Is Clean Architecture overkill for small apps?"
    a: "The full ceremony of many layers and mappers can be overkill for a small app. The underlying principle — keep business logic independent of frameworks — scales down fine. Apply the dependency rule everywhere; add layers only where they earn their keep."
  - q: "What is the difference between Clean Architecture and hexagonal architecture?"
    a: "They share the same goal: isolate business logic from external concerns. Hexagonal (ports and adapters) frames it as a core surrounded by pluggable adapters. Clean Architecture adds named concentric layers like entities and use cases. In practice they are close cousins."
---

Strip away the diagrams and the concentric circles and Clean Architecture is one rule: **source code dependencies point inward, toward your business logic.** Your domain and use cases must not know what database, UI framework, or HTTP client you use. Everything else — layers, mappers, interfaces — exists to serve that rule. If you internalize the dependency rule and treat the rest as tools you reach for *when they earn their keep*, you get the benefit (business logic that outlives frameworks and is trivial to test) without the cargo-cult ceremony that gives Clean Architecture a bad name.

I have applied this at scale in Flutter and on backends, and I have also watched teams drown in boilerplate applying it too literally. Here is the pragmatic version.

## The dependency rule is the whole point

Picture layers from the inside out: **entities** (core business objects and rules), **use cases** (application-specific business logic), then **interface adapters** (presenters, repositories, controllers), then **frameworks and drivers** (UI, database, network). The rule: inner layers never depend on outer ones. A use case defines an interface it needs; the outer layer implements it. Dependencies point in; control flows out via those interfaces.

```
        ┌─────────────────────────────┐
        │  Frameworks & Drivers        │  Flutter, SQLite, HTTP
        │  ┌───────────────────────┐   │
        │  │  Interface Adapters    │  │  repos, presenters
        │  │  ┌─────────────────┐   │  │
        │  │  │   Use Cases      │  │  │  application logic
        │  │  │  ┌───────────┐   │  │  │
        │  │  │  │ Entities   │  │  │  │  business rules
        │  │  │  └───────────┘   │  │  │
        │  │  └─────────────────┘   │  │
        │  └───────────────────────┘   │
        └─────────────────────────────┘
         dependencies point INWARD →
```

The payoff is concrete: swap SQLite for a REST API, or Flutter for a CLI, and your entities and use cases do not change. And you can test business logic with zero framework in play.

## Dependency inversion in practice

The mechanism that makes inward dependencies work is the *dependency inversion principle*. The use case declares an abstract need; the outer layer satisfies it. In Dart:

```dart
// Domain layer — knows nothing about HTTP or SQLite.
abstract interface class ChargerRepository {
  Future<List<Charger>> availableNearby(LatLng origin);
}

class GetNearbyChargers {          // a use case
  const GetNearbyChargers(this._repo);
  final ChargerRepository _repo;

  Future<List<Charger>> call(LatLng origin) => _repo.availableNearby(origin);
}

// Data layer — the arrow points inward: it implements the domain interface.
class HttpChargerRepository implements ChargerRepository {
  @override
  Future<List<Charger>> availableNearby(LatLng origin) async {
    // HTTP, JSON parsing, caching — all quarantined here.
  }
}
```

`GetNearbyChargers` is pure logic. Its test injects a fake repository and asserts behavior — no server, no widgets, no waiting. That is the entire value proposition, and it is worth a lot on a large codebase.

## Where the dogma goes wrong

Purists apply *every* layer to *every* feature, and that is where teams suffer:

- **Mapper explosion.** A separate model for entity, DTO, and UI, with mappers between each, for a screen that just displays three fields the server already returns. Three classes and two mappers to show a name.
- **Use cases that only forward.** A `GetUserUseCase` whose entire body is `return repo.getUser()` adds a file and indirection with zero logic. If a use case has no logic, let the presenter call the repository.
- **Interfaces with one implementation, forever.** Abstraction is insurance against change. If a boundary will never have a second implementation and is trivial to refactor later, the interface is premature.

Robert C. Martin's own point is that these are *tools*, not commandments. The dependency rule is the principle; the number of layers is a judgment call.

## How I decide how much structure to apply

I scale the ceremony to the stakes of the code:

| Code type | Structure I apply |
| --- | --- |
| Core business rules (billing, pricing) | Full separation: entities, use cases, interfaces — this is the crown jewels |
| CRUD-ish feature with real logic | Use cases + repository interface, shared models where the DTO already fits |
| Trivial display screen | Presenter calls repository directly; skip the empty use case |
| Throwaway / prototype | Whatever ships; refactor if it survives |

The billing logic in a system I built got the full treatment because it was where correctness mattered and where requirements churned. A settings screen did not. Applying identical rigor to both would have been a waste on one end and negligence on the other.

## It composes with everything else

The dependency rule is not a standalone religion; it is the connective tissue. It is how you keep a [modular monolith's](https://blog.michaelsam94.com/modular-monoliths-vs-microservices/) modules from rotting into a big ball of mud — each module's core depends inward, not on its neighbors' internals. It is why a well-layered app can swap transports the way the [EV platform I built](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) reused one command schema across cloud and local paths: the inner logic did not know or care which transport delivered the message.

Clean Architecture, done pragmatically, is not about drawing the perfect circles. It is about asking one question at every boundary: *does my business logic depend on this detail, or does this detail depend on my business logic?* Keep the arrow pointing inward for the code that matters, skip the ceremony for the code that does not, and you get durable, testable systems without burying your team in boilerplate. Want a review of where to draw those lines in your codebase? [Get in touch](/#contact).

## Resources

- [The Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Martin Fowler: PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html)
- [Android guide to app architecture](https://developer.android.com/topic/architecture)
- [Dependency inversion principle](https://martinfowler.com/articles/dipInTheWild.html)
- [Flutter architecture recommendations](https://docs.flutter.dev/app-architecture)
