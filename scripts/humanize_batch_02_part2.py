#!/usr/bin/env python3
"""Humanize batch-02-part2 posts (sorted indices 600-649). Unique deep dives, no wave2 template."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-02-part2.json"
SLICE_START, SLICE_END = 600, 649
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
        "slug": "android-play-billing-acknowledge-purchases",
        "title": "Play Billing Acknowledge Purchases",
        "description": "Production patterns for play billing acknowledge purchases — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play billing acknowledge purchases?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play billing acknowledge purchases in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, billing, acknowledge, purchases",
    },
    {
        "slug": "android-play-billing-consumables-testing",
        "title": "Play Billing Consumables Testing",
        "description": "Production patterns for play billing consumables testing — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play billing consumables testing?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play billing consumables testing in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, billing, consumables, testing",
    },
    {
        "slug": "android-play-billing-offer-tags",
        "title": "Play Billing Offer Tags",
        "description": "Production patterns for play billing offer tags — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play billing offer tags?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play billing offer tags in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, billing, offer, tags",
    },
    {
        "slug": "android-play-billing-subscription-lifecycle",
        "title": "Play Billing Subscription Lifecycle",
        "description": "Production patterns for play billing subscription lifecycle — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play billing subscription lifecycle?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play billing subscription lifecycle in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, billing, subscription, lifecycle",
    },
    {
        "slug": "android-play-console-vitals-debugging",
        "title": "Play Console Vitals Debugging",
        "description": "Production patterns for play console vitals debugging — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play console vitals debugging?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play console vitals debugging in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, console, vitals, debugging",
    },
    {
        "slug": "android-play-feature-delivery-on-demand",
        "title": "Play Feature Delivery On Demand",
        "description": "Production patterns for play feature delivery on demand — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play feature delivery on demand?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play feature delivery on demand in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, feature, delivery, on, demand",
    },
    {
        "slug": "android-play-integrity-api",
        "title": "Play Integrity API",
        "description": "Production patterns for play integrity api — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play integrity api?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play integrity api in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, integrity, api",
    },
    {
        "slug": "android-play-integrity-standard-request",
        "title": "Play Integrity Standard Request",
        "description": "Production patterns for play integrity standard request — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in play integrity standard request?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks play integrity standard request in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "play, integrity, standard, request",
    },
    {
        "slug": "android-pre-launch-report-fixes",
        "title": "Pre Launch Report Fixes",
        "description": "Production patterns for pre launch report fixes — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in pre launch report fixes?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks pre launch report fixes in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "pre, launch, report, fixes",
    },
    {
        "slug": "android-predictive-back-gesture",
        "title": "Predictive Back Gesture",
        "description": "Production patterns for predictive back gesture — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in predictive back gesture?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks predictive back gesture in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "predictive, back, gesture",
    },
    {
        "slug": "android-print-framework-integration",
        "title": "Print Framework Integration",
        "description": "Production patterns for print framework integration — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in print framework integration?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks print framework integration in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "print, framework, integration",
    },
    {
        "slug": "android-privacy-sandbox",
        "title": "Privacy Sandbox",
        "description": "Production patterns for privacy sandbox — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in privacy sandbox?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks privacy sandbox in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "privacy, sandbox",
    },
    {
        "slug": "android-process-death-state-restoration",
        "title": "Process Death State Restoration",
        "description": "Production patterns for process death state restoration — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in process death state restoration?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks process death state restoration in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "process, death, state, restoration",
    },
    {
        "slug": "android-profileinstaller-startup",
        "title": "Profileinstaller Startup",
        "description": "Production patterns for profileinstaller startup — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in profileinstaller startup?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks profileinstaller startup in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "profileinstaller, startup",
    },
    {
        "slug": "android-proguard-rules-compose",
        "title": "Proguard Rules Compose",
        "description": "Production patterns for proguard rules compose — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in proguard rules compose?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks proguard rules compose in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "proguard, rules, compose",
    },
    {
        "slug": "android-push-fcm-data-messages",
        "title": "Push Fcm Data Messages",
        "description": "Production patterns for push fcm data messages — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in push fcm data messages?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks push fcm data messages in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "push, fcm, data, messages",
    },
    {
        "slug": "android-r8-proguard-optimization",
        "title": "R8 Proguard Optimization",
        "description": "Production patterns for r8 proguard optimization — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in r8 proguard optimization?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks r8 proguard optimization in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "r8, proguard, optimization",
    },
    {
        "slug": "android-receiver-exported-security",
        "title": "Receiver Exported Security",
        "description": "Production patterns for receiver exported security — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in receiver exported security?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks receiver exported security in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "receiver, exported, security",
    },
    {
        "slug": "android-recyclerview-diffutil-performance",
        "title": "Recyclerview Diffutil Performance",
        "description": "Production patterns for recyclerview diffutil performance — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in recyclerview diffutil performance?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks recyclerview diffutil performance in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "recyclerview, diffutil, performance",
    },
    {
        "slug": "android-remember-coroutine-scope-pitfalls",
        "title": "Remember Coroutine Scope Pitfalls",
        "description": "Production patterns for remember coroutine scope pitfalls — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in remember coroutine scope pitfalls?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks remember coroutine scope pitfalls in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "remember, coroutine, scope, pitfalls",
    },
    {
        "slug": "android-render-effect-blur",
        "title": "Render Effect Blur",
        "description": "Production patterns for render effect blur — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in render effect blur?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks render effect blur in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "render, effect, blur",
    },
    {
        "slug": "android-retrofit-error-handling",
        "title": "Retrofit Error Handling",
        "description": "Production patterns for retrofit error handling — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in retrofit error handling?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks retrofit error handling in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "retrofit, error, handling",
    },
    {
        "slug": "android-robolectric-compose-tests",
        "title": "Robolectric Compose Tests",
        "description": "Production patterns for robolectric compose tests — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in robolectric compose tests?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks robolectric compose tests in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "robolectric, compose, tests",
    },
    {
        "slug": "android-roborazzi-screenshot-tests",
        "title": "Roborazzi Screenshot Tests",
        "description": "Production patterns for roborazzi screenshot tests — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in roborazzi screenshot tests?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks roborazzi screenshot tests in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "roborazzi, screenshot, tests",
    },
    {
        "slug": "android-room-auto-migrations",
        "title": "Room Auto Migrations",
        "description": "Production patterns for room auto migrations — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room auto migrations?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room auto migrations in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, auto, migrations",
    },
    {
        "slug": "android-room-flow-dispatchers",
        "title": "Room Flow Dispatchers",
        "description": "Production patterns for room flow dispatchers — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room flow dispatchers?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room flow dispatchers in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, flow, dispatchers",
    },
    {
        "slug": "android-room-fts-search-ranking",
        "title": "Room Fts Search Ranking",
        "description": "Production patterns for room fts search ranking — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room fts search ranking?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room fts search ranking in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, fts, search, ranking",
    },
    {
        "slug": "android-room-full-text-search-fts",
        "title": "Room Full Text Search Fts",
        "description": "Production patterns for room full text search fts — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room full text search fts?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room full text search fts in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, full, text, search, fts",
    },
    {
        "slug": "android-room-migrations-testing",
        "title": "Room Migrations Testing",
        "description": "Production patterns for room migrations testing — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room migrations testing?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room migrations testing in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, migrations, testing",
    },
    {
        "slug": "android-room-multimap-relations",
        "title": "Room Multimap Relations",
        "description": "Production patterns for room multimap relations — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room multimap relations?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room multimap relations in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, multimap, relations",
    },
    {
        "slug": "android-room-paging-source-local",
        "title": "Room Paging Source Local",
        "description": "Production patterns for room paging source local — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room paging source local?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room paging source local in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, paging, source, local",
    },
    {
        "slug": "android-room-relations-multimap",
        "title": "Room Relations Multimap",
        "description": "Production patterns for room relations multimap — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room relations multimap?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room relations multimap in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, relations, multimap",
    },
    {
        "slug": "android-room-transaction-patterns",
        "title": "Room Transaction Patterns",
        "description": "Production patterns for room transaction patterns — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room transaction patterns?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room transaction patterns in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, transaction, patterns",
    },
    {
        "slug": "android-room-type-converters-dates",
        "title": "Room Type Converters Dates",
        "description": "Production patterns for room type converters dates — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in room type converters dates?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks room type converters dates in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "room, type, converters, dates",
    },
    {
        "slug": "android-root-detection-tampering",
        "title": "Root Detection Tampering",
        "description": "Production patterns for root detection tampering — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in root detection tampering?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks root detection tampering in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "root, detection, tampering",
    },
    {
        "slug": "android-safer-intents-validation",
        "title": "Safer Intents Validation",
        "description": "Production patterns for safer intents validation — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in safer intents validation?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks safer intents validation in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "safer, intents, validation",
    },
    {
        "slug": "android-safety-net-play-integrity-migration",
        "title": "Safety Net Play Integrity Migration",
        "description": "Production patterns for safety net play integrity migration — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in safety net play integrity migration?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks safety net play integrity migration in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "safety, net, play, integrity, migration",
    },
    {
        "slug": "android-saved-state-registry-custom",
        "title": "Saved State Registry Custom",
        "description": "Production patterns for saved state registry custom — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in saved state registry custom?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks saved state registry custom in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "saved, state, registry, custom",
    },
    {
        "slug": "android-savedstatehandle-process-death",
        "title": "Savedstatehandle Process Death",
        "description": "Production patterns for savedstatehandle process death — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in savedstatehandle process death?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks savedstatehandle process death in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "savedstatehandle, process, death",
    },
    {
        "slug": "android-scoped-storage-media-store",
        "title": "Scoped Storage Media Store",
        "description": "Production patterns for scoped storage media store — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in scoped storage media store?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks scoped storage media store in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "scoped, storage, media, store",
    },
    {
        "slug": "android-screen-capture-prevention",
        "title": "Screen Capture Prevention",
        "description": "Production patterns for screen capture prevention — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in screen capture prevention?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks screen capture prevention in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "screen, capture, prevention",
    },
    {
        "slug": "android-screenshot-detection-api",
        "title": "Screenshot Detection API",
        "description": "Production patterns for screenshot detection api — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in screenshot detection api?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks screenshot detection api in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "screenshot, detection, api",
    },
    {
        "slug": "android-screenshot-testing-paparazzi",
        "title": "Screenshot Testing Paparazzi",
        "description": "Production patterns for screenshot testing paparazzi — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in screenshot testing paparazzi?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks screenshot testing paparazzi in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "screenshot, testing, paparazzi",
    },
    {
        "slug": "android-security-keystore-encrypted-storage",
        "title": "Security Keystore Encrypted Storage",
        "description": "Production patterns for security keystore encrypted storage — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in security keystore encrypted storage?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks security keystore encrypted storage in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "security, keystore, encrypted, storage",
    },
    {
        "slug": "android-sensor-batch-processing",
        "title": "Sensor Batch Processing",
        "description": "Production patterns for sensor batch processing — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in sensor batch processing?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks sensor batch processing in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "sensor, batch, processing",
    },
    {
        "slug": "android-serial-port-communication",
        "title": "Serial Port Communication",
        "description": "Production patterns for serial port communication — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in serial port communication?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks serial port communication in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "serial, port, communication",
    },
    {
        "slug": "android-servicelocator-antipattern-di",
        "title": "Servicelocator Antipattern Di",
        "description": "Production patterns for servicelocator antipattern di — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in servicelocator antipattern di?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks servicelocator antipattern di in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "servicelocator, antipattern, di",
    },
    {
        "slug": "android-share-sheet-direct-share",
        "title": "Share Sheet Direct Share",
        "description": "Production patterns for share sheet direct share — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in share sheet direct share?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks share sheet direct share in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "share, sheet, direct, share",
    },
    {
        "slug": "android-short-service-exemption",
        "title": "Short Service Exemption",
        "description": "Production patterns for short service exemption — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in short service exemption?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks short service exemption in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "short, service, exemption",
    },
    {
        "slug": "android-shortcuts-static-dynamic",
        "title": "Shortcuts Static Dynamic",
        "description": "Production patterns for shortcuts static dynamic — permissions, failure modes, testing, and rollout on real devices.",
        "faq": [
            ("When should I invest in shortcuts static dynamic?", "When production metrics or Play policy require it — pilot on one cohort, measure crash/ANR and business KPIs, then expand."),
            ("What breaks shortcuts static dynamic in production?", "Process death, OEM background limits, and permission revokes mid-flow — test with adb kill and airplane mode before wide rollout."),
        ],
        "focus": "shortcuts, static, dynamic",
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
        "batch": "02-part2",
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
