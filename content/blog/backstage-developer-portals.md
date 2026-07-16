---
title: "Developer Portals with Backstage"
slug: "backstage-developer-portals"
description: "Building developer portals with Backstage: the software catalog, golden-path scaffolder templates, TechDocs, and an honest look at the operational cost of running it."
datePublished: "2026-04-16"
dateModified: "2026-04-16"
tags: ["Platform Engineering", "DevOps", "Developer Experience"]
keywords: "Backstage, developer portal, software catalog, golden paths, scaffolder, internal developer platform"
faq:
  - q: "What is Backstage?"
    a: "Backstage is an open-source developer portal framework, originally built at Spotify and now a CNCF project. It provides a single UI where engineers can find all their services in a software catalog, create new projects from standardized templates, read documentation, and access plugins for CI, cloud, and monitoring — reducing the scavenger hunt of finding tools and information."
  - q: "Is Backstage a platform or a framework?"
    a: "It's a framework, and that distinction matters a lot. Backstage doesn't come as a ready-to-run product; you build and customize your own portal on top of it, writing configuration and often TypeScript plugin code. Teams that expect a turnkey product are frequently surprised by how much assembly it requires."
  - q: "What is the software catalog in Backstage?"
    a: "The software catalog is Backstage's inventory of everything your organization runs — services, libraries, APIs, resources, and the teams that own them — described in YAML files (catalog-info.yaml) that live alongside the code. It's the backbone of the portal, giving every entity an owner, dependencies, and links to its docs, pipelines, and dashboards."
---

Ask a new engineer at most companies to deploy their first service and watch them spend a week just finding which of forty tools they need and who owns what. A developer portal built on [Backstage](https://backstage.io/) attacks that specific waste: it's a single pane of glass where every service, its owner, its docs, its pipelines, and its dashboards are one search away, and where creating a new, production-ready service is a form instead of a two-week odyssey. Backstage — open-sourced by Spotify, now a CNCF project — is the de facto framework for building one.

I'll say up front that Backstage is powerful and genuinely improves developer experience when done well, and also that it's more work to run than the demos suggest. Both are true. Let's look at what it gives you and what it costs.

## The software catalog is the foundation

Everything in Backstage hangs off the software catalog — a live inventory of your systems. Each entity (a service, library, API, or resource) is described in a `catalog-info.yaml` that lives in the repo it describes:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payments-api
  description: Handles payment authorization and capture
  annotations:
    github.com/project-slug: acme/payments-api
    backstage.io/techdocs-ref: dir:.
spec:
  type: service
  lifecycle: production
  owner: team-payments
  system: checkout
  dependsOn:
    - resource:default/payments-db
    - component:default/fraud-check
```

Backstage discovers these files, builds a graph of what depends on what, and gives every entity a page with its owner, its dependencies, and links to the tools that operate it. The moment this catalog is populated, "who owns this service and what does it talk to?" becomes a search instead of a Slack archaeology expedition. Ownership being a required field is the quiet superpower here — it makes accountability structural rather than tribal.

## Golden paths through the scaffolder

The catalog answers "what exists." The scaffolder answers "how do I make a new one correctly." Scaffolder templates are parameterized generators: an engineer fills in a form (service name, team, language), and Backstage creates the repo, wires CI/CD, registers the service in the catalog, and applies your standards — all in one action.

This is where the term *golden path* earns its keep. Instead of a wiki page titled "How to create a new Go service (please follow all 23 steps)," you encode those 23 steps into a template. The engineer gets a working, compliant service in minutes, and it's compliant *by construction* rather than by hoping everyone read the doc. A template's steps look roughly like this:

```yaml
steps:
  - id: fetch
    name: Fetch skeleton
    action: fetch:template
    input:
      url: ./skeleton
      values:
        name: ${{ parameters.name }}
        owner: ${{ parameters.owner }}
  - id: publish
    name: Create repository
    action: publish:github
    input:
      repoUrl: ${{ parameters.repoUrl }}
  - id: register
    name: Register in catalog
    action: catalog:register
    input:
      repoContentsUrl: ${{ steps.publish.output.repoContentsUrl }}
      catalogInfoPath: /catalog-info.yaml
```

Golden paths are the heart of platform work — they turn best practices into the path of least resistance, which is the only way best practices actually get followed at scale. This is precisely the value an [internal developer platform](https://blog.michaelsam94.com/platform-engineering-internal-developer-platform/) is supposed to deliver, and Backstage is the most common front door to one.

## TechDocs and discoverability

Backstage's TechDocs renders Markdown docs (via MkDocs) that live in the same repo as the code, surfaced right on the service's catalog page. The win isn't the rendering — it's that docs stop being a separate, rotting wiki and become versioned artifacts next to the thing they describe. Docs that live with the code get updated with the code far more often than docs that live in Confluence.

Search ties it together: one search box across services, docs, APIs, and plugins. When it works, the portal becomes the honest answer to "where do I start" for any task, which is exactly the friction it exists to remove.

## The plugin ecosystem

Backstage's extensibility is its real differentiator. Plugins embed CI status, Kubernetes resources, cloud costs, PagerDuty on-call, and dozens of other tools directly into service pages. Instead of context-switching across ten dashboards, an engineer sees the operational picture for their service in one place. There's a large open-source plugin ecosystem, and you can write your own in TypeScript for internal systems.

That extensibility is also the catch, which brings me to the honest part.

## The cost nobody puts on the slide

Backstage is a framework, not a product. You don't install it and get a portal; you *build* a portal with it. That means:

- **You run a Node.js/React application** — hosting, upgrades, a database (PostgreSQL), auth integration. It's real software you now operate.
- **Upgrades are ongoing work.** Backstage moves fast; staying current is a recurring tax, not a one-time setup.
- **Customization needs TypeScript.** Non-trivial plugins and theming require frontend engineering skill on your platform team.
- **Adoption isn't automatic.** A portal nobody populates or visits is dead weight. You have to drive the catalog to completeness and make the golden paths genuinely better than the old way.

I've seen Backstage rollouts stall precisely because a team treated it as "install and done." Budget for a dedicated owner. The payoff — measurable in onboarding time and in [DORA delivery metrics](https://blog.michaelsam94.com/dora-metrics-that-matter/) once golden paths reduce lead time — is real, but it's earned through sustained investment, not a weekend spike.

## Should you use it?

If you have enough services that discovery and standardization are real problems — say, dozens of services and multiple teams — and you can commit a small platform team to owning it, Backstage is an excellent foundation and hard to beat as open source. If you're a handful of services, a well-maintained README index and good CI templates will get you most of the value for a fraction of the operational cost. Match the tool to the scale of the problem; a developer portal solves a coordination problem, and small orgs don't have that problem yet.

## Resources

- [Backstage — official site](https://backstage.io/)
- [Backstage documentation](https://backstage.io/docs/overview/what-is-backstage)
- [Backstage (GitHub, CNCF)](https://github.com/backstage/backstage)
- [Software Catalog concepts](https://backstage.io/docs/features/software-catalog/)
- [Software Templates (Scaffolder)](https://backstage.io/docs/features/software-templates/)
- [CNCF — Backstage project](https://www.cncf.io/projects/backstage/)
