# Content Delivery Network (CDN)

## Summary
A CDN is a globally distributed network of edge servers that caches and serves content close to users, cutting latency, offloading origin traffic, and absorbing large traffic spikes and DDoS attacks.

## Core Principles
- Edge caching: static (and increasingly dynamic) responses are cached at PoPs near users, served without a round trip to origin on a hit.
- Anycast routing: the same IP is announced from many PoPs; BGP routes each user to the nearest one, giving low-latency routing without client logic.
- TTL controls how long an edge node serves a cached object before revalidating with origin, set via `Cache-Control: max-age` or CDN-specific rules.
- `Cache-Control` directives (`public`, `private`, `no-store`, `s-maxage`, `stale-while-revalidate`, `stale-if-error`) let origin dictate cacheability for shared caches vs browsers.
- Origin shielding: one designated edge region sits between other PoPs and origin, coalescing simultaneous cache-miss requests into one origin call, blocking thundering herds.
- Cache invalidation/purging: explicit purge (by URL or surrogate key/cache-tag) is needed when content changes before TTL expiry.

## When to Use / When Not
- Use for static assets (JS/CSS/images), video streaming, cacheable API responses, and DDoS/traffic absorption at the edge.
- Avoid relying on CDN caching for personalized or write-heavy endpoints without careful cache-key/`Vary` design — misconfiguration leaks private data.

## Tradeoffs
- Longer TTLs improve hit ratio and cut origin load but increase staleness risk; short TTLs stay fresh but raise origin traffic and cost.
- Origin shielding reduces origin load but adds one extra hop on shield misses.
- Aggressive purging keeps content fresh, but global purge propagation isn't instantaneous and can be rate-limited.

## Common Patterns & Techniques
- Surrogate keys / cache tags for grouping and bulk-purging related cached objects (e.g., all pages referencing a product).
- `stale-while-revalidate` serves stale content immediately while refreshing in the background, hiding origin latency.
- Cache-key normalization (stripping irrelevant query params, disciplined `Vary` usage) maximizes hit ratio without cache poisoning.
- Multi-CDN strategies for resilience and cost arbitrage, routed via DNS or a traffic-steering layer.

## Pitfalls
- Caching authenticated/personalized responses without proper `Vary`/private cache-control, leaking one user's data to another.
- Forgetting cache invalidation on deploys, serving stale JS/CSS that breaks against a new API contract.
- Thundering herd on a cold or mass-purged cache without origin shielding or request coalescing.

## Real-World Examples
- Cloudflare and Akamai run anycast global edge networks with programmable edge logic (Workers/EdgeWorkers).
- Netflix built Open Connect, custom CDN appliances embedded in ISP networks to serve video with minimal backbone transit.
- Fastly's instant purge (sub-second global invalidation) is used by news sites to refresh cached pages instantly.
