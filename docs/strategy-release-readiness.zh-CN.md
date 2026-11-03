# 策略发布就绪门禁

`assess_strategy_release_readiness` 是策略、平台和插件共用的发布前纯函数。它不连接经纪商、不修改参数，也不会部署或下单。

它只在下列条件全部满足时，才允许 `StrategyReleaseReadiness.build_manifest()` 生成可加载的 `StrategyReleaseManifest`：

- 策略配置、风险规则和至少一个插件包均是可读取的普通文件；
- 证据包可验证、明确允许 promotion；
- 证据中的策略 profile 与 source revision 和待发布对象完全一致；
- 发布编号、生效交易日和目标集合符合不可变发布契约。

不满足时返回 `ready: false` 及稳定的、无路径无内容的 `findings`，例如 `evidence_package_missing`、`evidence_not_promotion_eligible` 或 `evidence_revision_mismatch`。此结果可以被监控系统汇总，但绝不能被当作发布身份或交易授权。

插件包的 digest 仅基于已批准文件的内容集合，因此同一包在不同工作目录或平台落地时仍得到相同 identity；本地绝对路径不会进入发布身份。

对 SOXL 等高杠杆策略，缺少正式回测/验收证据时必须停在这个门禁前：允许诊断与补齐证据，不允许纸面重载，更不允许进入 ACTIVE。
