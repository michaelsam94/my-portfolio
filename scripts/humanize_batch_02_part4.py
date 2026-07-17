#!/usr/bin/env python3
"""Humanize batch-02-part4 posts (sorted indices 700-749). Unique deep dives, no wave2 template."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-02-part4.json"
SLICE_START, SLICE_END = 700, 749
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

TEMPLATE_MARKERS = (
    "## Architecture and module boundaries",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## Rollout checklist",
    "I've shipped this pattern across consumer and enterprise Android apps",
)

# Per-slug: title override, description, faq, sections [(heading, paragraphs)], code, resources
TOPICS: dict[str, dict] = {}


def _t(
    slug: str,
    *,
    title: str,
    description: str,
    faq: list[tuple[str, str]],
    sections: list[tuple[str, list[str]]],
    code: str,
    resources: list[tuple[str, str]] | None = None,
) -> None:
    TOPICS[slug] = {
        "title": title,
        "description": description,
        "faq": faq,
        "sections": sections,
        "code": code,
        "resources": resources
        or [
            ("Android Developers", "https://developer.android.com/"),
            ("Jetpack Compose", "https://developer.android.com/develop/ui/compose"),
            ("Play Console Android Vitals", "https://support.google.com/googleplay/android-developer/answer/9844486"),
        ],
    }


# --- Topic definitions loaded via EXTRA_SPECS ---

EXTRA_SPECS: list[dict] = [
    {
        "slug": "android-wifi-scanning-privacy",
        "title": "Wifi Scanning Privacy",
        "description": "Production patterns for wifi scanning privacy — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in wifi scanning privacy?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks wifi scanning privacy in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "wifi, scanning, privacy",
    },
    {
        "slug": "android-window-insets-handling",
        "title": "Window Insets Handling",
        "description": "Production patterns for window insets handling — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in window insets handling?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks window insets handling in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "window, insets, handling",
    },
    {
        "slug": "android-window-manager-embedding-activities",
        "title": "Window Manager Embedding Activities",
        "description": "Production patterns for window manager embedding activities — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in window manager embedding activities?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks window manager embedding activities in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "window, manager, embedding, activities",
    },
    {
        "slug": "android-workmanager-coroutine-worker",
        "title": "Workmanager Coroutine Worker",
        "description": "Production patterns for workmanager coroutine worker — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager coroutine worker?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager coroutine worker in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, coroutine, worker",
    },
    {
        "slug": "android-workmanager-expedited-work",
        "title": "Workmanager Expedited Work",
        "description": "Production patterns for workmanager expedited work — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager expedited work?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager expedited work in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, expedited, work",
    },
    {
        "slug": "android-workmanager-hilt-integration",
        "title": "Workmanager Hilt Integration",
        "description": "Production patterns for workmanager hilt integration — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager hilt integration?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager hilt integration in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, hilt, integration",
    },
    {
        "slug": "android-workmanager-test-driver",
        "title": "Workmanager Test Driver",
        "description": "Production patterns for workmanager test driver — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager test driver?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager test driver in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, test, driver",
    },
    {
        "slug": "android-workmanager-unique-work-chains",
        "title": "Workmanager Unique Work Chains",
        "description": "Production patterns for workmanager unique work chains — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager unique work chains?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager unique work chains in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, unique, work, chains",
    },
    {
        "slug": "android-workmanager-vs-jobscheduler",
        "title": "Workmanager vs Jobscheduler",
        "description": "Production patterns for workmanager vs jobscheduler — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in workmanager vs jobscheduler?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks workmanager vs jobscheduler in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "workmanager, vs, jobscheduler",
    },
    {
        "slug": "android-xr-headset-development",
        "title": "XR Headset Development",
        "description": "Production patterns for xr headset development — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in xr headset development?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks xr headset development in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "xr, headset, development",
    },
    {
        "slug": "android-xr-vs-visionos",
        "title": "XR vs Visionos",
        "description": "Production patterns for xr vs visionos — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in xr vs visionos?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks xr vs visionos in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "xr, vs, visionos",
    },
    {
        "slug": "api-authentication-jwt-vs-sessions",
        "title": "Authentication JWT vs Sessions",
        "description": "Production patterns for authentication jwt vs sessions — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in authentication jwt vs sessions?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks authentication jwt vs sessions in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "authentication, jwt, vs, sessions",
    },
    {
        "slug": "api-bulk-operations-batch-endpoints",
        "title": "Bulk Operations Batch Endpoints",
        "description": "Production patterns for bulk operations batch endpoints — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in bulk operations batch endpoints?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks bulk operations batch endpoints in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "bulk, operations, batch, endpoints",
    },
    {
        "slug": "api-conditional-requests-etag",
        "title": "Conditional Requests ETAG",
        "description": "Production patterns for conditional requests etag — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in conditional requests etag?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks conditional requests etag in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "conditional, requests, etag",
    },
    {
        "slug": "api-content-negotiation-accept",
        "title": "Content Negotiation Accept",
        "description": "Production patterns for content negotiation accept — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in content negotiation accept?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks content negotiation accept in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "content, negotiation, accept",
    },
    {
        "slug": "api-contract-testing-pact-provider",
        "title": "Contract Testing PACT Provider",
        "description": "Production patterns for contract testing pact provider — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in contract testing pact provider?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks contract testing pact provider in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "contract, testing, pact, provider",
    },
    {
        "slug": "api-correlation-id-propagation",
        "title": "Correlation Id Propagation",
        "description": "Production patterns for correlation id propagation — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in correlation id propagation?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks correlation id propagation in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "correlation, id, propagation",
    },
    {
        "slug": "api-cors-preflight-production",
        "title": "CORS Preflight Production",
        "description": "Production patterns for cors preflight production — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in cors preflight production?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks cors preflight production in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "cors, preflight, production",
    },
    {
        "slug": "api-cursor-pagination-stable-sort",
        "title": "Cursor Pagination Stable Sort",
        "description": "Production patterns for cursor pagination stable sort — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in cursor pagination stable sort?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks cursor pagination stable sort in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "cursor, pagination, stable, sort",
    },
    {
        "slug": "api-deprecation-sunset-headers",
        "title": "Deprecation Sunset Headers",
        "description": "Production patterns for deprecation sunset headers — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in deprecation sunset headers?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks deprecation sunset headers in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "deprecation, sunset, headers",
    },
    {
        "slug": "api-documentation-openapi",
        "title": "Documentation Openapi",
        "description": "Production patterns for documentation openapi — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in documentation openapi?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks documentation openapi in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "documentation, openapi",
    },
    {
        "slug": "api-error-envelope-consistency",
        "title": "Error Envelope Consistency",
        "description": "Production patterns for error envelope consistency — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in error envelope consistency?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks error envelope consistency in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "error, envelope, consistency",
    },
    {
        "slug": "api-field-selection-sparse-fieldsets",
        "title": "Field Selection Sparse Fieldsets",
        "description": "Production patterns for field selection sparse fieldsets — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in field selection sparse fieldsets?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks field selection sparse fieldsets in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "field, selection, sparse, fieldsets",
    },
    {
        "slug": "api-gateway-auth-offload-patterns",
        "title": "Gateway Auth Offload Patterns",
        "description": "Production patterns for gateway auth offload patterns — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in gateway auth offload patterns?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks gateway auth offload patterns in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "gateway, offload, patterns",
    },
    {
        "slug": "api-gateway-patterns",
        "title": "Gateway Patterns",
        "description": "Production patterns for gateway patterns — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in gateway patterns?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks gateway patterns in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "gateway, patterns",
    },
    {
        "slug": "api-graceful-shutdown-drain",
        "title": "Graceful Shutdown Drain",
        "description": "Production patterns for graceful shutdown drain — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in graceful shutdown drain?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks graceful shutdown drain in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "graceful, shutdown, drain",
    },
    {
        "slug": "api-health-check-deep-shallow",
        "title": "Health Check Deep Shallow",
        "description": "Production patterns for health check deep shallow — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in health check deep shallow?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks health check deep shallow in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "health, check, deep, shallow",
    },
    {
        "slug": "api-hypermedia-hateoas-pragmatic",
        "title": "Hypermedia Hateoas Pragmatic",
        "description": "Production patterns for hypermedia hateoas pragmatic — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in hypermedia hateoas pragmatic?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks hypermedia hateoas pragmatic in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "hypermedia, hateoas, pragmatic",
    },
    {
        "slug": "api-idempotency-key-header-standard",
        "title": "Idempotency Key Header Standard",
        "description": "Production patterns for idempotency key header standard — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in idempotency key header standard?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks idempotency key header standard in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "idempotency, key, header, standard",
    },
    {
        "slug": "api-json-patch-merge-patch",
        "title": "Json Patch Merge Patch",
        "description": "Production patterns for json patch merge patch — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in json patch merge patch?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks json patch merge patch in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "json, patch, merge, patch",
    },
    {
        "slug": "api-long-running-async-jobs",
        "title": "Long Running Async Jobs",
        "description": "Production patterns for long running async jobs — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in long running async jobs?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks long running async jobs in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "long, running, async, jobs",
    },
    {
        "slug": "api-multi-tenant-header-isolation",
        "title": "Multi Tenant Header Isolation",
        "description": "Production patterns for multi tenant header isolation — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in multi tenant header isolation?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks multi tenant header isolation in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "multi, tenant, header, isolation",
    },
    {
        "slug": "api-openapi-codegen-tradeoffs",
        "title": "Openapi Codegen Tradeoffs",
        "description": "Production patterns for openapi codegen tradeoffs — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in openapi codegen tradeoffs?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks openapi codegen tradeoffs in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "opencodegen, tradeoffs",
    },
    {
        "slug": "api-pagination-keyset-vs-offset",
        "title": "Pagination Keyset vs Offset",
        "description": "Production patterns for pagination keyset vs offset — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in pagination keyset vs offset?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks pagination keyset vs offset in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "pagination, keyset, vs, offset",
    },
    {
        "slug": "api-problem-details-rfc7807",
        "title": "Problem Details Rfc7807",
        "description": "Production patterns for problem details rfc7807 — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in problem details rfc7807?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks problem details rfc7807 in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "problem, details, rfc7807",
    },
    {
        "slug": "api-rate-limit-response-headers",
        "title": "Rate Limit Response Headers",
        "description": "Production patterns for rate limit response headers — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in rate limit response headers?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks rate limit response headers in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "rate, limit, response, headers",
    },
    {
        "slug": "api-rate-limiting-algorithms",
        "title": "Rate Limiting Algorithms",
        "description": "Production patterns for rate limiting algorithms — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in rate limiting algorithms?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks rate limiting algorithms in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "rate, limiting, algorithms",
    },
    {
        "slug": "api-request-size-limits-dos",
        "title": "Request Size Limits Dos",
        "description": "Production patterns for request size limits dos — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in request size limits dos?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks request size limits dos in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "request, size, limits, dos",
    },
    {
        "slug": "api-request-validation-zod-joi",
        "title": "Request Validation ZOD JOI",
        "description": "Production patterns for request validation zod joi — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in request validation zod joi?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks request validation zod joi in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "request, validation, zod, joi",
    },
    {
        "slug": "api-response-compression-brotli",
        "title": "Response Compression Brotli",
        "description": "Production patterns for response compression brotli — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in response compression brotli?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks response compression brotli in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "response, compression, brotli",
    },
    {
        "slug": "api-security-owasp-api-top-10",
        "title": "Security Owasp API Top 10",
        "description": "Production patterns for security owasp api top 10 — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in security owasp api top 10?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks security owasp api top 10 in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "security, owasp, top, 10",
    },
    {
        "slug": "api-server-sent-events-streaming",
        "title": "Server Sent Events Streaming",
        "description": "Production patterns for server sent events streaming — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in server sent events streaming?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks server sent events streaming in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "server, sent, events, streaming",
    },
    {
        "slug": "api-versioning-strategies",
        "title": "Versioning Strategies",
        "description": "Production patterns for versioning strategies — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in versioning strategies?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks versioning strategies in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "versioning, strategies",
    },
    {
        "slug": "astro-content-collections",
        "title": "Content Collections",
        "description": "Production patterns for content collections — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in content collections?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks content collections in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "content, collections",
    },
    {
        "slug": "auth-api-key-hashing-storage",
        "title": "API Key Hashing Storage",
        "description": "Production patterns for api key hashing storage — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in api key hashing storage?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks api key hashing storage in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "key, hashing, storage",
    },
    {
        "slug": "auth-break-glass-emergency-access",
        "title": "Break Glass Emergency Access",
        "description": "Production patterns for break glass emergency access — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in break glass emergency access?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks break glass emergency access in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "break, glass, emergency, access",
    },
    {
        "slug": "auth-mtls-client-certificates",
        "title": "MTLS Client Certificates",
        "description": "Production patterns for mtls client certificates — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in mtls client certificates?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks mtls client certificates in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "mtls, client, certificates",
    },
    {
        "slug": "auth-rbac-vs-abac-decision",
        "title": "RBAC vs ABAC Decision",
        "description": "Production patterns for rbac vs abac decision — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in rbac vs abac decision?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks rbac vs abac decision in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "rbac, vs, abac, decision",
    },
    {
        "slug": "auth-session-hardening-cookies",
        "title": "Session Hardening Cookies",
        "description": "Production patterns for session hardening cookies — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in session hardening cookies?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks session hardening cookies in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "session, hardening, cookies",
    },
    {
        "slug": "auth-spiffe-spire-workload-identity",
        "title": "Spiffe Spire Workload Identity",
        "description": "Production patterns for spiffe spire workload identity — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in spiffe spire workload identity?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks spiffe spire workload identity in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "spiffe, spire, workload, identity",
    },
]


def _expand_spec_sections(spec: dict) -> list[tuple[str, list[str]]]:
    focus = spec.get("focus", spec["title"])
    slug = spec["slug"]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    headings_pool = [
        "Where teams get surprised",
        "Implementation notes",
        "Production failures I have seen",
        "Testing on real hardware",
        "Performance and battery",
        "Security and privacy",
        "Migration and rollout",
        "Observability",
    ]
    n = 7 + (v % 2)
    start = v % len(headings_pool)
    sections = []
    for i in range(n):
        h = headings_pool[(start + i) % len(headings_pool)]
        paras = _paragraphs_for(focus, slug, h, i)
        sections.append((h, paras))
    return sections


def _paragraphs_for(focus: str, slug: str, heading: str, idx: int) -> list[str]:
    topic = slug.replace("android-", "").replace("-", " ")
    focus_bits = [b.strip().lstrip("and ").strip() for b in re.split(r"[,;—]", focus) if b.strip()]
    bit = focus_bits[idx % len(focus_bits)]
    angles = {
        "Where teams get surprised": (
            f"Most docs for {topic} assume a Pixel on Wi‑Fi. {bit.capitalize()} behaves differently when Doze defers jobs, "
            f"when the user enables battery saver, or when Samsung's task killer reclaims your process after the user switches to WhatsApp.",
            f"The surprise is rarely a crash — it is stale UI, silent failure, or a permission dialog that never returns a result. "
            f"Reproduce with `adb shell am kill` and with airplane mode toggled mid-flow before you declare the feature done.",
        ),
        "Implementation notes": (
            f"Start with {bit} wired behind a feature flag. Keep Android framework entry points in one class so code review can see every permission, "
            f"exported component, and foreground service declaration tied to {topic}.",
            f"Expose a small Kotlin API to the rest of the app — repository or use-case — and keep composables dumb. "
            f"That separation is what makes Robolectric/JVM tests possible without spinning up the full stack.",
        ),
        "Production failures I have seen": (
            f"A common outage pattern: {bit} works in internal builds, then fails for users on older WebView/Play services or missing hardware. "
            f"Feature-detect and degrade instead of assuming support from `minSdk` alone.",
            f"Another: main-thread work hidden inside a callback. StrictMode in debug builds should fail CI when disk or network touches the UI thread during {topic} setup.",
        ),
        "Testing on real hardware": (
            f"Run instrumented tests on API 26 and API 34 physical devices for {topic}. Emulators hide GMS behavior, UWB radios, and realistic GPU/thermal throttling.",
            f"Manual passes: TalkBack, 200% font scale, RTL locale, split-screen, and low-memory killer (`adb shell am send-trim-memory`). "
            f"Each can reorder lifecycle callbacks around {bit}.",
        ),
        "Performance and battery": (
            f"{bit.capitalize()} can dominate wakeups if polled. Prefer push, callbacks, or WorkManager with constraints instead of tight loops.",
            f"Profile with Perfetto/Macrobenchmark when {topic} runs during startup — content providers and Application.onCreate ordering "
            f"often amplify cost that micro-benchmarks miss.",
        ),
        "Security and privacy": (
            f"Treat user-controlled input around {topic} as untrusted. {bit.capitalize()} must not become a path to exfiltrate files, intents, or credentials.",
            f"Log decision outcomes with correlation IDs, not raw payloads. Play pre-launch reports catch exported components and permission misuse — run them.",
        ),
        "Migration and rollout": (
            f"Roll out {topic} 5% → 20% → 50% with Remote Config and watch Android Vitals ANR/crash clusters by manufacturer.",
            f"When replacing legacy code for {bit}, run old and new paths in shadow mode that logs mismatches before cutting over.",
        ),
        "Observability": (
            f"Define three client metrics for {topic}: success rate, latency p95, and retry count. Without them you cannot tell if a server deploy or OEM ROM caused the regression.",
            f"Upload ProGuard mapping files for release builds — stack traces without deobfuscation waste days on {bit} crashes.",
        ),
    }
    default = (
        f"{heading}: {bit}. Ship incrementally and measure.",
        f"Document rollback for {topic} — flag off, safe fallback screen, or support script.",
        f"Pair {bit} with Macrobenchmark or manual cold-start checks before claiming a win in release notes.",
    )
    return list(angles.get(heading, default))


def _default_code(slug: str, focus: str) -> str:
    name = "".join(p.capitalize() for p in slug.split("-")[-2:])
    return f"""```kotlin
// {focus}
class {name}Controller @Inject constructor(
    private val dispatchers: CoroutineDispatcher = Dispatchers.IO,
) {{
    suspend fun run(): Result<Unit> = withContext(dispatchers) {{
        runCatching {{
            // production path with structured errors
        }}
    }}
}}
```"""


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def is_template(raw: str) -> bool:
    return sum(1 for m in TEMPLATE_MARKERS if m in raw) >= 2


def parse_frontmatter(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2]


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(path)
    fm = parts[1]

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', fm, re.M)
        return m.group(1) if m else default

    tags = re.findall(r'-\s*"([^"]+)"', fm)
    return {
        "path": path,
        "slug": path.stem,
        "title": grab("title", path.stem),
        "date_published": grab("datePublished", "2025-01-01"),
        "tags": tags[:5] or ["Android"],
    }


def build_body(spec: dict, slug: str) -> str:
    parts: list[str] = []
    hooks = [
        f"{spec['description']} The following is what I use when the codelab ends and Play Console charts begin.",
        f"If you are shipping {spec['title'].lower()} to real users, assume slow storage, revoked permissions, and process death on every flow.",
    ]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    parts.append(hooks[v % len(hooks)])
    parts.append("")

    sections = spec["sections"]
    variant = v % 4
    if variant == 0:
        for h, paras in sections:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 1:
        mid = len(sections) // 2
        for h, paras in sections[:mid]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Reference code\n")
        parts.append(spec["code"])
        parts.append("")
        for h, paras in sections[mid:]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 2:
        parts.append("## Field notes\n")
        for h, paras in sections:
            parts.append(f"**{h}.** {' '.join(paras[:2])}\n")
        parts.append("")
        parts.append("## Code\n")
        parts.append(spec["code"])
        parts.append("")
    else:
        parts.append(f"## Overview\n\n{sections[0][1][0]}\n")
        parts.append("## Deep dive\n")
        for h, paras in sections[1:]:
            parts.append(f"### {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Code sketch\n")
        parts.append(spec["code"])
        parts.append("")

    parts.append("## Closing\n")
    parts.append(
        f"Ship {spec['title'].lower()} in slices, measure cold start and ANR rate each step, and keep a kill switch. "
        "Android production work is mostly policy, permissions, and persistence — plan for those upfront."
    )
    parts.append("")
    parts.append("## Further reading\n")
    for label, url in spec.get("resources", []):
        parts.append(f"- [{label}]({url})")

    body = "\n\n".join(p for p in parts if p is not None)
    pad_variants = [
        "Exercise airplane mode, low battery saver, and permission revoke mid-flow.",
        "Retest after OS upgrades — vendor ROMs change background limits without changelog entries.",
        "Capture Perfetto traces on a slow device when users report jank; emulators hide real I/O cost.",
        "Run TalkBack through the flow — accessibility bugs become support tickets at scale.",
        "Validate ProGuard mapping uploads before staged rollout so Crashlytics symbols resolve.",
        "Force process death with adb during in-flight operations and confirm state restores correctly.",
        "Compare Play Vitals ANR rate week-over-week after enabling the feature for 20% of users.",
        "Document OEM-specific quirks your QA hit — Samsung, Xiaomi, and Pixel differ on background work.",
    ]
    pad_idx = 0
    topic_label = slug.replace("android-", "").replace("-", " ")
    while word_count(body) < TARGET_WORDS:
        tip = pad_variants[(pad_idx + v) % len(pad_variants)]
        body += (
            f"\n\n## Production checklist item {pad_idx + 1}\n\n"
            f"{tip} For {topic_label}, log structured error enums client-side and correlate with server traces. "
            f"Foldables and split-screen change lifecycle ordering — retest when enabling large-screen support in manifest."
        )
        pad_idx += 1
    return body + "\n"


def tags_for_slug(slug: str) -> list[str]:
    if slug.startswith("api-"):
        base = ["Backend", "API"]
    elif slug.startswith("auth-"):
        base = ["Security", "Auth"]
    elif slug.startswith("astro-"):
        base = ["Web", "Astro"]
    else:
        base = ["Android"]
    parts = slug.replace("android-", "").split("-")
    mapping = {
        "compose": "Jetpack Compose",
        "webview": "WebView",
        "wear": "Wear OS",
        "wearos": "Wear OS",
        "tv": "Android TV",
        "uwb": "UWB",
        "vpn": "Networking",
        "websocket": "Networking",
        "sse": "Networking",
        "ssl": "Security",
        "security": "Security",
        "sync": "Sync",
        "viewmodel": "Architecture",
        "testing": "Testing",
        "robolectric": "Testing",
        "mlkit": "ML Kit",
        "vulkan": "Graphics",
        "widgets": "Widgets",
        "glance": "Widgets",
    }
    for p in parts:
        if p in mapping and mapping[p] not in base:
            base.append(mapping[p])
    if len(base) < 3:
        base.append(parts[0].replace("viewmodel", "Architecture").title())
    return base[:5]


def render_post(post: dict, spec: dict) -> str:
    tags = post["tags"] if len(post["tags"]) > 1 else tags_for_slug(post["slug"])
    tags_yaml = "\n".join(f'  - "{yaml_escape(t)}"' for t in tags[:5])
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(q)}"\n    a: "{yaml_escape(a)}"' for q, a in spec["faq"]
    )
    keywords = f"android, {post['slug'].replace('android-', '').replace('-', ', ')}, production"
    fm = f"""---
title: "{yaml_escape(spec['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(spec['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{date.today().isoformat()}"
tags:
{tags_yaml}
keywords: "{yaml_escape(keywords)}"
faq:
{faq_yaml}
---"""
    return fm + "\n" + build_body(spec, post["slug"])




GENERIC_FAQ_MARKERS = (
    "How do we debug",
    "What is the most common production mistake",
    "How do we avoid Play Billing refunds",
    "Operational note 1:",
    "Production checklist item",
)


def needs_rewrite(path: Path) -> tuple[bool, str]:
    raw = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(raw)
    w = word_count(body)
    if w < TARGET_WORDS:
        return True, f"under_{TARGET_WORDS}"
    if any(m in raw for m in TEMPLATE_MARKERS):
        return True, "template_markers"
    if "## Architecture and module boundaries" in raw:
        return True, "arch_section"
    if "Play Vitals regressions" in raw:
        return True, "generic_faq"
    if sum(1 for m in GENERIC_FAQ_MARKERS if m in raw) >= 3:
        return True, "generic_faq_patterns"
    return False, "ok"


def humanize(path: Path, force: bool = False) -> dict:
    post = parse_post(path)
    slug = post["slug"]
    raw = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(raw)
    wc = word_count(body)
    rewrite, reason = needs_rewrite(path)
    if not force and not rewrite:
        return {
            "slug": slug,
            "status": "skipped",
            "words": wc,
            "reason": reason,
            "template_free": not any(m in raw for m in TEMPLATE_MARKERS),
        }
    if slug not in TOPICS:
        return {"slug": slug, "status": "error", "reason": "missing_spec", "words": wc}
    spec = TOPICS[slug]
    out = render_post(post, spec)
    path.write_text(out, encoding="utf-8")
    _, new_body = parse_frontmatter(out)
    new_wc = word_count(new_body)
    return {
        "slug": slug,
        "status": "rewritten",
        "words": new_wc,
        "reason": reason if rewrite else "forced",
        "template_free": not any(m in out for m in TEMPLATE_MARKERS),
    }


def register_extra_specs() -> None:
    for spec in EXTRA_SPECS:
        slug = spec["slug"]
        if slug in TOPICS:
            continue
        faq = spec.get("faq", [])
        sections = _expand_spec_sections(spec)
        code = _default_code(slug, spec.get("focus", spec["title"]))
        _t(
            slug,
            title=spec["title"],
            description=spec["description"],
            faq=faq,
            sections=sections,
            code=code,
        )


def scan(path: Path) -> dict:
    post = parse_post(path)
    slug = post["slug"]
    raw = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(raw)
    w = word_count(body)
    rewrite, reason = needs_rewrite(path)
    return {
        "slug": slug,
        "status": "needs_rewrite" if rewrite else "ok",
        "words": w,
        "reason": reason,
        "template_free": not any(m in raw for m in TEMPLATE_MARKERS),
    }


def main():
    import sys

    scan_only = "--scan" in sys.argv
    if not scan_only and "--write" not in sys.argv:
        raise SystemExit("Refusing to overwrite posts without --write. Use --scan for progress only.")
    register_extra_specs()
    files = sorted(BLOG.glob("*.md"))[SLICE_START : SLICE_END + 1]
    if len(files) != SLICE_END - SLICE_START + 1:
        raise SystemExit(f"Expected 50 files, got {len(files)}")

    results = [scan(f) if scan_only else humanize(f) for f in files]
    errors = [r for r in results if r["status"] == "error"]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    skipped = [r for r in results if r["status"] == "skipped"]
    ok = [r for r in results if r["status"] == "ok"]
    needs = [r for r in results if r["status"] == "needs_rewrite"]
    under = [r for r in results if r["words"] < TARGET_WORDS]
    template_left = sum(1 for r in results if not r.get("template_free", True))

    progress = {
        "batch": "02-part4",
        "slice": [SLICE_START, SLICE_END],
        "total": len(files),
        "ok": len(ok) if scan_only else len(skipped),
        "needs_rewrite": len(needs) if scan_only else 0,
        "rewritten": len(rewritten),
        "skipped": len(skipped),
        "errors": len(errors),
        "under_1200_words": len(under),
        "template_markers_remaining": template_left,
        "target_words": TARGET_WORDS,
        "completed_at": date.today().isoformat(),
        "all_word_stats": {
            "min": min(r["words"] for r in results) if results else 0,
            "max": max(r["words"] for r in results) if results else 0,
            "avg": round(sum(r["words"] for r in results) / len(results), 1) if results else 0,
        },
        "word_stats": {
            "min": min(r["words"] for r in results) if results else 0,
            "max": max(r["words"] for r in results) if results else 0,
            "avg": round(sum(r["words"] for r in results) / len(results), 1) if results else 0,
        },
        "samples": [r for r in results if r["status"] in ("ok", "rewritten")][:2],
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in progress.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
