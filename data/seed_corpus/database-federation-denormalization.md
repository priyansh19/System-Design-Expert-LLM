# Database Federation & Denormalization

## Summary
Federation splits a monolithic database by function across separate instances; denormalization intentionally duplicates data to speed reads — both trade join simplicity and single-source-of-truth for scalability and query speed.

## Core Principles
- Functional partitioning (federation): each database owns a bounded-context slice (Users DB, Orders DB), scaling independently but eliminating cross-domain SQL joins.
- Denormalization duplicates data (e.g., a display name copied onto every comment row) to avoid joins at read time, trading storage and write-side sync effort for read speed.
- Materialized views precompute and persist a query result, refreshed periodically or incrementally, giving fast reads without denormalizing the source schema.
- Read models (CQRS-style) are purpose-built, denormalized projections optimized for a query pattern, decoupled from the normalized transactional schema.
- Federation shifts referential integrity to the application layer, since cross-database foreign keys can't be enforced.

## When to Use / When Not
- Use federation when a single database becomes a scaling or team-ownership bottleneck and data naturally partitions along service boundaries.
- Use denormalization/materialized views when read latency or join cost dominates and source data changes far less than it's read.
- Avoid federation for tightly coupled data needing cross-entity ACID (e.g., ledger updates spanning accounts and transactions).
- Avoid heavy denormalization for rapidly changing data where sync cost exceeds the joins it avoids.

## Tradeoffs
- Federation: independent scaling vs loss of cross-database joins/transactions, requiring app-level aggregation.
- Denormalization: faster reads, fewer joins vs update anomalies, higher storage, and staleness if propagation lags.
- Materialized views: query speed without schema distortion vs refresh lag and cost at scale.

## Common Patterns & Techniques
- CDC pipelines (Debezium, Kafka) propagate changes from the system of record into denormalized stores or views asynchronously.
- CQRS: separate write model (normalized, consistent) from read model (denormalized, eventually consistent), scaled independently.
- API composition/aggregation layer (BFF, GraphQL gateway) stitches results across federated services instead of a database join.
- Incremental materialized view refresh (`REFRESH MATERIALIZED VIEW CONCURRENTLY`, streaming views in Materialize/ksqlDB) cuts staleness without full recompute.

## Pitfalls
- Forgetting to update all denormalized copies on write, leaving stale duplicates.
- Federating along the wrong boundary, forcing frequent cross-database queries that negate the scaling benefit.
- Treating a stale materialized view as real-time in a context needing freshness.
- Underestimating the operational cost of many small federated databases versus one well-tuned large one.

## Real-World Examples
- Amazon federated its monolithic database into per-service stores (orders, catalog, customers) to scale teams and traffic independently.
- Facebook/Meta's TAO and News Feed pipelines denormalize heavily for read-heavy social graph queries at scale.
- E-commerce platforms build materialized "product search" views combining inventory, pricing, and catalog data.
