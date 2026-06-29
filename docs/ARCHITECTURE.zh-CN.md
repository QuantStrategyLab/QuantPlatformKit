# QuantStrategyLab 架构设计

> 本文档是 QuantStrategyLab 所有仓库的架构设计规范。新增、修改平台、策略、插件必须遵守本文档。

## 1. 系统分层

```
┌──────────────────────────────────────────────────────────┐
│  执行层 (Execution Layer)                                 │
│  SchwabPlatform / IBKRPlatform / LongBridgePlatform      │
│  BinancePlatform / FirstradePlatform                     │
│  部署: Cloud Run (GCP) / GitHub Actions + VPS            │
├──────────────────────────────────────────────────────────┤
│  策略层 (Strategy Layer)                                  │
│  UsEquityStrategies / HkEquityStrategies                 │
│  CnEquityStrategies / CryptoStrategies                   │
│  QuantUsComboStrategies / QuantHkComboStrategies         │
│  发布: pip wheel, 版本锁定在 requirements.txt             │
├──────────────────────────────────────────────────────────┤
│  快照层 (Snapshot Layer)                                  │
│  UsEquitySnapshotPipelines / HkEquitySnapshotPipelines   │
│  CnEquitySnapshotPipelines / CryptoLivePoolPipelines     │
│  产出: GCS artifacts → 执行层消费                         │
├──────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure Layer)                        │
│  QuantPlatformKit / QuantRuntimeSettings                 │
│  QuantStrategyPlugins / MarketSignalSources              │
│  提供: 共享契约、适配器、运行时工具、通知                  │
└──────────────────────────────────────────────────────────┘
```

## 2. 数据流

```
策略定义 (pip 包, strategy catalog)
  → 平台策略注册 (strategy_registry.py, capability matrix 过滤)
    → 快照管线 (如需要, 产出 GCS 产物)
      → 运行时适配器 (StrategyRuntimeAdapter)
        → 平台执行 (fetch data → compute signals → submit orders)
          → 执行报告 (GCS + Cloud Logging)
            → 监控调度 (monitor-dispatch: probe + dry-run)
```

## 3. 核心设计原则

### 配置唯一数据源

每个平台服务只有一个权威配置入口 `RUNTIME_TARGET_JSON`。所有引用策略名、平台名的其他配置值都从这里推导。

### Scheduler 时区 = 市场时区

Scheduler cron 的时区必须等于策略对应的市场时区，不是 Cloud Run 服务部署区域。

### 策略跨平台兼容

策略在共享包中声明 `compatible_platforms`，平台通过 capability matrix 自动过滤。

### 配置自动同步

启动时，config-sync 层自动检查并修正 plugin mounts 和 monitor targets 中的策略名引用。

## 4. 命名规范

| 类型 | 规范 | 示例 |
|---|---|---|
| 平台 ID | 小写+下划线 | `schwab`, `longbridge` |
| 策略 profile | 小写+下划线 | `soxl_soxx_trend_income` |
| GCP 服务名 | 小写+连字符 | `charles-schwab-quant-service` |
| pip 包名 | 小写+连字符 | `us-equity-strategies` |
| Python 包名 | 小写+下划线 | `us_equity_strategies` |

## 5. 详细规范

请参考 `DESIGN_SPEC.md` —— 包含完整的平台/策略/插件开发规范、配置管理、调度监控、安全部署和检查清单。

## 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-06-30 | 初始版本 |
