---
title: "Runtime Security with Falco and eBPF"
slug: "runtime-security-falco-ebpf"
description: "Runtime security with Falco and eBPF: how syscall-level threat detection works, writing rules that don't drown you in noise, and where it fits in defense in depth."
datePublished: "2026-03-15"
dateModified: "2026-07-17"
tags: ["Security", "Kubernetes", "Observability"]
keywords: "runtime security, Falco, eBPF security, threat detection, syscall monitoring, container runtime security"
faq:
  - q: "What is runtime security?"
    a: "Runtime security is the practice of detecting and responding to threats while workloads are actually running, as opposed to scanning images or code before deployment. It watches live behavior — system calls, process launches, network connections, file access — and flags activity that indicates compromise, such as a web server suddenly spawning a shell."
  - q: "How does Falco use eBPF?"
    a: "Falco uses an eBPF program loaded into the Linux kernel to observe system calls with very low overhead and without kernel modules. Every syscall of interest is streamed to Falco's userspace engine, which evaluates it against a set of rules and raises alerts on matches. eBPF is what makes this deep visibility safe and performant enough for production."
  - q: "Does runtime security replace image scanning?"
    a: "No — they're complementary layers. Image scanning and SBOMs catch known-vulnerable components before deploy; runtime security catches what actually happens at execution, including zero-days and misuse that no scan could predict. A mature program runs both, since each covers the other's blind spot."
faqAnswers:
  - question: "When is runtime security falco ebpf the wrong tool?"
    answer: "Skip runtime security falco ebpf when a simpler control or library already covers the failure mode, or when the operational cost exceeds the risk reduction for your threat model."
  - question: "What should I measure after adopting runtime security falco ebpf?"
    answer: "Track a leading signal (coverage, error class rate, or latency) and a lagging outcome (incidents, CVEs exploited, or user-visible failures) tied specifically to runtime security falco ebpf."
  - question: "How do I roll back a bad runtime security falco ebpf change?"
    answer: "Keep the previous config/version behind a flag or previous artifact; verify the rollback path in staging once, then document the one-command revert for on-call."
---
Most security tooling checks your software before it runs. Runtime security watches what it does once it's actually running — and that's where you catch the attacks that scanning can't predict. Runtime security is the practice of observing live workload behavior (system calls, process execution, file and network activity) and flagging the patterns that indicate compromise: a database container spawning `/bin/bash`, a process reading `/etc/shadow`, an unexpected outbound connection to a fresh IP. [Falco](https://falco.org/), a CNCF project, does this by tapping the Linux kernel through eBPF and matching a stream of syscalls against rules in real time.

I added Falco to a cluster after an incident where a compromised dependency did exactly nothing a pre-deploy scan would have caught — the malicious behavior only showed up at runtime. That's the gap this closes. Here's how it works and how to run it without generating an alert firehose nobody reads.

## Why syscalls are the right vantage point

Almost everything a process does that matters for security eventually becomes a system call. Opening a file, spawning a child process, making a network connection, changing permissions — all syscalls. If you can observe syscalls reliably and cheaply, you can see the ground truth of what a workload is doing, regardless of what language it's written in or how it was packaged.

The historical problem was cost and safety. Watching every syscall used to mean kernel modules (fragile, dangerous) or `ptrace`-style interception (slow). [eBPF](https://ebpf.io/) changed the economics: you load a small, verified program into the kernel that observes events and streams them to userspace with minimal overhead and no custom kernel module. The kernel's verifier guarantees your eBPF program can't crash the system. This is the same technology that powers modern [eBPF-based observability with OpenTelemetry](https://blog.michaelsam94.com/ebpf-observability-opentelemetry-obi/) — the security use case is the same instrumentation aimed at threats instead of latency.

## How Falco is wired

The architecture is straightforward: an eBPF program in the kernel captures syscalls, Falco's userspace engine enriches them with container and Kubernetes metadata (which pod, which image, which namespace), and a rules engine evaluates each event. Matches produce alerts routed to stdout, a file, gRPC, or — via Falcosidekick — to Slack, a SIEM, or an alerting pipeline.

That metadata enrichment is what makes it useful in Kubernetes. A raw syscall alert saying "process 4821 opened /etc/shadow" is nearly useless. "Container `payments-api` (image `acme/payments:2.3`) in namespace `prod` read /etc/shadow" is actionable.

## Writing rules that don't drown you

Falco ships with a solid default ruleset, and your first instinct will be to enable all of it. Don't — not without tuning. The default rules are broad on purpose, and in a real cluster they'll fire constantly on legitimate behavior (package managers, init scripts, monitoring agents). Alert fatigue kills runtime security faster than any attacker; if every alert is noise, the real one gets ignored.

A Falco rule is YAML: a condition over syscall fields, plus output and priority.

```yaml
- rule: Shell spawned in web container
  desc: A shell was executed inside a container that should never need one
  condition: >
    spawned_process
    and container
    and shell_procs
    and container.image.repository in (acme/payments, acme/frontend)
  output: >
    Shell in web container
    (user=%user.name container=%container.name
     image=%container.image.repository cmdline=%proc.cmdline)
  priority: CRITICAL
  tags: [container, shell, mitre_execution]
```

The discipline that keeps this signal-rich:

- **Scope by image or namespace.** A shell in a build container is normal; a shell in `payments-api` is an incident. Encode that difference.
- **Build allowlists, not just blocklists.** Define what a workload *should* do and alert on deviation. This is far more robust than trying to enumerate every bad thing.
- **Tune iteratively.** Run in a low-priority "audit" mode first, collect a week of real behavior, then promote rules to alerting once you've suppressed the legitimate noise.
- **Tag with MITRE ATT&CK.** Mapping rules to attack techniques makes triage and reporting far easier.

## What it catches that nothing else does

Concretely, the class of threats runtime detection owns:

| Threat | Runtime signal Falco sees |
| --- | --- |
| Reverse shell from exploited service | Web process spawns shell + outbound connect |
| Container escape attempt | Sensitive mount access, privileged syscall |
| Cryptominer | Unexpected binary, sustained CPU, mining pool DNS |
| Credential theft | Read of `/etc/shadow`, cloud metadata endpoint |
| Supply-chain payload | New process not in the image's known set |

None of these are visible to a pre-deploy scanner, because they're *behaviors*, not *artifacts*. A vulnerable package might sit dormant for months; runtime security only fires when it's actually abused. That's the complement to artifact-based controls like [container image security and SBOMs](https://blog.michaelsam94.com/container-image-security-sbom/) — scanning tells you what could go wrong, runtime tells you what is going wrong.

## The honest limitations

Falco detects; it doesn't, by default, prevent. It tells you a shell spawned in your payments container after the fact. You can wire responses (kill the pod, quarantine the node) through Falcosidekick and response engines, but that automation carries its own risk — an aggressive auto-kill rule with a false positive can take down production. I keep enforcement conservative and let humans make the kill decision for anything short of the most unambiguous signals.

There's also overhead. eBPF is cheap, not free; on very high-syscall-rate workloads you'll pay a few percent CPU, and you should measure it rather than assume. And rules are only as good as your understanding of normal — the tuning work is real and ongoing, not a one-time setup.

## Where it fits

Runtime security is one layer of defense in depth, not a silver bullet. It sits downstream of secure images, least-privilege RBAC, network policies, and admission control. Its unique contribution is catching the unknown-unknowns — the behavior no pre-deploy check anticipated — with kernel-level ground truth. For any cluster running third-party code or exposed to the internet, that's a layer I now consider mandatory rather than optional. Set it up in audit mode, tune it until the signal is trustworthy, and you'll have visibility into the one phase of the software lifecycle that most tooling ignores: the part where it's actually running.

## Rule tuning before alert fatigue

Stock `Write below etc` fired 40k/min on CNI paths — real escape attempt buried in noise. Start new rules log-only seven days; promote with platform sign-off. Macro exceptions for known kubelet paths documented in rule YAML comment linking upstream issue.

## Rule tuning before alert fatigue

Stock `Write below etc` fired 40k/min on CNI paths — real escape attempt buried in noise. Start new rules log-only seven days; promote with platform sign-off. Macro exceptions for known kubelet paths documented in rule YAML comment linking upstream issue.

## Resources

- [Falco — official site](https://falco.org/)
- [Falco documentation and rules](https://falco.org/docs/)
- [eBPF — official site](https://ebpf.io/)
- [Falco project (GitHub, CNCF)](https://github.com/falcosecurity/falco)
- [MITRE ATT&CK for Containers](https://attack.mitre.org/matrices/enterprise/containers/)
- [Linux kernel — eBPF documentation](https://docs.kernel.org/bpf/)

## Failure modes specific to runtime security falco ebpf

Operating runtime security falco ebpf well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For runtime security falco ebpf:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified runtime security falco ebpf stops moving — sunsetting is a feature.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Migration path into runtime security falco ebpf

Reviewers should challenge assumptions encoded in runtime security falco ebpf: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for runtime security falco ebpf: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for runtime security falco ebpf: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for runtime security falco ebpf: bad config shipped — prove rollback within the declared RTO without data corruption.

## Post-incident changes after runtime security falco ebpf failures

Roll out runtime security falco ebpf behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for runtime security falco ebpf

Detail 1 (771): for runtime security falco ebpf, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for runtime security falco ebpf becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break runtime security falco ebpf, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about runtime security falco ebpf: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing runtime security falco ebpf

Detail 2 (416): for runtime security falco ebpf, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing runtime security falco ebpf becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break runtime security falco ebpf, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about runtime security falco ebpf: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.