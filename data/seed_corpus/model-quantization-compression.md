# Model Quantization & Compression for Serving

## Summary
Quantization shrinks a model's numerical precision (e.g. 16-bit weights down to 4-bit) to cut memory footprint and often increase throughput, trading a small, usually-acceptable amount of output quality for the ability to serve much bigger models on much less hardware — a systems decision, not just a modeling trick.

## Core Principles
- Post-training quantization (PTQ) compresses an already-trained model without retraining, using a small calibration dataset — the practical default for serving large models, since full retraining-aware quantization is far more expensive.
- Weight-only quantization (GPTQ, AWQ) keeps activations in higher precision and only compresses weights, which is enough to shrink memory footprint and speed up the memory-bandwidth-bound decode phase of LLM inference, the actual bottleneck for most serving workloads.
- Activation quantization (SmoothQuant-style W8A8) is harder because activations have outlier values that don't compress cleanly; the systems fix is migrating quantization difficulty from activations to weights via an equivalent mathematical transform before quantizing both.
- Quantization error isn't uniform across weights — activation-aware methods (AWQ) explicitly protect the small fraction of weights that matter most for output quality instead of compressing everything equally.
- Quantization is a serving-cost lever independent of the model architecture decision: a 4-bit-quantized 70B model can fit and run faster on hardware that couldn't hold the 16-bit version at all, changing which hardware tier is even viable.

## When to Use / When Not
- Quantize aggressively for serving-cost-sensitive deployments (self-hosted inference, edge/on-device, high-QPS APIs) where the memory/throughput win outweighs a small, measured quality drop.
- Be more conservative (higher precision, or skip quantization) for tasks highly sensitive to numerical precision or where the model is already near a capability cliff — quantization-induced degradation isn't always linear or predictable across tasks.
- Training itself typically still needs higher precision (mixed FP16/BF16, or specific quantization-aware training techniques) — post-training quantization for serving is a separate concern from training-time numerics.

## Tradeoffs
- Compression ratio vs quality: lower bit-widths (4-bit vs 8-bit) save more memory but risk more quality degradation, especially compounded over long generation or complex reasoning tasks.
- Calibration effort vs robustness: quantization methods that use more calibration data / more sophisticated error correction (GPTQ's second-order approach) generally produce better-quality quantized models but take longer to prepare.
- Hardware-specific kernels vs portability: the best throughput wins usually require quantization formats with dedicated fast kernels (e.g. specific INT4 GEMM kernels) — a quantization scheme without hardware/kernel support may compress memory but not actually speed up inference.

## Common Patterns & Techniques
- Mixed-precision serving: keep a few precision-sensitive layers (e.g. the first/last layers) at higher precision while aggressively quantizing the rest.
- Quantize-and-validate pipelines: automated evaluation on a held-out task suite before promoting a quantized model to production, since quality loss isn't always visible from perplexity alone.
- Combine quantization with other serving optimizations (continuous batching, KV-cache paging) — the gains are largely independent and compound.

## Pitfalls
- Quantizing a model and shipping it without task-specific quality evaluation, catching degradation only after it affects users.
- Assuming a quantization method's published benchmark numbers transfer directly to a different model family or downstream task without re-validating.
- Choosing a quantization format with no efficient inference kernel for your target hardware, so the "compressed" model doesn't actually run faster in practice.

## Real-World Examples
- GPTQ enabled serving 175B-class models on a single GPU that previously required multiple GPUs at full precision.
- AWQ ships alongside the TinyChat runtime as a full systems pipeline (not just an algorithm) purpose-built for efficient on-device/edge LLM serving.
- Most production LLM serving stacks (vLLM, TensorRT-LLM) now support one or more of GPTQ/AWQ/INT8 quantization as a standard deployment option, not an experimental feature.
