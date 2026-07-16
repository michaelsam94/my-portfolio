---
title: "remember Keys and the Bugs They Quietly Prevent"
slug: "compose-remember-keys-pitfalls"
description: "remember keys in Jetpack Compose: how remember(key) invalidates cached state, why missing keys cause stale values, and the difference from rememberSaveable and list keys."
datePublished: "2024-08-29"
dateModified: "2024-08-29"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "Compose remember key, remember vs rememberSaveable, stale state Compose, key parameter, LazyColumn item key, recomposition"
faq:
  - q: "What does the key parameter of remember do?"
    a: "The key (or keys) passed to remember tells Compose when to throw away the cached value and recompute it. As long as the keys are equal across recompositions, remember returns the same stored object; when any key changes, the calculation runs again and the old value is discarded. Without a key, remember holds its value for the entire time the composable stays in composition, which is often the source of stale-state bugs."
  - q: "Why is my remembered value stale after the input changed?"
    a: "Because you remembered it without a key, so Compose kept the first computed value even though the input changed. For example, remember { expensiveDerive(id) } captures the derivation for the original id and never recomputes when id changes. Adding the input as a key, remember(id) { expensiveDerive(id) }, makes Compose recompute whenever id changes, fixing the staleness."
  - q: "What's the difference between remember and rememberSaveable?"
    a: "remember survives recomposition but not configuration changes or process death, so a rotation wipes it. rememberSaveable additionally persists the value into the saved instance state bundle, so it survives rotation and process recreation, at the cost of the value needing to be Saveable or having a custom Saver. Use remember for transient UI state and rememberSaveable for anything the user would be annoyed to lose."
---

The `key` argument to `remember` is the difference between "recompute this when the input changes" and "compute this once and cling to a stale value forever." `remember { block }` caches the result of `block` and returns the same instance across recompositions for as long as the composable stays in the composition. `remember(key) { block }` adds an invalidation condition: when `key` changes, Compose throws the cached value away and re-runs `block`. That single parameter prevents a whole family of subtle, hard-to-spot staleness bugs — and forgetting it is one of the most common Compose mistakes I catch in review.

Let me make the failure modes concrete, because they don't crash — they just quietly show the wrong thing.

## The stale-derivation bug

The archetypal mistake: an expensive computation remembered without keying it to its input.

```kotlin
@Composable
fun UserBadge(userId: String) {
    // BUG: computed once for the first userId, never recomputed.
    val color = remember { colorForUser(userId) }
    Badge(color)
}
```

When `userId` changes (say this composable is reused in a list for a different user), `color` stays the value derived from the *original* id. The fix is to declare the dependency:

```kotlin
val color = remember(userId) { colorForUser(userId) }
```

Now Compose recomputes `color` whenever `userId` changes and returns the cached one otherwise. The rule that prevents this class of bug entirely: **whatever your `remember` block reads, key on it.** If the block reads `userId` and `theme`, key on both: `remember(userId, theme) { ... }`.

## remember is not free caching — it's identity

People treat `remember` as "make this fast." It's really "give this object a stable identity across recompositions." That distinction matters for mutable holders:

```kotlin
val listState = remember { mutableStateListOf<Item>() }
```

Here you specifically *don't* want a key — you want one list that persists across recompositions and accumulates items. If you accidentally keyed it on something that changes, you'd get a brand-new empty list every time that thing changed, silently losing state. So the question for every `remember` is: "do I want this to reset when X changes?" If yes, key on X. If it should live for the composable's whole lifetime, no key. Being deliberate about that question is the skill.

## remember vs rememberSaveable

`remember` survives recomposition but dies on configuration change and process death. Rotate the device and it's gone. `rememberSaveable` additionally stashes the value in the saved-instance-state bundle so it survives rotation and process recreation:

```kotlin
var query by rememberSaveable { mutableStateOf("") }  // survives rotation
var isExpanded by remember { mutableStateOf(false) }  // transient, fine to lose
```

The heuristic: would the user be annoyed if this reset when they rotated the phone or the process was killed in the background? A search query, a partially filled form, a selected tab — `rememberSaveable`. A transient "is this menu open" flag — `remember` is fine. `rememberSaveable` needs the value to be `Parcelable`/`Bundle`-able or to have a custom `Saver`, which is the extra cost. Note `rememberSaveable` *also* takes keys, with the same invalidation semantics.

## Keys in lists are a different (but related) thing

`remember` keys and `LazyColumn` item keys look similar and solve related problems. The list `key` tells Compose which item is which across data changes:

```kotlin
LazyColumn {
    items(messages, key = { it.id }) { message ->
        // Any remember { } inside here is scoped to this item's identity.
        var expanded by remember { mutableStateOf(false) }
        MessageRow(message, expanded) { expanded = !expanded }
    }
}
```

With a stable `key = { it.id }`, when the list reorders, Compose moves the composable *and its remembered state* with the item — so the `expanded` flag follows the right message. Without a key, Compose matches by position, and reordering leaves the expanded state stuck to a *slot* rather than an item, so the wrong row appears expanded. This is the list-level analog of the `remember` key: identity is what keeps state attached to the right thing. It's the same [recomposition and identity discipline](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) at two different scopes.

## A subtle trap: keys that are unstable

Because a changed key triggers recomputation, passing a key that changes every recomposition defeats `remember` entirely:

```kotlin
// BUG: new list allocated each recomposition -> key always "changes"
val processed = remember(items.map { it.id }) { process(items) }
```

`items.map { it.id }` allocates a fresh list each time, and even though the contents are equal, the reference used for keying leads to unnecessary recomputation unless `equals` saves you (list `equals` is by content, so this specific case survives — but a non-data-class key wouldn't). The lesson: keys should be stable, cheap-to-compare values. Prefer keying on the primitive that actually drives the computation (`userId`, `page`) rather than derived collections.

## My checklist for every remember

- Does the block read a value that can change? Key on it.
- Should this reset when something changes? Key on that thing; otherwise no key.
- Would the user hate losing this on rotation? `rememberSaveable`, and confirm it's `Saveable`.
- Is this inside a list item? Make sure the *list* has a stable `key` so state follows the item.
- Are my keys stable and cheap to compare? Key on primitives, not freshly-allocated objects.

None of these are advanced, but together they eliminate the quiet staleness bugs that survive code review because the app doesn't crash — it just shows last user's color, keeps a stale search result, or expands the wrong row after a reorder. `remember`'s key parameter is small; the bugs it prevents are not.

## Resources

- [State and remember in Compose](https://developer.android.com/develop/ui/compose/state)
- [rememberSaveable and state saving](https://developer.android.com/develop/ui/compose/state-saving)
- [Lists and keys in Compose](https://developer.android.com/develop/ui/compose/lists)
- [Side effects and keys](https://developer.android.com/develop/ui/compose/side-effects)
- [Compose mental model](https://developer.android.com/develop/ui/compose/mental-model)
