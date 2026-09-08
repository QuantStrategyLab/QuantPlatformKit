# 冻结研究输入的本地恢复

本轮在既有 research promotion ticket 上保存本地阶段进度。没有增加队列、排班或交易入口。基线为 QPK `d12309d`。

## 调用与归属

策略仓先验证真实输入、冻结窗口及 runner，再调用现有
`run_actionable_research_promotion`，增加两个参数：

- `ticket_dir`：调度者提供的、重启后仍保留的票据目录。
- `research_identity`：包含下列五个非空字符串的 mapping。

| 字段 | 必须绑定的实际材料 |
| --- | --- |
| `code_revision` | 实际执行的冻结策略代码版本 |
| `input_revision` | 已验证的冻结输入根，包括开发、WFA、锁定 OOS 的窗口和来源 |
| `param_space_revision` | 基线参数、固定参数和允许搜索的参数空间 |
| `cost_model_revision` | 完整费用与执行假设，包括最低佣金、成交参与率、lot 等适用设置 |
| `validator_revision` | 实际严格 validator、promotion plan 和阈值版本 |

复用已有 manifest/config 的根或真实版本号。QPK 不会把调用者填写的字符串当作输入已验证的证明；这些材料须在策略仓构造回调时验证并固定。修改其中任一材料必须修改对应 revision。

回调接口保持：`optimize(drift, budget) -> OptimizationProposal`、
`enforce_backtest_gates(proposal) -> PromotionBacktestRun | Mapping`、
`record_shadow(proposal) -> Mapping`。
可选 `diagnose(drift, budget) -> Mapping` 返回既有
`optimization_needed` 决定；AI 意见仍不能替代任何严格门或人工决定。
可选 `pull_console(ticket_id)` 使用原 QRT 读取接口。

可选 `admit_new_research(ticket_dir: Path, created_at: str) -> bool` 由实际调度者提供，正常周期与 runner 均向下传递。仅在持有同一目录锁且确认该身份没有票据之后、首次保存和 AI 调用之前执行；只有字面值 `True` 放行，异常返回 `research_admission_unavailable`，其他值返回 `new_research_not_admitted`，两者都不创建票据或调用阶段。`created_at` 是本次新票据实际持久化的同一个 UTC 时间。已有票据恢复不再次准入；回调不可重复获取该目录锁。AAB 可据已有票据的 `created_at` 实现每日新实验限额，坏记录和未知计数必须拒绝放行；QPK 不另建计数存储，也不在此实现调度者的每日政策。

正常 `run_auto_pilot_cycle(..., research_identity=...)` 已接入此入口，以
`store.local_root/research_promotion_tickets` 保存进度。未提供冻结身份或持久目录时，自动研究在 AI 前返回 `research_identity_unavailable`。
正常周期发现尚未开始同步的 awaiting checkpoint 时，使用 `resume_delivery_only` 路径：必须重新匹配同一冻结身份且票据已经存在，只可回收决定或继续首次同步；不得借此创建新票据或运行 AI/回测。其他 pending profile 仍保持跳过。
未传持久化参数的显式 runner 调用保留原接口，不能声称具有跨 run 去重。

QPK 管单次实验的本地进度、严格门与人工决定。AAB 管 AI job、额度准入和实际实验 dispatch；不同 GitHub 临时 runner 或不同目录不会共享 QPK 的锁。跨主机单重任务、每日候选上限和真实任务工件交接须由调度者保证，不由本补丁宣称完成。

## 去重与中断

去重身份包含五个 revision、target/domain、观察日期和 source revision、drift score、基线标识和硬预算。监测器的冷却、升级标记以及可选诊断回调的有无不会生成第二个相同实验。

持久化入口仍要求新鲜、可行动的 drift，绑定优化器、严格 backtest 和 shadow 回调；预算最多 25 次搜索、4 个参数，且必须 paired shadow。缺绑定、过期输入或身份缺失时不会调用 AI。

本地 ticket 增加 `research_progress`，包含身份及各阶段结果；该字段不进入 `to_dict()` 的控制台候选，也不发送给 QRT。保存继续使用临时文件、fsync 和原子替换。完整 proposal（含参数、费用、validation identity）和已完成 backtest/shadow 摘要可恢复；输入原始行和凭据不应作为回调结果传入。

| 保存状态 | 下次行为 |
| --- | --- |
| 某阶段尚未开始 | 从该阶段继续 |
| 某阶段已完成 | 复用结果；严格 WFA/OOS 门仍重新检查后才到 shadow |
| 阶段为 `running` 或 `unknown` | `research_outcome_unknown`，不再次调用该阶段；需要拥有原作业证据的操作方只读查明结果 |
| 明确额度延期 | 保存 `retry_at`；到期前不调用 AI，缺时间或首次收到时已经过期的时间不自动重试 |
| awaiting ticket，尚未开始同步 | 可以继续首次同步，原 sync adapter 仍先 GET 再决定是否 POST |
| 同步已开始但未确认 | 仅 GET 回收；不自动重复 POST，不能把失败当作不存在 |
| awaiting ticket 已有人工决定 | 原身份/参数/证据/权限校验后记录意图 |
| 本地 terminal ticket | 同一身份不重新诊断、优化或提交；新冻结证据可以产生新实验 |

### 长周期 paired shadow 的只读续收

新增可选 `read_pending_shadow(proposal) -> Mapping`，通过正常周期和 actionable runner 传到 saved 入口。首次 `record_shadow` 仍只执行一次；后续只使用这个专用读取回调，不能重复首次可能创建外部观察的操作。AAB 的实际回调读取受控本地 observation，并校验冻结 policy、候选/参数/source、完整 forward 窗口及当期材料有效性。

首次记录或后续读取可以返回 `status=pending`、`passed=false`、`no_order=true`、`live_authority_granted=false` 及未来的有限 Unix `retry_at`。票据保持已有非终态 `shadow_recorded`，本地 shadow 阶段为 pending，对外返回 deferred。到期前零读取；缺失、非有限或回调返回时已过期的 retry_at 保存为 null，不自动轮询。回调明确失败则 PARKED，异常或进程在调用中停止则 unknown，不再次调用。后续仍 pending 时，只更新明确的新期限；不会重跑诊断、优化、严格回测或首次记录。

完成返回 `{"status": "complete", "observation": ...}`。observation 使用既有 `PairedShadowObservation` 或 `collect_paired_shadow_for_promotion` 输入 mapping，包括 policy、当前/前一 receipt 和 paired evidence。QPK 校验 policy 的 profile/domain 和观察数量，并调用原 paired validator 验证本次及前序关联；修复 adapter 二次校验漏传 previous 材料的问题，缺少前序仍拒绝。裸 `passed=true` 不能替代这些材料。完整窗口的真实性、当前可用性以及具体候选参数/source 绑定仍由 AAB 的真实 policy reader 验证，单条合法 receipt 不能证明窗口完成。

新实验仍须通过 7 日 drift 有效期。过期观察只可定位同身份的已有票据：此前要求的诊断、优化、严格回测必须已完成，原 proposal 预算与严格门重新校验通过，且 shadow 为明确 pending，才能续收。刚保存了完整 shadow 结果但尚未来得及组装人工候选的中断，也只复用这个已验证结果。以上两类恢复均不会重调 AI、优化、backtest 或首次 `record_shadow`。身份改变、阶段缺失、unknown、新票据、未来/缺失日期仍拒绝；不通过刷新原 as_of 创建替代实验。正常 auto-pilot、actionable runner 与 saved 入口均保留此限制。

已经到达 awaiting 的同身份票据，也能在原 drift 过期后只读回收控制台决定：要求上述阶段和 shadow 全部完成、原严格门有效、票据候选参数匹配保存的 proposal。此路径只 GET，不再次 POST，不读取 shadow 或运行前置研究。未知提交先读取原票据；接受/拒绝后返回已有终态，不因时间过去而变成新实验。

`research_in_progress` 表示同一目录已被另一进程持有，本次返回 `deferred`；不会等待或发起模型请求。研究、自动决定回收及本地 `research-promotion-decide` CLI 使用同一目录锁。损坏的独立票据不会阻断其他身份；损坏的当前身份不会被覆盖成新研究。

输出沿用 `status/reason/ticket/console_synced`，增加 `research_key`（本地去重键）、`ticket_path`、`resumed`，额度延期时有 `retry_at`。`console_synced=true` 只来自本次同步回调明确确认；恢复 GET 的结果单列 `reconciliation`。任何接受仍只有 intent，`live_authority_granted=false`。

## 验证边界

新增离线回归实际覆盖完成阶段重用、阶段间/阶段中中断、完整 proposal 保存恢复、输入/代码/参数/费用/validator 变更、坏票据隔离、额度延期、未知 POST 只读恢复、首次提交前恢复及人工决定。独立子进程验证目录锁竞争和进程退出后的释放；Windows 分支尚未在 Windows 运行。

使用合成证据和注入回调验证控制流，不等于真实 WFA/OOS、paired forward shadow、模型调用、QRT 生产写入、部署或交易验证。没有修改 frozen artifacts，也没有调用真实 provider。

最终本地结果：新增恢复测试 53 项；恢复/cycle/runner/人工回收/codex integration/CLI/AI provider/freshness/paired shadow/strict orchestrator 共 11 个测试文件，271 tests + 37 subtests 通过；Ruff 与 `git diff --check` 通过。新增准入 10 项覆盖拒绝/异常、锁内执行、UTC 时间一致及已有票据不重复准入，实际先 RED 后 GREEN。测试使用 `/usr/local/bin/python3`、`PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`、禁用 pytest 外部插件和 cache，并阻断真实 socket 连接。

本次还将唯一 reusable drift workflow 的 AAB checkout 固定到 `60bd64a2ae059a082614181eeb845b46df395523`，采用已发布的研究主审 Codex-only、OIDC 和 `promotion_review` 边界。该版本主审显式传 `allowed_providers=["codex"]`，无需额外 provider 环境覆盖。精确引用断言先 RED 后 GREEN，工作流测试 1 项及 actionlint 通过；排班、采集和 validator 未修改。此处仅记录源码采用，实际发布和业务周期由部署方核实。

组合测试显式使用 `TZ=UTC`：既有 freshness 测试的一例采用本地 `date.today()`，生产观察时钟采用 UTC；本机跨日时，不指定 TZ 会先触发 future 拒绝，而非该测试预期的缺 source 拒绝。本轮保留生产 UTC 语义，没有修改该旧测试。

长周期观察增量在已发布分支 `f1e190a` 上新增 27 项离线测试：17 项先 RED，补正常 auto-pilot 和两处保存中断时再复现 3 项 RED；独立审查发现直接策略入口的过期 awaiting 回收被阻断，再用接受/拒绝 2 项 RED 修复，并保留缺阶段/候选错配拒绝。两条真实结构的合成 receipt 验证了多日材料传递，缺少前序、篡改 receipt、裸 passed、未满窗口、live 声明均不通过；没有真实观察数据。新 API 在 actual actionable runner 与正常 auto-pilot 上均验证，CN 的透传采用和 AAB 真实文件 reader 另由对应仓验证。

最终在相同隔离环境、阻断 socket 后，12 个相关测试文件为 298 tests + 37 subtests 通过；Ruff 和 `git diff --check` 通过。没有运行模型、真实 shadow、控制台生产写入或交易。
