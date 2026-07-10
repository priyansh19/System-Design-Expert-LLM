# Consistency Models

## Summary
Consistency models define the contract a distributed system makes about what values reads can return relative to concurrent and prior writes; the right model balances correctness, latency, and availability.

## Core Principles
- Strong consistency (linearizability): every read reflects the most recent completed write, with operations appearing to take effect atomically between invocation and response — behaves like a single copy of data.
- Eventual consistency: replicas converge to the same value given no new writes, but offer no bound on when, and reads may return stale or out-of-order values in the interim.
- Causal consistency: operations that are causally related (a write depending on a prior read) are seen by all nodes in that order; unrelated operations may appear in different orders on different nodes.
- Session guarantees — read-your-writes and monotonic reads (never see an earlier state after a later one) — are practical, client-scoped middle grounds cheaper than global strong consistency.
- Linearizability vs serializability: linearizability is a real-time recency guarantee on individual operations; serializability is a transaction-isolation guarantee about an equivalent serial order, with no real-time requirement. Strict serializability combines both.

## When to Use / When Not
- Use strong consistency for locks, leader election, payments, inventory decrements — anywhere stale reads cause real-world inconsistency.
- Use eventual or causal consistency for feeds, comments, presence, recommendation caches, or systems where availability matters more than immediate freshness.
- Avoid strong consistency across wide-area replicas for latency-insensitive reads; the round-trip cost is rarely justified.

## Tradeoffs
- Stronger models require coordination (quorums, consensus), raising latency and reducing availability under partition.
- Weaker models improve latency/availability but push complexity onto the application (conflict resolution, stale-read handling).
- Causal consistency needs metadata (vector clocks) that adds overhead versus plain eventual consistency.

## Common Patterns & Techniques
- Quorum reads/writes to approximate strong consistency in an otherwise AP store.
- Vector clocks / version vectors to track causal dependencies.
- Session tokens or "read-your-writes" sticky routing to the same replica or a version-bounded read.
- CRDTs for automatic, mathematically-guaranteed convergence in eventually consistent systems without conflict resolution logic.

## Pitfalls
- Assuming "eventual" means "soon" — convergence windows can be seconds to minutes under load or partition.
- Mixing consistency levels inconsistently across an API surface, confusing clients about what guarantee they're getting.
- Conflating serializability (transaction ordering) with linearizability (recency), causing false assumptions about real-time freshness.

## Real-World Examples
- Google Spanner offers external (strict) consistency globally using TrueTime and synchronized clocks.
- Amazon DynamoDB defaults to eventual consistency for reads but offers optional strongly consistent reads at higher latency/cost.
- Facebook/Meta's TAO provides read-your-writes within a region while being eventually consistent across regions.
