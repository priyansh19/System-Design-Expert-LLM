# Rate Limiting

## Summary
Rate limiting caps the request rate a client or system will accept, protecting backends from overload, enforcing fair usage/API tiers, and preventing abuse — the algorithm chosen determines burst tolerance and accuracy.

## Core Principles
- Token bucket: a bucket refills at a fixed rate up to a capacity; each request consumes a token, allowing bursts up to bucket size while enforcing a long-run average rate.
- Leaky bucket: requests queue and are processed at a constant output rate, smoothing bursts entirely but adding latency and needing a bounded queue.
- Fixed window: counts requests per discrete window (e.g., per minute); simple, but allows up to 2x the limit at window boundaries.
- Sliding window log: stores a timestamp per request for exact enforcement, but memory grows with request volume.
- Sliding window counter: approximates the log by weighting the previous window's count, giving near-exact accuracy with O(1) storage — the common production compromise.
- Distributed rate limiting needs a shared, low-latency counter store (Redis) with atomic increment-and-expire (Lua script or `INCR`+`EXPIRE`) to avoid races across app instances.

## When to Use / When Not
- Use at API gateways to protect origin services, for per-tenant fairness in multi-tenant SaaS, and to throttle expensive operations (search, exports).
- Avoid uniform limits when workload cost varies widely — prefer adaptive or cost-weighted quotas instead.

## Tradeoffs
- Token/leaky bucket allow bursts vs strict smoothing — bursts help spiky legitimate clients but risk momentary overload.
- Precision (sliding log) vs memory/CPU cost — exact algorithms don't scale to high QPS.
- Centralized (Redis) limiting is accurate but adds a network hop and contention point; local/in-memory limiting is fast but inconsistent across nodes.

## Common Patterns & Techniques
- Redis + Lua script implementing token bucket atomically to avoid check-then-act races.
- GCRA (Generic Cell Rate Algorithm), used by Stripe, computes a theoretical arrival time for smooth, low-memory limiting equivalent to leaky bucket.
- Layered limiting: per-IP, per-API-key, and per-endpoint limits applied simultaneously.
- Return `429 Too Many Requests` with a `Retry-After` header so clients back off correctly.

## Pitfalls
- Fixed-window boundary bursts silently doubling effective throughput.
- Not sharing limiter state across horizontally scaled instances, letting clients bypass limits by hitting different nodes.
- Limiting on request count alone while ignoring request cost (a cheap lookup vs a full table scan hitting the same limit).

## Real-World Examples
- Stripe's API uses a GCRA-style token-bucket algorithm per API key with clear rate-limit headers.
- Cloudflare enforces edge rate limiting to block abusive traffic before it reaches origin.
- GitHub enforces primary (per-hour) and secondary (concurrency/content-creation) limits to protect shared infrastructure.
