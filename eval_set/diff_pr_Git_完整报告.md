# 项目体检报告

共15个文件（另有0个不支持的文件类型被跳过），总行数1310

## 项目叙述（✓ 核实通过）

这个项目是「Claude Code 代码改动监控 Agent」——一个给看不懂代码的新手用户当"第三方裁判"的工具。它独立记录"用户要求了什么"和"AI 实际改了什么"，再用与 Claude 完全独立的 DeepSeek 模型客观核验两者是否匹配，判断权始终留给人，不做全自动。

**1. 项目定位**
面向完全不懂技术或刚学编程、让 Claude Code 帮忙写代码但无法亲自核验改得对不对的用户。解决"AI 帮我写代码，但我看不懂它写的对不对"的问题——让 Claude 自己审查自己有天然偏差，所以把"记录"和"审判"拆成两个独立角色：Claude Code 的 Hook 机制被动记录，DeepSeek 独立判断。

**2. 模块组成与职责边界**
- **Ledger 层**（ledger/）：只记录，不判断。Hook 脚本（ledger/hooks/log_user_prompt.py、log_tool_use.py、remind.py）几毫秒跑完退出，绝不在 Hook 里调用大模型；_store.py 按项目路径分区存储；confirm_intent.py 是唯一把对话提炼成需求意图的地方（DeepSeek + 人工确认）；_deepseek.py 封装 DeepSeek API 调用和提示词注入隔离；_text_safety.py 处理 Windows 编码坑。
- **Brain 层**（brain/）：独立裁判。review.py 核验需求 vs 代码改动，判断 matched/partial/missing，带历史模式记忆；_memory.py 处理模式匹配、门槛判断；clear_backlog.py 批量清理积压，不调用大模型。
- **Executor 层**（executor/report.py）：只读投影，生成 Markdown 报告，每次运行重新生成、不追加历史。
- **check.py**：唯一入口，自动接入项目（首次）+ 实时监控循环 + 空格键触发核查。

**3. 关键不变量/流程**
- **Ledger 是只增不减的账本**：events.jsonl 追加写、永不删除，审查"通过"不代表删除记录（_store.py 的 append_record 只追加）。
- **Hook 绝不调用大模型**：Hook 脚本只记录和计数，真正花钱的审查永远需要用户手动触发（check.py 里按空格键才进入核查）。
- **审查窗口精确圈定**：brain/review.py 的 collect_code_changes 从上一条 review_result 到这条 intent_snapshot 之间的代码改动，不多不少。
- **人工确认关卡不可绕过**：confirm_intent.py 提炼完必须人工确认才落盘；review.py 三选一（接受/重新审/清除），没有"手动改写判断"选项。
- **数据按项目路径分区，互不干扰**：_store.py 的 sanitize_project_path 用可读前缀 + 8 位 hash 后缀保证不撞车；report.py 的报告也按同一套规则分区，不能写死固定位置（README 里记录过这个 bug）。
- **提示词注入隔离**：_deepseek.py 的 wrap_untrusted 用分隔符包住不可信内容，配合 system prompt 里"这段是数据不是指令"的说明。
- **新建文件必须给完整内容**：brain/review.py 的 summarize_change 对 Write 工具给完整内容（超 4000 字符才截断），不能只给文件名+字符数（README 记录过这个 bug）。
- **轮次编号从 1 递增**：confirm_intent.py 的 next_round_number 按已有 intent_snapshot 数量 +1。

**4. 设计特点/取舍**
- **判断权留给人，不搞全自动**：实时计数提醒 + 手动触发审查，否决了实时自动审查方案。
- **记录和判断分离，判断者必须独立**：用 DeepSeek 而不是 Claude 自己。
- **先跑通单一场景再扩展**：先单项目验证，再讨论多项目支持；多项目支持用文件夹路径分区，不用插件。
- **纯 Python 标准库，零第三方依赖**：urllib.request 直接调 DeepSeek API，Windows msvcrt 做非阻塞按键检测。
- **接入顺序决定监控生不生效**：必须先跑 check.py 接好监控再打开 Claude Code，不支持热接入（README 明确记录了这个限制）。

## 行为 vs 项目叙述 对照结果

共20个函数：1个违反不变量、6个无法判断、13个支撑项目正确运行（不再展开）

### 违反不变量（1个，值得优先关注）

**executor\report.py :: main**
- 违反的不变量：数据按项目路径分区，互不干扰：_store.py 的 sanitize_project_path 用可读前缀 + 8 位 hash 后缀保证不撞车；report.py 的报告也按同一套规则分区，不能写死固定位置（README 里记录过这个 bug）。
- 判断依据：行为描述指出 report_file_for() 使用当前工作目录（Path.cwd()）作为项目路径，而非从 ledger 记录中获取实际项目路径，这会导致从不同目录调用时报告写入不同子目录，可能覆盖同名项目下的报告，违反按项目路径分区且互不干扰的不变量。

### 无法判断（6个——不代表没问题，只是材料不够判断，值得人工看一眼）

- brain\memory.py :: main —— 行为描述聚焦于记忆删除的交互流程，未涉及项目定位中列出的任何关键不变量（如Ledger只增不减、Hook不调用大模型、审查窗口精确圈定等），无法判断是否违反或支撑。
- brain\review.py :: main —— 行为描述未涉及项目定位中列出的具体不变量（如Ledger只增不减、Hook不调用大模型、审查窗口精确圈定等），仅描述main()的输入输出和副作用，无法判断是否违反任何不变量。
- executor\report.py :: collect_reviews —— 行为描述仅涉及报告生成时的数据聚合与排序，未提及任何与项目定位中列出的不变量（如Ledger只增不减、Hook不调用大模型、审查窗口精确圈定等）相关的细节，材料不足以判断是否违反。
- ledger\confirm_intent.py :: main —— 行为描述未涉及项目定位中列出的具体不变量（如Ledger只增不减、Hook不调用大模型、审查窗口精确圈定等），仅描述了main()的输入输出和副作用，无法判断其是否违反或支持这些不变量。
- ledger\confirm_intent.py :: parse_intents —— 行为描述未涉及项目定位描述中列出的任何关键不变量（如只增账本、Hook不调模型、审查窗口、人工确认等），仅描述了解析函数自身的输入输出行为，无法判断其是否支撑项目正确运行。
- ledger\view_events.py :: truncate —— 行为描述仅涉及字符串截断和递归处理，未提及任何项目定位描述中的关键不变量（如账本只增不减、Hook不调用大模型、审查窗口精确圈定等），材料不足以判断是否支撑项目运行。

### 支撑项目正确运行（13个，不再展开）

brain\_memory.py::apply_matches、brain\clear_backlog.py::main、brain\review.py::print_verdict、brain\review.py::collect_code_changes、brain\review.py::summarize_change、check.py::is_connected、check.py::merge_hooks、check.py::main、executor\report.py::render_review、ledger\_deepseek.py::load_env_file、ledger\_text_safety.py::sanitize、ledger\hooks\remind.py::count_pending、ledger\view_events.py::main


## 复杂度分级分布

- [A] 41个函数/类
- [B] 13个函数/类
- [C] 7个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [C] brain\clear_backlog.py :: main（第25行）复杂度=16
  [C] brain\review.py :: main（第142行）复杂度=16
  [C] brain\memory.py :: main（第17行）复杂度=15
  [C] ledger\hooks\remind.py :: count_pending（第21行）复杂度=15
  [C] executor\report.py :: render_review（第70行）复杂度=12
  [C] executor\report.py :: main（第110行）复杂度=12
  [C] brain\review.py :: print_verdict（第118行）复杂度=11
  [B] executor\report.py :: collect_reviews（第34行）复杂度=10
  [B] brain\_memory.py :: apply_matches（第52行）复杂度=9
  [B] check.py :: is_connected（第83行）复杂度=9
  [B] ledger\confirm_intent.py :: main（第51行）复杂度=9
  [B] brain\review.py :: collect_code_changes（第51行）复杂度=7
  [B] check.py :: merge_hooks（第66行）复杂度=7
  [B] check.py :: main（第197行）复杂度=7
  [B] ledger\view_events.py :: truncate（第12行）复杂度=7

## 行为描述明细（B级以上，共20个）

### [B] brain\_memory.py :: apply_matches（第52行，复杂度9）

在 brain/_memory.py 中，apply_matches 的契约如下（注意：文件是 brain/_memory.py，不是 brain_memory.py；函数在第 52 行附近）：

**输入**：
- `memory_list`：一个列表，元素是带 `id`、`status`、`occurrences`、`rounds`、`last_seen_round`、`updated_at` 等键的字典（记忆条目）。
- `matched_pattern_ids`：命中的模式 id 列表（可为 None/空）。
- `new_candidate_pattern`：新候选模式字符串（可为 falsy，如 None/空串）。
- `round_number`：当前轮次整数。

**输出**：返回 `newly_eligible` 列表——本次新跨过“提议门槛”（`status == "candidate"` 且 `occurrences >= PROPOSE_THRESHOLD`，即 >= 2）的模式字典列表。

**副作用（原地修改外部状态）**：
- 直接修改传入的 `memory_list`：对每个命中的 id，累加 `occurrences`、追加 `rounds`、更新 `last_seen_round` 和 `updated_at`（代码：`m["occurrences"] += 1; m["rounds"].append(round_number); m["last_seen_round"] = round_number; m["updated_at"] = ...`）。
- 若 `new_candidate_pattern` 非空，则 `memory_list.append(new_memory_entry(...))` 新增一条候选记忆。
- 不写文件、不改全局变量，但会修改调用方持有的列表对象。

**前置条件**：
- `memory_list` 中每个条目的 `id` 唯一（因为用 `by_id = {m["id"]: m ...}` 建索引，重复 id 会覆盖）。
- 传入的 `matched_pattern_ids` 里的 id 若在 `memory_list` 中不存在，会被静默跳过（`if not m ... continue`）。
- 若某条目的 `rounds` 已包含 `round_number`，则该轮不会重复累加（`if ... round_number in m["rounds"]: continue`）。

**调用后保证**：
- 命中的条目 `occurrences` 至少 +1（除非该轮已记录过），`rounds` 追加该轮，`last_seen_round` 更新为当前轮。
- 返回的 `newly_eligible` 只包含“本次”跨过门槛的候选（之前已跨过的不在返回里，因为 `occurrences` 是累加的，只有本次从 <2 变成 >=2 的才被 append）。
- 新增候选条目的 `occurrences` 恒为 1，不会出现在返回列表中。

【调用方须知】最该警惕的是：该函数会**原地修改你传入的 `memory_list` 列表对象**（累加次数、追加轮次、甚至 append 新条目），但它**不返回修改后的列表**，只返回 `newly_eligible`——如果你把返回值误当成“更新后的记忆列表”去用，会丢掉所有累加/新增的变更；必须继续使用原来的 `memory_list` 变量。另外，若 `matched_pattern_ids` 里含重复 id 或 memory_list 中 id 不唯一，`by_id` 字典会覆盖，导致部分命中条目被漏更新。

*✓ 核实通过——候选答案的所有具体描述均与代码原文一致，包括函数位置、参数、副作用、前置条件和返回值行为，且【调用方须知】指出的原地修改和返回值陷阱准确无误。*

### [C] brain\clear_backlog.py :: main（第25行，复杂度16）

函数 `main()`（brain/clear_backlog.py 第25行起）的契约如下，依据均来自该文件及被调用的 ledger/_store.py、brain/review.py 的代码原文：

**输入**：
- 无命令行参数。它通过 `load_records()`（ledger/_store.py）读取当前项目目录（`Path.cwd()`）下 `data/projects/<sanitized>/events.jsonl` 的全部记录（`load_records` 返回 `records` 列表）。
- 通过 `find_intent_snapshots(records)` 和 `find_reviewed_snapshot_ids(records)`（brain/review.py）从这些记录中筛出“待审查的需求快照” `pending`（`[s for s in snapshots if s["id"] not in reviewed_ids]`）。
- 通过 `safe_input`（ledger/_text_safety.py）交互式读取用户输入：编号列表（如 `1,3`）、`all`、或直接回车。

**输出**：
- 无返回值（`return` 时返回 `None`）。
- 向 stdout 打印提示信息、待审查快照的预览（`preview(s)`）、以及最终“已清除 N 条”的确认信息。

**副作用（外部状态/文件改动）**：
- 当用户确认清除时，对每个目标快照调用 `append_record("review_result", {...})`（ledger/_store.py），向 `events.jsonl` 追加一条 `review_result` 记录，其 `payload` 固定为：`intent_snapshot_id`、`round_number`、`reviewed_change_ids: []`、`ai_verdict: None`、`confirmed_verdict: {"overall": "skipped", "summary": "用户批量清除，未经 DeepSeek 审查"}`、`confirmation_method: "bulk_skipped"`。
- 该操作会改变 `find_reviewed_snapshot_ids` 的结果（因为新增了 `review_result` 记录），从而让这些快照不再出现在下次的 `pending` 中——即“清除”的实质是写入一条标记为已审查的记录，而非删除原快照。
- 全程不调用任何大模型（代码中无 `call_deepseek` 调用，且打印“全程没有调用任何大模型”）。

**前置条件**：
- 需要 `events.jsonl` 中存在 `intent_snapshot` 类型的记录（否则 `pending` 为空，直接打印“没有待审查的需求快照”并返回）。
- 需要 `setup_utf8_io()` 已执行（函数开头调用），保证中文输出正常。
- 需要 `ledger/_store.py`、`ledger/_text_safety.py`、`brain/review.py` 可导入（通过 `sys.path.insert` 加入路径）。

**调用后保证**：
- 若用户未输入或输入格式非法、编号越界、或确认时输入非空字符，则不会写入任何记录（各分支打印相应提示后 `return`）。
- 只有用户输入有效编号（或 `all`）且确认时直接回车（`confirm == ""`）时，才会对每个目标追加一条 `review_result` 记录。
- 追加记录后打印“已清除 N 条”，但**不修改** `events.jsonl` 中已有的 `intent_snapshot` 记录本身（原快照仍保留在文件中）。

【调用方须知】最容易被忽略的是：`main()` 的“清除”并不会删除或修改 `events.jsonl` 里原有的 `intent_snapshot` 记录，它只是**追加**一条 `review_result` 记录（`confirmation_method: "bulk_skipped"`）来把该快照标记为“已审查”，从而让 `find_reviewed_snapshot_ids` 在下次运行时把它排除出 `pending`。因此如果调用方期望“清除”会物理删除数据，或期望后续能重新看到这条快照，都会与实际情况不符——数据文件只会增长，不会因清除而变小。

*△ 未核实完——超过核实步数上限，未能完成核实*

### [C] brain\memory.py :: main（第17行，复杂度15）

函数 `main()`（brain/memory.py 第17行起）是一个交互式命令行工具，没有参数、没有返回值（隐式返回 None），其契约如下：

**输入**：
- 无函数参数。
- 依赖外部数据源：`load_memory()` 从 ledger 目录加载记忆列表（`memory_list = load_memory()`）。
- 依赖用户交互：通过 `safe_input(...)` 读取两处输入——①要删除的记录编号（逗号分隔，如 `1,3`），②删除确认（回车=确认，其他任意字符=取消）。

**输出**：
- 全部通过 `print()` 输出到 stdout，无返回值。
- 正常流程输出：记忆总数、每条记录的编号/状态标签/模式文本/出现次数/轮次、待删除列表、删除结果。
- 分支输出：无记忆时打印“这个项目还没有任何模式记忆。”；空输入打印“没有删除任何记录。”；格式错误打印“输入格式不对，没有删除任何记录。”；无有效编号打印“没有匹配到有效编号，没有删除任何记录。”；取消打印“已取消，没有删除任何记录。”。

**副作用（外部状态修改）**：
- 当用户确认删除时，调用 `save_memory(remaining)` 将过滤后的列表持久化写回 ledger 存储（`remaining = [m for i, m in enumerate(memory_list, 1) if i not in to_delete]`）。这是唯一的持久化副作用。
- 调用 `setup_utf8_io()` 设置 stdout/stdin 的 UTF-8 编码（影响进程 IO 环境）。
- 不修改任何全局变量、不修改传入的 `memory_list`（它只读，删除通过构造新列表 `remaining` 实现）。

**前置条件**：
- `load_memory()` 必须能成功执行并返回列表（若返回空列表则提前 return）。
- 每条记忆记录必须包含键 `rounds`（可迭代）、`status`、`pattern`、`occurrences`，否则会抛 KeyError（如 `m["rounds"]`、`m["status"]`）。
- 用户输入必须是可被 `int()` 解析的整数（否则走 ValueError 分支）。

**调用后保证**：
- 若用户确认删除，则存储中对应编号的记录被移除，其余记录原样保留并写回；若未确认或取消，存储不被修改。
- 无论何种分支，函数都会正常返回，不会抛出未捕获异常（除前置条件不满足时的 KeyError/ValueError 外）。

【调用方须知】最容易被忽略的是：`main()` 的删除操作**只在用户输入确认时（回车）才真正写盘**，但在此之前它已经通过 `safe_input` 读取了编号并打印了“即将删除”列表——如果调用方在非交互环境（如管道输入）下运行，`safe_input` 可能读到 EOF 或空串，导致函数在“没有删除任何记录”分支提前返回，而**不会**触发 `save_memory`；同时注意 `to_delete` 只保留 1..len 范围内的编号，超范围编号被静默忽略，但**不会**报错，调用方可能误以为越界编号也被删除了。

*✓ 核实通过——逐条核对代码原文，候选答案对输入、输出、副作用、前置条件和保证的描述均与代码相符，且调用方须知指出的非交互环境提前返回和越界编号静默忽略均属实。*

### [C] brain\review.py :: main（第142行，复杂度16）

main() 是 brain/review.py 的入口函数（第142行起，到第240行），无参数、无返回值，是命令行脚本的驱动函数。

【输入】
- 无显式参数。它从外部读取数据：
  - 调用 load_records() 读取事件记录（第146行 `records = load_records()`）。
  - 调用 load_memory() 读取历史模式记忆（第153行 `memory_list = load_memory()`）。
  - 通过 safe_input() 从 stdin 读取用户交互输入（第197行 `choice = safe_input(...)`、第224行 `ans = safe_input(...)`）。
  - 通过 load_env_file() 加载环境变量（第143行）。

【输出】
- 无返回值（函数体没有 return 语句，正常结束返回 None）。
- 副作用是主要的输出：
  - 打印大量提示信息到 stdout（如第149行 `print("没有待审查的需求快照...")`、第156行 `print(f"正在审查需求快照...")`、第190行 `print_verdict(ai_verdict, memory_list)` 等）。
  - 调用 DeepSeek API（通过 call_review → call_deepseek，第164行 `ai_verdict = call_review(review_input)`）。

【副作用（外部状态/文件/全局数据）】
1. 写入事件记录文件：
   - 第199-205行，用户确认（回车）时 `append_record("review_result", {...})` 写入一条 review_result 记录。
   - 第232-238行，用户选 s 时 `append_record("review_result", {...})` 写入一条 review_result 记录（confirmed_verdict 为 skipped）。
2. 修改记忆文件：
   - 第207-222行，确认后若 round_number 非空，调用 apply_matches(...) 得到 newly_eligible，然后对每个模式让用户选择 y/其他，修改 m["status"]，最后第222行 `save_memory(memory_list)` 写回记忆文件。
3. 修改全局/模块级数据：无直接修改全局变量，但通过 append_record/save_memory 修改了持久化文件（events.jsonl 和记忆文件）。

【前置条件】
- 需要能正常调用 DeepSeek API（依赖 load_env_file 加载的 API key 等环境变量）。
- 需要存在事件记录文件（load_records 能读到数据）。
- 需要存在至少一条未审查的 intent_snapshot 记录，否则函数在第149-150行直接打印提示并 return（`if not pending: print(...); return`）。
- 需要 setup_utf8_io() 已执行（函数内第142行调用）。

【调用后保证】
- 若存在待审查快照，会处理第一条 pending 快照（第151行 `snapshot = pending[0]`）。
- 若 AI 返回无法解析的 JSON，函数在第166-168行打印提示并 return，不写入任何记录（该快照保持未审查状态，可重跑）。
- 若用户确认（回车），会写入 review_result 记录，并可能更新记忆文件；若用户选 s，写入 skipped 的 review_result 记录；若用户选 r，重新调用 AI 审查（不写记录，循环继续）。
- 函数保证最终会退出 while 循环（通过 break），不会无限循环（除非用户一直输入无效选项，但每次无效输入都会打印提示并继续循环）。

【调用方须知】main() 最容易被忽略的副作用是：它不只是审查，还会在用户确认后**修改记忆文件**——apply_matches 会基于 AI 的 matched_pattern_ids/new_candidate_pattern 生成候选模式，并**逐个弹出交互式提问**（第224行 `ans = safe_input(...)`）让用户决定是否记住，然后 save_memory 写回。也就是说，运行这个脚本可能在你以为只是"审查一次"时，悄悄改变了项目的持久化记忆数据，而且这个改变依赖用户在交互提示下的选择——如果脚本在无人值守/CI 环境下运行，这个交互式提问会卡住或产生非预期结果。

*✓ 核实通过——逐条对照代码确认了候选答案中所有关键行为描述（输入来源、输出、副作用、前置条件、调用后保证）均与源码一致，包括交互式记忆确认和文件写入。*

### [C] brain\review.py :: print_verdict（第118行，复杂度11）

print_verdict(verdict, memory_list) 的契约（依据 brain/review.py 第118-140行）：

**输入**：
- `verdict`：一个 dict，来自 `call_review` 的 `json.loads` 结果（第113-117行）。函数通过 `.get()` 读取以下键：`restated_intents`（list，缺省空）、`overall`（缺省'未知'）、`summary`（缺省空串）、`per_intent`（list，缺省空）、`matched_pattern_ids`（list，缺省空）。
- `memory_list`：list，元素是含 `id`、`pattern`、`rounds` 字段的 dict（第132行 `m["id"]`、第137行 `m["pattern"]`、第138行 `m["rounds"]`）。

**输出**：无返回值（隐式返回 None）。所有输出都是通过 `print()` 写到 stdout 的文本。

**副作用**：
- 只读操作，不修改任何文件、全局数据或传入参数。不调用 `append_record`/`save_memory` 等写操作。
- 副作用仅限向 stdout 打印多行文本（第121-139行）。

**前置条件**：
- `verdict` 必须是 dict（或至少支持 `.get`），否则会抛 AttributeError。
- `memory_list` 中每个元素必须是 dict，且当 `matched_pattern_ids` 非空时，被引用的元素必须含 `id`、`pattern`、`rounds` 键（第132、137、138行），否则抛 KeyError。
- `matched_pattern_ids` 里的 id 若在 memory_list 中找不到，会被静默跳过（`by_id.get(pid)` 返回 None 时第134行 `if m:` 不打印），不会报错。

**调用后保证**：
- 若 `restated_intents` 非空，打印标题和每条复述（第121-125行）。
- 总是打印 `总体结论` 和 `总结` 两行（第127-128行）。
- 若 `per_intent` 非空，逐条打印状态、意图、理由（第129-131行）。
- 若 `matched_pattern_ids` 非空，打印标题，并对每个能找到的 id 打印模式及出现轮次（第133-139行）。
- 不抛异常的前提是上述前置条件满足。

【调用方须知】`matched_pattern_ids` 里的 id 如果在 `memory_list` 中找不到，函数会静默跳过不打印任何提示——调用方如果依赖打印结果判断“引用了哪些历史模式”，会漏掉这些缺失 id，且毫无报错迹象；另外该函数完全不校验 `per_intent` 里每个 item 是否含 `status`/`intent`/`reason` 键，缺键时打印出来的是 `None` 而不是报错，容易让调用方误以为数据完整。

*✓ 核实通过——逐行核对代码，候选答案对输入、输出、副作用、前置条件、保证的描述均与源码相符，且【调用方须知】指出的静默跳过缺失 id 和 per_intent 缺键打印 None 的行为在代码中确实存在。*

### [B] brain\review.py :: collect_code_changes（第51行，复杂度7）

函数 collect_code_changes(records, snapshot_record) 定义在 brain/review.py 第51-63行。

【输入】
- records：一个列表，元素是带 "id"、"record_type"、"payload" 字段的记录（从 load_records() 读出的 events.jsonl 记录）。
- snapshot_record：一条 intent_snapshot 记录，必须包含 "id" 字段，且该 id 必须存在于 records 中（第53-54行用 next(...) 按 id 查找，找不到会抛 StopIteration）。

【输出】
- 返回一个列表，元素是 records 中 record_type == "post_tool_use" 的记录（第62-63行）。这些是代码改动记录。

【行为/逻辑】
- 第53-54行：在 records 中找到 snapshot_record 的索引 snapshot_index。
- 第55-59行：从索引0开始，向前扫描到 snapshot_index 之前，把最后一条 record_type == "review_result" 的下一条作为 start_index（即从上一次审查结果之后开始）；如果没有 review_result，start_index 保持为 0（从头开始）。
- 第60行：取窗口 records[start_index : snapshot_index + 1]，包含该 intent_snapshot 本身。
- 第62-63行：只保留窗口内 record_type == "post_tool_use" 的记录返回。

【副作用】
- 无。纯函数，不修改 records、不写文件、不改全局状态。

【前置条件】
- records 中必须存在 id 等于 snapshot_record["id"] 的记录，否则 next() 抛 StopIteration（第53-54行）。
- snapshot_record 本身应是 intent_snapshot 类型（虽然函数本身不校验，但调用方 main() 传入的是 find_intent_snapshots 的结果）。

【调用后保证】
- 返回的列表只含 post_tool_use 记录，且这些记录的时间位置都在最后一次 review_result 之后、且不晚于该 intent_snapshot。
- 返回列表可能为空（若窗口内没有 post_tool_use）。

【调用方须知】
调用方最容易忽略的是：该函数返回的代码改动窗口是『从上一条 review_result 之后到这条 intent_snapshot 本身』，但窗口的右边界是 snapshot_index + 1（包含 snapshot 本身），而左边界 start_index 是上一条 review_result 的下一条——如果 records 里存在多条 review_result，它只取『最近一条』review_result 之后的内容，而不是所有未审查的改动；更关键的是，它完全不校验 snapshot_record 是否已经被审查过（main() 里用 find_reviewed_snapshot_ids 过滤了 pending，但 collect_code_changes 本身不检查），如果调用方误传一个已审查过的 snapshot，它仍会照常返回改动窗口，不会报错，可能让调用方以为这些改动还没被审过。

*✓ 核实通过——逐行核对代码后，候选答案的所有具体描述（行号、逻辑、边界行为）均与源码相符，没有夸大或虚构。*

### [B] brain\review.py :: summarize_change（第68行，复杂度6）

函数 `summarize_change(record)` 定义在 brain/review.py 第 68-91 行，契约如下：

**输入**：一个 `record` 字典，要求其 `payload` 字段存在，且 `payload` 内可能包含 `tool_name`、`tool_input`（含 `file_path`、`content`）、`tool_response`（含 `structuredPatch`）。代码原文：`payload = record["payload"]`、`tool_name = payload.get("tool_name", "未知工具")`、`file_path = payload.get("tool_input", {}).get("file_path", "未知文件")`、`patch = payload.get("tool_response", {}).get("structuredPatch") or []`。

**输出**：一个字符串，格式为 `文件: {file_path}\n改动类型: {tool_name}\n{diff_text}`（第 91 行 `return f"文件: {file_path}\n改动类型: {tool_name}\n{diff_text}"`）。其中 `diff_text` 有三种来源：
1. 若 `patch` 非空（即 `structuredPatch` 存在且有内容），则把每个 hunk 的 `lines` 拼接成 diff 文本（第 76-80 行）。
2. 否则若 `tool_name == "Write"`，取 `tool_input.content`；若长度超过 `WRITE_CONTENT_CAP`（=4000，第 66 行），则截断到前 4000 字符并加说明（第 82-86 行），否则输出完整内容（第 87-88 行）。
3. 否则输出 `"（无可用 diff）"`（第 89-90 行）。

**副作用**：无。函数只读取 `record` 并返回字符串，不修改任何外部状态、不写文件、不调用全局数据（不调用 `append_record`/`save_memory` 等）。

**前置条件**：调用方需保证 `record` 是字典且含 `payload` 键（否则第 69 行 `record["payload"]` 会抛 KeyError）；`payload` 中 `tool_input`/`tool_response` 若存在应为字典（否则 `.get` 链可能抛 AttributeError）。此外 `patch` 中的每个 hunk 应含 `lines` 列表（第 78 行 `hunk.get("lines", [])` 已做缺省处理）。

**调用后保证**：返回的字符串一定以 `文件: ` 开头，且包含 `改动类型: ` 行；`diff_text` 一定非空（至少是占位文本）。

【调用方须知】最容易被忽略的是：当 `tool_name` 不是 `"Write"` 且 `structuredPatch` 为空时，函数会静默返回 `"（无可用 diff）"`——也就是说，对于 `Edit` 之外的工具（比如 `Bash`、`Read` 等）如果 `tool_response` 里没有 `structuredPatch`，调用方拿到的 diff 文本是占位符，不会包含任何实际改动内容，审查时可能误以为“没有改动”。如果调用方需要这些工具的完整输出，必须在传入前自行从 `tool_response` 的其他字段（如 `output`）提取并拼进 `diff_text`，否则这些改动会被 `build_review_input` 以“无可用 diff”的形式喂给 DeepSeek，导致审查遗漏。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和调用后保证的描述与代码逐条吻合，且【调用方须知】指出的非Write工具无structuredPatch时静默返回占位符的行为确实存在（第89-90行），符合代码实际逻辑。*

### [B] check.py :: is_connected（第83行，复杂度9）

is_connected(project_path) 的契约如下（依据 check.py 第83-104行原文）：

【输入】一个 project_path（Path 对象，指向某个项目目录）。

【输出】返回 bool：
- 若 project_path/.claude/settings.json 不存在 → 返回 False（第87-88行 `if not settings_path.exists(): return False`）。
- 若该文件存在但 JSON 解析失败或读取出错（json.JSONDecodeError/OSError）→ 返回 False（第89-91行 `except (json.JSONDecodeError, OSError): return False`）。
- 否则读取该 JSON，检查 hook_config() 里定义的每个事件（UserPromptSubmit/PostToolUse/Stop）所需的 command 是否都已存在于现有配置中：只要有一个事件所需的命令集合不是现有命令集合的子集，就返回 False（第96-102行 `if not wanted_commands.issubset(existing_commands): return False`）；全部满足才返回 True（第103行 `return True`）。

【副作用】无。该函数只读文件（read_text），不写任何文件、不改任何全局状态、不打印输出。

【前置条件】无特殊前置条件；project_path 可以是任意路径，函数内部自行处理文件不存在/解析失败的情况。

【调用后保证】返回 True 表示该项目的 .claude/settings.json 已包含 hook_config() 定义的全部监控命令；返回 False 表示未接入或配置不完整/文件损坏。

【调用方须知】这个函数只检查“命令字符串是否出现在配置里”，并不校验这些命令对应的脚本文件是否真实存在、也不校验配置是否真的生效——即使返回 True，也只是说 settings.json 里写了这些 command 字符串，不代表监控 Hook 实际能跑起来（比如脚本被删了、路径写错、或配置格式虽能解析但结构不符合 Claude Code 预期）。所以调用方不能把 True 当作“监控一定在工作”，只能当作“配置项已写入”。

*✓ 核实通过——逐行核对代码，候选答案对输入、输出、副作用、前置条件和保证的描述均与源码相符，且调用方须知指出的'只检查命令字符串存在性、不校验脚本实际可用'也准确反映了代码逻辑。*

### [B] check.py :: merge_hooks（第66行，复杂度7）

merge_hooks(existing, new) 定义在 check.py 第 66-77 行，契约如下：

【输入】
- existing：一个 dict，代表已有的 Claude Code settings.json 内容（通常来自 json.loads 读出的文件内容）。
- new：一个 dict，代表要合并进去的 hook 配置（调用方传的是 hook_config() 的返回值，见第 79 行 connect_project 中 `merged = merge_hooks(existing, hook_config())`）。

【输出】
- 返回同一个 existing 对象（第 77 行 `return existing`），即原地修改后返回原对象，不是新建副本。

【副作用】
- 原地修改入参 existing：第 67 行 `existing.setdefault("hooks", {})` 会在 existing 没有 "hooks" 键时给它加上一个空 dict；第 70 行 `existing["hooks"].setdefault(event, [])` 会给每个事件加空列表；第 76 行 `existing["hooks"][event].append(entry)` 会把 new 里未重复的 entry 追加进 existing。
- 不写文件、不改全局变量、不打印。真正的文件写入发生在调用方 connect_project（第 84-86 行 `settings_path.write_text(...)`），不在本函数内。

【前置条件】
- existing 必须是 dict（否则 setdefault/下标赋值会抛 AttributeError/TypeError）。
- new 必须是 dict，且其值应为列表（第 69 行 `for event, entries in new.items()`，第 72 行 `for entry in entries`），每个 entry 应含 "hooks" 键（第 73 行 `entry.get("hooks", [])`，缺省按空列表处理）。
- 调用方需保证 existing 是希望被原地修改的对象——如果调用方后续还要用原来的 existing，会受影响。

【调用后保证】
- existing 一定包含 "hooks" 键，且对 new 中的每个事件，existing["hooks"][event] 都存在（至少是空列表）。
- 去重保证：对每个事件，如果 new 中某个 entry 的任一 command 已存在于 existing 该事件已有的 command 集合中，则该 entry 不会被追加（第 73-75 行）。注意去重粒度是「entry 内任一 command 命中即跳过整个 entry」，不是逐 command 合并。
- 不保证返回新对象，返回的就是入参 existing 本身。

【调用方须知】merge_hooks 是原地修改入参 existing 并返回同一个对象，不是返回新配置——如果调用方在调用前已经持有 existing 的引用（比如从文件读出的 dict），调用后这个 dict 就被改了；而且去重是按「entry 里任一 command 已存在就跳过整个 entry」来做的，所以如果 new 里某个 entry 同时含一个已存在的 command 和一个新 command，整个 entry 都会被丢弃，那个新 command 也不会被加进去。

*✓ 核实通过——逐行核对代码，候选答案对输入输出、原地修改副作用、去重逻辑（entry 内任一 command 命中即跳过）及调用方须知均与源码一致。*

### [B] check.py :: main（第197行，复杂度7）

main()（check.py 第197-232行）是脚本的顶层入口，契约如下：

**输入**：无参数。但依赖交互输入：
- 调用 resolve_project_path()（第201行）要求用户通过 safe_input 输入一个存在的项目文件夹路径（不设默认值，空输入会重试）。
- 在监控循环中，当有待处理内容时，调用 safe_input 询问是否开始核查（第216-219行），输入需匹配 START_COMMANDS = {"y", "核查"}（第19行，且经 .strip().lower() 归一化）。

**输出**：无返回值（隐式返回 None）。副作用是向 stdout 打印大量状态信息（锁定路径、监控提示、状态行、核查结果等）。

**副作用（外部状态/文件/全局数据）**：
1. 若项目未接入监控（is_connected 返回 False），调用 connect_project(project_path)（第203-204行），这会写/合并 .claude/settings.json 文件（见 connect_project 第96-110行：settings_path.write_text(...)），即修改了项目目录下的配置文件。
2. 调用 setup_utf8_io() 和 sys.stdout.reconfigure(line_buffering=True)（第198-199行），改变进程的 IO 编码和 stdout 缓冲模式（全局进程状态）。
3. 当用户确认核查时，调用 run_checks(project_path)（第224行），它会用 subprocess.run 启动 STEPS 中的三个子进程脚本（confirm_intent.py、review.py、report.py），这些子进程可能产生各自的副作用（写记录文件等），但 main() 本身不直接写文件。
4. 循环中调用 load_records(project_path) 和 count_pending(records)（第209-210行），这些函数会读取 ledger 记录（可能读文件），但 main() 不写。

**前置条件**：
- 依赖模块 _store、_text_safety、remind 可导入（第10-12行），且这些模块依赖的 ledger/hooks 目录存在。
- 依赖 msvcrt（Windows 专用，第3行），在非 Windows 平台会 ImportError。
- 用户必须能通过 safe_input 输入路径（stdin 可用）。
- 若项目已接入监控，.claude/settings.json 需可读（is_connected 内部处理了不存在/解析失败的情况，返回 False）。

**调用后保证**：
- 除非用户按 Ctrl+C（触发 KeyboardInterrupt），否则函数不会返回——它进入无限 while True 循环（第207行），持续监控直到被中断。
- 捕获 KeyboardInterrupt 后打印“已退出监控。”并正常返回（第231-232行）。
- 每次循环中，若没有待处理内容（pending_messages==0 且 pending_reviews==0），会打印“现在没有待处理的内容，继续监控...”并继续循环，不调用大模型。

【调用方须知】main() 一旦运行就进入无限循环，只有 Ctrl+C 才能退出；而且它会在项目未接入监控时**自动改写项目的 .claude/settings.json 文件**（connect_project 会写入 hook 配置），这个副作用在函数名和 docstring 里完全看不出来——调用方如果不想让脚本修改项目配置，必须在调用前先手动确认 is_connected(project_path) 为 True，否则脚本会静默地往项目里写入监控 Hook 配置。

*✓ 核实通过——逐条对照代码确认了候选答案的所有具体说法：行号、函数调用、副作用（写 settings.json、改 stdout）、无限循环、Ctrl+C 退出、START_COMMANDS 值均属实。*

### [C] executor\report.py :: render_review（第70行，复杂度12）

「render_review」定义在 executor/report.py 第70行，是一个纯函数（无副作用），契约如下：

**输入**（两个参数）：
1. `review`：一个字典，由 `collect_reviews` 生成，必须包含以下键（代码原文见第71-88行）：
   - `overall`（第72行 `label = STATUS_LABEL.get(review["overall"], review["overall"])`）
   - `round_number`（第73行 `round_label = f"第 {review['round_number']} 轮 — " if review["round_number"] else ""`）
   - `logged_at`（第74行 `lines = [f"### {round_label}{review['logged_at']} — {label}"]`）
   - `summary`（第76行 `if review["summary"]:`）
   - `restated_intents`（第79行 `if review["restated_intents"]:`）
   - `matched_pattern_ids`（第83行 `if review["matched_pattern_ids"]:`）
   - `per_intent`（第91行 `for item in review["per_intent"]:`，且每个 item 需有 `status`、`intent`、`reason` 键，见第92-93行）
   - `changes`（第95行 `if review["changes"]:`，每个 change 需有 `file_path` 和 `tool_name` 键，见第99-100行）
2. `memory_by_id`：一个字典，键为模式ID，值为含 `pattern` 和 `rounds` 键的字典（第85-88行 `m = memory_by_id.get(pid)`、`m["pattern"]`、`m["rounds"]`）。

**输出**：返回一个字符串（第102行 `return "\n".join(lines)`），是 Markdown 格式的审查报告文本。

**副作用**：无。函数体内没有任何文件写入、全局变量修改、打印或外部状态变更——它只读取入参并拼接字符串。

**前置条件**：
- `review` 必须包含上述所有键（否则会 KeyError），且 `per_intent` 的每个元素必须含 `status`/`intent`/`reason` 键。
- `memory_by_id` 中若 `matched_pattern_ids` 引用了不存在的ID，函数会静默跳过（第85行 `if m:` 判断），不会报错。
- `changes` 里的 `file_path` 会被 `Path(c["file_path"]).name` 处理（第99行），所以必须是合法路径字符串。

**调用后保证**：返回的字符串以 `### ` 开头（第74行），包含标题、summary、需求列表、历史模式引用、逐条判断、代码改动链接（若有）。

【调用方须知】函数名 `render_review` 字面意思是“渲染单条审查”，但它**不写任何文件、不打印**——它只是返回一个 Markdown 字符串，真正的文件写入发生在调用方 `main()` 里（第155行 `report_file.write_text(...)`）。另外最容易被忽略的是：第96-98行的注释明确说明，`changes` 里生成的 `file:///` 链接指向的是文件**现在**的样子，不是审查那一刻的历史 diff——调用方若把链接当作历史快照会误导用户，必须提醒用户用 `python ledger/view_events.py` 查精确历史改动。

*✓ 核实通过——逐行核对代码，候选答案对函数契约的描述（输入键、输出、无副作用、前置条件、调用后保证）均与代码原文一致，且引用的行号和注释准确无误。*

### [C] executor\report.py :: main（第110行，复杂度12）

main()（executor/report.py 第110-164行）的契约如下，均引用代码原文：

**输入**：无命令行参数、无返回值。它从全局/外部数据源读取：
- `records = load_records()`（第112行）——从 ledger 存储加载全部记录；
- `memory_by_id = {m["id"]: m for m in load_memory()}`（第113行）——加载历史模式记忆。

**输出**：
- 若 `not reviews`（第115行），打印提示 `"还没有任何审查结果，先跑 brain/review.py 生成审查结果。"` 并 `return`（第116-117行），不生成文件。
- 否则生成报告文件：`report_file = report_file_for()`（第151行），`report_file.write_text(...)`（第152行）写入 Markdown 文本，并在 stdout 打印 `f"报告已生成: {report_file}，共 {len(reviews)} 条审查记录（{len(needs_attention)} 条需要关注）。"`（第153-154行）。

**副作用（外部状态/文件/全局数据）**：
1. **写文件**：`report_file_for()`（第20-26行）在 `REPORTS_ROOT / sanitize_project_path(project_path)` 下 `folder.mkdir(parents=True, exist_ok=True)` 创建目录，并返回 `folder / "report.md"`。main 调用 `report_file_for()` 时不传参，`project_path = project_path or Path.cwd()`（第21行）——即**使用当前工作目录**作为项目路径，据此决定报告写入哪个子目录。
2. **修改全局 sys.path**：模块顶部 `sys.path.insert(0, str(LEDGER_DIR))`（第7行）在 import 时执行，main 本身不直接改，但 main 依赖该副作用才能 import `_store`。
3. **stdout 输出**：打印提示或报告路径。

**前置条件**：
- 模块 import 时 `sys.path.insert(0, str(LEDGER_DIR))` 已执行（第7行），且 `_store`、`_text_safety` 可导入。
- `load_records()` 返回的记录中，`review_result` 类型的记录需含 `payload`，且 `payload` 中 `confirmed_verdict`/`verdict` 为 dict（collect_reviews 第37-38行 `payload.get("confirmed_verdict") or payload.get("verdict") or {}`）。
- `load_memory()` 返回的每条记忆需有 `"id"` 字段（第113行 `m["id"]`）。
- 当前工作目录可写（report_file_for 会 mkdir）。

**调用后保证**：
- 若存在审查记录，则在 `REPORTS_ROOT/<sanitize(当前工作目录)>/report.md` 生成 UTF-8 编码的 Markdown 报告，内容含标题、生成时间、统计、需要关注部分（partial/missing）和存档部分（matched/skipped，折叠在 `<details>` 中）。
- 若没有任何审查记录，不写文件，仅打印提示。

【调用方须知】main 的报告文件路径取决于**调用时的当前工作目录**（`report_file_for()` 第21行 `project_path = project_path or Path.cwd()`），而不是代码库根目录或某个固定位置——从不同目录调用会把报告写到不同子目录，且 `sanitize_project_path` 会改写路径，调用方若从非预期目录运行，报告会落到别处，且可能覆盖同名项目目录下已存在的 report.md。

*✓ 核实通过——候选答案逐条与代码原文核对，所有引用（行号、函数名、行为）均准确，包括副作用和前置条件，调用方须知也正确指出路径依赖当前工作目录。*

### [B] executor\report.py :: collect_reviews（第34行，复杂度10）

collect_reviews(records) 的契约如下（依据 executor/report.py 第34-63行）：

**输入**：一个 records 列表，其中每个元素 r 是字典，需含键 "id"、"record_type"、"logged_at"、"payload"。
- 第35行 `by_id = {r["id"]: r for r in records}` 要求每个记录必须有 "id" 键（否则 KeyError）。
- 第37行 `if r["record_type"] != "review_result": continue` 只处理 record_type 为 "review_result" 的记录，其余被跳过。
- 第39行 `payload = r["payload"]` 要求有 "payload" 键。
- 第40行 `verdict = payload.get("confirmed_verdict") or payload.get("verdict") or {}` 从 payload 中取 verdict，优先 confirmed_verdict，其次 verdict，都没有则空字典。
- 第43行 `for change_id in payload.get("reviewed_change_ids", [])` 遍历 payload 里的 reviewed_change_ids（可缺省为空列表）。
- 第44行 `change = by_id.get(change_id)` 用 change_id 在 by_id 中查找对应记录，找不到则跳过（第45-46行）。
- 第47行 `cp = change["payload"]` 要求被引用的 change 记录必须有 "payload" 键。
- 第48行 `file_path = cp.get("tool_input", {}).get("file_path")` 从 change 的 payload.tool_input.file_path 取文件路径，tool_input 可缺省为空字典。

**输出**：返回一个列表 reviews，每个元素是字典，含键：logged_at、round_number、overall、summary、restated_intents、per_intent、matched_pattern_ids、changes。
- 第53-61行构造这些字段，其中 overall 默认 "未知"（第56行 `verdict.get("overall", "未知")`），summary 默认空串，其余列表字段默认空列表。
- changes 是去重后的列表（第44-51行，用 seen_files 集合按 file_path 去重），每个元素含 file_path 和 tool_name（tool_name 默认 "?"，第49行）。
- 第62行 `reviews.sort(key=lambda x: x["logged_at"], reverse=True)` 按 logged_at 降序排序后返回。

**副作用**：无。该函数不写文件、不改全局数据、不修改传入的 records（只读）。它只做纯计算并返回新列表。

**前置条件**：
- records 中每个元素必须是字典且含 "id"、"record_type"、"logged_at"、"payload" 键（缺 id 会 KeyError）。
- 被 reviewed_change_ids 引用的记录必须存在且含 "payload" 键，否则该 change 被静默跳过（第44-46行）。
- 各记录 payload 的 verdict 结构需符合预期（overall/summary/restated_intents/per_intent/matched_pattern_ids），缺失时用默认值兜底。

**调用后保证**：
- 返回的列表只包含 record_type == "review_result" 的记录，且按 logged_at 降序。
- 每个返回项的 changes 是去重后的文件列表（同一文件只出现一次，取首次出现的 tool_name）。
- 不会抛出因缺失可选字段的异常（除 id 外），缺失字段均被默认值替代。

【调用方须知】最容易被忽略的是：函数对 records 中每条记录的 "id" 键是硬性要求（第35行 `r["id"]` 直接索引，缺了会抛 KeyError），但被引用的 change 记录（reviewed_change_ids 指向的）却可以缺失——缺失时该 change 被静默丢弃（第44-46行 continue），不会报错，导致返回的 changes 列表可能比预期少，调用方若依赖 changes 完整性需自行校验 reviewed_change_ids 是否都能在 records 中找到。

*✓ 核实通过——候选答案对 collect_reviews 的契约描述与代码实际行为完全一致，包括输入要求、输出结构、默认值、去重逻辑和排序，且明确指出 id 键硬性要求而 change 缺失静默跳过的关键点。*

### [B] ledger\_deepseek.py :: load_env_file（第18行，复杂度6）

函数 load_env_file 定义在 ledger/_deepseek.py 第18-26行（注意：问题里写的 ledger_deepseek.py 实际是 ledger/_deepseek.py）。

【契约】

输入：无参数。它读取的输入是模块级常量 ENV_FILE（第8行：ENV_FILE = Path(__file__).resolve().parent.parent / ".env"），即项目根目录下的 .env 文件。

输出：无返回值（函数体里没有任何 return 语句，只有第20行的裸 return 用于提前退出）。

副作用：修改外部全局状态——通过 os.environ.setdefault 把 .env 文件里的键值对写入进程的环境变量（第26行）。注意它用的是 setdefault，即只在环境变量尚未设置时才写入，不会覆盖已存在的环境变量。

前置条件：无强制前置条件。若 ENV_FILE 不存在，函数直接返回（第19-20行），不报错。

调用后保证：
- 若 .env 存在，其中形如 KEY=VALUE 的行（跳过空行、以 # 开头的注释行、不含 = 的行）会被解析，key 和 value 都经过 strip() 去除首尾空白，value 还会去掉首尾的单/双引号（第26行），然后以 setdefault 方式写入 os.environ。
- 若 .env 不存在，函数静默返回，不产生任何效果。

【调用方须知】该函数使用 os.environ.setdefault 而非直接赋值，因此它绝不会覆盖调用方或系统已设置的环境变量——如果调用方在调用 load_env_file 之前已经手动设置了 DEEPSEEK_API_KEY（或任何同名变量），.env 文件里的对应值会被忽略，最终生效的是先设置的那个值；若你的程序依赖 .env 里的配置覆盖外部环境，需要先清空相关环境变量再调用本函数。

*✓ 核实通过——候选答案对函数位置、输入输出、副作用（setdefault 不覆盖）、前置条件（文件不存在静默返回）的描述均与代码原文一致，调用方须知也准确指出了 setdefault 不覆盖已存在环境变量的关键行为。*

### [B] ledger\_text_safety.py :: sanitize（第33行，复杂度6）

在 ledger/_text_safety.py 中，sanitize 函数（第33行）的契约如下：

**输入**：任意 Python 对象（value）。
**输出**：与输入同类型的对象，其中所有字符串都被清洗过；非字符串、非 dict、非 list 的值原样返回。
**副作用**：无。不修改外部状态、文件或全局数据，是纯函数。
**前置条件**：无特殊前置条件，可对任意值调用。
**保证**：
- 若 value 是 str，返回 sanitize_text(value) 的结果（第37行 `return sanitize_text(value)`）。
- 若 value 是 dict，返回一个新 dict，键不变，值递归调用 sanitize（第39行 `return {k: sanitize(v) for k, v in value.items()}`）。
- 若 value 是 list，返回一个新 list，每个元素递归调用 sanitize（第41行 `return [sanitize(v) for v in value]`）。
- 其他类型（int、None 等）原样返回（第42行 `return value`）。

递归清洗的具体行为由 sanitize_text 定义（第22行）：只处理字符串，删除孤立代理字符（`_SURROGATE_RE.sub("", value)`，第27行）、删除 BOM/零宽空格等隐形字符（第28-30行循环 replace）、并做 NFC 规范化（第31行 `unicodedata.normalize("NFC", value)`）。

【调用方须知】sanitize 只清洗字符串内容，但 dict 的**键**不会被清洗——第39行 `{k: sanitize(v) for k, v in value.items()}` 中键 k 原样保留，如果键本身含 BOM 或零宽空格（例如从外部 API 返回的字段名带隐形字符），这些键不会被清理，可能导致后续按键查找时匹配失败；若需清洗键，必须自行处理。

*✓ 核实通过——候选答案逐条对应代码原文，输入输出、递归行为、无副作用、前置条件均属实，且键不被清洗的提醒准确。*

### [B] ledger\confirm_intent.py :: main（第51行，复杂度9）

函数 main() 位于 ledger/confirm_intent.py 第 51 行，是脚本入口（`if __name__ == "__main__": main()`），无参数、无返回值（隐式返回 None）。

**输入**：无显式参数。它从外部读取两类输入：
1. 环境变量（通过 `load_env_file()` 加载，第 54 行）；
2. 持久化记录文件 events.jsonl（通过 `load_records()` 读取，第 56 行），从中筛选出上次 intent_snapshot 之后的所有 `user_prompt_submit` 记录（`collect_window`，第 57 行）。

**输出**：
- 若没有待确认消息，打印提示并直接 return（第 60-61 行）；
- 否则打印候选意图列表，并通过 `safe_input` 与用户交互（第 76-78 行）；
- 确认后打印“已确认（第 N 轮），记录已写入 events.jsonl。”（第 91 行）。

**副作用（外部状态变更）**：
- 调用 `setup_utf8_io()` 设置标准 IO 编码（第 53 行）；
- 调用 `load_env_file()` 加载 .env 环境变量（第 54 行）；
- 调用 `call_deepseek(SYSTEM_PROMPT, combined_text)` 发起外部 API 请求（第 70 行），消耗 API 配额；
- 用户确认后调用 `append_record("intent_snapshot", {...})` 向 events.jsonl 追加一条记录（第 82-90 行），这是最核心的持久化副作用——写入轮次编号、覆盖的消息 ID、候选/确认意图。

**前置条件**：
- 环境变量已配置（DeepSeek API Key 等），否则 `call_deepseek` 可能失败（第 70 行）；
- events.jsonl 存在且可读写；
- 标准输入可用（交互式确认）。

**调用后保证**：
- 若用户确认，会写入一条 intent_snapshot 记录，且该记录的 `covered_message_ids` 覆盖了本次窗口内所有消息 ID，后续 `collect_window` 将不再包含这些消息（因为 last_snapshot_index 更新）；
- 若用户选择重新分析，会再次调用 DeepSeek 并循环，直到确认或放弃；
- 若 DeepSeek 返回无法解析的内容，`parse_intents` 会退化为按行拆分（第 44-47 行），保证至少返回非空列表（除非原始内容全空）。

【调用方须知】最容易被忽略的是：main() 的“确认”动作会**永久性地把当前窗口内的所有消息标记为已覆盖**（写入 `covered_message_ids`），一旦确认，这些对话消息就再也不会出现在后续的确认窗口中——即使你当时只确认了部分意图、或者事后发现漏了需求，也无法再通过本工具重新提取这些消息的意图（工具明确提示“不支持逐条编辑”）。因此确认前务必仔细核对候选列表，确认后这些消息就“消费”掉了。

*✓ 核实通过——候选答案对 main() 的输入、输出、副作用、前置条件和保证的描述均与代码逐行吻合，且【调用方须知】指出的 covered_message_ids 永久覆盖行为在代码第84行明确体现。*

### [B] ledger\confirm_intent.py :: parse_intents（第40行，复杂度6）

parse_intents 的契约如下（依据 ledger/confirm_intent.py 第 40-48 行）：

【输入】一个字符串 raw_content（通常是 DeepSeek 返回的文本，见 main() 中 call_deepseek 的返回值）。

【输出】返回一个字符串列表。

【行为/副作用】无副作用——不写文件、不改全局状态、不调用外部 API，是纯函数。

【前置条件】无。对任意字符串都能安全调用，内部有 try/except 兜底。

【保证】
1. 若输入是合法 JSON 且其 "intents" 字段是非空列表，则返回该列表（第 42-45 行：`data.get("intents", [])`，`if isinstance(intents, list) and intents: return intents`）。
2. 若 JSON 解析失败（json.JSONDecodeError），或 "intents" 缺失/为空/不是列表，则回退为按行拆分：对每行去掉行首的 `-`、`•`、`*`、空格、制表符，并过滤空行（第 47-48 行：`[line.strip("-•* \t") for line in raw_content.splitlines() if line.strip()]`）。
3. 注意：回退分支不保证返回非空——若输入全是空行/空白，返回空列表。

【调用方须知】最容易忽略的是：当输入是合法 JSON 但 "intents" 字段为空列表（`[]`）时，函数会走回退分支，把整个 JSON 字符串按行拆成文本片段返回（比如返回 `['{"intents": []}']` 这样的垃圾列表），而不是返回空列表——因为第 44 行的 `and intents` 要求列表非空才走 JSON 分支。所以调用方不能依赖"JSON 合法就返回 JSON 内容"，必须自己再校验返回值是否真的是意图列表。

*✓ 核实通过——候选答案对输入输出、无副作用、前置条件、JSON分支和回退分支的描述均与代码逐行吻合，且正确指出空列表`[]`会走回退分支的边界情况。*

### [C] ledger\hooks\remind.py :: count_pending（第21行，复杂度15）

函数 count_pending(records) 位于 ledger/hooks/remind.py 第21行，契约如下：

**输入**：一个 records 列表，其中每个元素是字典，必须包含键 "record_type"（字符串），且可能包含 "payload"（字典，含 "intent_snapshot_id"）和 "id"（用于 intent_snapshot 记录）。依据：函数内多处访问 r["record_type"]、r["payload"]["intent_snapshot_id"]、s["id"]。

**输出**：返回一个三元组 (pending_messages, pending_changes, pending_reviews)，均为整数。
- pending_messages：最后一个 "intent_snapshot" 记录之后出现的 "user_prompt_submit" 记录数量。依据：`last_snapshot_index` 初始为 -1，遍历找最后一个 intent_snapshot，然后 `sum(1 for r in records[last_snapshot_index + 1:] if r["record_type"] == "user_prompt_submit")`。
- pending_changes：最后一个 "review_result" 记录之后出现的 "post_tool_use" 记录数量。依据：`last_review_index` 初始为 -1，遍历找最后一个 review_result，然后 `sum(1 for r in records[last_review_index + 1:] if r["record_type"] == "post_tool_use")`。
- pending_reviews：所有 "intent_snapshot" 记录中，其 "id" 不在任何 "review_result" 记录的 "payload"["intent_snapshot_id"] 集合里的数量。依据：`snapshots = [r for r in records if r["record_type"] == "intent_snapshot"]`，`reviewed_ids = {r["payload"]["intent_snapshot_id"] for r in records if r["record_type"] == "review_result"}`，`pending_reviews = sum(1 for s in snapshots if s["id"] not in reviewed_ids)`。

**副作用**：无。函数不修改传入的 records 列表，不写文件、不打印、不改变全局状态。它只做局部变量计算并返回。依据：函数体内只有局部变量赋值和 return，没有对 records 或任何外部对象进行赋值/修改。

**前置条件**：
1. records 必须是非空列表（或至少可迭代），否则 `records[last_snapshot_index + 1:]` 在 last_snapshot_index=-1 时等价于 records[0:]，仍可工作，但若 records 为空，切片为空，返回 (0,0,0)，不会报错。
2. 每个记录字典必须包含 "record_type" 键，否则访问 r["record_type"] 会抛 KeyError。
3. 对于 "review_result" 记录，必须包含 "payload" 且 "payload" 含 "intent_snapshot_id" 键，否则集合推导会抛 KeyError。
4. 对于 "intent_snapshot" 记录，必须包含 "id" 键，否则 `s["id"]` 抛 KeyError。

**调用后保证**：返回的三个整数分别代表上述三类待处理数量，且均为非负整数（因为 sum 计数）。函数不改变任何外部状态。

【调用方须知】最该警惕的是：pending_messages 和 pending_changes 的计数逻辑都依赖“最后一个特定类型记录的位置”——如果 records 中根本没有 "intent_snapshot" 或 "review_result" 记录，last_snapshot_index 或 last_review_index 会保持 -1，此时切片 records[0:] 会把整个列表都算进去，导致 pending_messages 统计所有 "user_prompt_submit"、pending_changes 统计所有 "post_tool_use"，这可能与直觉相反（以为没有快照/审查时应该返回 0）。调用方若期望“没有快照就没有待处理消息”，需要自行处理这种边界情况，而不是依赖 count_pending 的默认行为。

*✓ 核实通过——我直接读取了 ledger/hooks/remind.py 的完整代码，逐行核对了候选答案中引用的函数名、变量名、逻辑和边界行为，所有描述均与代码原文相符。*

### [B] ledger\view_events.py :: truncate（第12行，复杂度7）

函数 `truncate`（第12行）的契约如下，依据为 `ledger/view_events.py` 第12-19行原文：

**输入**：任意 Python 对象 `obj`（无类型限制，见 `def truncate(obj):`）。

**输出**：返回一个对象，规则为：
- 若 `obj` 是字符串且长度 > 300（`MAX_STR_LEN`），返回 `obj[:300] + f"...[还有 {len(obj)-300} 字符省略]"`（第13-14行）——即截断到300字符并追加省略说明。
- 若 `obj` 是字典，返回 `{k: truncate(v) for k, v in obj.items()}`（第15行）——对每个值递归调用 `truncate`，键不变。
- 若 `obj` 是列表，返回 `[truncate(v) for v in obj]`（第16行）——对每个元素递归调用。
- 其他类型（数字、布尔、None 等）原样返回（第17行 `return obj`）。

**副作用**：无。函数不修改任何外部状态、文件或全局数据；它只构造并返回新对象（字符串截断产生新字符串，字典/列表通过推导式生成新容器，原对象不被修改）。

**前置条件**：无。对任意输入均可调用，不会抛异常（对非字符串、非字典、非列表类型直接返回原值）。

**调用后保证**：返回的对象中，所有字符串（无论嵌套多深）长度不超过 300 字符（超长部分被替换为省略说明）；字典的键不被截断；原输入对象不被改变。

【调用方须知】该函数对字典只递归处理**值**，**键**（key）不会被截断——如果某个键本身是超长字符串，它会被原样保留，导致最终 `json.dumps` 输出中仍可能出现超长键；另外它只处理 `str`、`dict`、`list` 三种类型，若对象是元组（tuple）或自定义容器，其内部字符串不会被截断，会原样输出。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件的描述与代码逐条吻合，且调用方须知中关于键不截断和元组不处理的提醒准确。*

### [B] ledger\view_events.py :: main（第22行，复杂度6）

main() 是 ledger/view_events.py 的入口函数（第22行），无参数、无返回值，是一个命令行脚本的 main 函数。

**输入**：
- 无函数参数。
- 通过 `sys.argv[1]` 读取命令行第一个参数作为可选的项目路径（第24行：`project_path = sys.argv[1] if len(sys.argv) > 1 else None`）。

**输出**：
- 无返回值（隐式返回 None）。
- 向 stdout 打印内容：
  - 若事件文件不存在，打印 `f"还没有记录：{events_file}"`（第28行）。
  - 否则逐条打印每条记录，格式为 `--- 第 {i} 条 | {record['logged_at']} | {record['record_type']} ---` 和 `json.dumps(truncate(record), ensure_ascii=False, indent=2)`（第33-34行）。

**副作用**：
- 调用 `events_file_for(project_path)`（第25行），该函数在 `_store.py` 中会执行 `folder.mkdir(parents=True, exist_ok=True)`（_store.py 第24行），即**会创建数据目录**（若不存在）。
- 调用 `setup_utf8_io()`（模块顶层，第7行），设置 stdout/stderr 的 UTF-8 编码。
- 读取文件（只读），不修改事件文件内容。

**前置条件**：
- 模块顶层已执行 `setup_utf8_io()`（第7行）。
- 若传入项目路径，该路径需可被 `Path.resolve()` 解析（_store.py 中 `sanitize_project_path` 调用 `Path(path_str).resolve()`）。
- 事件文件（若存在）的每一行必须是合法的 JSON，且每条记录必须包含 `logged_at` 和 `record_type` 键（第33行直接访问 `record['logged_at']` 和 `record['record_type']`）。

**调用后保证**：
- 若事件文件不存在，打印提示并返回，不抛异常。
- 若文件存在，逐行解析并打印所有非空行（跳过空行，第31行 `if line.strip()`），每条记录打印后跟一个空行。
- 长字符串会被截断（`truncate` 函数，第10-18行），超过300字符的字符串会被截断并附省略说明。

【调用方须知】调用 main() 会通过 `events_file_for` 触发 `mkdir(parents=True, exist_ok=True)` 创建数据目录（即使只是查看也会创建目录），且若事件文件存在但某行 JSON 缺少 `logged_at` 或 `record_type` 键，会直接抛出 KeyError——调用方应确保事件文件格式符合 `append_record` 生成的记录结构（含 `logged_at`、`record_type`、`payload` 键）。

*✓ 核实通过——候选答案对 main() 的输入、输出、副作用、前置条件和保证的描述均与代码原文一致，包括通过 events_file_for 创建目录、直接访问 record['logged_at'] 和 record['record_type'] 可能抛 KeyError 等细节。*
