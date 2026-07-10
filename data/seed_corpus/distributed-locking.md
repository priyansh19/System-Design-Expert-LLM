# Distributed Locking

## Summary
Distributed locks coordinate mutually exclusive access to a shared resource across processes on different machines, substituting for the in-process mutex when the critical section spans a network — and are notoriously easy to implement unsafely.

## Core Principles
- A distributed lock must give mutual exclusion, deadlock freedom via TTL/expiry, and fault tolerance in the lock service itself.
- Redlock (Redis) writes a unique token with a TTL to a majority of independent Redis instances; low-latency but criticized (notably by Martin Kleppmann) for unsafe assumptions about clock synchrony and process pauses.
- ZooKeeper/etcd locks use ephemeral session-bound nodes: the lock lives as long as the client's session and dies automatically on crash or partition — safety comes from consensus, not clock-based TTLs.
- A fencing token is a monotonically increasing number returned per acquisition; the resource must reject operations carrying an older token than one already seen, closing the "paused client thinks it still holds the lock" hole.
- A lock alone guarantees nothing unless the protected resource itself enforces fencing/versioning.

## When to Use / When Not
- Use for exclusive access to external resources: a cron job that must run on only one node, a batch pipeline leader.
- Prefer optimistic concurrency (compare-and-swap) over locking when contention is low or the operation is idempotent.
- Avoid distributed locks for correctness-critical financial/inventory operations without fencing tokens — TTL expiry alone isn't safe.

## Tradeoffs
- Redis-based locks: low latency and simple ops vs. weaker safety under network delays, GC pauses, or clock drift.
- Consensus-based locks: stronger correctness guarantees vs. higher latency and an extra coordination-service dependency.
- Short TTLs limit stuck-lock duration after a crash but risk premature expiry under slowness; long TTLs do the opposite.

## Common Patterns & Techniques
- Lease + fencing token pattern: acquire lease, obtain token, pass token to storage on every write.
- Watchdog/auto-renewal threads extending a lock's TTL while the holder stays alive.
- Try-lock with exponential backoff and jitter to avoid thundering-herd retries.
- Single-Redis (not Redlock) locks are often "good enough" as an efficiency optimization, not a correctness guarantee.

## Pitfalls
- Using TTL-based locks as the sole correctness mechanism for non-idempotent operations without fencing.
- Clock skew across Redis nodes silently invalidating Redlock's timing assumptions.
- Not handling a lock holder crashing mid-critical-section, leaving state inconsistent even after expiry.

## Real-World Examples
- Chubby (Google) provides advisory locks with sequencers (fencing tokens) for GFS master election and Bigtable coordination.
- ZooKeeper's recipes library implements distributed locks used by Kafka, Hadoop, and HBase.
- Redlock (via Redisson) is used for lightweight locking where occasional double-execution is tolerable.
