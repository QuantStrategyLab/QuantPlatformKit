# Unattended draft review — 2026-10-15

Local self-review of exact GitHub PR diffs and current check results. This is not
an independent model review, production acceptance, or a grant verification.
No merge qualifies under the owner's requested conditions; all six stay draft.
Any future eligible merge must re-read all checks at the exact final head and use
`gh pr merge --squash --match-head-commit <head>` without `--admin`. A skipped gate
is not evidence that the gate passed.

| PR | Reviewed head | Observed checks | One-line disposition |
| --- | --- | --- | --- |
| QPK #672 | `0c727102b57074fab889fd156efedf2ba340f8af` | CI test success | Keep draft: deeper Dot routing/admission is unverified and the monitor executes a mutable feature-branch reference. |
| ARC #116 | `47539f27728ebd6eb8d40d8d1e3989797067a1f7` | CI test success | Keep draft: stacked on #115 and explicitly depends on unresolved issue #104 caller identity/model/material/routing admission. |
| US #601 | `295df4da6bef3e4e8ff22e95fb980a2d01035dce` | Four CI checks success; behind main | Keep draft: unadopted QPK runtime and mutable monitor reference; no verified deeper Dot route. |
| CN #330 | `6b4f0efc6c341b786a6e37a18e54171e0979c3c9` | CI test and actionlint success | Keep draft: unadopted QPK runtime and mutable monitor reference; no verified deeper Dot route. |
| HK #249 | `6c2b0b20c3ef234363e91b19279a323592a0be40` | CI success; Evidence Gate skipped | Keep draft: QPK/runtime/routing dependencies remain and the Evidence Gate has not passed. |
| Crypto #270 | `a8a413d08263fbe1d787e0d429daf6004fd0ab78` | CI test/actionlint success; Evidence Gate skipped | Keep draft: QPK/runtime/routing dependencies remain and the Evidence Gate has not passed. |

The diff review found no added trading, IAM or secret-access permission in these
six changes. GitHub issue writes are review-record/notification permissions;
existing OIDC permissions are retained, not new grants. This satisfies only part
of the requested merge conditions, and does not excuse runtime dependencies.

QPK `DotReview` selects a configured verifier or first reviewer and accepts only
agent mode before submission; its completed receipt checks request, task, owner
and provider. It cannot prove beforehand that the profile is an admitted Dot
route. Its monitor checks out `feat/advisory-review-closed-loop`. Consumer health
workflows call that same mutable branch. Consumers retain existing approved-wheel
digests, so enabling a new environment flag does not prove the installed runtime
contains the new disposition code. Do not change pins or READY variables here.

ARC #104 is an **issue**, not a PR. It remains open with unfilled acceptance items
for the caller, actual effective route, model/material authority and live receipt
verification. ARC #116 changes shipped `config/repair.json` to enable the loop
for an opt-in backend and suppresses some unconfirmed notices; without verified
adoption its new behavior must not be treated as operational recovery.

Additional concrete QPK monitor limitation: `check_lane` reads only completed
runs; a permanently queued/running review can be omitted. It also uses the latest
manual or PR run as the age anchor for a scheduled lane. Such runs can mask a
missing natural scheduled review. The independent monthly dead-man follow-up
uses expected schedule slots and detects stalled cycles without any model route.

Validation in this follow-up: QPK's review-loop/disposition/task/drift/summary
tests passed (43); ARC unittest suite passed (95). Tests use fakes. The reviewed
GitHub checks were read separately. Missing API secret availability and actual
Dot caller admission were not tested or modified. No ready conversion, merge,
production run, deployment, server access, trading operation or permission
change was performed.
