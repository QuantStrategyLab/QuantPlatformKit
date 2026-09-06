## Synthetic Combo Evidence

- 该模块仅用于 `learning_only` 的 synthetic 组合研究证据。
- 输出固定为 `promotion_eligible=false`、`live_ready=false`、`synthetic=true`。
- 目标是回答多个成员策略一起持有时，相关组风险袖是否需要 haircut。
- 输入只接受注入的成员权重 / `risk_sleeve` 与相关性估计。
- 不读取券商、账户、凭据、网络或运行态控制台。
- 不生成订单，不调用 `RiskEngine` 执行路径，不授予 live。
- 不修改 mandate、policy、账户 enablement 或 breaker 状态。
- 多成员组合缺任一 pairwise correlation 估计时，结果直接 fail-closed。
- fail-closed 只产生研究证据与 reason code，不假装已经完成 haircut。
- 相关组通过阈值化 pairwise correlation 连通分量识别。
- 若同组 `risk_sleeve` 之和超过 cap，则按比例裁切到 cap。
- 输出保留每个成员 haircut 前后的 sleeve，便于研究解释。
- `combined_risk_sleeve` 只是 synthetic 汇总量，不代表实盘额度。
- 该证据不能直接作为晋级、授权或恢复依据。
- 真正上线仍需既有晋级、账户硬门与 `RiskEngine` 链路单独评估。
