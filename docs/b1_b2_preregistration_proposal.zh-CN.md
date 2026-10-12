# B1/B2：连续波动率与回撤缩放研究的预注册草案

状态：**PROPOSAL / NOT_FROZEN / OWNER_APPROVAL_REQUIRED**。对应复利审计
报告第 5 页 HAR-RV 建议及第 10 页 B1/B2 任务，只提出离线研究设计。
最终模块与正式预注册应位于 UES `research/`；本 QPK 文档是跨库测量
合同的评审草案，没有研究代码、真实数据计算、holdout 冻结或账本写入。
所有未来结果固定 `DEVELOPMENT_ONLY`、`live_ready=False`、`no_order=True`，
只能建议封顶或降低预算。不得新增 B4 Bayesian Kelly、B5 调仓带或其他候选。

English scope: proposed B1/B2 preregistration only, not frozen or executed.
Existing approvals do not authorize these new studies. No live policy, risk
limit, real-data trial ledger or holdout is changed. Any result remains a
development-only cap note, never an allocation increase or execution authority.

## 现有依据与依赖

读过现有 UES [RS-04 预注册](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/7165a5406bf37977481a19fbc03807bd0d52847c/docs/research/fractional_kelly_preregistration.zh-CN.md)、
[评估器](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/7165a5406bf37977481a19fbc03807bd0d52847c/src/us_equity_strategies/research/fractional_kelly_walk_forward.py)
及[累计账本](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/7165a5406bf37977481a19fbc03807bd0d52847c/docs/research/kelly_trial_ledger.json)。
旧 RS-04 记录的批准仅属于其既有候选、变体、窗口与版本；不能转授
新 B1/B2。旧文件中的实盘配置是历史取证，不是本次对当前运行的证明。
其已见历史只能继续标 development，不能换名成为未触碰 OOS。

正式计算前须验证并绑定研究版本：A2 QPK 成交/成本模型、A2 UES adapter、
A3 指标语义与 B3 报告。当前候选分别见
[QPK #663](https://github.com/QuantStrategyLab/QuantPlatformKit/pull/663)、
[UES #587](https://github.com/QuantStrategyLab/UsEquityStrategies/pull/587)、
[A3 #662](https://github.com/QuantStrategyLab/QuantPlatformKit/pull/662)、
[B3 #664](https://github.com/QuantStrategyLab/QuantPlatformKit/pull/664)。
PR 或 CI 绿色不等于研究环境已安装该版本，也不证明相互叠加后的合同。
未来在隔离研究环境使用已核验的 immutable commit / lock / artifact；
依赖缺失或未合并组合尚未验证时 `PARKED`，不改生产 pin。

## B1：连续波动率目标与分数 Kelly

拟议问题：在相同完整策略路径、时点、窗口、现金与成本下，连续波动率
缩放能否改善净对数增长及风险，且是否优于既有分数 Kelly/固定 50%？
先逐条策略研究 SOXL/TQQQ，不把两个标的拼接成一条收益，也不擅自
把联合账户 R8 结果拆成单策略基准。具体 profile 与 variant 须重新批准；
存在不可复现插件时不伪称 live parity，可审批明确命名的 core-only 研究。

| 预注册候选/对照 | 拟议定义与边界 |
| --- | --- |
| 固定 50% | 资金暴露目标 0.5，其余现金；经过同一既有风险上限裁切，报告实际暴露，不能因“基准”豁免限额 |
| 四分之一 / 半 Kelly | 保持 RS-04 的训练窗均值收缩/样本方差定义，`c` 仅 `{0.25, 0.5}`；一次应用 fractional，不能重归一化满仓 |
| EWMA 连续波动目标 | 仅用截至决策时已知收益，`v_next = lambda*v_current + (1-lambda)*r_t²` 的零均值方案；初值、预热及 lambda 待批准 |
| HAR-RV 连续波动目标 | 日/周/月 realized variance 特征对下一期 RV 回归；拟采用训练窗 OLS，精确窗口、预热、重拟合节奏待批准 |
| 波动目标与 Kelly cap 的组合 | `w=min(existing_cap, clip(target_vol/forecast_vol,0,1), clip(c*f_star,0,1))`；仅在批准候选列表中作为独立比较行，不把 c 当额外满仓归一化系数 |

上述 `existing_cap` 是本研究作用域已批准风险/仓位/产品/现金上限的
共同最小值；单位为资金暴露。不能把 QPK `bet_loss_risk_share` 的旧字段
直接当暴露，单位与换算见[Kelly 契约](kelly_contract_v2.zh-CN.md)。
forecast_vol 和 target_vol 必须同一预测期、同一收益定义和单位。
目标波动、EWMA decay、HAR 窗口/模型变体/重拟合周期均 **PENDING**；
不能依据 holdout 或主比较结果选它们。候选笛卡尔积须显式列出、审批后
计入试验数，不能隐含自动扫描。纯波动目标与组合方案是否都执行，
须在最终候选列表中决定；不在看到结果后删除不理想的方案。

EWMA 递推依据
[J.P. Morgan/Reuters《RiskMetrics Technical Document》](https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a)
第 5.2.1 节。HAR-RV 依据
[Corsi (2009), A Simple Approximate Long-Memory Model of Realized Volatility](https://doi.org/10.1093/jjfinec/nbp001)。
这些来源支持候选形式，不保证适用于杠杆 ETF 或能跑赢对照。
真正 RV 要有授权的日内数据、采样规则、时区/交易时段、清洗与可用时点
合同。只有日线时不能把一天 close return 的平方冒称日内 RV；若批准
daily proxy，必须另命名、另登记并注明局限，否则 HAR-RV `PARKED`。
预测非有限、非正、缺历史或拟合失败时不取无限暴露，不自动换预测器；
按冻结的无新风险/现金处置规则处理，完整保留失败次数。

## B2：连续 drawdown / cushion 对照

拟议问题：在同一策略、基础 sizing 与既有风险上限下，连续縮放相比
既有 `{0,0.5,1}` 阶梯是否降低边界换手/摩擦并改善净增长与尾部风险？
B2 单独比较，不默认执行 B1×B2 全组合；组合研究须另列候选并批准。

设决策时已知的净 NAV 为 `W>0`，含初始 NAV 的历史峰值为 `M>=W`，
正损失回撤 `d=1-W/M`。`D_max` 必须来自本研究作用域的已审定限额，
不得拿更宽的新阈值替代；`alpha=1-D_max`。

| 候选 | 拟议缩放因子（仅离线研究） |
| --- | --- |
| 现有阶梯 | 原作用域现有阈值/边界语义原样保留，不重调档位 |
| 线性回撤缩放 | `clip(1-d/D_max,0,1)` |
| normalized cushion | `clip((W-alpha*M)/(D_max*W),0,1)`，峰值时为 1，达到已定 floor 时为 0 |

两条连续函数均为**待批准候选**；normalized cushion 是按审计缓冲思想
归一化的离散研究变体，不是连续时间最优策略的实现或保证。
审计所引理论来源为
[Grossman、Zhou (1993), Optimal Investment Strategies for Controlling Drawdowns](https://onlinelibrary.wiley.com/doi/10.1111/j.1467-9965.1993.tb00044.x)。
离散成交、跳空、成本与数据缺失可越过 floor，须报告突破，不能宣称硬回撤保证。

具体例子仅用于合同核对：[现有 QPK risk gate](../src/quant_platform_kit/risk/gate.py)
的 TQQQ evidence mandate 为 `d<=0.05 → 1`、`0.05<d<=0.10 → 0.5`、
`d>0.10 → 0`，并保留 TQQQ nominal 0.15 / effective 0.45 等上限。
[sizing helper](../src/quant_platform_kit/position_sizing.py) 的有关现有 mandate
还拒绝非阶梯值。不得把连续因子塞入这些合同、改变 5%/10% 边界或
放宽限制；未来连续计算必须是研究内部函数，输出另标研究目标，保持
所有已审定硬 gate 和 cap。超出限额、旧 breaker、风险 veto 优先，
候选连续因子不得覆盖它们，其他作用域亦不能照搬 TQQQ 阈值。

`W/M` 的更新必须使用本路径截至决策时的净 NAV，不能看当天尚未可用
的成交后收益；holdout 的峰值状态如何从训练/观察延续须预先约定。
成本反馈、现金流、公司行动、重新启动峰值和停放后的恢复规则必须
冻结；不能在亏损后重置 M 来解除回撤。未来新规则也不能绕过 kill switch。

## 共同数据、测量与因果时点

拟沿用旧 RS-04 的 XNYS、252/63/5 滚动 train/test/purge 和
5/10/15 bps 单边成本作为**待批准对照方案**，不是已冻结的新研究参数。
任何 embargo、窗口、费用组成、现金腿、variant 与分折规则变化必须
进入新登记。各行用精确相同的测试会话；遗漏、预热与尾部未覆盖会话
单独计数，禁止静默取日期交集、补零或删掉亏损/缺报价日。

主成交候选为 completed-close signal → `next_close`；`next_open` 可作
明确登记的敏感性，`same_close` 只能注明假设性的研究敏感性，不能声称
收盘后信号可在同一收盘前成交。遵守
[A2 纯模型](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/5c0693c8735f5ed04c8943ab1fab00c82496b22c/src/quant_platform_kit/research_stats/execution_models.py) 与
[UES adapter](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/7165a5406bf37977481a19fbc03807bd0d52847c/src/us_equity_strategies/research/execution_model_adapter.py)
的可用索引/真实 fill 时点；结合
[A1 #373](https://github.com/QuantStrategyLab/BinancePlatform/pull/373) 已审计
原则，禁止借 forward-fill 伪造成交，终端未成交和延期风险退出分别记录。
A1 是 Binance 回测修复，不证明 UES 全部策略已经具备相同实现。

A2 adapter 目前仅单证券、零收益现金、合成或一致的复权 OHLC，成本为
独立 NAV overlay，不反馈 gross 目标权重；不能当成 raw OHLC/公司行动、
真实 BOXX 现金、多资产插件已实现。若研究需要这些能力，先补合同与
适配验证，否则 `PARKED`。成交手续费/滑点按 pre-fill NAV 的交易名义额
逐边收取，买卖各一次，不重复扣策略内部已净成本。开盘费前/收盘费后
顺序与模型一致，terminal fill 的费用不能因移到下一日而丢失。

数据 manifest 需冻结：源/许可、获取时间、文件与内容 SHA-256、标的、
时区/日历、raw/split/total-return 价格口径、公司行动可用时点、现金
总收益口径、预热/训练/测试边界、完整性与缺失策略。历史窗口、依赖
源码 SHA、研究 runner/参数摘要、lock 和安装版本分别保存，不能只记 PR。
未来 holdout 的边界、内容 hash 与隔离管理员目前 **NOT_ASSIGNED**；
不得填写假的 hash 或把已见的旧 development 历史重标 holdout。

## 终点、统计与多重检验

主终点拟为同一会话净对数增长相对固定 50% 的 paired difference。
按[B3 报告](unified_net_report.zh-CN.md)输出八项：净 g、同频未年化 Sharpe
`ddof=1`、PSR、累计试验 DSR、MinTRL、fractional-tail CVaR95、含初始
NAV 的最大回撤及同路径 gross/net 成本拖累。不同仓位路径间的增长差
不能当作成本 drag。CVaR 和回撤为负损失口径；不可计算保留原因/None。
辅助报告 turnover、成本档位、预测误差、风险/缺失/停放/未成交计数。

paired stationary bootstrap 的目标统计量、block 规则、种子与次数，
PBO/Ledoit-Wolf 的既有使用范围、PSR/DSR 基准及 MinTRL 假设必须在审批
时指定。指标角色须先列为 ranking/report/veto；效应大小、概率门槛和
风险阈值当前 **PENDING**，不将默认估计参数误作通过标准。

新研究批准后，按审计在 UES `kelly_trial_ledger.json` 新增研究条目并
增加真实累计试验数：全部候选、参数变体、失败/拒绝/终止及必要敏感性
按预注册计数规则登记，不只把整个参数扫描算“加一”。预定成本档位
是否属于报告场景或独立选择试验须先声明；出现据此选择就须纳入计数。
不能降低有效试验数、删除失败行或仅用当前批次做 DSR。现有文件的 48
是该版本声明，不能冒称本次核验后的当前总数。DSR 的累计同频净 Sharpe
样本方差与账本摘要须独立验证，B3 caller-supplied digest 不是真实性证明。
本草案没有新增 trial，也未读写授权私有账本。

## 合成验收与批准/停止规则

未来合成检查拟显式 seed `20261013` 并记录 RNG/环境版本：常量和突变
方差的因果响应；修改未来 bar 不影响此前预测/权重；缺报价/无预热/
非有限输入停放；full Kelly 拒绝；单调 cushion 与边界为零；旧 hard gate
优先；漂移权重与现金/成交/成本对账；terminal 无 fill 和终端 close 成本；
相同种子重现与 B3 指标解析算例。**本次没有执行这些未来检查**。
合成 PASS 只证明实现合同，不能证明真实 edge 或允许访问私有数据。

正式运行前分别取得预注册批准与真实数据运行批准，验收记录至少包含
proposal/prereg id 与摘要、批准者身份/时间/有效期、候选和参数完整列表、
limit 来源/摘要、数据/窗口/holdout 身份、精确依赖/runner SHA、指标角色/
阈值、累计试验计数规则、私有运行位置与输出权限、停止/review 职责。
目前这些新批准、真实 holdout 和运行证据均 **NOT_APPROVED / UNKNOWN**。

任何身份漂移、泄漏/未批准数据、成本/时点对账失败、旧限额突破或研究
环境合同缺失，停止研究并保留失败记录，结果 `PARKED/UNCOMPUTABLE`。
修复后登记新版本/新试验，再获批准，不改冻结候选来救结果。回退仅
指撤回研究报告/隔离研究 artifact 或回到已审阅研究版本，不自动回滚
生产配置、解除 breaker、修改预算或启用策略。真实 promotion 另走
已有 owner 验收与授权流程；本草案不取代运营与统计双门槛。
