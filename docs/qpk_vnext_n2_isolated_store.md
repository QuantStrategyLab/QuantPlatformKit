# QPK vNext N2 isolated filesystem store

N2 stores only `qpk-vnext/result/v2` records below an explicitly supplied local
root. It never reads or scans legacy namespaces, performs no cloud/network I/O,
and intentionally provides no implicit `latest` operation. Callers must use an
exact contract key (or the explicit domain/profile/timing selector listing).

Only `persist_mode=durable` is accepted. Ephemeral contracts fail before any
filesystem side effect. Writes validate through the N1 encode/decode contract,
derive the complete path from `contract.key`, and use atomic temp-file replace.
Existing byte-identical canonical JSON is an idempotent no-op; any conflict or
corruption fails closed without overwrite. Temporary files are cleaned up on
failure. All key paths receive root-containment and single-segment checks.
