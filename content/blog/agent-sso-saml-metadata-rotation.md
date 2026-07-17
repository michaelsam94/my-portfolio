---
title: "AI Agents: SSO SAML Metadata Rotation"
slug: "agent-sso-saml-metadata-rotation"
description: "Rotate IdP signing certificates for agent admin SSO without downtime — dual-key overlap, SP metadata refresh, and debugging SAML signature failures after corporate IdP updates."
datePublished: "2025-11-04"
dateModified: "2026-07-17"
tags: ["AI", "Agent", "Security", "SSO"]
keywords: "SAML metadata rotation, IdP certificate rollover, agent SSO, SP metadata, Okta Azure AD SAML"
faq:
  - q: "How long should IdP signing certificates overlap during SAML rotation?"
    a: "Minimum 7–14 days where IdP publishes both old and new signing cert in metadata and accepts responses validated with either. Agent SP must load all certs from metadata — not pin single X509 in config file."
  - q: "Who initiates SAML metadata rotation — IdP or agent SP?"
    a: "Usually IdP admin rotates signing cert on schedule (Okta, Azure AD, Google Workspace). Agent platform as SP consumes IdP metadata URL and must refresh automatically. SP signing cert rotation is separate — update IdP with new SP metadata before old SP cert expires."
  - q: "What breaks when metadata rotation is mishandled?"
    a: "All agent admin logins fail with SAML signature validation error — often overnight when IdP switches primary cert without SP picking up new metadata. Enterprise tenants cannot access agent dashboards or tool configuration."
  - q: "How do I test SAML rotation before production?"
    a: "Staging IdP metadata URL, automated test login via Playwright after metadata fetch, monitor auth_success_rate during overlap window. Notify enterprise tenants of rotation window — not required for auto-refresh if implemented correctly."
---
Enterprise tenant Okta rotated SAML signing certificates on a Sunday without telling anyone. Monday 9 AM: every admin login to the agent control plane failed with `SAML response signature invalid`. The SP pinned a single IdP X509 cert in environment variables from 2024. IdP metadata had carried two certs for two weeks — nobody fetched metadata dynamically. Thirty-seven tenants locked out until ops manually pasted new cert and redeployed.

Agent platforms selling to enterprises integrate SAML SSO for admin consoles, tenant configuration, and audit-sensitive tool management. IdPs rotate signing certificates on security schedule. Service providers must consume fresh metadata and trust multiple signing keys during overlap — not static cert files.

## SAML metadata roles

| Party | Metadata contains |
|---|---|
| IdP (Okta, Azure AD) | SSO URL, signing certs, entity ID |
| SP (agent platform) | ACS URL, SP entity ID, optional SP signing cert |

## Dynamic metadata fetch

```python
def get_idp_signing_certs(tenant_id: str) -> list[str]:
    url = tenant_config[tenant_id]["idp_metadata_url"]
    xml = requests.get(url, timeout=10).text
    return parse_signing_certs(xml)

def verify_saml_response(tenant_id: str, saml_xml: bytes):
    certs = get_idp_signing_certs(tenant_id)
    for cert_pem in certs:
        try:
            return XMLVerifier().verify(saml_xml, x509_cert=cert_pem)
        except InvalidSignature:
            continue
    raise SAMLValidationError("No matching IdP signing cert")
```

Try all certs — overlap window requires both old and new.

## Rotation timeline

| Day | IdP signs with | SP must trust |
|---|---|---|
| 0–6 | A (primary) | A, B |
| 7–13 | B (primary) | A, B |
| 14+ | B | B |

## SP metadata rotation

When agent SP signing cert expires: generate new keypair, publish metadata with both SP certs during overlap, upload to each tenant IdP admin console, switch default signing key, remove old cert after IdP confirms.

Automate SP metadata endpoint: `GET https://agent.example.com/saml/metadata/{tenant_slug}`

## Multi-tenant metadata refresh job

```python
def refresh_all_tenant_metadata():
    for tenant in tenants_with_saml():
        try:
            certs = fetch_and_parse(tenant.idp_metadata_url)
            store.update_signing_certs(tenant.id, certs)
        except Exception as e:
            alert(f"saml_metadata_refresh_failed tenant={tenant.id} err={e}")
```

Run hourly — not only on login failure.

## Debugging signature failures

| Error | Likely cause |
|---|---|
| Signature invalid | Stale cert, clock skew |
| Audience mismatch | Wrong SP entity ID in IdP config |
| Assertion expired | NTP drift >5 min |

Enable SAML debug logging without logging full assertion PII.

## Clock skew handling

```python
ALLOWED_SKEW = timedelta(minutes=5)
if not (not_before - ALLOWED_SKEW <= now <= not_on_or_after + ALLOWED_SKEW):
    raise SAMLValidationError("Assertion window")
```

Sync NTP on agent auth pods before IdP rotation week.

## Agent embed SSO

Iframe embed SSO may use separate SP entity ID per embed origin — metadata rotation must update all registered ACS URLs in IdP. Document per-tenant IdP config checklist including embed-specific apps.

## IdP-specific notes

| IdP | Metadata refresh tip |
|---|---|
| Okta | Use org metadata URL not stale app cache |
| Azure AD | FederationMetadata.xml rotates on schedule |
| Google | Automate fetch — download link expires |

## Monitoring and alerts

Track `saml_login_success_rate` by tenant and `saml_signature_failure_total`. Page when success rate drops below 95% for enterprise tenant during business hours.

## Metadata cache headers

Fetch IdP metadata with `Cache-Control: no-cache` request header even if CDN serves long max-age — stale edge copy during rotation overlap causes signature failures until TTL expires.

## Encrypted assertions and SP decryption key rotation

When IdP encrypts assertions, SP decryption cert rotation requires dual decryption keys in SP metadata during overlap — mirror IdP signing rotation pattern. Store SP private keys in cloud KMS; agent admin pods mount signing material via CSI, not unencrypted Kubernetes Secret at rest.

## Federation metadata for multi-region agent admin

Geo-routed admin consoles (`admin.us`, `admin.eu`) must publish consistent SP entity ID or use per-region entity IDs documented in tenant config. Metadata refresh job keyed by `tenant_id + region` prevents EU tenant trusting US-only cert after failover drill.

## Break-glass local admin during SAML outage

Maintain break-glass OIDC or hardware-key local admin behind separate URL and IP allowlist — not a disabled SAML bypass in the main ACS code path. Quarterly drill: simulate IdP metadata fetch failure and verify break-glass login completes within RTO target.

## Separation from tool OAuth tokens

SAML session authenticates human admin to agent console. Tool connections use OAuth refresh tokens stored separately. Runbook must distinguish IdP SAML cert rotation from OAuth client secret rotation — on-call conflating the two extends outages.

## Compliance evidence

Export rotation audit log: metadata fetch timestamps, cert fingerprints added/removed. Retain metadata XML snapshots in immutable object storage for thirteen months for SOC2 auditor requests.

## Runbook excerpt

1. Confirm IdP rotation schedule with tenant
2. Verify metadata URL returns two certs
3. Force metadata refresh in staging — test login
4. Monitor production auth metrics 48h through switch day
5. Post-rotation: confirm old cert removed from metadata fetch

Static cert env vars are rotation incidents waiting for Monday morning.

## Metadata URL TLS and redirect traps

IdP metadata fetchers must follow HTTPS redirects cautiously — HTTP to HTTPS upgrade is fine; cross-domain redirect may indicate compromise. Pin metadata URL hostname in tenant config; reject fetch if final URL host differs from configured host without explicit admin approval.

## Agent embed and SAML ACS URLs

Iframe-embedded agent admin panels require separate SP entity ID or SameSite=None cookie strategy — metadata rotation must update all registered ACS URLs in IdP, including embed-specific apps. Missing one URL surfaces as works in main console, fails in Salesforce embed support tickets. Treat embed ACS URLs as first-class rotation checklist items alongside primary admin console URLs.

## Clock skew and NotOnOrAfter failures

SAML assertion validity windows are tight — SP servers more than 120 seconds skewed from IdP NTP reject valid assertions with `SubjectConfirmation` expiry errors that look like signature failures. Monitor `chrony` or `systemd-timesyncd` on agent admin API nodes; alert before cert rotation week.

## Metadata URL TLS and redirect traps

IdP metadata fetchers must follow HTTPS redirects cautiously — HTTP→HTTPS upgrade is fine; cross-domain redirect may indicate compromise. Pin metadata URL hostname in tenant config; reject fetch if final URL host differs from configured host without explicit admin approval.

## Encrypted assertions and SP private key rotation

When IdP encrypts assertions, SP decryption cert rotation requires dual decryption keys in SP metadata during overlap — mirror IdP signing rotation pattern. Store SP private keys in HSM or cloud KMS; agent admin pods should mount signing material via CSI, not Kubernetes Secret at rest unencrypted.

## Federation metadata for multi-region agent admin

Geo-routed admin consoles (`admin.us`, `admin.eu`) must publish consistent SP entity ID or use per-region entity IDs documented in tenant config. IdP metadata refresh job keyed by `tenant_id + region` prevents EU tenant trusting US-only cert after failover drill.

## Break-glass local admin during SAML outage

Maintain break-glass OIDC or hardware-key local admin behind separate URL and IP allowlist — not disabled SAML bypass in main ACS code path. Quarterly drill: simulate IdP metadata fetch failure and verify break-glass login completes within RTO target without reintroducing permanent backdoor credentials.

## Compliance evidence for enterprise audits

Export rotation audit log: metadata fetch timestamps, cert fingerprints added/removed, assertion validation failure counts. SOC2 auditors ask for proof of dual-key overlap — retain metadata XML snapshots in immutable object storage for 13 months.

## Resources

- [Okta SAML certificate rotation](https://help.okta.com/en-us/content/topics/apps/apps_cert_rotation.htm)
- [Microsoft Entra SAML signing cert rollover](https://learn.microsoft.com/en-us/entra/identity-platform/howto-saml-protocol-reference)
- [SAML 2.0 Metadata spec (OASIS)](https://docs.oasis-open.org/security/saml/v2.0/saml-metadata-2.0-os.pdf)
- [python3-saml / OneLogin toolkit](https://github.com/SAML-Toolkits/python3-saml)
- [SSOReady SAML debugging guide](https://ssoready.com/docs)
