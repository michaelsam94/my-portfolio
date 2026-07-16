---
title: "Mentoring Junior Engineers"
slug: "career-mentoring-junior-engineers"
description: "Effective mentoring accelerates junior engineers without creating dependency. Use guided questions, scoped tasks, paired reviews, and progressive autonomy to build independent contributors."
datePublished: "2025-01-03"
dateModified: "2025-01-03"
tags: ["Career", "Engineering", "Mentoring"]
keywords: "mentoring junior engineers, engineering mentorship, onboarding developers, code review mentoring, growing junior developers"
faq:
  - q: "How much should I help vs let junior engineers struggle?"
    a: "Let them struggle for 20–30 minutes on their own — that's where learning happens. If they're still stuck, ask guiding questions rather than giving answers. If they're blocked on access, environment, or a concept they've never seen, intervene faster. The goal is productive struggle, not frustration."
  - q: "What tasks are appropriate for junior engineers?"
    a: "Well-scoped tasks with clear acceptance criteria: bug fixes with reproduction steps, small feature additions in familiar code, test coverage for existing modules, documentation updates. Avoid ambiguous 'build the auth system' projects until they have context on the codebase and team patterns."
  - q: "How do I give code review feedback that teaches?"
    a: "Explain why, not just what. Link to docs or examples. Distinguish blocking issues (correctness, security) from suggestions (style, naming). Ask questions: 'What happens if this is null?' instead of 'Add a null check.' Approve when it's good enough — perfect is the enemy of shipping and confidence."
---

The junior engineer on your team will either become a self-sufficient contributor in six months or a permanent dependency who pings you before every commit. The difference isn't their talent — it's how you mentor. Good mentoring accelerates learning, builds confidence, and scales your team's output. Bad mentoring (doing their work, or abandoning them to sink) wastes everyone's time.

## The Socratic approach

When they ask "how do I fix this?", don't answer directly:

```
Junior: "The API call returns 403. What do I do?"
Bad:    "Add the Authorization header."
Good:   "What does 403 mean? What headers are you sending?
         What does the API doc say about authentication?"
```

Guided questions build debugging muscle. Direct answers build dependency.

Exception: first encounter with a concept (what's a JWT? how does git rebase work?) — teach directly, then ask questions on the next occurrence.

## Scoping tasks for growth

Use an expanding scope model:

| Week | Task type | Your involvement |
|------|-----------|-----------------|
| 1–2 | Bug fix with repro steps | Pair on investigation |
| 3–4 | Small feature, existing pattern | Review design before coding |
| 5–8 | Feature requiring one new concept | Available for questions |
| 9+ | Own a vertical slice | Review PRs only |

Each task should stretch one skill, not five. "Add a field to the API response" teaches one thing. "Build the notification system" teaches everything at once and overwhelms.

## Code review as teaching

Structure feedback in three tiers:

**Must fix (blocking):**
- Correctness bugs
- Security issues
- Data loss risks

**Should fix (non-blocking):**
- Missing tests for new logic
- Error handling gaps
- Performance concerns

**Consider (suggestions):**
- Naming preferences
- Alternative approaches
- Style nits

```markdown
<!-- Blocking -->
This SQL query is vulnerable to injection — use parameterized queries.
See: [OWASP SQL injection guide](https://owasp.org/...)

<!-- Teaching -->
Question: what happens if `user` is null here? Think about the
callers in AuthMiddleware.

<!-- Suggestion -->
nit: I'd name this `fetchActiveOrders` to match the repository pattern
in OrderRepository. Non-blocking.
```

Approve when blocking issues are resolved. Don't hold PRs for nits.

## Pairing sessions

Schedule 2–3 pairing sessions per week for the first month, tapering to weekly:

- **Driver/navigator rotation:** They drive 70% of the time. You navigate.
- **Time-box:** 60–90 minutes max. Cognitive overload is real.
- **Debrief:** 5 minutes after — what did they learn? what's unclear?

Don't pair on every task — solo struggle time is essential.

## Creating psychological safety

Juniors won't ask questions if they feel judged. Explicitly normalize:

- "I don't know either — let's figure it out together"
- "I made this exact mistake last year"
- "Dumb questions don't exist in your first six months"

Share your own PR feedback stories. Vulnerability from seniors invites questions.

## Common mentoring mistakes

| Mistake | Effect | Fix |
|---------|--------|-----|
| Doing their code for them | Dependency | Guide, don't take keyboard |
| No feedback until PR | Rework waste | Check in mid-task |
| Only critical feedback | Confidence erosion | Acknowledge what's good |
| Assigning isolated tasks | No context | Include in design discussions |
| Comparing to senior output | Imposter syndrome | Compare to their past self |

## Measuring mentorship success

After 3 months, a well-mentored junior should:
- Submit PRs with fewer blocking review rounds
- Debug independently for 30+ minutes before asking
- Ask specific questions ("I tried X and got Y") not vague ones ("it's broken")
- Understand the team's architecture at a high level
- Own at least one feature end-to-end

## Structured mentoring sessions

Replace ad-hoc "let me know if you need help" with scheduled structure:

```
Weekly 30-min mentoring session:
- 5 min: What did you learn this week?
- 10 min: Review one PR or code snippet together
- 10 min: One concept deep-dive (git rebase, debugging, testing)
- 5 min: What's blocking you? What's next week's goal?
```

Document session notes in shared doc — junior can reference past discussions. Manager can track growth arc over months.

## Graduated responsibility model

Increase autonomy progressively — don't hold juniors at "easy tasks" indefinitely:

| Phase | Timeline | Responsibility level |
|---|---|---|
| Shadow | Week 1–2 | Watch, ask questions, small fixes |
| Guided | Month 1–2 | Own tasks with check-ins mid-work |
| Supported | Month 2–3 | Own features, mentor reviews design |
| Independent | Month 3+ | Own features end-to-end, mentor reviews PR only |

Move to next phase when current phase indicators are met — not on calendar alone. A junior ready for independent work at month 2 shouldn't wait until month 3.

## Giving feedback that lands

Use SBI (Situation-Behavior-Impact) for actionable feedback:

```
❌ "Your code isn't good enough"
✅ "In yesterday's PR (situation), the error handling returned
   generic 500s without logging the root cause (behavior), which
   made debugging the staging incident take 2 extra hours (impact).
   Try wrapping external calls with specific error types."
```

Specific, behavioral, impact-linked feedback is actionable. Generic criticism teaches nothing.

## Failure modes

- **Mentor too busy for scheduled sessions** — junior feels abandoned; schedule is commitment
- **Only critical feedback** — confidence erodes; acknowledge what's working
- **Doing the work for them** — dependency, not growth; guide with questions
- **No graduated responsibility** — junior stuck on easy tasks at month 6
- **Comparing to senior output** — imposter syndrome; compare to their past self

## Production checklist

- Weekly 30-min mentoring session scheduled and protected
- Session notes documented in shared doc
- Graduated responsibility model with phase indicators defined
- SBI-format feedback in PR reviews (specific, behavioral, impact-linked)
- Mid-task check-ins before PR (not just at review time)
- Junior owns at least one feature end-to-end by month 3

## Resources

- [The Mentoring Handbook (GitLab)](https://about.gitlab.com/handbook/people-group/learning-and-development/mentor/)
- [StaffEng — Onboarding to a Senior Team](https://staffeng.com/guides/work-on-what-matters/)
- [Google engineering practices — code review](https://google.github.io/eng-practices/review/)
- [Thinking, Fast and Slow (Kahneman) — on learning](https://us.macmillan.com/books/9780374533557)
- [Apprenticeship Patterns (Hoover & Oshineye)](https://www.oreilly.com/library/view/apprenticeship-patterns/9780596806842/)
