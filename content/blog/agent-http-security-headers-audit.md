---
title: "HTTP Security Headers Audit for Agent Platforms"
slug: "agent-http-security-headers-audit"
description: "Automate HTTP security header audits across agent API gateways, chat UIs, and webhook endpoints—baseline policies, CI gates, drift detection, and remediation playbooks for production AI stacks."
datePublished: "2025-10-10"
dateModified: "2025-10-10"
tags: ["AI Agents", "Security", "HTTP", "DevSecOps"]
keywords: "HTTP security headers audit, HSTS, CSP, X-Frame-Options, agent API security, security header scanning, OWASP headers"
faq:
  - q: "Which HTTP security headers matter most for agent platforms?"
    a: "Prioritize Strict-Transport-Security, Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, and Cross-Origin-Opener-Policy on chat UIs. Agent API gateways need HSTS, X-Content-Type-Options, and Cache-Control on authenticated routes. Webhook receivers need tight CORS and no caching of signed payloads."
  - q: "Should security header audits run in CI or only against production?"
    a: "Both. CI catches regressions before deploy on staging URLs with production-shaped routes. Scheduled production scans detect CDN misconfigurations, legacy microservices, and third-party embed drift that staging never exercises. Treat header policy as code checked into the repo."
  - q: "How do you audit headers on streaming agent endpoints?"
    a: "SSE and chunked responses still carry headers on the initial response. Use HEAD or GET with Range: bytes=0-0 to minimize body download. Verify headers before the first data frame—some proxies strip headers mid-stream, which is itself a finding worth fixing."
  - q: "What is a realistic pass threshold for a header audit?"
    a: "Tier findings: critical (missing HSTS on auth routes, CSP with unsafe-inline on agent chat), high (missing X-Content-Type-Options, permissive frame-ancestors), medium (weak Referrer-Policy). Block deploy on critical; ticket high with SLA. Document accepted exceptions with expiry dates, not permanent waivers."
---

A penetration test on our agent dashboard found no SQL injection and no SSRF — and still opened with "your API returns `Access-Control-Allow-Origin: *` on authenticated routes and your chat UI has no Content-Security-Policy." The application logic was fine. The **HTTP security headers** were not. Agent platforms expose more surfaces than typical CRUD apps: streaming chat endpoints, tool webhooks, embedded widgets, and admin consoles that render model output. A header audit is how you prove, continuously, that every route enforces the same baseline.

This is not a one-time checklist before launch. Headers drift when someone adds a new CDN behavior, when a microservice bypasses the gateway, or when a vendor iframe lands on the settings page. An automated audit turns "we think we're secure" into a diffable policy with owners and rollback.

## What an agent platform actually exposes

Map your attack surface before choosing scan targets:

| Surface | Typical routes | Header priorities |
|---------|----------------|-------------------|
| Chat UI | `/agent`, `/chat`, `/embed` | CSP, COOP, Referrer-Policy, Permissions-Policy |
| Agent API | `/v1/runs`, `/v1/tools/invoke` | HSTS, Cache-Control, X-Content-Type-Options |
| Webhooks inbound | `/hooks/github`, `/hooks/slack` | No cache, strict CORS, body size limits |
| Static tool sandbox | `sandbox.tools.example.com` | CSP (strict), frame-ancestors, COEP if isolated |
| Admin / eval console | `/admin/prompts`, `/evals` | Same as chat UI plus stricter CSP |

Agent-specific risk: **user-influenced content in HTML responses**. Model markdown, retrieved RAG chunks, and tool JSON rendered in the browser mean XSS defenses live in CSP and sanitization — but the audit verifies CSP is present and not hollow (`unsafe-inline` everywhere).

## Baseline header policy as code

Encode your expected headers per route class in a version-controlled manifest:

```yaml
# security/header-policy.yaml
defaults:
  Strict-Transport-Security: "max-age=63072000; includeSubDomains; preload"
  X-Content-Type-Options: "nosniff"
  X-Frame-Options: "DENY"
  Referrer-Policy: "strict-origin-when-cross-origin"
  Permissions-Policy: "camera=(), microphone=(), geolocation=()"
  Cross-Origin-Opener-Policy: "same-origin"
  Cross-Origin-Resource-Policy: "same-origin"

route_classes:
  agent_chat_ui:
    paths:
      - "/agent/**"
      - "/chat/**"
    required:
      Content-Security-Policy:
        must_contain:
          - "script-src"
          - "'nonce-"
        must_not_contain:
          - "'unsafe-inline'"
          - "'unsafe-eval'"
      Cache-Control: "private, no-store"

  agent_api_authenticated:
    paths:
      - "/v1/**"
    required:
      Cache-Control: "no-store"
    forbidden:
      Access-Control-Allow-Origin: "*"

  public_webhook:
    paths:
      - "/hooks/**"
    required:
      Cache-Control: "no-store"
    note: "CORS should be absent or origin-allowlist only"
```

This manifest becomes the contract your audit tool evaluates. When security approves a temporary CSP exception for a legacy chart library, add it to an `exceptions:` block with `expires_at` — not a Slack thread nobody reads.

## Building the audit scanner

A practical scanner fetches each configured URL, normalizes header names to lowercase, and compares against policy. Use production-like auth: service tokens for API routes, session cookies for UI routes.

```typescript
// scripts/audit-security-headers.ts
import { readFileSync } from "fs";
import yaml from "yaml";

type HeaderRule = {
  must_contain?: string[];
  must_not_contain?: string[];
  exact?: string;
};

type RouteClass = {
  paths: string[];
  required?: Record<string, HeaderRule | string>;
  forbidden?: Record<string, string>;
};

interface Finding {
  url: string;
  severity: "critical" | "high" | "medium";
  header: string;
  message: string;
}

function matchPath(pattern: string, path: string): boolean {
  const regex = new RegExp("^" + pattern.replace(/\*\*/g, ".*").replace(/\*/g, "[^/]+") + "$");
  return regex.test(path);
}

function checkHeader(value: string | undefined, rule: HeaderRule | string): string | null {
  if (typeof rule === "string") {
    return value === rule ? null : `expected "${rule}", got "${value ?? "(missing)"}"`;
  }
  if (!value) return "header missing";
  for (const fragment of rule.must_contain ?? []) {
    if (!value.includes(fragment)) return `must contain "${fragment}"`;
  }
  for (const fragment of rule.must_not_contain ?? []) {
    if (value.includes(fragment)) return `must not contain "${fragment}"`;
  }
  return null;
}

export async function auditUrl(
  baseUrl: string,
  path: string,
  routeClass: RouteClass,
  fetchOpts: RequestInit = {}
): Promise<Finding[]> {
  const url = new URL(path, baseUrl).href;
  const res = await fetch(url, { method: "GET", redirect: "manual", ...fetchOpts });
  const findings: Finding[] = [];

  for (const [header, rule] of Object.entries(routeClass.required ?? {})) {
    const err = checkHeader(res.headers.get(header) ?? undefined, rule);
    if (err) {
      findings.push({
        url,
        severity: header === "Content-Security-Policy" ? "critical" : "high",
        header,
        message: err,
      });
    }
  }

  for (const [header, forbiddenValue] of Object.entries(routeClass.forbidden ?? {})) {
    const actual = res.headers.get(header);
    if (actual === forbiddenValue) {
      findings.push({
        url,
        severity: "critical",
        header,
        message: `forbidden value "${forbiddenValue}" present`,
      });
    }
  }

  return findings;
}
```

Run against a URL list generated from your OpenAPI spec and frontend route manifest so new endpoints cannot ship without audit coverage.

## CI integration and deploy gates

Wire the scanner into GitHub Actions (or your CI) against staging after every deploy:

```yaml
# .github/workflows/security-headers.yml
name: HTTP Security Headers Audit
on:
  deployment_status:
    types: [success]

jobs:
  audit:
    if: github.event.deployment_status.environment == 'staging'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - name: Run header audit
        env:
          AUDIT_BASE_URL: ${{ secrets.STAGING_URL }}
          AUDIT_TOKEN: ${{ secrets.STAGING_SERVICE_TOKEN }}
        run: npx tsx scripts/audit-security-headers.ts --fail-on critical,high
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: header-audit-report
          path: reports/security-headers.json
```

Block merges on **critical** findings only initially — teams need time to fix historical debt. Expand to **high** once the baseline is green for two sprints.

## Production drift detection

Staging parity lies. CDNs, WAFs, and regional edge configs differ from staging. Schedule a nightly cron against production URLs:

- Same manifest, read-only credentials
- Alert on **new** findings compared to yesterday's report (diff, not absolute pass/fail)
- Track mean time to remediate per severity

Store results in a time-series table:

```sql
CREATE TABLE header_audit_runs (
  id           BIGSERIAL PRIMARY KEY,
  run_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  url          TEXT NOT NULL,
  header       TEXT NOT NULL,
  severity     TEXT NOT NULL,
  message      TEXT NOT NULL,
  resolved_at  TIMESTAMPTZ
);

CREATE INDEX ON header_audit_runs (run_at, severity);
CREATE INDEX ON header_audit_runs (url, header) WHERE resolved_at IS NULL;
```

Dashboard open findings by owning team (derive team from URL prefix or service catalog). Unowned findings rot.

## Agent-specific audit scenarios

### Streaming chat (SSE)

Verify headers on the HTTP upgrade response before event frames flow:

```bash
curl -sI -N \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  "https://api.example.com/v1/chat/stream" | head -20
```

Confirm `Cache-Control: no-store` — caching partial streams leaks conversation fragments at shared CDN edges. Confirm no `Access-Control-Allow-Origin: *` unless the route is intentionally public.

### Tool iframe embeds

Fetch the sandbox origin separately from the main app. Expect a **tighter** CSP than the parent chat UI. Parent and child should both set `frame-ancestors` appropriately: parent allows framing nowhere; sandbox allows only the parent origin.

### Webhook receivers

Inbound webhooks (Slack events, GitHub Actions callbacks triggering agent runs) should not return sensitive headers or cache tool invocation results:

```bash
curl -sI -X POST "https://hooks.example.com/github" \
  -H "X-Hub-Signature-256: sha256=test" \
  -d '{}' | grep -iE 'cache-control|access-control|content-security'
```

Missing `Cache-Control` on POST responses is a medium finding; wildcard CORS on authenticated webhook admin panels is critical.

### LLM proxy routes

If your gateway proxies `api.openai.com`, audit the **outbound** policy too — some teams strip security headers from proxied responses. Users' browsers should never see raw upstream headers; your gateway should re-apply baseline headers on every response class.

## Remediation playbook

When the audit fails, route fixes to the right layer:

| Finding | Likely owner | Fix pattern |
|---------|--------------|-------------|
| Missing HSTS | Platform / ingress | Add at load balancer or API gateway |
| Weak CSP on chat UI | Frontend | Nonce middleware + report-only rollout |
| `Access-Control-Allow-Origin: *` on API | Backend service | Origin allowlist in gateway |
| Missing headers on one microservice | Service team | Sidecar or framework middleware |
| CDN stripping headers | Infra | Origin response header pass-through rules |

Provide copy-paste snippets per stack. For Express:

```typescript
import helmet from "helmet";

app.use(
  helmet({
    contentSecurityPolicy: false, // set per-route for agent UI
    hsts: { maxAge: 63072000, includeSubDomains: true, preload: true },
    frameguard: { action: "deny" },
    referrerPolicy: { policy: "strict-origin-when-cross-origin" },
  })
);

app.use("/agent", (req, res, next) => {
  res.setHeader("Cache-Control", "private, no-store");
  res.setHeader("Content-Security-Policy", buildAgentCsp(res.locals.nonce));
  next();
});
```

For nginx ingress annotations, document the exact `configuration-snippet` that passes audit — engineers should not reverse-engineer headers from a failing scan.

## Correlation with CSP violation reports

Header audits prove headers **exist**. CSP violation reports prove they **work** under real traffic. Pipe `/api/csp-report` payloads into the same dashboard as audit findings. A route can pass audit (CSP present, no `unsafe-inline`) while reports show blocked `connect-src` to a new LLM endpoint — that is a policy gap, not a missing header.

Track:

- Audit pass rate by route class (target: 100% critical, 95% high)
- CSP violations per 1k sessions (target: near zero after report-only phase)
- Time from new finding to merged fix (target: < 5 business days for critical)

## Third-party and vendor embeds

Agent products integrate analytics, support widgets, and OAuth consent screens. Each vendor script is a header audit exception waiting to happen. Maintain a **vendor register**: domain, required CSP fragments, review date, data classification. The audit manifest should include vendor-specific route overrides — not blanket `unsafe-inline` on the whole app.

When a vendor updates their embed, your nightly production scan catches header drift before users do. Pair with Subresource Integrity on static vendor scripts where the vendor supports it.

## The takeaway

HTTP security header audits give agent platforms a mechanical proof that every chat surface, API route, and webhook endpoint enforces the same baseline — and alert you when deploys or CDN changes drift away from it. Encode policy as code, scan staging in CI, diff production nightly, tier findings by severity, and tie remediation to owning teams. Headers are cheap defense-in-depth against XSS, clickjacking, and cache poisoning; the audit makes them operable instead of aspirational.

## Resources

- [OWASP — Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN — HTTP response headers](https://developer.mozilla.org/en-US/docs/Glossary/Response_header)
- [securityheaders.com — Header analysis reference](https://securityheaders.com/)
- [Helmet.js — Express security middleware](https://helmetjs.github.io/)
- [Mozilla Observatory — Server-side header scanner](https://observatory.mozilla.org/)
