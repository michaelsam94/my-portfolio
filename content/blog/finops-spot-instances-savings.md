---
title: "Saving with Spot Instances"
slug: "finops-spot-instances-savings"
description: "Run fault-tolerant workloads on Spot at 60–90% discount: interruption handling, capacity-optimized allocation, mixed instance policies, and when Spot is the wrong choice."
datePublished: "2024-09-04"
dateModified: "2024-09-04"
tags: ["DevOps", "FinOps"]
keywords: "Spot instances, AWS Spot, preemptible VMs, spot interruption, capacity-optimized allocation, cloud savings"
faq:
  - q: "How much can Spot instances save compared to On-Demand?"
    a: "Spot prices are typically 60–90% below On-Demand for the same instance type, though rates fluctuate by AZ, instance family, and demand. Savings are real for batch processing, CI runners, render farms, and stateless web tiers behind a load balancer. Never assume Spot pricing is static—monitor Spot Price History before committing architecture to a single instance type."
  - q: "What happens when AWS reclaims a Spot instance?"
    a: "You receive a two-minute Spot Instance Interruption Notice via instance metadata and EventBridge. Well-designed workloads drain connections, checkpoint work, and terminate gracefully within that window. Stateless workers simply exit; ASG or Karpenter replaces capacity from another instance type or AZ."
  - q: "Should production workloads use Spot instances?"
    a: "Only if they tolerate interruption and you maintain On-Demand baseline capacity for critical paths. Mixed Instance Policies and Karpenter's spot/on-demand split work well for Kubernetes. Databases, single-node stateful systems, and jobs that can't checkpoint should stay On-Demand or Reserved."
---

Spot instances are spare cloud capacity sold at auction prices. AWS can reclaim them with two minutes' notice. That sounds risky until you realize most of your fleet probably doesn't need a uptime SLA of 99.99%—CI runners, video transcoders, EMR clusters, and even stateless API pods behind Kubernetes can absorb interruption if you design for it. I've cut batch-processing bills by 70% without changing a line of application logic, only the capacity purchase model.

## How Spot pricing works

Each instance type in each Availability Zone has a Spot price that moves with supply and demand. You set a maximum price (often capped at On-Demand); you pay the current Spot price, not your max, as long as capacity exists. When AWS needs capacity back, instances with the lowest price first receive interruption notices.

Key concepts:

- **Spot Instance Interruption Notice** — 120 seconds warning via `http://169.254.169.254/latest/meta-data/spot/instance-action`.
- **Capacity pools** — Spot capacity is per instance type + AZ. Diversifying types increases availability.
- **Spot blocks (legacy)** — mostly replaced by On-Demand Capacity Reservations for fixed-duration needs.

Check historical prices before betting on `c6i.4xlarge` in `us-east-1a`:

```bash
aws ec2 describe-spot-price-history \
  --instance-types c6i.4xlarge m6i.4xlarge c7g.4xlarge \
  --product-descriptions "Linux/UNIX" \
  --start-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --max-items 20
```

## Workloads that fit Spot

| Workload | Spot fit | Notes |
|----------|----------|-------|
| CI/CD runners | Excellent | Job retries on new runner |
| Batch / ETL | Excellent | Checkpoint to S3 |
| Kubernetes worker nodes | Good | Use Karpenter or Cluster Autoscaler |
| Stateless web API | Good | Keep 30%+ On-Demand base |
| Kafka / databases | Poor | Avoid unless clustered with failover |
| Single-node cron | Poor | Use On-Demand or Fargate |

The pattern is simple: **stateless or checkpointed**. If losing a node mid-task means hours of rework, Spot isn't your tool.

## Handling interruptions gracefully

Listen for the interruption notice and act within 120 seconds:

```bash
#!/bin/bash
# Spot interruption handler (run as systemd service or sidecar)
while sleep 5; do
  ACTION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/spot/instance-action 2>/dev/null)
  if [ -n "$ACTION" ]; then
    echo "Spot interruption detected: $ACTION"
    # Drain from load balancer, flush queues, exit cleanly
    systemctl stop my-app
    exit 0
  fi
done
```

On Kubernetes, the **AWS Node Termination Handler** DaemonSet cordons and drains nodes automatically. Pair it with PodDisruptionBudgets so replacements spin up before critical replicas hit zero.

For batch jobs, write idempotent stages and persist progress externally:

```python
# Pseudocode: checkpoint every N records
for i, record in enumerate(records):
    process(record)
    if i % 1000 == 0:
        s3.upload_checkpoint(job_id, i)
# On restart, resume from s3.get_last_checkpoint(job_id)
```

## Auto Scaling and mixed instance policies

Don't launch Spot manually. Use Auto Scaling Groups with **MixedInstancesPolicy**:

```json
{
  "LaunchTemplate": { "LaunchTemplateSpecification": { "LaunchTemplateName": "worker-lt" } },
  "InstancesDistribution": {
    "OnDemandBaseCapacity": 2,
    "OnDemandPercentageAboveBaseCapacity": 25,
    "SpotAllocationStrategy": "capacity-optimized"
  },
  "Overrides": [
    { "InstanceType": "m6i.xlarge" },
    { "InstanceType": "m6a.xlarge" },
    { "InstanceType": "c6i.xlarge" }
  ]
}
```

`capacity-optimized` (not `lowest-price`) picks pools with the most free capacity, reducing interruption frequency. I've seen interruption rates drop by half after switching strategies.

## Kubernetes with Karpenter

Karpenter provisions nodes on demand and natively blends Spot and On-Demand:

```yaml
requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot", "on-demand"]
  - key: node.kubernetes.io/instance-type
    operator: In
    values: ["m6i.large", "m6a.large", "c6i.large", "c7g.large"]
```

Set `disruption.consolidationPolicy: WhenUnderutilized` to replace expensive nodes with cheaper Spot when pods reschedule cleanly.

## When Spot fails you

Spot isn't free money. Watch for:

- **Insufficient capacity** — frequent `InsufficientInstanceCapacity` means you need more instance type diversity or a higher On-Demand floor.
- **Interruption storms** — regional events can reclaim large Spot fleets simultaneously. Multi-AZ and multi-type policies mitigate this.
- **Two-minute jobs** — if your average task exceeds the notice window and can't checkpoint, interruption cost exceeds savings.

Track **Spot placement score** and **interruption rate** as FinOps KPIs alongside dollar savings.

### Measuring Spot ROI

Track three metrics monthly: Spot spend as percentage of total compute, interruption rate per 1,000 instance-hours, and job retry cost from failed Spot runs. If retry cost exceeds Spot savings, your workload isn't Spot-ready yet. Export CloudWatch metrics for Spot placement score and correlate with application SLO breaches.

Compare On-Demand equivalent cost vs actual Spot spend in Cost Explorer filters. Present savings to leadership as dollars and carbon-adjacent efficiency narrative—unused capacity utilization benefits the cloud provider and your budget simultaneously.

For Kubernetes, combine Karpenter consolidation with Spot—when pods reschedule, prefer cheaper nodes automatically. Document interruption playbooks in runbooks: which Deployments tolerate Spot (stateless API) vs require On-Demand (Redis primary). Game days simulating Spot reclaim validate alerting before real regional capacity crunches.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

## Common production mistakes

Teams get finops spot instances savings wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of finops spot instances savings fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Amazon EC2 Spot Instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html)
- [Spot Instance Interruption Notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [Auto Scaling MixedInstancesPolicy](https://docs.aws.amazon.com/autoscaling/ec2/APIReference/API_InstancesDistribution.html)
- [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler)
- [Karpenter Spot Documentation](https://karpenter.sh/docs/concepts/nodepools/)
