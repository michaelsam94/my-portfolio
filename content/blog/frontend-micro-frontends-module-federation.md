---
title: "Micro-Frontends with Module Federation"
slug: "frontend-micro-frontends-module-federation"
description: "Webpack Module Federation loads remote JavaScript bundles at runtime. Split teams by domain without iframes—shared dependencies, versioning, and failure modes."
datePublished: "2025-04-13"
dateModified: "2025-04-13"
tags: ["Web", "Frontend", "Architecture", "Webpack"]
keywords: "Module Federation, micro-frontends, webpack federation, remote entry, shared dependencies React"
faq:
  - q: "Module Federation vs iframe micro-frontends?"
    a: "Iframes isolate completely but hurt UX integration, routing, and performance. Module Federation shares runtime and can compose React trees across teams—stronger integration, requires disciplined shared dependency versions."
  - q: "How do shared dependencies avoid duplicate React?"
    a: "Federation shared config marks react and react-dom as singletons with requiredVersion. Host and remotes negotiate one copy at runtime—misaligned versions cause subtle hook errors."
  - q: "What happens if a remote fails to load?"
    a: "Host should catch dynamic import failure and show fallback UI or cached bundle. Production needs health checks on remoteEntry.js URLs and version pinning strategy—not always latest URL."
---

Checkout owned by Team Payments shipped on a different cadence than the shell owned by Platform. Module Federation let the host load `checkoutRemote/CheckoutApp` at runtime from Payments' CDN while sharing one React instance. The integration meeting was about semver ranges, not copying paste-updated bundles into a monolith `vendor/` folder.

Module Federation (Webpack 5+, supported in Rspack/Vite via plugins) exposes modules from a **remote** app consumed by a **host**.

## Remote configuration

```javascript
// webpack.config.js — checkout app (remote)
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'checkout',
      filename: 'remoteEntry.js',
      exposes: {
        './CheckoutApp': './src/CheckoutApp',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.2.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.2.0' },
      },
    }),
  ],
};
```

Remote serves `remoteEntry.js` at deploy URL.

## Host configuration

```javascript
new ModuleFederationPlugin({
  name: 'shell',
  remotes: {
    checkout: 'checkout@https://cdn.example.com/checkout/remoteEntry.js',
  },
  shared: {
    react: { singleton: true, requiredVersion: '^18.2.0' },
    'react-dom': { singleton: true, requiredVersion: '^18.2.0' },
  },
}),
```

## Loading remote in React

```tsx
import React, { lazy, Suspense } from 'react';

const CheckoutApp = lazy(() => import('checkout/CheckoutApp'));

export function CheckoutPage() {
  return (
    Suspense fallback={<Loading />}>
      <CheckoutApp cartId={cartId} />
    </Suspense>
  );
}
```

TypeScript needs module declaration:

```typescript
declare module 'checkout/CheckoutApp' {
  const CheckoutApp: React.ComponentType<{ cartId: string }>;
  export default CheckoutApp;
}
```

## Versioning and deployment

Strategies:

- **Runtime URL always latest** — simple, risky breaking changes
- **Environment pins** — staging remote URL vs production
- **Compatibility matrix** — host 2.x loads checkout remote ^2.x only

Document breaking changes in remote's public exposed API like any npm package.

## Routing integration

Host owns browser router; remote renders sub-routes or receives path via props:

```tsx
<CheckoutApp basename="/checkout" />
```

Avoid two routers fighting over history—single source in shell.

## CSS isolation

Remotes can leak global CSS. Prefer CSS modules, CSS-in-JS scoping, or shadow DOM for true isolation. Design system tokens shared as federated `designSystem/tokens` expose.

## Error boundaries

```tsx
<ErrorBoundary fallback={<CheckoutUnavailable />}>
  <Suspense fallback={<Loading />}>
    <CheckoutApp />
  </Suspense>
</ErrorBoundary>
```

Network failure loading remoteEntry should not white-screen entire app.

## When not to federate

Small teams, one product, shared release train—a monorepo with lazy routes is simpler. Federation pays off at organizational boundaries with independent deploy cadence.

## TypeScript sharing

Share types via federated `@types/checkout` or npm package—do not duplicate interface definitions in host and remote.

## Local development

Module Federation Dev Server proxies remotes:

```javascript
remotes: {
  checkout: 'checkout@http://localhost:3001/remoteEntry.js',
},
```

Document port map in monorepo README.

## Security boundaries

Remotes execute code in user session—treat remoteOrigin as trusted as host CSP allows. Subresource Integrity on remoteEntry where supported; pin versions in production.

## Performance

Lazy load remotes on route enter—do not fetch all remotes at initial page load unless needed.


## Deployment topology

Host and remotes deploy to separate CD pipelines—host must not hardcode latest remote URL without version pin in production. Common pattern: `checkout@https://cdn.example.com/checkout/1.4.2/remoteEntry.js` updated when remote team publishes; host bumps pin intentionally.

Staging uses `latest` symlink on CDN for integration testing; production uses immutable version paths for rollback—flip host config to previous remoteEntry path if remote regression detected.

## Shared dependency drift monitoring

Add CI job comparing `react` resolved version in host vs each remote's `package.json` requiredVersion. Mismatch warnings block release until aligned—React duplicate instance bugs manifest as invalid hook call errors that waste hours debugging.

## UX integration details

Loading remote modules should show skeleton UI in host route—never blank screen while remoteEntry downloads. Prefetch remote on link hover for internal navigation if latency sensitive.

Shared routing: document who owns 404 when deep link hits host path served by remote—usually host router delegates unknown `/checkout/*` to remote mount point.

## Organizational boundaries

Define API contract review between host and remote teams—breaking changes to exposed module surface require semver on remote package and coordinated host bump. Treat exposed federated modules like published npm packages with changelog and deprecation policy.

## Single SPA alternative

Evaluate Module Federation vs single SPA with lazy routes before splitting teams—organizational split should drive federation, not premature optimization for two features.

## Rollout guidance

Remote team publishes compatibility matrix host version x remote version supported—host PR bumping remote pin references matrix cell QA validated staging environment pairing before production pin update merge.

## Team practices

Shipping Frontend Micro Frontends Module Federation in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Frontend Micro Frontends Module Federation, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Frontend Micro Frontends Module Federation PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Frontend Micro Frontends Module Federation questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Frontend Micro Frontends Module Federation spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [Module Federation documentation](https://module-federation.io/)
- [Webpack Module Federation guide](https://webpack.js.org/concepts/module-federation/)
- [Module Federation examples (GitHub)](https://github.com/module-federation/module-federation-examples)
- [@module-federation/enhanced](https://www.npmjs.com/package/@module-federation/enhanced)
- [Micro-frontends patterns (martinfowler.com)](https://martinfowler.com/articles/micro-frontends.html)
