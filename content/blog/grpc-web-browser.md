---
title: "gRPC-Web in the Browser"
slug: "grpc-web-browser"
description: "How gRPC-Web actually works in the browser: the protocol gap, proxies vs Connect, protobuf codegen, streaming limits, and when it beats plain REST."
datePublished: "2026-06-05"
dateModified: "2026-06-05"
tags: ["Web", "gRPC", "API Design", "Backend"]
keywords: "gRPC-Web, Connect, protobuf browser, gRPC frontend, streaming gRPC web, envoy proxy"
faq:
  - q: "What is gRPC-Web?"
    a: "gRPC-Web is a variant of the gRPC protocol designed to run from a browser, where raw HTTP/2 frame control isn't available to JavaScript. It keeps protobuf messages and the same service definitions as gRPC, but wraps them in a wire format a browser's fetch or XHR can produce and consume, usually with a proxy or a Connect-compatible server translating between gRPC-Web and native gRPC."
  - q: "Why can't a browser speak plain gRPC?"
    a: "Native gRPC depends on low-level HTTP/2 features — trailers, full-duplex framing, and precise control over the request body — that browser JavaScript APIs don't expose. The Fetch and XHR APIs can't send HTTP/2 trailers or manage bidirectional streams the way gRPC needs, so a browser-safe framing (gRPC-Web) plus a translation layer is required."
  - q: "Do I still need Envoy for gRPC-Web?"
    a: "Not always. The classic setup uses an Envoy proxy with the grpc_web filter to translate gRPC-Web into native gRPC for your backend. But modern stacks like Connect let servers speak gRPC, gRPC-Web, and Connect's own protocol natively on one port, which removes the separate proxy for many teams."
---

If you've tried to call a gRPC service straight from a React app and hit a wall, this is why: browsers can't speak native gRPC, and gRPC-Web is the bridge. It keeps your protobuf contracts and generated clients but swaps the wire format for something a browser's `fetch` can actually produce, with a proxy or a Connect-compatible server translating on the way to your real gRPC backend. The payoff is a typed, schema-first API from database to DOM without hand-writing fetch calls and TypeScript interfaces that drift out of sync.

I've shipped this on a couple of internal dashboards where the backend was already gRPC, and the honest summary is: it's great once it's wired up, and the wiring is where people lose a day. Let me save you that day.

## The protocol gap nobody explains up front

Native gRPC leans on HTTP/2 in ways browser JavaScript simply can't reach. It uses HTTP/2 **trailers** to send the final status code and message after the response body, it needs full control over request framing for streaming, and it assumes a client that can manage bidirectional streams. The Fetch API and XHR give you none of that — you can't set trailers, and you can't do true bidirectional streaming over a single request.

So gRPC-Web defines a browser-friendly framing. Messages are still protobuf-encoded, but length-prefixed and packed into a body the browser can send, with the trailing status folded into the response body as a special frame instead of an HTTP/2 trailer. That last detail is the whole reason a translation layer exists: something has to convert between "status in a trailer" (native gRPC) and "status in a trailing body frame" (gRPC-Web).

## Two ways to bridge: Envoy vs Connect

The original answer was a proxy. You put [Envoy](https://www.envoyproxy.io/) in front of your gRPC services with the `grpc_web` filter, and it translates gRPC-Web requests from the browser into native gRPC for your backend. It works, it's battle-tested, and it's one more component to run, configure, and debug.

The newer answer is [Connect](https://connectrpc.com/), from the Buf team. A Connect server speaks three protocols on the same port — native gRPC, gRPC-Web, and Connect's own HTTP-friendly protocol — so a browser can call it directly with no separate proxy. Here's how the choice tends to shake out:

| Concern | Envoy + gRPC-Web | Connect |
| --- | --- | --- |
| Extra infra | Yes, a proxy tier | No, one server |
| Backend changes | None | Adopt Connect handlers |
| Debuggability | Binary frames, harder | Human-readable JSON option |
| Streaming | Server-streaming | Server-streaming |
| Ecosystem lock-in | Standard gRPC | Buf/Connect stack |

My default for a greenfield browser-facing API is Connect, because "curl-able, JSON-capable, no proxy" removes an entire class of operational pain. If you already run Envoy as your edge and have a fleet of existing gRPC services, the `grpc_web` filter is the lower-friction path.

## Codegen: the part that makes it worth it

The reason to bother with any of this is the generated client. You define the service once in protobuf and generate a typed TypeScript client, so the frontend calls a method instead of assembling a URL and parsing JSON by hand.

```protobuf
syntax = "proto3";
package orders.v1;

message GetOrderRequest { string id = 1; }
message Order {
  string id = 1;
  string customer_email = 2;
  int64 total_cents = 3;
}

service OrderService {
  rpc GetOrder(GetOrderRequest) returns (Order);
}
```

With Buf and the Connect plugin, generation is a short config and a single command:

```yaml
# buf.gen.yaml
version: v2
plugins:
  - remote: buf.build/bufbuild/es
    out: src/gen
  - remote: buf.build/connectrpc/es
    out: src/gen
```

```typescript
import { createConnectTransport } from "@connectrpc/connect-web";
import { createClient } from "@connectrpc/connect";
import { OrderService } from "./gen/orders/v1/orders_connect";

const transport = createConnectTransport({ baseUrl: "https://api.example.com" });
const client = createClient(OrderService, transport);

const order = await client.getOrder({ id: "ord_123" });
console.log(order.customerEmail); // fully typed, no manual parsing
```

The win is that when the backend changes a field, `tsc` breaks the build instead of production. That single property is why I'll pick a schema-first API over hand-rolled REST for any surface with more than a handful of endpoints. It's the same tradeoff I dug into comparing [REST vs gRPC vs GraphQL](https://blog.michaelsam94.com/rest-vs-grpc-vs-graphql-2026/): you pay upfront tooling cost to buy long-term contract safety.

## Streaming: know the limit before you design around it

Here's the sharp edge. gRPC has four call types — unary, server-streaming, client-streaming, and bidirectional. Over gRPC-Web in the browser, you reliably get **unary and server-streaming**. Client-streaming and bidirectional streaming are not supported by the gRPC-Web spec, because the browser can't stream a request body the way native gRPC needs.

Server-streaming is genuinely useful — think a live list of order updates pushed from server to client over one long-lived response. But if your design needs the browser to *push* a continuous stream to the server, or true bidirectional chat-style flow, gRPC-Web won't do it. That's where I reach for WebSockets instead; I've written about the tradeoffs in [WebSocket architecture at scale](https://blog.michaelsam94.com/websocket-architecture-at-scale/). A common, clean pattern is gRPC-Web for request/response and server-push, WebSockets for the genuinely bidirectional parts.

## Operational gotchas from real deployments

A few things that cost me time so they don't cost you:

- **CORS is not optional.** Browser-originated gRPC-Web is subject to CORS preflight. You must allow the `Content-Type` (`application/grpc-web+proto` or `application/connect+proto`) and expose the `grpc-status` and `grpc-message` headers, or the client sees opaque failures.
- **Binary framing hides errors.** With classic gRPC-Web the payloads are binary, so browser devtools show you nothing useful. Connect's JSON mode is worth enabling in staging purely so you can read requests.
- **Deadlines and retries.** gRPC's deadline propagation is a real advantage — set client-side timeouts and let the server honor them. Don't fall back to un-bounded fetches.
- **Bundle size.** The generated code plus runtime adds weight. It's modest, but measure it if you ship to low-end mobile browsers; tree-shaking the generated modules matters.

## When gRPC-Web is the right call — and when it isn't

Reach for gRPC-Web when your backend is already gRPC, you value end-to-end type safety, and your browser needs are request/response plus server-push. It shines for internal tooling, admin dashboards, and data-dense apps where the contract changes often and silent drift is expensive.

Skip it when your API is public and you want maximum client compatibility (plain REST or GraphQL is friendlier to third parties), when you need true bidirectional streaming from the browser, or when the team has no appetite for a protobuf toolchain. The tooling tax is real; I've seen small teams bounce off Buf config and codegen and be happier with a typed REST layer.

For the projects where it fits, though, gRPC-Web quietly deletes an entire category of frontend/backend integration bugs. Define once, generate everywhere, and let the compiler enforce the contract — that's a trade I'll take on any long-lived internal product.

## Resources

- [gRPC-Web on the gRPC site](https://grpc.io/docs/platforms/web/)
- [grpc-web repository (protocol and clients)](https://github.com/grpc/grpc-web)
- [Connect RPC documentation](https://connectrpc.com/docs/)
- [Envoy gRPC-Web filter reference](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/grpc_web_filter)
- [Protocol Buffers language guide](https://protobuf.dev/programming-guides/proto3/)
- [Buf documentation](https://buf.build/docs/)
