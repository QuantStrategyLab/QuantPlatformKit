# 资金信封目标缩仓与 Attention 预算

## API

1. `apply_combined_scale_to_targets(targets, combined_scale)`  
   - `None`/非法 scale → **omit**（原样返回有限非负目标）  
   - 合法 scale ∈ [0,1] → 只缩不扩  
2. `resolve_mandate_dd_budget(profile)`  
   - SOXL/TQQQ 默认 `0.35`（非 10%）  
   - 可被 `override` / `QSL_MANDATE_DD_BUDGET[_PROFILE]` 覆盖  
3. `publish_attention_telegram_transition` — ACTION/HALT 跃迁才发 TG

## 平台消费

- 买侧数量与目标权重只能选择一处缩放；同一路径重复使用 `combined_scale` 会造成双重缩放。
- Attention 通知应使用状态跃迁去重，成功发送后再记录 marker。
- 日损判断需要账户对应的日损事实；缺少事实时不能用通知结果推断保护已生效。

库 API 和依赖 pin 不能证明平台正在使用该路径。确认实际采用时，须分别核对部署版本、
配置及对应周期的执行证据。
