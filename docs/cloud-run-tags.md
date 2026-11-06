# Cloud Run revision tags

`quant_platform_kit.operators` exports the pinned offline operator contract
`cloud-run-tags/v1`. It performs no network calls, deployment, traffic updates,
renames, IAM changes or credential access. Runtime trading controls are outside
this module. Existing callers acquire no additional authority by importing it.

## Allocation

Call `headroom(service_name)` on the exact original service name, before display
redaction. The tagged URL budget is `len(service_name) + len(tag) <= 46`.
`allocate_tag` takes the exact service name, preferred tag, project, region,
candidate revision, operation/run identity, a complete fresh `existing_tags`
mapping, and a private job-local `state_path`.

- A fitting preferred tag is selected only when free or bound to this exact
  operation and candidate in the journal. A cloud revision match alone does
  not prove ownership. Foreign or unknown occupancy returns `TAG_OCCUPIED`.
  The first occupancy refusal durably initializes the journal without reserving
  a tag, so unrelated allocations can continue using the same journal.
- With headroom 1–12, an oversized preferred tag becomes one deterministic
  hash-derived legal tag, no longer than headroom. Collisions return
  `TAG_RESERVED` or `TAG_OCCUPIED`; there is no retry search or overwrite.
- Headroom at or below zero returns `Refusal('TAG_IMPOSSIBLE')`. Invalid input
  and unreadable, corrupt, incompatible or replaced state also return explicit
  refusals. Callers must branch on the result type and stop on every refusal;
  truthiness is not a success check.

Use an absent journal path in an existing private directory for the first
allocation. Only this module creates the mode-0600 file. Every process in the
same job must share it; preserve it across restarts. Never unlink, replace,
pre-create, truncate, copy to Git or reset it to recover from a failure. Missing
state after a restart requires operator reconciliation, not a fresh allocation.
The allocator holds a Linux `flock`, reads the current journal after locking,
checks the locked file's identity, then flushes/fsyncs the reservation before
returning. An interrupted in-place write can invalidate the journal and must
stop subsequent allocation. The private directory and its parent must remain
under exclusive caller control; this is not a cross-host lock or cloud lease.

The journal binds project/region/service, operation, candidate and preferred tag
using full hashes, retaining only the operational tag as plaintext. Hashes are
private correlation data, not anonymisation. Returned tags are operational
values; do not log them. Dataclass representations suppress operational fields;
refusal messages contain static codes and never raw exceptions. For any caller
logs or API output, use the existing shared masking helper, including
`quant_platform_kit.notifications._redaction.mask_identifier` for resource
identifiers. Never mask an identifier before budgeting or identity comparisons.

The caller's `existing_tags` maps **every** tag to its exact revision, including
zero-percent entries. An unknown revision is `None` and remains occupied.
Allocation leaves this mapping untouched. An allocation recovered after restart
is the same reservation, not an execution or replay permit. No release, expiry
or ownership-stealing operation is provided.

## Impossible-tag lifecycle

`lifecycle_for_impossible_tag` defaults to `STOP` and never claims an untagged
zero-percent candidate was warmed. A `MICRO_SPLIT` result proposes exactly
previous=99 / candidate=1, only when all these conditions hold:

- The service has no nonempty tag headroom.
- The caller verified an authentic owner decision and supplied a
  `WarmupApproval` with `warmup_traffic_approved=True` (a literal boolean).
- Project, region, service, action=`warmup`, and operation/run identity match
  exactly. An approval for promotion, another run or another service cannot
  widen the scope.
- `no_traffic` is explicitly `False` and `image_only` remains `False`; truthy
  strings and unknown values cannot satisfy either gate.

An approval object is policy input, not authentication. Callers must verify its
owner, validity, exact candidate and scope at their existing protected entry
point. Strict no-traffic diagnostics and image-only callers always stop on
impossible tags; this helper cannot grant them micro-traffic authority.

## Caller mutation and restore contract

Before any cloud write, the caller must hold a current exclusive execution
claim covering the exact target/run/candidate, durably record a single-use
mutation intent, and re-read the current service generation, image/source,
revision identity, traffic distribution and complete tags. The local allocation
journal does not serialize cloud writes across different jobs or hosts. Bind
approval to the exact candidate; do not reuse an operation ID for another image
or revision. Authenticate evidence using the caller's existing gates.

Preserve all pre-existing tags and traffic entries, including zero-percent tags,
and compare the current cloud state against the approved before-image before
every stage. Use the caller's existing conditional-write/ownership mechanism;
a preflight read alone cannot prevent cloud races. A lost claim, state drift,
unknown write result or timeout requires readback and reconciliation, never an
automatic replay. A matching allocated tag is not permission to overwrite it.

For an explicitly approved micro-split, verify exactly the permitted 99/1 split
and candidate startup/health. Restore the approved previous distribution on
failure, preserving every existing tag, then read it back before cleanup or a
subsequent stage. If ownership is lost or restoration cannot be verified, stop
all further writes and report `RESTORE_UNVERIFIED`. The policy supplies neither
gcloud mutation commands nor a claim that restore is atomic or always possible.

## Adoption

IBKR, Firstrade, LongBridge and QRS adopters must pin the reviewed QPK revision
or vendor this module with its contract version and offline tests. Replace
local formulas only within separately authorized caller changes, retaining the
entry point's existing traffic restrictions and identity gates. Confirm actual
caller use and pinned version before claiming adoption. This module alone
changes no deployed service or runtime behavior. Long-name service migration
remains deferred.
