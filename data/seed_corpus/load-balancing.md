# Load Balancing

## Summary
A load balancer distributes incoming traffic across backend instances to maximize throughput, minimize latency, and avoid overloading any single node.

## Core Principles
- L4 (transport layer) load balancers route based on IP/TCP/UDP info without inspecting payload, forwarding whole connections at line rate with minimal overhead (e.g., AWS NLB, IPVS, HAProxy TCP mode).
- L7 (application layer) load balancers terminate HTTP(S) and route on URL path, headers, or cookies, enabling content-based routing at the cost of higher CPU/latency per request.
- Round-robin distributes requests sequentially across backends; simple but ignores real load or backend health.
- Least-connections routes to the backend with the fewest active connections, adapting better than round-robin when request durations vary widely.
- Consistent hashing maps both requests (by key) and backends onto a hash ring so a given key routes to the same backend, minimizing remapping on backend join/leave — critical for cache affinity.

## When to Use / When Not
- Use L4 for raw TCP/UDP services or non-HTTP protocols; use L7 when routing needs to be content- or session-aware (API gateways, microservices).
- Use consistent hashing when backend affinity matters (cache locality, sharded services); avoid it for stateless compute where round-robin/least-conn is simpler and better balanced.
- Avoid sticky sessions for new stateless-by-design services; they reintroduce state coupling that undermines elastic scaling.

## Tradeoffs
- L7's flexibility costs CPU cycles (TLS termination, header parsing) versus L4's near-passthrough speed.
- Consistent hashing trades perfect load balance for minimal remapping on membership changes; without virtual nodes it can be badly skewed.
- Sticky sessions improve cache hit rate for stateful apps but create hot spots and complicate failover.

## Common Patterns & Techniques
- Active health checks (periodic synthetic probes) and passive checks (error-rate/latency ejection, outlier detection) to route around unhealthy nodes.
- Virtual nodes in consistent hashing (each physical node maps to many ring positions) smooth load distribution and reduce hotspots on scale events.
- Weighted round-robin/least-conn for heterogeneous instance sizes.
- Connection draining during deploys avoids killing in-flight requests.

## Pitfalls
- Health checks that only verify the process is up (not that it can serve real traffic) mask degraded backends.
- Consistent hashing without virtual nodes causes uneven load when the backend count is small.
- Sticky sessions with autoscaling can strand sessions on scaled-down instances, causing errors.

## Real-World Examples
- Google's Maglev is a software L4 load balancer using consistent hashing for connection-level balancing at massive scale.
- Envoy Proxy (used by Lyft, widely in service meshes) provides L7 routing with active/passive health checks and outlier detection.
- AWS offers both NLB (L4, high throughput) and ALB (L7, path/header routing) as managed complements to this pattern.
