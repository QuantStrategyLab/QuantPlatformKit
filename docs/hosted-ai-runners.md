# Hosted research/review runner migration (P1)

The selected workflows use fresh GitHub-hosted Linux runners. Their existing
OIDC admission, RELEASE_READY/run-attempt guards, manual execute switches,
concurrency groups, task timeouts and research limits are unchanged. This PR
has no auth grant, broker/trading configuration, deployment or IAM changes.

## Inputs and first execution

A self-hosted installation and its absolute paths are not available. Stage a
reviewed ZIP release asset from **this repository** using existing contents-read
GITHUB_TOKEN: HOSTED_INPUT_RELEASE, HOSTED_INPUT_ASSET, HOSTED_INPUT_SHA256.
The SHA256 is mandatory; traversal/symlinks and excessive expanded data fail.
Publish no credentials, .env files, CLI login data or credential-bearing git
config. Existing per-workflow material/source/wheel/root variables must point
inside `hosted-inputs/` (output roots can use RUNNER_TEMP). Frozen source git
metadata/commit pins and the existing wheel SHA256 checks still apply; do not
replace a reviewed wheel with a similarly named package from an index.
The bundle includes only licensed, approved research inputs and required
reviewed runtime wheels. Publishing private inputs requires owner approval.

The bundle must supply wheels/ and a fully pinned runtime-requirements.txt
for the approved task-client distribution and dependencies. Offline pip uses
only those reviewed artifacts; it cannot substitute an index package. The
caller itself is installed from this checkout. No client version/grant/model
is guessed by this PR. HOSTED_RESEARCH_ACCEPTED defaults to disabled; set it
only after input provenance, dependency pins and durable resume are accepted.
UES retains scripts/install_ai_task_client.py's exact approved wheel checks.
Missing bundles/wheels/relative paths/grants fail; no VPS fallback is provided.
Do not enable RELEASE_READY to bypass those prerequisites.

Hosted disks are ephemeral. Pending task/result/learning ledgers must be
exported as approved private artifacts before job termination, and a resumed
run must consume that exact latest ledger. A workflow rerun with an old bundle
is not a safe resume. Do not execute live research until persistence/resume and
licensed input accessibility have been accepted; retain this PR as draft
until those conditions are resolved. CI verifies engineering syntax/tests;
it does not call Dot or establish research/receipt completion.

## Acceptance and rollback

Run actionlint and the existing PR CI at the final commit. Before adoption,
execute a synthetic/offline bundle and confirm wheel/input digest rejection,
frozen-source identity, existing budgets and Docker availability where needed.
No production scheduler/trading changes are in this PR. Revert through a new
PR if needed; re-enabling a VPS runner needs separate owner approval.
