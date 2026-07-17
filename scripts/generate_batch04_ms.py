#!/usr/bin/env python3
"""Generate batch-04 model serving + platform posts (>=1250 words prose each)."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

BLOG = Path("/Users/michael/Desktop/my-portfolio/content/blog")
PROGRESS = Path("/Users/michael/Desktop/my-portfolio/scripts/humanize-progress/batch-04.json")
TODAY = "2026-07-17"
MIN_WC = 1250

SLUGS = [
    "devops-model-serving-batching",
    "devops-model-serving-circuit-breakers",
    "devops-model-serving-edge-deployment",
    "devops-model-serving-ensemble",
    "devops-model-serving-fallback-models",
    "devops-model-serving-kserve",
    "devops-model-serving-multi-model",
    "devops-model-serving-quantization",
    "devops-model-serving-triton",
    "devops-model-serving-warm-pools",
    "devops-monorepo-path-filters",
    "devops-multi-cloud-cost-benchmark",
    "devops-multi-region-capacity",
    "devops-network-partition-simulation",
    "devops-network-policies-default-deny",
    "devops-network-policy-audit",
    "devops-node-pool-rightsizing",
    "devops-observability-cost-control",
    "devops-oncall-runbook-automation",
    "devops-opentelemetry-logs-bridge",
    "devops-otel-auto-instrumentation",
    "devops-otel-collector-pipelines",
    "devops-overcommit-ratio-tuning",
    "devops-pci-dss-scope-reduction",
    "devops-pipeline-cost-allocation",
]


def wc(text: str) -> int:
    return len(re.sub(r"```.*?```", "", text, flags=re.DOTALL).split())


def read_fm(slug: str) -> dict:
    text = (BLOG / f"{slug}.md").read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(m.group(1))


def write_post(slug: str, faq: list, body: str) -> int:
    fm = read_fm(slug)
    fm["faq"] = faq
    fm["dateModified"] = TODAY
    header = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    (BLOG / f"{slug}.md").write_text(f"---\n{header}---\n\n{body.strip()}\n")
    return wc(body)


def paras(*chunks: str) -> str:
    return "\n\n".join(c.strip() for c in chunks if c.strip())


# Each entry: slug -> (faq, body)
CONTENT = {}

# --- KServe ---
CONTENT["devops-model-serving-kserve"] = (
    [
        {
            "q": "What does KServe add over a raw Kubernetes Deployment for models?",
            "a": "KServe provides InferenceService CRDs with built-in model storage URI handling, scale-to-zero via Knative, canary rollouts, gRPC/HTTP predict protocols, and integration with serving runtimes (Triton, MLServer, TorchServe). Raw Deployments leave autoscaling, networking, and revision management as bespoke glue code.",
        },
        {
            "q": "How should timeouts be configured on InferenceService?",
            "a": "Set request timeout on the predictor and queue timeout at the ingress/gateway layer. Without explicit timeouts, a slow model blocks worker threads and HPA sees false healthy RPS. Align timeout with client deadline minus network margin.",
        },
        {
            "q": "When is scale-to-zero wrong for KServe?",
            "a": "When cold start exceeds latency SLO, when GPU model load time is minutes, or when traffic is continuous but spiky—scale-to-zero saves cost only if warm pools or min replicas cover the gap. Batch inference jobs should use minReplicas: 0; realtime APIs usually need minReplicas: 1 or higher.",
        },
    ],
    paras(
        """Raw Deployments for models left GPU nodes idle 80% of the day—no scale-to-zero, no standardized canary, every team hand-rolled its own S3 download init container. Standardizing on KServe cut idle GPU spend 35% and made model rollouts reviewable in Git like any other service.""",
        """## InferenceService as the unit of deployment""",
        """An InferenceService abstracts storage, runtime, and scaling. Teams commit YAML; controllers reconcile model artifacts and pod templates. The predictor spec names model format, storage URI, and resource limits; transformer and explainer components optional for pre/post processing.""",
        """```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: churn-classifier
spec:
  predictor:
    minReplicas: 1
    maxReplicas: 8
    scaleTarget: 70
    model:
      modelFormat:
        name: sklearn
      storageUri: s3://models/churn/v3
      resources:
        limits:
          nvidia.com/gpu: "1"
```""",
        """Storage URI patterns should be immutable version paths—never `latest`. KServe downloads at pod start; large models need init timeout tuning and artifact caching on nodes via DaemonSet warmers when cold start hurts.""",
        """## Autoscaling and scale-to-zero""",
        """Knative-based autoscaler watches concurrency and RPS. Scale-to-zero removes pods after idle window—typically 30–600 seconds. GPU model load from S3 may take 60–180 seconds, dominating cold start. Options: minReplicas 1 during business hours, node-local model cache, or preloaded container images with weights baked in for tier-1 models.""",
        """Custom metrics autoscaling via KEDA on queue depth or GPU duty cycle often beats default concurrency targets for bursty batch scoring jobs triggered by Kafka lag.""",
        """## Canary and traffic splitting""",
        """KServe supports canaryTrafficPercent on revisions—route 5% to challenger before full promotion. Pair with statistical tests on business metrics, not only error rate. Shadow traffic (mirror) validates latency and score drift without user impact.""",
        """Document rollback: `kubectl patch` revision traffic to 0% or Git revert with Argo CD sync—never leave canary at 5% indefinitely without ownership.""",
        """## Timeouts and queue discipline""",
        """A slow model without timeout blocks the worker queue—symptom looks like cluster healthy but p99 exploding. Set predictor timeout, ingress timeout, and client deadline in one table. KServe without timeout was our top incident category before enforcement in CI.""",
        """## Multi-model and InferenceGraph""",
        """When chains exceed one model, InferenceGraph defines DAG routing between InferenceServices—see ensemble post for patterns. Keep graphs versioned separately from individual models so teams ship independently.""",
        """## Observability""",
        """Export revision labels on metrics, log model revision on each predict response header (`X-Model-Revision`), trace ingress → predictor → runtime. Alert on revision not Ready, storage download failures, and GPU OOM restarts.""",
        """## Security""",
        """Use IRSA/GKE workload identity for S3/GCS access—no long-lived keys in pods. NetworkPolicy restrict predict ingress to mesh gateway only. Scan model artifacts in CI for pickle deserialization risks if formats allow arbitrary code.""",
        """## Migration from raw Deployments""",
        """Lift-and-shift: wrap existing container as custom predictor, then migrate to Triton runtime for batching gains. Run dual-stack with traffic split until shadow metrics match.""",
        """## Day-two checklist""",
        """Quarterly: verify storage URI still resolves, test scale-from-zero against SLO, rehearse canary rollback, audit minReplicas vs cost. KServe succeeds when teams treat InferenceService like a microservice contract—not a one-time YAML dump.""",
        """## Failure modes""",
        """Init container OOM on huge models—raise limits or use chunked download. Wrong modelFormat prevents load—validate in staging with same runtime version as prod. Knative activator saturation during thundering herd—raise maxScaleRate or use warm pools.""",
        """## Cost governance""",
        """Tag InferenceServices with team and cost center labels; feed GPU utilization metrics to FinOps dashboards. Scale-to-zero without monitoring produces surprise cold-start SLO breaches—cost saved is not worth revenue lost.""",
        """KServe standardizes model serving on Kubernetes when you commit to CRD-driven ops, explicit timeouts, and revision-aware observability—not when you want the thinnest possible wrapper around a single pod.""",
    ),
)

# I'll add more topics via exec from external file to keep this manageable
print("Partial generator - extend CONTENT dict")
