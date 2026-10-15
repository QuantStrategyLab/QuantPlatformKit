# 可行动注意力门槛 V1（AttentionLevel）

> 范围：通知分级 / 人工恢复路由；不授权 live、不抬 RRL、不做 Kelly。

## 原则

1. **不**用全局绝对回撤（如 10%）对 TQQQ/SOXL 发 Telegram。  
2. 回撤仅相对显式 `mandate_dd_budget`；缺预算则 **omit** 该轴。  
3. 仅 `ACTION` / `HALT` 可通知；键为状态跃迁，发送成功后才记 marker。  
4. 自动刹车仍在 NEW_RISK / RiskEngine；本模块只分类注意力与短文案。

## API

- `evaluate_attention(AttentionAxes | mapping) → AttentionDecision`
- `resolve_mandate_dd_budget(profile)` — SOXL/TQQQ 默认 `0.35`（非 10%）
- `attention_transition_key(...)` 去重键
- `render_attention_compact(locale=...)`（`zh-CN`→`zh`）
- `publish_attention_telegram_transition` — ACTION/HALT 跃迁才发 TG
- `build_drift_alert` / `publish_drift_alerts`：WATCH 不建页；Telegram 走真实 `send_telegram_message`；缺配置记 `skipped` 并打日志（不再吞异常）

## 分级

| Level | 例 | TG |
|---|---|---|
| OK | 预算内路径回撤 | 否 |
| WATCH | drift watch；dd_ratio∈[0.7,1) | 否 |
| ACTION | NEW_RISK 禁买；drift review；dd 打穿 mandate | 是（跃迁） |
| HALT | drift critical；对账不确定；hard PARK | 是（跃迁） |

## 运行验收

Attention 消息只说明通知分类与投递结果。核验拒单、禁买或买侧缩仓是否生效，须检查
对应平台的部署版本、风险输入和实际周期结果；库内 API 可用不能替代这些证据。
日损事实缺失或 `assess_with_evidence` 调用未确认时，保留相应未知状态。
