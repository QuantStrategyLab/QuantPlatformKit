# Synthetic Combo Evidence

[简体中文](synthetic-combo-evidence.zh-CN.md)

- Produces `learning_only` synthetic combo research evidence only.
- Outputs always fix `promotion_eligible=false`, `live_ready=false`, and `synthetic=true`.
- Evaluates whether correlated strategy sleeves held together require a group risk-sleeve haircut.
- Accepts only caller-injected member weights / `risk_sleeve` and pairwise correlation estimates.
- Never reads brokers, accounts, credentials, networks, or runtime consoles.
- Emits no orders, skips `RiskEngine` execution paths, and grants no live authority.
- Leaves mandates, policies, account enablement, and circuit breakers unchanged.
- Fails closed immediately if any member pair lacks a correlation estimate.
- Fail-closed paths emit research evidence and reason codes only without faking a haircut.
- Identifies correlation groups via connected components over thresholded pairwise correlations.
- Scales group `risk_sleeve` sums proportionally whenever they exceed the group cap.
- Records pre- and post-haircut sleeves per member for research interpretability.
- `combined_risk_sleeve` is a synthetic aggregate only, not live risk allocation.
- Never substitutes for promotion gates, deployment authorization, or recovery approvals.
- Live enablement still requires independent promotion, account hard gates, and `RiskEngine` checks.
