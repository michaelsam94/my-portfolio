---
title: "Conversation State Machines for Chat Applications"
slug: "rag-conversation-state-machine"
description: "Model agent dialogues as explicit finite state machines — slot filling, tool-gated transitions, interrupt handling, persistence, and recovery from LLM non-determinism."
datePublished: "2025-04-22"
dateModified: "2026-07-17"
tags: ["AI Agents", "Dialogue", "State Machine", "Architecture"]
keywords: "conversation state machine agent, dialogue management LLM, slot filling FSM, agent session state, multi-turn agent architecture"
faq:
  - q: "When should an agent use a state machine vs free-form LLM dialogue?"
    a: "Use a state machine when the task has ordered steps, legal confirmations, slot requirements, or side effects (payments, deletes). Free-form dialogue works for open Q&A; FSMs work for workflows where skipping a step creates liability or bad data."
  - q: "Where does the LLM sit relative to the state machine?"
    a: "The FSM owns transitions and guards; the LLM fills slots, generates natural language, and proposes intents. Never let the model directly commit state transitions without validation — parse structured output and let the FSM decide."
  - q: "How do you persist state across server restarts and tab closes?"
    a: "Serialize FSM state (current state, filled slots, pending confirmations) to durable storage keyed by session ID. Version the schema. On resume, hydrate the FSM and inject a compact state summary into the LLM context — not the full transition log."
---

Free-form retrieval loops feel elegant until a user confirms a $2,000 refund, the model forgets it already collected the order ID, and support finds three duplicate API calls in the audit log. **Conversation state machines** bring structure to multi-turn agents: explicit states, guarded transitions, slot validation, and recovery paths that do not depend on the model remembering where the dialogue left off.

The LLM remains the voice and the parser. The FSM is the source of truth for what step you are on and what is allowed next. That separation is what makes agent workflows auditable, testable, and safe under non-deterministic generation.

## FSM vs ReAct loop

| Aspect | ReAct / retrieval loop | Conversation FSM |
|--------|-------------------|------------------|
| Control flow | Implicit in prompt | Explicit states and edges |
| Side effects | Any turn | Guarded transitions only |
| Testability | Scenario prompts | State table unit tests |
| Recovery | Re-prompt and hope | Defined rollback states |
| UX predictability | Variable | Consistent step order |

Most production agents combine both: an outer FSM for workflow phase, an inner ReAct loop for retrieval and reasoning within a state.

## Anatomy of an agent conversation FSM

States represent ** phases**, not individual messages:

```
                    ┌─────────────┐
         start ───► │   GREETING  │
                    └──────┬──────┘
                           │ intent=refund
                           ▼
                    ┌─────────────┐
              ┌──── │ COLLECT_ID  │ ◄─────┐
              │     └──────┬──────┘       │ invalid_id
              │            │ valid_id     │
              │            ▼              │
              │     ┌─────────────┐       │
              │     │ VERIFY_ELIG │───────┘
              │     └──────┬──────┘
              │            │ eligible
              │            ▼
              │     ┌─────────────┐
              │     │ CONFIRM_AMT │──► CANCELLED (interrupt)
              │     └──────┬──────┘
              │            │ user_confirmed
              │            ▼
              │     ┌─────────────┐
              └──── │  EXECUTE    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  COMPLETE   │
                    └─────────────┘
```

Each state defines:

- **Required slots** — data that must exist before exiting
- **Allowed tools** — subset available in this phase
- **Prompt template** — system instructions scoped to the state
- **Transitions** — events that move to the next state
- **On-enter / on-exit hooks** — side effects, analytics, idempotency keys

## Implementation with typed states and events

```python
# dialogue/fsm.py
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Optional

class State(Enum):
    GREETING = auto()
    COLLECT_ORDER_ID = auto()
    VERIFY_ELIGIBILITY = auto()
    CONFIRM_AMOUNT = auto()
    EXECUTE_REFUND = auto()
    COMPLETE = auto()
    CANCELLED = auto()

class Event(Enum):
    INTENT_REFUND = auto()
    SLOT_ORDER_ID = auto()
    ELIGIBLE = auto()
    INELIGIBLE = auto()
    USER_CONFIRMED = auto()
    USER_DECLINED = auto()
    INTERRUPT_CANCEL = auto()

@dataclass
class SessionSlots:
    order_id: Optional[str] = None
    amount_cents: Optional[int] = None
    eligibility_checked: bool = False

@dataclass
class Transition:
    target: State
    guard: Callable[["SessionContext"], bool] = lambda _: True
    action: Callable[["SessionContext"], None] = lambda _: None

@dataclass
class SessionContext:
    state: State = State.GREETING
    slots: SessionSlots = field(default_factory=SessionSlots)
    session_id: str = ""
    idempotency_key: str = ""

TRANSITIONS: dict[tuple[State, Event], Transition] = {
    (State.GREETING, Event.INTENT_REFUND): Transition(State.COLLECT_ORDER_ID),
    (State.COLLECT_ORDER_ID, Event.SLOT_ORDER_ID): Transition(
        State.VERIFY_ELIGIBILITY,
        guard=lambda ctx: ctx.slots.order_id is not None,
    ),
    (State.VERIFY_ELIGIBILITY, Event.ELIGIBLE): Transition(State.CONFIRM_AMOUNT),
    (State.VERIFY_ELIGIBILITY, Event.INELIGIBLE): Transition(State.COMPLETE),
    (State.CONFIRM_AMOUNT, Event.USER_CONFIRMED): Transition(
        State.EXECUTE_REFUND,
        action=lambda ctx: setattr(ctx, "idempotency_key", f"refund-{ctx.slots.order_id}"),
    ),
    (State.EXECUTE_REFUND, Event.USER_CONFIRMED): Transition(State.COMPLETE),
}

# Global interrupts
for state in State:
    if state not in (State.COMPLETE, State.CANCELLED):
        TRANSITIONS[(state, Event.INTERRUPT_CANCEL)] = Transition(State.CANCELLED)

def apply_event(ctx: SessionContext, event: Event) -> bool:
    key = (ctx.state, event)
    if key not in TRANSITIONS:
        return False
    t = TRANSITIONS[key]
    if not t.guard(ctx):
        return False
    t.action(ctx)
    ctx.state = t.target
    return True
```

Unit test every `(state, event)` pair. FSM bugs are cheaper to fix in Python than in prompt prose.

## LLM integration: parse, don't trust

Each turn, the LLM produces **structured output** alongside natural language:

```python
from pydantic import BaseModel
from typing import Literal

class TurnParse(BaseModel):
    detected_event: Optional[str]  # maps to Event enum
    slot_updates: dict[str, str] = {}
    user_message: str
    confidence: float

async def handle_turn(ctx: SessionContext, user_text: str) -> str:
    parse = await llm_parse(user_text, current_state=ctx.state.name, schema=TurnParse)

    # Global interrupt check first
    if parse.detected_event == "INTERRUPT_CANCEL":
        apply_event(ctx, Event.INTERRUPT_CANCEL)
        return "Understood — I've cancelled that. How else can I help?"

    # Apply slot updates before state events
    if "order_id" in parse.slot_updates:
        ctx.slots.order_id = validate_order_id(parse.slot_updates["order_id"])
        if ctx.slots.order_id:
            apply_event(ctx, Event.SLOT_ORDER_ID)

    # State-specific event handling
    if ctx.state == State.CONFIRM_AMOUNT and parse.detected_event == "USER_CONFIRMED":
        if parse.confidence < 0.85:
            return "Just to confirm — should I proceed with the refund? Reply yes or no."
        apply_event(ctx, Event.USER_CONFIRMED)
        await execute_refund(ctx)  # side effect ONLY after transition

    return await llm_respond(ctx, user_text, parse)
```

Low-confidence confirmations get a clarification turn — never execute side effects on ambiguous "sure" / "ok" without state-appropriate guardrails.

## Persistence and hydration

Serialize minimal state:

```json
{
  "schema_version": 2,
  "state": "CONFIRM_AMOUNT",
  "slots": {
    "order_id": "ORD-8842",
    "amount_cents": 5000,
    "eligibility_checked": true
  },
  "idempotency_key": "",
  "updated_at": "2025-04-23T14:22:00Z"
}
```

On session resume, inject into context window:

```
[SESSION STATE]
Workflow: refund
Phase: awaiting user confirmation
Order ID: ORD-8842
Amount: $50.00
Do not re-collect filled slots unless user explicitly corrects them.
```

Schema versioning matters. Migrations on load:

```python
def hydrate(raw: dict) -> SessionContext:
    version = raw.get("schema_version", 1)
    if version == 1:
        raw = migrate_v1_to_v2(raw)
    return SessionContext(
        state=State[raw["state"]],
        slots=SessionSlots(**raw["slots"]),
        session_id=raw["session_id"],
        idempotency_key=raw.get("idempotency_key", ""),
    )
```

## Side effects and idempotency

Side effects belong in **on-enter hooks** of states like EXECUTE_REFUND, not in LLM tool handlers that the model can invoke arbitrarily.

```python
async def execute_refund(ctx: SessionContext) -> None:
    if not ctx.idempotency_key:
        raise WorkflowError("missing idempotency key")
    result = await payments_api.refund(
        order_id=ctx.slots.order_id,
        amount_cents=ctx.slots.amount_cents,
        idempotency_key=ctx.idempotency_key,
    )
    if result.already_processed:
        metrics.increment("refund.idempotent_replay")
```

If the user double-sends "yes confirm," the FSM may fire twice — idempotency keys prevent duplicate charges.

## Tool availability per state

Restrict tools to reduce model error surface:

```python
TOOLS_BY_STATE = {
    State.COLLECT_ORDER_ID: ["lookup_order"],
    State.VERIFY_ELIGIBILITY: ["check_refund_policy"],
    State.CONFIRM_AMOUNT: [],  # no tools — conversation only
    State.EXECUTE_REFUND: ["process_refund"],
}
```

Pass only allowed tool schemas in the API call for the current state. Models invoke fewer wrong tools when they cannot see irrelevant ones.

## Handling LLM non-determinism

Models go off-script. Defenses:

1. **Invalid event ignored** — if `(state, event)` not in transition table, stay in state and re-prompt with state-specific instructions
2. **Slot validation** — regex, API lookup, or type check before accepting slot updates
3. **Max turns per state** — after N failed collection attempts, transition to HANDOFF_HUMAN
4. **State timeout** — sessions in CONFIRM_AMOUNT >24h auto-expire to GREETING with apology message

Log `fsm.invalid_transition_attempts` and `fsm.stuck_state_timeouts` — high rates mean prompt or parse schema needs work.

## Observability

Track funnel metrics per workflow:

- `fsm.entered_state` counts by state
- `fsm.transition` counts by `(from, event, to)`
- `fsm.time_in_state` histogram
- `fsm.dropoff_rate` — sessions that never reach COMPLETE
- `fsm.interrupt_rate` by state

Product reads funnels; engineering reads stuck states. A cliff at VERIFY_ELIGIBILITY means policy API latency or confusing copy — not "the model is dumb."

## Verifying transitions in CI

**Table tests** for transitions — every row in `TRANSITIONS` gets a pytest case.

**Simulation tests** — scripted user messages through the full FSM with mocked LLM parse responses.

**Property tests** — no path from EXECUTE_REFUND to COLLECT_ORDER_ID without explicit reset event.

**Chaos** — random invalid events never cause side effects; assert invariants on idempotency key presence before refund.

## Anti-patterns

**States per message** ("turn 3 state") — too granular; states become unmanageable.

**LLM chooses next state via free text** — parse structured events only.

**Side effects in tool definitions the model controls** — move to FSM-guarded hooks.

**No global cancel** — users always need an escape hatch; trapping them in slot collection destroys trust.

**Duplicating state in prompt and FSM** — one source of truth; prompt reflects FSM, not vice versa.

## The takeaway

Conversation state machines make agent workflows reliable by separating dialogue control from language generation. Model the happy path and interrupts explicitly, parse structured events from LLM output, guard side effects with idempotency keys, and persist versioned state for resume. The FSM is boring code — that is the point. Boring control flow with an eloquent LLM front end beats an eloquent model winging your refund policy.

## Resources

- [Rasa — Dialogue Policies and Stories](https://rasa.com/docs/rasa/policies/)
- [AWS — Step Functions for human-in-the-loop workflows](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-amazon-states-language.html)
- [XState — State machine concepts](https://xstate.js.org/docs/about/concepts.html)
- [OpenAI — Structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [Google — Dialogflow CX state handlers](https://cloud.google.com/dialogflow/cx/docs/concept/handler)
