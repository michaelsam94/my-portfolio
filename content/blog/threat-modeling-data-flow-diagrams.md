---
title: "Threat Modeling with Data-Flow Diagrams"
slug: "threat-modeling-data-flow-diagrams"
description: "Threat modeling identifies security risks before code is written. Learn STRIDE analysis with data-flow diagrams to systematically find vulnerabilities in system design."
datePublished: "2026-01-30"
dateModified: "2026-01-30"
tags: ["Security", "Threat Modeling", "STRIDE", "Architecture"]
keywords: "threat modeling, data flow diagram security, STRIDE analysis, threat modeling process, security design review, Microsoft Threat Modeling Tool"
faq:
  - q: "When should threat modeling happen in the development lifecycle?"
    a: "Before implementation — when the architecture is designed but code isn't written yet. Changing a design diagram is cheap; retrofitting security into shipped code is expensive. Also re-run threat modeling when architecture changes significantly: new data flows, new third-party integrations, new trust boundaries. Annual reviews for stable systems catch drift from the original threat model."
  - q: "What is STRIDE and how do I apply it?"
    a: "STRIDE is a threat categorization mnemonic: Spoofing (fake identity), Tampering (modify data), Repudiation (deny actions), Information Disclosure (leak data), Denial of Service (make unavailable), Elevation of Privilege (gain unauthorized access). For each component and data flow in your diagram, ask what STRIDE threats apply. Spoofing applies to authentication boundaries. Tampering applies to data in transit and at rest. Not every category applies to every element."
  - q: "Do I need special tools for threat modeling?"
    a: "A whiteboard or diagramming tool (Miro, Excalidraw, draw.io) works for most teams. Microsoft Threat Modeling Tool (free) generates STRIDE threats automatically from data-flow diagrams. OWASP Threat Dragon is an open-source alternative. The tool matters less than the process — a hand-drawn diagram with a STRIDE worksheet completed by the team is more valuable than a polished diagram nobody analyzed."
---

We shipped a file upload feature without threat modeling. Six months later, a pentest found that uploaded files were served from the same domain as the application — an attacker uploaded an HTML file with JavaScript that stole session cookies from other users. A one-hour threat modeling session would have identified the cross-origin data flow, flagged the missing content-type validation, and suggested serving uploads from a separate domain. The fix cost two weeks and a security advisory.

Threat modeling is a structured process for identifying security threats in a system design before they're exploited. Data-flow diagrams (DFDs) map what data moves where, and STRIDE analysis systematically asks what could go wrong at each point.

## Step 1: Draw the data-flow diagram

A DFD shows four element types:

- **External entity:** Users, admins, third-party services (rectangles).
- **Process:** Your code — APIs, services, workers (circles).
- **Data store:** Databases, caches, file storage (parallel lines).
- **Data flow:** Arrows showing data movement between elements.
- **Trust boundary:** Dashed lines separating zones of different trust levels.

```
┌──────────┐         ┌──────────────┐         ┌──────────┐
│  User    │──HTTPS─→│  Web API     │──SQL───→│ Database │
│ (Browser)│←─JSON───│  (Process)   │←────────│ (Store)  │
└──────────┘         └──────┬───────┘         └──────────┘
                            │
                     ─ ─ ─ ─│─ ─ ─ ─ Trust Boundary
                            │
                     ┌──────▼───────┐
                     │  S3 Bucket   │
                     │  (File Store)│
                     └──────────────┘
```

Mark trust boundaries where data crosses from one security zone to another: internet to DMZ, DMZ to internal network, your system to third-party APIs.

## Step 2: Apply STRIDE per element

For each element in the diagram, identify applicable STRIDE categories:

| Element | S | T | R | I | D | E |
|---------|---|---|---|---|---|---|
| User → Web API | ✅ | ✅ | | ✅ | ✅ | |
| Web API (process) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Web API → Database | | ✅ | | ✅ | | |
| Web API → S3 | | ✅ | | ✅ | | ✅ |
| Database (store) | | ✅ | | ✅ | ✅ | |

**Spoofing:** Can an attacker impersonate a user or service?
- Mitigation: Authentication (JWT, mTLS), API keys, certificate pinning.

**Tampering:** Can data be modified in transit or at rest?
- Mitigation: TLS, signed tokens, database encryption, input validation.

**Repudiation:** Can a user deny performing an action?
- Mitigation: Audit logs with tamper-proof storage, digital signatures.

**Information Disclosure:** Can sensitive data leak?
- Mitigation: Encryption at rest/transit, access controls, data minimization.

**Denial of Service:** Can the system be made unavailable?
- Mitigation: Rate limiting, autoscaling, CDN, input size limits.

**Elevation of Privilege:** Can a user gain unauthorized access?
- Mitigation: RBAC, least privilege, authorization checks on every endpoint.

## Step 3: Document threats and mitigations

For each identified threat, document:

```markdown
### T-001: Unauthenticated file upload (Spoofing + Elevation of Privilege)

**Element:** User → Web API → S3
**Threat:** Any internet user can upload files without authentication.
**Impact:** Storage abuse, malicious file hosting, malware distribution.
**Likelihood:** High
**Mitigation:** Require authentication for upload endpoint. Validate file type
  by content (magic bytes), not extension. Scan uploads with antivirus.
**Status:** Open → implement in sprint 23
```

Prioritize by impact × likelihood. Address critical and high-priority threats before shipping.

## Worked example: the file upload threat

Applying STRIDE to the upload flow from the opening:

**Spoofing:** Attacker uploads without authenticating.
→ Require JWT on upload endpoint.

**Tampering:** Attacker modifies file content in transit.
→ TLS (already present for HTTPS).

**Information Disclosure:** Uploaded files contain sensitive data visible to other users.
→ Serve files from a separate domain (uploads.example.com) with `Content-Disposition: attachment` and `Content-Type` matching actual content. Prevent browser execution of uploaded HTML/JS.

**Elevation of Privilege:** Attacker uploads a web shell disguised as an image.
→ Validate content type by magic bytes. Strip EXIF metadata. Store outside web root. Use pre-signed URLs with short TTL for access.

```python
ALLOWED_TYPES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

async def validate_upload(file: UploadFile):
    header = await file.read(8)
    await file.seek(0)

    content_type = None
    for magic, mime in ALLOWED_TYPES.items():
        if header.startswith(magic):
            content_type = mime
            break

    if not content_type:
        raise InvalidFileType()

    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise FileTooLarge()
```

## Threat modeling in agile teams

Threat modeling doesn't require a waterfall phase gate:

**Feature-level (1 hour):** Before building a new feature, draw a quick DFD, run STRIDE, document top 3-5 threats. Attach to the design doc or ticket.

**Service-level (half day):** When designing a new service or major refactor, full DFD with all data flows, complete STRIDE analysis, mitigation plan.

**Annual review (1 day):** Revisit existing threat models. Architecture drifted? New integrations added? Update diagrams and re-prioritize.

Include the engineer building the feature, a security-minded reviewer, and optionally product (for risk acceptance decisions). Three people for one hour beats one security engineer reviewing code after the fact.

## Common mistakes

**Modeling too late:** Threat modeling after code is shipped finds vulnerabilities you can't easily fix without rework.

**Too broad:** Modeling "the entire platform" produces an unreadable diagram. Model one service or feature at a time.

**Stopping at identification:** Finding threats without assigning mitigations and tracking resolution is theater. Every threat needs an owner and a status.

**Ignoring trust boundaries:** The most critical threats occur at trust boundaries — where data crosses from untrusted (internet) to trusted (internal). Focus STRIDE analysis on boundary crossings.

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Resources

- [OWASP Threat Modeling Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html)
- [Microsoft STRIDE model documentation](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool)
- [OWASP Threat Dragon (open-source tool)](https://owasp.org/www-project-threat-dragon/)
- [Adam Shostack — Threat Modeling: Designing for Security (book)](https://www.amazon.com/Threat-Modeling-Designing-Adam-Shostack/dp/1118809998)
- [Data Flow Diagrams for threat modeling — OWASP](https://owasp.org/www-community/Threat_Modeling_Process)
