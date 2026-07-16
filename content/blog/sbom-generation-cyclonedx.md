---
title: "Generating SBOMs with CycloneDX"
slug: "sbom-generation-cyclonedx"
description: "Produce CycloneDX SBOMs in CI for every build: tooling by ecosystem, VEX linkage, and ingestion into dependency scanners."
datePublished: "2025-05-11"
dateModified: "2025-05-11"
tags: ["Security", "Supply Chain", "SBOM", "DevSecOps"]
keywords: "CycloneDX SBOM, software bill of materials, supply chain security, SBOM generation CI, SPDX vs CycloneDX, VEX"
faq:
  - q: "CycloneDX or SPDX?"
    a: "Both are NTIA-minimum-element compliant. CycloneDX integrates tightly with OWASP Dependency-Track and security tooling via VEX and vulnerability extensions. SPDX excels at license compliance documentation. Many organizations generate CycloneDX for security ops and export SPDX for legal when needed—tools convert between formats."
  - q: "When should the SBOM be generated?"
    a: "Generate at build time from lockfiles and actual resolved artifacts, not from hand-edited manifests alone. Attach SBOMs to container images as OCI referrer artifacts or release assets. Rebuild SBOM when lockfiles change even if application code does not—dependency drift is the point."
  - q: "Does an SBOM replace vulnerability scanning?"
    a: "No. The SBOM is inventory; scanners match inventory to CVE databases. Without continuous scanning, yesterday's clean SBOM misses today's published CVE. Pipe SBOMs into Dependency-Track or Grype on every build and alert on new matches against deployed versions."
---

Executive order memos and customer security questionnaires now ask for SBOMs attached to every release artifact. An SBOM without automation is a PDF fiction—stale the day after npm install. CycloneDX JSON (or XML) lists components, hashes, and dependencies in machine-readable form so Grype, Dependency-Track, and procurement portals ingest them. The work is wiring generation into CI so every image and JAR carries provably current inventory.

## Minimum viable pipeline

```yaml
- name: Generate CycloneDX SBOM
  run: |
    npm ci
    npx @cyclonedx/cyclonedx-npm --output-file sbom.json
- name: Scan SBOM
  run: grype sbom:sbom.json --fail-on high
- name: Upload artifact
  uses: actions/upload-artifact@v4
  with:
    name: sbom-${{ github.sha }}
    path: sbom.json
```

Pin CycloneDX CLI versions. Scan the SBOM, not just `package-lock.json`—transitive resolution belongs in the bill.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Ecosystem tooling

| Ecosystem | Tool |
|-----------|------|
| Node.js | `@cyclonedx/cyclonedx-npm` |
| Java/Maven | `cyclonedx-maven-plugin` |
| Python | `cyclonedx-bom` |
| Rust | `cargo-cyclonedx` |
| Containers | Syft → CycloneDX export |

For Docker images, run Syft on the final image layers—devDependencies in build stages should not appear if multi-stage builds discard them.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Component identity

Each component needs `name`, `version`, and `purl` (package URL):

```
pkg:npm/lodash@4.17.21
```

Hashes (`SHA-256` of downloaded artifact) prove integrity when registries republish. Include `supplier` and `licenses` fields for enterprise procurement reviews.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Publishing with artifacts

Attach to OCI images:

```bash
cosign attach sbom --sbom sbom.json ghcr.io/org/app:1.2.3
```

Or store in release alongside binaries with immutable retention. Tag SBOM filename with git SHA, not only semver—hotfix rebuilds share tags.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## VEX and false positives

When analysis proves a CVE is not exploitable in your configuration, publish a CycloneDX VEX document linking to the SBOM component and status `not_affected` with justification. Scanners that understand VEX reduce noise without hiding real issues.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Operational integration

Dependency-Track ingests SBOMs via API on each deploy, diffing against previous bomVersion. Alert when new critical CVE affects production component versions. Map project version to git tag for traceability during incident response.

Attach SBOMs to OCI images as referrer artifacts or release assets. Tag filename with git SHA, not only semver—hotfix rebuilds may share tags. Cosign attach sbom binds digest to CI run that passed scan.

VEX documents link not_affected status when exploit preconditions do not apply. Scanners that understand VEX reduce noise without hiding real issues. Dependency-Track diffs bomVersion on deploy—alert when new critical CVE affects production component versions.

Pin CycloneDX CLI versions in CI. Scan the SBOM output, not just manifest ranges—transitive resolution is the point of the bill of materials.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [CycloneDX specification](https://cyclonedx.org/specification/overview/)
- [OWASP Dependency-Track](https://dependencytrack.org/)
- [Anchore Syft](https://github.com/anchore/syft)
- [NTIA SBOM minimum elements](https://www.ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom)
- [CISA SBOM community guidance](https://www.cisa.gov/sbom)
