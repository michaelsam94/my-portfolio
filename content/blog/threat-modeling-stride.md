---
title: "Threat Modeling with STRIDE for Product Teams"
slug: "threat-modeling-stride"
description: "A practical guide to threat modeling with STRIDE: mapping data flows, walking the six threat categories, and running lightweight security design reviews product teams keep doing."
datePublished: "2026-01-09"
dateModified: "2026-01-09"
tags: ["Security", "Architecture", "DevSecOps"]
keywords: "threat modeling, STRIDE, security design, attack surface, data flow diagram, security review"
faq:
  - q: "What is threat modeling with STRIDE?"
    a: "Threat modeling is the practice of systematically finding what could go wrong with a system's security before you build it, and STRIDE is a framework that structures that search into six categories: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, and Elevation of privilege. You diagram how data flows through your system, then walk each element against those six categories asking 'how could this be attacked?' It turns a vague 'is this secure?' into a concrete checklist tied to your actual design."
  - q: "When should a team do threat modeling?"
    a: "At design time, before code is written, when changing a design is cheap — that's the whole point of catching threats on a whiteboard instead of in production. Revisit the model when the architecture changes meaningfully: a new trust boundary, a new data store, a new external integration, or a new class of user. Threat modeling every tiny change is wasteful; doing it for significant designs and boundary changes is where the value concentrates."
  - q: "Do you need a security expert to run STRIDE?"
    a: "No, and that's STRIDE's biggest strength. The six categories give a non-specialist team enough structure to find the majority of design flaws on their own. A security expert adds depth and catches subtler issues, but a product team that draws a data flow diagram and honestly walks STRIDE will surface far more than a team that does nothing. The framework democratizes threat modeling rather than gatekeeping it."
---

Most security bugs aren't clever — they're obvious in hindsight, missed because nobody stopped to ask "how could someone abuse this?" before shipping. Threat modeling with STRIDE is the structured version of asking that question at design time. You draw how data moves through your system, then walk each piece against six categories of attack — Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege — and write down what could go wrong while the design is still just lines on a whiteboard and cheap to change.

I've run this exercise with teams who had zero security specialists, and it consistently surfaces real issues that would otherwise have shipped. The value isn't in producing a perfect document; it's in the conversation that forces engineers to look at their design through an attacker's eyes. Here's how to run it so the team actually keeps doing it.

## Start with a data flow diagram, not a threat list

STRIDE only works if you first understand what you're protecting. Before naming any threat, sketch a data flow diagram (DFD) of the feature: the **external entities** (users, third-party services), the **processes** (your services, functions), the **data stores** (databases, caches, files), and the **data flows** between them. Then draw the **trust boundaries** — the lines where data crosses from a less-trusted zone to a more-trusted one (the internet to your API, your app to the database, one microservice to another).

Those trust boundaries are where threats concentrate. Any flow crossing one deserves scrutiny; a flow entirely within a single trust zone usually needs less. Keep the diagram at the whiteboard level — boxes, arrows, and boundary lines. If it takes more than 30 minutes to draw, you're modeling at too fine a grain for a first pass.

## The six categories, and the property each protects

The elegance of STRIDE is that each threat maps to a security property you want, so the framework doubles as a checklist of controls. This is the reference I put on the wall:

| Threat | Violates | Ask yourself |
|---|---|---|
| **S**poofing | Authentication | Can someone pretend to be another user or service? |
| **T**ampering | Integrity | Can data be modified in transit or at rest? |
| **R**epudiation | Non-repudiation | Can someone deny an action with no evidence? |
| **I**nformation disclosure | Confidentiality | Can data leak to someone unauthorized? |
| **D**enial of service | Availability | Can someone make it unavailable? |
| **E**levation of privilege | Authorization | Can someone gain rights they shouldn't have? |

You walk each element of the diagram against the relevant categories. A data flow crossing the internet boundary invites Spoofing (who's really calling?), Tampering (can they alter the payload?), and Information disclosure (is it encrypted?). A data store invites Tampering and Information disclosure. A process that performs privileged actions invites Elevation of privilege. You don't apply all six to everything — you apply the ones that fit each element type.

## Walking it in practice

Take a concrete example: a mobile app calling a payments API that writes to a database. Walk the internet-facing flow first, because that's the highest-value trust boundary:

- **Spoofing** — Can an attacker impersonate a legitimate user or the app itself? This is where you decide the flow needs strong auth like [OAuth 2.0 PKCE for mobile apps](https://blog.michaelsam94.com/oauth-pkce-mobile/) rather than a guessable API key.
- **Tampering** — Can the request body be altered? You need TLS in transit and server-side validation; never trust the client to enforce amounts or prices.
- **Repudiation** — If a user disputes a charge, do you have a tamper-evident audit log proving what happened?
- **Information disclosure** — Are card details or tokens exposed in logs, error messages, or over an unencrypted channel?
- **Denial of service** — Can someone hammer the endpoint and exhaust it? You need rate limiting and quotas.
- **Elevation of privilege** — Can a normal user hit an admin endpoint or manipulate an ID to act on another user's account (IDOR)?

That last one — object-level authorization — is the single most common real flaw I find in these sessions. Teams authenticate the user correctly and then forget to check that *this* user is allowed to touch *that* resource.

## Keep it lightweight or it dies

The failure mode of threat modeling isn't doing it wrong — it's doing it once, producing a 40-page document, and never doing it again. Heavy process kills the practice. What survives contact with real product teams:

- **Timebox it.** A 60–90 minute session per significant feature, not a multi-day audit.
- **Do it at design time.** The whole point is catching threats when changing the design is cheap. Threat modeling after launch is just an incident post-mortem waiting to happen.
- **Capture threats as work items.** Each accepted threat becomes a ticket with a mitigation or an explicit, signed-off "we accept this risk." A threat with no owner is a threat you'll forget.
- **Right-size the trigger.** New trust boundary, new data store, new external integration, new user class → model it. Renaming a field → don't.

Recording the *decisions*, including risks you consciously accept, matters as much as finding threats. A documented "we accept low-severity DoS on this internal endpoint" is a legitimate engineering choice; an undocumented gap is negligence.

## Where STRIDE fits in the bigger picture

STRIDE finds design-level threats; it doesn't replace the rest of your security program. It pairs with a "shift left" philosophy where security is a design input, not a gate at the end — the mindset laid out in [DevSecOps and shifting security left](https://blog.michaelsam94.com/devsecops-shift-left/). The threats you identify also inform architecture: recurring Spoofing and Elevation-of-privilege findings are usually a sign you should adopt stronger identity foundations, which for client apps points toward [zero-trust mobile architecture](https://blog.michaelsam94.com/zero-trust-mobile-apps/) and never trusting the client or network by default.

My honest take after running dozens of these: STRIDE's limitation is that it's design-focused and won't catch implementation bugs — a buffer overflow or an injection flaw lives below its abstraction level, so you still need code review, SAST, and testing. And it's only as good as the honesty in the room; a team that hand-waves "nobody would do that" gets a useless model. But as a repeatable way to get non-specialists thinking like attackers before they write code, nothing else I've used comes close for the effort involved. Draw the diagram, walk the six letters, write down what you find, and fix or consciously accept each one. That loop, done regularly, prevents more incidents than any tool you can buy.

## Resources

- [Microsoft — threat modeling and STRIDE](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)
- [OWASP — threat modeling process](https://owasp.org/www-community/Threat_Modeling_Process)
- [OWASP Threat Dragon (modeling tool)](https://owasp.org/www-project-threat-dragon/)
- [The Threat Modeling Manifesto](https://www.threatmodelingmanifesto.org/)
- [NIST SP 800-154 — data-centric threat modeling (draft)](https://csrc.nist.gov/pubs/sp/800/154/ipd)
- [CISA — secure by design](https://www.cisa.gov/securebydesign)
