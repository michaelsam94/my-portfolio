---
title: "Automating Tasks with Kotlin Scripting"
slug: "kotlin-scripting-kts-automation"
description: "Use Kotlin scripting (.kts) for real automation: shebang scripts, dependencies with @file:DependsOn, and when a .kts script beats Bash or a Gradle task."
datePublished: "2024-09-27"
dateModified: "2024-09-27"
tags: ["Kotlin", "DevOps", "Automation", "Backend"]
keywords: "Kotlin scripting, .kts script, kotlin main-kts, Kotlin shebang script, DependsOn kotlin, kotlin automation"
faq:
  - q: "How do I run a Kotlin script from the command line?"
    a: "Save the code as a .main.kts file and run it with the kotlin command, or add a shebang line pointing at the kotlin runner and make the file executable so you can run it directly. The main-kts scripting host compiles and caches the script, so the second run is fast. This gives you a real scripting workflow without a build file."
  - q: "Can a Kotlin script use external libraries?"
    a: "Yes. In a .main.kts file, add @file:DependsOn(\"group:artifact:version\") at the top and @file:Repository if you need a custom Maven repo. The scripting host resolves and downloads the dependency, then makes it available to the script. This lets a single-file script pull in an HTTP client, a JSON parser, or any Maven library."
  - q: "When should I use a Kotlin script instead of Bash?"
    a: "Reach for a Kotlin script when the logic has real data structures, error handling, or library needs that would make Bash brittle — parsing JSON, calling HTTP APIs, non-trivial control flow. Bash is still better for short pipelines of shell commands. The rule of thumb: if you find yourself reaching for jq, arrays, and functions in Bash, a Kotlin script will be more maintainable."
---

Kotlin scripting — `.kts` files run directly rather than compiled into an app — is one of the most underused parts of the Kotlin ecosystem. Everyone knows `build.gradle.kts` is a Kotlin script, but far fewer people use standalone `.main.kts` scripts to replace the pile of fragile Bash and one-off Python that accumulates around every project. I've swapped out gnarly release scripts, log parsers, and API-poking glue for single-file Kotlin scripts, and the maintainability difference is stark: real types, real error handling, and the same language as the codebase.

The core question isn't "can Kotlin script?" — it can — it's "when is a script the right tool, and how do I make it pull dependencies without a build file?" Both have clean answers.

## The simplest script: shebang and go

A `.main.kts` file is a self-contained Kotlin script. Add a shebang and mark it executable, and it runs like any other script:

```kotlin
#!/usr/bin/env kotlin

val name = args.getOrElse(0) { "world" }
println("Hello, $name")
```

```bash
chmod +x greet.main.kts
./greet.main.kts Michael
```

`args` is available implicitly — no `fun main` required. The first run compiles the script (there's a startup cost), but the `main-kts` host caches the compiled result, so subsequent runs are quick. That caching is what makes Kotlin scripting practical for tools you run repeatedly, not just once.

## Dependencies without a build file

Here's the feature that makes Kotlin scripting genuinely useful: a single file can declare Maven dependencies. Annotate the file and the scripting host resolves them for you.

```kotlin
#!/usr/bin/env kotlin

@file:DependsOn("com.squareup.okhttp3:okhttp:4.12.0")
@file:DependsOn("com.squareup.moshi:moshi-kotlin:1.15.1")

import okhttp3.OkHttpClient
import okhttp3.Request

val client = OkHttpClient()
val req = Request.Builder().url("https://api.github.com/repos/JetBrains/kotlin").build()
client.newCall(req).execute().use { resp ->
    println("Stars: ${resp.body?.string()?.let { extractStars(it) }}")
}
```

`@file:DependsOn` pulls artifacts from Maven Central; `@file:Repository` adds custom repos. Suddenly a single file can make HTTP calls with OkHttp, parse JSON with Moshi, or use any library on Maven — no `build.gradle`, no project structure. This is the capability that lets a script grow up: it starts as ten lines and can reach for real libraries the moment the task demands them, without becoming a "project."

## When a script beats the alternatives

The honest decision matrix, because Kotlin scripting isn't always the answer:

| Task shape | Best tool | Why |
| --- | --- | --- |
| Short pipeline of shell commands | Bash | Bash is built for piping processes |
| JSON/HTTP, real data structures, error handling | Kotlin script | Types and libraries beat `jq` gymnastics |
| Logic your app already implements | Gradle task / app entrypoint | Reuse code, don't reimplement |
| Cross-platform dev tooling | Kotlin script | Same script runs anywhere the JVM does |
| Hot-path production job | Compiled app | Skip per-run compile/startup cost |

My rule of thumb: the moment a Bash script sprouts arrays, functions, and three `jq` invocations, it's telling you it wants to be a Kotlin script. Conversely, if you're just chaining `git`, `docker`, and `cp`, Bash is fine — don't over-engineer it.

## A real example: a release-notes generator

The scripts that pay off most are the ones that touch data with structure. A release-notes generator that reads git log, groups commits by conventional-commit type, and formats markdown is miserable in Bash and pleasant in Kotlin:

```kotlin
#!/usr/bin/env kotlin

val log = ProcessBuilder("git", "log", "--pretty=%s", "HEAD~50..HEAD")
    .redirectErrorStream(true).start()
    .inputStream.bufferedReader().readLines()

val groups = log.groupBy { line ->
    when {
        line.startsWith("feat") -> "Features"
        line.startsWith("fix")  -> "Fixes"
        else -> "Other"
    }
}

groups.forEach { (heading, commits) ->
    println("## $heading")
    commits.forEach { println("- ${it.substringAfter(": ")}") }
    println()
}
```

Real collections, `groupBy`, `when` — logic that would be error-prone shell one-liners is readable and testable-in-your-head Kotlin. And because it's the same language as the app, any engineer on the team can maintain it without context-switching to a second scripting language.

## Fitting scripts into CI

Kotlin scripts slot naturally into CI pipelines where you'd otherwise write shell steps. Because they can pull dependencies and produce structured output, they're good for tasks like validating a release manifest, posting a formatted status to an API, or transforming build metadata — the connective tissue around a build. Keep the *heavy* build logic in Gradle where it belongs, and use scripts for the glue that would otherwise be brittle inline YAML shell. The same reliability mindset from [generating build artifacts in CI](https://blog.michaelsam94.com/android-baseline-profiles-ci/) applies: a typed script fails loudly and predictably, where a shell one-liner fails silently.

## A few practical gotchas

- **First-run compile cost.** Scripts compile on first run; the cache makes repeats fast, but a fresh CI container recompiles. For hot paths, prefer a compiled tool.
- **Keep them single-file.** The strength of `.main.kts` is that it's one file you can read top to bottom. If it wants multiple files and modules, it wants to be a real project.
- **Pin dependency versions.** `@file:DependsOn` with a floating version is a reproducibility hazard — pin exact versions so the script behaves the same next month.
- **Error handling is real.** Unlike Bash's silent failures, exceptions surface with stack traces. Lean on that; let it throw rather than swallowing errors.

## What I'd take away

Kotlin scripting turns Kotlin into a legitimate replacement for the Bash-and-Python glue that surrounds every project. A `.main.kts` file with a shebang runs directly, caches its compilation for fast repeats, and can pull any Maven library with `@file:DependsOn` — so a single file scales from a ten-line helper to a real HTTP-and-JSON tool. Use it when tasks have structure, error handling, or library needs that make Bash brittle; keep Bash for short shell pipelines and Gradle for heavy build logic. The win isn't novelty — it's one language, real types, and scripts your whole team can maintain.

## Resources

- [Kotlin custom scripting and main-kts](https://kotlinlang.org/docs/custom-script-deps-tutorial.html)
- [Kotlin command-line compiler and running scripts](https://kotlinlang.org/docs/command-line.html)
- [KEEP — Kotlin scripting support](https://github.com/Kotlin/KEEP/blob/master/proposals/scripting-support.md)
- [Gradle Kotlin DSL primer](https://docs.gradle.org/current/userguide/kotlin_dsl.html)
