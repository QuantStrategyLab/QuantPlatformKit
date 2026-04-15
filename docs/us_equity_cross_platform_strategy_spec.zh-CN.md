# 美股策略跨平台设计规范

## 目标

所有美股策略都应该做到“一套策略代码，尽量在当前三个券商运行时复用”：

- `ibkr`
- `schwab`
- `longbridge`

这份文档定义两件事：

- 以后新增美股策略必须遵守什么规则
- 现有策略最终要往什么方向迁移

## 适用范围

这份规范适用于：

- `QuantPlatformKit`
- `UsEquityStrategies`
- 消费它们的美股平台仓库

它不负责定义券商鉴权、Cloud Run 部署、调度器配置，也不规定
Telegram 文案细节。

## 总原则

策略代码必须平台无关。

也就是：

1. 策略仓库只声明自己要什么输入、输出什么仓位意图
2. 平台仓库负责把运行时数据整理成这些输入
3. 策略仓库返回标准 `StrategyDecision`
4. 平台仓库把 `AllocationIntent` 翻译成自己的下单方式

策略代码里不能按平台分支。

## 必须有的四层

### 1）策略定义层

每条美股策略都必须明确声明：

- canonical profile
- 展示元数据
- `target_mode`
- `required_inputs`
- 支持的平台
- entrypoint

### 2）runtime adapter 层

每个支持的平台都必须有一份 `StrategyRuntimeAdapter`。

adapter 可以描述：

- 可用输入
- 可用能力
- 哪个输入当作 `portfolio`
- artifact 校验约束
- 迁移窗口里确实还需要的少量运行时元数据

但 adapter 不能把券商专属下单细节塞回策略层。

### 3）平台输入构建层

平台仓库负责把券商数据、账户数据、行情数据整理成标准输入。
策略只消费标准输入，不关心这些数据从哪个券商来。

### 4）执行翻译层

平台仓库负责把统一 allocation 意图翻译成自己的原生执行方式：

- `ibkr`：原生偏 `weight`
- `schwab`：原生偏 `value`
- `longbridge`：原生偏 `value`

策略本身不能去做券商专属执行转换。

## 统一输入枚举

以后新增美股策略，`required_inputs` 只能从下面这些 canonical 名字里选：

- `market_history`
- `benchmark_history`
- `portfolio_snapshot`
- `derived_indicators`
- `feature_snapshot`

现在仓库里还存在一些旧名字，迁移期间平台仓库可以保留映射层；
但新策略从第一天开始就应该用 canonical 名字，不要继续发散。

### 各输入的含义

- `market_history`：用于轮动、排序、风控的市场历史数据
- `benchmark_history`：单独的基准历史，比如 `QQQ`、`SPY`
- `portfolio_snapshot`：当前持仓、现金、市值、账户状态
- `derived_indicators`：平台侧预计算好的 regime / indicator 包
- `feature_snapshot`：带 schema/version/freshness 约束的特征快照工件

## 策略输出规范

美股策略只能输出：

- `StrategyDecision`
- 由它派生出来的 `AllocationIntent`

不能直接输出这些平台专属内容：

- 券商订单字段
- UI 排版字段
- 通知布局字段
- 服务运行状态写入字段

这些都必须放在平台仓库里处理。

### `target_mode`

每条策略必须明确只有一种 `target_mode`：

- `weight`
- `value`

不能一条策略里混用两种模式。

策略只负责声明自己的目标语义；
平台仓库负责在必要时做 `weight/value` 翻译。

## Artifact 规范

如果策略依赖 artifact，例如 feature snapshot，就必须声明清楚：

- artifact 类型
- schema 版本
- 新鲜度规则
- 是否需要 manifest / checksum

平台仓库负责：

- artifact transport
- 存储路径或 URI
- 新鲜度校验
- 注入到 `StrategyContext`

策略层不能假设某个平台本地一定有某个文件。

## 三平台支持规则

以后新增美股策略，默认目标应该是三平台都能接：

- `ibkr` adapter
- `schwab` adapter
- `longbridge` adapter

如果某个平台当前明确不支持，PR 里必须写清原因；
在问题没补齐前，该平台上应该保持 `eligible=false`。

## `eligible` 和 `enabled` 要分开

这两个状态不能混：

- `eligible`：理论上平台能跑
- `enabled`：当前 rollout 真的打开

`eligible` 应该由契约推导出来：

- domain 匹配
- `target_mode` 平台能支持或能翻译
- 平台能提供所需输入
- runtime adapter 存在
- capability 满足

allowlist 只影响 `enabled`，不要再手写一堆“这个策略天生只能跑某平台”的散规则。

## 新策略的完成标准

一条新的美股策略，至少满足下面这些条件才算 ready：

1. metadata 和 canonical profile 注册完成
2. manifest 和 entrypoint 完成
3. `target_mode` 明确
4. `required_inputs` 使用 canonical 枚举
5. 为目标平台补齐 runtime adapter
6. allocation contract tests 通过
7. platform adapter tests 通过
8. 每个 enabled 平台至少有一条 dry-run smoke path

## Review checklist

如果 PR 里出现下面这些情况，应该直接打回：

- 策略代码按平台分支
- 策略代码直接读券商 env
- 策略输出里混入券商专属订单字段
- 新造了一个临时 `required_inputs` 名字
- `target_mode` 缺失或混用
- artifact 依赖没有 schema / freshness 校验

## 当前策略的迁移目标

现有 runtime-enabled profile 可以分步迁移，但目标状态应该是：

- `global_etf_rotation`
  - 通过标准历史数据输入 + `weight/value` 翻译实现跨平台
- `tqqq_growth_income`
  - 通过基准/账户输入 + `value/weight` 翻译实现跨平台
- `soxl_soxx_trend_income`
  - 通过指标/账户输入 + `value/weight` 翻译实现跨平台
- `russell_1000_multi_factor_defensive`
  - 通过标准化 `feature_snapshot` artifact contract 实现跨平台
- `tech_communication_pullback_enhancement`
  - 通过标准化 `feature_snapshot` artifact contract 实现跨平台
- `mega_cap_leader_rotation_dynamic_top20`
  - 通过标准化 `feature_snapshot` artifact contract 实现跨平台
- `dynamic_mega_leveraged_pullback`
  - 通过标准化 `feature_snapshot` artifact contract，加标准 market、benchmark 和 portfolio 输入实现跨平台

以后新策略应该直接朝这个目标写，不要再新增一堆一次性的运行时契约。
