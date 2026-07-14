# QPK-N2 SQLite exact foundation

This slice is a trusted single-process, stdlib-only durable foundation. The
constructor performs no filesystem I/O. `put` is the only operation allowed to
initialize a missing/empty absolute database path; reads never create files.
Existing non-empty databases must already have exactly the v2 marker schema.

The schema contains only `store_meta(namespace)` and `results(key,payload)`.
Transactions implement create-once, byte-identical idempotency and conflict
without overwrite. `get` accepts a complete N1 key, requires a BLOB-like
payload, decodes and verifies the embedded key, and sanitizes all failures.
Connections close on every success and failure path. SQLite paths are opened
with ordinary `sqlite3.connect(str(path))`, never URI interpolation. Selector,
listing, latest, legacy, migration, network, caller, and live APIs are absent.
