# Multi-Region Active-Active

## Summary
Multi-region active-active deployments serve reads and writes from independent regions simultaneously, minimizing latency and surviving regional outages, at the cost of conflict resolution, data residency complexity, and harder-to-reason-about consistency.

## Core Principles
- Active-active: every region accepts writes concurrently; requires multi-leader or leaderless replication plus conflict resolution, since concurrent writes to the same key can arrive at different regions.
- Active-passive (active-standby): one region is authoritative for writes; standbys replicate asynchronously and only take write traffic during failover — simpler consistency, but idle standby capacity and failover RTO/RPO gaps.
- Cross-region WAN latency (50-150ms+ RTT) makes synchronous cross-region commits expensive, so active-active usually implies eventual consistency for cross-region writes.
- Data residency laws (GDPR, localization mandates) often force geo-partitioning specific data to home regions rather than replicating everywhere.
- Failover needs health-checked traffic steering (DNS/anycast/global LB) plus a promotion protocol that prevents split-brain — two regions both believing they own the same write.

## When to Use / When Not
- Use active-active when a global user base needs low write latency everywhere and writes are naturally conflict-free (per-user/tenant home-region partitioning).
- Use active-passive when strong consistency matters more than latency, or conflict risk/operational cost of full active-active is unjustified.
- Avoid active-active for workloads with frequent cross-region contention on the same record (global counters, inventory) without CRDTs or partitioning.

## Tradeoffs
- Active-active: lower latency, higher availability vs conflict complexity, possible silent merges/data loss, doubled running cost.
- Active-passive: simpler and cheaper vs failover latency (RTO) and risk of losing unreplicated writes (RPO).
- Geo-partitioning for compliance reduces cross-region traffic but complicates global aggregation and can create hot regions.

## Common Patterns & Techniques
- Cell-based active-active: partition by tenant/region so each write's true owner is deterministic, avoiding real multi-master conflicts.
- CRDTs or commutative operations for fields that must auto-merge (counters, sets, presence).
- Global load balancers (Route 53 latency routing, Cloudflare, GCP Global LB) with health checks driving automatic failover.
- Regular chaos/game-day failover drills to validate RTO/RPO before a real outage.

## Pitfalls
- Split-brain during a network partition: both regions accept writes as primary, producing divergent state that's costly to reconcile.
- Assuming active-active gives strong consistency "for free" when most implementations are eventually consistent cross-region.
- Deferring data residency decisions until a compliance audit forces expensive re-architecture.
- Under-provisioning standby capacity so failover traffic cascades into overload.

## Real-World Examples
- Netflix runs active-active cell architecture across AWS regions so one region's failure only degrades that region.
- Google Spanner offers synchronous multi-region replication via TrueTime, trading write latency for strong consistency.
- DynamoDB Global Tables and Cosmos DB provide active-active with last-writer-wins or custom conflict resolution.
