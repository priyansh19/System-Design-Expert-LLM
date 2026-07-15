# Vector Databases & Approximate Nearest Neighbor Search

## Summary
A vector database stores high-dimensional embeddings and answers "find the k most similar vectors to this query" fast at billion-scale — exact nearest-neighbor search is too slow at scale, so every production system trades a small, tunable amount of recall for large speedups via approximate nearest neighbor (ANN) indexing.

## Core Principles
- Graph-based indexes (HNSW — Hierarchical Navigable Small World) build a multi-layer proximity graph and greedily walk it toward the query vector; they give excellent recall/latency and are the default in-memory index in most production vector DBs (Milvus, Weaviate, Qdrant, pgvector).
- Disk-resident graph indexes (DiskANN/Vamana, SPANN) are built specifically so a single node with modest RAM can serve billion-vector search from SSD, avoiding the cost of holding the whole index in memory.
- Quantization (Product Quantization, and newer binary methods like RaBitQ) compresses each vector into a small code, cutting memory footprint 10-30x at some recall cost — essential once the raw vector count no longer fits in RAM.
- Index freshness is a hard systems problem: graph/quantized indexes are expensive to rebuild; incremental in-place update techniques (SPFresh) exist specifically because naive "rebuild on every insert" doesn't scale for live, constantly-updated corpora (e.g. a RAG knowledge base).
- Hybrid queries (vector similarity + structured filters, e.g. "similar products AND in stock") need index-aware filtering, not a post-filter on top-k results, or recall collapses when the filter is selective (VBASE's "relaxed monotonicity" is one systems answer to this).

## When to Use / When Not
- Use a dedicated vector DB or ANN index when similarity search is a first-class, high-QPS query path (semantic search, RAG retrieval, recommendation candidate generation) over more than a few hundred thousand vectors.
- Below that scale, or for infrequent/offline queries, exact brute-force search (or a simple in-memory FAISS flat index) is simpler, has perfect recall, and avoids operating a new distributed system.
- Avoid bolting vector search onto a general-purpose relational DB without checking its ANN index maturity — filter-heavy hybrid queries and update-heavy workloads expose real correctness/performance gaps in early implementations.

## Tradeoffs
- Recall vs latency/memory: every ANN method (graph depth, PQ bits, IVF cluster count) has a tunable knob trading search accuracy for speed and footprint — there is no free lunch, only where you sit on the curve.
- Build/update cost vs query speed: highly optimized static indexes (well-tuned HNSW, DiskANN) are expensive to rebuild, which conflicts with corpora that mutate constantly.
- Single-node simplicity vs distributed scale: a well-tuned single machine (DiskANN-style) can serve a billion vectors cheaply; going distributed (Milvus, HARMONY) adds real operational complexity and is only worth it past that scale or for multi-tenant isolation needs.

## Common Patterns & Techniques
- IVF (inverted file index): cluster vectors, restrict search to the nearest few clusters — often combined with PQ (IVFPQ) as the classic FAISS building block.
- Two-stage retrieval: a cheap, high-recall ANN pass to get a candidate set, followed by exact re-ranking on the (small) candidate set for precision.
- Sharding by cluster/partition for horizontal scale, mirroring classic partitioning strategies from relational systems.
- Serverless/elastic vector search (Vexless) to handle bursty query load without paying for idle capacity.

## Pitfalls
- Benchmarking recall/latency only at low concurrency, then discovering the index degrades badly under real production QPS and concurrent writes.
- Choosing embedding dimensionality without considering its multiplicative effect on both index memory and query latency.
- Rebuilding the entire index for small incremental updates instead of using an update-aware index design, causing serving gaps or stale results.

## Real-World Examples
- FAISS (Meta) is the ubiquitous GPU-accelerated ANN library underlying many custom and off-the-shelf vector search stacks.
- Milvus (Zilliz) is a purpose-built, horizontally-scalable distributed vector database used widely for production RAG and search systems.
- Google's ScaNN powers large-scale embedding retrieval across Google's own products via anisotropic vector quantization tuned for inner-product search.
