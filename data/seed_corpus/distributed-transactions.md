# Distributed Transactions

## Summary
Distributed transactions coordinate atomic updates across independent services; since two-phase commit scales poorly under microservice failure, most production systems favor sagas with compensating actions plus a transactional outbox for reliable event publication.

## Core Principles
- Two-Phase Commit (2PC): a coordinator asks participants to "prepare" (vote), then commits only if all vote yes; it guarantees atomicity but blocks all participants if the coordinator crashes mid-protocol.
- Sagas break a distributed transaction into a sequence of local transactions, each with a compensating action to undo it if a later step fails — no distributed locking.
- Orchestration sagas use a central coordinator that invokes each step and triggers compensations on failure — one place for workflow logic.
- Choreography sagas have each service publish events triggering the next service's local transaction — decentralized, but harder to trace as steps multiply.
- The outbox pattern writes the state change and the "event to publish" in one local DB transaction; a relay (CDC or polling) publishes it, avoiding the dual-write problem.

## When to Use / When Not
- Use sagas when a business process spans multiple services/databases and eventual consistency is acceptable (order placement, booking flows).
- Use 2PC only within a tightly coupled, low-latency, small-participant system (a DB's internal shard commit) — not across microservice boundaries.
- Use the outbox pattern whenever a service must both persist state and reliably emit an event.
- Avoid distributed transactions when a single-service transaction can own the whole operation.

## Tradeoffs
- 2PC gives strong atomicity but sacrifices availability (blocking on coordinator failure) and throughput (held locks).
- Sagas gain availability and scalability but expose intermediate inconsistent states and require idempotent, compensable steps.
- Orchestration centralizes complexity into one point; choreography avoids that but complicates observability.

## Common Patterns & Techniques
- Compensating transactions (semantic rollback, e.g., refund instead of undoing a payment).
- CDC (Debezium) tailing the outbox table to Kafka for reliable async publication.
- Idempotency keys on each step to safely handle retries.
- Saga state persisted so orchestration can resume after a crash.

## Pitfalls
- Non-idempotent compensations causing double-refunds or lost updates on retry.
- Saga steps visible to other transactions before completion, needing semantic locking or "pending" states.
- Running 2PC across a WAN, where partitions cause indefinite blocking.
- Dual-writing to DB and message broker directly instead of an outbox, risking data loss.

## Real-World Examples
- Uber's trip lifecycle uses saga orchestration (Temporal/Cadence) across payment, matching, and notification services.
- Debezium plus Kafka is a standard open-source outbox/CDC combination used at companies like Shopify.
- Google Spanner uses 2PC internally across shards, made viable by TrueTime bounding clock uncertainty.
