---
title: "Running Effective Engineering Meetings"
slug: "career-running-effective-meetings"
description: "Most engineering meetings waste time. Run effective standups, design reviews, and retrospectives with clear agendas, time limits, and documented outcomes that drive decisions."
datePublished: "2025-01-08"
dateModified: "2025-01-08"
tags: ["Career", "Engineering", "Meetings"]
keywords: "effective engineering meetings, standup best practices, design review meeting, sprint retrospective, meeting agenda engineering"
faq:
  - q: "How long should a daily standup be?"
    a: "Fifteen minutes maximum for teams under 10 people. Each person shares: what they did, what they're doing, blockers — in under 90 seconds. Standups are for coordination and blocker surfacing, not problem-solving. Take discussions offline."
  - q: "What makes a design review meeting useful?"
    a: "A written design doc shared 24 hours before the meeting, a clear problem statement, 2–3 proposed approaches with tradeoffs, and specific questions for reviewers. The meeting discusses decisions, not discovers the problem. Outcome: approved direction or explicit list of revisions needed."
  - q: "When should a meeting be an email or doc instead?"
    a: "If the goal is information sharing without discussion, use async. Status updates, announcements, and FYI items don't need synchronous time. Meetings are for decisions, brainstorming with real-time back-and-forth, and relationship building — not reading slides aloud."
---

The average engineer spends 10–18 hours per week in meetings. Half of that time produces no decision, no action item, and no information that couldn't have been a three-paragraph doc. I've sat in hour-long "syncs" that ended with "let's take this offline" — meaning the meeting had no purpose. Effective meetings are short, have agendas, produce outcomes, and respect that every attendee's time is worth more than the organizer's convenience.

## Meeting types that earn their time

| Meeting | Duration | Purpose | Output |
|---------|----------|---------|--------|
| Standup | 15 min | Coordination | Blockers assigned |
| Design review | 45 min | Decision | Approved/revise doc |
| Retro | 60 min | Improvement | 2–3 action items |
| 1:1 | 30 min | Growth + unblock | Follow-ups noted |
| Incident review | 60 min | Learning | Action items + doc |

Everything else should justify its existence quarterly.

## Standup that doesn't suck

**Format:** Round-robin, timed.

```
Yesterday: Shipped payment retry (PR #412). 
Today: Starting webhook signature verification.
Blockers: Need API rate limit decision from PM.
```

**Rules:**
- No laptops (optional but effective)
- No problem-solving — "I'll sync with you after" 
- Blockers get an owner and a time, not a discussion
- Cancel standup if nothing to coordinate (async update instead)

For distributed teams, async standup in Slack/Linear works better than a video call where half the team is muted doing other work.

## Design review structure

**Before the meeting:**
1. Author publishes design doc (problem, options, recommendation)
2. Reviewers comment async for 24 hours
3. Author addresses comments, updates doc

**During the meeting (45 min):**
- 5 min: Author summarizes problem and recommendation
- 25 min: Discuss unresolved comments and tradeoffs
- 10 min: Decision — approve, revise, or defer
- 5 min: Document action items

**The doc is the artifact.** The meeting is for disagreement and decision, not presentation.

## Retrospectives that change things

Bad retro: "what went well? what didn't?" → vague answers → same problems next sprint.

Good retro structure:

1. **Data first:** Metrics (incidents, velocity, escaped bugs) — 5 min
2. **Individual write:** Everyone writes 1 keep, 1 change, 1 try — 5 min silently
3. **Discuss top themes:** Vote on items — 20 min
4. **Action items:** Max 3, each with owner and due date — 10 min
5. **Review last retro actions:** Did we do them? — 5 min

If retro action items never get done, the team stops participating. Follow through or stop having retros.

## Meeting hygiene

**Every meeting invite needs:**
- Agenda (what decisions will be made)
- Pre-read links
- Expected outcome ("decide X" not "discuss X")

**During:**
- Timekeeper (not the facilitator)
- Notes taker (rotate role)
- Parking lot for off-topic items

**After:**
- Action items with owners sent within 30 minutes
- No action items = meeting probably didn't need to happen

## Killing unnecessary meetings

Audit quarterly:
- Meetings with < 50% attendance → reschedule or cancel
- Recurring meetings with no action items for 3 sessions → cancel
- "Status sync" that duplicates written updates → async
- Meetings you attend but never speak in → decline

Declining meetings is a skill. "I don't think I can contribute to this — can you share notes?" is professional.

## The async alternative

Replace meetings with:
- **Design docs** for decisions (comment async, meet only if unresolved)
- **Recorded Loom** for demos (watch at 1.5x, comment in doc)
- **Slack threads** for quick alignment
- **Written weekly updates** for status

My team's rule: if a meeting could have been a doc, the person who called the meeting writes the doc next time instead.

## Meeting types and their formats

Different meetings need different structures — one format doesn't fit all:

| Meeting type | Duration | Required prep | Output |
|---|---|---|---|
| Decision meeting | 30 min | Written proposal circulated 24h before | Decision recorded in doc |
| Brainstorm | 45 min | Problem statement shared | Ideas captured, owner assigned to synthesize |
| 1:1 | 30 min | Agenda from both parties | Action items, not status recap |
| Incident postmortem | 60 min | Timeline doc pre-written | Action items with owners and dates |
| Status sync | ❌ Cancel | Written update instead | — |

Decision meetings without pre-circulated proposal default to the loudest voice winning. Require written context before scheduling.

## The written decision record

Every decision meeting produces a record:

```markdown
## Decision: Migrate from Postgres to CockroachDB

**Date:** 2024-12-27
**Participants:** alice, bob, carol
**Decision:** Proceed with CockroachDB for new services; existing Postgres unchanged
**Rationale:** Multi-region requirement for EU expansion; CockroachDB native geo-distribution
**Dissent:** bob preferred Vitess — noted, not blocking
**Action items:**
- [ ] alice: POC by 2025-01-15
- [ ] carol: cost model by 2025-01-10
**Review date:** 2025-02-01
```

Decisions without records get re-litigated. The doc is the decision — the meeting was the discussion.

## Remote meeting hygiene

Remote meetings fail differently than in-person:

- **Camera optional, engagement required** — async reactions in chat count
- **Record by default** — absent stakeholders watch at 1.5×
- **No hybrid without remote-first design** — in-room side conversations exclude remote attendees
- **5-minute buffer between meetings** — no back-to-back Zoom marathons
- **Shared doc as primary surface** — not screen share of presenter's notes

```markdown
Meeting norms (team agreement):
- Agenda required 24h before — no agenda, meeting cancelled
- Hard stop at scheduled end — remaining items become async
- Action items in shared doc during meeting, not after
- "Could this be a Slack thread?" asked before scheduling
```

## Failure modes

- **No agenda** — meeting meanders, no decisions made
- **Status meeting that duplicates written update** — wasted time for all attendees
- **Decision without pre-circulated context** — loudest voice wins, not best argument
- **No action items recorded** — same discussion repeats next week
- **Recurring meeting with no output for 3 sessions** — zombie meeting, cancel it

## Production checklist

- Agenda required before scheduling — no agenda, no meeting
- Decision meetings require written proposal circulated 24h before
- Action items with owners sent within 30 minutes of meeting end
- Quarterly audit: cancel meetings with <50% attendance or no action items
- Remote-first design for hybrid meetings
- Written decision record for every decision meeting

## Resources

- [Amazon — two-pizza teams and meeting culture](https://www.amazon.jobs/content/en/our-workplace/leadership-principles)
- [Basecamp — Meetings are toxic (calibrated take)](https://basecamp.com/guides/how-we-communicate)
- [Google re:Work — running effective meetings](https://rework.withgoogle.com/guides/meetings/)
- [Atlassian playbook — retrospectives](https://www.atlassian.com/team-playbook/plays/retrospective)
- [StaffEng — Writing design docs](https://staffeng.com/guides/work-on-what-matters/)
