# Data Partitioning

## Summary
Partitioning (sharding) splits a dataset across multiple nodes so no single machine holds all the data, enabling horizontal scalability of storage and throughput.

## Core Principles
- Range partitioning assigns contiguous key ranges to shards (e.g., A-M on shard 1, N-Z on shard 2), preserving efficient range scans but risking hot spots when access clusters at one end (monotonic keys).
- Hash partitioning applies a hash function to the key to pick a shard, spreading load evenly and avoiding sequential hot spots, but destroying efficient range queries across keys.
- Consistent hashing places both shards and keys on a hash ring; a key belongs to the first shard clockwise from its hash, so a shard change remaps only the adjacent ring portion instead of rehashing everything.
- Virtual nodes assign each physical shard many ring positions, smoothing distribution and making rebalancing proportionally fair across nodes rather than dumping load on one neighbor.
- Rebalancing must move minimum necessary data without downtime; naive mod-N hashing (hash(key) % N) fails this since changing N remaps almost every key.

## When to Use / When Not
- Use range partitioning when range scans are a primary access pattern and you can pre-split or auto-split to avoid hotspots.
- Use hash partitioning when access is point-lookup dominated and even load distribution matters more than range locality.
- Avoid naive hash-mod-N in any growing system; avoid range partitioning on monotonic keys (auto-increment IDs, timestamps) without mitigation.

## Tradeoffs
- Range partitioning: great range-query locality vs hot-spot risk on skewed/sequential key distributions.
- Hash partitioning: even distribution vs loss of range-query efficiency (fan-out to all shards).
- Consistent hashing minimizes data movement on resize vs added routing complexity and ring imbalance without virtual nodes.

## Common Patterns & Techniques
- Salting/bucketing monotonic keys (prefixing with a random or hashed shard-id) to break up hot ranges while retaining locality.
- Auto-splitting ranges past a size threshold (as in HBase, CockroachDB).
- Virtual nodes (100s per physical node) to smooth ring distribution, used in Dynamo, Cassandra.
- Directory-based partitioning (explicit key-to-shard mapping) for flexible rebalancing at the cost of a lookup hop.

## Pitfalls
- Choosing a hash key with low cardinality or correlated with access pattern, causing hot partitions.
- Rebalancing that moves too much data at once, saturating network/disk and spiking latency.
- Ignoring secondary-index patterns that require cross-shard scatter-gather, hurting tail latency.

## Real-World Examples
- Amazon DynamoDB and Apache Cassandra use consistent hashing with virtual nodes to distribute and rebalance data.
- HBase and Bigtable use range partitioning with automatic region/tablet splitting to handle growth and hotspots.
- Vitess (YouTube/Slack's MySQL sharding layer) supports range and hash-based sharding with online resharding.
