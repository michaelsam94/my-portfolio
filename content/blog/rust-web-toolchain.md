---
title: "Rust in the Web Toolchain"
slug: "rust-web-toolchain"
description: "Why Rust is quietly taking over JavaScript tooling: how Turbopack, oxc, SWC and friends deliver 10-100x faster builds, and what the Rust web toolchain means for your DX."
datePublished: "2026-06-20"
dateModified: "2026-06-20"
tags: ["Rust", "Web Tooling", "Build Tools", "Frontend"]
keywords: "Rust tooling, Turbopack, Rust web tools, Rust bundler, oxc, JavaScript tooling, SWC"
faq:
  - q: "Why is Rust being used for JavaScript tooling?"
    a: "JavaScript build tools written in JavaScript are limited by the single-threaded, garbage-collected nature of Node. Rewriting bundlers, transpilers, and linters in Rust gives true multithreading, no GC pauses, and native speed — often 10-100x faster — which matters enormously as codebases grow."
  - q: "What are the main Rust-based JavaScript tools?"
    a: "SWC (transpiler, used by Next.js), Turbopack (bundler from Vercel), oxc (a fast linter/parser/toolchain), Biome (formatter and linter), and Rolldown (a Rust bundler for Vite). Together they're replacing Babel, webpack, ESLint, and Prettier piece by piece."
  - q: "Do I need to know Rust to benefit from these tools?"
    a: "No. These tools are drop-in replacements you configure the same way as their JavaScript predecessors — you get the speed without writing any Rust. Knowing Rust only matters if you want to contribute to or extend the tools themselves."
---

There's a quiet rewrite happening under every JavaScript project, and most developers only notice it as "why did my build suddenly get fast." The tools that transpile, bundle, lint, and format your code — historically written in JavaScript — are being rebuilt in Rust, and the speedups aren't incremental. They're the kind of 10-100x that changes how it feels to work. The Rust web toolchain isn't a niche experiment anymore; it's shipping in Next.js, Vite, and the linters teams reach for by default.

I'm a mobile developer by trade, but I run enough web tooling that build times affect my day, and the shift has been dramatic enough to be worth explaining. Here's what's happening and why.

## Why JavaScript tools hit a wall

The core problem is structural. Node.js is single-threaded per process and garbage-collected. A bundler like webpack, doing enormous amounts of parsing, AST transformation, and graph work, is fighting the runtime the whole way: it can't easily use all your CPU cores, and it pauses for GC at inconvenient moments. For a small project this is invisible. For a large monorepo with tens of thousands of modules, it means cold builds measured in minutes and dev-server startup that has you reaching for coffee.

You can optimize JavaScript tooling only so far before the runtime itself is the ceiling. Rust removes that ceiling: real threads across all cores, no garbage collector, and native code without an interpreter in the way. Parsing and transforming ASTs — embarrassingly parallel work — is exactly what Rust is good at.

## The players, and what they replace

The migration is happening tool by tool, and it helps to know the map:

| Rust tool | Replaces | Role |
|---|---|---|
| SWC | Babel | Transpile/compile JS/TS |
| Turbopack | webpack | Bundler (Next.js) |
| Rolldown | Rollup (in Vite) | Bundler |
| oxc | ESLint/Babel parser | Linter, parser, toolchain |
| Biome | Prettier + ESLint | Formatter + linter |

SWC was the beachhead — Next.js swapped Babel for SWC years ago and most people never noticed except that compilation sped up. Turbopack is Vercel's from-scratch bundler, now the default dev bundler in recent Next.js and increasingly stable for production builds. On the Vite side, Rolldown is bringing a Rust bundler under a tool that already felt fast. And for linting/formatting, oxc and Biome are posting numbers that make ESLint-plus-Prettier feel archaic.

## The speed is real, and here's why it matters beyond bragging

The benchmarks (oxc's linter running dozens of times faster than ESLint, Turbopack's incremental updates in milliseconds) are impressive, but the *why it matters* is subtler than "fast is nice." Three real effects:

- **The dev feedback loop tightens.** When hot-module updates go from seconds to sub-100ms, you stay in flow instead of context-switching while you wait. The difference between 2s and 50ms isn't 40x, it's the difference between waiting and not.
- **CI gets cheaper and faster.** Build and lint steps are often the long pole in [fast CI/CD pipelines](https://blog.michaelsam94.com/fast-cicd-pipelines/). Cutting them 10x cuts both wall-clock time and the compute bill.
- **Big codebases stay viable.** The tools that fell over on large monorepos now handle them, which changes what architectures are practical.

That last point connects to why this matters for teams doing serious work: build performance is a scaling constraint, and Rust tooling pushes the constraint out.

## An architectural pattern worth noticing

The interesting thing to a builder is *how* these tools are structured, because it's a repeatable pattern: a fast Rust core with thin, ergonomic bindings for the JavaScript world. The heavy lifting — parsing, transforming — happens in Rust, exposed to Node through N-API bindings so you install and configure them like any npm package. You get native speed with a JavaScript-shaped API.

```jsonc
// A Biome config — you configure it like any JS tool; the engine is Rust
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "formatter": { "enabled": true, "indentStyle": "space" },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true }
  }
}
```

You never touch Rust. That's the point — the language choice is an implementation detail that shows up only as speed. This same "Rust core, friendly bindings" shape is why Rust is spreading into so many places, from web tooling to the [WASI runtime ecosystem](https://blog.michaelsam94.com/webassembly-beyond-browser-wasi/), where much of the tooling is Rust under the hood.

## The trade-offs and rough edges

It's not pure upside, and adoption deserves eyes open:

- **Maturity gap in the long tail.** ESLint's plugin ecosystem is vast; oxc and Biome cover the common rules extremely well but may not have every niche plugin your team relies on yet. Check your specific rules before switching.
- **Extensibility is harder.** Writing a custom transform or lint rule for a JavaScript tool meant writing JavaScript. Extending a Rust tool means Rust, or waiting for a plugin API. Some tools are building JS-friendly plugin systems; it's still evolving.
- **Subtle behavioral differences.** A different parser can, rarely, disagree on edge-case syntax or formatting. Migrations are usually smooth but not always bit-identical, so run the formatter across your codebase once and review the diff.

None of these are dealbreakers for most teams, but "just swap it in" occasionally has a tail of small surprises.

## What I'd do today

If you're on Next.js, you're already getting SWC and increasingly Turbopack — let it happen and enjoy the faster dev server. For linting and formatting, Biome is worth a serious trial: one tool replacing two, dramatically faster, with a sane default config. For Vite users, Rolldown is arriving under the hood. The pragmatic stance is to adopt these where they're drop-in and mature (transpile, format, lint) and watch the bundler space as Turbopack and Rolldown finish stabilizing production builds.

The meta-point: the JavaScript ecosystem outgrew tools written in JavaScript, and Rust turned out to be the right tool for building the tools. You don't have to learn Rust to benefit — you just have to notice that your builds got fast and let the change happen. If you want the broader context on Rust showing up in server-side and edge runtimes too, the [WebAssembly and WASI](https://blog.michaelsam94.com/webassembly-beyond-browser-wasi/) story is the other half of Rust's push into web infrastructure.

## Resources

- [Rust programming language](https://www.rust-lang.org/)
- [Turbopack documentation](https://turbo.build/pack/docs)
- [SWC — speedy web compiler](https://swc.rs/)
- [oxc — the JavaScript oxidation compiler](https://oxc.rs/)
- [Biome — toolchain for web projects](https://biomejs.dev/)
- [Rolldown — Rust bundler](https://rolldown.rs/)
