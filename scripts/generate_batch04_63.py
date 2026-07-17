#!/usr/bin/env python3
"""Generate 63 batch-04 DevOps blog posts with topic-specific deep dives."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

BLOG = Path("/Users/michael/Desktop/my-portfolio/content/blog")
PROGRESS = Path("/Users/michael/Desktop/my-portfolio/scripts/humanize-progress/batch-04.json")
TODAY = "2026-07-17"
MIN_WC = 1200

FORBIDDEN = [
    "What broke first on dashboards",
    "What changes when you leave the tutorial",
    "Operating ",
    "Handoff to adjacent teams",
    "Sustaining the practice long term",
    "leading metric tied to",
    "Reference configuration",
    "@task(retries=3",
]

SLUGS = [
    "devops-dbt-incremental-models",
    "devops-dbt-semantic-layer",
    "devops-dbt-exposures-lineage",
    "devops-ebpf-observability-cilium",
    "devops-dynamodb-feature-serving",
    "devops-dbt-snapshot-strategies",
    "devops-egress-cost-optimization",
    "devops-dimensional-modeling-pitfalls",
    "devops-dbt-run-hooks-ops",
    "devops-dbt-star-schema-design",
    "devops-dependency-latency-injection",
    "devops-dns-failure-injection",
    "devops-dind-rootless-buildkit",
    "devops-deployment-gates-smoke-tests",
    "devops-ephemeral-storage-limits",
    "devops-egress-filtering-dns",
    "devops-etcd-backup-restore-ops",
    "devops-downward-api-metadata",
    "devops-database-connection-pools",
    "devops-model-serving-warm-pools",
    "devops-model-serving-triton",
    "devops-model-serving-quantization",
    "devops-dbt-cicd-testing",
    "devops-helm-library-chart-patterns",
    "devops-data-versioning-dvc",
    "devops-helmfile-multi-env",
    "devops-helm-chart-testing-ct-lint",
    "devops-model-serving-multi-model",
    "devops-helm-dependency-management",
    "devops-helm-secrets-sops",
    "devops-helm-values-schema-validation",
    "devops-helm-diff-pre-deploy",
    "devops-helm-governance-standards",
    "devops-helm-rollback-strategies",
    "devops-helm-chart-signing-provenance",
    "devops-container-image-signing-cosign",
    "devops-helm-hooks-weight-order",
    "devops-model-serving-fallback-models",
    "devops-otel-auto-instrumentation",
    "devops-chaos-mesh-network-faults",
    "devops-helm-release-health-checks",
    "devops-otel-collector-pipelines",
    "devops-multi-region-capacity",
    "devops-overcommit-ratio-tuning",
    "devops-multi-cloud-cost-benchmark",
    "devops-helm-starter-chart-scaffolding",
    "devops-network-partition-simulation",
    "devops-observability-cost-control",
    "devops-oncall-runbook-automation",
    "devops-network-policy-audit",
    "devops-gpu-scheduling-ml-workloads",
    "devops-network-policies-default-deny",
    "devops-opentelemetry-logs-bridge",
    "devops-helm-oci-registry-migration",
    "devops-grafana-dashboard-as-code",
    "devops-pci-dss-scope-reduction",
    "devops-pipeline-cost-allocation",
    "devops-headroom-policy-enforcement",
    "devops-gitops-drift-detection",
    "devops-circleci-orb-patterns",
    "devops-monorepo-path-filters",
    "devops-container-image-scanning-gate",
    "devops-node-pool-rightsizing",
]

# Import article bodies from companion module
from batch04_63_bodies import ARTICLES  # noqa: E402


def wc(text: str) -> int:
    return len(re.sub(r"```.*?```", "", text, flags=re.DOTALL).split())


def read_existing_fm(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        raise ValueError(f"No frontmatter in {slug}")
    return yaml.safe_load(m.group(1))


def write_post(slug: str, article: dict) -> int:
    fm = read_existing_fm(slug)
    fm["faq"] = article["faq"]
    fm["dateModified"] = TODAY
    if "description" in article:
        fm["description"] = article["description"]
    header = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = article["body"].strip()
    for forbidden in FORBIDDEN:
        if forbidden in body:
            raise ValueError(f"{slug} contains forbidden pattern: {forbidden!r}")
    (BLOG / f"{slug}.md").write_text(f"---\n{header}---\n\n{body}\n")
    return wc(body)


def main():
    missing = [s for s in SLUGS if s not in ARTICLES]
    if missing:
        print(f"Missing articles: {missing}")
        return 1
    counts = {}
    for slug in SLUGS:
        counts[slug] = write_post(slug, ARTICLES[slug])
    prog = json.loads(PROGRESS.read_text())
    done = set(prog.get("done", []))
    done.update(SLUGS)
    prog["done"] = sorted(done)
    prog["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    prog["notes"] = f"Rewrote 63 DevOps batch-04 posts; all slugs merged into done array"
    prog["batch04_63_complete"] = True
    PROGRESS.write_text(json.dumps(prog, indent=2) + "\n")
    low = [s for s, w in counts.items() if w < MIN_WC]
    print(f"Written {len(counts)} posts. Below {MIN_WC} words: {len(low)}")
    if low:
        for s in low:
            print(f"  LOW {counts[s]} {s}")
    else:
        samples = sorted(counts.items(), key=lambda x: -x[1])[:3]
        for s, w in samples:
            print(f"  SAMPLE {w} {s}")
    return 0 if not low else 1


if __name__ == "__main__":
    raise SystemExit(main())
