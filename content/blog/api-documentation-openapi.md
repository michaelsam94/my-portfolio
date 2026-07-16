---
title: "API Docs with OpenAPI"
slug: "api-documentation-openapi"
description: "Generate and maintain API documentation with OpenAPI 3.1: spec-first vs code-first, Swagger UI, client SDK generation, and keeping docs in sync with code."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "API", "Documentation", "DevOps"]
keywords: "OpenAPI documentation, Swagger API docs, OpenAPI 3.1, API spec first, generate API client SDK"
faq:
  - q: "What is OpenAPI and why use it for API documentation?"
    a: "OpenAPI (formerly Swagger) is a machine-readable specification format for describing REST APIs — endpoints, parameters, request/response schemas, authentication, and error codes. It generates interactive documentation (Swagger UI), client SDKs, server stubs, and mock servers from a single source of truth."
  - q: "Should I write the OpenAPI spec first or generate it from code?"
    a: "Spec-first (design the API in OpenAPI before coding) produces better API design and enables parallel frontend/backend development. Code-first (generate spec from annotations) stays in sync automatically but produces specs that mirror implementation quirks rather than ideal design. Use spec-first for public APIs; code-first is acceptable for internal services."
  - q: "How do I keep OpenAPI docs in sync with the implementation?"
    a: "In spec-first workflows, validate implementation against the spec in CI using contract tests. In code-first workflows, generate the spec as a CI artifact and diff against the previous version. Either way, treat spec changes as breaking-change review items."
---

API documentation that lives in a wiki is stale the week it ships. OpenAPI makes your API contract machine-readable — which means it generates interactive docs, client SDKs, mock servers, and CI validation from one source file. I've worked on teams where the OpenAPI spec was the API design document, the test contract, and the client generation input simultaneously. The teams that treat the spec as a first-class artifact ship APIs that clients can integrate with on day one; the teams that write docs after the fact spend half their support time explaining endpoints that don't match the wiki.

## Spec-first example

```yaml
# openapi.yaml
openapi: 3.1.0
info:
  title: Orders API
  version: 1.0.0
  description: Manage customer orders

paths:
  /api/v1/orders:
    get:
      summary: List orders
      parameters:
        - name: cursor
          in: query
          schema: { type: string }
        - name: limit
          in: query
          schema: { type: integer, default: 20, maximum: 100 }
      responses:
        "200":
          description: Paginated order list
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/OrderListResponse"
      security:
        - bearerAuth: []

  /api/v1/orders/{orderId}:
    get:
      summary: Get order by ID
      parameters:
        - name: orderId
          in: path
          required: true
          schema: { type: string, format: uuid }
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Order"
        "403":
          description: Not authorized to access this order
        "404":
          description: Order not found

components:
  schemas:
    Order:
      type: object
      required: [id, status, total]
      properties:
        id: { type: string, format: uuid }
        status: { type: string, enum: [pending, shipped, delivered, cancelled] }
        total: { type: number, format: double }
        createdAt: { type: string, format: date-time }
    OrderListResponse:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Order" }
        nextCursor: { type: string, nullable: true }
        hasMore: { type: boolean }
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

## Interactive docs with Swagger UI

Serve the spec with Swagger UI for interactive exploration:

```python
# FastAPI — built-in OpenAPI
app = FastAPI(
    title="Orders API",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc",     # ReDoc at /redoc
)
```

For standalone spec files, use Swagger UI Docker:

```bash
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/spec/openapi.yaml \
  -v $(pwd)/openapi.yaml:/spec/openapi.yaml \
  swaggerapi/swagger-ui
```

Developers can explore endpoints, see request/response schemas, and try calls against your staging environment.

## Code-first generation

Generate spec from code annotations:

```python
# FastAPI — automatic
@app.get("/api/v1/orders/{order_id}", response_model=Order)
def get_order(order_id: UUID, user: User = Depends(get_current_user)):
    return order_service.get(order_id, user)
# OpenAPI spec generated from type hints and decorators
```

```kotlin
// Spring Boot with springdoc-openapi
@RestController
@RequestMapping("/api/v1/orders")
class OrderController {
    @GetMapping("/{orderId}")
    @Operation(summary = "Get order by ID")
    @ApiResponse(responseCode = "200", description = "Order found")
    @ApiResponse(responseCode = "403", description = "Not authorized")
    fun getOrder(@PathVariable orderId: UUID): Order { ... }
}
```

Code-first stays in sync but tends to produce specs that reflect implementation details (internal fields, inconsistent naming) rather than clean API design.

## Client SDK generation

Generate typed clients from the spec:

```bash
# TypeScript client
npx openapi-generator-cli generate \
  -i openapi.yaml \
  -g typescript-fetch \
  -o clients/typescript

# Kotlin client
openapi-generator-cli generate \
  -i openapi.yaml \
  -g kotlin \
  -o clients/kotlin
```

Mobile and frontend teams integrate with generated clients instead of hand-writing HTTP calls. When the spec changes, regenerate — type errors catch mismatches at compile time.

## Contract testing in CI

Validate implementation matches spec:

```python
# schemathesis — property-based testing against OpenAPI spec
import schemathesis

schema = schemathesis.from_path("openapi.yaml")

@schema.parametrize()
def test_api(case):
    case.call_and_validate()
```

Or use Pact/Dredd for request/response validation. Fail CI if the implementation drifts from the spec.

## Versioning in the spec

Document [API versioning and deprecation](https://blog.michaelsam94.com/backend-api-versioning-deprecation/) in the spec:

```yaml
info:
  version: 2.0.0
  description: |
    ## Changelog
    ### v2.0.0 (2026-01-15)
    - BREAKING: Removed /api/v1/orders/{id}/items endpoint
    - Added cursor pagination to list endpoint
    ### v1.0.0 (2025-06-01)
    - Initial release
```

Mark deprecated endpoints:

```yaml
/api/v1/orders/{orderId}/items:
  get:
    deprecated: true
    description: "Deprecated in v2.0. Use /api/v2/orders/{orderId}?include=items"
```

## Documentation UX that gets used

Specs nobody reads fail the same way as no spec:

- **Try-it-out** enabled in Swagger UI against staging — developers test before coding
- **Examples on every endpoint** — request and response bodies, not just schemas
- **Error catalog** — document all 4xx/5xx with remediation hints
- **Authentication section** — copy-paste curl with token placeholder

```yaml
paths:
  /orders:
    post:
      x-codeSamples:
        - lang: curl
          source: |
            curl -X POST https://api.example.com/orders \
              -H "Authorization: Bearer $TOKEN" \
              -H "Content-Type: application/json" \
              -d '{"items": [{"sku": "ABC", "qty": 1}]}'
```

## Linting and breaking change detection

```bash
# Redocly — breaking change detection between versions
redocly diff openapi-v1.yaml openapi-v2.yaml --fail-on-incompatible

# Spectral — style and security rules
spectral lint openapi.yaml --ruleset .spectral.yaml
```

CI pipeline: lint on PR, diff against main on release branches, block merge on incompatible changes without major version bump.

## Multi-spec federation

Microservices with separate specs need aggregation:

- **BFF spec** — what clients consume (subset of backend capabilities)
- **Service specs** — internal, owned per team
- **Event schemas** — AsyncAPI for webhooks and message contracts

Don't merge 40 service specs into one 10,000-line file — publish federated catalog with search.

Pair with [microservices contract testing Pact](https://blog.michaelsam94.com/microservices-contract-testing-pact/) to verify implementations match published OpenAPI contracts.

## Common production mistakes

Teams get documentation openapi wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

API design for documentation openapi frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.

## Resources

- [OpenAPI Specification 3.1](https://spec.openapis.org/oas/v3.1.0)
- [Swagger UI documentation](https://swagger.io/tools/swagger-ui/)
- [OpenAPI Generator](https://openapi-generator.tech/)
- [FastAPI automatic OpenAPI docs](https://fastapi.tiangolo.com/features/)
- [API versioning and deprecation](https://blog.michaelsam94.com/backend-api-versioning-deprecation/)
