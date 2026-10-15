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
Release assets must contain public code, synthetic material and reviewed
runtime wheels only. Private material and real market/account inputs stay in
approved cloud storage; do not publish them as repository release assets.

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

### Optional cloud input fetch (draft; disabled by default)

`HOSTED_INPUT_FETCH_ENABLED=true` selects a single object in approved GCS
storage instead of a GitHub Release asset. It requires `HOSTED_INPUT_URI`
(exact `gs://` object; no wildcards), `HOSTED_INPUT_GENERATION` (immutable
generation), the existing `HOSTED_INPUT_SHA256` (archive SHA256), and
`HOSTED_INPUT_ASSET` (local ZIP basename). There are no private default values.
The fetcher runs only on a main-branch GitHub-hosted runner, checks the pinned
object metadata before download, caps the compressed archive at 512 MiB,
verifies its length and digest, and then uses the existing safe ZIP staging.
It requests exact-object metadata/GET operations without listing the bucket.
Fetch or validation failure stops the job; it does not fall back to a release
asset, a different generation, or a server directory. CLI error details are
withheld because they may contain private object names.

The workflow does **not** configure GCP authentication. The `gcloud` CLI must
already have an approved keyless identity on that hosted runner. Existing
OIDC permission for the task service is not proof of GCS access. Before any
enablement, review reuse of the existing GitHub OIDC/WIF pool/provider and a
dedicated read-only service account restricted to the approved bucket prefix.
Authentication, IAM, variables and secrets have not been changed here. The
current review job has no GCP authentication step, so this remains a draft
until that separate authorization and the actual bundle/resume acceptance
are complete. Do not enable the flag to test missing permissions.

Local tests use synthetic bytes and a fake cloud command. No real input is
fetched to a developer machine, and CI does not authenticate, deploy, submit
tasks, or call paid model APIs. Keep `HOSTED_RESEARCH_ACCEPTED` and
`AI_SERVICE_RELEASE_READY` at their existing values.

Run actionlint and the existing PR CI at the final commit. Before adoption,
execute a synthetic/offline bundle and confirm wheel/input digest rejection,
frozen-source identity, existing budgets and Docker availability where needed.
No production scheduler/trading changes are in this PR. Revert through a new
PR if needed; re-enabling a VPS runner needs separate owner approval.
