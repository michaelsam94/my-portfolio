#!/usr/bin/env python3
"""Generate generate_batch_c_posts.py with 250 inline topics."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "generate_batch_c_posts.py"

# Each topic: suffix, title, description, tags (list), keywords, hook, faq_when, faq_mistake, tool
# Plus 5 sections: each (heading, para1, para2, code_or_empty)

def T(suffix, title, desc, tags, kw, hook, when, mistake, tool, sections):
    return {
        "suffix": suffix, "title": title, "desc": desc, "tags": tags, "kw": kw,
        "hook": hook, "when": when, "mistake": mistake, "tool": tool, "sections": sections,
    }

def S(h, p1, p2="", code=""):
    return {"h": h, "p1": p1, "p2": p2, "code": code}

TOPICS = []

def extend(cat, items):
    for item in items:
        item["category"] = cat
        TOPICS.append(item)

extend("Kubernetes", [
T("pod-disruption-budgets","Pod Disruption Budgets for Safe Cluster Upgrades",
  "Design PodDisruptionBudgets that protect quorum during node drains, cluster upgrades, and Karpenter consolidation.",
  ["DevOps","Kubernetes","SRE"],"PodDisruptionBudget, PDB, node drain, cluster upgrade",
  "At 2 a.m. during a node pool upgrade, Redis Sentinel lost quorum because three pods were evicted simultaneously—no PDB existed on the StatefulSet.",
  "Before enabling cluster autoscaler consolidation or your first production node drain.",
  "Setting minAvailable to 100% on stateless Deployments blocks all voluntary evictions and stalls upgrades for days.",
  "PodDisruptionBudget",
  [S("Why PDBs exist","Voluntary disruptions—kubectl drain, cluster upgrades, Karpenter consolidation—can remove multiple pods at once. PodDisruptionBudgets cap simultaneous evictions so quorum services survive.",
     "PDBs apply only to voluntary disruptions. Involuntary ones—node failure, OOMKill—need anti-affinity, replication, and health checks—not PDB alone."),
   S("PDB spec patterns","For Deployments with three replicas, minAvailable: 2 or maxUnavailable: 1 preserves capacity during drains.",
     "StatefulSets often need minAvailable tied to replica count minus one for quorum.",
     """```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api
```"""),
   S("Autoscaler interaction","Cluster Autoscaler and Karpenter respect PDBs when consolidating nodes. Overly strict PDBs prevent bin-packing savings.",
     "Review PDB coverage in pre-upgrade checklists alongside replica counts and zone spread."),
   S("Testing drains","Run kubectl drain against staging nodes with production-shaped replica counts. Measure time-to-drain and whether PDB blocks appear in events.",
     "Document max concurrent drains per service tier in your platform runbook."),
   S("Observability","Alert on kube_poddisruptionbudget_status_current_healthy approaching limits during maintenance windows.",
     "Track eviction failures in audit logs for postmortems and quarterly PDB reviews.")]),
])

print(len(TOPICS))
