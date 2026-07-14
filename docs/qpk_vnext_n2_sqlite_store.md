# QPK-N2 SQLite isolated store

N2 is a trusted single-process local research backend using only Python's
stdlib `sqlite3`. The constructor validates an explicit absolute database path
without touching the filesystem; callers provide the parent directory. Durable
operations open the database with fixed rollback-journal and `synchronous=FULL`
policy. Ephemeral contracts fail before opening or creating the database.

The schema is marked `qpk-vnext/result/v2`; legacy files/tables/namespaces are
never read. The complete N1 key is the primary key and canonical payload bytes
are stored with explicit identity columns. Transactions provide create-once,
byte-identical idempotency and conflict/no-overwrite semantics. Exact reads and
domain/profile/timing selector listing decode and cross-check every payload.
Latest remains deferred. Hostile parent-directory/filesystem mutation is outside
this trusted-backend contract; no portable openat/path walker is claimed.
