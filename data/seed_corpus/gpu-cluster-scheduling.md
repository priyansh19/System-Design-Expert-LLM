# GPU Cluster Scheduling for ML Workloads

## Summary
Scheduling ML training and inference jobs across a shared GPU cluster is a fundamentally different problem than classic CPU cluster scheduling (Borg/Kubernetes): jobs are long-running, gang-scheduled (all-or-nothing across many GPUs), have predictable per-iteration timing that can be exploited, and GPUs are far more expensive and often underutilized than CPU cores.

## Core Principles
- Gang scheduling: a distributed training job needs all its GPUs to start together (and stay together) — partial allocation is often useless, unlike typical stateless microservice scheduling, which makes bin-packing and preemption much harder.
- DL job predictability is a schedulable resource: many training jobs have highly regular per-iteration time, which schedulers like Gandiva exploit for fine-grained time-slicing, suspend-resume, and migration that a generic scheduler couldn't safely do.
- "Goodput" (useful training progress per unit time), not raw GPU utilization, is the metric that actually matters — Pollux showed that jointly co-adapting resource allocation and training hyperparameters (batch size, learning rate) beats optimizing either alone.
- Fairness in a shared multi-tenant GPU cluster needs an explicit definition and mechanism (Themis's finish-time fairness, auction-based allocation) — GPUs are scarce and expensive enough that "first come first served" or naive round-robin leads to real user complaints and wasted spend.
- GPU sharing (time-slicing, MPS, MIG hardware partitioning) matters because many inference and small-training workloads don't need a full GPU — packing multiple jobs onto one device (AntMan, Salus, MISO) raises utilization but requires careful isolation to avoid interference.

## When to Use / When Not
- A dedicated, sophisticated ML-aware scheduler earns its complexity once you're running many concurrent training/inference jobs from multiple teams on shared GPU capacity — below that scale, simple static allocation is fine.
- Heterogeneity-aware scheduling (Gavel, Sia) matters once your cluster has a mix of GPU generations; on a homogeneous cluster it's unnecessary complexity.
- GPU sharing/fractional allocation is worth it for inference and small/interactive jobs, but rarely for large distributed training jobs that already saturate a GPU's memory and compute.

## Tradeoffs
- Utilization vs isolation: packing more jobs per GPU raises utilization but risks memory contention and unpredictable latency for co-located jobs, especially for latency-sensitive inference sharing a GPU with a training job.
- Fairness vs throughput: strict fairness guarantees can leave the cluster underutilized when demand is uneven; throughput-optimized scheduling can starve smaller/lower-priority tenants.
- Scheduling sophistication vs operational complexity: goodput-aware, elastic, heterogeneity-aware schedulers deliver real efficiency gains but are genuinely hard to operate, debug, and reason about compared to a simple priority queue.

## Common Patterns & Techniques
- Elastic training: a job that can grow or shrink its GPU allocation mid-run in response to cluster pressure (Pollux, Sia) instead of requiring a fixed reservation for its whole lifetime.
- Preemption + fast checkpoint/resume so higher-priority jobs can reclaim GPUs from lower-priority ones without losing significant progress.
- Locality-aware placement: co-locating a job's GPUs on the same rack/node group to minimize cross-node communication latency for tensor/pipeline-parallel training.
- Spot/preemptible-instance-tolerant scheduling (Bamboo, Varuna) that assumes capacity can be reclaimed at any time and designs the job around that.

## Pitfalls
- Scheduling ML jobs with a generic Kubernetes scheduler that doesn't understand gang semantics, leading to partial allocations that waste GPU-hours while a job waits for the rest of its gang.
- Measuring cluster health by GPU utilization alone, which can be high while goodput (useful training progress) is low due to poor batch-size/resource matching.
- Ignoring interference when co-locating jobs on shared GPUs (via MPS/MIG) without validating that latency-sensitive workloads stay within SLO under contention.

## Real-World Examples
- Google's Borg (and its Kubernetes-lineage successors) established production cluster-scheduling patterns that ML-specific schedulers like Gandiva and Pollux extend for gang scheduling and goodput optimization.
- Microsoft's Philly cluster study (analysis of large-scale multi-tenant GPU clusters) is the landmark production-trace paper documenting real failure/locality/scheduling characteristics at scale.
- Alibaba's AntMan dynamically shares GPU memory and compute across co-located deep learning jobs in production.
