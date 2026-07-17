---
title: "W3C Trace Context and Baggage"
slug: "observability-trace-context-w3c-baggage"
description: "Propagate traceparent and tracestate—and use W3C Baggage for tenant tier without bloating span attributes."
datePublished: "2026-02-03"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "OpenTelemetry"
  - "Backend"
keywords: "W3C trace context, traceparent header, tracestate, W3C baggage, opentelemetry propagation"
faq:
  - q: "What is traceparent?"
    a: "Carries version, trace-id, parent-span-id, trace-flags—required for distributed tracing over HTTP/gRPC/messaging."
  - q: "How is baggage different?"
    a: "Baggage propagates optional key-value context (tenant tier, experiment flags) across services without indexing every value as span attributes."
  - q: "Should user_id go in baggage?"
    a: "Avoid PII—use opaque tenant_id or tier. Validate at edge; treat client-supplied baggage as untrusted."
---

Premium tenant outage but traces showed no tier difference—`tenant_tier` was only in a DB join. W3C Baggage carries `tenant_tier=enterprise` on every hop for tail sampling and log filters.

## traceparent flow

Extract on ingress, child span, inject on egress—same trace-id, new parent span-id for downstream.

## Async

Kafka/SQS inject traceparent in headers; thread pools must propagate OTel context.

## Baggage rules

Keep under 4KB; no JWTs or emails; strip and re-set from verified token at gateway.

## Migration

Dual B3 + W3C propagators during migration; remove B3 when all services export W3C.


## Baggage size limits at gateway

Strip or truncate baggage exceeding 4KB at API gateway—prevent client-supplied baggage DOS on downstream header parsing.

## W3C vs AWS X-Ray

Hybrid AWS migration: OTel propagator `xray` alongside tracecontext during Lambda → EKS transitions. Document header precedence in shared library—dual context bugs split traces for weeks.

## Propagation integration tests in CI

Testcontainers spin mock services A→B→C; assert trace-id unchanged and baggage key survives—all services must pass before deploy to production mesh.

## Service mesh and traceparent

Istio/Linkerd generate sidecar spans—traceparent arriving at app container may differ from edge. Consistent service graph requires telemetry API or mesh config propagating same trace IDs—consult mesh docs for YOUR mesh version; misconfiguration common during Istio upgrades.

## Baggage and GDPR

Right-to-erasure requests: baggage must not cache user identifiers across async jobs—stateless propagation only; do not write baggage keys to durable queues without TTL and legal review.

## Debugging propagation failures in production

When orphan spans appear, enable OpenTelemetry Collector `probabilistic_sampler` debug logging temporarily OR use telemetry introspection API—avoid enabling debug globally. Common fix: reorder middleware so trace extraction runs before auth middleware that short-circuits unauthenticated requests without span.

Baggage propagation failures often manifest as missing tenant tier in downstream logs while present upstream—add integration test asserting baggage keys at each hop in CI pipeline for tier-1 services.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.
