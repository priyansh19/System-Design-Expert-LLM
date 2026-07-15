# Distributed Model Training Infrastructure

## Summary
Training a modern large model doesn't fit on one GPU's memory or compute budget, so the training job itself becomes a distributed system — the core design problem is splitting the model/data/optimizer state across thousands of accelerators while keeping them all fed and in sync, and recovering cheaply when (not if) hardware fails.

## Core Principles
- Data parallelism replicates the full model on every GPU and splits the batch across them, syncing gradients (all-reduce) each step — simple and the default first step, but every replica must hold a full copy of weights, gradients, and optimizer state.
- Tensor parallelism splits individual layers' matrix multiplications across GPUs (Megatron-LM); it needs very high-bandwidth interconnect (NVLink) since it requires communication inside every layer's forward/backward pass.
- Pipeline parallelism splits the model's layers across GPU stages and streams micro-batches through them (GPipe, PipeDream) — cheaper on interconnect than tensor parallelism, but introduces "bubble" (pipeline stall) overhead that micro-batching and careful scheduling must minimize.
- ZeRO (DeepSpeed) shards optimizer state, gradients, and optionally parameters across data-parallel ranks instead of replicating them, eliminating the redundant-memory problem of pure data parallelism without changing the model code — the standard technique behind PyTorch FSDP.
- At real scale (thousands of GPUs, weeks-long jobs), hardware failures are a certainty, not an edge case: frequent, low-overhead checkpointing (CheckFreq, Gemini, Check-N-Run) and fast failure detection/recovery (MegaScale, ByteRobust) are load-bearing infrastructure, not an afterthought.

## When to Use / When Not
- Data parallelism (plus ZeRO/FSDP sharding) alone is sufficient and simplest whenever the model fits in a single GPU's memory with room for activations — reach for tensor/pipeline parallelism only once it doesn't.
- Combine all three ("3D parallelism": data + tensor + pipeline) only at the scale where a single technique's overhead or memory ceiling becomes the bottleneck — it multiplies operational and debugging complexity.
- For cost-sensitive or opportunistic compute (spot/preemptible instances), fault-tolerant pipeline designs (Bamboo, Oobleck, Varuna) that tolerate node loss cheaply are worth the added complexity; for stable dedicated clusters they're often unnecessary.

## Tradeoffs
- Communication overhead vs memory savings: more aggressive sharding (ZeRO stage 3, full tensor parallelism) reduces per-GPU memory but increases cross-GPU communication, which can bottleneck throughput on lower-bandwidth interconnects.
- Checkpoint frequency vs training throughput: frequent checkpointing shrinks recovery time after a failure but steals GPU cycles and I/O bandwidth from the actual training step.
- Automatic parallelism-plan search (Alpa) vs hand-tuned configs: automatic search saves engineering time and can match hand-tuned performance, but is a black box that's harder to reason about and debug when something goes wrong.

## Common Patterns & Techniques
- Micro-batching + gradient accumulation to simulate a large effective batch size without holding it all in memory at once.
- Activation checkpointing/recomputation (recompute activations in the backward pass instead of storing them) trading compute for memory, refined by selective recomputation (only recompute the cheapest-to-recompute, most memory-hungry activations).
- Mixture-of-experts (MoE) sparsity (Switch Transformers, GShard): route each token to only a subset of "expert" sub-networks, scaling total parameter count without proportionally scaling compute per token.
- Elastic/preemption-tolerant training that can grow, shrink, or restart around available capacity instead of requiring a fixed, always-available GPU allocation.

## Pitfalls
- Under-provisioning checkpoint I/O bandwidth relative to cluster size, turning "fast" checkpointing into a throughput bottleneck at scale.
- Choosing a parallelism strategy based on model size alone without accounting for actual interconnect topology and bandwidth between nodes.
- Treating a training job as a single long-running process instead of designing for resumability from the start — a job that can't cheaply resume after a failure effectively has no fault tolerance.

## Real-World Examples
- Meta's Llama 3 herd of models paper documents production training infrastructure at 16K-H100 scale, including storage (Tectonic) and scheduling (MAST) design.
- ByteDance's MegaScale scales LLM training past 10,000 GPUs with full-stack co-design of algorithms, networking, and fault tolerance.
- Google's Pathways system orchestrates asynchronous distributed dataflow across thousands of TPU chips for training models like PaLM.
