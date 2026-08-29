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
- 只有已获 Shadow 准入、并绑定 immutable release 的候选可以被排名；`shadow_candidate`
  仅可得到“建议进入 Shadow”的零仓位结论，不能由此启动 runtime。
- P0 不能改变平台、策略、插件挂载、仓位或调度器。

后续 M1 才能把 Shadow 结论呈现给人工；M2/M3 还必须经过独立的 Paper、Canary、
双 AI 复核和既有风险授权，不能由本模块单独开启。

## 与顾投研究系统的边界

`QuantAdvisorResearch` 是 **AssetIdeaAdvisor**：它回答“哪些标的或主题值得继续研究”，
并给出非个性化的研究理由、风险提示和观察周期。它不是组合配置器，也不是策略或平台
选择器。

本控制面回答的是另一件事：在已经通过生命周期准入、绑定 immutable release 的策略中，
基于可验证市场数据与平台对账健康，哪些可以获得 **零仓位的 Shadow 建议**。它不把顾投的
`recommend`、新闻文字、主题叙事或人工偏好当作可执行分数。

因此两个系统之间只允许以下单向、延迟的研究通道：

```text
顾投研究结论
  → 人工/双 AI 建立研究假设
  → P1–P3 数据、回测与独立证据
  → immutable 策略候选
  → P0 Shadow 选择记录
  → M1 人工查看
```

不允许的捷径：

- 不把顾投 artifact 直接作为 `qsl.selection_input.v1` 的市场因子、`base_score`、
  插件风险乘数、平台健康或策略权重；
- 不让顾投报告调用策略切换、runtime target、券商或下单接口；
- 不把 Shadow 选择结果回写为顾投结论的“市场验证”，以免形成自我证实循环；
- 当两边观点不同，以确定性风险门禁、对账和 lifecycle 准入为准；顾投结论只能触发
  研究，不得覆盖拒绝原因。

M1 控制台应把两类信息分栏展示并明确标注“研究线索”和“Shadow 运行建议”。同一标的或
主题的文字建议不等于系统持仓意图；没有独立 P1–P6 证据，就不会进入运行路径。
