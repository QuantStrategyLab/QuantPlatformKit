# QPK-N2 descriptor-relative store

This fresh reslice is local-only and consumes only the merged N1 vNext contract.
It opens and traverses every path component relative to verified directory file
descriptors with `O_NOFOLLOW`; pathname `resolve()` checks are not used as a
security boundary. Missing directories are created one segment at a time and
new ancestor descriptors are fsynced. Payload files are fsynced and installed
with create-only linking, preserving write-once/idempotent semantics under
concurrency. Selector listing decodes every candidate before returning it.

The store accepts durable records only, rejects ephemeral before filesystem I/O,
has exact reads and explicit selector listing, and defers latest. Legacy paths,
network/S3, callers, orchestrators, exporters, and live behavior are excluded.
