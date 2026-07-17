---
title: "OAuth Device Flow for TVs"
slug: "oauth2-device-flow-tv"
description: "Implement OAuth 2.0 device authorization flow for TVs, CLI tools, and IoT devices: user codes, polling, token exchange, and UX patterns."
datePublished: "2025-09-21"
dateModified: "2026-07-17"
tags: ["Security", "Authentication", "IoT", "API"]
keywords: "OAuth device flow, device authorization grant, OAuth TV login, user code flow, RFC 8628, smart TV authentication, input-constrained devices"
faq:
  - q: "When is the device flow required instead of authorization code flow?"
    a: "Use device flow when the client cannot receive redirects—smart TVs, streaming sticks, printers, CLI tools on headless servers, and IoT devices without browsers. The user authorizes on a separate device (phone or laptop) while the constrained device polls for tokens."
  - q: "How long should device codes remain valid?"
    a: "Typical device code lifetime is 15–30 minutes. Polling interval starts at 5 seconds with exponential backoff per RFC 8628. Expire codes aggressively—stale codes sitting on a TV screen are a social engineering vector if someone walks by and uses them."
  - q: "Can device flow use PKCE?"
    a: "PKCE is not part of the standard device flow—the device never handles an authorization code directly. Security relies on the user physically entering the code on a trusted secondary device. Bind tokens to device_id claims where possible."
---

Your streaming app runs on a TV with no keyboard and no way to handle OAuth redirects. Email-and-password on a TV remote is worse. The OAuth 2.0 device authorization flow (RFC 8628) splits authentication across two devices: the TV displays a short user code and URL, the user opens that URL on their phone, logs in, and enters the code. The TV polls the token endpoint until it receives tokens. Netflix, YouTube, and Spotify all use variants of this pattern.

## Flow sequence

```
TV (device)                    Auth Server              Phone (browser)
  |--- device authorization -->|                              |
  |<-- device_code, user_code -|                              |
  |    display: "Go to tv.app/activate"                        |
  |    display: "Enter: WXYZ-1234"                             |
  |                            |<--- user visits /activate ----|
  |                            |<--- user logs in + enters code|
  |--- poll token endpoint --->|                              |
  |    (every 5s)              |                              |
  |<-- access_token -----------|  (after user authorizes)     |
```

## Device authorization request

```javascript
const res = await fetch("https://auth.example.com/oauth/device/code", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams({
    client_id: "tv-app",
    scope: "openid profile streaming:play",
  }),
});
const data = await res.json();
// {
//   device_code: "GmRhmhcxhwAz8ejaBd2",
//   user_code: "WDJB-MJHT",
//   verification_uri: "https://auth.example.com/activate",
//   verification_uri_complete: "https://auth.example.com/activate?user_code=WDJB-MJHT",
//   expires_in: 1800,
//   interval: 5
// }
```

Display `verification_uri` and `user_code` prominently on the TV screen.

## Polling for tokens

```javascript
async function pollForToken(deviceCode, interval = 5) {
  while (true) {
    await sleep(interval * 1000);

    const res = await fetch("https://auth.example.com/oauth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
        device_code: deviceCode,
        client_id: "tv-app",
      }),
    });

    const data = await res.json();

    if (res.ok) return data; // { access_token, refresh_token, ... }

    switch (data.error) {
      case "authorization_pending":
        continue; // user hasn't authorized yet
      case "slow_down":
        interval += 5; // server requests slower polling
        continue;
      case "expired_token":
        throw new Error("Device code expired — restart flow");
      case "access_denied":
        throw new Error("User denied authorization");
      default:
        throw new Error(`Token error: ${data.error}`);
    }
  }
}
```

Respect `slow_down` responses. Aggressive polling gets you rate-limited.

## TV display UX

```
┌─────────────────────────────────────┐
│                                     │
│   To sign in, visit:                │
│   tv.example.com/activate           │
│                                     │
│   And enter this code:              │
│                                     │
│        W D J B  -  M J H T          │
│                                     │
│   Code expires in 28:45             │
│                                     │
│   Waiting for authorization...      │
│                                     │
└─────────────────────────────────────┘
```

Requirements:
- Large, high-contrast text readable from 10 feet
- Monospace font for the code
- Countdown timer showing expiry
- QR code encoding `verification_uri_complete` for phone camera scan
- Clear error state when code expires

## Activation page (browser)

```html
<form action="/activate" method="POST">
  <label>Enter the code shown on your TV:</label>
  <input name="user_code" pattern="[A-Z0-9]{4}-[A-Z0-9]{4}"
         placeholder="XXXX-XXXX" autocomplete="off" />
  <button type="submit">Continue</button>
</form>
```

After login, show consent screen: "Allow TV App to access your profile and play content?"

## Refresh tokens on devices

TVs stay logged in for months. Issue long-lived refresh tokens with device binding:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "refresh_token_expires_in": 31536000
}
```

Store refresh tokens in the device's secure storage (Android Keystore, iOS Keychain). On logout, revoke the refresh token server-side.

## Security considerations

- **Rate limit** device authorization requests per IP—prevents code farming.
- **Normalize user codes** — accept with or without dash, case-insensitive.
- **Short code alphabet** — exclude ambiguous characters (0/O, 1/I/L).
- **Audit log** every device authorization with `device_code`, IP, and user agent.
- **Bind tokens** to `device_id` claim; reject token use from different device fingerprints.

## CLI tool variant

Same flow works for headless servers:

```bash
$ mycli login
Visit https://cli.example.com/activate and enter: HGKL-9P2M
Waiting... Done. Logged in as michael@example.com.
```

The CLI polls in the background while the user authorizes in a browser.

## Polling interval and UX

RFC 8628 recommends `interval` from authorization server (minimum seconds between polls). Implement exponential backoff with jitter on client:

```javascript
let interval = 5; // seconds from server
while (Date.now() < expiresAt) {
  await sleep(interval * 1000 + Math.random() * 1000);
  const res = await pollDeviceToken(deviceCode);
  if (res.status === "authorized") return res.tokens;
  if (res.status === "slow_down") interval += 5;
  if (res.status === "expired_token") throw new Error("Code expired");
}
```

Show countdown on TV: "Code expires in 4:32." Users abandon slow flows — target authorization completion under 60 seconds from code display.

## Error states on constrained displays

TV apps can't show stack traces. Map OAuth errors to actionable UI:

| Error | User message | Action |
|-------|--------------|--------|
| `expired_token` | Code expired | Generate new code button |
| `access_denied` | Permission denied | Retry or contact support |
| `authorization_pending` | (no message) | Keep polling |
| Network failure | Can't reach server | Check connection |

Log full OAuth error codes server-side with `device_code` correlation ID.

## PKCE and device flow

Device flow traditionally omits PKCE (no client secret on device). For hybrid apps with confidential backend:

1. TV displays user code
2. Backend holds `device_code` + client credentials
3. Mobile/web authorization completes
4. Backend polls and delivers tokens to TV via secure channel (WebSocket, push)

This keeps client secrets off the TV firmware while still using standard device authorization UX.

Pair with [OAuth2 client credentials for M2M](https://blog.michaelsam94.com/oauth2-client-credentials-m2m/) for backend services that poll on behalf of devices.

## Production checklist

- [ ] User code alphabet excludes ambiguous characters (0/O, 1/I)
- [ ] Countdown timer shown on TV for code expiry
- [ ] Polling respects `slow_down` and `interval` from server
- [ ] Refresh tokens stored in Android Keystore / iOS Keychain
- [ ] Rate limiting on device authorization endpoint

Device flow UX fails when codes expire silently — always show a visible countdown and auto-refresh the code 30 seconds before expiry without requiring the user to navigate back.

## Federation and enterprise TVs

Enterprise deployments may require device flow against a corporate IdP with conditional access. Surface MDM compliance status on the activation page and block token issuance when device posture fails. Document token lifetime policies for shared conference-room displays — shorter refresh TTL than living-room TVs.

## Telemetry for product teams

Funnel metrics: code displayed → activation page loaded → consent granted → token issued. Drop-off between steps indicates UX friction, not OAuth bugs. Segment by TV OEM and app version — firmware WebView differences cause disproportionate failures on older platforms.

## Resources

- [RFC 8628 — OAuth Device Authorization Grant](https://www.rfc-editor.org/rfc/rfc8628) — full specification
- [Google OAuth device flow](https://developers.google.com/identity/protocols/oauth2/limited-input-device) — Google's implementation
- [Auth0 device authorization flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/device-authorization-flow) — setup guide
- [GitHub device flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow) — CLI authentication example
- [OAuth.net device flow overview](https://oauth.net/2/grant-types/device-code/) — grant type summary
