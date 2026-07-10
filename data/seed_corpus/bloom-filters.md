# Bloom Filters

## Summary
A Bloom filter is a probabilistic data structure that tests set membership using a fixed-size bit array and multiple hash functions, answering "definitely not present" or "possibly present" with no false negatives, trading exactness for large space savings.

## Core Principles
- A Bloom filter is a bit array of size m with k hash functions; inserting sets k bits (hash(x) mod m); querying checks whether all k bits are set.
- False positives are possible (hash bits overlap between elements) but false negatives are impossible — an unset bit proves the element was never inserted.
- The false-positive rate depends on m, count n, and k; optimal k ≈ (m/n)·ln(2), sized against a target FP rate (e.g., 1%).
- Standard Bloom filters cannot delete elements (unsetting a bit could affect another element) — Counting Bloom Filters use small counters to support deletion.
- Count-Min Sketch estimates item frequency via a 2D counter; collisions cause overestimation, never underestimation. HyperLogLog estimates cardinality via bit-pattern counting in log space, ~1-2% error.

## When to Use / When Not
- Use Bloom filters for fast, memory-efficient "might exist" checks before an expensive lookup (disk read, network call, DB query) when small false positives are ok.
- Use Count-Min Sketch for approximate frequency counting over high-cardinality streams (top-K, heavy hitters) when exact counts are infeasible.
- Use HyperLogLog for approximate distinct-count estimation (unique visitors, IPs) when exact counting needs prohibitive memory.
- Avoid these when exact answers are required (financial counts, security allow-lists needing zero false positives).

## Tradeoffs
- Space vs accuracy: smaller sketches save memory but raise error rates; sizing must match expected cardinality, or Bloom filters degrade past capacity.
- Bloom filters trade a bounded false-positive cost for avoiding expensive negative lookups entirely.
- HyperLogLog trades exactness for O(log log n) space, enabling billion-scale cardinality estimation in kilobytes.

## Common Patterns & Techniques
- LSM-tree engines (RocksDB, Cassandra, LevelDB) attach a Bloom filter per SSTable to skip disk reads for absent keys.
- CDNs and browsers use Bloom filters for malicious-URL checks (e.g., Google Safe Browsing).
- Redis implements HyperLogLog natively (PFADD/PFCOUNT) for cheap unique counting.

## Pitfalls
- Undersizing the filter for actual data volume, spiking the false-positive rate above target.
- Assuming Bloom filters support deletion without switching to a counting variant.
- Using HyperLogLog for small cardinalities where its relative error costs more than exact counting would.

## Real-World Examples
- Cassandra and RocksDB use per-SSTable Bloom filters to avoid unnecessary disk seeks on read.
- Google Chrome originally used a Bloom filter for the Safe Browsing malicious-URL blocklist.
- Redis HyperLogLog powers approximate unique-visitor counters in analytics pipelines at companies like Reddit.
