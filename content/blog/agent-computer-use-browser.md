---
title: "Computer-Use and Browser Agents"
slug: "agent-computer-use-browser"
description: "Building browser and computer-use agents: screenshot loops, DOM access, action reliability, and why most demos fail in production on real websites."
datePublished: "2026-06-21"
dateModified: "2026-06-21"
tags: ["AI Agents", "LLM", "Automation", "Architecture"]
keywords: "computer use agent, browser agent, LLM web automation, screenshot agent, Playwright agent"
faq:
  - q: "What is a computer-use agent?"
    a: "A computer-use agent is an LLM that controls a desktop or browser environment through a loop of observe → plan → act. It receives screenshots or DOM snapshots, decides the next action (click, type, scroll), executes it via automation APIs, and repeats until the task completes. The model acts as a general-purpose operator rather than calling fixed API tools."
  - q: "Should browser agents use screenshots or DOM access?"
    a: "Use DOM access when you control or trust the target site — it's faster, cheaper, and more precise than vision. Use screenshots for cross-site generalization, canvas-heavy UIs, or sites that obfuscate DOM structure. Production systems often hybridize: DOM-first with screenshot fallback when element lookup fails."
  - q: "Why do browser agents fail in production?"
    a: "Production sites have dynamic loading, cookie banners, CAPTCHAs, A/B layouts, and anti-bot measures that demos skip. Agents also drift — a pixel coordinate that worked once fails after a CSS change. Reliability requires retries, element-based selectors, explicit wait conditions, and human escalation paths."
---

Computer-use agents — the ones that look at your screen and click things — are the most impressive demo in AI right now and the least reliable thing you can put in production without serious engineering. I've watched a browser agent book a flight in a staged environment, then fail for twenty minutes on a real airline site because a cookie banner moved a button three pixels and the vision model clicked empty space. The gap between "it works in the demo" and "it works on the internet" is entirely about how you observe, act, and recover — not which foundation model you picked.

## The observe-act loop

Every browser agent is the same loop:

1. **Observe** — screenshot, accessibility tree, or DOM snapshot
2. **Plan** — model decides next action given goal + history
3. **Act** — execute click/type/navigate via Playwright/Puppeteer
4. **Verify** — did the page change as expected?

```python
async def agent_loop(page, goal: str, max_steps: int = 30):
    history = []
    for step in range(max_steps):
        observation = await capture_state(page)  # DOM + optional screenshot
        action = await llm.plan(goal, observation, history)
        if action.type == "done":
            return action.result
        result = await execute_action(page, action)
        history.append({"action": action, "result": result})
        if result.error:
            action = await llm.recover(goal, observation, history, result.error)
    raise AgentTimeout(f"Failed after {max_steps} steps")
```

The model is the planner; Playwright is the executor. Never let the model emit raw JavaScript to `page.evaluate()` unless you enjoy XSS in your automation pipeline.

## DOM-first beats vision-first

Screenshot-only agents are expensive (vision tokens per step) and fragile (layout shifts break coordinate clicks). When I build for a known workflow — internal admin tools, specific SaaS products — I give the model structured DOM:

```python
async def capture_dom(page) -> str:
    elements = await page.evaluate("""
        () => [...document.querySelectorAll('button, a, input, [role=button]')]
            .filter(el => el.offsetParent !== null)
            .slice(0, 100)
            .map((el, i) => ({
                id: i,
                tag: el.tagName,
                text: el.innerText?.slice(0, 80),
                role: el.getAttribute('role'),
                type: el.type,
            }))
    """)
    return json.dumps(elements, indent=2)
```

The model returns `{"action": "click", "element_id": 7}` instead of `{"x": 342, "y": 891}`. Element IDs are re-resolved each turn, so layout shifts don't break the chain.

Reserve screenshots for:
- Unknown third-party sites where DOM is hostile or obfuscated
- Canvas/WebGL interfaces (maps, design tools)
- Verifying visual state ("is the chart red or green?")

## Action reliability patterns

**Explicit waits, not fixed sleeps.** `await page.wait_for_selector('[data-testid=checkout]')` beats `await asyncio.sleep(3)` every time. Agents that sleep randomly add minutes and still race the UI.

**Retry with backoff on stale elements.** DOM references go stale after navigation. Catch `ElementHandle` errors, re-capture state, replan.

**Checkpoint human approval.** Before irreversible actions — purchase, delete, send email — pause for [human-in-the-loop approval](https://blog.michaelsam94.com/agent-human-in-the-loop-approval/). I've seen agents double-click "Confirm" because the first click didn't register in the screenshot.

**Session persistence.** Log in once, save cookies to encrypted storage, reuse across runs. Making the agent re-authenticate through MFA every invocation is neither safe nor usable.

## Anti-bot and CAPTCHA reality

If your agent targets sites you don't control, assume:
- Rate limiting after N requests from one IP
- CAPTCHA on suspicious patterns
- Terms of service that prohibit automation

Run browser agents from residential proxy pools only when you have legal clearance. For production internal automation, target sites with official APIs first — use browser agents only where no API exists. The [tool selection routing](https://blog.michaelsam94.com/agent-tool-selection-routing/) layer should prefer API tools and fall back to browser control.

## Observability you actually need

Log every step: observation hash, action, DOM diff, screenshot URL (stored, not inlined), latency, token cost. When an agent fails at step 17, you need a replayable trace — not a user report of "it got stuck." OpenTelemetry spans per step with the model's reasoning (when available) make debugging tractable.

Set budgets: max steps, max cost per run, max wall time. An agent that loops clicking "Next" on a paginated table for 200 steps is a runaway bill, not intelligence.

## Production checklist

- [ ] HITL approval before irreversible actions (purchase, delete, send)
- [ ] Max steps, cost, and wall-time budgets per run
- [ ] Screenshot + DOM diff logged per step for replay
- [ ] Prefer official APIs over browser automation where available
- [ ] Session cookies stored encrypted, scoped to target domain

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get computer use browser wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using computer use browser loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When computer use browser misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Playwright documentation](https://playwright.dev/docs/intro)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Anthropic computer use documentation](https://docs.anthropic.com/en/docs/build-with-claude/computer-use)
- [Accessibility tree inspection guide (MDN)](https://developer.mozilla.org/en-US/docs/Glossary/Accessibility_tree)
- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
