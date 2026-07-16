---
title: "Calling Kotlin Multiplatform from SwiftUI"
slug: "kotlin-multiplatform-swiftui-interop"
description: "How to consume a Kotlin Multiplatform shared module from SwiftUI: the Objective-C bridge, suspend functions and Flows in Swift, and wrapping it cleanly."
datePublished: "2024-06-10"
dateModified: "2024-06-10"
tags: ["Kotlin", "Kotlin Multiplatform", "iOS"]
keywords: "Kotlin Multiplatform SwiftUI, KMP iOS interop, suspend function Swift, Kotlin Flow Swift, KMP-NativeCoroutines, ObjC bridge"
faq:
  - q: "How do you call a Kotlin suspend function from Swift?"
    a: "The Kotlin/Native compiler exposes a suspend function to Swift as a function with a completion handler, which Swift bridges into an async function you can await. So a Kotlin suspend fun load(): User becomes something you call as try await load() in Swift. Cancellation and error propagation work, but Flows and some generics need extra tooling because the default bridge doesn't map them well."
  - q: "Why do Kotlin Flows not map cleanly to Swift?"
    a: "The Objective-C bridge that Kotlin/Native uses has no native concept of a Kotlin Flow, so a Flow is exposed as an opaque type you can't collect idiomatically from Swift. The common fix is a library like KMP-NativeCoroutines or SKIE, which generates Swift-friendly wrappers turning Flows into AsyncSequence and suspend functions into clean async APIs. Without such a tool you end up writing manual collector callbacks."
  - q: "Should SwiftUI depend on the shared Kotlin module directly?"
    a: "It works, but it is cleaner to put a thin Swift wrapper or ViewModel layer between SwiftUI and the shared framework. That isolates the slightly awkward bridged types, lets you expose idiomatic Swift Observable objects, and means SwiftUI views never see Kotlin-specific artifacts. It also makes it far easier to evolve the shared API without churning every view."
---

The mechanics of calling a Kotlin Multiplatform module from SwiftUI come down to one fact: Kotlin/Native exposes your shared code to Swift through an **Objective-C framework**, so everything Swift sees has passed through the ObjC bridge. Plain classes, functions, and value types come across cleanly and feel almost native. Suspend functions bridge into Swift `async` functions you can `await`. The rough edges are `Flow` and Kotlin generics, which the ObjC bridge has no vocabulary for — and that's precisely where a tool like SKIE or KMP-NativeCoroutines earns its place. Get the bridge model in your head and the whole integration stops feeling like magic.

I've shipped a KMP shared module backing both an Android app and a SwiftUI app, and the thing I wish I'd internalized on day one is that the *shape* of your shared API determines how pleasant the Swift side feels. Design the shared surface for the bridge, wrap it in a thin Swift layer, and SwiftUI never has to know it's talking to Kotlin.

## What the bridge exposes

When you build the shared module for iOS, Kotlin/Native produces an `.framework` (or an XCFramework) with an Objective-C header. Swift imports it like any Apple framework:

```swift
import shared   // your KMP module's framework name

let repo = UserRepository()
let name = repo.formatName(user: user)   // plain call, feels native
```

Simple functions, data classes, enums, and sealed hierarchies bridge well. A Kotlin `data class User(val id: String, val name: String)` becomes a Swift class with the properties you'd expect. Two things to watch: Kotlin `Int` maps to Swift `Int32` (not `Int`), and everything lands under the framework's namespace, sometimes with a prefix, so names can look slightly foreign. Neither is a real obstacle — just know it before you go hunting for a type that "moved."

## Suspend functions become async

This is the part that works better than people expect. A Kotlin suspend function:

```kotlin
class UserRepository {
    suspend fun load(id: String): User { /* ... */ }
}
```

is exposed to Swift with a completion handler, which Swift's concurrency interop turns into a proper `async` function:

```swift
let user = try await repo.load(id: "42")
```

Errors thrown in Kotlin surface as Swift `throws`, and Swift task cancellation propagates into Kotlin's [cooperative cancellation](https://blog.michaelsam94.com/kotlin-coroutine-cancellation-cooperative/). So a `Task` you cancel in SwiftUI cancels the coroutine underneath. That's a genuinely clean bridge — for one-shot async calls, you barely notice you've crossed a language boundary.

## Flows are where it gets awkward

`Flow` is the sharp edge. The ObjC bridge has no concept of it, so a Kotlin `Flow<T>` comes across as an opaque type you can't `for await` over idiomatically. Out of the box you're reduced to manual collection with callbacks, which is verbose and easy to leak. The pragmatic fix is a code-generation tool:

- **SKIE** (from Touchlab) post-processes your framework and generates Swift wrappers that turn `Flow` into Swift `AsyncSequence` and expose sealed classes as Swift enums you can `switch` over exhaustively. It's the closest thing to "it just works."
- **KMP-NativeCoroutines** annotates your Kotlin APIs and generates Swift extensions giving you `async` and `AsyncSequence` variants with proper cancellation.

With SKIE, collecting a shared `Flow` in SwiftUI looks like idiomatic Swift:

```swift
for await state in repo.observeUser() {   // Flow -> AsyncSequence via SKIE
    self.user = state
}
```

Without one of these, you write a manual collector that takes a callback and returns a cancellable handle, then remember to cancel it in `onDisappear`. I've done it both ways; the tooling is worth adopting on day one rather than hand-rolling collectors you'll get subtly wrong. This is the same reasoning behind choosing generated, type-safe layers elsewhere — like [SQLDelight for KMP persistence](https://blog.michaelsam94.com/kotlin-multiplatform-sqldelight/) — let a generator handle the bridge boilerplate.

## Wrap the shared module behind a Swift ViewModel

The architectural decision that pays off most: don't let SwiftUI views touch the shared framework directly. Put a thin Swift `ObservableObject` between them.

```swift
@MainActor
final class UserViewModel: ObservableObject {
    @Published var user: User?
    @Published var error: String?

    private let repo = UserRepository()   // the KMP type

    func load(id: String) async {
        do { user = try await repo.load(id: id) }
        catch { self.error = error.localizedDescription }
    }
}
```

```swift
struct UserView: View {
    @StateObject var vm = UserViewModel()
    var body: some View {
        // pure SwiftUI, no Kotlin types in sight
        Text(vm.user?.name ?? "…")
            .task { await vm.load(id: "42") }
    }
}
```

Now the bridged types — the ones with `Int32` quirks and namespaced names — live in one file. Views bind to plain `@Published` Swift properties. When the shared API changes, you update the wrapper, not every view. This is standard MVVM, but the boundary does double duty: it also quarantines the interop friction so it never spreads into your view layer.

## Threading and memory: two things to respect

Two runtime realities to keep in mind. First, callbacks from Kotlin coroutines may arrive on a background thread, so anything touching SwiftUI state must hop to the main actor — the `@MainActor` on the ViewModel above handles that. Second, the Kotlin/Native memory model changed: the current one allows sharing objects across threads without the old freezing rules, so you no longer fight `InvalidMutabilityException`. If you're on a recent Kotlin version you get the new model by default; if you inherit an older KMP project, migrating off the legacy memory model is worth doing before anything else, because the freezing errors are miserable to debug.

## The workflow that holds up

Putting it together, the setup I recommend:

1. Design the shared API with the bridge in mind — favor suspend functions and `Flow`, avoid exposing Kotlin generics and deeply nested type parameters across the boundary.
2. Adopt SKIE (or KMP-NativeCoroutines) from the start so `Flow` and sealed types feel native in Swift.
3. Ship the iOS binary as an XCFramework, ideally consumed via Swift Package Manager or CocoaPods so versioning is sane.
4. Wrap everything in Swift `ObservableObject` ViewModels; keep Kotlin types out of your views.
5. Route all UI-state updates through `@MainActor`.

Do that and SwiftUI developers on the team can work against clean, idiomatic Swift APIs while the business logic lives once in Kotlin, shared with Android. The interop isn't frictionless — the `Flow` gap is real and the ObjC bridge shows through in small ways — but with the right tooling and a thin wrapper layer, KMP delivers on its core promise: write the logic once, consume it natively on both platforms.

## Resources

- [Kotlin/Native interoperability with Swift/Objective-C](https://kotlinlang.org/docs/native-objc-interop.html)
- [Kotlin Multiplatform documentation](https://kotlinlang.org/docs/multiplatform.html)
- [SKIE — Swift-friendly KMP APIs (Touchlab)](https://skie.touchlab.co/)
- [KMP-NativeCoroutines (Rick Clephas)](https://github.com/rickclephas/KMP-NativeCoroutines)
- [Kotlin/Native memory management](https://kotlinlang.org/docs/native-memory-manager.html)
