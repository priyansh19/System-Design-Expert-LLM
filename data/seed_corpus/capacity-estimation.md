# Capacity Estimation

## Summary
Back-of-envelope capacity estimation converts business requirements (users, growth) into concrete numbers — QPS, storage, bandwidth, server count — that drive architecture decisions before any code is written.

## Core Principles
- Start from DAU and actions-per-user-per-day: `QPS = DAU × actions/day / 86,400`; multiply by a peak factor (commonly 2-5x average) for peak QPS.
- Storage estimation: `records/day × avg record size × retention`, then add replication factor (e.g., 3x) and index/metadata overhead (typically +20-50%).
- Bandwidth: `QPS × avg payload size` for ingress and egress separately, since read:write ratios are often skewed.
- Powers of ten checks: 1 KB ≈ 10^3 B, 1 MB ≈ 10^6 B, 1 GB ≈ 10^9 B; a day ≈ 86,400s ≈ ~10^5 s; 1 million requests/day ≈ ~12 QPS average.
- RPS-to-servers: `servers = peak QPS / QPS-per-server`, where QPS-per-server comes from realistic single-node throughput, not theoretical max — a stateless API node might sustain 500-2,000 RPS.
- State assumptions explicitly (avg object size, cache hit ratio, fan-out) — the estimate's value is exposing which assumption dominates the result.

## When to Use / When Not
- Use at the start of design exercises, or real capacity planning, to size infrastructure, choose sharding strategy, and catch infeasible designs early.
- Not a substitute for load testing before launch — estimates validate direction, not exact provisioning.

## Tradeoffs
- Precision vs speed: back-of-envelope favors round numbers over precise modeling — acceptable since inputs (user growth) are themselves uncertain.
- Overestimating peak factors leads to overprovisioning cost; underestimating risks outages during real spikes.

## Common Patterns & Techniques
- 80/20 read-heavy assumption for consumer apps, justifying aggressive caching to cut effective backend QPS.
- Cache hit ratio applied to storage/QPS math: `origin QPS = total QPS × (1 - hit ratio)`.
- Compute per-shard capacity limits (storage, QPS) first, then derive shard count from total load ÷ per-shard limit.
- Express results in both average and peak (often 2-10x for diurnal patterns) to size for the worst realistic case, not the mean.

## Pitfalls
- Confusing average and peak load, leading to systems that fall over during traffic spikes.
- Ignoring replication/index overhead, underestimating true storage needs by 2-4x.
- Treating estimates as exact rather than order-of-magnitude — the goal is "10 servers or 10,000," not the fourth decimal place.

## Real-World Examples
- URL shortener: 100M new URLs/month, ~6-byte base62 key, ~500 bytes/record → tens of GB/year, trivially shardable.
- Twitter-scale fan-out: push-on-write multiplies write QPS by follower count, justifying a hybrid push/pull model for celebrity accounts.
- Video platforms estimate storage as `uploads/day × avg encoded size × renditions × retention`, typically dominating other cost centers.
