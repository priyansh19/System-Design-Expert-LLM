# Backpressure

## Summary
Backpressure is the mechanism by which a system signals or forces an upstream producer to slow down when a downstream consumer can't keep up, preventing unbounded queue growth and cascading failure.

## Core Principles
- Flow control: consumers communicate capacity back to producers (TCP windowing, reactive streams' `request(n)`, HTTP/2 flow-control frames) so producers send only what can be handled.
- Bounded queues: every buffer (in-memory queue, thread-pool queue, connection pool) must be finite — unbounded queues just delay an OOM crash instead of preventing it.
- Load shedding: once capacity is exceeded, deliberately reject or drop excess requests (fail fast with 503) rather than queue indefinitely, preserving latency for accepted requests.
- Circuit breakers: track failure/latency rates to a dependency and "open" (fail fast without calling) past a threshold, giving the dependency time to recover and preventing resource exhaustion in the caller.
- Bulkheads: partition resources (thread pools, connection pools) per dependency so one slow/failing downstream can't exhaust resources needed by others.
- Little's Law underlies the math: concurrency = arrival rate × latency; as latency grows under load, required concurrency grows too, which is why unbounded queues explode.

## When to Use / When Not
- Use whenever a fast producer feeds a slower/rate-limited consumer: ingestion pipelines, API gateways in front of a DB, clients syncing to a backend.
- Overkill for internal calls with well-known, bounded volume and generous headroom — the added complexity isn't free.

## Tradeoffs
- Load shedding improves availability for accepted traffic but sacrifices some requests entirely — callers must handle rejection gracefully.
- Larger buffers absorb bursts but increase tail latency (bufferbloat) and delay failure detection.
- Circuit breakers reduce cascading failure but can false-trip under transient blips if thresholds are too sensitive.

## Common Patterns & Techniques
- Reactive Streams / Project Reactor / RxJava backpressure operators (`onBackpressureDrop`, `onBackpressureBuffer`).
- Semaphore-based concurrency limiting (Netflix concurrency-limits, adaptive TCP-Vegas-style algorithms) instead of fixed thread-pool sizes.
- Hystrix/resilience4j-style circuit breakers combined with per-downstream bulkhead thread pools.
- Queue-depth-based autoscaling and explicit `429`/`503` responses with `Retry-After`.

## Pitfalls
- Unbounded thread pools or queues that hide the problem until a full outage.
- Retrying aggressively into an already-overloaded service, amplifying failure (retry storms) — needs exponential backoff with jitter.
- Circuit breakers with no half-open probing, permanently blocking a recovered dependency.

## Real-World Examples
- Netflix's Hystrix (and successor resilience4j) pioneered circuit breakers and bulkheads for microservice resilience.
- TCP itself implements backpressure via congestion/flow-control windows.
- Kafka consumers apply backpressure naturally through poll rate, preventing producers from overwhelming a slow consumer group.
