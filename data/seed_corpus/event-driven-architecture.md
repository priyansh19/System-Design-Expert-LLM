# Event-Driven Architecture

## Summary
Event-driven architecture structures systems around producing, detecting, and reacting to events — immutable facts about something that happened — decoupling producers from consumers in time and space, at the cost of strong consistency.

## Core Principles
- Events are immutable facts ("OrderPlaced"), not commands ("PlaceOrder"); once published they represent history.
- Producers and consumers are decoupled via a broker (Kafka, SNS/SQS, RabbitMQ); producers don't know who consumes.
- Eventual consistency is the default: consumers process asynchronously, so downstream state can lag upstream state.
- Event sourcing stores the sequence of state-changing events as the system of record, with current state derived by replaying/folding events, giving a full audit log for free.
- CQRS splits the write model (commands mutate state) from read models (denormalized projections built by consuming the event stream).
- At-least-once delivery is the realistic guarantee in most brokers, so consumers must be idempotent (dedupe by event ID).

## When to Use / When Not
- Use for workflows spanning multiple services (order fulfillment, notifications), audit-critical domains (finance), or high-throughput ingestion.
- Avoid when the domain needs strong read-after-write consistency for a single user-facing request (e.g., balance check right after a debit), or the team lacks maturity for async debugging.

## Tradeoffs
- Loose coupling and scalability vs. harder debugging (causality spread across logs instead of a call stack).
- Auditability/replay-ability vs. storage growth and the need to snapshot to avoid replaying millions of events.
- Read-model flexibility (CQRS) vs. eventual consistency and multi-projection maintenance cost.

## Common Patterns & Techniques
- Outbox pattern: write the event to an outbox table in the same DB transaction as the state change, then relay it, avoiding dual-write inconsistency.
- Schema evolution via a schema registry (Confluent Schema Registry, Avro/Protobuf), adding optional fields rather than renaming/removing.
- Dead-letter queues for events that repeatedly fail processing.
- Saga pattern (choreography or orchestration) for distributed transactions with compensating actions.
- Change Data Capture (Debezium) to turn DB writes into an event stream without app-level dual writes.

## Pitfalls
- Breaking event schema changes without versioning, silently breaking consumers on different deploy schedules.
- Non-idempotent consumers double-processing on redelivery (e.g., double-charging a retried payment event).
- Using event sourcing for simple CRUD domains where it adds unjustified complexity.
- Losing per-entity ordering by partitioning incorrectly (must partition by aggregate ID).

## Real-World Examples
- Uber uses Kafka for trip-state event streams feeding pricing, dispatch, and analytics independently.
- LinkedIn built Kafka to decouple its monolith's activity-stream producers from many downstream consumers.
- Walmart uses event-driven inventory updates across stores and online channels to keep stock projections eventually consistent at scale.
