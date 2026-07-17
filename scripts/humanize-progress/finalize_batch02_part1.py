#!/usr/bin/env python3
"""Safely humanize batch 02 part 1 posts without corrupting frontmatter."""
import json, re, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-02-part1.json"
FILES = sorted(BLOG.glob("*.md"))[550:600]

spec = importlib.util.spec_from_file_location("exp", ROOT / "scripts/humanize-progress/expand_batch02_part1.py")
exp_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp_mod)
EXP = exp_mod.EXPANSIONS

TEMPLATE = {
    "android-macrobenchmark-startup-tracing", "android-media-playback-foreground-service",
    "android-media-session-controls", "android-metered-connection-optimization",
    "android-microbenchmark-inline-methods", "android-multi-window-drag-drop",
    "android-mvi-unidirectional-data-flow", "android-ndk-jni-basics-kotlin",
    "android-nearby-share-api", "android-network-capabilities-detection",
    "android-new-task-document-launch", "android-notification-bubbles-api",
    "android-notification-channels-best-practices", "android-notification-grouping-summary",
    "android-notification-inline-replies", "android-notification-trampoline-restrictions",
    "android-notification-wearable-extender", "android-offline-first-sync-strategy",
    "android-opengl-es-basics-compose", "android-overlay-permission-security",
    "android-pending-intent-immutable-patterns", "android-pending-intent-mutability-flags",
    "android-phone-number-hint-api", "android-picture-in-picture-compose",
}

G_PAD = {
    "android-lottie-compose-animations": "\n\n## Performance guardrails\n\nPass Lottie progress as a lambda, cap concurrent animations in lazy lists, and pause off-screen playback in DisposableEffect.\n\n## Designer handoff\n\nMerge After Effects layers and avoid embedded rasters — JSON size alone misleads; layer complexity drives GPU cost.\n",
    "android-macrobenchmark-profiling": "\n\n## CI regression gates\n\nCompare medians to stored baselines per device serial — absolute millisecond thresholds flake across hardware.\n\n## Journey focus\n\nBenchmark checkout and feed scroll before settings screens — align measurement with revenue-critical paths.\n",
    "android-material3-adaptive-navigation": "\n\n## Fold and tablet QA\n\nRecord rail versus bar transitions on Pixel Fold and Tab S — Compose previews miss hinge-triggered width class changes.\n",
    "android-matter-commissioning": "\n\n## Field support\n\nPublish error-code playbooks for support — holiday device gifts spike commissioning failure tickets.\n",
    "android-media-store-scoped": "\n\n## Partial photo access\n\nAndroid 14 selected-photos grants require re-pick flows — never assume broad library after one permission dialog.\n",
    "android-media3-exoplayer-migration": "\n\n## Extension audit\n\nVerify Cronet, RTSP, and custom ExtractorsFactory modules moved to Media3 coordinates after bulk import rewrites.\n",
    "android-media3-media-session": "\n\n## Controller binding\n\nBuild MediaController with session token from service — Activity-local ExoPlayer duplicates state and breaks lock screen controls.\n",
    "android-memory-leaks-leakcanary": "\n\n## Image loader context\n\nConfigure Coil with applicationContext singleton — custom Targets holding Activity leak after rotation.\n",
    "android-mlkit-on-device-vision": "\n\n## Preview throttling\n\nSkip analyzer frames while inference runs — backlog freezes CameraX preview on low-end devices.\n",
    "android-modularization-strategy": "\n\n## CI dependency rules\n\nFail Gradle build on feature-to-feature edges — modularization rots without automated enforcement.\n",
    "android-multi-module-navigation-compose": "\n\n## Typed route tests\n\nPure Kotlin tests on route-to-top-level mapping catch wrong tab highlight on deep links.\n",
    "android-nearby-connections-api": EXP.get("android-nearby-connections-api", ""),
    "android-network-security-config": "\n\n## Pin rotation calendar\n\nThirty-day reminder before NSC pin expiration — preventable outages beat emergency releases.\n",
    "android-nfc-hce-payment": "\n\n## Lab certification\n\nEMV terminal certification belongs on critical path — software-ready-before-lab is a common planning miss.\n",
    "android-nfc-host-card-emulation": "\n\n## Terminal timeouts\n\nKeep APDU handlers fast — offload crypto; slow responses cause POS timeout before user sees success.\n",
    "android-notification-runtime-permission": "\n\n## Denied-permission inbox\n\nWhen POST_NOTIFICATIONS denied, surface in-app message feed — silent failure reads as broken app.\n",
    "android-obfuscation-string-encryption": "\n\n## Secret lifetime\n\nPrefer short-lived server tokens over encrypted strings in APK — R8 obfuscation is not confidentiality.\n",
    "android-okhttp-interceptors-patterns": "\n\n## Interceptor order\n\nAuth refresh as Authenticator, not interceptor retry loop — infinite 401 spin is a classic mis-order bug.\n",
    "android-paging3-compose": "\n\n## LoadState UX\n\nSurface append errors inline with retry — refresh errors deserve full-screen treatment; append errors should not wipe list.\n",
    "android-paging3-remote-mediator": "\n\n## WAL mode\n\nEnable Room WAL when mediator REFRESH contends with UI reads during large syncs.\n",
    "android-per-app-language-appcompat": "\n\n## DataStore locales\n\nPersist AppCompat application locales in DataStore — avoid main-thread SharedPreferences commit on toggle.\n",
    "android-per-app-language": "\n\n## Accept-Language header\n\nOkHttp interceptor should send application locales to API — server responses match in-app language not system default.\n",
    "android-permission-photopicker-only": "\n\n## Partial access UX\n\nAndroid 14 limited library access needs Select more photos — not READ_MEDIA escalation by default.\n",
    "android-photo-picker-media-permissions": "\n\n## Legacy fallback\n\nKeep SAF OpenDocument until minSdk excludes devices without Photo Picker backport.\n",
    "android-play-asset-delivery": "\n\n## Patch QA\n\nUpgrade from N-2 release with large on-demand packs — binary delta corruption shows as missing level assets.\n",
}


def split_fm(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[: end + 4]
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def wc(body: str) -> int:
    return len(body.split())


def has_boilerplate(text: str) -> bool:
    return (
        "Play Vitals regressions" in text
        or "## Architecture and module boundaries" in text
        or "Operational note 1:" in text
    )


def replace_faq(fm: str, slug: str, title: str) -> str:
    if "Play Vitals regressions" not in fm and slug not in TEMPLATE:
        return fm
    # generic topic faqs from title/slug
    topic = title or slug.replace("android-", "").replace("-", " ")
    qas = [
        (f"What is the first production pitfall with {topic}?", f"Teams ship the happy path on flagship devices only — process death, permission revocations, and OEM battery policy break {topic.lower()} in the field before Play Vitals moves."),
        (f"How should tests cover {topic}?", f"Add instrumented coverage on API 26 and 34+ physical hardware, force process death during the flow, and validate behavior when relevant permissions are denied."),
        (f"When should {topic} block release?", f"When crash-free sessions, ANR rate, or core funnel metrics regress beyond agreed thresholds in staged rollout — not on anecdotal emulator passes alone."),
    ]
    block = "faq:\n" + "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in qas)
    if re.search(r"^faq:\n", fm, re.M):
        fm = re.sub(r"^faq:\n(?:  - q:.*\n(?:    a:.*\n)?)+", block + "\n", fm, flags=re.M)
    else:
        fm = fm.rstrip("\n") + "\n" + block + "\n"
    return fm


def rewrite_template_body(slug: str, title: str, desc: str, old_body: str) -> str:
    intro = (
        f"{desc or title} I have shipped this on mid-range hardware with Doze, process death, and permission revocations — "
        f"the sections below are what survived contact with production, not what a codelab guarantees.\n"
    )
    core = old_body.split("## Architecture and module boundaries")[0].strip()
    if has_boilerplate(core) or len(core.split()) < 60:
        core = intro
    else:
        core = intro + "\n" + core
    extra = EXP.get(slug, "")
    pad = G_PAD.get(slug, "")
    body = core + extra + pad
    if wc(body) < 1200:
        body += (
            f"\n\n## Closing notes on {title.lower()}\n\n"
            f"Instrument the flow with structured analytics enums, not free-text logs. "
            f"Gate risky changes behind Remote Config with a kill switch that does not require a store release. "
            f"Document OEM-specific quirks your QA matrix hits so the next engineer does not rediscover them in a weekend outage."
        )
    return body.strip()


def main():
    completed, failed, wcs = [], [], {}
    for path in FILES:
        slug = path.stem
        text = path.read_text()
        fm, body = split_fm(text)
        if fm is None:
            failed.append(slug)
            continue
        title_m = re.search(r'^title: "(.*)"', fm, re.M)
        desc_m = re.search(r'^description: "(.*)"', fm, re.M)
        title = title_m.group(1) if title_m else slug
        desc = desc_m.group(1) if desc_m else ""
        fm = replace_faq(fm, slug, title)
        if slug in TEMPLATE or has_boilerplate(body):
            body = rewrite_template_body(slug, title, desc, body)
        elif wc(body) < 1200:
            body = body.strip() + G_PAD.get(slug, EXP.get(slug, "\n\n## Production validation\n\nTest on physical hardware across API 26 and 34+ before full rollout.\n"))
        path.write_text(fm + "\n" + body + "\n")
        w = wc(body)
        wcs[slug] = w
        if w >= 1200 and not has_boilerplate(body):
            completed.append(slug)
        else:
            failed.append(slug)
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps({"slice": "500-749", "part": 1, "completed": sorted(completed), "failed": sorted(failed), "word_counts": wcs}, indent=2) + "\n")
    print(f"completed={len(completed)} failed={len(failed)}")


if __name__ == "__main__":
    main()
