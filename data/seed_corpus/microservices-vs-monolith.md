# Microservices vs Monolith

## Summary
Monoliths and microservices are ends of a spectrum for organizing deployable units around business capability; the choice trades operational simplicity against independent scalability and team autonomy, and most systems should start as a modular monolith before splitting.

## Core Principles
- Service boundaries should follow domain boundaries (bounded contexts, per Domain-Driven Design), not technical layers.
- A modular monolith enforces boundaries via module structure and internal APIs while deploying as one unit, giving much of microservices' clarity without network overhead.
- Microservices trade in-process calls for network calls, introducing partial failure and the need for retries, timeouts, and circuit breakers.
- Data ownership must be exclusive per service; a shared database across services recreates coupling and defeats the split.
- Conway's Law: architecture mirrors team communication structure, so boundaries should often match team boundaries.
- Independent deployability is the real test of a microservice — if two services must deploy together, they are one service.

## When to Use / When Not
- Split when teams are blocked on each other's deploy cadence, a subsystem has distinct scaling needs, or independent compliance boundaries are required.
- Stay monolithic for small teams (<20-30 engineers), unstable early-stage domain models, or when the org lacks CI/CD and on-call maturity for distributed systems.
- Never split for resume-driven architecture; the domain rarely justifies it early.

## Tradeoffs
- Development velocity (monolith) vs. deployment independence (microservices, with integration and versioning overhead).
- Simple ACID transactions vs. finer-grained scaling and fault isolation.
- Lower latency (in-process) vs. per-service tech-stack flexibility.

## Common Patterns & Techniques
- Strangler Fig pattern: incrementally carve services out behind a facade/proxy.
- Modular monolith as a stepping stone before extraction.
- API Gateway / Backend-for-Frontend to aggregate cross-service calls.
- Saga pattern for cross-service transactions instead of distributed 2PC.
- Service mesh (Istio, Linkerd) for mTLS, retries, and observability once service count grows.

## Pitfalls
- "Distributed monolith": services deployed separately but sharing a database or deploying in lockstep — worst of both worlds.
- Chatty inter-service calls causing N+1 network round trips.
- Splitting along technical layers instead of business capability.
- Underestimating the cost of distributed tracing and contract versioning.

## Real-World Examples
- Amazon moved from a monolith to service-oriented architecture in the early 2000s, mandating well-defined service APIs (the "Bezos API Mandate").
- Shopify kept a modular "majestic monolith" for years, extracting services (e.g., checkout) only where scaling demanded it.
- Segment migrated from microservices back to a monolith in 2018 after operational overhead outweighed benefits at their team size.
