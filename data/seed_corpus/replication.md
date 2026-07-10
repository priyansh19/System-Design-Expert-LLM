# Replication

## Summary
Replication maintains copies of the same data on multiple nodes to improve availability, durability, and read scalability, at the cost of coordination and divergence management.

## Core Principles
- Leader-follower (single-leader): all writes go to one leader, which propagates changes to followers; simple, avoids write conflicts, but the leader is a single point of write failure.
- Multi-leader: multiple nodes accept writes independently (often one per datacenter) and replicate to each other, improving write availability and geo-latency at the cost of conflict resolution.
- Leaderless (quorum-based): any replica can accept reads/writes; correctness relies on overlapping quorums, using W + R > N to guarantee at least one up-to-date replica is read.
- Synchronous replication waits for follower ack before confirming a write: durable, but higher write latency and reduced availability if a follower is slow.
- Asynchronous replication confirms the write once the leader persists it, propagating to followers in the background — low latency but risks losing acknowledged writes on leader crash (replication lag).

## When to Use / When Not
- Use single-leader for most OLTP workloads needing simple consistency and no multi-region write conflicts.
- Use multi-leader for multi-region active-active systems where latency to a single leader is unacceptable and conflicts are rare or mergeable.
- Use leaderless/quorum for high-availability, high-throughput systems tolerating tunable/eventual consistency (Dynamo-style stores).
- Avoid sync replication across distant regions for latency-sensitive writes; avoid multi-leader when strict conflict-free correctness is required.

## Tradeoffs
- Sync replication: stronger durability/consistency vs higher write latency and lower availability when followers lag.
- Async replication: lower latency and higher availability vs data loss risk and stale reads on followers (replication lag).
- Multi-leader/leaderless: better write availability and geo-distribution vs app-level complexity from conflict resolution.

## Common Patterns & Techniques
- Semi-synchronous replication: leader waits for one follower ack, balancing durability and latency.
- Quorum reads/writes and read-repair/hinted handoff converge leaderless replicas.
- Conflict resolution: last-write-wins (simple but lossy), vector clocks (detect concurrent writes), CRDTs (automatic merge), or app-level merge logic.
- Read replicas for scaling read throughput, with lag monitoring to avoid serving badly stale data.

## Pitfalls
- Reading from a lagging async follower right after a write and seeing stale data, violating read-your-writes without a routing fix.
- Underestimating multi-leader conflict rates, causing silent data loss with naive last-write-wins.
- Not monitoring replication lag, so failover promotes a follower missing recent writes.

## Real-World Examples
- MySQL and PostgreSQL commonly run single-leader with async (or semi-sync) replication for read replicas.
- DynamoDB and Cassandra use leaderless replication with tunable quorums (N, R, W) and hinted handoff.
- CouchDB and multi-region Cosmos DB use multi-leader replication with conflict resolution for active-active geo-distribution.
