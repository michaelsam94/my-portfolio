---
title: "Incident Response and Forensics Basics"
slug: "incident-response-forensics"
description: "Run effective incident response: detection, containment, evidence preservation, timeline reconstruction, and post-incident review without destroying forensic data."
datePublished: "2025-07-04"
dateModified: "2025-07-04"
tags: ["Security", "DevOps", "Incidents", "Architecture"]
keywords: "incident response forensics, security incident handling, digital forensics basics, evidence preservation, incident timeline, post-incident review"
faq:
  - q: "What should I do first when a security incident is detected?"
    a: "Confirm the alert is real (not a false positive), assign an incident commander, and start a shared timeline document immediately. Do not reboot affected systems or delete logs — you'll destroy evidence. Contain the blast radius (isolate affected hosts, revoke compromised credentials) while preserving data for investigation."
  - q: "What evidence should be preserved during an incident?"
    a: "Memory dumps (if the system is still running), disk snapshots, network flow logs, authentication logs, application logs, cloud audit trails (CloudTrail, Azure Activity Log), and any malware samples. Capture timestamps in UTC. Document the chain of custody — who collected what, when, and where it's stored."
  - q: "How detailed should a post-incident review be?"
    a: "Focus on timeline, root cause, blast radius, what worked in response, and what didn't. Blameless — the goal is systemic improvement, not individual fault. Include concrete action items with owners and deadlines. Share a summary with leadership; keep the full report restricted to the response team."
---

The pager goes off at 2 AM. Someone's credentials are being used from an IP in a country you've never had users in. Your first instinct is to kill the account and go back to sleep. That's the wrong first move — if you don't preserve evidence first, you'll never know what they accessed, how they got in, or whether they're still in through a backdoor. Incident response is a discipline, not a reflex.

## The response phases

```
Detect → Triage → Contain → Investigate → Eradicate → Recover → Review
```

Each phase has a goal. Skipping containment to investigate lets the attacker keep moving. Skipping evidence preservation to contain destroys the investigation.

## Detection and triage (first 15 minutes)

1. **Confirm the alert** — check if it's a false positive (developer VPN, new office IP, scheduled pentest)
2. **Assign roles:**
   - **Incident Commander (IC)** — makes decisions, owns timeline
   - **Scribe** — documents everything in real time
   - **Technical Lead** — runs investigation commands
   - **Comms Lead** — handles internal/external communication
3. **Start the timeline** — a shared doc with UTC timestamps:

```
2025-07-04 02:14 UTC — Alert: unusual login from 185.x.x.x for user admin@company.com
2025-07-04 02:16 UTC — IC assigned: Alice. Severity: SEV-2 (confirmed unauthorized access)
2025-07-04 02:18 UTC — Verified: user admin@company.com has no travel to this region
```

Don't wait for perfect information. Log what you know, update as you learn.

## Containment without destroying evidence

**Do:**
- Disable the compromised account (don't delete it)
- Revoke active sessions and API keys
- Snapshot the affected VM/disk before any changes
- Block the attacker IP at the WAF/firewall
- Isolate the affected host (security group change, not power off)

**Don't:**
- Reboot the server (destroys memory artifacts)
- Delete logs to "clean up"
- Run antivirus scans that modify files before imaging
- Notify the attacker (by changing passwords on systems they may be watching)

Cloud snapshot before anything else:

```bash
aws ec2 create-snapshot \
  --volume-id vol-0abc123 \
  --description "IR-evidence-20250704-vol-0abc123" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Incident,Value=IR-2025-074}]'
```

## Investigation and forensics

Reconstruct the attack path:

1. **Authentication logs** — when did the attacker first log in? What auth method?
2. **Cloud audit trail** — what API calls were made? What resources were created/modified?
3. **Network logs** — VPC flow logs, DNS queries, firewall logs
4. **Application logs** — what data was accessed? Any exfiltration patterns?
5. **Endpoint artifacts** — process list, cron jobs, SSH keys, `.bash_history`

Build the timeline backward from detection to initial access:

```
02:14 — Alert triggered (impossible travel)
01:52 — Successful login from 185.x.x.x via password (no MFA)
01:48 — Password spray detected against 12 accounts (only admin hit)
01:30 — First failed login attempt from 185.x.x.x
Nov 12 — Attacker credential first appeared in breach dump (Have I Been Pwned)
```

Initial access vector matters for eradication. A phished password requires different remediation than an SQL injection.

## Evidence preservation

| Artifact | Method | Priority |
|----------|--------|----------|
| Disk | Cloud snapshot or `dd` image | Immediate |
| Memory | `lime` or `dumpit` (before reboot) | Immediate if possible |
| Logs | Export to immutable storage (S3 Object Lock) | Within 1 hour |
| Network | VPC flow logs, packet capture if available | Within hours |
| Cloud audit | CloudTrail export to separate account | Immediate |

Chain of custody: record who collected each artifact, the exact command used, the storage location, and a hash (SHA-256) of the image.

```bash
sha256sum evidence-disk.img > evidence-disk.img.sha256
```

Store evidence in a separate AWS account or bucket with Object Lock enabled — the attacker shouldn't be able to delete their own trail.

## Eradication and recovery

Only after you understand the full scope:

- Rotate all credentials the attacker may have accessed
- Remove persistence mechanisms (backdoor accounts, cron jobs, web shells)
- Patch the vulnerability used for initial access
- Rebuild compromised hosts from known-good images (don't "clean" in place)
- Restore data from pre-compromise backups if data was modified

## Post-incident review

Within 5 business days, publish a blameless post-incident review:

1. **Summary** — what happened, in plain language
2. **Timeline** — key events with UTC timestamps
3. **Root cause** — the underlying failure, not the proximate trigger
4. **Blast radius** — what data/systems were affected
5. **What went well** — detection time, response speed, communication
6. **What didn't** — gaps in monitoring, missing runbooks, slow escalation
7. **Action items** — specific, owned, with deadlines

Action items should be tracked like any other engineering work — in your issue tracker, with sprint allocation.

## Common production mistakes

Teams get incident response forensics wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of incident response forensics fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When incident response forensics misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [NIST SP 800-61 — Computer Security Incident Handling Guide](https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final) — the canonical IR framework
- [SANS Incident Handler's Handbook](https://www.sans.org/white-papers/33901/) — practical IR procedures
- [AWS Security Incident Response Guide](https://docs.aws.amazon.com/whitepapers/latest/aws-security-incident-response-guide/welcome.html) — cloud-specific evidence collection
- [Google SRE — Managing Incidents](https://sre.google/sre-book/managing-incidents/) — incident command and communication patterns
