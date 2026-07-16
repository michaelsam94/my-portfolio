---
title: "Deterministic Replay for Agent Tests"
slug: "agent-deterministic-replay-testing"
description: "How to test LLM agents deterministically: recorded fixtures, mock LLM responses, VCR-style replay, and eval harnesses that catch regressions before production."
datePublished: "2026-06-23"
dateModified: "2026-06-23"
tags: ["AI Agents", "LLM", "Testing", "Architecture"]
keywords: "agent testing, deterministic replay, LLM mock testing, agent eval harness, VCR agent tests"
faq:
  - q: "Can LLM agent tests be deterministic?"
    a: "The orchestration layer can be fully deterministic even when the model is not. Record LLM responses and tool outputs as fixtures, replay them in CI with mocked model endpoints, and assert on final state and side effects. You test the agent's control flow and error handling without paying for inference or accepting non-deterministic flakiness."
  - q: "What should agent tests assert on?"
    a: "Assert on outcomes, not exact wording: final answer contains expected facts, correct tools were called in order, side effects occurred (DB rows, API calls), and budget limits were respected. Use LLM-as-judge only for subjective quality checks in nightly evals, not in CI gates."
  - q: "How do you record agent traces for replay?"
    a: "Log every LLM request/response pair and tool call/result during a golden run. Serialize to JSON fixtures keyed by scenario name. In CI, swap the real LLM client for a fixture loader that returns recorded responses in sequence. Update fixtures intentionally when prompts or tools change."
---

You cannot unit-test an LLM agent the way you test a REST handler — call it twice, get two different answers, watch CI flip red and green for no reason. But you *can* test everything around the model deterministically: which tools get called, in what order, with what arguments, and what happens when tool three throws a timeout. I've built agent test suites that run in four seconds in CI with zero inference cost by treating the LLM as a recorded dependency, the same way we used VCR cassettes for HTTP a decade ago.

## Separate what you're testing

| Layer | Deterministic? | Test strategy |
|-------|---------------|---------------|
| Tool implementations | Yes | Unit tests |
| Orchestration / state machine | Yes | Replay with mocked LLM |
| Prompt formatting | Mostly | Snapshot tests |
| Model reasoning quality | No | Offline evals, not CI gates |
| End-to-end user experience | No | Nightly eval + human review |

CI should never block on "did the model phrase it nicely." CI should block on "did the agent call `refund_order` with the right order ID when the user asked for a refund."

## The replay pattern

Record a golden trace during development:

```python
# Recording mode (run once manually)
class RecordingLLMClient:
    def __init__(self, real_client, fixture_path):
        self.real = real_client
        self.trace = []
        self.fixture_path = fixture_path

    async def complete(self, messages, tools):
        response = await self.real.complete(messages, tools)
        self.trace.append({"messages": messages, "response": response})
        return response

    def save(self):
        Path(self.fixture_path).write_text(json.dumps(self.trace, indent=2))
```

```python
# Replay mode (CI)
class ReplayLLMClient:
    def __init__(self, fixture_path):
        self.trace = json.loads(Path(fixture_path).read_text())
        self.index = 0

    async def complete(self, messages, tools):
        entry = self.trace[self.index]
        self.index += 1
        # Optional: assert messages match recorded input
        return entry["response"]
```

Run the agent against `ReplayLLMClient`, mock tools with fixed returns, assert on final state. The test validates your orchestrator handles the recorded conversation correctly.

## Fixture maintenance workflow

Fixtures go stale when prompts change. My workflow:

1. **Scenario name** maps 1:1 to a fixture file (`refund_happy_path.json`)
2. **CI failure on sequence mismatch** — if the agent sends different messages than recorded, the replay client raises immediately with a diff
3. **`--record` flag** on the test runner re-records fixtures after intentional prompt changes
4. **Review recorded traces** in PR diffs — they're human-readable JSON

When you add a new tool, re-record affected scenarios. When you change system prompt wording, expect most fixtures to need refresh — that's the cost of the approach, and it's cheaper than flaky live-model CI.

## Testing failure paths

The highest-value agent tests are error recovery, not happy paths:

```python
@pytest.mark.parametrize("failure,expected_recovery", [
    ("search_timeout", "retry_with_broader_query"),
    ("invalid_tool_args", "reformat_and_retry"),
    ("budget_exceeded", "partial_answer_with_explanation"),
])
async def test_error_recovery(failure, expected_recovery):
    tools = MockToolRegistry(fail_on=failure)
    agent = Agent(llm=ReplayLLMClient(f"fixtures/{expected_recovery}.json"), tools=tools)
    result = await agent.run("Find order #12345 status")
    assert result.completed
    assert tools.call_log[-1].name == expected_recovery
```

Record separate fixtures for each failure mode. The model's recovery *wording* varies; the recovery *action* should not.

## Eval vs test

Keep offline evals separate from CI:

- **CI tests**: deterministic replay, <30 seconds, zero API cost
- **Nightly evals**: live model, 50–200 scenarios, LLM-as-judge scoring, trend dashboards
- **Pre-release**: human review of eval regressions

The [trajectory analysis](https://blog.michaelsam94.com/agent-evaluation-trajectory-analysis/) metrics you track in eval — tool accuracy, step efficiency, goal completion — inform prompt changes. CI replay tests ensure those changes don't break orchestration.

## Recording and maintaining fixtures

Fixture hygiene determines whether replay tests stay useful or become noise:

```python
# conftest.py — replay fixture manager
@pytest.fixture
def replay_llm(request):
    fixture_path = Path(f"fixtures/{request.node.name}.json")
    if request.config.getoption("--record"):
        client = RecordingLLMClient(fixture_path)
    else:
        client = ReplayLLMClient(fixture_path)
    yield client
    if request.config.getoption("--record"):
        client.save()
```

Run `pytest --record` locally after intentional prompt changes. Commit updated fixtures in the same PR as the prompt change — reviewers see exactly how model behavior shifted.

Fixture review checklist:
- Tool call sequence unchanged (or change is intentional)
- No new unexpected tool calls added
- Argument shapes match current tool schemas
- Token counts within budget expectations

## Versioning fixtures with agent versions

Tag fixtures with agent configuration hash:

```json
{
  "fixture_version": "2",
  "agent_config_hash": "a3f8c2",
  "system_prompt_version": "support-v2.1.0",
  "recorded_at": "2024-12-27T10:00:00Z",
  "turns": [...]
}
```

When agent config hash changes, CI warns that fixtures may be stale. Prevents silent false greens from fixtures recorded against old agent behavior.

## Integration with CI pipeline

```yaml
# .github/workflows/agent-tests.yml
jobs:
  replay-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/agent/ -x --timeout=30
        env:
          AGENT_MODE: replay  # never live API in CI
  nightly-eval:
    if: github.event_name == 'schedule'
    steps:
      - run: python scripts/run_agent_eval.py --live --scenarios=200
```

Replay tests on every PR (<30 seconds, zero cost). Live eval nightly only — catches reasoning drift replay can't detect.

## Failure modes

- **Fixtures never updated after prompt change** — tests pass but agent behavior regressed
- **Live API in CI** — flaky, expensive, non-deterministic failures
- **Only happy-path fixtures** — error recovery untested until production
- **Fixtures without version metadata** — can't tell which agent config they match
- **Recording in CI** — non-deterministic fixtures committed automatically

## Production checklist

- CI uses replay mode exclusively — zero live API calls
- `--record` flag for local fixture updates after prompt changes
- Fixtures committed in same PR as prompt/model changes
- Error recovery fixtures for each known failure mode
- Fixture metadata includes agent config hash and prompt version
- Nightly live eval separate from CI replay tests

## Resources

- [LangSmith evaluation documentation](https://docs.smith.langchain.com/evaluation)
- [pytest-recording (VCR for Python)](https://github.com/kiwicom/pytest-recording)
- [OpenAI evals framework](https://github.com/openai/evals)
- [Martin Fowler — Testing LLM applications](https://martinfowler.com/articles/engineering-practices-for-LLM-applications.html)
- [OpenTelemetry tracing for test observability](https://opentelemetry.io/docs/concepts/signals/traces/)
