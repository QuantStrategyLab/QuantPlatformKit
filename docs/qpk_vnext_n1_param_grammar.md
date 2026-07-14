# QPK vNext N1 Params Grammar

Approved clean-slate source of truth for `qpk-vnext/result/v2`:

```text
Params      := JSON object / safe Mapping<Name, Value> (top-level only)
Name        := non-empty bounded Unicode-scalar string
Value       := bool | safe integer | bounded Unicode-scalar string | Sequence
Sequence    := tuple at Python construction; JSON array on wire; tuple after decode
```

`null`, float (including finite, `-0.0`, NaN, Inf), nested Mapping/object,
mutable list/dict at Python construction, unknown types, unsafe/overlong strings,
surrogates, and excessive recursion/size fail closed with sanitized contract errors.
Decimal values must be canonical strings or scaled safe integers. Profile policy is
owned by higher layers; this contract only requires an uppercase safe identifier.

Identity digest/key use the documented stable identity subset and exclude
`persist_mode` and `computed_at`; both remain wire metadata. Wire and identity
digests are deterministic canonical JSON hashes. No legacy/default/ANY/alias
fallback or store I/O is part of N1.
