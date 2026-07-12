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
cp .env.example .env      # set TEACHER_PROVIDER (claude = no key; or add DEEPSEEK_API_KEY)
```

Providers are OpenAI-compatible (or the local `claude` CLI) and selected via env:
- **Teacher** (`TEACHER_PROVIDER`) — generates scenarios + answers. Options: `claude`
  (local Claude Code CLI, no API key — auth via the logged-in CLI), `deepseek`, `xai`, `openai`.
- **Base** (`BASE_PROVIDER`, default `ollama`) — produces DPO "rejected" answers locally.
- **Judge** (`JUDGE_PROVIDER`, default `openai`) — must be a *different family* than the teacher.

## Grounding sources

The teacher answers are grounded in two pools so recommendations trace back to primary sources:

```bash
# GitHub references (system-design-primer, ByteByteGo 101, karanpratapsingh) -> 431 chunks
python scripts/ingest_sources.py

# 29 canonical research papers (Dynamo, GFS, Bigtable, Spanner, Raft, Paxos, ZooKeeper,
# MapReduce, Dataflow, Kafka, Memcache, TAO, Dapper, Borg, Consistent Hashing, ...) -> ~1.5k chunks
python scripts/ingest_papers.py
```

Both write heading-scoped `{source, heading, text, words}` chunks into
`data/generated/grounding.jsonl` (BM25-retrievable). `ingest_papers.py` caches PDFs under
`data/sources/papers/` and is idempotent (re-running replaces only `paper:*` rows).

## Data collection

```bash
# One shot: N rounds of (scenarios -> answers -> gates), accumulate, dedup, then DPO.
# Resumable — re-running loads the existing sft.jsonl and adds more rounds.
python scripts/run_pipeline.py --rounds 15 --per-round 20 --dpo 1200
```

Or run each stage manually:

```bash
python scripts/gen_scenarios.py --n 500   # scenarios grounded in the seed corpus topic index
python scripts/gen_answers.py             # structured, grounded answers
python scripts/quality_filter.py          # structure + length gates, then embedding dedup
python scripts/build_dpo.py --n 1200      # preference pairs (chosen=teacher, rejected=base)
```

Outputs land in `data/generated/` (gitignored): `sft.jsonl` (`instruction`/`output`) and
`dpo.jsonl` (`prompt`/`chosen`/`rejected`). The seed corpus in `data/seed_corpus/` **is**
tracked — it is the factual grounding and doubles as a future RAG knowledge base.

## Package for Kaggle

```bash
python scripts/prepare_kaggle_dataset.py --user YOUR_KAGGLE_USERNAME --slug sdx-dataset
kaggle datasets create -p data/kaggle_upload --dir-mode zip
```

Bundles `sft.jsonl` + `dpo.jsonl` into one dataset. The notebooks read them from
`/kaggle/input/sdx-dataset/{sft,dpo}.jsonl` (keep the `sdx-dataset` slug, or update the
`SFT_PATH`/`DPO_PATH` cells to match).

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
