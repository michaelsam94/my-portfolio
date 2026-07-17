---
title: "AI Agents: Container Image Scanning Gate"
slug: "agent-container-image-scanning-gate"
description: "Gate agent deployments with container image scanning—CVE policy tiers, SBOM-aware exceptions, admission control, and CI pipelines that block bad images without blocking model iteration."
datePublished: "2025-11-11"
dateModified: "2025-11-11"
tags: ["AI", "Agent", "Container"]
keywords: "container image scanning, CVE gate, admission controller, Trivy, agent Docker security, SBOM policy, supply chain"
faq:
  - q: "Where should image scanning run for agent workloads—CI, registry, or cluster admission?"
    a: "All three, with different jobs. CI fails builds on critical CVEs in base layers you control. Registry scanning catches images promoted from untrusted paths and rescan when vulnerability databases update. Admission control is the last line—it blocks pull even if someone bypasses CI with a manual tag push."
  - q: "How do scanning gates handle ML base images with many transitive CVEs?"
    a: "Use tiered policies: block critical and high with known fixes in your base image lineage; ticket medium on SLA; allowlist only with expiry, owner, and compensating controls. Scan the full filesystem including Python wheels and CUDA libs—agent images are fatter than typical microservices and accumulate silent debt."
  - q: "Should agent images be rebuilt when only the vulnerability DB changes?"
    a: "Yes for production promotion paths. A clean scan yesterday does not mean clean today. Rescan on deploy and nightly; trigger rebuilds when upstream base images publish patches. Pin digests in manifests, not mutable latest tags."
  - q: "What breaks if scanning gates only check OS packages and ignore application layers?"
    a: "You miss CVEs in pip, npm, and bundled model weights loaded from compromised upstreams. Filesystem scanners and SBOM generators must include language ecosystems. Agent stacks often ship fifty-plus Python packages; OS-only scanning gives false confidence."
---
The security review asked a reasonable question: "How do you know the agent inference image running in production does not contain a critical OpenSSL CVE?" Engineering answered "we use Docker." That was not an answer—it was a category error. Building a container and scanning a container are different controls. Agent teams ship large images fast; without a scanning gate, every deploy is a supply-chain bet.

Container image scanning gates turn "trust me, I ran apt upgrade" into an enforceable policy: no workload schedules unless the image digest passes vulnerability thresholds, provenance checks, and optional SBOM attestation. For AI agent platforms—where images bundle orchestration code, tool runtimes, and sometimes local model weights—the gate is as important as network policy.

## Defense in depth: three enforcement points

```
Developer push → CI scan (build fail) → Registry scan (quarantine) → Deploy → Admission webhook (reject)
```

| Stage | Catches | Agent-specific note |
|-------|---------|---------------------|
| CI | Bad Dockerfile layers before merge | Cache-heavy builds may skip rescan without explicit step |
| Registry | Re-scan on DB update, rogue tags | Model-serving images re-tagged across envs |
| Admission | Manual bypass, stale promotions | Last chance before GPU nodes pull |

Each stage should emit the same **policy result schema** so teams do not reconcile three different severities for the same CVE.

## Policy design that teams can live with

Naive "zero CVEs" policies fail on day one. Agent images inherit CUDA, PyTorch, and distro packages with hundreds of findings. Effective policies combine:

**Severity thresholds** — block `CRITICAL` with fix available; warn on `HIGH`; track `MEDIUM` with 30-day SLA.

**Fix availability** — ignore unfixed upstream issues only with documented risk acceptance, not silent suppression.

**Scope by image class** — stricter on `agent-worker` (network egress, tool access) than on offline batch eval images.

**Time-bounded exceptions** — exception records include CVE id, owner, expiry, compensating control (WAF rule, network deny).

```yaml
# policy/agent-images.rego (OPA-style example)
deny[msg] {
  input.image.class == "agent-worker"
  some vuln in input.scan.vulnerabilities
  vuln.severity == "CRITICAL"
  vuln.fix_available == true
  not exception_valid(vuln.id, input.image.digest)
  msg := sprintf("critical fixed CVE %s in %s", [vuln.id, input.image.name])
}
```

Review exceptions weekly; agents change fast and yesterday's compensating control may no longer apply.

## CI integration with Trivy or Grype

Scan in the pipeline after `docker build` and before push:

```yaml
# .github/workflows/agent-image.yml (excerpt)
- name: Build agent worker
  run: docker build -t ghcr.io/acme/agent-worker:${{ github.sha }} .

- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/acme/agent-worker:${{ github.sha }}
    format: sarif
    severity: CRITICAL,HIGH
    exit-code: 1
    ignore-unfixed: true

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: trivy-results.sarif
```

Pin scanner versions. Vulnerability matching changes between Trivy releases; unpinned scanners create flaky CI.

Generate SBOM alongside scan:

```bash
trivy image --format spdx-json -o sbom.spdx.json ghcr.io/acme/agent-worker:${SHA}
cosign attest --predicate sbom.spdx.json --type spdx ghcr.io/acme/agent-worker:${SHA}
```

Attach SBOM attestations so admission can verify package inventory matches scan subject.

## Registry scanning and digest promotion

Tags lie; digests do not. Promotion flow:

1. CI pushes `agent-worker:sha-abc123` and scan passes.
2. Staging deploy references digest `sha256:def...`.
3. Production promotion copies digest, not retag of `latest`.
4. Registry webhook rescan on CVE DB bump; if policy fails, mark digest quarantined and alert.

Quarantined digests still run until replaced—that is intentional. Gates stop **new** schedules; rolling replacement is a deploy concern, not a scanner toggle.

For agent platforms with frequent hotfixes, maintain a **fast lane** with tighter scope (single-service patch) but identical scan rigor—no lane skips scanning.

## Kubernetes admission control

Deploy a validating webhook (Kyverno, OPA Gatekeeper, or cloud-native policy) that rejects pods whose image digest lacks a passing scan record:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-agent-image-scan
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-scan-annotation
      match:
        any:
          - resources:
              kinds: [Pod]
              selector:
                matchLabels:
                  app.kubernetes.io/component: agent-worker
      validate:
        message: "Image missing valid scan attestation"
        pattern:
          metadata:
            annotations:
              scan.acme.com/result: "pass"
              scan.acme.com/digest: "?*"
```

Your CI/CD pipeline writes annotations or signs images with Cosign predicates consumed by policy. Manual `kubectl run` with unscanned images should fail closed.

## Agent image composition risks

Agent Dockerfiles often:

- `pip install` fifty packages from PyPI without hash pinning
- Copy local tool binaries from unverified sources
- Bundle Hugging Face weights via curl without checksum verify
- Run as root for convenience

Scanning gates surface CVEs, but **preventive Dockerfile review** reduces noise:

```dockerfile
FROM python:3.12-slim-bookworm@sha256:...

RUN pip install --no-cache-dir -r requirements.txt \
    --require-hashes

USER 65532:65532
COPY --chown=65532:65532 agent/ /app/agent/
```

Multi-stage builds drop compiler toolchains from runtime layers—fewer packages, smaller attack surface, faster scans.

## Handling false positives and scanner disagreement

Different scanners disagree on severity and fix status. Pick a **primary scanner** for gating and ingest others as advisory. When developers dispute findings:

1. Verify CVE applies to actually installed version (not phantom DB match).
2. Check if vulnerable code path is reachable in agent runtime.
3. If false positive, file upstream scanner issue and add time-boxed ignore with CVE justification.

Document ignores in version-controlled policy files—never only in SaaS UI.

## Operational metrics

Track:

- `scan_fail_rate` by image class
- `mean_time_to_remediate` critical CVEs
- `exception_count` and `exception_expired`
- `admission_reject_rate`
- `deployments_blocked` (should correlate with scan failures, not webhook outages)

Alert on webhook availability—if admission is down, clusters often fail open or halt all deploys. Both are bad; prefer fail closed for agent workers with egress.

## Incident response when a critical CVE lands mid-week

1. Registry rescan flags running digests.
2. Identify workloads via image digest index, not tag.
3. Build patched image from updated base; emergency scan lane.
4. Roll workers with surge capacity; drain long agent runs gracefully.
5. Postmortem: why was package in image—direct dep or transitive bloat?

Keep a runbook that names who can grant exceptions and maximum exception duration without VP approval.

## Signing, provenance, and trusted base images

Scanning answers "what vulnerabilities exist?" Provenance answers "who built this and from what sources?" For agent images, chain both:

- Build in CI from tagged Dockerfiles in your org repo—no manual `docker commit`.
- Sign images with Cosign or Notary v2; admission verifies signature before scan annotation check.
- Prefer hardened base images (distroless, slim LTS) maintained by your platform team over ad-hoc `python:latest`.

```bash
# Verify before deploy
cosign verify --certificate-identity-regexp '.*@acme.com' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/acme/agent-worker@${DIGEST}
```

Distroless reduces CVE surface but complicates debugging—maintain a debug variant tagged separately and blocked from production admission. Agent on-call engineers need a documented path to shell into troubleshooting images without bypassing scan gates in prod.

## Related concepts

Image scanning connects to [SBOM generation in CI](https://blog.michaelsam94.com/agent-sbom-generation-ci/) and [pod security standards](https://blog.michaelsam94.com/agent-pod-security-standards/). Gates enforce what those practices produce.

## The takeaway

A container image scanning gate is enforceable supply-chain hygiene—not a checkbox scan in CI that everyone ignores when deadlines loom. Layer CI, registry, and admission enforcement; use severity-plus-fix-available policies suited to fat agent images; pin digests and SBOM attestations. When security asks how you know the image is safe, you show policy results tied to the digest running on the cluster—not a Dockerfile from last quarter.

## Resources

- [Trivy documentation](https://aquasecurity.github.io/trivy/) — filesystem and image scanning
- [Anchore Grype](https://github.com/anchore/grype) — alternative vulnerability matcher
- [Sigstore Cosign](https://docs.sigstore.dev/cosign/overview/) — sign and verify scan attestations
- [Kyverno verifyImages policies](https://kyverno.io/docs/writing-policies/verify-images/) — admission based on signatures
- [NSA Kubernetes Hardening Guidance](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/2716980/nsa-cisa-release-kubernetes-hardening-guidance/) — container supply chain context
