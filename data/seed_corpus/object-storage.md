# Object Storage

## Summary
Object storage systems like Amazon S3 and Google Cloud Storage store immutable blobs with metadata under flat keys inside buckets, offering near-limitless scale and extreme durability at the cost of higher, less predictable latency than block or file storage.

## Core Principles
- Objects are opaque byte blobs plus metadata, addressed by a key within a bucket — no native hierarchical filesystem, though key prefixes simulate directories.
- Durability is engineered via erasure coding/replication across zones; S3 Standard advertises 11 nines annual durability, distinct from availability (99.99% SLA), which measures uptime.
- Objects are immutable: updating means writing a new version (if versioning is enabled) — simplifying caching and replication (S3 is strongly read-after-write consistent as of 2020).
- Presigned URLs let a client upload/download directly to/from the bucket via a time-limited signed URL, avoiding proxying large payloads through application servers.
- Lifecycle policies automatically transition objects between tiers (S3 Standard → Infrequent Access → Glacier) or expire them, trading retrieval latency for storage cost.

## When to Use / When Not
- Use it for large, infrequently-modified assets: media, backups, data lake files, logs, static assets, ML datasets.
- Avoid it for low-latency random-access or frequent small updates — use a database or block storage (EBS) instead.
- Avoid it for POSIX filesystem semantics (in-place append, file locking) — use a network filesystem (EFS) instead.

## Tradeoffs
- Cost vs retrieval latency: colder tiers (Glacier Deep Archive) are far cheaper per GB but incur retrieval delays of minutes to hours.
- Durability vs consistency: multi-region replication boosts durability but adds cross-region propagation delay.
- Simplicity vs control: presigned URLs offload bandwidth from app servers but reduce ability to validate content pre-upload.

## Common Patterns & Techniques
- Presigned upload flow: client requests a signed URL from the API, uploads directly to the bucket, backend confirms via an object-created event.
- CDN fronting (CloudFront, Cloud CDN) for read-heavy public objects, cutting latency and offloading the origin.
- Multipart upload for large files, parallelizing and resuming interrupted transfers.
- Event-driven pipelines: object-created events trigger downstream processing (thumbnailing, virus scanning, ETL).

## Pitfalls
- Using object storage as a queue or database, causing listing/consistency problems at scale.
- Public bucket misconfiguration is a leading root cause of cloud data breaches.
- Ignoring hot key-prefix throttling on stores that still partition by key range.

## Real-World Examples
- Netflix stores and serves petabytes of encoded video from S3, fronted by its own CDN (Open Connect).
- Dropbox originally built on S3 before migrating storage in-house (Magic Pocket) for cost control at scale.
- Data lakes (Snowflake, Databricks) use S3/GCS as the durable storage layer beneath compute-separated query engines.
