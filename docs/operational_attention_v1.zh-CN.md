# 可行动注意力门槛 V1（AttentionLevel）

> 状态：库侧纯函数 + drift Telegram 分发修复（本 PR）；平台周期接线与 mandate 预算表另票。  
> 范围：通知分级 / 人工恢复路由；不授权 live、不抬 RRL、不做 Kelly。

## 原则

1. **不**用全局绝对回撤（如 10%）对 TQQQ/SOXL 发 Telegram。  
2. 回撤仅相对显式 `mandate_dd_budget`；缺预算则 **omit** 该轴。  
3. 仅 `ACTION` / `HALT` 可通知；键为状态跃迁，发送成功后才记 marker。  
4. 自动刹车仍在 NEW_RISK / RiskEngine；本模块只分类注意力与短文案。

## API

- `evaluate_attention(AttentionAxes | mapping) → AttentionDecision`
- `attention_transition_key(...)` 去重键
- `render_attention_compact(locale=...)`（`zh-CN`→`zh`）
- `build_drift_alert` / `publish_drift_alerts`：WATCH 不建页；Telegram 走真实 `send_telegram_message`；缺配置记 `skipped` 并打日志（不再吞异常）

## 分级

| Level | 例 | TG |
|---|---|---|
| OK | 预算内路径回撤 | 否 |
| WATCH | drift watch；dd_ratio∈[0.7,1) | 否 |
| ACTION | NEW_RISK 禁买；drift review；dd 打穿 mandate | 是（跃迁） |
| HALT | drift critical；对账不确定；hard PARK | 是（跃迁） |

## 复利风控审计对照（同批）

生存层（拒单 / 禁新买 / Policy A / RRL）已能支撑「先活下来」的几何复利。  
连续最优仓位仍缺：日损事实生产者、`combined_scale` live 缩仓、`assess_with_evidence`。  
**默认后置** Kelly / 抬 RRL；下一有界工程仅「日损事实→禁买」（材料齐时）。

## 后续（非本 PR）

- 平台在禁买/CRITICAL 首次跃迁时调用 publish + marker store  
- 为 SOXL/TQQQ 配置 mandate_dd_budget（研究/mandate 口径，非 10%）  
- 信封 `combined_scale`→目标缩仓另票  
