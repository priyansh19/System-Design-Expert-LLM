# SystemDesignExpertLLM

Fine-tune an open 7–8B LLM into a **best-in-class architecture advisor for real systems** —
given a real requirement, it produces concrete architecture recommendations, technology
choices, and rigorous tradeoff analysis at a senior/staff-engineer level.

Design spec: [`docs/superpowers/specs/2026-07-11-system-design-expert-llm-design.md`](docs/superpowers/specs/2026-07-11-system-design-expert-llm-design.md)

## Pipeline

```
seed corpus (curated markdown)                data/seed_corpus/*.md
   -> gen_scenarios.py   (teacher: DeepSeek)  -> scenarios.jsonl
   -> gen_answers.py     (teacher, grounded)  -> sft_raw.jsonl
   -> quality_filter.py  (gates + dedup)      -> sft.jsonl
   -> build_dpo.py       (base = Ollama)      -> dpo.jsonl
   -> notebooks/kaggle_sft.ipynb  (QLoRA SFT)
   -> notebooks/kaggle_dpo.ipynb  (DPO refine)
   -> eval/ (LLM-as-judge vs baselines)
   -> deploy/ (GGUF for Ollama + Hugging Face)
```

## Setup

```bash
uv venv --python 3.12
uv pip install -e .
cp .env.example .env      # then fill in DEEPSEEK_API_KEY (teacher)
```

Providers are OpenAI-compatible and selected via env:
- **Teacher** (`TEACHER_PROVIDER`, default `deepseek`) — generates scenarios + answers.
- **Base** (`BASE_PROVIDER`, default `ollama`) — produces DPO "rejected" answers locally.
- **Judge** (`JUDGE_PROVIDER`, default `openai`) — must be a *different family* than the teacher.

## Data collection

```bash
# 1. Generate scenarios (grounded in the seed corpus topic index)
python scripts/gen_scenarios.py --n 500

# 2. Generate structured, grounded answers
python scripts/gen_answers.py

# 3. Filter: structure + length gates, then embedding dedup
python scripts/quality_filter.py

# 4. Build DPO preference pairs (chosen=teacher, rejected=base model)
python scripts/build_dpo.py --n 1200
```

Outputs land in `data/generated/` (gitignored). The seed corpus in `data/seed_corpus/` **is**
tracked — it is the factual grounding and doubles as a future RAG knowledge base.

## Training

Training runs on **Kaggle free GPU** (single P100/T4) via QLoRA + Unsloth. See `configs/sft.yaml`
and `configs/dpo.yaml`, driven by the notebooks in `notebooks/`. Checkpoints are written
frequently so a 12h Kaggle session cutoff never loses progress.

## Layout

```
data/seed_corpus/   curated topic notes (tracked)
data/generated/     synthetic datasets (gitignored)
src/sdx/            config, provider-agnostic LLM client, schemas, corpus io
scripts/            data-collection pipeline
configs/            sft.yaml, dpo.yaml
notebooks/          Kaggle SFT + DPO
eval/               held-out prompts, judge, report
deploy/             GGUF conversion + HF push
```
