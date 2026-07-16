---
title: "How the Agent-to-Agent (A2A) Protocol Actually Works"
slug: "agent-to-agent-a2a-protocol-explained"
description: "A clear breakdown of the A2A protocol: agent cards, discovery, tasks, and streaming — how independent agents interoperate, and how A2A differs from MCP."
datePublished: "2026-01-11"
dateModified: "2026-01-11"
tags: ["AI Agents", "A2A", "Interoperability", "Protocols"]
keywords: "A2A protocol, Agent2Agent, agent interoperability, agent cards, multi-agent, agent discovery"
faq:
  - q: "What is the A2A protocol?"
    a: "A2A (Agent2Agent) is an open protocol that lets independent AI agents — often built by different teams or vendors — discover each other and collaborate on tasks. Each agent publishes an agent card describing its skills, and clients call it over HTTP using JSON-RPC with support for streaming and long-running tasks."
  - q: "How is A2A different from MCP?"
    a: "MCP connects one agent to tools and data (the agent-to-tools layer). A2A connects agents to other agents (the agent-to-agent layer). They're complementary: an agent might use MCP to call its own tools and A2A to delegate a subtask to another team's agent."
  - q: "What is an agent card in A2A?"
    a: "An agent card is a JSON document, usually served at a well-known URL, that describes an agent's identity, endpoint, authentication, and skills. Clients fetch it to discover what an agent can do and how to talk to it, similar to an OpenAPI spec for agents."
---

A2A (Agent2Agent) answers a question that MCP doesn't: how do two agents built by different teams, in different languages, running on different infrastructure, actually work together? MCP gives one agent access to tools and data. A2A gives one agent the ability to delegate work to *another agent* it didn't build and can't see inside. That's the whole distinction, and holding it clearly makes the rest of the protocol easy to follow.

Think of A2A as the layer that turns isolated agents into a network. Your travel agent doesn't need to know how a hotel-booking agent works internally — it just needs a standard way to find it, understand what it offers, hand it a task, and get results back. A2A defines that standard way, originally introduced by Google and now developed as an open project under the Linux Foundation.

## Agent cards: discovery and capability

Everything starts with the **agent card** — a JSON document that describes an agent to the outside world. By convention it lives at a well-known path so clients can find it:

```
GET https://booking.example.com/.well-known/agent.json
```

A trimmed card looks like this:

```json
{
  "name": "Hotel Booking Agent",
  "description": "Searches and books hotels worldwide.",
  "url": "https://booking.example.com/a2a",
  "version": "1.2.0",
  "capabilities": { "streaming": true, "pushNotifications": true },
  "authentication": { "schemes": ["bearer"] },
  "skills": [
    {
      "id": "search_hotels",
      "name": "Search hotels",
      "description": "Find hotels by city, dates, and budget.",
      "examples": ["Find a hotel in Cairo under $120 for next weekend"]
    }
  ]
}
```

The card is to agents what an OpenAPI spec is to REST APIs. It tells a client the endpoint, the auth scheme, whether the agent supports streaming, and — crucially — the **skills** it offers, each with a natural-language description a calling agent's model can reason over. Discovery, then, is just fetching cards, whether from a known URL, a registry, or a catalog your platform maintains.

## The task lifecycle

A2A is built around **tasks**, not one-shot requests, because agent work is often long-running. A client sends a task, and the remote agent moves it through states: `submitted` → `working` → `input-required` (if it needs clarification) → `completed` or `failed`. This state machine is the heart of the protocol.

Communication uses JSON-RPC 2.0 over HTTP. A client kicks off a task with a message:

```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{ "kind": "text", "text": "Book a hotel in Cairo, Jan 20-22, under $120" }]
    }
  }
}
```

The remote agent responds with a task object carrying an id and status. For anything slow, the client either polls, subscribes to a **streaming** connection (server-sent events) to receive incremental updates, or registers a push notification webhook so the agent can call back when the task finishes. Handling long-running work as a first-class concept is what separates A2A from a plain function call — booking a hotel might involve a human in the loop and take minutes.

## Messages, parts, and artifacts

A2A is multimodal by design. Messages are made of **parts** — text, files, or structured data — so an agent can send a PDF, an image, or a JSON payload alongside prose. When a task produces a result, that result comes back as an **artifact**, again composed of parts. This structure means a returning agent can hand back a confirmation number as structured data *and* a human-readable summary in the same response, and the calling agent picks whichever it needs.

## Security is not an afterthought

Because A2A crosses trust boundaries — you're calling an agent you don't control — security is explicit. The agent card declares supported authentication schemes (bearer tokens, OAuth, API keys), and the transport is expected to be HTTPS. But protocol-level auth only covers "is this caller allowed to talk to me." The harder problem is what the remote agent *does* with the task. Treat any content returned by a remote agent as untrusted input, exactly as you would with [prompt injection and agent security](https://blog.michaelsam94.com/prompt-injection-agent-security/) — a compromised or adversarial remote agent can return text designed to manipulate your calling agent's next actions.

## Where A2A fits with MCP

The cleanest mental model I've found:

| Layer | Protocol | Connects |
| --- | --- | --- |
| Agent → tools/data | [MCP](https://blog.michaelsam94.com/building-an-mcp-server-practical-guide/) | one agent to its tools |
| Agent → agent | A2A | agents to each other |

These aren't competitors. A realistic system uses both: your orchestrator agent uses MCP to call its own database and file tools, and uses A2A to delegate a specialized subtask to a partner team's agent. If you're coordinating agents you *own*, you often don't need A2A at all — the in-process [orchestrator-workers pattern](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/) is simpler. A2A earns its place specifically when agents are owned by different parties and must interoperate across organizational or vendor lines.

## When to actually adopt it

A2A is worth reaching for when you're building an ecosystem: a marketplace of agents, a platform where third parties publish agents, or an enterprise where different teams ship agents that need to call each other without bespoke integrations. For a single team building a single product, it's usually premature — you'd be paying protocol overhead for interoperability you don't need yet.

The value shows up at the boundaries between organizations. That's the same lesson from any integration standard: [OCPP for EV chargers](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) exists so vendors don't hand-integrate with each other, and A2A exists so agent builders don't either. When you feel the pain of N×M custom agent integrations, that's the signal A2A was designed for.

## Resources

- [A2A Project — official documentation](https://a2a-protocol.org/)
- [A2A GitHub organization and spec](https://github.com/a2aproject/A2A)
- [Google — Announcing the Agent2Agent protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [Linux Foundation — Agent2Agent project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification)
