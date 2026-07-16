---
title: "Compose for Web with Kotlin/Wasm"
slug: "kotlin-wasm-compose-web"
description: "Compose Multiplatform for web on Kotlin/Wasm: how it renders, what it's good for today, the download-size and interop tradeoffs, and when to choose it."
datePublished: "2024-09-26"
dateModified: "2024-09-26"
tags: ["Kotlin", "Jetpack Compose", "Kotlin/Wasm", "Web"]
keywords: "Compose for Web, Kotlin Wasm, Compose Multiplatform web, WasmGC, Compose HTML, kotlin wasm browser"
faq:
  - q: "How does Compose for Web on Kotlin/Wasm render the UI?"
    a: "It renders onto an HTML canvas using Skia, the same rendering engine used on Android and desktop, so the UI is pixel-identical across targets rather than mapped to DOM elements. That means your Compose code — layouts, animations, custom drawing — runs unchanged in the browser. The tradeoff is that the app is a canvas surface, not semantic HTML, which has accessibility and SEO implications."
  - q: "Is Compose for Web with Kotlin/Wasm production ready?"
    a: "It has matured a lot and is stable enough for internal tools, dashboards, and apps where sharing UI with Android and desktop outweighs web-native concerns. For public marketing pages or content sites where SEO and accessibility are critical, DOM-based approaches are still the safer choice. Evaluate it per use case rather than as an all-or-nothing decision."
  - q: "What is the difference between Compose HTML and Compose for Web on Wasm?"
    a: "Compose HTML maps Compose-style code to actual DOM elements, giving you semantic HTML and CSS control. Compose for Web on Kotlin/Wasm renders your shared Compose UI to a canvas via Skia for pixel-perfect parity with other platforms. They solve different problems: Compose HTML for web-native pages, canvas-based Compose for sharing the exact app UI everywhere."
---

Compose for Web on Kotlin/Wasm lets you take the exact Jetpack Compose UI you wrote for Android or desktop and run it in a browser — not a re-skinned web version, the *same* code rendering the *same* pixels. It does this by compiling to WebAssembly and drawing the UI onto an HTML canvas with Skia, the same graphics engine Compose uses on Android and desktop. That's the headline feature and also the source of every tradeoff worth understanding before you commit.

I'll be direct about what it's genuinely good at and where it isn't the right tool, because "share your UI everywhere" is exciting enough that people skip the part where a canvas isn't a web page.

## Canvas rendering, not DOM

The defining architectural choice: Compose for Web renders to a `<canvas>`, not to DOM elements. Your `Column`, `LazyColumn`, animations, gestures, and custom `Canvas` drawing all run through Skia and paint onto that single canvas surface. The browser sees one element; your entire app lives inside it.

The upside is real and rare: **pixel-perfect parity** with Android and desktop. There's no "web looks slightly different" bug class, because it's literally the same renderer. Complex custom UI, charts, animations, and drawing that would be a slog to reproduce in DOM/CSS just work, because they're the code you already wrote. If you've built a rich Compose app and want it on the web without a rewrite, this is the shortest path.

The downside is equally real: **it's not semantic HTML.** No `<h1>` for search engines, no native form fields, and accessibility must be bridged rather than inherited from the platform. Which leads to the fork in the road.

## Two different "Compose on web" things

People conflate two distinct technologies, and picking the wrong one wastes weeks.

| | Compose for Web (Kotlin/Wasm) | Compose HTML |
| --- | --- | --- |
| Renders to | Canvas via Skia | Real DOM elements |
| UI parity with Android/desktop | Pixel-identical | None — it's web-native |
| SEO / semantic HTML | Weak (canvas) | Strong |
| Reuses your existing Compose UI | Yes, directly | No — different API |
| Best for | Sharing the exact app UI | Web-native pages/sites |

If your goal is "my Android app, in a browser," you want canvas-based Compose for Web on Wasm. If your goal is "a website that happens to be written in Kotlin," you want Compose HTML. They're not competitors; they're answers to different questions.

## Why Wasm, and what WasmGC changed

Kotlin/Wasm targets WebAssembly with garbage collection (**WasmGC**), a browser feature that lets managed languages like Kotlin run efficiently without shipping their own GC in the bundle. This matters for two reasons. First, performance: Wasm executes near-native, so Compose's rendering and your logic run fast. Second, it's why modern browsers are required — WasmGC support is what makes the output small and quick enough to be practical, and it's now broadly available in current Chrome, Firefox, and Safari.

Download size is the honest sore point. A canvas-based Compose app ships the Skia renderer and the Compose runtime, so the initial payload is larger than a hand-written web page. It has shrunk considerably with WasmGC and optimization, but if first-load size on a cold cache is your top constraint, factor it in and measure. For an internal dashboard behind a login, nobody cares; for a public landing page, they might.

## Interop with the browser

You're still in a browser, so you'll occasionally need the DOM, browser APIs, or JS libraries. Kotlin/Wasm provides interop for this, conceptually similar to Kotlin/JS `external` declarations covered in [Kotlin/JS interop fundamentals](https://blog.michaelsam94.com/kotlin-js-interop-basics/): you declare the browser API you need and call it. Common cases are reading the URL, browser storage, or handing off to a native `<input>` for something the canvas can't do well. Keep this interop confined to a thin layer, the same discipline as any platform boundary.

## Where I'd actually use it today

My pragmatic guidance, from shipping shared-UI apps:

- **Great fit:** internal tools, admin dashboards, data-heavy apps, anything already built in Compose where you want a web presence without a second UI codebase. The parity and code reuse are worth the payload.
- **Reasonable fit:** consumer apps where you control the entry point (users click into an app, not a search result), and you're willing to invest in accessibility bridging.
- **Poor fit:** public marketing sites, blogs, content that must be indexed, or anything where SEO and semantic HTML are the point. Use Compose HTML or a DOM framework there.

The reuse story is the same one that makes Compose compelling across form factors generally, echoing the [adaptive layout thinking](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) that already spans phones, foldables, and tablets — now extended to the browser.

## What I'd take away

Compose for Web on Kotlin/Wasm is a genuine "write once, render everywhere" story for Compose UI, achieved by drawing to a canvas with Skia so the web build is pixel-identical to Android and desktop. That's its superpower and its constraint: you get perfect parity and full code reuse, but a canvas isn't semantic HTML, so SEO and accessibility need deliberate work. Choose it for apps where sharing the exact UI matters — internal tools, dashboards, rich interactive apps — and reach for Compose HTML when you actually need a web-native page. Match the tool to whether you're shipping an *app* or a *website*, and it's a remarkably productive way to reach the browser from a Kotlin codebase.

## Resources

- [Compose Multiplatform for web](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-and-jetpack-compose.html)
- [Kotlin/Wasm overview](https://kotlinlang.org/docs/wasm-overview.html)
- [WebAssembly Garbage Collection (WasmGC) proposal](https://github.com/WebAssembly/gc)
- [Skia graphics library](https://skia.org/)
- [web.dev — WebAssembly](https://web.dev/explore/webassembly)
