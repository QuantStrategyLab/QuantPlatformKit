# 资金信封目标缩仓与 Attention 预算

## API

1. `apply_combined_scale_to_targets(targets, combined_scale)`  
   - `None`/非法 scale → **omit**（原样返回有限非负目标）  
   - 合法 scale ∈ [0,1] → 只缩不扩  
2. `resolve_mandate_dd_budget(profile)`  
   - SOXL/TQQQ 默认 `0.35`（非 10%）  
   - 可被 `override` / `QSL_MANDATE_DD_BUDGET[_PROFILE]` 覆盖  
3. `publish_attention_telegram_transition` — ACTION/HALT 跃迁才发 TG

## 目标波动率输入

`evaluate_capital_risk_envelope` 的 `target_vol` 为年化目标波动率。省略参数时，
仍使用 `DEFAULT_TARGET_VOL_ANNUAL = 0.20`。显式传入的值必须是有限正数；
`NaN`、无穷、零、负数、布尔值、字符串或 `None` 会使 `vol_scale` 和
`combined_scale` 归零，并返回 `new_risk_allowed=False`，原因码为
`INVALID_TARGET_VOL_FAIL_CLOSED`。缺少或为零的 `realized_vol` 不会绕过该检查。

`evaluate_multi_account_envelope_view` 对各账户及聚合信封使用相同规则。
调用方不得将显式无效的目标波动率替换成默认值；只有省略参数才使用默认值。
该规则不改变 `apply_combined_scale_to_targets` 的非法 scale 省略约定。

## 平台消费

- 买侧数量与目标权重只能选择一处缩放；同一路径重复使用 `combined_scale` 会造成双重缩放。
- Attention 通知应使用状态跃迁去重，成功发送后再记录 marker。
- 日损判断需要账户对应的日损事实；缺少事实时不能用通知结果推断保护已生效。

库 API 和依赖 pin 不能证明平台正在使用该路径。确认实际采用时，须分别核对部署版本、
配置及对应周期的执行证据。

采用包含该输入检查的依赖版本时，应核对各调用方的 `target_vol` 来源，并分别验证
显式无效值被拒绝、省略参数保留默认行为。依赖更新本身不授权调整已运行账户的持仓。
