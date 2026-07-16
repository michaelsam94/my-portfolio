---
title: "How Container Runtimes Work"
slug: "containers-oci-runtime-internals"
description: "Understand OCI container runtimes from docker run to runc: namespaces, cgroups, layers, image spec, and how Kubernetes invokes containerd."
datePublished: "2025-05-06"
dateModified: "2025-05-06"
tags: ["DevOps", "CI/CD"]
keywords: "OCI runtime, runc, containerd, cgroups namespaces, container internals, CRI Kubernetes"
faq:
  - q: "What is the difference between a container and a VM?"
    a: "Containers share the host kernel and isolate processes via Linux namespaces and cgroups—they are not separate operating systems. VMs run a full guest OS on hypervisor hardware virtualization. Containers start in milliseconds and use less memory; VMs provide stronger isolation boundaries for untrusted multi-tenant workloads."
  - q: "What does runc do?"
    a: "runc is the OCI reference runtime that creates container processes: sets up namespaces (PID, NET, MNT, UTS, IPC, USER), applies cgroup limits, configures root filesystem from image layers, and execs the container entrypoint. Higher-level tools like containerd and Docker invoke runc—most users never call runc directly."
  - q: "How does Kubernetes run containers?"
    a: "kubelet talks CRI (Container Runtime Interface) to containerd or CRI-O. containerd pulls OCI images, unpacks layers, creates a container spec, and calls runc (or runc-compatible runtime like crun). The pod sandbox (pause container) holds network namespace shared by app containers in the pod."
---

`docker run nginx` feels like magic—a command and a web server appears isolated on your laptop. Underneath it is a stack of specifications and Unix primitives: OCI image format, overlay filesystems, namespaces that fake process isolation, cgroups that cap CPU and memory, and a small binary called runc that actually starts the process. Knowing this stack helps when containers behave oddly in production: OOM kills that are cgroup limits, not app bugs; PID 1 signal handling; or why your image runs as root inside a user namespace.

## The OCI specifications

Open Container Initiative defines two specs:

**Image Spec** — manifest, config JSON, layer tarballs (filesystem diffs)

**Runtime Spec** — `config.json` describing how to execute: args, env, mounts, namespaces, cgroups path, user IDs

Any compliant runtime executes any compliant image—Docker Hub images run on Podman, containerd, etc.

## Layered filesystem

Images stack read-only layers:

```
┌─────────────────┐
│  App layer      │  COPY binary
├─────────────────┤
│  deps layer     │  npm install
├─────────────────┤
│  base OS layer  │  debian:12-slim
└─────────────────┘
       +
  container layer (RW copy-on-write)
```

Union mount (overlay2 on Linux) presents merged view. Writes go to thin RW layer; deletes create whiteouts. This enables image sharing—ten containers from same base share read-only layers.

## Linux namespaces (isolation)

| Namespace | Isolates |
|-----------|----------|
| PID | Process tree — container PID 1 is isolated |
| NET | Network interfaces, routes, iptables |
| MNT | Mount points — container root `/` |
| UTS | Hostname |
| IPC | Shared memory, semaphores |
| USER | UID/GID mapping — root in container ≠ root on host |
| cgroup | cgroup hierarchy view (cgroupns) |

`unshare` and `clone` system calls create namespace boundaries.

## cgroups (resource limits)

cgroups v2 limit and account resources:

```json
"linux": {
  "resources": {
    "memory": { "limit": 536870912 },
    "cpu": { "quota": 100000, "period": 100000 }
  }
}
```

Kubernetes `resources.limits.memory` maps to cgroup memory.max. Exceeding limit → OOM kill inside container, not host.

## runc execution flow

Simplified:

1. Read `config.json` (bundle directory with rootfs)
2. Create namespaces
3. Setup cgroups and apply limits
4. Pivot root to container rootfs (`pivot_root` or `chroot`)
5. Drop capabilities, set seccomp, AppArmor/SELinux labels
6. `execve` entrypoint process as PID 1

```bash
# OCI bundle layout
bundle/
  config.json
  rootfs/
```

`runc run mycontainer` executes the bundle.

## containerd and Docker's role

Docker Engine (containerd backend):

```
docker CLI → dockerd → containerd → runc
```

containerd handles:

- Image pull/push to registries
- Layer extraction and snapshot management
- Container lifecycle (create, start, stop, delete)
- CRI plugin for Kubernetes

Docker adds UX, buildkit, networking plugins—production K8s often skips dockerd entirely.

## Kubernetes pod model

Each pod:

1. **Pause container (sandbox)** — holds network namespace, infra container
2. **App containers** — join sandbox network, share optional volumes

```yaml
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      limits:
        memory: "512Mi"
        cpu: "500m"
```

kubelet → CRI → containerd creates two runc containers in shared net ns.

## Security boundaries

Containers are **not** VMs. Kernel exploits breaking isolation affect host. Mitigations:

- Run as non-root (`USER` in Dockerfile)
- Drop capabilities (`CAP_DROP ALL`, add minimal)
- seccomp profile limiting syscalls
- read-only root filesystem
- gVisor/Kata for kernel isolation when needed

## Debugging internals

```bash
# Inspect running container namespaces
docker inspect --format '{{.State.Pid}}' mycontainer
ls -la /proc/$PID/ns/

# cgroup memory current
cat /sys/fs/cgroup/system.slice/.../memory.current
```

`nsenter` enters namespaces for troubleshooting:

```bash
nsenter -t $PID -m -u -i -n -p -- bash
```

## containerd vs Docker architecture

Docker is a developer experience layer; containerd is the production runtime:

```
docker CLI → dockerd → containerd → runc → container process
kubectl    → kubelet → containerd → runc → container process
```

containerd handles image pull, storage, and container lifecycle. runc creates the actual isolated process. Docker adds build, network, and volume management for developer workflows.

In Kubernetes, kubelet talks directly to containerd (or CRI-O) — Docker is not in the path since Kubernetes 1.24 removed dockershim.

## Image layers and overlay filesystem

Container images are layered tar archives:

```
Layer 1: base OS (ubuntu:22.04)     — 77MB
Layer 2: apt install python3          — 45MB
Layer 3: COPY app.py /app/          — 2KB
Layer 4: RUN pip install -r req.txt — 120MB
```

Overlay filesystem merges layers read-only; container writes go to a thin writable layer:

```
Lower layers (read-only): Layer1 + Layer2 + Layer3 + Layer4
Upper layer (writable):    container runtime changes
Merged view:               what the container process sees
```

Shared layers between images save disk — 10 containers from same base image share Layer 1 on disk once.

## CRI-O vs containerd

Both implement Kubernetes Container Runtime Interface:

| | containerd | CRI-O |
|---|---|---|
| Origin | Docker donated to CNCF | Red Hat, Kubernetes-native |
| Ecosystem | Broader tooling | OpenShift default |
| Features | Rich (namespaces, snapshots) | Minimal, K8s-focused |
| Adoption | Default on most K8s distros | OpenShift, Fedora CoreOS |

Choose containerd unless on OpenShift. Both use OCI spec and runc under the hood — container images are interchangeable.

## Failure modes

- **Running as root in container** — UID 0 inside container; use USER directive
- **No resource limits** — container consumes all host memory; set cgroup limits
- **Writable root filesystem** — attacker modifies binaries; use read-only rootfs
- **Privileged container** — bypasses all namespaces; avoid unless absolutely required
- **Image layer cache exhaustion** — disk full from accumulated layers; prune regularly

## Production checklist

- Containers run as non-root user (USER in Dockerfile)
- Memory and CPU cgroup limits set (K8s requests/limits)
- Read-only root filesystem where possible
- seccomp profile limiting syscalls
- containerd (not Docker) as K8s runtime
- Regular image prune to prevent disk exhaustion

## Common production mistakes

Teams get oci runtime internals wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of oci runtime internals fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec)
- [runc documentation](https://github.com/opencontainers/runc)
- [containerd architecture](https://containerd.io/docs/)
- [Kubernetes CRI](https://kubernetes.io/docs/concepts/architecture/cri/)
