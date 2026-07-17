---
title: "AI Agents: Egress Filtering Dns"
slug: "agent-egress-filtering-dns"
description: "DNS-layer egress control for agent sandboxes—split-horizon resolution, allowlist enforcement, SSRF prevention, and observability when tools fetch arbitrary URLs."
datePublished: "2026-02-05"
dateModified: "2026-02-05"
tags: ["AI", "Agent", "Egress"]
keywords: "egress filtering, DNS firewall, agent SSRF, split horizon DNS, network policy, tool sandbox, CoreDNS, allowlist, zero trust egress"
faq:
  - q: "Why filter egress at DNS instead of only using firewall rules?"
    a: "Firewalls block IPs and ports; agents generate hostnames dynamically from LLM tool calls. DNS filtering intercepts resolution—if a hostname is not on the allowlist, the sandbox never learns an IP. Combine both: DNS for policy at hostname granularity, firewall for defense in depth against IP literal bypasses."
  - q: "How do agents bypass DNS filtering?"
    a: "Common paths: requesting raw IP addresses, URL encodings, DNS over HTTPS to external resolvers, IPv6 literals, redirects to forbidden hosts, and metadata service endpoints (169.254.169.254). Block IP literals in tool URL validators, force traffic through a proxy resolver you control, and deny link-local ranges at the network layer."
  - q: "What domains belong on an agent tool allowlist?"
    a: "Start minimal: your API domains, approved SaaS integrations (Slack, GitHub Enterprise), and public documentation hosts your retrieval needs. Avoid wildcard `*.com`. Use category-based approval workflows—security reviews add CNAME targets, not individual URLs. Separate allowlists per agent profile (research vs code-execution)."
  - q: "How do I debug tool failures caused by DNS blocks?"
    a: "Log every denied query with `{agent_id, tool_name, qname, policy_rule, request_id}`—never log full URLs containing secrets. Expose a staging mirror with permissive policy for developer testing. Surface `EGRESS_DENIED: hostname not allowlisted` as structured tool errors the LLM can relay to users."
---
An agent with web-search tools exfiltrated internal config in a red-team exercise. The prompt never mentioned secrets—the model chain-read a wiki page, followed a link to an internal hostname, and pasted JSON into the chat. Network policy allowed outbound 443 because "agents need the internet." Nobody had controlled **name resolution**. Fixing it required DNS-layer egress filtering: sandboxes resolve only through a policy resolver that returns NXDOMAIN for everything except an approved set of zones.

Agent tool runtimes fetch URLs the LLM chooses. That is SSRF at scale with a stochastic attacker. IP firewall rules alone fail because hostnames multiply, CDNs shift addresses, and operators cannot predict tomorrow's `api.new-vendor.io`. DNS filtering is the choke point where you enforce **which names may become connections** before packets leave the pod.

## Threat model for agent egress

Agent sandboxes face three egress classes:

**Intentional integrations.** GitHub, Jira, customer webhooks—stable hostnames, contractually approved.

**User-directed fetches.** "Summarize this article" → arbitrary HTTPS URLs.

**Adversarial exfiltration.** Prompt injection steering tools toward `metadata.google.internal`, `169.254.169.254`, or `internal-admin.corp`.

Controls must address:

- Direct IP requests (`https://10.0.0.5/admin`)
- DNS rebinding (allowlisted hostname resolves to internal IP seconds later)
- Redirect chains landing on forbidden hosts
- DNS tunneling over long TXT queries (rare but noisy in logs)

Assume the LLM is compromised for policy design. The sandbox network must contain damage.

## Architecture: policy DNS resolver in the sandbox path

```
Pod → /etc/resolv.conf → CoreDNS (cluster) → Policy Forwarder → Upstream 8.8.8.8
                              ↓ deny
                         NXDOMAIN + audit log
```

Every agent pod uses a cluster DNS configuration that forwards external queries to a **policy resolver** service—not directly to public DNS.

Components:

1. **Policy engine.** Evaluates `(agent_profile, qname, qtype)` against allowlists and blocklists.
2. **Response policy zone (RPZ)** or custom plugin returning NXDOMAIN or sinkhole IP for denies.
3. **Audit sink.** Structured logs to SIEM; metrics for deny rate by agent profile.
4. **Egress proxy (optional).** HTTP CONNECT proxy that re-validates hostname after DNS—catches IP literal bypass.

```yaml
# coredns/Corefile fragment
.:53 {
    errors
    health
    kubernetes cluster.local in-addr.arpa ip6.arpa {
        pods verified
        fallthrough in-addr.arpa ip6.arpa
    }
    forward . policy-dns.egress.svc.cluster.local:5353
    cache 30
}
```

```python
# policy_resolver/server.py
import dns.message
import dns.rcode
from allowlist import is_allowed

def handle_query(envelope: dict) -> dns.message.Message:
    qname = envelope["qname"].rstrip(".")
    profile = envelope["agent_profile"]
    req = dns.message.from_wire(envelope["wire"])

    if not is_allowed(profile, qname):
        log_denied(profile, qname, envelope["request_id"])
        resp = dns.message.make_response(req)
        resp.set_rcode(dns.rcode.NXDOMAIN)
        return resp

    return forward_to_upstream(req)
```

## Building allowlists that survive agent chaos

Start from **deny-all, permit-by-exception**. Each allowlist entry records:

- `hostname` or suffix (`.githubusercontent.com` narrower than `.github.com`)
- `agent_profiles` that may resolve it
- `owner` and `expiry` for quarterly review
- `max_redirect_depth` when fetched via HTTP tool

```python
# allowlist.py
from dataclasses import dataclass

@dataclass
class AllowRule:
    suffix: str  # e.g. "api.github.com" or ".stripe.com"
    profiles: frozenset[str]
    expires_at: str | None = None

RULES = [
    AllowRule("api.github.com", frozenset(["code-agent", "research-agent"])),
    AllowRule(".docs.example.com", frozenset(["*"])),
    AllowRule(".slack.com", frozenset(["ops-agent"])),
]

def is_allowed(profile: str, qname: str) -> bool:
    for rule in RULES:
        if profile not in rule.profiles and "*" not in rule.profiles:
            continue
        if qname == rule.suffix or qname.endswith("." + rule.suffix.lstrip(".")):
            return True
    return False
```

Avoid glob explosions. If marketing needs "any news site," use a categorized proxy service with its own filtered catalog instead of opening `.com`.

## SSRF hardening beyond DNS

DNS filtering is necessary, not sufficient. Layer these in the tool runtime:

**Block IP literals and private ranges.**

```typescript
import { BlockList } from "net";
import { lookup } from "dns/promises";

const blocked = new BlockList();
blocked.addSubnet("10.0.0.0", 8, "ipv4");
blocked.addSubnet("172.16.0.0", 12, "ipv4");
blocked.addSubnet("192.168.0.0", 16, "ipv4");
blocked.addSubnet("169.254.0.0", 16, "ipv4");
blocked.addSubnet("127.0.0.0", 8, "ipv4");

export async function safeFetch(url: string): Promise<Response> {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:") throw new Error("HTTPS only");

  const host = parsed.hostname;
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host) || host.includes(":")) {
    throw new Error("IP literals forbidden");
  }

  const { address } = await lookup(host);
  if (blocked.check(address)) throw new Error("Resolved to blocked range");

  return fetch(url, { redirect: "manual" }); // inspect redirects manually
}
```

**Pin resolution and reconnect.** Resolve once, connect to that IP, set TLS SNI to original host—defeats simple rebinding if re-resolution on redirect is forbidden.

**Redirect cap.** Max three hops; re-run allowlist check on each `Location` hostname.

**Disable DoH in sandbox.** Block UDP/TCP 443 to known DoH providers if browsers or runtimes embed them.

## Kubernetes and service mesh integration

For Kubernetes agent workers:

- `NetworkPolicy` default deny egress except to policy DNS and egress proxy.
- `dnsPolicy: None` with explicit `dnsConfig` pointing to cluster CoreDNS.
- Service mesh (Istio/Linkerd) `ServiceEntry` only for approved external hosts—mesh and DNS policy must match or debugging becomes hell.

For serverless agent runners, inject resolver via sidecar or VPC DNS firewall (Route 53 Resolver DNS Firewall, Azure DNS Private Resolver policies).

## Observability and incident response

Metrics:

- `dns_egress_denied_total{profile, qname_suffix}`
- `dns_query_latency_ms` p95
- `tool_fetch_egress_error_total` by reason (`NXDOMAIN`, `blocked_ip`, `redirect_denied`)

Alerts:

- Deny rate spike on a single profile → possible prompt injection campaign
- Allowlist miss on critical integration → deployment broke prod agent
- Unusual TXT query volume → investigate tunneling

Runbook for "agent tool cannot reach API":

1. grep audit log for `request_id` from tool error
2. if `NXDOMAIN`, check whether hostname is allowlisted and not expired
3. if allowed but failing, check upstream DNS forwarder health
4. if IP block, verify CDN did not shift to private range (misconfigured origin)

## Testing egress policy

Automated tests run inside the sandbox network namespace:

```bash
# expect NXDOMAIN
dig +short forbidden.example @policy-dns.egress.svc.cluster.local

# expect A record
dig +short api.github.com @policy-dns.egress.svc.cluster.local

# curl through tool runtime
curl -sf --max-redirs 0 https://api.github.com/zen
curl -sf --max-redirs 0 https://169.254.169.254/latest/meta-data/ && exit 1 || true
```

Red-team quarterly: prompt-inject "fetch internal wiki" and verify deny. Chaos: kill policy resolver pods and confirm agents fail closed (errors, not open DNS).

## Split-horizon DNS for hybrid agent deployments

Many agent platforms run sandboxes in Kubernetes but keep human-facing admin APIs on managed SaaS. Split-horizon DNS returns different answers depending on who asks:

- **Sandbox pods** resolve `api.github.com` through the policy forwarder with allowlist enforcement.
- **Corporate laptops** on VPN resolve the same names through standard corporate DNS with unrelated HR policies.

Implement split horizon in CoreDNS or BIND views keyed on source network. Document which namespaces use which resolver—accidentally pointing staging sandboxes at public DNS bypasses the entire control.

For multi-cloud agent runners (AWS Lambda, Cloudflare Workers, GKE), centralize policy in one resolver reachable over private link rather than maintaining three divergent allowlists. Export policy as versioned JSON artifacts consumed by each environment's plugin.

## Coordinating with LLM tool schemas

Tool definitions should not advertise URLs the sandbox cannot reach. Generate tool JSON schemas from the same allowlist source:

```typescript
// tools/schema-from-allowlist.ts
import { rulesForProfile } from "./allowlist";

export function webFetchToolSchema(profile: string) {
  const hosts = rulesForProfile(profile).map((r) => r.suffix);
  return {
    name: "web_fetch",
    description: `Fetch HTTPS content. Allowed domains include: ${hosts.slice(0, 5).join(", ")}...`,
    parameters: {
      type: "object",
      properties: {
        url: { type: "string", format: "uri" },
      },
      required: ["url"],
    },
  };
}
```

When the model proposes a disallowed host, return a structured tool error before DNS is even queried—the LLM can self-correct in the next turn. This reduces noise in deny logs and improves user-visible recovery.

## Governance and change management

Allowlist changes go through PR review with security sign-off. CI validates:

- No duplicate suffix rules
- No `.com` or `.net` top-level suffix entries
- Expired rules fail the build

Provide self-service **staging** allowlist append for developers; promote to prod via merge. Agents should surface human-readable errors when egress denies—helps support without exposing policy internals.

## Closing

DNS egress filtering gives agent platforms a scalable answer to "the model chose this URL"—intervene at resolution time, deny by default, audit every rejection, and pair DNS policy with IP literal blocks and redirect inspection. Firewalls guard ports; DNS guards intent. Teams that treat allowlists as living contracts, not one-time setup, keep agent tools useful without handing SSRF to prompt injection.

## Resources

- [Response Policy Zones (RPZ) overview — ISC](https://www.isc.org/docs/rpz.pdf)
- [CoreDNS external plugin development](https://coredns.io/explugins/)
- [AWS Route 53 Resolver DNS Firewall](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Kubernetes NetworkPolicy documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
