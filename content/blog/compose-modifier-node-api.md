---
title: "The Modifier.Node API for Custom Compose Behavior"
slug: "compose-modifier-node-api"
description: "The Modifier.Node API is Compose's low-allocation way to build custom modifiers, replacing composed{} with nodes that survive recomposition and cut GC pressure."
datePublished: "2026-06-06"
dateModified: "2026-06-06"
tags: ["Android", "Jetpack Compose", "Performance"]
keywords: "Modifier.Node, custom modifier Compose, modifier node API, Compose performance modifiers, delegatable node"
faq:
  - q: "What is the Modifier.Node API in Jetpack Compose?"
    a: "Modifier.Node is the lower-level API for writing custom modifiers as long-lived node objects attached to the layout tree, together with a ModifierNodeElement that creates and updates them. Unlike the older composed{} factory, a node isn't recreated on every recomposition — Compose updates the existing node in place — so custom modifiers stop allocating and stop triggering unnecessary recomposition."
  - q: "Why is Modifier.Node faster than composed{}?"
    a: "The composed{} approach runs a composable lambda for each modifier instance on every recomposition, which allocates and can pull in CompositionLocals that widen recomposition scope. A Modifier.Node is a plain object that Compose creates once and mutates when parameters change, so there is no per-recomposition allocation and no hidden composition happening inside the modifier."
  - q: "Do I need Modifier.Node for simple modifiers?"
    a: "No. If you can build your modifier by chaining existing modifiers in a plain function, do that — it is simpler and just as fast. Reach for Modifier.Node when you need to hook directly into draw, layout, pointer input, semantics, or focus, or when a composed{} modifier shows up as an allocation or recomposition hotspot in profiling."
---

If you've ever written a custom modifier with `Modifier.composed { ... }` and later found it lighting up a performance trace, you've met the problem the Modifier.Node API was built to solve. `composed{}` runs a composable for every instance of your modifier on every recomposition — it allocates, it can capture `CompositionLocal`s, and it quietly widens your recomposition scope. Modifier.Node replaces that with a long-lived node object that Compose creates once and updates in place, so custom modifiers stop being a hidden tax on your frame budget.

I'll be direct: for most app code you should reach for existing modifiers first and not think about this at all. But when you're writing library-grade or performance-sensitive custom behavior — a custom draw, a gesture, a layout tweak used in a scrolling list — Modifier.Node is the correct tool, and understanding it changes how you reason about the whole modifier system.

## The three parts

A custom modifier built on this API has three pieces:

- A **`Modifier.Node` subclass** that holds mutable state and implements the behavior by mixing in interfaces like `DrawModifierNode`, `LayoutModifierNode`, `PointerInputModifierNode`, or `SemanticsModifierNode`.
- A **`ModifierNodeElement`** that acts as the factory: it creates the node, updates an existing node when parameters change, and defines `equals`/`hashCode` so Compose knows when an update is even needed.
- A **public extension function** on `Modifier` that hides all of this behind a clean call site.

Here's a minimal custom draw modifier that paints a background circle:

```kotlin
private class CircleNode(var color: Color) : Modifier.Node(), DrawModifierNode {
    override fun ContentDrawScope.draw() {
        drawCircle(color)
        drawContent()
    }
}

private data class CircleElement(val color: Color) : ModifierNodeElement<CircleNode>() {
    override fun create() = CircleNode(color)
    override fun update(node: CircleNode) { node.color = color }
}

fun Modifier.circleBackground(color: Color): Modifier = this then CircleElement(color)
```

Notice what *doesn't* happen: no composable runs, no allocation on recomposition. When `color` changes, Compose calls `update` on the existing node and mutates one field. When it doesn't change, the `data class` equality on `CircleElement` tells Compose there's nothing to do. That's the entire performance story in one example.

## Why composed{} was a trap

`Modifier.composed { }` felt convenient because you could use `remember`, read `CompositionLocal`s, and generally write a modifier like a composable. That convenience is exactly the problem:

- Every modifier instance ran a **new composition** on each recomposition — allocation and work proportional to how often the composable recomposed.
- Reading a `CompositionLocal` inside it could **widen recomposition scope** in ways that were hard to see.
- Modifiers built this way couldn't be **skipped** or reasoned about structurally, so they undercut exactly the recomposition discipline you were trying to maintain elsewhere.

I've traced jank in a list to a `composed{}` modifier applied per-item that was allocating on every scroll frame. Converting it to a node made the allocations vanish. If you've spent time on [Compose performance, stability, and recomposition](https://blog.michaelsam94.com/compose-performance-stability-recomposition/), you already know that per-frame allocation in a scrolling container is one of the most reliable ways to introduce jank — and `composed{}` modifiers are a common, easy-to-miss source of it.

## Delegation: the feature that makes it composable

The API's best idea is `delegate`. A single node can delegate to other nodes, so you compose behavior from small, reusable pieces instead of one giant node that implements six interfaces:

```kotlin
class InteractiveCardNode(
    color: Color,
    onClick: () -> Unit,
) : DelegatingNode() {
    private val background = delegate(CircleNode(color))
    private val clickable = delegate(
        SuspendingPointerInputModifierNode { detectTapGestures { onClick() } }
    )
}
```

This is genuinely elegant. Instead of a monolithic node that tangles drawing and gesture handling, you assemble smaller nodes and let the parent coordinate them. It mirrors good object composition, and it's how the framework's own modifiers are built internally. When I write a reusable interaction modifier now, I think in terms of which small nodes to delegate to rather than one big `draw`-plus-`pointerInput` blob.

## composed{} vs Modifier.Node

| Aspect | `composed{}` | `Modifier.Node` |
| --- | --- | --- |
| Allocation on recomposition | Yes, per instance | None; node updated in place |
| Can read CompositionLocal | Yes, freely | Yes, via `currentValueOf` |
| Recomposition impact | Can widen scope | Contained |
| Access to draw/layout/pointer | Indirect | Direct interfaces |
| Boilerplate | Low | Higher (three parts) |
| Right for | Quick app-level modifiers | Library / hot-path modifiers |

The honest tradeoff is boilerplate. Modifier.Node makes you write three things where `composed{}` was one lambda. That's the price of admission, and it's why I don't convert every modifier — only the ones that are reused widely, sit in a hot path, or need direct access to draw/layout/pointer that `composed{}` couldn't give cleanly anyway.

## Reading CompositionLocals and coroutines from a node

Two practical needs come up constantly. First, you can still read `CompositionLocal`s from a node via `currentValueOf(LocalDensity)` and similar, but only while the node is attached — so read them inside `draw`, `measure`, or an effect, not in the constructor. Second, nodes get a `coroutineScope` tied to their attachment lifecycle, which is the right place to run animations or collect flows driven by the modifier. That scope is cancelled automatically when the node detaches, so you don't leak. This is the modern replacement for the awkward patterns people used to build with `composed{}` plus `LaunchedEffect`.

## When to actually use it

My rule of thumb, refined over a lot of Compose code:

1. **Can you express it by chaining existing modifiers in a plain function?** Do that. `fun Modifier.card() = this.padding(16.dp).clip(...).background(...)` needs no node.
2. **Do you need direct draw, layout, pointer, semantics, or focus hooks?** That's a node.
3. **Is a `composed{}` modifier showing up in a profile as allocation or recomposition churn?** Convert it to a node.
4. **Are you writing a library others depend on?** Prefer nodes for anything non-trivial, because your modifier's cost multiplies across every consumer.

This connects to broader API design in Compose too — the same instinct that leads you toward a well-shaped [styles API in Jetpack Compose](https://blog.michaelsam94.com/jetpack-compose-styles-api/) applies here: expose a clean, minimal call site and hide the machinery. Users of your `Modifier.circleBackground(color)` never need to know a node exists, which is exactly right.

The Modifier.Node API isn't something every Compose developer needs to touch weekly. But when you're writing the reusable, performance-sensitive modifiers that a whole app leans on, it's the difference between a modifier that's free and one that quietly costs you frames. Learn it, keep it in reserve, and pull it out when the profiler — not your instinct — tells you `composed{}` has become the bottleneck.

## Resources

- [Compose Modifier.Node documentation](https://developer.android.com/reference/kotlin/androidx/compose/ui/node/ModifierNodeElement)
- [Custom modifiers guide](https://developer.android.com/develop/ui/compose/custom-modifiers)
- [Compose performance guidance](https://developer.android.com/develop/ui/compose/performance)
- [AndroidX Compose UI source](https://github.com/androidx/androidx/tree/androidx-main/compose/ui)
- [Now in Android sample app](https://github.com/android/nowinandroid)
