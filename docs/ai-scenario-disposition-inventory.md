# AI scenario disposition inventory

Source: owner-provided ~/codex-jobs/scenarios/final.txt, refreshed for completed monthly_audit, harden and arc_migrate jobs on 2026-10-15.

Classification is operational, not a claim that merged source has been deployed or exercised. No scenario has current evidence of the complete unattended pattern in production. Counts: 0 already unattended-closed-loop, 25 need loop/adoption, 7 human-only by design. Groups preserve the original 32-row inventory; some groups contain multiple repositories.

| ID | Scenario | Classification | Concrete change or retained boundary |
| --- | --- | --- | --- |
| 1 | Gateway dispatch infrastructure | needs loop | Require consumer-owned review disposition and liveness; the gateway itself must not close consumer issues. |
| 2 | Gateway short structured API tasks | needs loop | Validate frozen outputs and caps; add outcome artifacts and failed/skipped-task monitoring before unattended use. |
| 3 | Daily briefing and QPK research summaries | needs loop | Review factual summaries against frozen facts; archive/close passes, one Dot escalation for flags; propagate summary unavailability to host-job failure. QPK draft adds the review hook. |
| 4 | Daily briefing dual review | needs loop | Feed all three role outcomes to disposition; retain strict quorum and existing admission; independent briefing dead-man. |
| 5 | Health-cycle diagnosis | needs loop | Preserve failure fingerprint deduplication; add one deeper Dot confirmation and notify only confirmed problems; monitor diagnostic job liveness. |
| 6 | 12345 short complaint rewriting | needs loop | Keep deterministic fact preservation and length checks; archive validation outcomes; review factual flags and monitor rewrite failure without automating identity verification. |
| 7 | 12345 synthetic assistant verification | needs loop | Close successful synthetic verification records; preserve one original task on timeout; alert after N failed/skipped verification jobs. |
| 8 | Portal CAPTCHA and identity verification | human-only by design | Human-only: retain manual identity verification; do not build bypass or visual solving. |
| 9 | Medical local SSO/OCR collection | human-only by design | Human-only: protected local session and owner-controlled collection; no unattended login. |
| 10 | Recruitment report rewriting | needs loop | Validate rewritten facts against original evidence; archive passes, confirm factual flags through Dot; retain disabled state until separately admitted. |
| 11 | Recruitment frozen lead audit | needs loop | Replace server CLI with existing-grant frozen-material tasks; add strict evidence review/disposition and independent liveness. No server path restoration. |
| 12 | Ctrip compliance evidence review | needs loop | Retain collection coverage/evidence gates; add frozen dual review/disposition once admitted. Login/CAPTCHA/needs_review remain operational states, never legal findings. |
| 13 | PhotoStory multi-stage review | needs loop | Retire server CLI under a separate cutover; attach per-batch verdicts, one deeper Dot review for flags, and processor/review dead-man. Publication remains separately authorized. |
| 14 | Actions failure diagnosis | needs loop | Stack on arc_migrate #115; add issue-only verdict disposition, one deeper task, and diagnostic liveness. Preserve #104 identity blocker and no auto-repair. |
| 15 | HomeNetwork router/server repair | human-only by design | Human-only: retain hard-disabled privileged AI repair from #39; deterministic checks remain. |
| 16 | Telegram owner Mac engineering session | human-only by design | Human-only: interactive owner-controlled engineering; no autonomous review-triggered code/configuration repair. |
| 17 | Telegram remote server agent mode | human-only by design | Human-only: never operate servers through an unattended AI agent; retain disabled/unapproved boundary. |
| 18 | Telegram speech transcription | needs loop | Add deterministic duration/output/cost validation and liveness; factual transcript corrections require bounded review, no server actions. |
| 19 | QPK frozen engineering-material review | needs loop | Use shared issue-only disposition, archive verdicts and monitor failures/skips; retain merge/deployment authority restrictions. QPK draft. |
| 20 | US/CN/HK/Crypto drift review | needs loop | Use shared disposition without altering drift or trading outcomes; one Dot escalation; severe consensus reports missing cycle-pause binding. QPK and consumer drafts. |
| 21 | US/CN/HK/Crypto Evidence Gate | needs loop | Opt into shared disposition and companion issues, archive verdicts and monitor gate liveness; never close a PR or bypass deterministic evidence/READY checks. Consumer drafts preserve harden role fixes. |
| 22 | Research promotion-cycle findings and summaries | needs loop | Review frozen summaries, withhold unverified summaries, archive results; retain human adoption gates. QPK draft covers summaries, not automatic research/code generation. |
| 23 | SOXL code-generation research | human-only by design | Human-only: owner-controlled one-off engineering; do not restore autonomous model code edits. |
| 24 | SOXL fixed-parameter learning review | needs loop | Attach frozen-request verdict records, one deeper confirmation and task liveness; preserve manual trigger and grant blocker. |
| 25 | Global ETF deep source review | needs loop | Add strict source-evidence verdicts and one deeper task; retain current grant/READY block and bounded task limits. |
| 26 | CN ETF request advice | needs loop | Archive frozen-request review outcomes, one deeper Dot confirmation and liveness; retain missing CN admission as a blocker. |
| 27 | Strategy plugin evidence cross-check | needs loop | Migrate V1 facts-only calls to admitted V2; archive verification, confirm flags and monitor failed/skipped checks. Never change plugin signals or trading settings. |
| 28 | Crypto monthly dual-API audit | needs loop | Source loop merged in CryptoLivePoolPipelines #208. Runtime remains blocked on existing API secret availability and monthly-workload Dot admission; no cycle-bound pause API exists. |
| 29 | Deleted Crypto automatic optimization repair | human-only by design | Human-only: remain deleted; autonomous AI code/configuration repair is forbidden by the current pattern. |
| 30 | HK/US monthly snapshot audit | needs loop | Connect frozen published snapshots to admitted independent reviews, companion issue disposition, one deeper Dot review and monthly dead-man; no snapshot/configuration mutation. |
| 31 | Monthly shadow signal review | needs loop | Review frozen source material through existing admitted tasks, archive/close passes, confirm flags; retain manual/blocked state until grants exist. |
| 32 | Six-repository engineering PR review | needs loop | Replace retired failing scripts with admitted frozen-diff review and companion issue disposition/dead-man; never auto-merge or change code based on findings. |

Conflicts: harden finished before consumer edits; HK/Crypto drafts are stacked on its role/READY drafts. arc_migrate finished before ARC edits; the ARC draft is stacked on #115. No in-flight job worktree was edited.

Owner decisions/adoption gaps: make existing API secrets available if desired; authorize no new grants in this task; establish admissible monthly/ARC routes through separate approved work; select existing cycle-pause bindings if available; adopt reviewed wheels/references; propagate summary unavailability to host job status; retain human-only flows. No live trading, server, IAM, secret-value or force-push operations were performed.
