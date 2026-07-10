# Leader Election

## Summary
Leader election designates one node as the authoritative coordinator for a task — serializing writes, assigning work, driving replication — so distributed systems avoid conflicting concurrent decisions while tolerating node failure.

## Core Principles
- A leader removes coordination ambiguity: someone must own writes, assignment, or scheduling so peers don't race each other.
- Consensus-based election (Raft, ZAB) ties leadership to a quorum vote and a term number, so changes are safe and only one leader is valid per term.
- Lease-based election (ZooKeeper ephemeral nodes, etcd leases) ties leadership to a time-bounded lock: the leader must renew before expiry or another node acquires it.
- A fencing token — a monotonically increasing number issued per acquisition — lets downstream resources reject stale writes from a leader that lost its lease but hasn't noticed.
- Failover time is detection latency (heartbeat/timeout) plus election latency; tuning trades faster failover against false-positive elections.

## When to Use / When Not
- Use when a single writer/coordinator is needed: primary-replica databases, job schedulers, Kafka partition leaders, distributed cron.
- Skip it for stateless, independently-scalable workers with no coordination need — a leader there is unnecessary complexity.
- Avoid rolling your own election protocol; use a battle-tested coordination service instead of ad hoc heartbeat races.

## Tradeoffs
- Faster detection (short timeouts) increases false-positive elections during GC pauses vs. longer timeouts increasing real downtime.
- Centralizing coordination simplifies logic but caps throughput/availability to what one node (plus failover pause) sustains.
- External coordination services add an operational dependency but remove correctness burden from application code.

## Common Patterns & Techniques
- ZooKeeper: ephemeral sequential znodes; lowest-sequence node is leader, others watch their predecessor to avoid herd effects.
- etcd: lease + campaign API built on Raft, giving TTL-based leadership with automatic renewal.
- Bully and Ring algorithms: older ID-based election schemes, largely superseded by consensus-backed approaches.
- Fencing tokens passed to storage backends (a monotonic epoch on every write) to guard against zombie leaders.

## Pitfalls
- Assuming a leader that stops renewing its lease immediately stops acting — without fencing, a paused leader can wake and write after a new leader is elected.
- Setting timeouts too aggressively on high-latency or bursty networks, causing election storms ("flapping" leadership).
- Forgetting election guarantees "at most one leader per term," not "exactly one leader always" — brief leaderless gaps are normal.

## Real-World Examples
- Kafka uses a controller broker (formerly ZooKeeper-elected, now KRaft/Raft) to manage partition leader assignment.
- Kubernetes control-plane components use leader election via Lease objects in etcd for active-standby HA.
- PostgreSQL HA tools like Patroni use etcd/Consul/ZooKeeper for primary election and automated failover.
