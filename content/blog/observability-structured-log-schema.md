---
title: "Structured Log Schema Design"
slug: "observability-structured-log-schema"
description: "Define a versioned JSON log schema with required fields and evolution rules for Loki and Elasticsearch."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Backend"
  - "Architecture"
keywords: "structured log schema, json logging schema, log field standards, observability logging contract, log schema versioning"
faq:
  - q: "What fields belong in every log line?"
    a: "timestamp, level, message, service.name, environment, trace_id, stable event name."
  - q: "How do I version without breaking queries?"
    a: "schema_version field; additive changes only in minor versions; dual-write on renames."
  - q: "Should logs duplicate trace attributes?"
    a: "Overlap trace_id and business IDs only—not full span attribute dumps."
---

Three teams, three JSON dialects—Loki query for `payment_failed` returned nothing. Versioned schema with required fields and CI validation makes logs queryable at scale.

## Base schema

`schema_version`, ISO timestamp, level, message, `event` (snake_case), service block, trace_id, context object, structured error block.

## JSON Schema CI

Reject logs missing required fields at ingest. `additionalProperties: false` on core schema with namespaced extensions.

## PII

Never raw PAN/email; hash user_id; security review for new context fields.

## SIEM

Export schema to Splunk/Datadog field mappings; webhook on major version bumps.


## Schema registry integration

Publish log schemas to internal registry (similar to Avro for Kafka). CI of each service validates against latest compatible schema version—breaking changes require major bump approval.

## OpenTelemetry log attributes mapping

Map schema fields to OTel log record attributes when using Logs Bridge—`service.name` resource attribute duplicates JSON `service.name`; pick one source of truth to avoid double-indexing in backends.

## Log schema for audit events

Separate `event` namespace `security.*` with immutability requirements—append-only index, longer retention, stricter schema (who, what, when, resource, action, result). Distinct from debug application logs.

## Schema for mobile clients

Mobile apps logging to same pipeline need schema fields `client.os`, `client.app_version`—version as semver string for comparison queries. Crash logs separate schema extension `mobile.crash.*` with symbolication metadata.

## Breaking change communication

Schema major version bump triggers Slack notification to all service owners via CI—30-day dual-write window before enforcement. Silence breaks downstream SIEM parsers.

## SIEM field mapping

Export JSON schema to Splunk/Datadog field mapping configuration when enterprise SIEM ingests application logs—field name mismatches break correlation rules for security detections. Security team signs off schema changes affecting `security.*` events; application team signs off `event` catalog for product analytics.

Schema registry webhook notifies downstream parser owners on major version bump—prevent silent parse failures Friday evening after merge.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.
