# Heartbeats & Failure Detection

## Summary
Failure detection is how a distributed system infers a remote node is unreachable or dead, using periodic signals and timeouts — inherently imperfect since network delay and crash look identical to a waiting observer.

## Core Principles
- A heartbeat is a periodic "I'm alive" message (push) or poll (pull); missing heartbeats past a timeout is interpreted as failure.
- Fixed timeouts force a tradeoff: too short causes false positives under GC pauses or congestion; too long delays real detection.
- Phi-accrual (Cassandra, Akka) replaces a binary verdict with a continuous suspicion level (phi) from the distribution of recent heartbeat inter-arrival times, letting apps pick their own confidence threshold instead of a hardcoded timeout.
- SWIM avoids O(n) fan-out from one coordinator: each node pings a random peer; unacked pings trigger indirect probing via other peers before declaring suspicion, then gossip disseminates it.
- Detectors are inherently probabilistic on async networks (FLP impossibility: perfect accuracy and completeness can't coexist) — systems accept eventual, imperfect detection.

## When to Use / When Not
- Use whenever cluster membership or leader liveness must be tracked: consensus systems, service meshes, health checks.
- Use phi-accrual or adaptive detectors when nodes span variable-latency networks where one fixed timeout fits no link well.
- Avoid aggressive fixed timeouts with known GC pauses or bursty I/O; they generate false-positive failovers more than real ones.

## Tradeoffs
- Short timeouts: fast failure response, more false positives (unnecessary failovers/re-elections).
- Long timeouts: fewer false positives, slower recovery and longer degraded-service windows during a real outage.
- Centralized heartbeating is simple but doesn't scale and is a single point of failure; gossip-style detection scales better but converges more slowly.

## Common Patterns & Techniques
- Phi-accrual detector: maintains a sliding window of heartbeat intervals, fits a distribution, outputs a suspicion score.
- SWIM's indirect probing reduces false positives from one congested link by cross-checking through other members first.
- Combining heartbeats with application-level health/readiness checks, not pure network liveness.
- Exponential backoff on retries before declaring a node dead, to absorb transient blips.

## Pitfalls
- Confusing "unreachable" with "dead" — a partitioned-but-alive node causes split-brain if the cluster acts on a false verdict without fencing.
- Using one fixed global timeout across nodes with very different baseline latencies.
- Ignoring heartbeat message loss as a signal — dropped heartbeats under load can cascade into false failure storms.

## Real-World Examples
- Cassandra uses phi-accrual to decide when to mark a node down for routing.
- Consul and HashiCorp's memberlist implement SWIM-based gossip for membership and failure detection.
- Kubernetes uses kubelet liveness/readiness probes plus heartbeats to evict failed nodes.
