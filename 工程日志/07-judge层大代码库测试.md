# judge层在大代码库/跨语言场景下的真实测试

> 2026-08-17

## 背景

sensor层（agent.py读代码问答）刚在deepseek-harness上做完压力测试、修了MAX_STEPS的问题。但judge层（complexity.py+behavior.py+report.py）从来没有在跟sensor同等量级的场景下测过——之前全部测试都在自动剧本生成机的几个文件上做的。这次补上这一课，顺带因为deepseek-harness主体是TypeScript，第一次真实暴露了"语言范围"这个之前完全没考虑过的维度。

## 发现1：complexity.py完全锁定在Python，遇到TS直接崩溃

`complexity.py`用`radon.raw.analyze`/`radon.complexity.cc_visit`，底层是Python自己的`compile()`/AST，不是通用的多语言解析器。真实测试：

- **对该仓库的Python文件（`python/sdk/src/deepseek_harness/client.py`，557行）**：正常工作，43个函数，复杂度分布正常（最高`_request_raw`，D级，复杂度23）——确认在陌生Python代码上依然可用。
- **对TypeScript文件（`packages/core/agent-loop/src/agent.ts`）**：直接抛`SyntaxError: invalid syntax (<unknown>, line 1)`，不是结果不准，是完全跑不起来。

这个仓库2589个`.ts/.tsx`文件、只有18个`.py`文件——`complexity.py`目前只能覆盖这个仓库不到1%的文件。**是硬性崩溃（fail-fast），不是静默给出错误数字，这一点是好的失败模式**，不会让人误以为TS代码"复杂度很低"。

## 发现2：report.py被这个限制完全卡住

`report.py`的`generate_report()`第一步无条件调用`complexity.measure_file()`（第25行）——这是整条流水线的入口。也就是说**只要目标是TS文件，report.py在第一步就崩，behavior.py根本轮不到跑**，即使behavior.py本身没有这个问题（见发现3）。

## 发现3：behavior.py（LLM判断的一半）实测证明是语言无关的

`behavior.py`的机制本身（`agent.answer_question`生成描述 + `verifier.verify_answer`独立核实）不依赖AST解析，只是它的prompt模板里写了"radon测得圈复杂度{complexity}"这句话，文字上跟`complexity.py`耦合，不是机制上的耦合。

**真实测试**：手动构造`function_info`（跳过complexity.py，直接指定函数名`step`、第332行、复杂度标注为"N/A，非radon测得"），让`behavior.py`去描述`packages/core/agent-loop/src/agent.ts`里的私有异步方法`step()`——这是一个完全陌生的TS函数，我自己没有先读过。

结果：**4步生成了详细、逐条带行号引用的契约描述，独立verifier核实通过（`verified: True`）**，理由具体（"输入、前置条件、输出、副作用、调用后保证均与代码原文逐条吻合，包括循环重试、inbox修改和事件写入"）。【调用方须知】抓到了一个真实的、不明显的细节：`step()`内部有个`while(true)`循环，一次调用可能触发多次LLM请求，调用方不能假设"一次step调用=一次模型请求"。

**诚实的局限**：这不是像Flask那次`get_root_path`那样的严格盲测——我没有在跑工具之前自己先独立读代码留证据，是工具跑完之后才去看它读的内容。核实通过给出的是"工具自己独立核实"这一层信心，不是"我自己也读过、结论一致"这种双路径交叉验证的信心等级。要达到那个等级需要我自己也先读一遍`step()`函数。

## 结论

- **judge层的两半命运不同**：确定性半边（complexity.py，AST/radon）严格锁定在Python，这次是第一次真实撞见这个边界（之前测试对象自动剧本生成机全是Python，从没暴露过）；LLM判断半边（behavior.py+verifier.py）经真实TS代码测试证明是语言无关的，机制能直接搬到陌生语言的陌生函数上用。
- **report.py目前对TS代码完全不可用**，因为流水线入口就是Python专属的complexity.py——这不是bug，是设计时没考虑多语言场景的自然结果。
- 要不要让judge层支持多语言，是一个需要跟用户讨论权衡的产品决策（要么接入TS专用的复杂度分析库、要么放弃"确定性AST复杂度"这条腿换成别的近似），不属于"直接修"的范畴，这次先如实记录边界，不擅自决定方向。

## 还没做的

- 没有测试behavior.py在Python之外别的语言（比如这个仓库里也有少量shell脚本、CSS）上的表现，样本只有一个TS函数。
- 没有做真正的双路径盲测（自己先独立读代码、再跟工具结果对照）来验证TS场景下behavior.py的可靠度，目前的"verified: True"只是工具自己的独立核实，信心等级低于Flask那次的双路径盲测。
