# API Design

## Summary
API design is the contract layer between services and consumers; the choice of protocol (REST, gRPC, GraphQL), versioning strategy, and error semantics determines how safely the system can evolve without breaking clients.

## Core Principles
- REST models resources with HTTP verbs and status codes; cacheable and human-debuggable but requires discipline to stay consistent.
- gRPC uses HTTP/2 and Protobuf for compact binary payloads, bidirectional streaming, and strongly-typed contracts — ideal for internal service-to-service calls.
- GraphQL exposes one endpoint with a query language letting clients request exactly the fields needed, reducing over/under-fetching, at the cost of harder caching.
- Idempotency matters per verb: GET, PUT, DELETE should be idempotent; POST is not, so mutating endpoints need explicit idempotency keys for safe retries.
- Consistent error contracts (RFC 7807 Problem Details or a fixed `{code, message, details}` envelope) let clients handle failures programmatically.
- Pagination must be explicit: offset-based is simple but breaks under concurrent writes; cursor-based (keyset) is stable and scales better.

## When to Use / When Not
- REST for public APIs and simple CRUD resources needing cacheability and tooling ubiquity.
- gRPC for internal high-throughput microservice communication, especially with streaming needs.
- GraphQL for client-driven apps aggregating many backend resources, not for simple single-resource APIs.

## Tradeoffs
- REST's simplicity vs. gRPC's performance/typing vs. GraphQL's flexibility vs. its harder caching and rate-limiting.
- Fine-grained client control (GraphQL) vs. unpredictable server-side query cost (N+1 resolvers, deep nesting).
- Strict versioning (breaking changes require a new version) vs. evolvability (additive-only changes).

## Common Patterns & Techniques
- Versioning via URL path, header, or content negotiation; additive-only changes avoid bumping major versions.
- Idempotency keys (client-generated UUID header) so retried POSTs are deduplicated server-side.
- DataLoader pattern in GraphQL to batch/cache resolver calls, avoiding N+1 queries.
- API Gateway for auth, rate limiting, and request/response transformation at the edge.

## Pitfalls
- Leaking internal implementation details (DB columns, internal IDs) into the contract, making refactors breaking changes.
- Returning 200 OK with an error payload instead of correct HTTP status codes, breaking client handling and monitoring.
- Unbounded GraphQL queries without depth/complexity limits, enabling resource exhaustion.
- Offset pagination on large, frequently-updated tables causing skipped or duplicate results.

## Real-World Examples
- Stripe's REST API is a widely cited standard for dated versioning, idempotency keys, and error object design.
- Google uses gRPC pervasively internally and defined the Protobuf/gRPC ecosystem standard for polyglot microservices.
- GitHub migrated much of its public API to GraphQL (v4) so integrators fetch nested repo/issue/PR data in one round trip.
