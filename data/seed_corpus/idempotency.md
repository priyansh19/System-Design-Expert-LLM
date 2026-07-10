# Idempotency

## Summary
An idempotent operation produces the same effect no matter how many times it is applied, which is what makes retries — the primary tool for handling network failures — safe in distributed systems.

## Core Principles
- Retries are unavoidable (a timeout doesn't reveal whether the server executed the request), so any retriable mutating endpoint must be idempotent.
- Idempotency keys: the client generates a unique key (UUID) per operation and resends it with every retry; the server persists the key with its result and returns the cached result on replay.
- Natural idempotency: some ops are inherently idempotent (`SET x = 5`, `DELETE id=1`), unlike others (`increment balance by 10`) which need explicit dedup.
- Deduplication needs a durable store (DB unique constraint, Redis `SETNX` with TTL) keyed by the idempotency key, checked atomically before side effects run.
- Exactly-once *effects* (not delivery) is the real goal: delivery can be at-least-once as long as the effect applies once, via idempotent writes or dedup.
- The key must scope to one logical operation with a bounded lifetime — reusing it for a different operation is a correctness bug.

## When to Use / When Not
- Use for payment/order APIs, webhook handlers, queue consumers, and client-retried POSTs.
- Less critical for pure reads or ops where duplicate execution is provably harmless (e.g., re-setting a cache value).

## Tradeoffs
- Storing keys adds a lookup per request; too-short TTL risks duplicate execution, too-long wastes storage.
- Strong dedup (DB unique constraint) is safest but adds contention; best-effort caching (Redis) is faster but can lose the key on eviction/crash.

## Common Patterns & Techniques
- Idempotency-Key HTTP header (popularized by Stripe) with server-side request/response caching per key.
- Unique constraint on (idempotency_key, resource) as the atomic dedup gate, written in the same transaction as the write.
- Outbox/inbox pattern: an "inbox" table records processed message IDs so a consumer skips handled messages.
- Conditional writes (`INSERT ... ON CONFLICT DO NOTHING`, DynamoDB conditional expressions) make writes naturally idempotent.

## Pitfalls
- Checking the key and inserting the record as two non-atomic steps, reintroducing a race under concurrent retries.
- Returning a different response body on retry than the original call, breaking client trust in the cached result.
- Forgetting idempotency must cover side effects too — don't resend an email on retry even if the write is deduped.

## Real-World Examples
- Stripe's Idempotency-Key header guarantees a charge is created at most once under client retries.
- DynamoDB conditional writes and SQS FIFO dedup IDs make AWS consumers idempotent.
- Kafka consumers commonly use an "inbox" table keyed by (topic, partition, offset) to avoid double-processing on rebalance redelivery.
