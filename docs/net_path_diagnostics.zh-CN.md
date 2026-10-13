# 同频净收益路径诊断

这是 `REPORT_ONLY` / `DEVELOPMENT_ONLY` 的独立研究摘要；
`no_order=True`、`live_ready=False` 为固定边界。纯函数不读取数据、账户、
账本或配置，不更改已有统一报告、schema、生产依赖 pin、预算或风控。

```python
from quant_platform_kit.research_stats.net_path_diagnostics import (
    build_net_path_diagnostics,
)

# 仅手算合成输入：窗口 NAV 为初始 1、.5、.5、1。
report = build_net_path_diagnostics((-.5, 0., 1.))
assert report.metric("longest_underwater_run_observations").value == 2
assert report.metric("longest_recovered_drawdown_duration_observations").value == 3
assert report.metric("terminal_underwater_run_observations").value == 0
assert report.metric("longest_negative_net_return_run_observations").value == 1
payload = report.to_dict()
```

## 输入与窗口

使用已有 `simple_returns` 校验：同频、净成本、有限简单收益，严格大于 -1，
不能为空。缺失、NaN、无穷、布尔或非法值拒绝整个输入并抛
`ResearchInputError`，不删观察、不补零、不再扣费、不做日期相交或年化。
调用者负责在外层 manifest/timing 中声明真实频率与完整窗口；纯序列 API
不能证明日历连续、来源完整、PIT、真实成本或收益能力。

每次调用独立从归一化 NAV=1 开始，初始点参与峰值，但不增加收益观察数。
`scope=window_only`、`prior_history=unknown`：此前峰值、此前连亏与此前
回撤是否延续均未知。截短窗口再调用会归一化新的起点，不能据此称原有
回撤已经恢复，也不能将窗口最长 run 宣称为账户全历史最长 run。

## 四项计数

所有值的单位固定为 `return_observations`，不是日历天、成交笔数、交易
往返或亏损金额。输出是具有 `status/value/reason_code/details` 的四项 metric。

|名称|定义|
|---|---|
|`longest_underwater_run_observations`|窗口 NAV 严格低于已观测窗口峰值的最长连续收益观察数；恢复观察不属于 underwater。|
|`longest_recovered_drawdown_duration_observations`|已经恢复的回撤中，恢复 index 减最近峰值 index 的最大值，包含恢复观察。若无完成恢复样本，`UNCOMPUTABLE/no_recovered_drawdown/value=None`。|
|`terminal_underwater_run_observations`|窗口末仍低于峰值的连续观察数；未 underwater 为 0。`details.right_censored=True` 表示结束时仍未恢复，不推断未来恢复时间。|
|`longest_negative_net_return_run_observations`|严格负净收益的最长连续观察数；零与正收益均中断。它是周期净收益连亏，不是逐笔亏损交易连败。|

零收益处于 underwater 时继续该 episode；处于峰值时更新最近的同峰
index。达到或超过此前窗口峰值即恢复，并以本期作为最近峰值；多个相同
峰值之间的 plateau 不拉长后来回撤。没有回撤时 underwater/terminal 为
实测 0，而 recovered duration 仍缺失，不能伪造一个零时长恢复样本。

实现只保留相对最近峰值的财富比率，用 `Fraction` 精确乘以 `1 + r`，
其中 r 是已有校验转换的二进制浮点数。这样极小负收益不会因为普通浮点
`1+r == 1` 被当作峰值，极大/极小 NAV 也不需转换为浮点财富值；同峰
比较无 epsilon、四舍五入或人为恢复宽容。例如精确提供的浮点 `-.2`
略小于 -1/5，与 `.25` 复利后仍略低于初始峰值，不能强行判恢复。
若算术失败，三项回撤计数为 `UNCOMPUTABLE/numerical_failure`，终端
右删失状态为 null；独立可观察的 strict-negative 计数仍保留。

独立摘要版本为 `qsl.net_path_diagnostics.v1`；不替代
`qsl.unified_net_report.v1` 或 `qsl.backtest_report.v1`。它不选择模型参数、
尾部预算、交易配对规则、研究晋级阈值或生产恢复条件，也不授权订单。

## 验证

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_net_path_diagnostics.py -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m pytest -q tests/test_net_path_diagnostics.py tests/test_research_stats_import_boundary.py
ruff check .
```

验收仅用合成手算序列，覆盖初始峰值、恢复时长、同峰 plateau、零收益、
未恢复右删失、严格连亏、极小收益、溢出/下溢、窗口截断、输入拒绝、
独立调用及无 numpy/pandas、无网络/子进程的纯函数边界。
