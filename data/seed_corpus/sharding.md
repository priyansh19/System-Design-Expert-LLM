# Sharding

## Summary
Sharding partitions a dataset horizontally across multiple database instances so no single node holds all the data or absorbs all the write load, trading single-node simplicity (joins, transactions) for near-linear write scalability.

## Core Principles
- A shard key determines which shard owns a row; choosing it well is the most consequential decision — it must distribute load evenly and align with the dominant query pattern.
- Application-level sharding routes queries to the correct shard in application code (or a proxy like Vitess/Citus), unlike built-in DB auto-sharding.
- Range-based sharding enables efficient range scans but risks hotspots when writes cluster at one end.
- Hash-based sharding distributes keys evenly, avoiding hotspots, but makes range queries expensive (must fan out to all shards).
- Cross-shard queries (joins, aggregations) are expensive or impossible atomically; systems denormalize, scatter-gather with app-side merging, or keep a separate index.
- Resharding is the hardest operational problem — consistent hashing minimizes data movement versus naive modulo schemes when shard count changes.

## When to Use / When Not
- Shard when a single instance can no longer handle write throughput or dataset size (beyond vertical scaling limits) and the workload is well partitioned by a natural key (tenant ID, user ID).
- Avoid sharding prematurely: try read replicas, caching, and vertical scaling first — sharding adds irreversible complexity that is costly to unwind.

## Tradeoffs
- Write scalability and fault isolation vs. loss of cross-shard ACID transactions and joins.
- Even load distribution (hash-based) vs. efficient range queries (range-based) — rarely optimal for both.

## Common Patterns & Techniques
- Consistent hashing (with virtual nodes) to minimize reshuffling when adding/removing shards.
- Directory-based sharding: a lookup service maps keys to shards, allowing rebalancing without changing the hash function.
- Composite/salted keys to break up hot ranges (prefixing a monotonic ID with a random or hashed suffix).
- Read replicas per shard for read scaling independent of writes.

## Pitfalls
- Celebrity/hotspot problem: a shard key like "account ID" fails when one account generates disproportionate traffic, overwhelming its shard — mitigated by sub-sharding hot keys or dedicated capacity.
- Choosing a shard key that doesn't match query patterns, forcing expensive cross-shard fan-out for common queries.
- Underestimating resharding complexity — live migration needs dual-writes or CDC-based cutover.
- Sequential/monotonic keys causing writes to land on the last shard.

## Real-World Examples
- Instagram shards Postgres by user ID using custom IDs embedding shard ID, logical shard, and timestamp.
- Discord sharded Cassandra/ScyllaDB by channel ID, hitting hotspots on mega-popular channels requiring special handling.
- Vitess (built at YouTube) shards MySQL transparently to the application and now powers Slack and other large-scale MySQL deployments.
