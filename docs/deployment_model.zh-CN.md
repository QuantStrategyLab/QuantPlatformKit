# 部署模型

## 结论

- `QuantPlatformKit` 是共享平台代码仓库，**不单独部署**。
- `InteractiveBrokersPlatform`、`CharlesSchwabPlatform`、`LongBridgePlatform`、`BinanceQuant` 这些仓库才是实际运行单元。
- 策略仓库应该固定依赖某个 Git tag，不要直接依赖 `main`。

如果要看当前线上真实运行清单，包括仓库、项目、服务、scheduler、runtime identity、secret 名称，见 [`platform_runtime_inventory.zh-CN.md`](./platform_runtime_inventory.zh-CN.md)。

如果要看 `QuantPlatformKit`、平台运行仓库、未来策略仓库三者的职责边界，见 [`platform_repo_boundaries.zh-CN.md`](./platform_repo_boundaries.zh-CN.md)。

如果要看当前的平台 / 策略大类 / live profile 对照表，请看 [`platform_strategy_matrix.zh-CN.md`](./platform_strategy_matrix.zh-CN.md)。

## 仓库职责

### 平台仓库

- `QuantPlatformKit`
  - 统一领域模型
  - broker 适配层
  - 通知和少量通用工具
  - 公共策略契约（策略大类、profile、平台兼容关系）

### 运行仓库

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `BinanceQuant`

这些仓库现在负责：

- 策略规则
- 执行编排
- 运行入口
- 各自部署配置
- 运行时身份和环境变量读取

### 未来策略仓库

如果后面决定把策略实现真正拆出去，策略仓库应只负责：

- 可复用的策略计算
- 域内参数
- 尽量平台无关的 allocation / signal 逻辑

不应该负责：

- Cloud Run 入口
- broker 登录
- scheduler
- 平台运行时 secret

### 基础设施仓库

- `IBKRGatewayManager`
- `SchwabTokenAutoRefresher`

它们不属于策略执行仓库，也不属于平台包。

## 依赖方式

策略仓库应该固定依赖某个 tag，例如：

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.5.0
```

不要用：

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@main
```

原因：

- 构建可重复
- 回滚简单
- Cloud Run / VPS 的部署单元不需要感知两个源码仓库

## 发布顺序

每次平台层改动建议按这个顺序走：

1. 在 `QuantPlatformKit` 完成改动并跑测试
2. 推送到 `main`
3. 打新 tag
4. 在策略仓库里升级依赖到新 tag
5. 再让策略仓库触发自己的构建或部署

## 部署单位

### Cloud Run

Cloud Run 继续只部署运行仓库，不部署 `QuantPlatformKit`。

推荐服务名：

| 仓库 | 推荐服务名 |
|---|---|
| `InteractiveBrokersPlatform` | `interactive-brokers-quant-global-etf-rotation-service` |
| `CharlesSchwabPlatform` | `charles-schwab-quant-hybrid-growth-income-service` |
| `LongBridgePlatform` | `longbridge-quant-semiconductor-rotation-income-hk-service` / `longbridge-quant-semiconductor-rotation-income-sg-service` |

如果后面同一平台下再增加第二套相近策略，可以用：

- `interactive-brokers-quant-rotation`
- `interactive-brokers-quant-income`

但前提是它们共享大部分代码路径。不要一开始就把完全不同的策略塞进同一个服务里靠参数切换。

### VPS / self-hosted runner

`BinanceQuant` 继续走现有 self-hosted runner + 外部调度。

推荐运行单元名：

- `binance-quant-crypto-leader-rotation-service`

## 参数化边界

可以参数化的：

- `IB_GATEWAY_MODE`
- `ACCOUNT_PREFIX`
- `SERVICE_NAME`
- `NOTIFY_LANG`
- 同策略族里的 `SERVICE_VARIANT` / `STRATEGY_PROFILE`

不建议参数化的：

- 完全不同的策略体系
- 完全不同的持仓模型
- 完全不同的调度周期

更推荐：

- 同仓库
- 不同服务
- 不同 env

而不是一个服务里塞很多 `if STRATEGY == ...`。

## Google Cloud Trigger / Cloud Build 处理规则

如果以后改了 GitHub 仓库名或 owner，Cloud Build / Cloud Run 的 GitHub 来源一般需要重新选。

建议步骤：

1. 先记下原来的：
   - trigger 名
   - region
   - branch
   - target service
2. 到 GCP 控制台删除旧的 GitHub 来源绑定，或者直接重建 trigger
3. 重新选择新的仓库路径
4. 检查 branch 还是不是 `main`
5. 检查目标 `service` 和 `region` 有没有变
6. 手动跑一次构建
7. 确认新 trigger 正常后，再删旧 trigger

### LongBridge 双服务

`LongBridgePlatform` 的 HK / SG 继续保持：

- 同一个策略仓库
- 两个 Cloud Run 服务
- 两个 trigger
- 两个 GitHub Environment

区分方式始终是：

- `CLOUD_RUN_SERVICE`
- `CLOUD_RUN_REGION`

## 改仓库名时的建议

如果只是为了让组织结构更清楚，先改：

- GitHub 简介
- topics
- README

仓库名可以放后面统一处理。  
原因是仓库名改动会影响：

- Cloud Build trigger
- Cloud Run GitHub source deploy
- 本地 git remote
- 文档里的 clone 地址

## 一句话规则

- 平台共享代码进 `QuantPlatformKit`
- 平台运行仓库继续作为部署单元
- GCP / VPS 只部署平台运行仓库
- 版本靠固定 tag 管理
