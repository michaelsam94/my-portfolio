---
title: "Consent Management for Apps"
slug: "consent-management-platforms"
description: "Implement GDPR and CCPA consent in mobile and web apps: CMP SDKs, consent strings, preference centers, and analytics gating patterns."
datePublished: "2025-04-30"
dateModified: "2025-04-30"
tags: ["Security"]
keywords: "consent management platform, GDPR consent, CCPA opt-out, IAB TCF, mobile app consent, analytics gating"
faq:
  - q: "What is a Consent Management Platform (CMP)?"
    a: "A CMP collects, stores, and signals user privacy choices—cookie consent on web, tracking permission on mobile—for regulations like GDPR, ePrivacy, and CCPA. It presents first-layer banners and preference centers, generates standardized consent strings (IAB TCF on web), and gates third-party SDKs until appropriate consent is granted."
  - q: "Do mobile apps need a CMP like websites?"
    a: "Yes when you use advertising SDKs, analytics with personal data, or cross-app tracking subject to GDPR, ATT on iOS, or Google Play data safety requirements. Native CMP SDKs (OneTrust, Usercentrics, Ketch) wrap legal text, geolocation rules, and SDK initialization gates. ATT prompt is separate from GDPR consent but part of the same UX flow."
  - q: "How do I gate analytics SDKs on consent?"
    a: "Initialize analytics only after consent for the Analytics purpose is true. Use a consent listener that fires on update—user changes mind in preference center, SDKs must disable collection and flush queues. Store consent locally with timestamp and policy version for audit; sync server-side for logged-in users."
---

Privacy regulation turned "drop Firebase in AppDelegate" into a compliance project. Consent Management Platforms coordinate what users agreed to, what vendors can run, and what your backend logs—all with audit trails regulators expect. Getting it wrong means SDKs firing before consent, ad networks reading IDFA without legal basis, or a preference center that does not actually disable tracking.

## Regulatory landscape (practical)

**GDPR (EU/EEA/UK)** — lawful basis required before non-essential processing; consent must be freely given, specific, informed, withdrawable.

**ePrivacy / cookie directive** — storage and tracking technologies need consent except strictly necessary.

**CCPA/CPRA (California)** — opt-out of sale/share; "Do Not Sell" link; limited opt-out for sensitive processing.

**iOS ATT** — Apple prompt for cross-app tracking; independent of GDPR banner but UX-coupled.

**Google Play Data safety** — declare data collection; match runtime behavior.

CMPs encode jurisdiction rules: show GDPR banner in DE, CCPA link in CA, minimal friction elsewhere where legally permitted.

## Architecture overview

```
App launch
    │
    ▼
CMP SDK init (no trackers yet)
    │
    ▼
Geo + policy version → show banner?
    │
    ├─ Accept / Reject / Customize
    │
    ▼
Consent record persisted (local + server)
    │
    ▼
Initialize allowed SDKs only
```

Third-party SDKs stay uninitialized until their purpose passes consent check.

## Android integration pattern

```kotlin
class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        ConsentManager.init(this) { status ->
            if (status.analyticsAllowed) {
                FirebaseAnalytics.getInstance(this).setAnalyticsCollectionEnabled(true)
            }
            if (status.adsPersonalizationAllowed) {
                MobileAds.initialize(this) { /* ... */ }
            }
        }
    }
}
```

Use CMP vendor SDK callbacks—do not hardcode banner logic unless you enjoy legal review cycles.

## Web IAB TCF 2.2

Web CMPs register with IAB Europe, serve `__tcfapi`:

```javascript
__tcfapi('getTCData', 2, (tcData, success) => {
  if (success && tcData.purpose.consents[1]) {
    loadAnalytics();
  }
});
```

Ad tags read consent string from CMP before bidding. Google Certified CMP list required for serving ads in EEA/UK.

## Preference center requirements

Users must reopen choices easily—persistent "Privacy settings" in app menu, not buried in onboarding once.

Each toggle maps to:

- Purpose ID (analytics, personalization, functional)
- Vendor list affected
- Immediate effect on SDK state

```kotlin
fun onConsentUpdated(preferences: ConsentPreferences) {
    analytics.setEnabled(preferences.analytics)
    crashReporting.setEnabled(preferences.functional) // often legitimate interest or strictly necessary—legal decides
    adSdk.setPersonalization(preferences.ads)
    repository.syncConsent(preferences.toPayload())
}
```

## Server-side sync

For authenticated users, POST consent record:

```json
{
  "policyVersion": "2025-03-01",
  "purposes": { "analytics": true, "ads": false },
  "timestamp": "2025-04-30T12:00:00Z",
  "source": "preference_center"
}
```

Backend gates marketing emails, profile enrichment, and third-party data shares. Client-only consent fails web-to-app continuity.

## Common failures

**SDK auto-init in manifest.** Firebase, Facebook SDK historically auto-started—disable until consent via manifest flags or delayed init.

**Pre-ticked boxes.** Invalid under GDPR for non-essential cookies.

**Consent wall.** Blocking service until accept-all may be unlawful depending on jurisdiction.

**No withdrawal path.** Must be as easy as granting consent.

**Mismatch with Data safety / privacy nutrition labels.** Store listing claims must match runtime.

## Vendor selection criteria

- Google-certified (if serving ads in EEA)
- Mobile SDK quality (Compose/SwiftUI support)
- Geolocation rule engine
- Offline consent storage
- Export for DSAR audits

OneTrust, Usercentrics, Cookiebot, Ketch, Didomi—evaluate against your stack and legal counsel's templates.

## Consent string and TCF 2.2

IAB Transparency & Consent Framework (TCF) encodes consent in a compact string passed to ad tech:

```
Consent string → parsed by vendors → determines which purposes/legal bases apply
```

TCF 2.2 (2024) removed legitimate interest for most purposes — explicit consent required. If serving ads in EEA, your CMP must be Google-certified and TCF 2.2 compliant.

```javascript
// Reading consent from CMP API
__tcfapi('getTCData', 2, (tcData, success) => {
  if (success) {
    const analyticsAllowed = tcData.purpose.consents[1]; // purpose 1 = analytics
    if (analyticsAllowed) initAnalytics();
  }
});
```

Never initialize analytics or ad SDKs before consent callback resolves.

## Mobile-specific consent patterns

**Android:** Use Google User Messaging Platform (UMP) SDK for GDPR/TCF consent before AdMob initialization:

```kotlin
ConsentInformation.getInstance(context).requestConsentInfoUpdate(
    activity,
    params,
    { UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity) { /* init ads */ } },
    { /* handle error */ }
)
```

**iOS:** ATT prompt is separate from GDPR consent — both may be required. ATT covers IDFA tracking; GDPR covers data processing. Show ATT after GDPR consent decision, not before.

**Cross-platform:** Store consent server-side keyed by user ID or device fingerprint hash. Web consent should carry to app on login — don't re-prompt unnecessarily.

## Audit trail requirements

Regulators and DSAR requests require proof of consent:

```sql
CREATE TABLE consent_records (
    user_id UUID NOT NULL,
    consent_version TEXT NOT NULL,      -- policy version user saw
    purposes JSONB NOT NULL,            -- {analytics: true, marketing: false}
    granted_at TIMESTAMPTZ NOT NULL,
    ip_hash TEXT,                       -- hashed, not raw IP
    user_agent TEXT,
    source TEXT NOT NULL                -- 'web_banner', 'ios_settings', 'api'
);
```

Retain consent records for statute of limitations (typically 3–7 years depending on jurisdiction). Never delete on user request — anonymize instead.

## Failure modes

- **SDK auto-init before consent** — processes data before user choice; GDPR violation
- **Consent not synced to backend** — marketing emails sent despite opt-out
- **No withdrawal UI** — GDPR requires as-easy-as-grant withdrawal path
- **Stale consent after policy update** — old consent invalid for new purposes
- **TCF string not passed to ad partners** — partners can't respect consent

## Production checklist

- No analytics/ad SDK init before consent callback
- Consent stored server-side with version, timestamp, purposes
- Withdrawal path as prominent as grant path
- TCF 2.2 compliant CMP if serving ads in EEA
- ATT prompt after GDPR consent on iOS
- Consent audit trail retained per legal retention period
- Privacy policy version tracked with each consent record

Log consent string version with every analytics event — GDPR audits ask for proof of consent state at event time, not current banner state.

## Resources

- [IAB Europe Transparency & Consent Framework](https://iabeurope.eu/transparency-consent-framework/)
- [Google CMP certification requirements](https://support.google.com/admob/answer/13554116)
- [Apple App Tracking Transparency](https://developer.apple.com/documentation/apptrackingtransparency)
- [ICO consent guidance (UK)](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/guidance-on-the-use-of-cookies-and-similar-technologies/)
