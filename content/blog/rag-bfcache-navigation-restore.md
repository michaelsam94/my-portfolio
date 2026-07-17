---
title: "Back/Forward Cache (bfcache) and SPA Navigation Restore"
slug: "rag-bfcache-navigation-restore"
description: "Preserving page state on browser back navigation — bfcache eligibility, unload handlers, and Next.js/React pitfalls."
datePublished: "2025-07-03"
dateModified: "2026-07-17"
tags:
  - "Frontend"
  - "Performance"
  - "Web Platform"
keywords: "bfcache, back forward cache, spa navigation, page lifecycle"
faq:
  - q: "What is bfcache?"
    a: "Browser keeps fully frozen JS heap and DOM when navigating away so back button restores instantly without rerun — unlike traditional reload."
  - q: "What prevents bfcache eligibility?"
    a: "unload/beforeunload listeners, open IndexedDB connections without closure, Cache-Control no-store, certain WebSockets, and unclosed BroadcastChannels."
  - q: "How test bfcache in SPAs?"
    a: "Chrome DevTools Application panel bfcache test; navigation timing type back_forward; Playwright back navigation asserting no network refetch."
---
Users expect the back button to return to scroll position and form state instantly — but SPAs break bfcache with careless unload listeners and eternal WebSockets. bfcache restores frozen pages from memory; fighting it wastes CPU and hurts Core Web Vitals. Frontend engineers must audit lifecycle APIs, close resources on pagehide, and validate frameworks do not opt out by default.

## Page Lifecycle API

pageshow/pagehide with persisted flag indicates bfcache restore — reattach listeners idempotently, refresh stale data selectively not full remount.

Safari and Chrome differ on bfcache eligibility — test both engines in CI, not Chrome-only.

## Common SPA bfcache killers

Analytics beforeunload, legacy jQuery unload cleanup, service worker no-store on HTML shell — audit with Chrome bfcache diagnostic.

## WebSocket and SSE on restore

Close on pagehide freeze; reconnect on pageshow if persisted. Server must handle duplicate session or use resumable tokens.

## React and Next.js considerations

StrictMode double mount differs from bfcache restore — use persisted flag not mount count. Next.js app router cache vs bfcache separate concerns.

## Measuring impact

Field data back_forward navigation timing; lab Lighthouse bfcache audit. Conversion funnels comparing back navigation drop-off before/after fix.

## Privacy and sensitive pages

Logout pages should opt out via Cache-Control no-store — financial confirmations may need fresh fetch not frozen state.

## Analytics and bfcache

Page view analytics firing only on load undercount back navigations — listen to pageshow persisted event for accurate funnel metrics. Marketing attribution missing bfcache restores misallocates conversion credit to wrong campaign entry points.

## Service worker interaction

Service worker fetch handler may bypass bfcache restore expecting network — test SW update during back navigation. skipWaiting can invalidate frozen page state confusing users.

## Memory pressure eviction

Mobile browsers evict bfcache entries under memory pressure — do not rely on bfcache for critical unsaved form persistence; use localStorage debounced save as backup.

bfcache is free performance if you stop blocking it — remove unload handlers, close sockets on hide, test back navigation like users do.

Add bfcache restore case to E2E suite for top three revenue URLs — regression catches framework upgrade opt-out.

Design review checklist item 1 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 12 for bfcache navigation restore: validate failure modes, owner, and rollback before merge to main.

Observability gap 12 in bfcache navigation restore often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 12 for bfcache navigation restore should assert behavior under duplicate requests and slow dependencies.

Runbook section 12 for bfcache navigation restore documents escalation when primary and secondary on-call roles are unreachable.

## Integration notes for bfcache navigation restore

This rarely lives alone. Map upstream dependencies (auth, data stores, queues) and downstream consumers before you harden the happy path. Sequence the rollout: observability first, then flags, then the risky behavior change. That order turns rollback into a flag flip instead of a reverse migration under pressure. Keep the integration diagram in the same repo as the code so it cannot rot in a slide deck.
