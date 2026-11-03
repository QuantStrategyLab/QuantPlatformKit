# 策略—M0 研究覆盖目录

`qsl.strategy-context-coverage-catalog.v1` 是一份版本化、只读的研究覆盖目录。
它把一个**明确指定**的 `strategy_profile` 与其策略类型、资产类别、风险暴露桶、资本
角色、基准标识和可接受的 M0 研究对象关联起来。

它不是运行配置：不能包含仓位、订单、账户、券商、平台、调度器或启用状态；固定
`authority={"research_only": true, "no_order": true}`。加载器不会从 profile 名称、
display name 或 ticker 推断任何分类。没有所有者明确声明的 profile 必须保持
`not_mapped`，不能消费 M0 研究结果。

示例位于
[`registry/strategy_context_coverage_catalog.example.json`](registry/strategy_context_coverage_catalog.example.json)。
示例不是生产目录；接入仓库必须创建由 owner 审核的实例并显式绑定自身 profile。

## 每项必须声明

- `strategy_kind`：如 `equity_selection`、`diversified_etf_rotation`、`dca`、
  `crypto_pool_rotation`、`multi_strategy_combo` 或 `risk_overlay`；未知类型 fail-closed。
- `instrument_classes`：如 `single_equity`、`etf`、`leveraged_etf`、`crypto_asset`、
  `multi_asset` 或 `plugin`。
- `exposure_buckets`：所有者维护的可比较风险暴露标签，例如行业、地区、因子或底层
  指数暴露。它们是相关性/重叠分析的输入，不能由名称猜测。
- `capital_role`：`core`、`satellite`、`defensive`、`reserve` 或 `overlay`。
- `benchmark_ids`：仅为研究/监控引用的标识；真实的被动或无杠杆基准仍由独立的
  `strategy-benchmark-catalog.v1` 绑定。
- `allowed_m0_research_subject_types`：`asset_idea`、`theme_context`、
  `strategy_hypothesis`、`risk_context` 中的显式允许集合。

## 与顾投和策略生命周期的边界

顾投输出先被适配为 M0 研究对象，再以本目录检查它是否与某个 strategy profile 有
明确覆盖关系。通过覆盖检查只能创建有配额、可追溯的 P1--P3 研究任务；它不能改变
`base_score`、风险乘数、候选权重、平台路由或运行开关。

```text
M0 研究对象 → 显式覆盖目录 → P1--P3 研究/回测/证据
            → immutable candidate → P0 Shadow（零仓位） → M1 展示
```

因此个股观点不会直接切换行业 ETF 或杠杆 ETF；主题观点也不会越过 DCA 的既有频率、
基准与风险约束。P0 的 `selection_input.v1` 继续只接受可验证市场数据、平台健康和
已准入 immutable candidate，不能直接摄入本目录或顾投文本。

## 迁移顺序

1. 各策略/插件 owner 为自身 profile 写出明确 entry，并在 PR 中提供基准与暴露依据。
2. 目录校验通过后，M0 adapter 才能产生 `research task`，未知 profile 只展示为
   `not_mapped`。
3. 将通过 P1--P3 的结果绑定 immutable candidate，再交给现有 P0 Shadow 链路。
4. 真实 benchmark、风险门、对账、生命周期与平台审批仍为独立的 fail-closed 控制。
