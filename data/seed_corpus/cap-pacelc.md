# CAP Theorem and PACELC

## Summary
CAP theorem states a distributed store can provide at most two of Consistency, Availability, and Partition tolerance during a network partition; PACELC extends this to the tradeoff that persists even when the network is healthy.

## Core Principles
- Partitions are not optional (packet loss, GC pauses, NIC failures happen), so partition tolerance is effectively mandatory — the real choice is CP vs AP during a partition.
- CP systems refuse to serve (or reject writes on) the minority side of a partition to preserve consistency; AP systems keep serving on both sides and reconcile later, accepting divergence.
- PACELC: if Partitioned, choose Availability or Consistency (as in CAP); Else, choose Latency or Consistency — every system makes this second tradeoff too.
- CAP describes a single register's guarantee under partition, not a whole-system label; large systems mix CP and AP subsystems.
- Consistency in CAP means linearizability, a much stronger bar than typical "ACID consistency."

## When to Use / When Not
- Choose CP for coordination/metadata: leader election, config stores, financial ledgers, inventory counts where overselling is unacceptable.
- Choose AP for user-facing data where staleness is tolerable: social feeds, shopping carts, presence, analytics counters.
- PACELC's E/L axis matters even without partitions: choose lower latency (async replication, local reads) when strict consistency isn't worth the tail-latency cost.

## Tradeoffs
- CP systems sacrifice availability during partitions (some requests fail/timeout) to avoid stale or conflicting reads.
- AP systems sacrifice consistency, requiring conflict resolution (LWW, vector clocks, CRDTs) and exposing stale reads.
- Even in normal operation, synchronous consistency protocols (quorum, consensus) add latency that async/local reads avoid.

## Common Patterns & Techniques
- Quorum reads/writes (W + R > N) to tune the consistency/availability point within a nominally AP system.
- Consensus protocols (Raft, Paxos) for CP coordination services.
- Hinted handoff and read-repair in AP systems to converge replicas after a partition heals.
- Tunable consistency levels (Cassandra's ONE/QUORUM/ALL) letting callers pick per-query.

## Pitfalls
- Treating CAP as a permanent system-wide label instead of a per-operation, per-partition-event tradeoff.
- Assuming a CP system is always "slow" or an AP system "always fast" — normal-case latency is a separate design axis.
- Deploying a CP system (e.g., ZooKeeper, etcd) as the hot path for high-QPS user traffic instead of for coordination only.

## Real-World Examples
- DynamoDB and Cassandra are AP by default (tunable), prioritizing availability and low latency with eventual consistency.
- Google Spanner and etcd/ZooKeeper are CP, using consensus (Paxos/Raft) to guarantee linearizable reads at the cost of availability during partitions.
- MongoDB defaults to CP-leaning behavior with a single primary, sacrificing writes availability during failover elections.
