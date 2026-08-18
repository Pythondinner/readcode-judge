# 模块体检报告：writer.py

总行数289，代码行数194

## [C] write_long_script（第174行，复杂度13）

【write_long_script 契约】

**输入**（依据函数签名与 docstring）：
- `snapshot: dict`：已收尾的创作设定快照，必须含 `sub_intents` 字段（第174行签名；docstring 明确“把 sub_intents 按 chunk_size 拆成若干段”）。
- `mode: str`："novel" 或 "screenplay"，必须存在于 `MODE_INSTRUCTIONS`，否则 `write_script` 抛 `ValueError`（write_script 内 `if mode not in MODE_INSTRUCTIONS: raise ValueError`）。
- `chunk_size: int = 5`：每段包含的 sub_intents 条数（`CHAPTER_CHUNK_SIZE = 5`）。
- `previous_excerpt: str = None`：上一幕/上一段正文，仅用于延续文风（docstring："只用于延续文风/措辞"）。
- `world_state: str = None`：更早事实清单，硬性约束（write_script 的 CORE_RULES 中："<world_state>…这是硬性事实约束，优先级高于文风参考"）。
- `on_chapter=None`：可选回调，每写完一段调用一次（docstring："on_chapter(report) 可选，每写完一段调用一次"）。

**输出**（docstring 末尾）：返回 `(full_content, chapter_reports)` 元组。
- `full_content`：纯文本正文。若 `len(chunks) > 1`，用 `\n\n` 连接各段，每段前缀 `第{i}章\n\n`（代码：`f"第{i}章\n\n{c}"`）；若只有一段，直接返回该段内容，不产生章节标题（docstring："sub_intents 数量 <= chunk_size 时…不会产生章节标题"）。
- `chapter_reports`：每段一个 dict，含 `index`、`total`、`sub_intent_ids`（该段 sub_intents 的 id 列表）、`char_count`（len(content)）、`finish_reason`（"length" 表示该段被 max_tokens 截断）。

**副作用**：
- 调用 `deepseek_client.call`（网络 API 调用），消耗 token，且每次调用有 `WRITER_MAX_TOKENS = 8192` 上限，可能截断（`finish_reason == "length"`）。
- 每段调用 `extract_world_state(content)` 提炼事实清单，追加到局部 `rolling_world_states`，仅影响后续段，不写文件、不改全局。
- 若 `on_chapter` 传入，会同步调用它（可能触发外部副作用，如 UI 更新）。
- **不写任何文件、不修改 snapshot 或任何全局数据**——存档由 `write_and_save_one` 负责，本函数只返回内容。

**前置条件**：
- `snapshot` 必须含 `sub_intents`（可为空列表，代码 `snapshot.get("sub_intents") or []`，空时 `chunks=[[]]`，仍会调用一次 write_script 生成空段）。
- `mode` 必须是 "novel" 或 "screenplay"，否则 ValueError。
- 若传 `world_state`/`previous_excerpt`，其内容会被嵌入 user_content 的 `<world_state>`/`<previous_act_content>` 标签，需符合 CORE_RULES 中对应语义（world_state 是硬性事实约束）。

**调用后保证**：
- 返回的 `full_content` 中，若分段，每段以 `第N章` 标题分隔；若单段，无标题。
- 每段的 `finish_reason` 如实反映是否被截断（"length" 表示未正常写完）。
- 若某段 `extract_world_state` 抛 `ApiCallError`，会被捕获忽略，不影响已生成内容，只是下一段少该段事实参考（代码 try/except pass）。

【调用方须知】当 `sub_intents` 数量 > `chunk_size` 时，函数会在返回的 `full_content` 里自动插入 `第1章`、`第2章`… 这样的章节标题（代码 `f"第{i}章\n\n{c}"`），但 `write_script` 的 CORE_RULES 明确要求模型“不要自己生成章节编号，由外部系统统一处理”——也就是说这些标题是 write_long_script 事后拼上去的排版标记，不是模型正文的一部分；如果你把 `full_content` 再喂回下一幕的 `previous_excerpt`，模型会被要求“只学文字风格、不要模仿结构性标记”，所以这些章节标题不会污染续写，但如果你自己解析/展示这段内容，要意识到标题是函数加的，且只有 `len(chunks) > 1` 时才存在。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件、调用后保证的描述均与代码逐条吻合，且【调用方须知】指出的章节标题是函数事后拼接、非模型生成，与 CORE_RULES 中“不要自己生成章节编号”及代码 `f"第{i}章\n\n{c}"` 一致。*

## [B] write_script（第114行，复杂度6）

【write_script 契约】

**输入**（见 writer.py 第114行起函数签名）：
- `snapshot: dict`：已收尾的创作设定快照，含 `sub_intents`、`characters`、`rule_based`、`assumptions` 等字段（由 CORE_RULES 中的 schema 映射规则约束）。
- `mode: str`：必须为 `"novel"` 或 `"screenplay"`，否则抛 `ValueError`（代码：`if mode not in MODE_INSTRUCTIONS: raise ValueError(...)`）。
- `previous_excerpt: str = None`：上一幕同模式正文全文，仅用于延续文风/措辞。
- `world_state: str = None`：更早几幕的事实清单，硬性事实约束。
- `return_finish_reason: bool = False`：控制返回类型。

**输出**：
- 默认返回纯文本正文（`return_finish_reason=False` 时直接返回 `deepseek_client.call(...)` 的结果）。
- `return_finish_reason=True` 时返回 `(content, finish_reason)` 元组，`finish_reason == "length"` 表示被 `max_tokens` 截断（见 docstring 和 `WRITER_MAX_TOKENS = 8192`）。

**副作用**：
- 无直接文件/全局数据修改。它只调用 `deepseek_client.call(...)` 发起一次 LLM 请求，不写任何文件、不修改 snapshot 或全局状态。

**前置条件**：
- `mode` 必须在 `MODE_INSTRUCTIONS` 中（`"novel"`/`"screenplay"`），否则抛异常。
- `snapshot` 需包含 `sub_intents` 等字段（由 CORE_RULES 的 schema 映射规则隐含要求）。
- 调用方需保证 snapshot 已收尾（docstring 说“把一份已收尾的 snapshot 写成正文”）。

**调用后保证**：
- 返回的正文遵循 CORE_RULES 的硬性要求：`rule_based.must_include` 必须字面出现、`must_avoid` 绝不能出现；`sub_intents` 按 id 顺序逐场写，不遗漏不合并；`world_state` 的既成事实优先于新设定（CORE_RULES 中“以 <world_state> 记录的既成事实为准”）。
- 输出语言与 `<ledger_content>` 一致（通常中文）。
- 只输出正文，不输出解释/前言（CORE_RULES：“只输出正文内容，不要输出任何解释”）。

【调用方须知】当 `return_finish_reason=False`（默认）时，如果内容被 `max_tokens=8192` 截断，函数不会给出任何提示——它只返回被截断的纯文本，调用方无法察觉内容不完整；因此长文本场景必须显式传 `return_finish_reason=True` 并检查 `finish_reason == "length"`，否则会静默产出残缺正文。

*✓ 核实通过——逐条核对了函数签名、参数校验、docstring、CORE_RULES 相关规则和调用代码，候选答案的所有具体描述都与代码原文吻合，包括默认返回纯文本、截断时无提示的副作用。*

## [B] write_and_save_one（第242行，复杂度6）

函数 `write_and_save_one`（writer.py 第242行起）的契约如下，依据均为 writer.py 源码原文：

**输入**：
- `project_name: str`：项目名，用于定位快照和存档。
- `mode: str`："novel" 或 "screenplay"，决定输出格式。
- `on_chapter=None`：可选回调，每写完一段调用一次（`on_chapter(report)`）。

**输出**：返回 `(filename, content)` 元组——`filename` 是存档文件名，`content` 是生成的正文纯文本。

**副作用（外部状态/文件/全局数据改动）**：
1. 调用 `ledger.save_draft(project_name, mode, content)` 保存正文到磁盘。
2. 修改快照的 `_meta.generated_from`：`generated_from[mode] = predecessor_draft_filename`，然后 `ledger.save_snapshot` 写回快照（代码注释明确说明这是为了记录"这一幕参考的是上一幕哪个版本"）。
3. 调用 `ledger.save_world_state(project_name, mode, state_text)` 保存提炼出的运行事实清单。

**前置条件**：
- 这一幕的 snapshot 必须已存在且 `_meta` 里有 `predecessor` 字段（代码直接 `snapshot["_meta"].get("predecessor")`，若无 `_meta` 会抛 KeyError）。
- 调用方需确认这一幕状态是 confirmed——函数 docstring 明确说"这里不做校验"。
- 若 `predecessor` 存在，需要能通过 `ledger.latest_draft_filename` 找到上一幕的草稿文件，且 `ledger.load_draft` 能读到。

**调用后保证**：
- 正文已生成并保存到磁盘，返回文件名和内容。
- 快照的 `generated_from[mode]` 已更新并持久化。
- 若事实清单提炼成功，`save_world_state` 已保存；若提炼失败（`ApiCallError`），会静默跳过，不影响本次生成结果（代码 `except deepseek_client.ApiCallError: pass`）。

**【调用方须知】**：调用方最容易忽略的是：这个函数会**修改并持久化快照的 `_meta.generated_from` 字段**（`generated_from[mode] = predecessor_draft_filename`），即使你只是"生成一幕看看效果"，也会永久改写项目快照的元数据——如果上一幕之后又生成了新版本，这条记录会与"上一幕当前最新版本"不一致，前端会据此提示"参考可能过时"，但如果你没打算让这一幕正式成为后续的参考基准，这个副作用可能造成误导。

*✓ 核实通过——逐条对照 writer.py 源码，候选答案对输入、输出、副作用、前置条件、保证的描述均与代码原文相符，且【调用方须知】指出的 generated_from 副作用在代码中有明确注释支持。*

## [A] extract_world_state（第162行，复杂度1）

（复杂度低于B级，未生成行为描述）
