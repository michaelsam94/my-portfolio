---
title: "Running WebAssembly Workloads on Kubernetes"
slug: "wasm-workloads-kubernetes"
description: "Running WebAssembly workloads on Kubernetes with SpinKube, runwasi, and containerd shims — what Wasm buys you, where it hurts, and when to actually use it."
datePublished: "2026-05-06"
dateModified: "2026-05-06"
tags: ["Kubernetes", "WebAssembly", "DevOps"]
keywords: "WebAssembly Kubernetes, Wasm workloads, SpinKube, runwasi, containerd wasm, wasm microservices"
faq:
  - q: "What does running WebAssembly on Kubernetes actually mean?"
    a: "It means scheduling Wasm modules as pods instead of, or alongside, OCI containers. A containerd shim (runwasi) runs the module in a Wasm runtime like Wasmtime rather than a full Linux container, so the same kubectl, scheduling, and networking apply while the workload is a sandboxed Wasm binary measured in kilobytes."
  - q: "Is Wasm on Kubernetes faster than containers?"
    a: "For cold starts and image size, dramatically — Wasm modules start in single-digit milliseconds and are often under a megabyte, versus hundreds for container images. For steady-state compute-heavy work, native containers usually still win. Wasm's advantage is startup, density, and portability, not raw throughput."
  - q: "Can I run any application as a Wasm workload?"
    a: "No. You're limited to languages that compile to Wasm/WASI and libraries that don't assume full POSIX. Rust, Go (TinyGo), and C are the smoothest; anything needing threads, raw sockets, or arbitrary syscalls may not work yet. Treat Wasm as a target for new, well-scoped services rather than a lift-and-shift for existing ones."
---

Wasm on Kubernetes sounds like a contradiction until you see the numbers: a service that cold-starts in 3 milliseconds and ships as a 900 KB artifact, scheduled by the same control plane running your containers. Running WebAssembly workloads on Kubernetes means packaging code as WASI modules and executing them through a containerd shim instead of a container runtime, so `kubectl`, the scheduler, and your networking stack all keep working while the actual unit of execution is a sandboxed Wasm binary. The payoff is startup speed, tiny images, and a security boundary that's deny-by-default.

I've been running a couple of Wasm services in a mixed cluster for about a year. It's genuinely useful for the right shape of workload and genuinely frustrating if you expect it to replace containers wholesale. Here's the honest version.

## How the plumbing works

The magic is that Kubernetes doesn't need to know about Wasm. It talks to containerd; containerd delegates to a *shim* per workload type. For Wasm, the [runwasi](https://github.com/containerd/runwasi) project provides shims that embed a Wasm runtime (Wasmtime, WasmEdge). You install the shim on nodes, register a `RuntimeClass`, and pods that request that class get run as Wasm modules instead of Linux containers.

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: wasmtime-spin
handler: spin          # matches the containerd shim binary
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-wasm
spec:
  replicas: 3
  selector: { matchLabels: { app: hello-wasm } }
  template:
    metadata:
      labels: { app: hello-wasm }
    spec:
      runtimeClassName: wasmtime-spin
      containers:
        - name: app
          image: ttl.sh/hello-spin:1h   # an OCI artifact wrapping the Wasm module
```

The Wasm module is still distributed as an OCI artifact, so your existing registry, image pull policy, and signing tooling apply. That reuse is the reason this pattern is viable at all — you're not bolting on a parallel distribution system.

## What Wasm actually buys you

Three things, concretely:

- **Cold start.** A Wasm module instantiates in single-digit milliseconds. If you're scaling to zero and back — serverless-style — this eliminates the cold-start tax that makes container-based scale-to-zero painful. This dovetails with where [serverless is heading in 2026](https://blog.michaelsam94.com/serverless-2026/).
- **Density and size.** Modules are often under a megabyte and use a fraction of the memory of a container. You can pack far more of them per node, which matters for high-cardinality, low-traffic services (per-tenant handlers, edge logic).
- **Security posture.** Wasm is a capability-based sandbox. A module can't touch the filesystem, network, or clock unless the host explicitly grants it. That's a much smaller attack surface than a container that shares the host kernel.

The portability story — "compile once, run on any architecture" — is real but oversold for server-side use, where you control the nodes anyway. I care more about the cold-start and sandbox properties. The one place portability does pay off is a heterogeneous fleet: the same module runs unmodified on an arm64 node and an amd64 node, so you stop maintaining per-architecture image variants. That's a small but genuine operational saving if you run mixed hardware.

## Where it hurts

I'll be blunt about the sharp edges, because the marketing won't be:

| Concern | Container | Wasm workload |
| --- | --- | --- |
| Language support | Anything | Rust/Go/C smooth; JVM, Python partial |
| Threading | Full | Limited / immature |
| Networking | Full sockets | Via host, WASI networking still maturing |
| Ecosystem/libraries | Vast | Small, WASI-constrained |
| Debugging tooling | Mature | Thin |

The WASI standard is still filling in capabilities — sockets, threads, and async are at various stages. If your service needs raw TCP or spawns threads, you'll hit a wall or a workaround. The library ecosystem assumes POSIX in a thousand places, so a dependency that shells out or opens `/proc` simply won't compile to a usable module. Debugging is also thinner; a panic in a Wasm module gives you less to work with than a container you can `exec` into.

## SpinKube: the ergonomic path

Raw runwasi is low-level. [SpinKube](https://www.spinkube.dev/) puts an operator and CRDs on top so you deploy a `SpinApp` custom resource and it handles the RuntimeClass wiring, scaling, and executor selection. If you're building HTTP microservices, the Spin framework gives you a sane programming model (request in, response out) and SpinKube makes it a first-class Kubernetes citizen. This is the operator pattern doing exactly what it's good for — the same idea behind [writing a Kubernetes operator with CRDs](https://blog.michaelsam94.com/kubernetes-operators-crd/), applied to a new workload type.

```rust
use spin_sdk::http::{IntoResponse, Request, Response};
use spin_sdk::http_component;

#[http_component]
fn handle(req: Request) -> anyhow::Result<impl IntoResponse> {
    Ok(Response::builder()
        .status(200)
        .header("content-type", "text/plain")
        .body(format!("path: {}", req.path()))
        .build())
}
```

That compiles to a Wasm module a few hundred kilobytes in size, deploys as a `SpinApp`, and cold-starts fast enough that scale-to-zero is actually pleasant instead of a latency cliff.

## When I'd reach for it

My rule: Wasm workloads are for **new, well-scoped, event- or request-driven services** where cold start and density matter more than raw throughput or ecosystem breadth. Per-tenant business logic, webhook handlers, edge functions close to users, plugin systems where you run untrusted code — these fit beautifully because the sandbox and the fast start are exactly the properties you want.

What I would *not* do is try to migrate a mature Go or Java service to Wasm to chase a trend. The porting cost is real and the payoff for a long-running, chatty service is small. Run Wasm and containers side by side in the same cluster — that's the actual endgame here, not replacement. Kubernetes is happy to schedule both, and picking the runtime per workload is a feature, not a compromise.

Wasm on Kubernetes is past the toy stage and short of the boring, mature stage. If you have a workload shaped like its strengths, it's one of the more interesting tools available right now — just go in knowing which half of the tradeoff you're standing on.

## Resources

- [WebAssembly official site](https://webassembly.org/)
- [WASI — the WebAssembly System Interface](https://wasi.dev/)
- [runwasi (containerd)](https://github.com/containerd/runwasi)
- [SpinKube documentation](https://www.spinkube.dev/docs/)
- [Wasmtime runtime](https://wasmtime.dev/)
- [Kubernetes — RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/)
