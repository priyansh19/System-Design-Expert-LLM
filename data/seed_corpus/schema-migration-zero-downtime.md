# Zero-Downtime Schema Migration

## Summary
Zero-downtime schema migration changes a production database's structure without an outage or breaking in-flight requests, by decoupling schema changes from deploys so old and new code are never simultaneously invalid.

## Core Principles
- Expand-contract: additively expand the schema (new column/table beside the old), migrate reads/writes to the new shape, then contract by dropping the old structure — never one atomic replace.
- Backward/forward compatibility: at every intermediate deploy, both old and new code must work against the current schema, since rolling deploys run mixed versions concurrently.
- Online DDL adds columns/indexes without full table locks by rewriting data in the background, taking only a brief metadata lock (MySQL 8 instant ADD COLUMN, PostgreSQL CREATE INDEX CONCURRENTLY).
- Backfills must be batched and rate-limited to avoid replication lag, lock contention, or I/O saturation on a live table.
- Dual-write periods bridge old and new schemas/tables during migration, requiring careful write ordering and eventual reconciliation.

## When to Use / When Not
- Use for changes on live production tables where downtime is unacceptable — renames, type changes, table splits, primary key changes.
- A maintenance window may suffice for simple additive changes on low-traffic tables.
- Avoid ad hoc dual-writes for high-value data without a reconciliation job; prefer backfill-then-cutover with verification.

## Tradeoffs
- Expand-contract is safer and reversible at each step but slower and needs temporary extra storage/complexity.
- Direct in-place ALTER is faster but risks locks and lag spikes, and is effectively irreversible mid-flight.
- App-level dual-write is simple but error-prone on partial failures; CDC sync (Debezium/Kafka Connect) is more reliable but adds infrastructure.

## Common Patterns & Techniques
- gh-ost and pt-online-schema-change: build a shadow table, copy rows in batches, capture ongoing changes via binlog/triggers, then atomically rename — avoiding long MySQL locks.
- PostgreSQL: `CREATE INDEX CONCURRENTLY`, instant `ADD COLUMN ... DEFAULT`, `pg_repack` for lock-light rewrites.
- Feature-flagged dual-write plus backfill job, followed by verification comparing old vs new before contract.
- Tolerant application code (ignore unknown fields, default missing ones) to survive schema drift mid-rollout.

## Pitfalls
- Dropping a column an older running instance still references during a rolling deploy, causing errors.
- Unthrottled backfill jobs saturating I/O or replica lag.
- Skipping contract, leaving permanent dual-write overhead as long-lived debt.
- Non-idempotent backfill scripts that corrupt data on retry after partial failure.

## Real-World Examples
- GitHub built gh-ost for large-scale MySQL migrations on production tables without locking.
- Stripe and Shopify document expand-contract playbooks for primary key changes and table splits at scale.
- Airbnb's data platform uses CDC-based dual-write validation when migrating between storage systems.
