# Large File Storage & Chunking

## Summary
Storing and syncing large files efficiently requires splitting them into chunks, enabling deduplication, resumable transfer, and parallelism — the foundation behind Dropbox-style sync and multipart APIs like S3.

## Core Principles
- Chunking splits a file into fixed-size or content-defined blocks (e.g., 4–8MB) so upload operates on parallelizable units instead of one blob.
- Content-addressed storage: each chunk is identified by the hash (SHA-256) of its content, so identical chunks across files are stored once — the basis of dedup.
- Content-defined chunking (rolling hash) picks boundaries based on content, so inserting a byte near the start doesn't shift every boundary and break dedup.
- Resumable upload: the client tracks acknowledged chunks and only retransmits missing ones after a disconnect, avoiding a full restart.
- A manifest (file → ordered chunk hashes) reassembles the original file; only the manifest changes on a small edit, not the unchanged chunks.

## When to Use / When Not
- Use chunking for large file sync/backup, media platforms, and uploads where files exceed tens of MBs or the network is unreliable (mobile).
- Use content-defined chunking when files are frequently edited and re-uploaded (documents, VM images) to maximize dedup savings.
- Avoid the overhead for small files well under the chunk size — manifest cost outweighs the benefit.

## Tradeoffs
- Smaller chunks improve dedup granularity and resumability vs increase metadata volume and per-chunk overhead.
- Content-defined chunking maximizes dedup across edits vs costs more CPU than fixed-size chunking.
- Client-side hashing enables end-to-end dedup and integrity checks vs adds CPU/battery cost on mobile.

## Common Patterns & Techniques
- Rolling hash (Rabin-Karp style) for content-defined boundaries, used in rsync and Dropbox's block-splitting algorithm.
- S3 Multipart Upload: parts uploaded independently, each returning an ETag, then `CompleteMultipartUpload` assembles them.
- Merkle-tree-style manifests verify whole-file integrity from chunk hashes without re-downloading everything.
- Delta sync: after an edit, only re-upload chunks that actually changed (hash mismatch against the prior manifest).

## Pitfalls
- Pure fixed-size chunking on frequently-edited files, where one inserted byte shifts every downstream boundary and destroys dedup.
- Not verifying chunk integrity before commit, letting silent corruption from a flaky network reach stored data.
- Leaving orphaned, uncommitted multipart uploads unmanaged, accumulating storage cost without a garbage-collection policy.

## Real-World Examples
- Dropbox's sync engine chunks files into ~4MB blocks, hashes them client-side, and only uploads blocks the server lacks.
- Amazon S3 Multipart Upload lets clients upload objects over 100MB (required above 5GB) as independently retryable, parallel parts.
- Git uses content-addressed, hash-identified objects — the same dedup principle — to avoid storing duplicate blobs across commits.
</content>
<parameter name="i">Rewrite large-file-storage-chunking tighter