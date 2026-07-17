---
title: "eBPF Network Observability"
slug: "observability-ebpf-network-observability"
description: "Use eBPF to observe TCP, DNS, and HTTP traffic between pods without sidecar instrumentation—Cilium Hubble, Pixie, and kernel-level flow visibility."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Kubernetes"
  - "Networking"
keywords: "ebpf network observability, cilium hubble, kubernetes network flows, pixie ebpf, kernel tracing networking"
faq:
  - q: "How is eBPF network observability different from service mesh metrics?"
    a: "Service meshes use sidecars with L7 awareness but add latency. eBPF observes in the kernel with lower overhead—often without modifying application pods."
  - q: "Can eBPF replace distributed tracing?"
    a: "No. eBPF sees connections and DNS; traces carry business context across async boundaries."
  - q: "Does eBPF work on all cloud Kubernetes offerings?"
    a: "Most managed K8s support eBPF agents as DaemonSets; kernel 5.x preferred."
---

Payment service logs showed connection timeouts to `inventory.internal`. TCP dumps showed SYN without SYN-ACK. NetworkPolicy had been fixed last sprint—but which pod talked to which IP on which port? eBPF flow observability answered in five minutes: checkout hit inventory on 8080, inventory listened on 8081.

## Cilium + Hubble

Flow logging with source/destination service names, L7 HTTP when enabled, DNS queries, NetworkPolicy drop reasons. Alert on `hubble_drop_total{reason="Policy denied"}`.

## Pixie

Scriptable PxL queries for HTTP/SQL/DNS without changing CNI—good when you cannot migrate to Cilium.

## Debugging workflows

DNS failures: `hubble observe --protocol dns`. Intermittent TLS: correlate with app traces. Silent drops: compare drop metrics with user-facing error spikes.

## Limits

Payload contents opaque; encrypted traffic limits L7 parsing; pair with distributed tracing for request semantics.


## Correlating Hubble flows with application traces

When flow shows `DROPPED` between checkout and payments, grab `trace_id` from checkout logs and verify HTTP client span never received response—confirms network drop vs application timeout misconfiguration.

Teach on-call: **Hubble first for connection refused / policy denied**; **traces first for slow OK responses**.

## Multi-cluster and mesh boundaries

Service mesh mTLS hides payload from eBPF L7 parsers on some platforms—flows show encrypted bytes only. Combine mesh telemetry (Istio access logs) with eBPF L4 for packet drops on node. Document which tool owns which failure mode in runbook matrix.

## Cost of flow log retention

Full L7 flow logs at 100k RPS overwhelm storage. Retention tiers:

- **24 hours** full L4+L7 for incident window
- **7 days** aggregated flow counts only
- **Metrics** (`hubble_flows_processed_total`) for 90 days

Tune Hubble `--enable-l7-proxy-visibility` only on namespaces under active network debugging—not entire cluster indefinitely.

## IPv6 dual-stack clusters

Hubble must resolve IPv6 pod addresses—verify flow maps show same edges as IPv4 during dual-stack migration. Mixed stacks cause "missing edge" when CSMS or legacy monitors IPv4-only.

## Incident timeline reconstruction

Export Hubble flows to PCAP-less timeline CSV during postmortem: `{timestamp, src, dst, verdict, bytes}`. Attach to incident doc—faster than screenshot gallery for auditors.

## Runbook integration

Network timeout runbooks should start with Hubble/Pixie query templates parameterized by namespace and service labels from the alert. Copy-paste commands beat prose instructions at 3 AM. Include screenshot of healthy baseline flow map in runbook appendix so on-call recognizes abnormal edge colors quickly.

For hybrid cloud, eBPF sees pod-to-NAT-to-internet paths—document which hops are visible vs blind when debugging SaaS API failures from Kubernetes workloads. Reduces false accusations of external vendor outage when corporate proxy MITM is the actual fault.


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
