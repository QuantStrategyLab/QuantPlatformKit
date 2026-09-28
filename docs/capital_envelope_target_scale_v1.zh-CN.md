# 资金信封目标缩仓与 Attention 预算（2026-09-18）

> 状态：库侧已合；三平台买侧数量缩仓已在 main；Attention 跃迁本批 pin `bd8d06e`。

## 已合 API

1. `apply_combined_scale_to_targets(targets, combined_scale)`  
   - `None`/非法 scale → **omit**（原样返回有限非负目标）  
   - 合法 scale ∈ [0,1] → 只缩不扩  
2. `resolve_mandate_dd_budget(profile)`  
   - SOXL/TQQQ 默认 `0.35`（非 10%）  
   - 可被 `override` / `QSL_MANDATE_DD_BUDGET[_PROFILE]` 覆盖  
3. `publish_attention_telegram_transition` — ACTION/HALT 跃迁才发 TG

## 平台消费

- **买侧数量**：Schwab / IBKR / LB 在提交前 `apply_combined_scale(qty, admission.combined_scale)`（已 live）  
- **勿**再对同一路径的目标权重叠缩，避免双重缩放  
- **Attention**：周期 NEW_RISK 评估后 `maybe_publish_attention_for_admission`（进程内 marker 去重）  
- 日损事实生产者：仍阻塞（见 DAILY_LOSS_FACT_PRODUCER_GAP）
