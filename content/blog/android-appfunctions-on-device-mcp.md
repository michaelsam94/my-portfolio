---
title: "Android AppFunctions and On-Device MCP for Agents"
slug: "android-appfunctions-on-device-mcp"
description: "How Android AppFunctions expose app capabilities to on-device agents, how it relates to MCP and App Actions, and how to make your app assistant-callable safely."
datePublished: "2026-03-30"
dateModified: "2026-03-30"
tags: ["Android", "AI Agents", "AppFunctions", "On-Device AI"]
keywords: "AppFunctions, Android MCP, on-device MCP server, Android agents, Gemini app actions, app intents, App Functions API"
faq:
  - q: "What are Android AppFunctions?"
    a: "AppFunctions are typed, annotated Kotlin functions your app exposes to the system so an on-device agent like Gemini can discover and invoke them. Think of them as structured entry points — 'start a charge session', 'find a receipt' — that an assistant can call with real arguments rather than screen-scraping your UI."
  - q: "How do AppFunctions relate to MCP?"
    a: "Conceptually they solve the same problem MCP solves for servers: exposing typed capabilities to an agent. AppFunctions is Android's on-device, intent-style mechanism, so the app itself becomes the equivalent of a local MCP server that the platform agent can call without a network round-trip."
  - q: "Do AppFunctions replace App Actions and App Intents?"
    a: "They're the evolution of that lineage. App Actions and shortcuts were built around fixed built-in intents; AppFunctions let you declare arbitrary typed functions with schemas, which is far more flexible for agentic use cases where the assistant composes multiple calls."
---

Agents are moving on-device, and the interesting question for app developers isn't "which model" — it's "how does an assistant actually *do* something in my app?" On Android the answer is increasingly **AppFunctions**: typed, annotated functions you expose so the system's agent (Gemini) can discover and call them with real arguments. If you've built an [MCP server](https://blog.michaelsam94.com/building-an-mcp-server-practical-guide/), the mental model transfers directly — your app becomes the local, on-device equivalent, letting an agent invoke capabilities without scraping your UI or making a network hop.

I've been wiring apps into assistant flows since the App Actions days, and AppFunctions is the first version of this that feels built for real agents rather than a fixed catalog of voice commands. Here's how it fits together and how to expose functionality without opening a security hole.

## From App Actions to AppFunctions

The old model — built-in intents, shortcuts, App Actions — worked by mapping user phrases to a fixed set of system-defined intents. It was rigid: if Google hadn't defined an intent for your domain, you were stuck bending your feature into "ORDER_MENU_ITEM" or similar. That doesn't scale to agents that need to compose arbitrary steps.

AppFunctions flips it. You declare functions with schemas — inputs, outputs, descriptions — and the platform indexes them so an on-device agent can plan over them. The shift is from "here are the phrases I recognize" to "here are the typed capabilities I offer, you figure out when to use them." That's exactly the [structured outputs and function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/) pattern, moved on-device and into the OS.

## Declaring an AppFunction

The API centers on the `@AppFunction` annotation over a suspend function. The parameters and return type become the schema the agent sees:

```kotlin
class ChargingFunctions(private val repo: ChargeRepository) {

    @AppFunction(
        description = "Start a charging session at a given charger for the signed-in user."
    )
    suspend fun startCharge(
        @AppFunctionParam(description = "Charger ID from a nearby list")
        chargerId: String,
        @AppFunctionParam(description = "Target charge percent, 50-100")
        targetPercent: Int = 80,
    ): ChargeSession {
        require(targetPercent in 50..100) { "targetPercent out of range" }
        return repo.startSession(chargerId, targetPercent)
    }
}
```

The compiler generates the metadata that registers this with the system's function index. The agent can now say, in effect, "the user asked to charge to 90% at the charger they're looking at" and produce a concrete `startCharge("CHG-4821", 90)` call. Rich return types get serialized into a schema too, so the agent can chain — call `findNearbyChargers`, pick one, then `startCharge`.

## Why on-device matters here

Running this locally isn't just a latency win, though a call that never leaves the device does feel instant. The bigger deal is privacy and availability. The arguments the agent extracts — a receipt query, a charge target, a message body — stay on the phone. That aligns with the broader push toward [on-device AI for privacy](https://blog.michaelsam94.com/on-device-ai-for-privacy/) and pairs naturally with [Gemini Nano](https://blog.michaelsam94.com/on-device-ai-android-gemini-nano/) doing the reasoning. No server means the capability works on a plane, and it means you're not shipping user intent to a backend just to open a screen.

## Treat every function like a public API endpoint

This is where I get insistent, because it's the part that bites teams. An AppFunction is a **remotely-triggerable entry point into your app**. The agent calling it is trusted-ish, but the *arguments* originate from natural language the user (or a shared context) supplied. Guard accordingly:

- **Validate every argument** as if it came from an untrusted client. `require`/`check` on ranges, IDs, and enums. The example above rejects out-of-range percents before touching the repo.
- **Enforce auth and ownership** inside the function. Never assume the agent checked that the user owns `chargerId` — verify it against the signed-in session.
- **Confirm destructive or costly actions.** Starting a paid charge, sending money, deleting data — return a state that requires an explicit user confirmation step rather than executing silently.
- **Mind prompt injection.** If any argument is derived from content the app itself displays (a message, a web page), you're one hop from [prompt-injection risk](https://blog.michaelsam94.com/prompt-injection-agent-security/). Sanitize and constrain.

A quick checklist I run before shipping any function:

| Check | Why |
| --- | --- |
| Argument validation | Args come from an LLM's interpretation, not your UI |
| Ownership/auth enforced in-function | The agent isn't your authorization layer |
| Idempotency on writes | The agent may retry; don't double-charge |
| Confirmation for side effects | Users must approve money/data actions |
| Minimal surface | Only expose functions you'd expose as an API |

## Designing functions agents can actually use

The difference between a function that gets called correctly and one that confuses the planner is mostly in the descriptions and the granularity. Write descriptions the way you'd write API docs for a junior engineer: say what it does, what the arguments mean, and any constraints. Keep functions single-purpose — `findNearbyChargers` and `startCharge` compose better than one mega-function with a mode flag. And return structured, self-describing results so the agent can decide the next step without guessing.

The reliability lessons from server-side agents apply directly here; the same discipline behind [building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/) — narrow tools, strict schemas, idempotent writes — is what makes on-device function calling dependable.

AppFunctions is early, and the API surface is still settling, but the direction is clear: the apps that get invoked by the phone's agent will be the ones that exposed clean, safe, well-described functions. That's a design problem more than an AI problem, and it's squarely in the wheelhouse of engineers who already think in terms of APIs and contracts.

## AppFunctions schema versioning

On-device MCP surfaces require stable JSON schema for function params — breaking change needs new function id, not in-place edit. Google Play validates function declarations at upload; invalid schema blocks release.

## Permission bridge to sensitive APIs

Functions calling SMS or call log need runtime permission at invocation time, not only at install — return structured error to host agent when permission denied.

## Appfunctions On Device Mcp Supplement 0 on Samsung and Pixel divergence

Exercise appfunctions on device mcp supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching appfunctions; regressions above 8% block release for `android-appfunctions-on-device-mcp-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Appfunctions On Device Mcp Supplement 0" should map to a single runbook section with known workarounds.

## Mcp regression gates for Play Vitals

Before promoting `android-appfunctions-on-device-mcp-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [App Functions documentation](https://developer.android.com/guide/app-functions)
- [App Actions and shortcuts](https://developer.android.com/guide/app-actions/overview)
- [Gemini Nano and AICore](https://developer.android.com/ai/gemini-nano)
- [Android developers blog](https://android-developers.googleblog.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [App Intents design guidance](https://developer.android.com/design/ui/mobile)

*Making an Android app assistant-ready? [Reach out](https://michaelsam94.com/) — happy to review your function surface.*
