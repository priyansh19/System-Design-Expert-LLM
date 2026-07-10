# Message Queues

## Summary
Message queues decouple producers from consumers, buffering work so services scale, fail, and deploy independently; the broker choice (Kafka, RabbitMQ, SQS) encodes different delivery, ordering, and durability guarantees.

## Core Principles
- Decoupling in time and space: producers don't need consumers up; consumers pull at their own pace.
- Delivery semantics: at-most-once (fire-and-forget, can lose messages), at-least-once (ack after processing, can duplicate), exactly-once (needs idempotent consumers or transactional writes — true end-to-end exactly-once is rare and costly).
- Kafka is a distributed commit log: topics split into ordered partitions, each consumed by one consumer per group at a time; scaling reads means adding partitions, not just consumers.
- RabbitMQ is a smart broker with routing (direct/topic/fanout exchanges) and push delivery with acks/nacks and priorities — better for complex routing and low-latency dispatch than replay.
- SQS is managed and near-infinitely scalable, using visibility timeouts instead of persistent connections; standard queues are at-least-once/unordered, FIFO queues add strict ordering and dedup at lower throughput.
- Consumer groups load-balance Kafka partitions across instances; rebalances on scale-up/down or crash briefly pause consumption — a common latency-spike source.

## When to Use / When Not
- Use for async workflows, event sourcing, log aggregation, load leveling in front of slow downstreams, and fan-out to subscribers.
- Avoid when the caller needs a synchronous response (use RPC) or strict cross-system transactional consistency without an outbox/saga.

## Tradeoffs
- Kafka: high throughput and replay, but operational complexity (partition rebalancing, storage management, KRaft/ZooKeeper).
- RabbitMQ: flexible routing and lower per-message latency, but weaker horizontal scale and no long-term log retention.
- SQS: zero ops, pay-per-use, but higher per-message latency and limited ordering (FIFO caps near 3,000 msg/s per group without batching).

## Common Patterns & Techniques
- Dead-letter queues (DLQ) capture messages failing after N retries, keeping poison-pill messages from blocking a queue.
- Outbox pattern: write state and event in one DB transaction, then relay to the broker, avoiding dual-write inconsistency.
- Idempotent consumers keyed by message ID make at-least-once delivery safe in practice.
- Partition-key selection (e.g., user ID) preserves per-entity ordering while enabling parallelism.

## Pitfalls
- Assuming exactly-once without idempotent handlers — duplicates will occur.
- Under-provisioning partitions, blocking future consumer scale-out without a repartition.
- Ignoring consumer-lag monitoring until backlog causes cascading staleness.

## Real-World Examples
- LinkedIn built Kafka for activity-stream and log aggregation at massive scale.
- Uber uses Kafka for trip event pipelines and CDC (Debezium) feeding analytics.
- AWS-native teams pair SQS with Lambda for serverless, cost-efficient async processing without broker ops.
