# Search Indexing

## Summary
Full-text search systems like Elasticsearch and OpenSearch use an inverted index — mapping terms to documents containing them — to answer relevance-ranked queries far faster than scanning raw text, at the cost of index-build latency and near-real-time visibility.

## Core Principles
- An inverted index maps each unique token to a postings list of document IDs (and positions/frequencies), enabling fast term lookup instead of linear scans.
- Tokenization/analysis breaks text into terms: lowercasing, stemming, stop-word removal, n-gram generation — the analyzer at index time must match query time for correct matching.
- Relevance scoring ranks results with BM25 (the default), weighing term frequency in a document against term rarity across the corpus (IDF) with saturation and length normalization.
- Elasticsearch/OpenSearch are built on Apache Lucene, sharding the inverted index across nodes; each shard is a self-contained Lucene index, queried in parallel and merged by a coordinator.
- Near-real-time (NRT) search: writes go to an in-memory buffer and translog; a periodic refresh (default ~1s) makes them searchable, with the translog providing durability before segment flush.

## When to Use / When Not
- Use it for free-text search, faceted/filtered search, fuzzy matching, and relevance-ranked results (product search, log search, autocomplete).
- Avoid it as a system of record — it isn't ACID-transactional; keep a source-of-truth database and index into search as a derived view.
- Avoid it for simple exact-match key lookups where a plain KV/DB index is cheaper.

## Tradeoffs
- Indexing latency vs query speed: richer indexes (more fields, n-grams) speed queries but slow ingestion and grow storage.
- NRT freshness vs throughput: frequent refreshes tighten searchability latency but hurt indexing throughput via more segment merges.
- Precision vs recall: aggressive stemming/fuzzy matching raises recall but can hurt precision.

## Common Patterns & Techniques
- CDC pipelines (Debezium, Kafka Connect) keep the search index in sync with the primary database asynchronously.
- Segment merging/compaction (Lucene) controls read amplification from many small segments.
- Custom analyzers per field (keyword for exact filters, stemmed for free text) via multi-fields.
- Query-time boosting and function_score blend relevance with business signals (recency, popularity).

## Pitfalls
- Reindexing an entire large corpus after a mapping change, since field types are largely immutable once set.
- Over-sharding, adding coordination overhead and hurting relevance accuracy since term statistics are local per shard.
- Assuming strong consistency — reads immediately after write may miss results before the next refresh.

## Real-World Examples
- GitHub uses Elasticsearch for code and issue search across billions of documents.
- Wikipedia (via CirrusSearch) runs Elasticsearch backed by Lucene for full-text article search.
- Netflix and Uber use Elasticsearch/OpenSearch for log aggregation and operational search dashboards.
