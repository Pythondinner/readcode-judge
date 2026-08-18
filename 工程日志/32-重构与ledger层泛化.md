# 重构成Observer/Analysis/Ledger分层，ledger层泛化成通用产物存取

> 2026-08-18

## 背景

用户指出他自己在多个项目里反复验证过一套个人架构范式——Ledger+Observer+Brain+Executor(+Analysis)，读码机对照这套范式，定位是只做Observer+Analysis两块，Brain/Executor刻意不做（`docs/04`已经加了这个映射）。为了让代码结构本身也能直接体现这个映射、方便理解，要求把899行的`report.py`按这套架构拆分。

## 重构

`src/`拆成四个包：
- `sensor/`：agent.py、tools.py、verifier.py、deepseek_client.py、mcp_server.py、agent_mcp.py（读代码的底层能力）
- `observer/`：complexity.py、lizard_complexity.py、behavior.py + 从report.py拆出的narrative.py（项目叙述）、judgment.py（行为对照判断）、consensus.py（一致率测量+改动对比）、iteration_signal.py（分级信号），report.py只保留编排入口
- `analysis/`：diagnosis.py（原report.py的diagnose_and_propose_fix）
- `ledger/`：新建，见下

跨包引用：同包内相对导入，跨包绝对导入（`sensor/`是独立包，`observer/`引用它用`from sensor import agent`）。`run_eval*.py`几个更早期的评测脚本也同步改了import，不留断链。

**验证**：先给读码机自己（一直没提交过）建了baseline git提交，再做拆分，全部模块import检查通过后，对`deep_search_Git`跑一次真实的`observer.report`端到端（真实API调用，7个函数触发行为描述，0失败），确认拆分前后行为一致，才提交。

## Ledger泛化

用户追问"批分析要专门设计一个ledger层，会不会普适性不够"——这个疑虑是对的。区分清楚：不该为"大项目分批分析"单独写一套存取逻辑，该把ledger层设计成通用的"按(project, scope)存分析产物"能力，批分析只是它的一个消费方。

具体去看了用户另一个项目`刑事阅卷Agent_Git`找参考——它按内容量分三档处理（≤30万token单次分析、30万-60万token跑2次取共识、>60万token按卷分批+**专门做一步跨批关联整合**），阈值是"被真实案子的截断问题倒逼重新校准过的"。**关键启发是"跨批关联整合"这一步**——单纯分批处理会制造新问题：批次A和批次B之间的关系会被切断（这正是今晚`core`模块测试撞见的"叙述覆盖率不够"问题的另一种变体，不是解药，是同一个病换了个位置）。ledger层该存的不是模糊的"历史记录"，是"每个批次的分析结果"，好让跨批整合这一步有材料可用。

`ledger/snapshots.py`（原本只会存"最新一份整体快照"）泛化成`ledger/store.py`：`save_artifact(project_root, scope, data)` / `load_artifact` / `list_artifacts(prefix=...)`，一个项目一份`store.json`按scope做key（不是每个scope单独存文件、靠转义文件名反查——那样"batch:core/session"这类含特殊字符的scope容易跟别的scope转义后撞名，没法可靠区分）。`checkup_cli.py`原有的用法（`scope="latest"`）原样保留，只是换了函数名。

**验证**：写了独立测试脚本，覆盖单scope覆盖存取、多scope+前缀过滤、不存在的scope返回None三个场景，全部通过；再跑一次真实的`checkup_cli.py`端到端确认整条链路（observer+ledger）还能一起正常工作。

## 结论

- 代码结构现在直接体现Observer/Analysis/Ledger这套架构，不用再靠文档去讲"这块对应哪个概念"。
- ledger层是被两个真实需求（checkup_cli的整体快照、批分析的按批存取）同时验证过的通用设计，不是替单一场景写的一次性脚本——这跟今晚一直在守的"先查有没有更普适的做法，别为一个场景单独造"是同一条纪律。

## 还没做的

- 批分析本身（按子模块拆分narrative生成+跨批关联整合的具体实现）还没建，只是设计上确认了ledger层能撑住这个需求，`ledger.store`目前只有`checkup_cli.py`一个真实消费方。
- 增量缓存（只重新分析变过的文件）是ledger层可预见的第三个用途，还没验证过。
