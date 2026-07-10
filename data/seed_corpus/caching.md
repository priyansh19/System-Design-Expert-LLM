# Caching Strategies

## Summary
Caching stores a cheap-to-read copy of expensive-to-compute or expensive-to-fetch data closer to the consumer, trading staleness risk for reduced latency and reduced load on the system of record.

## Core Principles
- Cache-aside (lazy loading): app checks cache first, on miss reads the DB and populates the cache; simple and resilient to cache failure, but the first request after eviction pays full latency.
- Write-through: writes go to the cache and the DB synchronously in the same request path, keeping the cache always consistent at the cost of write latency.
- Write-back (write-behind): writes land in the cache and are asynchronously flushed to the DB later, giving very fast writes but risking data loss on cache failure before flush.
- TTL (time-to-live) bounds staleness for data where exact invalidation is hard; shorter TTL means fresher data but more origin load.
- Eviction policy: LRU (evict least recently used, cheap via a doubly-linked list + hashmap, good default) vs LFU (evict least frequently used, better for skewed access but costlier to track and slower to adapt).

## When to Use / When Not
- Use for read-heavy workloads with skewed key popularity (Zipfian access), expensive joins/aggregations, or slow upstream APIs.
- Avoid for data needing strict read-your-writes or regulatory-grade consistency without an invalidation strategy, and for low-reuse or uniform-access write-heavy data where hit rate would be poor.

## Tradeoffs
- Freshness vs latency: aggressive invalidation keeps data correct but increases origin traffic and complexity.
- Memory cost vs hit rate: bigger caches raise hit rate with diminishing returns and real infra cost.
- Write-through simplicity vs write-back throughput, at the cost of durability guarantees.

## Common Patterns & Techniques
- Cache stampede / thundering herd mitigation: request coalescing (single-flight), probabilistic early expiration, and locking so only one caller refills a hot key while others wait or serve stale data.
- Negative caching for known-absent keys to prevent repeated DB misses.
- Read-through caches (cache library owns the fetch-on-miss logic transparently).
- Multi-tier caching: CDN edge cache, local in-process cache (Caffeine, Guava), distributed cache (Redis, Memcached).

## Pitfalls
- No jitter on TTLs causes synchronized mass expiration and stampedes.
- Caching without a clear invalidation trigger leads to permanently stale data ("cache never expires" bugs).
- Ignoring cache key cardinality explosion (e.g., per-user + per-locale + per-feature-flag) destroys hit rate.

## Real-World Examples
- Facebook's TAO and Memcache deployment uses cache-aside with lease tokens to prevent stampedes at massive fan-out.
- Netflix uses EVCache (Memcached-based) as a distributed cache-aside layer in front of Cassandra for low-latency reads.
- CDNs like Cloudflare and Akamai apply TTL-based caching with cache-tag purging for static and semi-dynamic content.
