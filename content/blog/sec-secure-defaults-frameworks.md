---
title: "Secure Defaults in Frameworks"
slug: "sec-secure-defaults-frameworks"
description: "Audit framework secure defaults: cookies, CSRF, headers, debug modes, and configuration checklists before shipping to production."
datePublished: "2025-06-12"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "Web Development"
  - "Frameworks"
  - "Configuration"
keywords: "secure defaults frameworks, Django security settings, Express helmet, Spring Security defaults, production hardening checklist, insecure defaults"
faq:
  - q: "Why are insecure defaults still common?"
    a: "Frameworks optimize developer experience and tutorial simplicity—DEBUG=True, permissive CORS, and verbose errors help local development. Production deployment is opt-in hardening. Teams assume they will fix it before launch and miss flags in obscure settings files when deadlines pressure."
  - q: "What should be disabled in production first?"
    a: "Debug modes, stack traces to users, open admin interfaces on public URLs, default credentials, directory listing, and detailed server version headers. Enable HTTPS redirects, secure cookies, CSRF on state-changing routes, and content security policies. Run framework-specific check commands like django-admin check --deploy."
  - q: "Do security headers replace input validation?"
    a: "No. Headers like CSP and HSTS reduce impact of classes of bugs but do not fix SQL injection or broken auth. Secure defaults layer defense in depth—use framework middleware for headers plus parameterized queries and session management from the same checklist."
---
Rails shipped with `config.force_ssl = false` and the staging URL leaked in email links over HTTP. Django ran six months with `ALLOWED_HOSTS = ['*']` because someone copied a Stack Overflow snippet. Frameworks increasingly ship safer defaults—HttpOnly cookies, CSRF tokens, escaped templates—but the escape hatches remain one env var away from catastrophe. Treat "secure by default" as a claim to verify against a production checklist, not a promise.

## Framework deploy checks

**Django:**

```bash
python manage.py check --deploy
```

Fix `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECRET_KEY` rotation.

**Rails:**

```ruby
config.force_ssl = true
config.hosts << "app.example.com"
config.action_dispatch.default_headers = {
  "X-Frame-Options" => "DENY",
  "X-Content-Type-Options" => "nosniff",
}
```

**Express:**

```javascript
import helmet from "helmet";
app.use(helmet());
app.disable("x-powered-by");
```

## Cookie defaults matrix

| Flag | Purpose |
|------|---------|
| Secure | HTTPS only |
| HttpOnly | No document.cookie access |
| SameSite=Lax/Strict | CSRF reduction |

Framework session middleware often sets these in production profile—confirm your `NODE_ENV=production` actually loads that profile.

## CSRF and CORS

Enable CSRF on cookie-authenticated forms and SameSite APIs. CORS is not auth—`Access-Control-Allow-Origin: *` with credentials enabled is invalid and dangerous patterns abound. Allowlist origins explicitly.

## Secrets and debug

Never commit `SECRET_KEY`, JWT secrets, or encryption keys. Use env vars or secret managers. `DEBUG=True` exposes settings and SQL in tracebacks—guard with env check that fails startup in prod if debug enabled.

## ORM over raw SQL

Default to ORM/query builders. Raw SQL escape hatches need code review labels. Mass assignment protection (`strong_parameters`, `@BindParam`) should stay on.

## Dependency and template auto-escape

Keep framework and template engine updated. Auto-escaping HTML in templates is default in modern engines—do not disable without explicit sanitizer pipeline.

- [ ] Deploy check command passes
- [ ] TLS enforced end-to-end
- [ ] Admin routes IP-restricted or SSO
- [ ] Error pages generic
- [ ] Security headers verified (securityheaders.com)
- [ ] Rate limits on auth endpoints
- [ ] Logging excludes secrets

Automate checklist in CI where possible—lint for `DEBUG=true` in Kubernetes manifests.

Automate django-admin check --deploy or framework equivalent in CI on production-like settings. DEBUG=true in Kubernetes manifests should fail lint.

Admin routes IP-restricted or behind SSO even when framework admin is convenient for demos. Error pages generic in production; stack traces belong in logs only.

Securityheaders.com or Mozilla Observatory scans in CI on staging URLs track header regressions when marketing adds third-party scripts.

## Django SECURE_* and Flask-Talisman

Framework secure defaults ship disabled for backwards compatibility—explicitly enable in production settings template. `DEBUG=False`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_HTTPONLY=True` belong in prod checklist enforced by linter on settings module.

## Next.js defaults in 2026

Server Actions require explicit opt-in; image optimization domains whitelisted. Review `next.config.js` security headers on every major version bump—defaults evolve.

## Secure-by-default library selection

Prefer libraries that fail closed: Zod parse throws, Rust `unwrap` discouraged in prod paths, SQL builders over string concat. Default choices in scaffolding templates matter more than security training slides.

## Sec Secure Defaults Frameworks: operational depth

Framework secure defaults ship disabled for backwards compatibility—production templates must flip them explicitly. Teams that skip instrumentation ship blind—baseline p75 latency and error rate on affected routes one week before change and compare seven days after.

Integration boundaries deserve contract tests with golden fixtures sampled from production traffic anonymized. Synthetic empty payloads pass CI while production fails on nullable fields you never modeled.

Security review asks three questions: what untrusted input enters, what secrets could leak in logs, and what happens when upstream is slow or malicious. Answers belong in the PR, not a post-launch wiki page.

Rollout prefers feature flags or canary deploys when behavior touches authentication, payments, or PII. Rollback command documented in runbook header—not discovered during incident via git archaeology.

On-call dashboards slice metrics by region and device class. Global averages hide mobile regressions until App Store reviews mention slowness—field data honesty beats demo Lighthouse scores.

## Resources

- [Django deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Rails security guide](https://guides.rubyonrails.org/security.html)
- [Helmet.js documentation](https://helmetjs.github.io/)
- [OWASP Secure Configuration Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Configuration_Cheat_Sheet.html)
- [Spring Security documentation](https://docs.spring.io/spring-security/reference/index.html)

## Extended guidance (1) for Sec Secure Defaults Frameworks

Operators owning sec secure defaults frameworks should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (2) for Sec Secure Defaults Frameworks

Operators owning sec secure defaults frameworks should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (3) for Sec Secure Defaults Frameworks

Operators owning sec secure defaults frameworks should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (4) for Sec Secure Defaults Frameworks

Operators owning sec secure defaults frameworks should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (5) for Sec Secure Defaults Frameworks

Operators owning sec secure defaults frameworks should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.