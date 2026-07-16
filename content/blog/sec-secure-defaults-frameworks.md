---
title: "Secure Defaults in Frameworks"
slug: "sec-secure-defaults-frameworks"
description: "Audit framework secure defaults: cookies, CSRF, headers, debug modes, and configuration checklists before shipping to production."
datePublished: "2025-06-12"
dateModified: "2025-06-12"
tags: ["Security", "Web Development", "Frameworks", "Configuration"]
keywords: "secure defaults frameworks, Django security settings, Express helmet, Spring Security defaults, production hardening checklist, insecure defaults"
faq:
  - q: "Why are insecure defaults still common?"
    a: "Frameworks optimize developer experience and tutorial simplicity—DEBUG=True, permissive CORS, and verbose errors help local development. Production deployment is opt-in hardening. Teams assume 'we'll fix it before launch' and miss flags in obscure settings files when deadlines pressure."
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Cookie defaults matrix

| Flag | Purpose |
|------|---------|
| Secure | HTTPS only |
| HttpOnly | No document.cookie access |
| SameSite=Lax/Strict | CSRF reduction |

Framework session middleware often sets these in production profile—confirm your `NODE_ENV=production` actually loads that profile.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## CSRF and CORS

Enable CSRF on cookie-authenticated forms and SameSite APIs. CORS is not auth—`Access-Control-Allow-Origin: *` with credentials enabled is invalid and dangerous patterns abound. Allowlist origins explicitly.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Secrets and debug

Never commit `SECRET_KEY`, JWT secrets, or encryption keys. Use env vars or secret managers. `DEBUG=True` exposes settings and SQL in tracebacks—guard with env check that fails startup in prod if debug enabled.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## ORM over raw SQL

Default to ORM/query builders. Raw SQL escape hatches need code review labels. Mass assignment protection (`strong_parameters`, `@BindParam`) should stay on.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Dependency and template auto-escape

Keep framework and template engine updated. Auto-escaping HTML in templates is default in modern engines—do not disable without explicit sanitizer pipeline.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Django deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Rails security guide](https://guides.rubyonrails.org/security.html)
- [Helmet.js documentation](https://helmetjs.github.io/)
- [OWASP Secure Configuration Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Configuration_Cheat_Sheet.html)
- [Spring Security documentation](https://docs.spring.io/spring-security/reference/index.html)
