# Newsfeed Fan-out

## Summary
Newsfeed generation delivers a personalized, ranked stream of posts from a user's social graph, and the central design decision is when fan-out happens: at write time, read time, or a hybrid of both.

## Core Principles
- Fan-out on write (push): posting writes the post ID into every follower's precomputed feed (Redis sorted set), so reads are a fast lookup.
- Fan-out on read (pull): feeds are computed at request time by merging recent posts from followees, avoiding wasted writes but making reads expensive as follow counts grow.
- Hybrid fan-out: most users use push, but "celebrity" accounts with huge follower counts are excluded and merged in at read time, avoiding a write storm per post.
- Timeline cache: precomputed feeds are bounded, capped lists (e.g., last 800 IDs) keyed by user, trimmed to bound memory.
- Ranking is decoupled from fan-out: a candidate set is scored by a model (recency, engagement, affinity) before final ordering.

## When to Use / When Not
- Use pure push for read-heavy products with moderate, bounded follower counts.
- Use hybrid fan-out once the platform has power users/celebrities with millions of followers — pure push becomes write amplification.
- Avoid pure pull for high-follower-count reads; merging thousands of timelines per request doesn't scale.

## Tradeoffs
- Push optimizes read latency at the cost of write amplification and wasted storage for inactive followers.
- Pull avoids wasted writes but pushes cost to read time, which is far more frequent than write time.
- Hybrid bounds both write and read cost at the cost of two code paths and a threshold to tune.

## Common Patterns & Techniques
- Redis sorted sets or Cassandra wide rows keyed by user ID for precomputed timelines, scored by timestamp or rank.
- Celebrity/whale detection by follower-count threshold, routing those accounts to pull-based merge-at-read.
- Raw posts (canonical, durable) stored separately from feed indexes (derived, rebuildable) so feed corruption never risks data loss.
- Two-stage ranking: cheap candidate generation followed by an ML ranking pass on a bounded candidate set.

## Pitfalls
- Pure push fan-out melting down when a celebrity posts, generating millions of writes in seconds.
- Treating the timeline cache as source of truth instead of a rebuildable derived index, complicating recovery.
- Over-engineering strong consistency into a feed use case that tolerates seconds of staleness.

## Real-World Examples
- Twitter's fan-out-on-write architecture evolved into a hybrid model specifically to handle celebrity accounts.
- Instagram's feed uses candidate generation plus ML ranking, merging push-based fan-out with relevance scoring.
- Facebook's feed infrastructure (EdgeRank and successors) separates candidate aggregation from a heavyweight ranking model.
</content>
<parameter name="i">Rewrite newsfeed-fanout tighter