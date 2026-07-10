# SystemDesignExpertLLM — Design Spec

**Date:** 2026-07-11
**Status:** Draft (pending user review)

## 1. Goal

Fine-tune an open 7–8B LLM into a **best-in-class architecture advisor for real systems**: given a real requirement, it produces concrete architecture recommendations, technology choices, and rigorous tradeoff analysis at the level of a senior/staff engineer. Not an interview-trivia bot; a practical design advisor.

"Best-in-class" is defined operationally in §5: measured by LLM-as-judge, the fine-tune must clearly beat its base model and close most of the quality gap to a strong frontier API model on a held-out rubric.

## 2. Constraints (locked)

- **Compute:** Kaggle free GPU only — single P100 (16GB) preferred, or 2×T4. ~30 GPU-hrs/week, 12h max per session.
- **Data strategy:** Hybrid — curated seed corpus + synthetic expansion.
- **Teacher model:** Paid API, DeepSeek-V3 (cheap, strong technical reasoning). Estimated total cost ~$3–8.
- **Evaluation:** LLM-as-judge vs baselines.
- **Delivery:** Both GGUF (local Ollama) and Hugging Face repo (adapter + merged weights).

## 3. Approach

Chosen training strategy: **SFT baseline → DPO quality lift**.

- SFT (QLoRA) produces a working end-to-end model early (de-risks the pipeline).
- A lightweight DPO pass then pushes tradeoff-depth and reasoning quality toward the judge rubric.
- Continued/domain-adaptive pretraining was considered and **rejected**: low ROI for 7–8B on Kaggle free tier at this data scale.

## 4. Architecture

### 4.1 Base model & method

- **Base:** `Qwen2.5-7B-Instruct` — strongest 7B for technical/structured reasoning, 32k context, Apache-2.0, strong Unsloth support. Fallback: `Llama-3.1-8B-Instruct`.
- **Method:** QLoRA (4-bit NF4) via Unsloth. LoRA rank 16–32, alpha 32, dropout 0.05, targeting all attention + MLP projection layers.
- **Kaggle fit:** single-GPU. Checkpoint to a Kaggle Dataset every N steps; resume across sessions so a 12h cutoff never loses progress.

### 4.2 Data pipeline

```
seed corpus (curated MD)
  -> scenario generator (DeepSeek): diverse real requirements
  -> answer generator (DeepSeek): senior-level, corpus-grounded, fixed structure
  -> quality filter + dedup (schema, length, embedding-dedup, judge filter)
  -> SFT set (instruction -> answer JSONL)
  -> DPO pair builder (chosen = teacher, rejected = base-model answer)
```

- **Seed corpus:** ~40–60 curated markdown topic notes (caching, sharding, CAP/PACELC, queues, consistency models, load balancing, CDNs, data stores, observability, rate limiting, idempotency, etc.). Provides factual grounding so synthetic answers cite real principles, not hallucinations. Doubles as a future RAG knowledge base.
- **Scenario generation:** DeepSeek generates diverse real requirements varied by domain, scale, and constraint. Target ~5–10k SFT pairs.
- **Answer format (fixed structure):** requirements clarification -> high-level architecture -> component choices with tradeoffs -> data model -> scaling & failure modes -> bottleneck analysis.
- **Quality control:** JSON schema validation, min/max length gates, embedding-similarity dedup, judge-based filter dropping low-scoring pairs.
- **DPO pairs:** ~800–1500. "chosen" = teacher answer; "rejected" = base Qwen answer to the same prompt.

### 4.3 Training config

- **SFT:** 2–3 epochs, effective batch ~16 (grad accum), lr 2e-4 cosine, 5% warmup, max_seq 4096, sequence packing on, bf16/fp16.
- **DPO:** load SFT adapter, beta 0.1, lr 5e-6, 1 epoch. Short run.
- **Artifacts:** per-stage LoRA adapters + merged fp16 weights.

## 5. Evaluation harness

- **Held-out set:** ~50–80 architecture prompts not present in training, spanning domains and scales.
- **Judge:** DeepSeek (or GPT-4o) scores each answer 1–10 on a rubric: correctness, tradeoff depth, completeness, feasibility, clarity.
- **Baselines:** (a) base Qwen2.5-7B, (b) our fine-tune, (c) a strong frontier API model as reference ceiling.
- **Report:** per-dimension mean scores + comparison table. Success = fine-tune clearly beats base and closes most of the gap to the API ceiling.
- **Bias controls:** fixed rubric prompt, randomized answer order, human spot-check of a sample.

## 6. Deployment

- **GGUF:** merge adapter -> convert via llama.cpp -> quantize q4_K_M + q8_0 -> `Modelfile` (system prompt + chat template) -> `ollama create system-design-expert`.
- **HF:** push LoRA adapter repo + merged-weights repo with a model card documenting data, eval scores, and usage.

## 7. Repo structure

```
SystemDesignExpertLLM/
  data/            seed_corpus/*.md, generated/*.jsonl
  scripts/         gen_scenarios.py, gen_answers.py, build_dpo.py, quality_filter.py
  notebooks/       kaggle_sft.ipynb, kaggle_dpo.ipynb
  eval/            prompts.jsonl, judge.py, report.py
  deploy/          Modelfile, convert_gguf.sh, push_hf.py
  configs/         sft.yaml, dpo.yaml
  pyproject.toml, README.md
```

## 8. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Kaggle 12h session cutoff | Checkpoint + resume via Kaggle Dataset |
| Teacher hallucination | Seed-corpus grounding + judge-based filter |
| DeepSeek API cost | Capped; ~$3–8 est. for 10k pairs |
| Judge bias | Randomized order, fixed rubric, human spot-check |
| Single-GPU memory limits | QLoRA 4-bit + Unsloth + max_seq 4096 + packing |

## 9. Out of scope (v1)

- Multi-GPU / distributed training.
- Continued pretraining.
- RAG at inference (corpus is reserved for it but not wired in v1).
- Diagram-image generation (text/mermaid only).
