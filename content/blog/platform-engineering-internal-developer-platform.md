---
title: "Platform Engineering: Building an Internal Developer Platform"
seoTitle: "Building an Internal Developer Platform (IDP)"
slug: "platform-engineering-internal-developer-platform"
description: "What platform engineering really is, how to build an internal developer platform (IDP) with golden paths and self-service, and failure modes to avoid."
datePublished: "2026-05-22"
dateModified: "2026-05-22"
tags: ["Platform Engineering", "DevEx", "Infrastructure", "Backstage"]
keywords: "platform engineering, internal developer platform, IDP, self-service infrastructure, developer experience, Backstage"
faq:
  - q: "What is an internal developer platform (IDP)?"
    a: "An internal developer platform is a self-service layer that lets product engineers ship, run, and operate software without filing tickets to a central ops team. It packages infrastructure, CI/CD, and operational tooling behind golden paths so common tasks are one command or one click."
  - q: "Is platform engineering the same as DevOps?"
    a: "No. DevOps is a culture of shared responsibility between dev and ops. Platform engineering is a discipline that builds a product — the platform — to deliver on DevOps promises at scale, so every team does not reinvent pipelines and infrastructure themselves."
  - q: "Do we need Backstage to build an IDP?"
    a: "No. Backstage is a popular developer portal and a fine front door, but an IDP is defined by self-service golden paths, not by any single tool. Many teams start with templates, a CLI, and good defaults before adopting a portal."
---

Platform engineering is the practice of building an **internal developer platform** — a product, owned by a platform team, whose customers are your own engineers. Its job is to let product teams ship and operate software through self-service, without filing a ticket and waiting on a central ops group for every environment, pipeline, or database. When it works, a developer goes from "I need a new service" to a running, observable, secured service in minutes, along a paved "golden path." When it fails, you have built an expensive internal tool nobody uses.

I have seen both outcomes. The difference is almost always whether the platform was treated as a product or as a pile of scripts.

## Why this became a discipline

The "you build it, you run it" DevOps model was right, but it quietly pushed enormous cognitive load onto product engineers. To ship one service they were expected to know Kubernetes, Terraform, CI/CD YAML, secrets management, observability wiring, and a security checklist. That does not scale — every team reinvents the same plumbing, badly and inconsistently.

Platform engineering answers that by **abstracting the plumbing behind golden paths**. The platform team encodes the organization's best practice once, as reusable templates and self-service actions, so a product engineer gets a compliant, observable, secure service without becoming an infrastructure expert. The platform reduces cognitive load; it does not remove the underlying systems.

## What actually makes it a platform

A pile of Terraform modules is not an IDP. The properties that matter:

- **Self-service.** A developer can provision what they need without a human in the loop for common cases.
- **Golden paths, not golden cages.** The paved path is the easy default, but teams with genuine reason can step off it. Mandatory-only platforms breed shadow infrastructure.
- **Abstraction with escape hatches.** Hide Kubernetes for the 90% case; let the 10% who need raw access get it.
- **Product mindset.** It has an owner, a roadmap, users you interview, and metrics. Adoption is voluntary and earned.

## A golden path, concretely

Here is what "create a new service" should feel like — one command that scaffolds the repo, pipeline, infra, and observability from a vetted template:

```bash
# The platform CLI: one command, a compliant service in minutes
platform new service \
  --name payments-webhook \
  --template kotlin-ktor-service \
  --tier internal \
  --db postgres

# What it wires up behind the scenes:
#  - repo from template with CI/CD pipeline
#  - Terraform/OpenTofu module for a Postgres instance + secrets
#  - Kubernetes manifests with sane resource limits
#  - OpenTelemetry, dashboards, and default SLO alerts
#  - RBAC, image scanning, and SBOM generation in the pipeline
```

The developer writes business logic. The platform guarantees the service is built, deployed, observable, and secured the same way as every other service. That consistency is the payoff — incident response, cost control, and audits all get dramatically easier when services are shaped alike.

## Building blocks in 2026

You assemble an IDP from layers, most of them open standards:

| Concern | Common building blocks |
| --- | --- |
| Developer portal / catalog | Backstage, or a lightweight internal UI |
| Infrastructure provisioning | OpenTofu / Terraform, Crossplane |
| Orchestration | Kubernetes with an abstraction layer |
| CI/CD & GitOps | Argo CD or Flux, pipeline templates |
| Observability | OpenTelemetry, dashboards, SLO alerting |
| Templates / scaffolding | Backstage software templates, cookiecutters |

[Backstage](https://backstage.io/) is the best-known front door — a service catalog plus software templates — but do not confuse the portal with the platform. Plenty of effective IDPs start as a good CLI, a set of templates, and strong defaults, adding a portal only once the paved paths exist. The golden paths are the product; the portal is packaging.

## The failure modes I watch for

**Building infrastructure, calling it a platform.** If developers still file tickets and wait, you have automation, not self-service. The test is whether a developer can get to a running service alone.

**Golden cages.** Mandating the one path with no escape hatch pushes capable teams into workarounds and resentment. Make the paved road the *easiest* option, not the *only* one.

**No product owner.** A platform without a roadmap and user research ossifies. Treat internal engineers as customers: interview them, measure adoption, and track lead time and deployment frequency as your success metrics — the same [SLO and observability discipline](https://blog.michaelsam94.com/designing-for-observability-slos/) you would apply to any product.

**Over-abstracting too early.** Abstract the patterns that are genuinely common and stable. Wrapping something three teams do differently in a leaky abstraction is worse than leaving it exposed.

## Where to start

Do not boil the ocean. Find the single most painful, most repeated workflow — usually "stand up a new service" or "get a database" — and pave that one path end to end. Ship it, get real teams using it, measure whether lead time dropped, then pave the next path. An IDP grows by earning adoption one golden path at a time, not by a big-bang platform launch.

Platform engineering done well is invisible: developers just notice that shipping got easy and that everything runs the same way. Done poorly, it is a monument to good intentions. The dividing line is treating the platform as a product with real customers — your own engineers. Want help scoping a first golden path? [Get in touch](/#contact).

## Resources

- [Backstage developer portal](https://backstage.io/)
- [Team Topologies: platform teams](https://teamtopologies.com/)
- [CNCF Platforms White Paper](https://tag-app-delivery.cncf.io/whitepapers/platforms/)
- [Google Cloud: internal developer platforms](https://cloud.google.com/architecture)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)
- [OpenTelemetry documentation](https://opentelemetry.io/docs/)
