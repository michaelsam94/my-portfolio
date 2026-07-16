---
title: "Proto DataStore for Typed, Safe Preferences"
slug: "proto-datastore-typed-preferences"
description: "Proto DataStore gives you typed, schema-backed preferences on Android: how it works, migrating from SharedPreferences, and the protobuf pitfalls to avoid."
datePublished: "2026-05-11"
dateModified: "2026-05-11"
tags: ["Android", "Data", "Kotlin"]
keywords: "Proto DataStore, typed preferences, DataStore migration, SharedPreferences replacement, protobuf DataStore"
faq:
  - q: "What is Proto DataStore?"
    a: "Proto DataStore is Android's typed key-value storage solution built on Kotlin coroutines and Flow, where the shape of your data is defined by a protocol buffer schema rather than loose string keys. Because the schema is compiled, every read and write is type-safe at compile time and you never guess at whether a value exists or what type it holds."
  - q: "What's the difference between Proto DataStore and Preferences DataStore?"
    a: "Preferences DataStore keeps the SharedPreferences-style API of untyped string keys, just wrapped in Flow and coroutines. Proto DataStore replaces that with a compiled protobuf message, so a typo can't create a phantom key and defaults are defined in one place. Use Preferences DataStore for a quick lift-and-shift, and Proto DataStore when the data has real structure."
  - q: "Can I migrate from SharedPreferences to Proto DataStore without losing data?"
    a: "Yes. DataStore ships a SharedPreferencesMigration that runs once on first read, copying existing keys into your proto message and then clearing the old file. You register it in the DataStore builder and map each legacy key into the corresponding proto field inside the migration lambda."
---

SharedPreferences has quietly caused more subtle bugs in my Android projects than almost any other API — a misspelled key that silently returns a default, a `getInt` on something stored as a `String`, a synchronous `commit()` blocking the main thread during a cold start. Proto DataStore fixes the root cause: instead of a loose bag of string keys, your persisted state is a single compiled protobuf message with real types, real defaults, and no stringly-typed guessing. You read it as a `Flow`, write it inside a transaction, and the compiler catches the mistakes that used to ship to production.

I've now migrated a couple of production apps off SharedPreferences to Proto DataStore, and the win isn't just cleanliness — it's that a whole category of "why is this setting wrong" tickets disappears. Here's how it actually works and where it bites.

## Why typed beats stringly-typed

The core problem with SharedPreferences is that the schema lives in your head. `prefs.getBoolean("dark_mode", false)` compiles whether or not `"dark_mode"` was ever written, whether it was written as a boolean, and whether some other module used `"darkMode"` instead. The type system gives you zero help.

Proto DataStore moves the schema into a `.proto` file that the build compiles into a Kotlin class. The field is `dark_mode` of type `bool`, full stop. You can't read it as an int, you can't misspell it, and the default is declared once in the serializer rather than scattered across every call site. When a `UserSettings` message grows to fifteen fields, that difference is the gap between confidence and archaeology.

## Defining the schema and serializer

You start with a protobuf definition. Keep it in `src/main/proto/`:

```proto
syntax = "proto3";

option java_package = "com.example.settings";
option java_multiple_files = true;

message UserSettings {
  bool dark_mode = 1;
  int32 sync_interval_minutes = 2;
  string preferred_language = 3;
  bool analytics_opt_in = 4;
}
```

Then you supply a `Serializer` so DataStore knows how to read and write the bytes. This is the one piece of boilerplate you can't avoid:

```kotlin
object UserSettingsSerializer : Serializer<UserSettings> {
    override val defaultValue: UserSettings = UserSettings.getDefaultInstance()

    override suspend fun readFrom(input: InputStream): UserSettings =
        try {
            UserSettings.parseFrom(input)
        } catch (e: InvalidProtocolBufferException) {
            throw CorruptionException("Cannot read UserSettings proto", e)
        }

    override suspend fun writeTo(t: UserSettings, output: OutputStream) =
        t.writeTo(output)
}

val Context.settingsStore: DataStore<UserSettings> by dataStore(
    fileName = "user_settings.pb",
    serializer = UserSettingsSerializer,
)
```

The `CorruptionException` matters more than it looks. When the underlying file gets truncated — a crash mid-write on a cheap device, a bad OTA — DataStore uses that signal to invoke your corruption handler instead of throwing on every subsequent read. Wire up a handler that resets to defaults; a bricked settings file should never brick the app.

## Reading and writing

Reads are a `Flow`, so your UI observes changes reactively and you get atomic snapshots — no torn reads where half the fields are old and half are new:

```kotlin
val darkMode: Flow<Boolean> = context.settingsStore.data
    .map { it.darkMode }
    .distinctUntilChanged()

suspend fun setDarkMode(enabled: Boolean) {
    context.settingsStore.updateData { current ->
        current.toBuilder().setDarkMode(enabled).build()
    }
}
```

`updateData` runs its lambda inside a transaction on a single background dispatcher, so concurrent writers are serialized and you never race. This is the behavior SharedPreferences' `apply()` only pretended to give you. If you're building a broader persistence story, this pairs naturally with the patterns I described in [a shared data layer with Room and KMP](https://blog.michaelsam94.com/shared-data-layer-room-kmp/) — DataStore for settings-shaped state, Room for relational data.

## Migrating off SharedPreferences

You almost never get a greenfield start, so the migration path is what really decides adoption. DataStore's `SharedPreferencesMigration` runs exactly once, on the first read after you ship the update:

```kotlin
val Context.settingsStore: DataStore<UserSettings> by dataStore(
    fileName = "user_settings.pb",
    serializer = UserSettingsSerializer,
    produceMigrations = { ctx ->
        listOf(
            SharedPreferencesMigration(ctx, "legacy_prefs") { prefs, current ->
                current.toBuilder()
                    .setDarkMode(prefs.getBoolean("dark_mode", false))
                    .setSyncIntervalMinutes(prefs.getInt("sync_interval", 15))
                    .build()
            }
        )
    },
)
```

Two things I learned the hard way. First, don't delete the old SharedPreferences access code the same day you add the migration — keep a rollback path in case the migration lambda has a mapping bug, because it only runs once and a wrong mapping is a wrong mapping forever. Second, test the migration with a real pre-populated prefs file in an instrumented test, not just an empty one. The interesting bugs only appear when there's legacy data present.

## Proto vs Preferences DataStore

Both live under the DataStore umbrella, and choosing wrong just means more work later. Here's how I decide:

| Concern | Preferences DataStore | Proto DataStore |
|---|---|---|
| Type safety | None (string keys) | Full (compiled schema) |
| Setup cost | Minimal | Serializer + .proto |
| Defaults | Per call site | One place |
| Refactor safety | Manual | Compiler-checked |
| Best for | Quick SharedPrefs swap | Structured, evolving state |

For a five-key toggle screen that will never grow, Preferences DataStore is fine and I won't pretend otherwise. But the moment settings have relationships, nested structure, or a lifespan measured in years, the protobuf schema pays for its own setup. If serialization choices interest you more broadly, I dug into the tradeoffs in [Kotlin serialization beyond JSON](https://blog.michaelsam94.com/kotlin-serialization-beyond-json/), and protobuf shows up there too as a compact, schema-first option.

## Schema evolution and the gotchas

Protobuf's field numbers are the contract, not the field names. You can rename `dark_mode` to `use_dark_theme` freely as long as it keeps field number `1`; you can add new fields with new numbers and old files still parse. What you must never do is reuse a retired field number for a different type — that's how you resurrect garbage data from an old install.

Other traps worth naming plainly: proto3 scalar fields can't distinguish "unset" from "default zero," so a `bool` that defaults to `false` can't tell you whether the user explicitly chose false — use a wrapper or an enum if that distinction matters. And keep the message small; DataStore rewrites the whole file on every `updateData`, so a multi-megabyte proto is the wrong tool. Settings and flags, yes. A cache of a thousand records, no — that's Room's job.

Used within those lines, Proto DataStore is the storage layer I wish Android had shipped first. Typed, coroutine-native, transactional, and boring in the best possible way.

## Resources

- [Android DataStore documentation](https://developer.android.com/topic/libraries/architecture/datastore)
- [Proto DataStore guide](https://developer.android.com/codelabs/android-proto-datastore)
- [Protocol Buffers language guide (proto3)](https://protobuf.dev/programming-guides/proto3/)
- [DataStore migration reference](https://developer.android.com/reference/kotlin/androidx/datastore/migrations/SharedPreferencesMigration)
- [Kotlin coroutines documentation](https://kotlinlang.org/docs/coroutines-overview.html)
