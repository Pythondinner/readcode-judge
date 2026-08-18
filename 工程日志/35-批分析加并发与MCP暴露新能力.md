# 批分析加并发，批分析+决策层接上MCP

> 2026-08-18

## 背景

`core`那次批分析顺序跑8个批次接近1.5小时，用户当场指出"巨型项目按天算"的顾虑。三层并发机会（批次之间、批次内文件分析、批次内判断）之前设计ledger时就点名过是性能问题、可以后补，这次真的补上。

## 并发实现

- `observer/report.py`：`generate_project_report`按文件并发（`ThreadPoolExecutor`，默认3并发）。
- `observer/judgment.py`：`judge_project_against_narrative`按函数并发判断（默认3并发）。
- `observer/consensus.py`：`judge_project_against_narrative_consensus`透传`max_workers`。
- `observer/batch.py`：`run_batch_analysis`按批次并发（默认3并发），每批内部再用上面两层并发（默认3并发），两层叠加。

`deepseek_client.py`/`agent.py`/`verifier.py`/`tools.py`确认过都没有模块级可变共享状态，只读常量+本地变量，并发调用是安全的，不需要额外加锁。

**唯一真实需要处理的并发安全问题**：`ledger.store.save_artifact`是整份读store.json、改一个scope、整份写回——早先泛化ledger时就点名过"如果批分析并发跑，这种整份读写会有竞态，后写的覆盖丢失先写的"，这次是这个风险第一次真的会被触发。修复方式：worker线程只负责算结果，`save_artifact`只在主线程里、每个批次的future完成时调用（用`as_completed`收集结果），不会有两个线程同时写。

## 验证

GDPR_Git（5个批次）真实跑一遍：870秒（14.5分钟）完成，`ledger.store`里5个批次全部正确存进去、正确取回，没有并发写导致的数据丢失。跟`core`那次（8批次、顺序、1.5小时，约11分钟/批）比例推算，这次5批次14.5分钟总耗时（不是55分钟）说明并发确实生效，虽然不是同一个项目、不能算精确对照。

## MCP暴露新能力

`judge_mcp_server.py`加两个工具：
- `run_batch_analysis_tool`：包`observer.batch.run_batch_analysis`。
- `auto_diagnose_confirmed_findings_tool`：把"生成报告→consensus→迭代信号→决策层自动诊断"整条链路包成一次调用，外部agent不需要自己维护中间状态、分好几次调用来回传JSON——跟`generate_project_report_tool`已有的"自包含完整流程"设计是同一个思路。

决策层的边界没有因为接上MCP而松动：`auto_diagnose_confirmed_findings_tool`只能自动决定"诊断哪些发现"，不能决定"要不要应用修复"，产出仍然只是文字建议。

## 结论

- 三层并发都是I/O等待场景，线程池够用，不需要把`deepseek_client.py`重写成异步——这个判断在加之前就做过，这次验证是对的。
- ledger的并发写风险不是纸上谈兵，这次真的第一次跑并发批分析就会撞上，如果不修、直接接并发会真实丢数据。
- 判断层能力现在全部接上了MCP（报告生成、诊断、批分析、自动诊断汇总），不再有"建好了但外部agent够不着"的能力。

## 还没做的

- 没有精确的同项目顺序vs并发耗时对照（`core`和GDPR_Git是两个不同项目，只能按比例推算，不是严格对照实验）。
- GDPR_Git这次批分析里"modules"批次100%无法判断、"_root"批次89%无法判断——这个结果本身没有深究原因（这次测试目的是验证并发机制和ledger安全，不是分析GDPR_Git本身），值得以后单独看一下是narrative覆盖问题还是这个项目本身的特点。
