---
title: "Consumer-Driven Contract Testing"
slug: "microservices-contract-testing-pact"
description: "Prevent microservice integration breaks with consumer-driven contract testing using Pact: define expectations, verify providers, and publish contracts."
datePublished: "2025-06-09"
dateModified: "2026-07-17"
tags:
keywords: "Pact contract testing, consumer driven contracts, microservices integration testing, Pact broker, contract testing CI, API contract verification"
faq:
  - q: "What is the difference between contract testing and integration testing?"
    a: "Integration tests require both services running together — slow, flaky, and hard to maintain. Contract tests verify that a provider's API matches what consumers expect, using mocked interactions recorded by the consumer. Each service tests independently in CI, catching breaking changes before deployment."
  - q: "Who writes the contract — the consumer or the provider?"
    a: "The consumer writes the contract. The consumer defines what requests it sends and what responses it expects. The provider verifies it can satisfy those expectations. This inverts traditional API design where the provider defines the contract — consumer-driven means the provider cannot break consumers without explicit agreement."
  - q: "Do I need a Pact Broker?"
    a: "For one consumer and one provider, local contract files work. For teams with multiple consumers of the same provider, a Pact Broker (self-hosted or pactflow.io) stores contracts, tracks verification results, and provides a compatibility matrix showing which consumer-provider pairs are safe to deploy."
---
Your frontend team deploys a change that expects a new field in the user API response. The backend team deploys a refactor that renames that field. Both pass their unit tests. Both deploy successfully. Production breaks because nobody tested the interaction between them.

Integration tests catch this, but full integration test suites are slow, require all services running, and break when any service changes. Contract testing solves the specific problem of service-to-service compatibility — fast, isolated, and run in each service's own CI pipeline.

## How consumer-driven contracts work

1. **Consumer** defines expectations: "when I GET /users/123, I expect a 200 with `{ id, name, email }`."
2. **Consumer test** runs against a mock provider that validates requests and returns canned responses per the contract.
3. **Contract file** (JSON) is generated from the test interactions.
4. **Provider verification** replays the contract against the real provider implementation.
5. **Both pass** → safe to deploy independently.

```
Consumer test → Mock Provider → pact.json → Provider verification → ✅/❌
```

## Consumer-side test with Pact

```python
from pact import Consumer, Provider, Like, EachLike
import pytest

pact = Consumer("OrderService").has_pact_with(Provider("UserService"))
pact.start_service()

@pytest.fixture
def user_service():
    (pact
     .given("user 123 exists")
     .upon_receiving("a request for user 123")
     .with_request("GET", "/users/123")
     .will_respond_with(200, body={
         "id": Like("123"),
         "name": Like("Jane Doe"),
         "email": Like("jane@example.com"),
     }))
    with pact:
        yield pact

def test_get_user(user_service):
    client = UserServiceClient(base_url=pact.uri)
    user = client.get_user("123")
    assert user.name == "Jane Doe"
    assert "@" in user.email
```

`Like("Jane Doe")` means "a string matching this type," not "exactly this value." Contracts capture structure, not specific data.

Running this test generates `order-service-user-service.json` — the contract file.

## Provider verification

The provider replays all interactions from the contract against its real API:

```python
from pact import Verifier

def test_user_service_honors_contract():
    verifier = Verifier(provider="UserService", provider_base_url="http://localhost:8080")

    output, logs = verifier.verify_pacts(
        "./pacts/order-service-user-service.json",
        provider_states_setup_url="http://localhost:8080/_pact/provider_states",
    )
    assert output == (0, '')
```

Provider states set up test data:

```python
@app.post("/_pact/provider_states")
def setup_provider_state(state: dict):
    if state["state"] == "user 123 exists":
        db.seed_user(id="123", name="Jane Doe", email="jane@example.com")
    return {"result": "success"}
```

## Pact matchers for flexible contracts

Exact matching breaks on irrelevant changes. Matchers focus on structure:

```python
from pact import Like, EachLike, Term, Format

body={
    "id": Like("123"),                              # any string
    "email": Term(r".+@.+\..+", "jane@example.com"), # regex match
    "created_at": Format().iso_8601_datetime,         # format match
    "tags": EachLike("premium"),                     # array of strings
    "address": Like({                                 # nested object
        "city": Like("Portland"),
        "zip": Term(r"\d{5}", "97201"),
    }),
}
```

## Pact Broker for multi-team workflows

With multiple consumers, the broker tracks compatibility:

```yaml
# CI pipeline: consumer publishes contract
- name: Publish pact
  run: pact-broker publish ./pacts --consumer-app-version $GIT_SHA --broker-base-url $PACT_BROKER_URL

# CI pipeline: provider verifies against latest contracts
- name: Verify pact
  run: |
    pact-broker can-i-deploy --pacticipant UserService --version $GIT_SHA
    pytest tests/test_provider_verification.py
```

`can-i-deploy` checks whether all consumer contracts are satisfied by the provider version about to deploy. Block deployment if verification fails.

## Can-I-Deploy gate

The deployment safety check:

```bash
# Before deploying UserService v2.3.0
pact-broker can-i-deploy \
  --pacticipant UserService \
  --version 2.3.0 \
  --to-environment production

# Checks:
# ✅ OrderService expects GET /users/{id} → 200 (verified)
# ✅ NotificationService expects GET /users/{id}/email → 200 (verified)
# ❌ AnalyticsService expects GET /users/{id}/preferences → 404 (NOT verified)
# Result: BLOCKED — AnalyticsService contract not satisfied
```

This prevents deploying a provider that breaks any consumer.

## What contract testing does not cover

- **Behavioral correctness** — the provider returns the right shape but wrong data.
- **Performance** — contracts verify structure, not latency.
- **New endpoints** — contracts only cover interactions consumers actually use.
- **Authentication flows** — token exchange and OAuth require separate testing.

Contract testing complements — does not replace — unit tests, integration tests, and end-to-end tests.

## Provider verification workflow

Consumer tests generate pacts; provider verification replays them:

```python
# Provider side (pytest)
@pytest.fixture
def pact_verifier():
    return Verifier(
        provider="OrderService",
        provider_base_url="http://localhost:8000",
    )

def test_honors_consumer_contracts(pact_verifier):
    pact_verifier.verify_with_broker(
        broker_url=PACT_BROKER,
        provider_version=GIT_SHA,
        consumer_version_selectors=[{"mainBranch": True}],
    )
```

Run provider verification in CI on every PR. Consumer tests run in consumer repos — the broker is the contract hub connecting both sides.

## Breaking change workflow

Safe provider evolution:

1. Add optional field → deploy provider → consumers unaffected
2. Add required field → deploy provider first → update consumer pacts → deploy consumers
3. Remove field → deprecate in provider, verify no consumer pact uses it → remove

Never remove a field while any consumer pact still expects it — `can-i-deploy` exists to enforce this ordering.

## Pact vs OpenAPI contract testing

| Approach | Strength | Weakness |
|----------|----------|----------|
| Pact | Tests actual consumer usage | Per-consumer maintenance |
| OpenAPI diff | Single spec source | Doesn't prove consumers use endpoints correctly |
| Schema registry (events) | Async message contracts | Different tooling |

Use Pact for synchronous HTTP between teams you don't control. Use shared OpenAPI when one team owns both sides.

Pair with [CI/CD deployment strategies](https://blog.michaelsam94.com/ci-cd-deployment-strategies-blue-green/) when `can-i-deploy` gates production releases.

## Resources

- [Pact documentation](https://docs.pact.io/)
- [Pact Python library](https://github.com/pact-foundation/pact-python)
- [Pact Broker documentation](https://docs.pact.io/pact_broker)
- [PactFlow (hosted Pact Broker)](https://pactflow.io/)
- [Martin Fowler: Consumer-Driven Contracts](https://martinfowler.com/articles/consumerDrivenContracts.html)

## Production notes for LLM stacks

When `microservices-contract-testing-pact` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `consumer-driven contract testing` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
