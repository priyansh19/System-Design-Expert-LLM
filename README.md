# SystemDesignExpertLLM

Fine-tune an open 7–8B LLM into a **best-in-class architecture advisor for real systems** —
given a real requirement, it produces concrete architecture recommendations, technology
choices, and rigorous tradeoff analysis at a senior/staff-engineer level.

Design spec: [`docs/superpowers/specs/2026-07-11-system-design-expert-llm-design.md`](docs/superpowers/specs/2026-07-11-system-design-expert-llm-design.md)

## Pipeline

```
seed corpus (curated markdown)                data/seed_corpus/*.md
   -> gen_scenarios.py   (teacher: ornith)   -> scenarios.jsonl
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
cp .env.example .env      # defaults to TEACHER_PROVIDER=ornith (local, no key needed)
```

Providers are OpenAI-compatible (local Ollama models are OpenAI-compatible too, routed over
Ollama's native `/api/chat` under the hood) and selected via env:
- **Teacher** (`TEACHER_PROVIDER`) — generates scenarios + answers. Default: `ornith`
  (local Ollama model `ornith-nothink:9b`, no API key, no cost, but slow on CPU-only boxes —
  measured ~8 tok/s). `groq` (free, no card, `qwen/qwen3-32b`, ~400 tok/s, ~30 RPM/6K TPM/1K
  RPD) is a fast free upgrade, verified safe to train on per Groq's Services Agreement. Paid
  fallbacks if quality is insufficient: `deepseek`, `xai`, `openai`.
- **Base** (`BASE_PROVIDER`, default `ollama` / `qwen2.5:0.5b`) — produces DPO "rejected"
  answers locally; deliberately small+fast since it only needs to be worse, not diverse.
- **Judge** (`JUDGE_PROVIDER`, default `openai`) — must be a *different family* than the teacher.
  `nvidia` (free trial key, Llama-family) also works and is judge-ONLY: NVIDIA's trial ToS is
  "internal testing and evaluation, not production," so it's fine for scoring but must never be
  the teacher for data that trains the shipped model.

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

## Resuming on another machine (e.g. Mac Mini + MLX)

`grounding.jsonl`, the raw paper PDF cache (`data/sources/papers/`), and the raw HF dataset
cache (`data/sources/hf_datasets/`) are gitignored — multiple GB of derived/re-downloadable
data that doesn't belong in git history. Two ways to get them on a new machine:

**Rebuild from scratch (no transfer, just re-run the ingesters):**
```bash
python scripts/ingest_sources.py      # GitHub references
python scripts/ingest_papers.py       # re-downloads PDFs listed in data/sources/paper_list.json
python scripts/ingest_hf_dataset.py   # re-downloads ajibawa-2023/Software-Architecture from HF
python scripts/ingest_gh_repo.py      # design-gurus/grokking-system-design
```

**Or pull the prebuilt artifacts from the GitHub Release** (skips re-downloading/re-parsing
~1020 papers and an 819MB HF dataset):
```bash
gh release download data-v1 -p "*.gz" -p "papers.tar"
gunzip grounding.jsonl.gz && mv grounding.jsonl data/generated/
gunzip ajibawa-2023__Software-Architecture__Software_Architecture_Final.jsonl.gz \
  && mkdir -p data/sources/hf_datasets && mv ajibawa-2023*.jsonl data/sources/hf_datasets/
tar -xf papers.tar -C data/sources
```

Either way, `sft.jsonl` / `sft_cerebras.jsonl` / `dpo.jsonl` are already tracked in git (they're
the actual expensive-to-produce generated output, not derived cache), so `run_pipeline.py`
resumes from the existing pool immediately — recreate `.env` from `.env.example` (never
committed) and point `TEACHER_PROVIDER` at whatever's fastest locally (e.g. an MLX server
exposed as an OpenAI-compatible endpoint — point `ORNITH_BASE_URL`/`OLLAMA_BASE_URL` at it,
or add a new provider entry in `src/sdx/config.py`).

## Evaluation

Before spending Kaggle GPU-hours, score the pipeline's own output on a held-out set —
cheap, local (no key needed for generation), and it tells you whether a fix (grounding,
DPO format, domain coverage) actually moved quality, not just changed the code:

```bash
# 1. Build a held-out prompt set (deduped against data/generated/sft.jsonl so it never
#    overlaps training data, even if re-run later). Tracked in git -- stays fixed run to run.
python eval/make_prompts.py --n 60 --out eval/prompts.jsonl

# 2. Generate answers for whichever system(s) you want to compare.
python eval/generate.py --system teacher-grounded --provider ornith --mode grounded  # the actual pipeline
python eval/generate.py --system teacher-bare      --provider ornith --mode bare     # ablation: no grounding
python eval/generate.py --system base-bare          --provider ollama --mode bare     # sanity floor

# 3. Judge every eval/answers/*.jsonl (needs a paid or NVIDIA-trial key: JUDGE_PROVIDER
#    must differ from TEACHER_PROVIDER's family -- enforced, see .env.example).
python eval/judge.py --answers "eval/answers/*.jsonl"

# 4. Aggregate into a per-dimension comparison table.
python eval/report.py
```

`report.py` writes `eval/report.md`: a mean-score table (`correctness`, `tradeoff_depth`,
`completeness`, `feasibility`, `clarity`, `overall`) per system, ranked descending. Once
trained, re-run step 2 with `--provider finetune --mode bare` to add the fine-tune itself to
the comparison.

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
