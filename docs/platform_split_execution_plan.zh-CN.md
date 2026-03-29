# 平台拆分执行清单

_核对时间：2026-03-30_

这份文档把当前的平台 / 策略现状，整理成一份可执行的拆分路线。

## 最终目标

### 命名目标

对外运行单元统一用：

```text
{platform}-quant-{strategy}-{scope?}-service
```

示例：

- `interactive-brokers-quant-global-etf-rotation-service`
- `charles-schwab-quant-hybrid-growth-income-service`
- `longbridge-quant-semiconductor-rotation-income-hk-service`
- `longbridge-quant-semiconductor-rotation-income-sg-service`
- `binance-quant-crypto-leader-rotation-service`

运行时内部前缀（例如日志 / Telegram）统一用：

```text
{platform}-quant-{strategy}-{scope?}
```

不要为了形式统一，强行把 `-service` 也塞进所有用户可见前缀里。

调度器命名统一用：

```text
{service-name}-scheduler
```

trigger 命名统一用：

```text
{platform-or-repo}-{strategy}-{scope?}-main-deploy
```

示例：

- `interactive-brokers-quant-global-etf-rotation-service-scheduler`
- `charles-schwab-platform-hybrid-growth-income-main-deploy`
- `longbridge-platform-semiconductor-rotation-income-hk-main-deploy`

### 仓库目标

- 一个平台一个运行仓库
- 一个共享 `QuantPlatformKit`
- 后续策略仓优先按**策略大类**拆，不按 broker 拆

建议的后续策略仓：

- `UsEquityStrategies`
- `CryptoStrategies`

### 策略选择目标

- 加密平台只能选 `crypto` 策略
- 美股平台只能选 `us_equity` 策略
- 平台仓通过配置选择策略
- 可复用的策略实现最终应从平台仓里抽出去

## 当前离目标还有多远

### 已经很接近的部分

- IBKR / Schwab / LongBridge 的 Cloud Run service 命名已经很接近最终格式
- `us_equity` / `crypto` 两个策略大类已经明确
- 每个平台仓库都已经有 `STRATEGY_PROFILE`
- 公共策略契约已经在 `QuantPlatformKit`

### 走到一半的部分

- 平台仓已经会做大类 / profile 校验，但每个平台现在实际上还是只支持一个真实 profile
- LongBridge、IBKR 的运行时命名已经大致理顺，但 `-service` 这条最终规则还没有完全统一
- `BinancePlatform` 已完成改名；后面剩下的是策略/代码层拆分，不是仓库命名

### 还差得比较远的部分

- 还没有独立策略仓
- 平台仓现在还是直接 import 本地策略实现
- 改 `STRATEGY_PROFILE` 还不会去加载独立策略包
- 美股平台之间还不能真正共享同一个生产策略实现包

## 分阶段执行

### 阶段 1：先定死命名规则

目标：

- 把运行单元、运行时前缀、scheduler、trigger 的命名规则固定下来

任务：

1. 在文档里定 Cloud Run / VPS 服务名规则
2. 在文档里定运行时前缀规则
3. 在文档里定 scheduler / trigger 命名规则
4. 这一阶段不动 GCP project id

验收标准：

- 文档里已经明确最终命名规则
- 对 `-service` 的使用边界没有歧义

### 阶段 2：补齐平台仓命名

目标：

- 所有平台运行仓库都统一成平台名风格

任务：

1. 保持 `BinancePlatform` 作为当前运行仓库名
2. 继续让 Oracle/VPS dispatch、runner、本地工作目录和新仓库名一致
3. 后续再进入策略拆分

验收标准：

- 所有运行仓库都遵循平台命名风格

### 阶段 3：把运行服务名统一到最终格式

目标：

- 把 live 运行单元统一到 `...-service` 规则

任务：

1. 改 IBKR Cloud Run service 名
2. 改 Schwab Cloud Run service 名
3. 改 LongBridge HK / SG Cloud Run service 名
4. 给 Binance 的 VPS 运行单元定义正式服务名
5. 同步 scheduler / trigger / URL / audience
6. 同步文档和运行清单

验收标准：

- 所有 live 运行单元都符合最终服务名规则
- scheduler 和 trigger 也统一到同一套命名风格

### 阶段 4：先建策略仓骨架

目标：

- 先把平台仓 / 策略仓的边界搭出来，但不一次搬走所有策略代码

任务：

1. 建 `UsEquityStrategies`
2. 建 `CryptoStrategies`
3. 选定打包 / 发版方式
4. 选定平台仓如何依赖策略包

验收标准：

- 两个策略仓真实存在
- 已经明确包管理和版本流转方式

### 阶段 5：先迁第一批真实策略实现

目标：

- 先挑最适合的策略，验证“平台仓 + 策略仓”这条链路真的能跑

建议第一批：

- `global_etf_rotation` -> `UsEquityStrategies`
- `crypto_leader_rotation` -> `CryptoStrategies`

不建议第一批就迁：

- SOXL / TQQQ 相关策略
- 平台耦合特别重的运行逻辑

验收标准：

- 至少有一个 `us_equity` 策略和一个 `crypto` 策略能从平台仓外部加载

### 阶段 6：让平台仓真正按 profile 选外部策略

目标：

- 让 `STRATEGY_PROFILE` 真的去选择外部策略实现

任务：

1. 需要时扩展共享策略契约
2. 从领域策略包里加载实现
3. 继续保留平台 / 大类兼容性校验
4. 平台自己的 runtime config 仍然放在平台仓里

验收标准：

- 改 `STRATEGY_PROFILE` 能选择受支持的外部策略实现
- 不支持的大类 / profile 组合仍然 fail-fast

### 阶段 7：逐步迁后续策略

目标：

- 第一批跑通后，再把其他策略逐步迁出去

建议顺序：

1. `hybrid_growth_income`
2. `semiconductor_rotation_income`
3. 最后再评估 SOXL / TQQQ 相关策略

验收标准：

- 后续迁出的策略，确实值得放到共享策略仓
- 平台仓里只保留还平台强耦合的策略实现

## 执行原则

每一步都按这个顺序做：

1. 先查代码和当前运行状态
2. 做最小、最安全的修改
3. 做本地或线上验证
4. 验证符合这一阶段目标后再 push
