# Graph Report - my-portfolio  (2026-06-19)

## Corpus Check
- 88 files · ~78,772 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 703 nodes · 786 edges · 66 communities (53 shown, 13 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `89a1e6e4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 65|Community 65]]

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 20 edges
2. `compilerOptions` - 18 edges
3. `main()` - 16 edges
4. `Hi there, I'm Michael Samuel Naeem! 👋` - 12 edges
5. `Hi there, I'm Michael Samuel Naeem! 👋` - 12 edges
6. `workSlug()` - 10 edges
7. `🛠️ Technical Skills` - 10 edges
8. `🎨 Featured Projects & Apps` - 10 edges
9. `renderPost()` - 9 edges
10. `renderWork()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `workSlug()`  [EXTRACTED]
  scripts/fetch-readmes.mjs → src/data/portfolio.ts
- `workJsonLd()` --calls--> `workSlug()`  [EXTRACTED]
  scripts/build-blog.mjs → src/data/portfolio.ts
- `renderWork()` --calls--> `workSlug()`  [EXTRACTED]
  scripts/build-blog.mjs → src/data/portfolio.ts
- `main()` --calls--> `workSlug()`  [EXTRACTED]
  scripts/build-blog.mjs → src/data/portfolio.ts
- `main()` --calls--> `enrichVscodePages()`  [INFERRED]
  scripts/build-blog.mjs → scripts/vscode-longform.mjs

## Import Cycles
- None detected.

## Communities (66 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (27): Contact(), currentUrl(), links, shareVia(), LinkedInProfileBadge(), linkedinVanity(), links, featuredApps (+19 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (41): workSlug(), APP_FAQ, autoFaq(), BLOG_DIST, buildFeed(), buildLlms(), buildLlmsFull(), buildSitemap() (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (40): 🎯 About Me, AI & Emerging Tech, Android Developer · **EME International**, Android Developer · **Pan Arab Media**, 💫 *“Architecting scalable mobile systems—from smart cities and robots to EV grids and fintech at scale.”*, Architecture & Patterns, Async & DI, 💳 Banking & wallets (samples of shipped work) (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (37): 🎯 About Me, 📁 About this repository, AI & Emerging Tech, Android Developer · **EME International**, Android Developer · **Pan Arab Media**, 💫 *“Architecting scalable mobile systems—from smart cities and robots to EV grids and fintech at scale.”*, Architecture & Patterns, Async & DI (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (30): dependencies, framer-motion, react, react-dom, devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (23): API Reference, Architecture Overview, Build, Install, And Launch, Components And Layers, Configuration, Coverage, Data Flow, Debug APK (+15 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (13): prompts, About, Certifications, Citations, Contact, Experience, IdleWindow, Impact (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (18): buildEmptyContributionDays(), ContributionDay, ContributionsFunctionResponse, ContributionTooltip, fetchContributionDetails(), fetchOpenSourceData(), fetchStaticContributions(), GitHubCommit (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (20): Android Debug Builds, Android Release Builds, API Reference, Architecture Overview, Build And Install The Android App, Components, Configuration, Deployment (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (18): Android, API Reference, Architecture Overview, Build A Release APK, Components And Layers, Configuration, Deployment, Design Patterns (+10 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (18): API Reference, Architecture Overview, Build And Run The App, Components And Layers, Configuration, Debug Build, Deployment, Design Patterns (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (16): Android Debug Builds, Android Release Builds, API Reference, Architecture Overview, Components, Configuration, Data Flow, Deployment (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (15): API Reference, Architecture Overview, Configuration, Debug Deployment, Deployment, Generate Play Store Assets, Key Features, Privacy Policy Site (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (15): API Reference, Architecture Overview, Build and Run, Components, Configuration, Data Flow, Deployment, Design Patterns (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (14): Android App, API Reference, Architecture Overview, Build and Run the Android App, Build Store Assets Into a Release Workflow, Configuration, Deployment, Key Features (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.13
Nodes (14): Architecture, Budget, Categories, Data flow (single source of truth), Home (Dashboard), Insights (Analytics), Ledger, Libraries (+6 more)

### Community 18 - "Community 18"
Cohesion: 0.26
Nodes (12): addOneYear(), buildContributionDays(), dateOnly(), fetchJson(), githubGraphql(), handler(), headers, loadPublicContributionHistory() (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.28
Nodes (12): APP_REPO, EXTENSIONS, fetchFile(), fetchReadme(), fromListing(), isBoilerplate(), main(), neutralizeRelativeLinks() (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.38
Nodes (8): ThemeToggle(), useTheme(), applyTheme(), getStoredTheme(), getSystemTheme(), initTheme(), resolveTheme(), Theme

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (9): appsHubArticle(), blogHubArticle(), enrichVscodePages(), extensionArticle(), EXTENSIONS, hubArticle(), injectBeforeMainClose(), paragraphs() (+1 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (9): Camera array — optical tracking, From geometry to broadcast: the output side, Fusion: aligning two independent clocks, Performance envelope: what "real-time" actually means here, Sensing layer: two independent data sources, fused, The broader pattern: convergence, not novelty, The instrumented ball — high-frequency IMU, The problem, stated precisely (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (9): API Reference, Architecture Overview, Configuration, Deployment, Key Features, Project Overview, Tech Stack & Libraries, Testing (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.25
Nodes (7): Interop is a feature, not a failure, Recomposition is the whole game, `remember` the right thing, for the right lifetime, Stability: the silent recomposition tax, State hoisting is an architecture decision, not a style, The short version, What actually improved

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (7): Contact, Features, Permissions, Play Store assets, Project layout, Tech stack, Tests

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (7): Derived state belongs in providers, not widgets, Keep rebuilds surgical with `select`, One notifier per domain, not per screen, Testing is the payoff, Treating connectivity as state, not an exception, What I'd tell a team adopting Riverpod, Why Riverpod over the alternatives

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): Designing for the network that fails, Idempotency: the rule that prevented disasters, Layered architecture, Sub-100ms P2P local control, Takeaways for any real-time IoT platform, The shape of the problem, Why it shipped clean

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (6): Features, Permissions, Play Store assets, Privacy, Tech stack, Tests

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (6): Current Status, Next Actions, Official Wikipedia References, Source Quality Tiers, What Wikipedia Needs, Wikipedia Notability Checklist

### Community 30 - "Community 30"
Cohesion: 0.33
Nodes (5): Architecture, CI, Permissions, Run instrumented tests, Run unit tests

### Community 31 - "Community 31"
Cohesion: 0.33
Nodes (5): Features, Play Store assets, Privacy, Screenshots, Tech stack

### Community 32 - "Community 32"
Cohesion: 0.33
Nodes (5): App Details, Features, Play Store Assets, Release Notes, Secrets

### Community 33 - "Community 33"
Cohesion: 0.33
Nodes (5): Features, Privacy, Screenshots, Tech stack, Tests

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (5): Show your README on your GitHub **profile** (like [EslamFareed](https://github.com/EslamFareed)), Step 1 — Create the repository on GitHub, Step 2 — Add your profile `README.md`, Step 3 — Confirm on your profile, What stays where

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (5): accountCreatedAt, contributionDays, generatedAt, source, totalContributions

### Community 36 - "Community 36"
Cohesion: 0.40
Nodes (4): Features, Play Store assets, Project layout, Tech stack

### Community 37 - "Community 37"
Cohesion: 0.40
Nodes (4): Commands, Features, Privacy and limitations, Settings

### Community 38 - "Community 38"
Cohesion: 0.40
Nodes (4): Commands, Features, Settings, Usage

### Community 40 - "Community 40"
Cohesion: 0.50
Nodes (3): Core Features, Overview, Recent updates

### Community 41 - "Community 41"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 42 - "Community 42"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 43 - "Community 43"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 44 - "Community 44"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 45 - "Community 45"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (3): Extension Settings, Features, Publish

### Community 47 - "Community 47"
Cohesion: 0.50
Nodes (3): 1. Create the repository on GitHub, 2. Push your code, Publish this project to GitHub

## Knowledge Gaps
- **444 isolated node(s):** `tsBuildInfoFile`, `target`, `lib`, `module`, `types` (+439 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 1` to `Community 21`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Why does `workSlug()` connect `Community 1` to `Community 0`, `Community 19`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **What connects `tsBuildInfoFile`, `target`, `lib` to the rest of the system?**
  _444 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05137844611528822 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.11382113821138211 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.04878048780487805 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.05263157894736842 - nodes in this community are weakly interconnected._