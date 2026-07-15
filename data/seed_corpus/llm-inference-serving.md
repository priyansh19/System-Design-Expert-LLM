# LLM Inference Serving

## Summary
Serving a large language model means turning a GPU-resident set of weights into a low-latency, high-throughput API — the hard part isn't the model, it's scheduling many concurrent, variable-length generation requests over a scarce, expensive resource (GPU memory + compute) without wasting either.

## Core Principles
- Autoregressive decoding is inherently sequential and memory-bound: each new token requires a full forward pass, and the KV cache (attention keys/values for every prior token) grows linearly with sequence length and must stay resident in GPU memory for the entire generation.
- Continuous (iteration-level) batching inserts new requests into a running batch as soon as any request finishes, instead of waiting for a static batch to fully complete — this is the single biggest throughput lever over naive request-level batching (Orca, OSDI'22).
- PagedAttention (vLLM) manages the KV cache like OS virtual memory: fixed-size non-contiguous "pages" instead of one contiguous pre-allocated buffer per request, eliminating internal fragmentation and enabling near-100% memory utilization plus cheap KV-cache sharing across requests with a common prefix.
- Prefill (processing the input prompt, compute-bound, parallel) and decode (generating tokens one at a time, memory-bandwidth-bound) have opposite resource profiles; mixing them in one batch causes decode requests to stall behind long prefills unless explicitly chunked/scheduled (Sarathi-Serve) or physically disaggregated onto separate GPU pools (DistServe, Splitwise, Mooncake).
- Speculative decoding uses a small/cheap draft model (or extra decode heads) to propose several tokens, then verifies them all in one parallel forward pass with the target model — a systems-level latency win when acceptance rate is high, since it's still exact (not approximate) generation.

## When to Use / When Not
- Purpose-built serving engines (vLLM, TensorRT-LLM, SGLang, TGI) are the default for anything beyond a single-user demo — they implement continuous batching and KV-cache management you should not hand-roll.
- A naive request-per-GPU or static-batch approach is fine only for very low, predictable QPS or offline/batch scoring workloads where latency doesn't matter.
- Disaggregated prefill/decode pays off at scale (multiple GPUs, mixed short/long requests with strict TTFT and TPOT SLOs); it's overkill and adds operational complexity for a single-GPU deployment.

## Tradeoffs
- Throughput vs latency: larger batches and higher KV-cache utilization raise throughput but increase per-request queueing/interference; SLO-aware schedulers (Sarathi-Serve, Clockwork) trade some throughput to bound tail latency.
- Memory for KV-cache vs memory for model weights/activations: more cache headroom means more concurrent requests, but quantizing or evicting cache (H2O, StreamingLLM's attention sinks) trades a small quality risk for much better memory efficiency.
- Multi-tenant fairness vs raw utilization: naive continuous batching can starve low-priority tenants; explicit fairness schedulers (Virtual Token Counter/VTC) trade some aggregate throughput for guaranteed per-tenant service.

## Common Patterns & Techniques
- Prefix caching / automatic KV-cache reuse across requests sharing a system prompt or few-shot prefix (RadixAttention in SGLang) — huge win for agentic/RAG workloads with repeated context.
- Multi-LoRA serving (S-LoRA, Punica): one base-model copy in memory, thousands of small adapter deltas swapped per-request, instead of one full model copy per fine-tune.
- Multi-query / grouped-query attention reduces KV-cache size per token by sharing key/value heads across query heads — a model-level change that directly cuts serving memory pressure.
- Live request/KV-cache migration across replicas (Llumnix) for load balancing and defragmentation without dropping in-flight generations.

## Pitfalls
- Sizing GPU memory only for model weights and forgetting KV-cache headroom — the cache, not the weights, is usually what limits concurrent request count at long context lengths.
- Treating prefill and decode as the same workload when scheduling, causing long-prompt requests to blow up p99 latency for everyone else in the batch.
- Ignoring that speculative decoding's benefit collapses (or turns negative) when the draft model's acceptance rate is low — it needs monitoring, not a one-time setup.

## Real-World Examples
- vLLM (PagedAttention) is the de facto open-source serving engine baseline that most production and research systems now compare against.
- Moonshot AI's Mooncake disaggregates prefill/decode with a global KVCache scheduler across CPU/DRAM/SSD/RDMA at real production scale for Kimi.
- Microsoft Azure's Splitwise runs prefill and decode on heterogeneous GPU pools in production to cut cost per token.
