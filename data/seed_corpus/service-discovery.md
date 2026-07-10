# Service Discovery

## Summary
Service discovery lets services find the current network location of other services in a dynamic environment where instances are constantly added, removed, or rescheduled, replacing static hostnames/IPs with a live, queryable registry.

## Core Principles
- Client-side discovery: the client queries a registry directly and load-balances across returned instances itself (Netflix Eureka + Ribbon); low latency but couples clients to the registry's library.
- Server-side discovery: the client calls a fixed endpoint (load balancer/router), which queries the registry and forwards the request (AWS ELB, Kubernetes Service); simpler clients, extra hop.
- A service registry (Consul, etcd, Eureka, Kubernetes API) maintains the authoritative, continuously updated mapping of service name to healthy instance addresses.
- Health checks (active polling or passive/heartbeat) keep the registry accurate by evicting instances that stop responding, preventing routing to dead nodes.
- DNS-based discovery (CoreDNS, Consul DNS) exposes the registry through standard DNS/SRV records, trading fine-grained control for compatibility with existing tooling.

## When to Use / When Not
- Use in any environment with dynamic scaling, orchestration, or frequent deployments where IPs change constantly.
- Server-side discovery fits polyglot microservice fleets where a client library per language is unwanted.
- Skip a dedicated registry for small, static deployments where fixed IPs or a DNS A record suffices.

## Tradeoffs
- Client-side discovery: lower latency, smarter load-balancing policies, but every client language needs registry-aware logic.
- Server-side discovery: uniform behavior and simpler clients, but adds a hop and makes the router/LB a scaling concern.
- Push-based updates (watches) give near-real-time freshness at the cost of connection overhead; polling is simpler but stale.

## Common Patterns & Techniques
- Sidecar/service-mesh discovery (Envoy + xDS, Istio) where a local proxy handles discovery and load balancing transparently.
- Self-registration (instance registers/deregisters itself) vs. third-party registration (an agent like a Consul agent or kubelet registers on its behalf).
- Health-check strategies: TCP/HTTP liveness probes, TTL heartbeats, readiness vs. liveness to avoid routing to a not-yet-ready instance.
- Caching discovery results client-side with short TTLs to reduce registry load while bounding staleness.

## Pitfalls
- Self-registration without reliable deregistration (crash without cleanup) leaves ghost entries; TTL expiry or health checking is needed as a backstop.
- Treating DNS caching as instant — discovery can lag actual changes by the resolver's cache TTL.
- Registry becoming a single point of failure without its own replication/quorum (most registries are themselves consensus-backed).

## Real-World Examples
- Kubernetes uses server-side discovery via kube-proxy/Services and CoreDNS, backed by etcd-stored API server state.
- Netflix's original microservices stack used Eureka for client-side discovery paired with Ribbon.
- HashiCorp Consul combines a registry, health checking, and DNS/HTTP interfaces for mixed VM/container environments.
