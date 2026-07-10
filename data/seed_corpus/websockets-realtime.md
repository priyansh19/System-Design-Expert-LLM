# WebSockets & Realtime Systems

## Summary
Realtime systems push updates to clients with low latency using persistent bidirectional connections (WebSockets), server-push streams (SSE), or polling fallbacks; the hard problem is not the protocol but fanning out messages and scaling millions of stateful connections.

## Core Principles
- WebSockets provide a full-duplex persistent TCP connection after an HTTP upgrade handshake, suited for bidirectional traffic (chat, collaborative editing, gaming).
- Server-Sent Events (SSE) are unidirectional (server-to-client) over plain HTTP, simpler to operate (standard HTTP infra, browser auto-reconnect) and sufficient when clients only receive updates.
- Long-polling (client holds a request open, server responds when data is ready or on timeout, client reopens) is the fallback where persistent connections are blocked, at the cost of latency.
- Connections are stateful and pinned to a server process, breaking the stateless-request assumption of typical load balancers, requiring sticky routing.
- Fan-out must be decoupled from the origin server via a backplane (Redis Pub/Sub, Kafka, NATS) so any server instance can publish and the instance holding the relevant connection delivers it.
- Presence (who's online, typing indicators) is modeled as ephemeral state with heartbeats/TTLs in a fast store (Redis), not the primary database.

## When to Use / When Not
- WebSockets for low-latency bidirectional interaction (chat, multiplayer, live cursors, trading); SSE for one-way feeds (live scores, notifications) where HTTP-compatibility matters more.
- Avoid persistent connections for infrequent updates (e.g., a daily digest) where polling or push notifications are cheaper.

## Tradeoffs
- Lower latency and duplex traffic vs. operational complexity of stateful connections (load balancing, reconnect storms, per-connection memory).
- SSE's HTTP-native simplicity vs. no client-to-server push on the same channel.

## Common Patterns & Techniques
- Pub/sub backplane (Redis, NATS, Kafka) to decouple producers from the server holding a given connection.
- Sticky sessions or connection routing (consistent hashing on user/room ID) for stateful reconnects.
- Heartbeat/ping-pong frames to detect dead connections and free resources.
- Backpressure and per-connection queues to avoid a slow client blocking the event loop.

## Pitfalls
- Storing realtime state only in server memory with no backplane, so a restart silently drops or misroutes messages.
- Thundering-herd reconnect storms after a deploy overwhelming the backend simultaneously.
- Unbounded per-connection buffers for slow clients causing memory exhaustion.
- Ignoring the C10K/C1M problem: thread-per-connection doesn't scale; event-loop/async I/O is required.

## Real-World Examples
- Slack uses WebSockets with a Gateway layer and pub/sub fan-out across millions of concurrent connections.
- Discord scaled WebSocket gateways using Elixir/Erlang's lightweight process model for millions of presence-aware connections.
- Google Docs and Figma use realtime bidirectional connections with operational transforms/CRDTs for collaborative editing atop the transport layer.
