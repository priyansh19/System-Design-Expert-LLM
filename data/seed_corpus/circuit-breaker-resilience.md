# Circuit Breaker & Resilience Patterns

## Summary
Circuit breakers and related patterns — retries with jitter, timeouts, bulkheads, graceful degradation — stop a failing dependency from cascading into an outage by failing fast and isolating blast radius.

## Core Principles
- States: Closed (requests flow, failures counted), Open (fail immediately once a threshold trips), Half-Open (after cooldown, trial requests test recovery before fully closing).
- Timeouts bound how long a caller waits for a dependency; without them, slow dependencies exhaust caller threads — a common cascading-failure cause.
- Bulkheads isolate resource pools per dependency so one failing downstream can't starve resources serving healthy ones.
- Retries with exponential backoff and jitter reduce load on a recovering service and avoid thundering-herd retry storms.
- Graceful degradation returns a reduced-but-useful response (cache, default, partial result) instead of a hard failure.

## When to Use / When Not
- Use circuit breakers on any synchronous call to a service, downstream microservice, or database that can be slow or unavailable under load.
- Use bulkheads when a service calls multiple downstreams with different reliability profiles.
- Avoid blind retries on non-idempotent operations without dedup keys — retrying a failed charge can double-bill a user.
- Skip breakers for low-latency, reliable in-process calls where the overhead isn't justified.

## Tradeoffs
- Circuit breakers improve availability during outages but add complexity and can trip on transient blips if thresholds are too tight.
- Retries raise success rate for transient errors but amplify load on a struggling dependency without backoff and jitter.
- Graceful degradation improves perceived availability but can mask real failures if not distinctly logged.

## Common Patterns & Techniques
- Resilience4j (Hystrix's successor): composable CircuitBreaker, Retry, TimeLimiter, Bulkhead, RateLimiter modules around a call.
- Full-jitter exponential backoff (`sleep = random(0, min(cap, base * 2^attempt))`) avoids synchronized retry storms.
- Fallback methods configured alongside the breaker degrade gracefully instead of propagating errors.
- Health-check-based load balancer ejection complements breakers by removing unhealthy instances from rotation.
- Service-mesh resilience (Istio, Envoy, Linkerd) applies circuit breaking transparently outside application code.

## Pitfalls
- Retries without a total budget cap, so one request fans out into dozens of downstream retries.
- No timeout at all — the single most common root cause of cascading-failure incidents.
- Breaker thresholds tuned without load testing, tripping too eagerly or too late.
- Retrying non-idempotent writes without idempotency keys, causing duplicate side effects.

## Real-World Examples
- Netflix's Hystrix pioneered circuit breaking and bulkheading for microservice resilience at scale.
- AWS SDKs default to exponential backoff with jitter, per AWS's retry/backoff guidance.
- Envoy and Istio provide circuit breaking (outlier detection, pool limits) at the service mesh layer.
