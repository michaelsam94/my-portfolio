---
title: "AI Agents: Model Card Documentation"
slug: "agent-model-card-documentation"
description: "Treat model cards as versioned, testable artifacts—not PDF afterthoughts—so agent releases ship with auditable limits, eval evidence, and clear ownership."
datePublished: "2025-05-16"
dateModified: "2025-05-16"
tags: ["AI", "Agent", "Model"]
keywords: "model cards, ML documentation, LLM governance, agent model registry, responsible AI, model metadata, Hugging Face model card"
faq:
  - q: "What must a model card include for a production agent?"
    a: "At minimum: intended use and out-of-scope uses, training or fine-tune data summary, evaluation results on tasks that mirror production, known failure modes, inference limits (context, tools, languages), privacy and retention behavior, and an owner plus escalation path."
  - q: "How is an agent model card different from a vendor datasheet?"
    a: "Vendor datasheets describe the base model. Your card describes the composed system: base model plus prompts, tools, retrieval index, safety filters, and deployment configuration. Auditors care about what you actually run, not what the API marketing page claims."
  - q: "Should model cards block CI if eval scores regress?"
    a: "They should block promotion when regressions exceed agreed thresholds on release gates tied to the card's eval suite—not on every commit. Store eval artifacts as immutable blobs referenced by card version so historical releases remain explainable."
  - q: "Where should model cards live in the repo?"
    a: "Alongside the agent bundle they describe: `models/support-agent/v3/model-card.yaml`, referenced by deployment manifests. Generated PDFs are optional exports; the source of truth is structured text under version control."
---
Legal asked a reasonable question during a procurement review: "Which model answers EU customer tickets, what data does it retain, and what testing proves it won't invent refund policies?" Engineering opened Notion, found a slide from last quarter, and a PDF exported from a notebook. The base model had been swapped twice since then. Prompts had moved to a new tool-calling schema. Nobody could map the slide to what was running in `prod-eu-west`.

That afternoon is when model card documentation stops being "ML paperwork" and becomes release infrastructure. A model card is the contract between the team that ships an agent and everyone who must trust it—security, legal, support leads, and your future self during a 2 a.m. incident.

## What a model card is not

It is not a marketing blurb or a dump of training hyperparameters copied from a paper. It is not a one-time ethics checklist signed at launch.

A useful card answers operational questions without a live engineer:

- What is this agent allowed to do autonomously?
- What must it escalate?
- What languages, regions, and data classes does it handle?
- What evals ran before this version promoted, and what failed?
- What changed since the last version?

If those answers live only in Slack threads, you do not have documentation—you have folklore.

## Structure that survives audits and refactors

Adapt the [Model Card framework (Mitchell et al.)](https://arxiv.org/abs/1810.03993) to agent systems by adding a **composition** section. Base models are rarely deployed naked; agents are stacks.

Recommended sections for agent model cards:

1. **Model details** — base model IDs, fine-tunes, quantization, hosting region
2. **Composition** — prompts, tool schemas, retrieval sources, guardrails
3. **Intended use** — workflows, user populations, success criteria
4. **Out-of-scope uses** — explicit non-goals (medical advice, binding contracts)
5. **Training and data** — fine-tune sets, PII handling, retention windows
6. **Evaluation** — offline suites, online metrics, human review samples
7. **Limitations and risks** — hallucination patterns, bias findings, jailbreak sensitivity
8. **Monitoring** — dashboards, alert thresholds, rollback triggers
9. **Version history** — changelog with diffs to prompts and tools
10. **Contacts** — owner, backup, security liaison

Keep prose tight. Long narrative belongs in linked runbooks; the card should be scannable.

## Model card as code

Treat the card like application config: validate in CI, render for humans, attach to deployments.

```yaml
# models/support-agent/v3/model-card.yaml
schema_version: 1
model_card_version: "3.2.1"
agent_id: support-agent
display_name: "Support Agent — EU Tier-1"
owner:
  team: agent-platform
  email: agent-platform@company.com
  slack: "#agent-releases"

base_models:
  - provider: anthropic
    model_id: claude-3-5-sonnet-20241022
    region: eu-west-1

composition:
  prompt_bundle: prompts/support/eu/v12.txt
  tools:
    - ticket_lookup
    - refund_policy_rag
    - escalate_to_human
  retrieval:
    index: kb-eu-refunds-v4
    max_chunks: 8
  safety:
    - input_pii_redaction
    - output_policy_filter_v2

intended_use: |
  Draft replies and suggest macros for tier-1 billing and shipping questions
  for EU customers on paid plans. Human agents approve before send.

out_of_scope:
  - legal interpretation
  - medical or safety emergencies
  - autonomous refunds above €50

data:
  fine_tune: none
  logs_retention_days: 30
  pii_fields_redacted: [email, phone, address]

evaluation:
  gates:
    - name: golden_set_accuracy
      metric: exact_match_approval_rate
      threshold: 0.91
    - name: policy_violation_rate
      metric: policy_violations_per_1k
      threshold_max: 0.5
  artifacts:
    - s3://eval-artifacts/support-agent/3.2.1/report.json

monitoring:
  dashboards:
    - https://grafana.internal/d/support-agent-eu
  rollback_if:
    handoff_rate_1h_delta: "> 0.15"
    policy_violation_spike: "> 3x baseline"

changelog:
  - version: "3.2.1"
    date: "2025-05-10"
    notes: "Prompt v12 tightens refund eligibility wording; tool schema unchanged."
```

Validation rules catch incomplete cards before merge:

```python
# ci/validate_model_card.py
from pathlib import Path
import sys
import yaml

REQUIRED_TOP_LEVEL = [
    "model_card_version", "owner", "base_models", "composition",
    "intended_use", "out_of_scope", "evaluation", "monitoring",
]

def validate(path: Path) -> list[str]:
    errors = []
    doc = yaml.safe_load(path.read_text())
    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            errors.append(f"{path}: missing required key '{key}'")
    if "evaluation" in doc:
        gates = doc["evaluation"].get("gates", [])
        if not gates:
            errors.append(f"{path}: evaluation.gates must not be empty")
    owner = doc.get("owner", {})
    if not owner.get("email"):
        errors.append(f"{path}: owner.email required for escalation")
    return errors

if __name__ == "__main__":
    paths = list(Path("models").rglob("model-card.yaml"))
    all_errors = []
    for p in paths:
        all_errors.extend(validate(p))
    if all_errors:
        print("\n".join(all_errors))
        sys.exit(1)
    print(f"Validated {len(paths)} model cards.")
```

Pair validation with eval artifact checks: CI downloads `report.json`, verifies thresholds, and comments on the pull request with a diff summary.

## Binding cards to releases

A card nobody reads is shelfware. Wire it into the deployment path:

```yaml
# deploy/support-agent-eu.yaml
apiVersion: serving.internal/v1
kind: AgentDeployment
metadata:
  name: support-agent-eu
spec:
  agent_version: "3.2.1"
  model_card: models/support-agent/v3/model-card.yaml
  model_card_digest: sha256:8f3a2c...  # computed in CI
  promotion_requires:
    - ci/model-card-validate
    - ci/eval-gates
    - approval: agent-release-approvers
```

At deploy time, the controller refuses promotion if the digest does not match the built artifact—preventing "we updated the card but forgot to redeploy" drift.

For multi-tenant agents, maintain **tenant overlays** rather than forking entire cards:

```yaml
# models/support-agent/v3/overlays/tenant-acme.yaml
extends: ../model-card.yaml
tenant_id: acme-corp
composition:
  retrieval:
    index: kb-acme-v2
out_of_scope:
  - competitor_price_matching   # contractual exclusion
```

The base card stays canonical; overlays diff cleanly in review.

## Human-readable exports without losing truth

Some stakeholders want PDFs. Generate them from the same YAML so exports never diverge:

```bash
# Makefile target — pseudocode pipeline
model-card-render models/support-agent/v3/model-card.yaml > dist/support-agent-v3.2.1.md
pandoc dist/support-agent-v3.2.1.md -o dist/support-agent-v3.2.1.pdf
```

Store PDFs as release attachments, not sources of truth. When legal asks for "the card," send a link to the tagged commit.

## Operating model cards after launch

Documentation rots when behavior changes silently. Enforce **card updates on meaningful diffs**:

| Change | Card action |
|--------|-------------|
| Prompt wording only | Bump patch version, changelog entry |
| New tool or retrieval index | Minor version, re-run eval gates |
| Base model swap | Minor or major, full eval suite + security review |
| Data retention change | Major version, legal review required |

Schedule quarterly reviews even if nothing shipped—verify monitoring links, contacts, and out-of-scope lists still match reality.

During incidents, the card is the first document on-call opens. If `rollback_if` conditions are defined upfront, decisions happen faster than debating whether a spike is noise.

## Cross-team review without calendar bloat

Model cards work best with lightweight review lanes instead of a single heavyweight committee:

- **Security** reviews `out_of_scope`, data retention, and tool permissions—async comment on the pull request within two business days.
- **Legal** reviews intended use statements and regional deployment notes—only on major version bumps or new data classes.
- **Support** validates that failure modes match macros they actually send—15-minute read-through, not a slide deck.

Tag reviewers in CODEOWNERS by directory. If `models/support-agent/**` changes, `@support-leads` auto-requests review. Cards that never get eyeballs from downstream teams fail exactly when an auditor calls.

Store resolved review threads in the pull request history; do not copy meeting notes into the card body. The YAML stays terse; GitHub/GitLab holds the conversation.

## Measuring documentation quality

Track meta-metrics:

- Percentage of production agents with cards linked in deploy manifests
- Mean age of eval artifacts referenced by live cards
- Time to answer audit questionnaires (should drop after cards mature)
- Number of incident postmortems citing missing or stale card sections

Good cards reduce repeated cross-team meetings. That is the ROI—not checkbox compliance.

Model card documentation is how you prove you knew what you shipped. Build it into the pipeline early, keep it structured, and treat changes with the same discipline as code—because for agents, the card is part of the system.

## Resources

- [Model Cards for Model Reporting (Mitchell et al., 2019)](https://arxiv.org/abs/1810.03993) — original framework paper
- [Hugging Face: Model Cards documentation](https://huggingface.co/docs/hub/model-cards) — widely used card format and metadata fields
- [Google Model Card Toolkit](https://github.com/tensorflow/model-card-toolkit) — generators and schemas for structured cards
- [NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework) — risk framing that maps to intended use and monitoring sections
- [EU AI Act high-level summary (European Commission)](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — regulatory context for documentation expectations in EU deployments
