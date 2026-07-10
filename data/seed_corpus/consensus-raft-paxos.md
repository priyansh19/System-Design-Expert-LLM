# Consensus: Raft & Paxos

## Summary
Consensus algorithms let unreliable clustered nodes agree on a single value or ordered operation sequence despite crashes and message loss, underpinning replicated state machines, distributed locks, and metadata stores.

## Core Principles
- Quorum agreement: a value commits only after a majority (N/2 + 1) accepts it, so any two quorums overlap, preventing conflicting decisions.
- Raft splits consensus into leader election, log replication, and safety: one elected leader serializes writes into a replicated log; followers apply entries only after majority replication (commit index).
- Raft election uses randomized timeouts and increasing terms so at most one leader wins per term; voters reject candidates with a less up-to-date log.
- Paxos agrees on a single value via Prepare/Promise and Accept/Accepted phases using proposal numbers; Multi-Paxos chains instances into a log, similar to Raft but harder to implement correctly.
- Split-brain is prevented by quorum overlap, not locking: a stale leader can't commit without a majority once a newer term is elected elsewhere.

## When to Use / When Not
- Use for small, critical state — membership, election, configuration, locks — not general application data at scale.
- Use when strict linearizability and crash-fault tolerance are required, e.g., a lock service or routing metadata.
- Avoid running consensus directly over large, high-throughput datasets; it doesn't scale like sharded replication.

## Tradeoffs
- Safety under crash faults vs. throughput ceiling: every commit needs a majority round-trip, bounded by the slowest quorum member.
- Leader-failure availability gap is a temporary election pause, unlike leaderless systems that stay writable through partitions.
- Raft trades theoretical minimality for an implementable, teachable protocol, why most systems now favor it over classic Paxos.

## Common Patterns & Techniques
- Log replication with commit index and matchIndex/nextIndex bookkeeping per follower (Raft).
- Leases and fencing tokens atop a consensus-backed lock to prevent stale-leader writes.
- Joint consensus for membership changes to avoid two disjoint majorities during reconfiguration.
- Snapshotting/log compaction to bound log growth for long-running clusters.

## Pitfalls
- Treating consensus as general database replication, causing severe throughput bottlenecks.
- Hand-rolling a "simplified Raft" that skips log-matching/safety rules, causing committed-then-lost entries.
- Assuming a stale leader instantly stops acting; it must be fenced or it can serve stale reads during a partition.

## Real-World Examples
- etcd and Consul use Raft for cluster metadata and leader election, underpinning Kubernetes control-plane state.
- Chubby (Google) and ZooKeeper's ZAB are Paxos-family systems providing locking and configuration.
- CockroachDB and TiDB use per-range Raft groups to replicate sharded data with linearizable consistency.
