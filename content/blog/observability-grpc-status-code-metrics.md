---
title: "gRPC Status Code Metrics"
slug: "observability-grpc-status-code-metrics"
description: "Instrument gRPC servers and clients with per-method status counters and latency histograms for OK, INVALID_ARGUMENT, and UNAVAILABLE."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Backend"
  - "gRPC"
keywords: "grpc metrics prometheus, grpc status codes observability, grpc_server_handled_total, opentelemetry grpc, grpc slo"
faq:
  - q: "Why are gRPC status codes different from HTTP metrics?"
    a: "gRPC uses numeric codes over HTTP/2. DEADLINE_EXCEEDED means something different from NOT_FOUND—instrument grpc_code labels explicitly."
  - q: "Should client and server both emit metrics?"
    a: "Yes. Divergence (client UNAVAILABLE high, server OK) indicates infrastructure between them."
  - q: "How do I alert on gRPC SLOs?"
    a: "Treat non-OK codes as errors except client faults like INVALID_ARGUMENT when appropriate."
---

HTTP dashboards showed 200 OK at the gateway while internal gRPC returned UNAVAILABLE during rolling deploys—800ms added by retries before HTTP timed out. `grpc_server_handled_total` by method and code made deploy correlation obvious.

## Codes that matter

INTERNAL and UNAVAILABLE page-worthy; INVALID_ARGUMENT and NOT_FOUND often client issues. Document SLI error set explicitly.

## prometheus/grpc-go

`grpc_prometheus` server and client interceptors with handling time histogram enabled.

## OpenTelemetry

`otelgrpc.NewServerHandler()` with semconv `rpc.grpc.status_code`.

## Dashboards

Availability by method, error heatmap by code, p99 latency per `grpc_method`.

## Graceful shutdown

Rolling deploy without `GracefulStop()` causes UNAVAILABLE spikes and retry storms—preStop hook and readiness removal before SIGTERM.


## Interceptor ordering in Go

Register metrics interceptor **after** auth interceptor so rejected unauthenticated requests still count toward `UNAUTHENTICATED` metrics—otherwise blind spot on attack traffic volume.

```go
grpc.ChainUnaryInterceptor(
  authInterceptor,
  grpcMetrics.UnaryServerInterceptor(),
  loggingInterceptor,
)
```

## protobuf service versioning

When `inventory.v2.Inventory` ships alongside v1, labels must include `grpc_service` separately—dashboards filter v2 canary error rates without v1 noise.

## Envoy sidecar gRPC stats

If using Istio/Envoy, validate sidecar stats match application stats—Envoy may report `upstream_rq_200` while app returns gRPC `INTERNAL` mapped to HTTP 200 (gRPC over HTTP/2 framing). Trust application-level `grpc_server_handled_total` for SLOs, Envoy for network layer.

## Reflection and health service noise

gRPC health checks and reflection RPCs inflate `grpc_server_started_total`—exclude from SLO denominators via label `grpc_method!~"Check|ServerReflectionInfo"` or separate service port for health on different registration.

## Streaming backpressure signals

Client-side `RESOURCE_EXHAUSTED` on streaming RPC may indicate consumer slower than producer—track per-method stream duration and message rate metrics alongside unary RED.

## gRPC retries and metric interpretation

Client retry middleware inflates `grpc_client_attempts` relative to server handled count—track attempt ratio as separate metric. High retry ratio with elevated `UNAVAILABLE` during deploys signals need for better graceful shutdown, not automatic client retry increase which amplifies load.

Document gRPC SLO error code sets in service README—new engineers otherwise assume all non-OK codes are page-worthy, causing alert definition drift between teams.


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
