# SQL vs NoSQL

## Summary
SQL (relational) databases enforce a fixed schema with strong consistency and multi-row ACID transactions; NoSQL databases (document, key-value, wide-column, graph) trade schema rigidity and cross-entity transactions for horizontal scalability and flexible data models at higher throughput.

## Core Principles
- Relational systems normalize data into tables with foreign keys; joins are computed at query time by the planner.
- NoSQL systems denormalize: the access pattern is baked into the data model at write time (document embedding, wide-column pre-aggregation).
- ACID multi-row transactions are native to SQL; most NoSQL stores offer only single-key atomicity.
- CAP tradeoffs are explicit in NoSQL: DynamoDB/Cassandra favor availability/partition tolerance (AP) with tunable consistency; traditional RDBMS favor consistency (CP).
- Schema flexibility in document stores (MongoDB) speeds iteration but pushes validation into application code.

## When to Use / When Not
- Use SQL for highly relational data needing ad-hoc joins/aggregations and strong consistency (ledgers, inventory, orders).
- Use NoSQL when the access pattern is known upfront and must scale horizontally at low latency (sessions, profiles, catalogs, time-series).
- Avoid NoSQL when you need flexible ad-hoc queries, multi-entity transactions, or referential integrity.
- Avoid SQL when write throughput must scale linearly across commodity nodes beyond what sharding/replicas support.

## Tradeoffs
- Consistency vs availability: RDBMS transactions serialize under contention; AP NoSQL systems stay available during partitions but may return stale reads.
- Flexibility vs integrity: schemaless documents move validation to application code.
- Query power vs scale: SQL joins are expensive to distribute; NoSQL denormalization avoids joins but multiplies storage and update complexity.

## Common Patterns & Techniques
- Polyglot persistence: Postgres for transactional core, Redis for caching, Elasticsearch for search, DynamoDB for high-throughput key-value access.
- NewSQL (Spanner, CockroachDB, YugabyteDB) combines SQL semantics with horizontal scale via distributed consensus (Paxos/Raft).
- Single-table design in DynamoDB models multiple entity types in one table keyed by access pattern.

## Pitfalls
- Choosing NoSQL prematurely, then discovering missing transactions/joins mid-project.
- Using MongoDB with heavy $lookup joins, negating its performance advantages.
- Ignoring eventual-consistency windows in AP stores, causing read-your-write bugs.

## Real-World Examples
- Uber migrated core trip data off Postgres to a custom schemaless layer for scale, then partially back for correctness.
- Amazon uses DynamoDB for cart/session data alongside Aurora for order/financial transactions.
- Discord uses Cassandra/ScyllaDB for message storage where the access pattern (fetch by channel+time) is fixed.
