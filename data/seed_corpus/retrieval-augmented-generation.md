# Retrieval-Augmented Generation (RAG) Architecture

## Summary
RAG grounds an LLM's answer in retrieved external documents rather than relying solely on knowledge baked into its weights — it trades a training-time knowledge problem for a runtime systems problem: retrieve the right passages, fast, and feed them to the generator without blowing the latency or cost budget.

## Core Principles
- The canonical architecture (Lewis et al.'s original RAG paper) is a dense retriever (encodes query + corpus into the same vector space, e.g. DPR) plus a generator (seq2seq/LLM) conditioned on the top-k retrieved passages — parametric memory (model weights) plus non-parametric memory (an updatable external index).
- Retrieval quality bounds generation quality: a generator cannot answer correctly from irrelevant or missing context, so retriever recall/precision is usually the highest-leverage place to invest, not the generator's prompt.
- Fixed top-k retrieval every step is wasteful and sometimes harmful; adaptive/on-demand retrieval (Self-RAG) lets the model decide when retrieval actually helps versus when it should just answer from parametric knowledge.
- Retrieval and generation are naturally sequential, adding latency; systems-level optimizations pipeline them (PipeRAG), speculate ahead (Speculative RAG), or reuse cached retrieved-document computation across queries (RAGCache) to hide or amortize that cost.
- Index freshness and update latency matter as much as retrieval accuracy for any live corpus — RAG serving is inseparable from the vector-database update/freshness problem.

## When to Use / When Not
- Use RAG when answers must cite/ground in a specific, changing, or proprietary corpus (internal docs, recent events, licensed content) that can't or shouldn't be baked into model weights.
- Skip RAG (or keep it minimal) for tasks that are purely reasoning/generation over user-provided context, or where the required knowledge is stable, general, and already well-represented in the base model.
- Don't reach for RAG to fix a model that's bad at instruction-following or reasoning — retrieval only helps with a knowledge gap, not a capability gap.

## Tradeoffs
- Latency vs grounding quality: more retrieved passages and reranking passes improve grounding but add real wall-clock time and token cost per request.
- Freshness vs index cost: near-real-time index updates are expensive to maintain at scale; most systems accept some staleness bound instead.
- Precision vs recall in retrieval: casting a wide net (high k) risks diluting the generator's context with irrelevant passages ("lost in the middle"); too narrow risks missing the answer entirely.

## Common Patterns & Techniques
- Hybrid retrieval: combine sparse (BM25) and dense (embedding) retrieval, since each catches failure modes the other misses (exact keyword/entity matches vs semantic similarity).
- Reranking: a cheap first-pass retriever over-fetches candidates, then a more expensive cross-encoder reranker picks the final top-k for the generator.
- Chunking strategy (fixed-size, semantic, heading-scoped) materially affects retrieval quality — too-large chunks dilute relevance signal, too-small chunks lose context.
- Query rewriting/expansion before retrieval to bridge the gap between a user's phrasing and the corpus's vocabulary.

## Pitfalls
- Treating RAG as a solved, static pipeline instead of monitoring retrieval hit rate and generation faithfulness separately — a RAG system can fail silently by retrieving well but still hallucinating past the context.
- Ignoring retrieval latency in the end-to-end SLO budget, then being surprised when adding RAG doubles response time.
- Chunking documents without preserving enough surrounding context (headings, section boundaries) for the retrieved passage to be self-contained and useful to the generator.

## Real-World Examples
- Enterprise "chat with your docs" products are almost universally RAG: dense retrieval over an internal knowledge base feeding a general-purpose LLM.
- Perplexity and similar answer engines combine live web retrieval with LLM synthesis and citation, a RAG variant optimized for freshness over a static corpus.
- This project's own data-generation pipeline is a RAG-adjacent pattern: teacher-model answers are grounded in BM25-retrieved passages from a curated corpus and research papers before being written into training data.
