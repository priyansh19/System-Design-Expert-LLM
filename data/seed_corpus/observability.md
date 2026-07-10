# Observability

## Summary
Observability is the ability to understand a system's internal state from its external outputs — metrics, logs, and traces — letting engineers debug novel production failures rather than only ones anticipated by pre-built dashboards.

## Core Principles
- The three pillars: metrics (aggregated numeric time series), logs (discrete timestamped events, ideally structured), and traces (causal chains of spans across services for one request).
- RED method (Rate, Errors, Duration) is standard for request-driven services: requests/sec, error rate, latency distribution per endpoint.
- USE method (Utilization, Saturation, Errors) is for resources: how busy, how much work is queued, error counts.
- SLIs are the measured metric (e.g., p99 latency); SLOs are the target (e.g., 99.9% <300ms); error budgets (100% - SLO) are spent on risk before freezing changes.
- Distributed tracing propagates a trace ID and span IDs across service boundaries (W3C Trace Context) to reconstruct a request's full path and latency breakdown.
- High-cardinality data (user/request ID) belongs in traces/logs, not metric labels — unbounded cardinality blows up time-series cost.

## When to Use / When Not
- Essential for any distributed system with more than a couple of services or any system with an SLA.
- Overkill initially for a single-process prototype; start with structured logging and add metrics/tracing as the system grows past one service.

## Tradeoffs
- Storage/ingestion cost vs. granularity — full tracing at 100% sample rate is expensive, so most systems use tail- or head-based sampling.
- Alerting on symptoms (SLO burn rate) vs. causes (CPU, queue depth) — symptom-based reduces noise but needs good SLOs first.

## Common Patterns & Techniques
- OpenTelemetry as the vendor-neutral standard for instrumenting metrics, logs, and traces together.
- Multi-burn-rate alerting on error-budget consumption avoids noisy pages and missed slow leaks.
- Structured JSON logging with correlation IDs linking logs to traces.
- Dashboards built around the four golden signals: latency, traffic, errors, saturation.

## Pitfalls
- Alerting on every metric anomaly instead of user-facing SLO violations, causing alert fatigue.
- No trace context propagation across async boundaries (queues, background jobs), breaking the causal chain.
- Logging PII/secrets in plaintext, creating compliance risk.
- Treating 100% uptime as the goal instead of an agreed error budget, stalling deploys and experiments.

## Real-World Examples
- Google's SRE practice popularized SLOs and error budgets balancing reliability work against feature velocity.
- Netflix built Atlas for high-cardinality metrics at massive scale and relies heavily on distributed tracing to debug microservice cascades.
- Honeycomb popularized high-cardinality event-based observability as an alternative to pre-aggregated metrics for debugging novel failures.
