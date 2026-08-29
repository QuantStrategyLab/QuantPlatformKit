# 自适应配置控制面（P0）

P0 提供统一、只读的 Shadow 决策记录，不提供交易授权。它解决的是“为什么建议某个
已批准策略/平台”，而不是让模型直接改变实盘配置。

## 输入与输出

输入都必须带版本并可回放：

- `qsl.market_context_snapshot.v1`：可验证的市场因子、状态、置信度和数据新鲜度；
- `qsl.platform_health_snapshot.v1`：平台健康、对账、容量和成本估计；
- 已批准的 immutable strategy release 与插件风险缩放。

输出为 `qsl.selection_decision.v1`，完整保存候选、拒绝原因、平台选择、策略分数和
输入摘要。输出固定为 `authority=shadow_only`、`no_order=true` 且所有建议权重为零。

## 通用接入边界

任何策略仓库或平台仓库都可以向 `quant-adaptive-selection` 提交
`qsl.selection_input.v1` JSON，并得到可保存、可回放的决策工件：

```bash
quant-adaptive-selection --input selection-input.json --output selection-decision.json
```

输入必须提供带时区的平台健康快照、版本化市场上下文、不可变候选 release、插件风险
缩放和冻结策略。命令不接受 broker 凭据、运行时目标或下单参数；输出文件仅是 JSON
工件，不会修改平台或调度器。

## 固定边界

- 不读取新闻叙事并直接交易；因子必须来自版本化的数据链。
- 数据过期、状态不明、置信度不足、插件未批准、平台未对账或不健康时 fail-closed。
- 插件只能给出 `0..1` 的风险缩放，不能增加风险或提交订单。
- 只有已获 Shadow 准入、并绑定 immutable release 的候选可以被排名。
- P0 不能改变平台、策略、插件挂载、仓位或调度器。

后续 M1 才能把 Shadow 结论呈现给人工；M2/M3 还必须经过独立的 Paper、Canary、
双 AI 复核和既有风险授权，不能由本模块单独开启。
