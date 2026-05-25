# 美股执行翻译规范

## 目标

这份文档定义 P3 阶段的统一规则：怎么把美股策略输出的统一
`AllocationIntent` 翻译成各个平台原生可执行的目标。

它处在两层之间：

- 策略侧的 `target_mode`
- 平台侧的券商执行目标

它不负责定义策略公式、平台输入构建，也不规定券商下单顺序。

## 各平台当前原生执行模式

当前三个平台的原生偏好是：

- `ibkr`：`weight`
- `schwab`：`value`
- `longbridge`：`value`

所以平台运行时必须支持这两类翻译：

- `weight -> value`
  - `schwab` 需要
  - `longbridge` 需要
- `value -> weight`
  - `ibkr` 需要

如果平台和策略本来就是同一种模式，就只做校验和规范化，不需要跨模式转换。

## 翻译层边界

策略代码负责：

- 目标语义本身
- 风险标记
- 诊断信息
- canonical `target_mode`

平台代码负责：

- 转成券商原生目标单位
- 手数/股数取整
- 最小交易门槛过滤
- 可执行现金检查
- 券商专属下单顺序
- 缺少实时价格时的 fail-close

策略代码不能自己做券商执行翻译。

## 翻译层允许依赖的输入

执行翻译层可以依赖：

- `AllocationIntent`
- `PortfolioSnapshot`
- 最新可执行价格表
- 平台执行配置

但不能把策略代码重新耦合回券商 env。

## `weight -> value` 规则

当 `weight` 策略跑在 value-native 平台上时：

1. 先确定翻译基数
   - 默认用 `portfolio_snapshot.total_equity`
   - 如果以后某个平台要改成更窄的执行基准，必须显式写在平台配置里
2. 每个 symbol 的目标金额计算为：
   - `target_value = target_weight * translation_base`
3. 明确为零的目标要保留为零
4. 不要偷偷重归一化策略权重，除非策略契约明确允许
5. 剩余现金处理留在平台层
   - 取整残留
   - 最小交易残留
   - 券商 buying power 限制

## `value -> weight` 规则

当 `value` 策略跑在 weight-native 平台上时：

1. 先确定翻译基数
   - 默认用 `portfolio_snapshot.total_equity`
2. 每个非零目标 symbol 都必须拿到实时价格
3. 目标权重计算为：
   - `target_weight = target_value / translation_base`
4. 明确为零的目标要保留
5. 缺价格时不能默默部分执行
   - 平台应该明确 fail-close 或 no-op，并给出原因

## 现金和残差处理

剩余现金是平台执行问题，不是策略问题。

残差可能来自：

- 整股/整手约束
- 最小成交金额约束
- 券商精度限制
- 实时价格缺失

这些都可以出现在平台诊断里，但不要反推回策略契约。

## 防守/停泊标的

如果策略显式给出 `BIL`、`BOXX` 这类停泊标的，执行翻译必须保留这个 symbol。

除非策略契约明确允许，不要在平台层把它偷偷替换成“本地现金逻辑”。

## 取整和门槛

下面这些事情都属于平台执行层：

- 股数取整
- 是否支持碎股
- 最小交易门槛
- 订单类型
- time-in-force

这些动作必须在 target-mode 翻译之后做。

## 失败策略

如果翻译层没法安全地产出可执行目标，平台必须给出明确的 blocked/no-op 结果。

典型 fail-close 原因包括：

- 必需 symbol 缺实时价格
- 翻译基数为零或非法
- 券商精度/约束不支持当前目标集

这些原因应该体现在平台诊断或 runtime report 里。

## 对当前 runtime-enabled profile 的影响

- `global_etf_rotation`
  - 现在策略契约已经是 `market_history` + `target_mode=weight`
  - `schwab` / `longbridge` 后续需要 `weight -> value`
- `tqqq_growth_income`
  - 现在已经是 canonical `value`
  - `ibkr` 后续需要 `value -> weight`
- `soxl_soxx_trend_income`
  - 现在已经是 canonical `value`
  - `ibkr` 后续需要 `value -> weight`
- `russell_1000_multi_factor_defensive`
  - 目前还是先走 artifact contract
  - 后面做跨平台 rollout 时也会依赖执行翻译支持
- `tech_communication_pullback_enhancement`
  - 路径和 Russell 类似：先 artifact，再执行翻译

## P3 PR 的 review 要点

一个执行翻译 PR 至少要写清楚：

- 改的是哪条翻译路径
- 翻译基数是什么
- 实时价格从哪里来
- 缺价格时怎么处理
- 哪些取整/最小交易规则仍然留在平台层
