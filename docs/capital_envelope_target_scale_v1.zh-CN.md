# 资金信封目标缩仓与 Attention 预算（2026-09-18）

> 状态：库侧本 PR；平台接线随后 pin 本 SHA。

## 本 PR

1. `apply_combined_scale_to_targets(targets, combined_scale)`  
   - `None`/非法 scale → **omit**（原样返回有限非负目标）  
   - 合法 scale ∈ [0,1] → 只缩不扩  
2. `resolve_mandate_dd_budget(profile)`  
   - SOXL/TQQQ 默认 `0.35`（非 10%）  
   - 可被 `override` / `QSL_MANDATE_DD_BUDGET[_PROFILE]` 覆盖  
3. `publish_attention_telegram_transition` — ACTION/HALT 跃迁才发 TG

## 平台接线（后续 PR）

- admission 后：`allocation["targets"] = apply_combined_scale_to_targets(..., admission.combined_scale)`  
- 禁买/CRITICAL：调用 `publish_attention_telegram_transition` + marker  
- 日损事实生产者：仍阻塞（见 DAILY_LOSS_FACT_PRODUCER_GAP）
