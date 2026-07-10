# API Gateway

## Summary
An API gateway is a single entry point in front of backend services, handling cross-cutting concerns (routing, auth, rate limiting, aggregation) so individual services don't reimplement them — the edge where client concerns meet internal topology.

## Core Principles
- Request routing maps paths/hosts/headers to the correct upstream via a dynamic service registry (Consul, Eureka, Kubernetes Service) rather than static config.
- Authentication/authorization terminates TLS, validates JWTs against an OAuth2/OIDC provider, and forwards a trusted identity context downstream.
- Rate limiting and quota enforcement happen at the edge, per API key/tenant, before load reaches internal services.
- Request/response transformation (protocol translation, header rewriting) lets clients and services evolve independently.
- Aggregation composes multiple backend calls into one client-facing response, reducing round trips.
- Backend-for-Frontend (BFF) is a gateway variant tailored per client type (mobile, web, partner) exposing a shape optimized for that consumer.

## When to Use / When Not
- Use when many client types hit growing microservices and cross-cutting logic would otherwise be duplicated per service.
- Use a BFF when client types need meaningfully different data shapes from the same backend.
- Avoid for a small monolith — the gateway adds latency with no payoff.
- Avoid letting the gateway accumulate business logic; it should stay a routing/policy layer.

## Tradeoffs
- Simplifies client integration and centralizes policy vs introduces a single point of failure and an extra hop per request.
- Aggregation reduces client round trips vs couples the gateway to backend response shapes.
- Centralized auth simplifies services vs makes the gateway a high-value attack target and scaling bottleneck if under-provisioned.

## Common Patterns & Techniques
- Envoy/Kong/NGINX/AWS API Gateway for north-south traffic, paired with a service mesh for east-west traffic.
- Circuit breaking and retries with timeouts at the gateway to prevent cascading failures into misbehaving upstreams.
- Canary/blue-green routing by weighting traffic across service versions at the gateway.
- GraphQL gateways (Apollo Federation) aggregate over a composed schema instead of per-service REST calls.

## Pitfalls
- Putting business logic or domain-specific transformation in the gateway, coupling it tightly to service internals.
- Under-provisioning the gateway tier so it becomes the bottleneck the microservices split was meant to avoid.
- Aggregation calls made serially instead of in parallel, turning fan-out into added latency instead of savings.

## Real-World Examples
- Netflix's Zuul (and successor Spring Cloud Gateway) routes and filters requests across hundreds of backend microservices.
- Amazon API Gateway fronts Lambda and backend services with built-in throttling, API keys, and usage plans.
- Kong and Envoy are widely self-hosted in Kubernetes, combining routing with plugin-based auth and rate limiting.
</content>
<parameter name="i">Trim api-gateway note to fit word range