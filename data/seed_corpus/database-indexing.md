# Database Indexing

## Summary
An index is an auxiliary data structure that trades storage and write cost for faster lookups, avoiding full table scans; the choice of index structure (B-tree, hash, LSM-based) fundamentally shapes a database's read/write performance profile.

## Core Principles
- B-tree indexes keep sorted keys in a balanced tree, giving O(log n) point lookups and efficient range scans — the default in Postgres and MySQL/InnoDB.
- Hash indexes give O(1) average point lookups but no range scan support; used for pure exact-match workloads.
- Composite (multi-column) indexes are ordered by column sequence — a query must use a left-prefix of the index columns to benefit.
- Covering indexes include every column a query needs, letting the engine answer from the index alone (index-only scan) without touching the heap.
- LSM-trees buffer writes in memory (memtable), flush sorted immutable segments (SSTables), and merge them via background compaction — optimizing write throughput over read latency.
- Write amplification is the ratio of physical to logical bytes written; B-trees suffer page-write amplification on random inserts, LSMs suffer compaction-driven amplification.

## When to Use / When Not
- Use B-tree indexes for general-purpose OLTP with mixed range and point queries.
- Use hash indexes only for pure equality lookups where range queries are never needed.
- Use LSM-based engines (RocksDB, Cassandra, HBase) for write-heavy workloads (logging, time-series) where read latency tolerance is higher.
- Avoid over-indexing: every index slows inserts/updates/deletes since each must be maintained transactionally.

## Tradeoffs
- Read speed vs write cost: more indexes speed reads but multiply write-path work and storage.
- LSM write throughput vs read amplification: reads may check memtable plus multiple SSTable levels, mitigated by per-SSTable Bloom filters.
- B-tree writes cause page splits and fragmentation, requiring periodic reindexing/vacuum.

## Common Patterns & Techniques
- Index-only scans / covering indexes to eliminate heap fetches.
- Partial indexes (indexing only rows matching a predicate) to shrink index size for selective queries.
- Leveled compaction (RocksDB) vs size-tiered compaction (Cassandra default) tune the LSM write/read/space amplification triangle.
- Composite index ordering by equality-then-range-then-sort columns matching the query pattern.

## Pitfalls
- Indexing a low-cardinality column (e.g., boolean) yields little benefit and wastes write cost.
- Composite index column order mismatched with WHERE clauses silently disables index usage.
- Neglecting LSM compaction tuning, letting read latency degrade under write pressure.
- ORMs auto-generating redundant or missing indexes.

## Real-World Examples
- Postgres uses B-tree by default; GIN/GiST indexes support full-text and geospatial queries.
- Cassandra and HBase use LSM-trees to sustain very high write throughput for time-series and logging workloads.
- RocksDB (inside MySQL's MyRocks, CockroachDB, Kafka Streams) exemplifies tuned LSM compaction in production.
