# 项目体检报告

共13个文件（另有0个不支持的文件类型被跳过），总行数2585

## 项目叙述（✓ 核实通过）

项目定位描述如下（依据：README.md、docs/11-系统架构总览.md、src/ 下各模块源码）：

## 1. 项目是什么

这是一个**基于 want/obstacle 张力理论的自动剧本/小说生成系统**。面向需要快速产出故事正文的用户（可能是编剧、小说作者或内容创作者），解决从模糊需求到完整正文的自动化问题：通过对话收集需求、推断结构化设定、确认后生成正文，并支持长篇分段、系列多幕续写、批量生成时自动质量检查与修复。

## 2. 模块组成与职责边界

- **brain.py**：交互层，显式状态机（empty→candidates_pending→collecting→confirmed），负责需求收集/推断/校验，不持久化，每次从 ledger 读、处理完写回。
- **ledger.py**：持久化层，快照+草稿存取、版本管理、系列目录结构，被动存取不做判断。
- **writer.py**：写手层，把 schema 翻译成正文，含长篇自动分段（write_long_script）、单幕生成（write_and_save_one）。
- **checker.py / checker_include.py**：must_avoid / must_include 语义检查器，只做判断。
- **goal_loop.py**：批量生成的自动检查+修复循环（write_with_check / write_missing_acts_in_series），手动模式的检测按钮也复用其诊断逻辑（check_and_report）。
- **chat.py**：终端交互入口。
- **server.py**：Web 后端（Flask），包一层 HTTP API。
- **deepseek_client.py**：共享 API 调用封装。

## 3. 关键不变量（含证据范围）

### 3.1 状态机转移合法性
- **不变量**：不允许转入 confirmed 除非 throughline.want 和 obstacle 都非空。
- **证据**：brain.py 的 process_turn 中，`if next_state == "confirmed": if not merged_throughline or not merged_throughline.get("want") or not merged_throughline.get("obstacle"): next_state = "collecting"`（同时 reject_throughline_patch 拒绝数据）。
- **覆盖入口**：chat.py 的 main 循环（调用 brain.process_turn）和 server.py 的 /api/projects/<name>/message 路由（同样调用 brain.process_turn）。两个入口共用同一函数，规则一致。

### 3.2 草稿版本不覆盖
- **不变量**：同一项目同一模式反复生成，新版本不覆盖旧版本，文件名带递增版本号。
- **证据**：ledger.py 的 save_draft 中，`next_version = (max(versions) + 1) if versions else 1`，文件名 `{mode}_v{next_version}.md`。
- **覆盖入口**：writer.write_and_save_one（手动单幕）、goal_loop.write_and_save_one_with_check（自动批量）都调用 ledger.save_draft，规则一致。

### 3.3 删除草稿时事实清单联动
- **不变量**：删除某模式最新版本草稿时，连带删除对应的运行事实清单（state 文件）；删除历史版本不影响。
- **证据**：ledger.py 的 delete_draft 中，`was_latest = mode and latest_draft_filename(project_name, mode) == filename`，若 was_latest 则删除 `{mode}_state.md`。
- **覆盖入口**：chat.py 的 offer_to_write 中 `删除<文件名>` 分支调用 ledger.delete_draft；server.py 的 DELETE /api/projects/<name>/drafts/<filename> 路由调用 ledger.delete_draft。两个入口一致。

### 3.4 系列续写前置条件
- **不变量**：只有 predecessor 状态为 confirmed 时才能创建续集。
- **证据**：ledger.py 的 create_continuation 中，`if pred_state != "confirmed": raise ContinuationError`。
- **覆盖入口**：chat.py 的 maybe_link_predecessor 调用 create_continuation；server.py 的 POST /api/projects/<name>/continue_from 路由调用 create_continuation。两个入口一致。

### 3.5 批量生成顺序与跳过/停止
- **不变量**：批量生成必须按链顺序执行；已有正文的幕次跳过；遇到未收尾的幕次停止（不继续处理后续）。
- **证据**：goal_loop.py 的 write_missing_acts_in_series 中，`if ledger.latest_draft(name, mode) is not None: results.append({"status": "skipped_exists"}); continue`；`if ledger.load_snapshot(name)["_meta"]["project_state"] != "confirmed": results.append({"status": "skipped_not_confirmed"}); break`。
- **覆盖入口**：chat.py 的 offer_to_write 中 `批量小说/批量剧本` 分支调用 write_missing_acts_in_series；server.py 的 POST /api/projects/<name>/write_series 路由调用 write_missing_acts_in_series。两个入口一致。

### 3.6 手动模式检测不自动修改
- **不变量**：手动模式的检测（check_and_report）只诊断、不修改任何内容（不调用 repair_sub_intent、不重试）。
- **证据**：goal_loop.py 的 check_and_report 中，只调用 checker/checker_include 和 diagnose，不调用 repair_sub_intent；注释明确"只查、只诊断，不自动修复"。
- **覆盖入口**：chat.py 的 offer_to_write 中 `检测` 分支调用 check_and_report；server.py 的 POST /api/projects/<name>/drafts/<filename>/check 路由调用 check_and_report。两个入口一致。

### 3.7 自动路径的修复持久化边界
- **不变量**：自动路径（write_and_save_one_with_check）中，sub_intent 修复结果存回 snapshot，但 must_avoid/must_include 的加固措辞不持久化。
- **证据**：goal_loop.py 的 write_and_save_one_with_check 中，`if result["sub_intent_changes"]: current["sub_intents"] = result["snapshot"]["sub_intents"]; ledger.save_snapshot(...)`，但 must_avoid/must_include 的加固只在 write_with_check 内部的内存副本上修改，不写回 ledger。
- **覆盖入口**：仅自动路径（write_and_save_one_with_check），手动路径不涉及。

### 3.8 封顶未通过时草稿仍保存但标记
- **不变量**：自动路径封顶（cap_reached）时，草稿仍无条件保存，但会写一个 `.unchecked` 标记文件。
- **证据**：goal_loop.py 的 write_and_save_one_with_check 中，`if result["status"] == "cap_reached": ledger.mark_draft_unchecked(project_name, filename)`。
- **覆盖入口**：仅自动路径。

### 3.9 重试时 previous_excerpt 保持不变
- **不变量**：goal loop 重试时，previous_excerpt（跨幕文风锚点）不被替换成本幕失败的重试草稿。
- **证据**：goal_loop.py 的 write_with_check 中，`previous_excerpt` 参数在循环外传入，循环内调用 write_long_script 时始终使用该参数，不更新。
- **覆盖入口**：仅自动路径（write_with_check）。

### 3.10 系列续写时 want/obstacle 必须重新推导
- **不变量**：新一幕承接时，角色/场景等既有事实继承，但 want/obstacle 不能照抄上一幕，必须重新确立。
- **证据**：ledger.py 的 build_continuity_brief 中，只搬运 characters/setting/genre/tone，不搬运 throughline；brain.py 的 STATE_INSTRUCTIONS["empty"] 中明确"throughline.want/obstacle 依然必须重新确立，不能照抄上一幕的"。
- **覆盖入口**：chat.py 和 server.py 的续写入口都通过 create_continuation 创建种子快照（不含 throughline），后续通过 brain.process_turn 重新推导。

### 3.11 删除项目需两步确认（Web 入口）
- **不变量**：Web 端删除项目必须走"先查询依赖、用户确认、再带 force=true"两步流程，不带 force 不真的删。
- **证据**：server.py 的 DELETE /api/projects/<name> 中，`if not force: return jsonify({"needs_confirmation": True, ...})`，只有 force=true 才调用 ledger.delete_project。
- **覆盖入口**：仅 server.py（Web 入口）。chat.py 没有删除项目的功能，因此这条规则只对 Web 入口成立。

### 3.12 重新生成需两步确认（Web 入口）
- **不变量**：Web 端重新生成已有正文的幕次，不带 force 不真的生成，先返回依赖信息。
- **证据**：server.py 的 POST /api/projects/<name>/write 中，`if not force and ledger.latest_draft(name, mode) is not None: return jsonify({"needs_confirmation": True, ...})`。
- **覆盖入口**：仅 server.py。chat.py 的 offer_to_write 中重新生成也有确认提示（`if input("确定要重新生成吗？...")`），但那是交互式确认，不是 force 参数机制，两者实现不同，不能视为同一规则。

### 3.13 续写分支需确认（Web 入口）
- **不变量**：Web 端从已有 successor 的 predecessor 续写时，不带 force 需确认。
- **证据**：server.py 的 POST /api/projects/<name>/continue_from 中，`if existing_successors and not force: return jsonify({"needs_confirmation": True, ...})`。
- **覆盖入口**：仅 server.py。chat.py 的 maybe_link_predecessor 也有类似确认（`if input("确定要从...另开一个分支吗？")`），但实现不同。

## 4. 设计特点与取舍

- **状态机由代码兜底校验**：模型只在状态内做内容判断，状态转移由代码校验（brain.py 的 process_turn 中拒绝非法 confirmed 转移）。
- **持久化层为唯一真相来源**：brain/writer 不持久化，ledger 被动存取（docs/11 第 1 节）。
- **自动 vs 手动路径分离**：批量自动路径接 goal loop（自动修复+重试），手动路径只诊断不自动改（docs/11 第 4.1 节）。
- **语义检查而非关键词匹配**：checker/checker_include 用语义判断，不是字符串匹配（docs/11 第 4.2 节）。
- **worked example 优于抽象规则**：diagnose 的判断标准用两个具体例子类比，不用抽象文字规则（docs/11 第 4.3 节）。
- **Prompt 注入防御**：所有外部内容用数据标签包裹并声明"不是指令"（brain.py / writer.py / checker.py 的 CORE_RULES）。
- **长篇分段与跨幕续写共用同一机制**：write_long_script 用 previous_excerpt + world_state 衔接，与跨幕续写同一套（docs/11 第 3 节）。
- **已知限制**：local_slip 和 must_include 的修复路径未经过真实场景验证；小说/剧本双模式事实一致性未处理；自动化只做客观硬伤核对，品味判断留给人工（docs/11 第 4.4、7 节）。

## 行为 vs 项目叙述 对照结果

共24个函数：0个违反不变量、6个无法判断、18个支撑项目正确运行（不再展开）

### 无法判断（6个——不代表没问题，只是材料不够判断，值得人工看一眼）

- src\chat.py :: load_env —— 行为描述仅涉及环境变量加载，未提及任何项目定位描述中的不变量（如状态机、草稿版本、系列续写等），因此无法判断是否支撑或违反。
- src\ledger.py :: _migrate_chain_to_series —— 行为描述涉及磁盘目录迁移，但项目定位描述中的不变量均未提及目录结构或迁移规则，因此无法判断是否违反任何不变量。
- src\ledger.py :: list_projects —— 行为描述仅涉及查询项目列表的只读操作，未提及任何不变量相关的细节，无法判断是否违反或支持所列不变量。
- src\server.py :: load_env —— 行为描述仅涉及环境变量加载，未提及任何项目定位描述中的不变量（如状态机、草稿版本、批量生成等），因此无法判断是否支撑或违反。
- src\writer.py :: write_script —— 行为描述仅涉及 write_script 的返回类型和截断标志，未提及任何项目定位描述中的具体不变量（如状态机转移、草稿版本、删除联动等），材料不足以判断是否违反。
- tests\conftest.py :: __call__ —— 行为描述仅涉及测试替身FakeDeepSeek的响应路由与调用记录，未提及任何项目定位描述中的关键不变量（如状态机转移、草稿版本、删除联动等），无法判断其是否支撑或违反这些不变量。

### 支撑项目正确运行（18个，不再展开）

src\brain.py::process_turn、src\chat.py::offer_to_write、src\chat.py::main、src\chat.py::maybe_link_predecessor、src\deepseek_client.py::call、src\goal_loop.py::write_with_check、src\goal_loop.py::check_and_report、src\goal_loop.py::write_and_save_one_with_check、src\ledger.py::save_draft、src\ledger.py::delete_draft、src\server.py::continue_from、src\server.py::write_draft、src\writer.py::write_long_script、src\writer.py::write_and_save_one、tests\test_goal_loop.py::test_structural_conflict_gets_repaired_and_retry_passes、tests\test_goal_loop.py::test_write_missing_acts_in_series_skips_existing_and_stops_at_unconfirmed、tests\test_ledger.py::test_save_draft_versions_increment_and_dont_overwrite、tests\test_writer_chunking.py::test_long_snapshot_splits_into_multiple_chunks_with_headers


## 复杂度分级分布

- [A] 77个函数/类
- [B] 18个函数/类
- [C] 4个函数/类
- [D] 2个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [D] src\chat.py :: offer_to_write（第102行）复杂度=27
  [D] src\goal_loop.py :: write_with_check（第124行）复杂度=26
  [C] src\chat.py :: main（第205行）复杂度=17
  [C] src\brain.py :: process_turn（第166行）复杂度=15
  [C] src\writer.py :: write_long_script（第174行）复杂度=13
  [C] src\deepseek_client.py :: call（第28行）复杂度=11
  [B] src\chat.py :: maybe_link_predecessor（第56行）复杂度=10
  [B] src\goal_loop.py :: check_and_report（第228行）复杂度=10
  [B] tests\conftest.py :: __call__（第38行）复杂度=10
  [B] src\ledger.py :: _migrate_chain_to_series（第153行）复杂度=9
  [B] src\server.py :: continue_from（第44行）复杂度=9
  [B] src\server.py :: write_draft（第192行）复杂度=9
  [B] src\goal_loop.py :: write_and_save_one_with_check（第263行）复杂度=8
  [B] tests\test_goal_loop.py :: test_structural_conflict_gets_repaired_and_retry_passes（第20行）复杂度=8
  [B] tests\test_goal_loop.py :: test_write_missing_acts_in_series_skips_existing_and_stops_at_unconfirmed（第194行）复杂度=8

## 行为描述明细（B级以上，共24个）

### [C] src\brain.py :: process_turn（第166行，复杂度15）

process_turn(snapshot: dict, user_input: str) -> dict 的契约如下（依据 src/brain.py 第166-212行）：

**输入**
- `snapshot`: 一个 dict，必须含 `_meta.project_state`（第170行 `state = snapshot["_meta"]["project_state"]`），且 `_meta` 会被原地修改（第207-210行）。
- `user_input`: 字符串，本轮用户输入。

**输出**
- 返回同一个 `snapshot` 对象（原地修改后返回，第212行 `return snapshot`），不是新对象。

**副作用（外部状态/全局数据）**
- 原地修改传入的 `snapshot`：合并 patch 到顶层字段（第198-202行）、写入 `raw_user_request`（第204-205行）、更新 `_meta.project_state`（第207行）、写入 `_meta.flagged_injection`/`flagged_snippets`/`conflicts_flagged`（第208-210行）、写入 `_last_reply`（第211行）。
- 调用 `deepseek_client.call`（第164行 `_call_model`），即发起一次外部 API 调用，有网络/计费副作用。

**前置条件**
- `snapshot` 必须包含 `_meta` 且 `_meta` 可写（会被修改）；`_meta.project_state` 若不在 VALID_STATES 会被重置为 "empty"（第171-172行）。
- `snapshot` 中 `throughline` 字段（若存在）需为 dict 或 None，因为第190行会调用 `.get("want")`。
- 无其他严格前置条件；`user_input` 可为任意字符串。

**调用后保证**
- 返回的 `snapshot` 的 `_meta.project_state` 一定在 VALID_STATES 内（第193-194行兜底）。
- 若 `next_state == "confirmed"` 但合并后的 throughline 缺 want 或 obstacle，则强制回退到 "collecting"，且该轮的 throughline patch 被丢弃（第188-192行、第199-200行）。
- patch 中出现的顶层字段（rule_based/throughline/candidates/sub_intents/assumptions）整体替换旧值，未出现的保留（第198-202行）。
- `_last_reply` 一定被设置为模型返回的 assistant_reply（第211行）。

【调用方须知】process_turn 会**原地修改并返回你传入的 snapshot 对象**——它不是纯函数，调用后原对象已被改写（包括 `_meta.project_state`、`_last_reply`、以及 patch 命中的顶层字段），如果你还需要调用前的快照，必须先自行深拷贝；另外它每次调用都会真实触发一次 deepseek API 请求（第164行），有成本，不要无谓重复调用。

*✓ 核实通过——候选答案逐条与代码原文核对，所有行为描述（输入要求、原地修改、副作用、前置条件、状态回退逻辑）均与第166-212行实际代码一致，且引用的行号和函数名准确无误。*

### [D] src\chat.py :: offer_to_write（第102行，复杂度27）

函数 `offer_to_write(project_name: str, snapshot: dict) -> None`（src/chat.py 第102行）的契约如下：

**输入**：
- `project_name: str`：项目名，用于定位 ledger 中的草稿、快照等（如 `ledger.list_drafts(project_name)`、`ledger.latest_draft(project_name, mode)`）。
- `snapshot: dict`：当前项目快照，函数只读取 `snapshot["_meta"].get("predecessor")`（第157行）来提示上一幕是否已生成正文。

**输出**：无返回值（`-> None`）。所有结果都通过 `print` 输出到 stdout，或通过 `input` 交互。

**副作用（修改外部状态）**：
1. 当用户输入 `删除<文件名>` 时，调用 `ledger.delete_draft(project_name, filename)`（第118行）删除草稿文件，并可能连带清除运行事实清单（打印信息“如果它是当时最新版本，对应的运行事实清单也一并清掉了”）。
2. 当用户选择生成正文（小说/剧本/批量）时，调用 `writer.write_and_save_one(project_name, mode, ...)`（第176行）或 `goal_loop.write_missing_acts_in_series(...)`（第127行），会写入草稿文件到 `ledger/…/drafts/`（打印“已生成并存入 ledger/…/drafts/{filename}”）。
3. 当用户输入 `检测` 时，调用 `goal_loop.check_and_report(...)`（第194行），但该调用只读快照（`ledger.load_snapshot`）并打印报告，不修改任何内容（打印“仅供参考，不会自动修改任何内容”）。

**前置条件**：
- 调用方应确保 `project_name` 对应的项目已存在且快照可加载（函数内部会调用 `ledger.list_drafts`、`ledger.latest_draft`、`ledger.load_snapshot` 等，若项目不存在可能抛异常）。
- 函数设计为在项目“收尾后”（state == "confirmed"）调用（见 main 第222行 `if state == "confirmed": offer_to_write(...)`），但函数本身不校验 state。
- 需要 `writer.deepseek_client` 可用，否则生成正文时会捕获 `ApiCallError` 并打印失败信息（第178行、第132行）。

**调用后保证**：
- 函数会一直循环直到用户直接回车（`if not choice: return`，第110行）才返回。
- 若生成正文失败（ApiCallError），不会写入任何文件（打印“生成失败，没有写入任何文件”），可重试。
- 批量生成中途失败时，已生成的部分保留，可重新执行补齐（第133行）。
- 函数不修改传入的 `snapshot` 对象（只读取 `_meta.predecessor`）。

【调用方须知】最该警惕的是：函数内部会**实际写入/删除磁盘上的草稿文件**（通过 `writer.write_and_save_one` 和 `ledger.delete_draft`），且这些操作**只在用户交互确认后触发**——但函数名“offer_to_write”字面上只暗示“询问是否写”，实际它还会处理“删除草稿”和“批量补齐系列幕次”两类操作；尤其删除草稿时，如果删除的是当时最新版本，会**连带清除对应的运行事实清单**（第118行打印信息），这是名字看不出来、且不可逆的副作用，调用方若在自动化/非交互场景误用（例如传入非交互输入流）可能意外删数据。

*✓ 核实通过——逐条核对了候选答案中的每个具体说法，与代码原文完全一致，包括行号、函数调用、打印信息和行为描述。*

### [C] src\chat.py :: main（第205行，复杂度17）

【main 的契约】

**输入**：
- 无参数（`def main():`，第205行）。
- 通过 `sys.argv` 读取命令行参数：`project_name = sys.argv[1] if len(sys.argv) > 1 else choose_project()`（第211行），`predecessor_arg = sys.argv[2] if len(sys.argv) > 2 else None`（第210行）。
- 通过 `input()` 从 stdin 读取用户多轮输入（第238、243、248行等）。

**输出**：
- 无返回值（函数体末尾无 return 或 return 不带值，第269行 `break` 后结束）。
- 副作用输出到 stdout：打印项目状态、brain 回复、snapshot（`print_snapshot`）、正文预览等。

**副作用（外部状态/文件/全局数据）**：
1. **持久化 ledger 文件**：每轮对话后调用 `ledger.save_snapshot(project_name, snapshot)`（第255行）和 `ledger.append_log(project_name, "user", user_input)`、`ledger.append_log(project_name, "brain", ...)`（第256-257行），写入项目快照和对话日志。
2. **创建承接关系**：`maybe_link_predecessor(project_name, predecessor_arg)`（第212行）内部调用 `ledger.create_continuation(project_name, predecessor)`（第92行），创建项目间的承接关系。
3. **生成/删除正文文件**：`offer_to_write`（第268行调用）内部调用 `writer.write_and_save_one`（第174行）写文件、`ledger.delete_draft`（第126行）删文件、`goal_loop.write_missing_acts_in_series`（第135行）批量写文件。
4. **环境变量**：`load_env()`（第208行）读取 `.env` 文件并 `os.environ.setdefault` 设置环境变量。
5. **stdout 编码**：`sys.stdout.reconfigure(encoding="utf-8")`（第206行）修改全局 stdout 编码。

**前置条件**：
- 依赖模块 `brain`、`goal_loop`、`ledger`、`writer` 可导入（第8-11行）。
- 若项目已存在，`ledger.load_snapshot(project_name)`（第213行）能读到快照；若不存在，`maybe_link_predecessor` 会尝试创建或走全新流程。
- 需要 `.env` 文件（若存在）提供 API key 等（`load_env`）。

**调用后保证**：
- 若项目状态为 `confirmed`（已收尾），打印提示后调用 `offer_to_write` 并 `return`（第225-228行），不再进入对话循环。
- 否则进入 while 循环，每轮：若输入 exit/quit 则 break；若输入“状态”则打印 snapshot 不消耗模型调用；否则调用 `brain.process_turn`，出错时打印错误且不保存（第251-254行），成功后保存快照和日志，若状态变为 `confirmed` 则调用 `offer_to_write` 并 break（第266-268行）。
- 循环中捕获 `EOFError`/`KeyboardInterrupt` 正常退出（第239-241行）。

【调用方须知】main 会**在每轮对话后无条件把快照和日志写入 ledger 文件**（`ledger.save_snapshot` + `ledger.append_log`，第255-257行），即使这轮 brain 回复只是普通闲聊也会持久化——所以调用方若只想“试一下不落盘”是做不到的，任何一次 `input` 后的成功处理都会改磁盘上的项目状态；另外它还会在收尾时通过 `offer_to_write` 直接写正文文件、删文件、批量生成，这些文件操作都发生在 main 内部，调用方无法预先拦截。

*✓ 核实通过——我逐行核对了 src/chat.py 的 main 函数及其调用的相关函数，候选答案中引用的行号、函数名、行为描述均与代码原文一致，没有发现任何虚构或错误之处。*

### [B] src\chat.py :: maybe_link_predecessor（第56行，复杂度10）

函数 `maybe_link_predecessor(project_name: str, predecessor_arg: str = None) -> None` 位于 src/chat.py 第 56 行，其契约如下：

**输入**
- `project_name`：目标项目名（字符串）。
- `predecessor_arg`：可选，命令行传入的承接源项目名（默认 None）。

**输出**
- 无返回值（`-> None`）。

**副作用（外部状态/文件/全局数据）**
- 可能调用 `ledger.create_continuation(project_name, predecessor)`（第 99 行），该函数会创建新项目文件夹并写入 snapshot.json（见 ledger.py 第 236-244 行），即持久化地新建一个承接项目。
- 可能调用 `ledger.find_successors` / `ledger.find_leaf_descendants`（第 84、86 行），这些是纯查询，无副作用。
- 会向 stdout 打印提示信息（第 88-90、101 行等）。
- 不修改任何全局变量。

**前置条件**
- 调用前 `ledger` 模块已可用（`ledger.list_projects()` 能正常执行）。
- 若 `predecessor_arg` 非空，它必须是 `existing` 列表中的项目名，否则函数会打印提示并直接返回（第 79-81 行）。
- 若 `predecessor` 已存在且有后继（`existing_successors` 非空），需要用户输入“是”确认，否则取消续写（第 84-93 行）。

**调用后保证**
- 若 `project_name` 已存在于 `ledger.list_projects()`，函数立即返回，不做任何改动（第 60-61 行）。
- 若 `project_name` 是全新项目且没有其他项目可承接（`existing` 为空），直接返回，不创建任何东西（第 62-63 行）。
- 若用户未提供承接源且输入为空，直接返回，不创建（第 70-72 行）。
- 若承接源无效（不在 `existing` 中），打印提示并返回，不创建（第 79-81 行）。
- 若用户取消确认（输入非“是”），打印提示并返回，不创建（第 92-93 行）。
- 若成功调用 `create_continuation`，会创建新项目并打印成功信息（第 99-101 行）。
- 若 `create_continuation` 抛出 `ledger.ContinuationError`，捕获并打印错误，不创建（第 102-103 行）。

【调用方须知】最容易被忽略的是：即使 `predecessor` 已存在且有后继（即它不是这条链的最新一幕），函数仍可能创建承接——它只是打印警告并要求用户输入“是”确认，但若用户输入“是”，就会从非最新的幕次创建新分支，这会导致系列出现分叉，后续 `find_leaf_descendants` 会返回多个末端，且 `dependent_drafts` 等逻辑会同时影响多个分支，调用方若未预期分叉可能产生数据不一致。

*✓ 核实通过——我逐行核对了 src/chat.py 中该函数的完整实现，并对照 ledger.py 中 `create_continuation` 的行为，确认候选答案的每一条描述都有代码依据，没有虚构或夸大。*

### [B] src\chat.py :: load_env（第25行，复杂度6）

函数 `load_env(path=".env")`（src/chat.py 第25-32行）的契约如下：

**输入**：一个可选参数 `path`，默认值为字符串 `".env"`（第25行 `def load_env(path=".env"):`）。

**输出**：无返回值（函数体没有 `return` 语句，隐式返回 `None`）。

**副作用**：修改进程级环境变量——通过 `os.environ.setdefault(key.strip(), value.strip())`（第31行）把 `.env` 文件中的键值对写入 `os.environ`。注意用的是 `setdefault`，即**仅当该环境变量尚未被设置时才写入**，不会覆盖已存在的值。

**前置条件**：
- `path` 指向的文件若存在，必须是 UTF-8 编码的文本文件（第28行 `with open(path, encoding="utf-8") as f:`）。
- 文件内容按行解析，每行格式为 `key=value`（第29-30行：`if line and not line.startswith("#") and "=" in line:` 然后 `key, value = line.split("=", 1)`）。
- 若文件不存在（`os.path.exists(path)` 为假，第26行），函数直接返回，不做任何事，也不报错。

**调用后保证**：
- 文件中所有满足条件的行（非空、不以 `#` 开头、含 `=`）的键值对，其 key 和 value 两侧空白会被去除（`.strip()`），并写入 `os.environ`，但**不会覆盖**已存在的同名环境变量。
- 注释行（以 `#` 开头）和空行被忽略。
- 若文件不存在，则环境变量完全不被修改。

【调用方须知】该函数用 `os.environ.setdefault` 而非直接赋值，所以**它永远不会覆盖进程里已经存在的同名环境变量**——如果你在调用 `load_env()` 之前已经通过别的方式（比如 shell 导出、或代码里直接 `os.environ["KEY"]=...`）设置了某个变量，`.env` 文件里同名的配置会被静默忽略，这可能让调用方误以为 `.env` 里的值生效了，实际用的是旧值。若想强制让 `.env` 覆盖，需要先 `os.environ.pop(key, None)` 再调用。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和保证的描述与代码完全一致，特别是setdefault不覆盖已存在环境变量的行为，以及文件不存在时直接返回的细节，均准确无误。*

### [C] src\deepseek_client.py :: call（第28行，复杂度11）

函数 `call`（src/deepseek_client.py 第28行起）的契约如下，每条均引用代码原文：

**输入**
- 必填参数：`system_prompt: str`、`user_content: str`（第29-30行）。
- 可选参数：`temperature: float = 0.7`、`json_mode: bool = False`、`max_tokens: int = None`、`return_finish_reason: bool = False`（第31-34行）。
- 前置条件：环境变量 `DEEPSEEK_API_KEY` 必须已设置，否则直接 `raise SystemExit("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")`（第52-54行）——注意这是 `SystemExit` 而非 `ApiCallError`，调用方无法捕获后重试。

**输出**
- `json_mode=False`（默认）时返回原始文本字符串（`content`，第86行）。
- `json_mode=True` 时返回已解析的 dict（`json.loads(content)` 的结果，第78行）。
- `return_finish_reason=True` 时返回 `(content_or_dict, finish_reason)` 元组（第86行），其中 `finish_reason == "length"` 表示被 `max_tokens` 截断（docstring 第39-40行）。
- 失败时抛出 `ApiCallError`（网络/超时/限流/响应结构异常/JSON 解析失败），见第63、70、83行。

**副作用**
- 无文件写入、无全局状态修改。docstring 明确承诺："调用失败时不会有任何副作用发生，上层的 snapshot/草稿都不会被写脏"（第22-23行）。
- 唯一外部影响是发起 HTTP 请求到 `https://api.deepseek.com/chat/completions`（第58-62行），并读取环境变量 `DEEPSEEK_API_KEY`。
- 内部重试（json_mode 下最多 `JSON_RETRY_LIMIT=2` 次）对调用方透明，调用方感知不到中间轮次（docstring 第43-47行）。

**调用后保证**
- 成功时要么返回合法 dict（json_mode）或原始文本，要么返回元组；不会返回半解析状态。
- 失败时抛 `ApiCallError`，且保证无副作用。

【调用方须知】最容易忽略的是：`json_mode=True` 时，如果模型连续 `JSON_RETRY_LIMIT`（2）次输出非法 JSON，函数会抛出 `ApiCallError`，但**此时已经向 API 发送了多次请求、消耗了 token 配额**——这不是无副作用的失败，调用方若在重试逻辑里再次调用 `call`，会叠加消耗；另外 `max_tokens` 不传时用 API 默认值，长文本会被**静默截断**（docstring 第37-38行明确警告过），且只有 `return_finish_reason=True` 时才能通过 `finish_reason == "length"` 察觉截断，默认返回模式下截断完全无提示。

*✓ 核实通过——候选答案逐条核对了代码原文，所有引用的行号、函数行为、异常类型、副作用描述均与源码一致，包括 SystemExit 而非 ApiCallError、json_mode 重试机制、finish_reason 返回等细节，结论准确。*

### [D] src\goal_loop.py :: write_with_check（第124行，复杂度26）

write_with_check 的契约如下（依据 src/goal_loop.py 第124-261行）：

**输入**：
- `snapshot: dict`（必填）：含 `rule_based.must_avoid`、`rule_based.must_include`（可缺省，用 `or []` 兜底）、`sub_intents`、`throughline` 等字段的完整快照。
- `mode: str`（必填）：传给 `writer.write_long_script` 的生成模式。
- `previous_excerpt: str = None`：跨幕文风衔接锚点，重试时保持不变（docstring 明确："previous_excerpt 在重试时保持不变，一直是调用方传入的'上一幕正文'，不会被替换成本幕失败的重试草稿"）。
- `world_state: str = None`：传给写手的世界状态。
- `max_attempts: int = MAX_ATTEMPTS`：重试封顶次数。
- `on_chapter`、`on_attempt`：可选回调，`on_attempt(attempt_num, problem_count)` 每轮尝试后调用。

**输出**：返回 dict，两种状态：
- `{"status": "passed", "content", "chapter_reports", "attempts", "snapshot", "sub_intent_changes"}`（第190-195行）
- `{"status": "cap_reached", "content", "chapter_reports", "attempts", "best_attempt", "snapshot", "sub_intent_changes"}`（第258-261行）——封顶时返回违反条数最少的一版（`best = min(attempts, key=lambda a: a["violation_count"])`，第255行），不是最后一版。

**副作用**：
- 不修改调用方传入的原始 `snapshot`：第137行 `current_snapshot = json.loads(json.dumps(snapshot))` 做深拷贝，docstring 明确"修复发生在 snapshot 的内存拷贝上，不会改调用方传进来的原始 snapshot"。
- 不写文件、不写 ledger、不写磁盘——docstring 明确"要不要把修复结果存回 ledger，由调用方（writer.write_and_save_one_with_check）决定"。
- 会修改 `current_snapshot` 内存副本里的 `sub_intents`（第211-220行改 `target["text"]` 和 `target["local_obstacle"]`）和 `must_avoid`/`must_include` 列表（第225-227行、第230-233行加固措辞）。
- 会调用 `on_attempt` 回调（第185行）。

**前置条件**：
- `snapshot` 必须含 `rule_based` 键，且 `rule_based.must_avoid` 必须存在（第139行直接索引 `current_snapshot["rule_based"]["must_avoid"]`，缺了会 KeyError）；`must_include` 可缺省。
- `snapshot` 需含 `sub_intents`（第207行 `diagnose(current_snapshot["sub_intents"], ...)`）和 `throughline`（第213行 `repair_sub_intent(current_snapshot["throughline"], ...)`）。
- 依赖全局 `writer`、`checker`、`checker_include`、`diagnose`、`repair_sub_intent`、`MAX_ATTEMPTS` 等模块级对象/常量。

**后置保证**：
- 最多执行 `max_attempts` 轮（第143行 `for attempt_num in range(1, max_attempts + 1)`）。
- 每轮都生成内容并检查 must_avoid/must_include，`problem_count == 0` 立即返回 `passed`（第188-195行）。
- 未通过时做诊断修复：structural_conflict 且能定位冲突 sub_intent 时改 sub_intent 文本（第207-220行），must_avoid/must_include 措辞被加固（第225-233行）。
- 封顶时保证返回一个 `content`（违反最少的那版），不会返回空/None。

【调用方须知】最容易忽略的是：`previous_excerpt` 在整个重试循环里始终是调用方传入的"上一幕正文"，绝不会被替换成本幕失败的重试草稿——它只用于跨幕文风衔接，不是"上一次尝试"的意思；如果你误以为重试会更新它，就会在下一幕生成时用错锚点，导致文风衔接断裂。另外注意：封顶（cap_reached）时返回的 content 是违反条数最少的一版，不是最后一次尝试的草稿，且此时 must_avoid/must_include 可能并未全部满足，调用方若直接存盘需自行处理这个"未通过"事实（write_and_save_one_with_check 里用 ledger.mark_draft_unchecked 标记）。

*✓ 核实通过——逐条核对了候选答案引用的行号、代码逻辑和docstring，所有具体描述均与源码相符，包括封顶返回最少违反版本和previous_excerpt语义。调用方须知也准确反映了代码行为。*

### [B] src\goal_loop.py :: check_and_report（第228行，复杂度10）

【check_and_report 契约】

**输入**（第228行定义）：
- `content: str` —— 待检查的正文文本
- `must_avoid: list` —— 硬性禁止出现的条目列表
- `must_include: list` —— 必须出现的条目列表
- `sub_intents: list` —— 场次大纲（用于诊断）

**输出**（第247-248行）：
返回一个 dict，含两个键：
- `violations`：list，每个元素是 `{"item", "evidence", "reasoning", "diagnosis_type", "conflicting_sub_intent_id", "diagnosis_explanation"}`
- `missing`：list，每个元素是 `{"item", "reasoning"}`

**行为/副作用**（第230-246行）：
- 只检查、只诊断，**不修改任何内容**——docstring 明确说“只查、只诊断，不自动修复”（第229-230行）。
- 不调用 `repair_sub_intent`、不重试（第231行）。
- **不修改任何外部状态**：不写文件、不更新 ledger、不改 snapshot。它只是读取 `content` 和两个列表，调用 `checker.check`/`checker_include.check` 和 `diagnose`，纯计算后返回结果。
- 副作用仅限调用 `diagnose`（第236行）——这会调用 `writer.deepseek_client.call`（第75-77行），即**发起一次 LLM API 调用**，这是唯一的“外部”副作用（消耗 API 配额、可能产生网络请求）。

**前置条件**：
- `checker` 和 `checker_include` 模块已导入且可用（第10-11行）。
- `must_avoid`/`must_include` 为空时，对应检查直接跳过（第232-233行），不会报错。
- `sub_intents` 需是合法的 JSON 可序列化对象（`diagnose` 里 `json.dumps` 它，第73行）。

**调用后保证**：
- 返回的 dict 结构固定，`violations` 和 `missing` 两个键一定存在（第247-248行）。
- 只包含真正违反/缺失的条目：`violations` 只收集 `violated` 为真的项（第234-235行），`missing` 只收集 `satisfied` 不为真的项（第243-245行）。
- 每条 violation 都带 `diagnosis_type`（`local_slip` 或 `structural_conflict`）和 `diagnosis_explanation`（第238-241行）。

【调用方须知】这个函数名字叫“check_and_report”，看起来只是“检查并报告”，但它内部会调用 `diagnose`，而 `diagnose` 会发起一次真实的 LLM API 调用（`writer.deepseek_client.call`，第75-77行）——也就是说，**每次调用这个“只读检查”函数都会消耗一次大模型 API 配额并产生网络请求**，不是零成本的纯本地检查。如果调用方在循环里频繁调用它（比如对多幕内容逐幕检查），会累积可观的 API 费用和延迟，务必注意这一点。

*✓ 核实通过——候选答案对 check_and_report 的输入、输出、副作用、前置条件和后置条件的描述均与代码原文一致，特别是关于 LLM API 调用的副作用和返回结构，已逐条核实。唯一小偏差是候选答案提到“第228行定义”，实际代码中函数定义在第228行（从文件开头数），但这不是实质错误。整体准确。*

### [B] src\goal_loop.py :: write_and_save_one_with_check（第263行，复杂度8）

【函数契约】write_and_save_one_with_check(project_name, mode, on_chapter=None, on_attempt=None) -> dict

**输入**：
- project_name: str，项目名，用于定位 ledger 快照/草稿（第263行签名，第268行 `ledger.load_snapshot(project_name)`）
- mode: str，生成模式，用于草稿文件名和 generated_from 键（第268-269行）
- on_chapter/on_attempt: 可选回调，透传给 write_with_check（第279-280行）

**输出**：dict，含 `filename`、`content`、`status`、`attempts`、`sub_intent_changes`（第316-319行）。其中 `status` 来自 write_with_check 的 `"passed"` 或 `"cap_reached"`（第281行）。

**副作用（外部状态改动）**：
1. 存草稿：`ledger.save_draft(project_name, mode, result["content"])`（第282行）
2. 若封顶未通过检查，标记草稿为未检查：`ledger.mark_draft_unchecked(project_name, filename)`（第291行，仅当 status=="cap_reached"）
3. 若发生 sub_intent 修复，把修复后的 sub_intents 写回 snapshot：`ledger.save_snapshot(project_name, current)`（第296-298行）
4. 更新 `_meta.generated_from[mode]` 为前驱草稿文件名并保存 snapshot（第300-305行）
5. 提炼世界状态并保存：`ledger.save_world_state(project_name, mode, state_text)`（第308-310行）；若提炼失败（ApiCallError）则静默跳过（第311-312行）

**前置条件**：
- 项目必须已有 snapshot（第268行直接 load，未检查存在性）
- 若 snapshot 的 `_meta.predecessor` 存在，则需能通过 `ledger.latest_draft_filename` 和 `ledger.load_draft` 读到前驱草稿（第269-274行）；若 predecessor 为空则跳过（第275行）

**调用后保证**：
- 无论 status 是 passed 还是 cap_reached，都会无条件保存草稿（第282行，注释明确"生成一定要给点东西，不能让批量流程卡死"）
- 返回的 content 在 cap_reached 时是违反条数最少的一版（write_with_check 第229行 `best = min(attempts, ...)`），不是最后一版
- 修复只发生在内存拷贝上，不修改调用方传入的原始 snapshot（write_with_check 第191行 `json.loads(json.dumps(snapshot))`）

【调用方须知】当 status 为 "cap_reached" 时，函数虽然照常返回并保存了草稿，但该草稿并未通过 must_avoid/must_include 检查，且会通过 `ledger.mark_draft_unchecked` 在磁盘上留下"未检查"标记——调用方不能因为拿到了非空 content 就认为生成合格，必须检查返回的 status 字段，否则会把不合格的草稿当作正常结果使用。

*✓ 核实通过——逐条核对了候选答案中的每个具体说法（签名、行号、函数调用、行为描述），均与src/goal_loop.py实际代码一致，包括副作用、前置条件和调用后保证，且【调用方须知】准确指出了cap_reached时草稿未通过检查且留下未检查标记这一关键点。*

### [B] src\ledger.py :: _migrate_chain_to_series（第153行，复杂度9）

函数 `_migrate_chain_to_series(any_member_name: str) -> str`（src/ledger.py 第153行起）的契约如下：

**输入**：一个字符串 `any_member_name`，表示链上任意一幕的项目名（第153行）。

**输出**：返回该链的系列根名（`return root`，第186行），即 `series_root(any_member_name)` 的结果。

**副作用（外部状态修改）**：
1. 若根节点尚未嵌套（`root_already_nested` 为 False），会移动磁盘目录：先把根节点从 `ledger/<root>/` 移到临时目录 `ledger/.<root>.migrating`，再创建 `ledger/<root>/`，最后把临时目录移入 `ledger/<root>/<root>/`（第166-172行，`shutil.move` 和 `os.makedirs`）。
2. 遍历所有项目，把链上其余仍扁平存储的成员（`os.path.dirname(current_path) == LEDGER_ROOT`）搬进 `ledger/<root>/<name>/`（第174-183行，`shutil.move`）。
3. 若根节点磁盘路径不存在（`root_current_path is None`），抛出 `FileNotFoundError(f"project '{root}' not found")`（第168行）。

**前置条件**：
- 调用前 `any_member_name` 必须已存在于磁盘（否则 `series_root` 可能返回它自己，但 `_resolve_existing_path` 找不到会抛 `FileNotFoundError`）。
- 需要 `LEDGER_ROOT` 目录存在且可写。

**调用后保证**：
- 整条 predecessor 链的所有成员都位于同一个系列文件夹 `ledger/<root>/` 下（嵌套结构），且系列文件夹名等于链根的名字。
- 若链已在系列中，函数是空操作（docstring 第155行），不移动任何文件，仅返回 `root`。

【调用方须知】最容易被忽略的是：该函数会**实际移动磁盘上的目录**（`shutil.move`），且移动过程使用临时目录中转——如果调用方在移动中途（比如 `shutil.move` 抛异常）中断，磁盘上可能残留 `ledger/.<root>.migrating` 临时目录，导致项目暂时处于不一致状态；另外，若链根节点磁盘路径不存在，会直接抛 `FileNotFoundError`，调用方需先确保项目已创建（例如通过 `project_dir`），否则不能安全调用。

*✓ 核实通过——候选答案对函数契约的描述与代码逐条吻合，包括输入输出、副作用（磁盘目录移动）、前置条件（FileNotFoundError）和空操作行为，且调用方须知准确指出了临时目录残留和FileNotFoundError风险。*

### [B] src\ledger.py :: list_projects（第105行，复杂度7）

函数 `list_projects()`（src/ledger.py 第105行附近）的契约如下：

**输入**：无参数。

**输出**：返回一个 `list`，元素是字符串（项目名）。根据 docstring（第106-107行）：“返回所有‘幕’的名字（扁平的独立项目 + 每个系列文件夹里的每一幕），对外依然是一份单层的名字列表，嵌套只是磁盘层面的事。”

**行为/副作用**：
- 纯查询，不修改任何文件、目录或全局状态。它只调用 `os.path.isdir`、`os.listdir`、`os.path.isfile` 等只读操作（第110-121行）。
- 如果 `LEDGER_ROOT` 目录不存在，直接返回空列表 `[]`（第110-111行：`if not os.path.isdir(LEDGER_ROOT): return []`）。

**前置条件**：无。即使 `LEDGER_ROOT` 不存在也能安全调用（返回空列表）。

**返回值的具体规则**（依据第112-121行）：
1. 遍历 `LEDGER_ROOT` 下的条目，按 `sorted` 排序（第112行）。
2. 只考虑目录（第113-114行：`if not os.path.isdir(entry_path): continue`）。
3. 如果该目录下存在 `snapshot.json` 文件（即扁平独立项目），把该目录名加入结果（第115-116行）。
4. 否则（该目录是系列文件夹），遍历其子目录（同样 `sorted` 排序，第118行），对每个子目录，如果其下存在 `snapshot.json`，把**子目录名**（不是“系列/幕”复合路径）加入结果（第119-121行）。

**保证**：返回的列表是单层的名字列表，每个名字对应一个实际存在 `snapshot.json` 的项目；列表按字母序排序（因为 `sorted`）。

【调用方须知】最容易被忽略的是：**返回的名字可能重名**——一个扁平项目叫 `foo`，同时某个系列文件夹下也可能有一个子目录也叫 `foo`（因为系列展开时只取子目录名，不包含系列前缀），两者都会被加入列表，导致列表中出现两个相同的字符串。调用方若用这个名字去 `load_snapshot`/`project_dir`，`_resolve_existing_path` 会优先命中扁平路径（第20-24行），可能取到错误的项目。因此调用方不能假设返回的名字唯一，也不能仅凭名字区分扁平项目与系列中的幕。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件、返回规则和重名风险的描述均与代码逐行吻合，且【调用方须知】指出的重名问题（扁平项目与系列子目录同名时列表出现重复字符串）在代码逻辑中确实存在，因为系列展开只取子目录名不加前缀。*

### [B] src\ledger.py :: save_draft（第292行，复杂度7）

函数 save_draft(project_name, mode, content) 的契约（依据 src/ledger.py 第292-306行）：

【输入】
- project_name: str，项目标识符（某一幕的名字，单一字符串，见第20-22行注释）。
- mode: str，草稿模式（如 "novel"）。
- content: str，要写入的草稿正文。

【输出】
- 返回 str：写入的文件名（不含目录），形如 "{mode}_v{N}.md"，N 是版本号。

【副作用（外部状态/文件）】
- 会创建草稿目录：调用 _drafts_dir(project_name)，该函数用 os.makedirs(path, exist_ok=True) 确保目录存在（第286-290行）。
- 会写入一个新文件：open(os.path.join(d, filename), "w", encoding="utf-8") 覆盖式写入 content（第304-305行）。
- 版本号递增：扫描目录下所有以 "{mode}_v" 开头、".md" 结尾的文件，取最大版本号+1；若无则从1开始（第294-303行）。

【前置条件】
- project_name 对应的项目目录必须可写（_drafts_dir 会自动创建，但若磁盘只读会抛异常）。
- 无其他显式前置条件；不检查 project_name 是否已存在快照。

【调用后保证】
- 返回的文件名是唯一的（版本号递增，不会覆盖已有文件）。
- 文件内容与传入的 content 完全一致（UTF-8 编码）。
- 不修改任何已有文件，只新增。

【调用方须知】版本号计算依赖目录里所有匹配 "{mode}_v*.md" 的文件名，且只认纯数字版本号（int 解析失败的文件会被跳过，见第298-301行 try/except ValueError: continue）。如果目录里混入一个像 "novel_vabc.md" 这样的文件，它会被忽略，不会影响版本号计算；但如果混入 "novel_v2.md" 这类合法格式，会被计入，导致下次生成的版本号可能跳过某些数字（比如已有 v1、v3，下次会生成 v4，而不是 v2）。调用方若期望版本号连续，需自行保证目录里没有手工放置的、格式合法的草稿文件。

*✓ 核实通过——候选答案逐条对应了 save_draft 的实际实现，包括版本号计算逻辑和异常处理，且【调用方须知】中关于版本号计算依赖目录中合法格式文件、跳过非法格式文件的描述与代码完全吻合。*

### [B] src\ledger.py :: delete_draft（第357行，复杂度6）

函数 `delete_draft(project_name: str, filename: str) -> None`（src/ledger.py 第357行）的契约如下：

**输入**：
- `project_name`：项目（幕）的名字，用于定位草稿目录（`_drafts_dir(project_name)`，第357行调用）。
- `filename`：要删除的草稿文件名（如 `novel_v3.md`）。

**输出**：无返回值（`-> None`）。

**副作用（外部状态/文件修改）**：
1. 删除草稿正文文件：`path = os.path.join(_drafts_dir(project_name), filename)`，若文件存在则 `os.remove(path)`（第360-361行）。
2. 条件性删除运行事实清单：当 `was_latest` 为真时，删除同目录下的 `<mode>_state.md` 文件（第363-365行）。

**前置条件**：
- 无显式前置条件。函数不检查 `filename` 是否存在于磁盘（`os.path.exists(path)` 判断后才删，第360行）；`filename` 中若不含 `"_v"`，则 `mode` 为 `None`，`was_latest` 为 `False`，此时只尝试删正文文件（第358行）。
- 依赖 `_drafts_dir` 会创建目录（`os.makedirs(path, exist_ok=True)`，第339行），因此即使项目目录不存在也会被创建。

**调用后保证**：
- 若 `filename` 存在，正文文件被删除；若不存在，无操作（`os.path.exists` 守卫）。
- 若删除的是该 mode 的最新版本（`was_latest` 为真，即 `latest_draft_filename(project_name, mode) == filename`，第358行），则同时删除对应的 `<mode>_state.md` 文件（若存在）；否则 state 文件保留。
- 不修改 snapshot.json、log.jsonl 或其他文件。

**【调用方须知】**：当删除的是某 mode 的最新版本草稿时，函数会连带删除同目录下的 `<mode>_state.md` 运行事实清单文件——这个副作用从函数名 `delete_draft` 看不出来，且它只发生在删除最新版本时；如果调用方在删除后仍依赖该 state 文件（例如后续生成需要读取事实清单），会因文件被删而丢失数据，务必在删除前确认是否真的需要保留该 state 文件。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和调用后保证的描述均与代码原文逐条吻合，特别是关于删除最新版本时连带删除 state 文件的副作用，在代码和 docstring 中都有明确依据。*

### [B] src\server.py :: continue_from（第44行，复杂度9）

continue_from 是 src/server.py 第44行起的 Flask 路由处理函数（POST /api/projects/<name>/continue_from），不是普通函数而是 HTTP 端点。它的契约如下：

【输入】
- 路径参数 name：要创建的新项目名（URL 里 <name>）。
- JSON 请求体（request.get_json(force=True) or {}），字段：
  - predecessor（必填，字符串，会 strip 空白）：被承接的旧项目名。
  - force（可选，bool(data.get("force"))）：是否跳过分支确认。

【输出】
- 成功：返回 jsonify(snapshot)，即 ledger.create_continuation(name, predecessor) 的返回值（快照对象）。
- 失败/需确认时返回带状态码的 JSON：
  - 400 {"error": "missing predecessor"}（predecessor 为空）
  - 404 {"error": f"project '{predecessor}' not found"}（predecessor 不在 ledger.list_projects()）
  - 409 {"error": f"project '{name}' already exists"}（name 已存在）
  - 400 {"error": str(e)}（ledger.ContinuationError 异常）
  - 200 {"needs_confirmation": True, "existing_successors": ..., "leaf_suggestions": ...}（predecessor 已有后继且未带 force）

【副作用】
- 成功时调用 ledger.create_continuation(name, predecessor)，会创建新项目（写入磁盘/ledger 状态），这是主要副作用。
- 失败/需确认路径不调用 create_continuation，无副作用。

【前置条件】
- 请求必须是 POST 且带 JSON body（force=True 强制解析）。
- predecessor 必须非空、必须已存在于 ledger.list_projects()。
- name 必须不存在于 ledger.list_projects()。
- 若 predecessor 已有后继（ledger.find_successors(predecessor) 非空），必须带 force=true 才能继续，否则返回 needs_confirmation。

【调用后保证】
- 成功时返回的 snapshot 是新项目的快照；新项目已创建。
- 若返回 needs_confirmation，则未创建任何项目，调用方需展示 existing_successors 和 leaf_suggestions 让用户确认后带 force 重调。

【调用方须知】当 predecessor 已有后继（即它不是链上最新一幕）时，不带 force 的调用不会创建项目，而是返回 needs_confirmation 提示分支；只有带 force=true 才会真正创建分支。调用方最容易忽略的是：这个确认不是可选的——只要 predecessor 有后继，就必须先收到 needs_confirmation 再带 force 重调，否则永远创建不了新项目。

*✓ 核实通过——逐条对照代码确认了输入处理、错误分支、副作用和前置条件，候选答案准确反映了函数契约。*

### [B] src\server.py :: write_draft（第192行，复杂度9）

write_draft 是 Flask 路由处理函数（@app.route("/api/projects/<name>/write", methods=["POST"])），接收 URL 路径参数 name（项目名）和 JSON 请求体（mode、force），返回 JSON 响应。

**输入**：
- URL 路径参数 `name`（项目名）
- JSON 请求体：`mode`（必须为 "novel" 或 "screenplay"）、`force`（可选布尔值）

**输出**（成功时）：
- `filename`、`content`（生成并保存的正文）、`continued_from_draft`（布尔值，表示是否承接了上一幕的正文）、`chapters`（章节报告列表）

**副作用**：
- 调用 `writer.write_and_save_one(name, mode, on_chapter=chapter_reports.append)`，该函数会：
  - 调用 `ledger.save_draft(project_name, mode, content)` 写入草稿文件
  - 更新 snapshot 的 `_meta.generated_from` 并调用 `ledger.save_snapshot` 保存
  - 调用 `ledger.save_world_state` 保存运行事实清单

**前置条件**：
- 项目必须存在（`name not in ledger.list_projects()` 返回 404）
- 项目状态必须是 `confirmed`（`snapshot["_meta"]["project_state"] != "confirmed"` 返回 400）
- `mode` 必须是 "novel" 或 "screenplay"（否则返回 400）
- 若已有正文且未带 `force=true`，则返回 `needs_confirmation: true` 和 `dependents`，不实际生成

**保证**：
- 若生成失败（`writer.deepseek_client.ApiCallError`），返回 502 且不写入任何文件（错误信息明确说"没有写入任何文件"）
- 成功时返回的 `chapters` 列表长度等于分段数（未分章时为 1）

【调用方须知】最容易被忽略的是：**当项目已有正文且未带 `force=true` 时，函数不会生成任何内容，而是返回 `needs_confirmation: true` 和 `dependents` 列表——调用方必须据此提示用户确认，然后带 `force=true` 再次调用才能真正生成。** 这是与删除项目相同的两步确认流程，若调用方直接忽略 `needs_confirmation` 响应而继续期待 `filename`/`content`，会得到缺失这些字段的响应。

*✓ 核实通过——候选答案对函数行为、输入输出、副作用和前置条件的描述与代码逐条吻合，且调用方须知准确指出了两步确认流程。*

### [B] src\server.py :: load_env（第18行，复杂度6）

函数 `load_env(path=".env")` 定义在 src/server.py 第18-25行，其契约如下：

**输入**：一个可选参数 `path`，默认值为字符串 `".env"`（第18行 `def load_env(path=".env"):`）。

**输出**：无返回值（函数体没有 `return` 语句，隐式返回 `None`）。

**副作用**：修改全局环境变量——通过 `os.environ.setdefault(key.strip(), value.strip())`（第24行）把 `.env` 文件中的键值对写入进程的环境变量。注意用的是 `setdefault`，即**仅当该环境变量尚未设置时才写入**，不会覆盖已存在的值。

**前置条件**：
- 若 `path` 指定的文件存在，则必须是可读的文本文件（用 `open(path, encoding="utf-8")` 打开，第20行）。
- 文件内容按行解析，每行格式需为 `key=value`（第22行 `if line and not line.startswith("#") and "=" in line`），且 `=` 两侧会被 `strip()` 去除空白（第23行 `key, value = line.split("=", 1)`）。
- 空行、以 `#` 开头的注释行、不含 `=` 的行都会被跳过（第22行条件）。

**调用后保证**：
- 若文件不存在，函数不做任何事（第19行 `if os.path.exists(path):` 为假则直接返回）。
- 若文件存在，所有符合格式的 `key=value` 行中，那些尚未在环境中设置的键会被设置为其对应的值；已存在的键不会被修改。

**调用时机**：在模块顶层第27行 `load_env()` 被调用一次，使用默认路径 `.env`，在创建 Flask 应用（第29行）之前执行，确保后续代码能读取到环境变量。

【调用方须知】最该警惕的是：`load_env` 使用 `os.environ.setdefault`，意味着它**永远不会覆盖已存在的环境变量**——如果调用方在调用 `load_env()` 之前已经通过其他方式（如 shell 导出、`os.environ` 直接赋值）设置了同名变量，`.env` 文件里的值会被静默忽略，这可能导致配置不生效且无任何报错提示。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和调用后保证的描述均与代码原文一致，且调用方须知准确指出了setdefault不覆盖已有环境变量的行为。*

### [C] src\writer.py :: write_long_script（第174行，复杂度13）

函数 `write_long_script`（src/writer.py 第174行起）的契约如下：

**输入**（形参，见第174-180行）：
- `snapshot: dict`：必填，一份已收尾的创作设定快照，其中 `sub_intents` 字段是场次大纲列表（第191行 `sub_intents = snapshot.get("sub_intents") or []`）。
- `mode: str`：必填，"novel" 或 "screenplay"，决定输出格式（透传给 `write_script`）。
- `chunk_size: int = CHAPTER_CHUNK_SIZE`：可选，默认5，每段包含的 sub_intents 条数。
- `previous_excerpt: str = None`：可选，上一幕/上一段正文，只用于延续文风。
- `world_state: str = None`：可选，更早事实清单，作为硬性事实约束。
- `on_chapter=None`：可选回调，每写完一段调用一次。

**输出**（第188行 `返回 (full_content, chapter_reports)`）：
- `full_content`：纯文本正文。若 `len(chunks) > 1`，各段用 `"\n\n".join(f"第{i}章\n\n{c}" ...)` 拼接，即**每段前自动加"第N章"标题**（第238-241行）；若只有一段则直接返回该段内容，**不加章节标题**（第242-243行）。
- `chapter_reports`：列表，每段一个 dict，含 `index/total/sub_intent_ids/char_count/finish_reason`（第218-226行）。

**副作用**：
- 函数本身**不写文件、不改全局数据**，纯计算返回。但它会**多次调用外部 API**（`write_script` → `deepseek_client.call`，第210行；以及每段后调 `extract_world_state` → 又一次 API 调用，第231行），每次调用都消耗 token 并产生网络副作用。
- 若 `on_chapter` 回调被传入，会在每段生成后同步调用它（第227-228行），回调内部可做任何事（如写文件、更新 UI），这是调用方注入的副作用。

**前置条件**：
- `mode` 必须是 `MODE_INSTRUCTIONS` 的键（"novel"/"screenplay"），否则 `write_script` 会抛 `ValueError`（第134行 `if mode not in MODE_INSTRUCTIONS: raise ValueError`）。
- `snapshot` 应含 `sub_intents` 字段；若缺失或为空，`chunks` 会退化为 `[[]]`（第191-192行），此时循环仍执行一次，`write_script` 收到空 sub_intents 列表，最终 `full_content` 为空字符串（第243行）。
- 若 `world_state` 为 None，`rolling_world_states` 初始为空列表，`combined_world_state` 为 None（第196、205行），不影响调用。

**调用后保证**：
- 返回的 `full_content` 一定非 None（至少是空字符串），`chapter_reports` 长度等于实际分段数（至少1）。
- 每段的 `finish_reason` 会如实反映该段是否被截断（"length" 表示被 max_tokens 截断，第223行注释），但**函数不会因截断而重试或报错**，截断内容照样拼进 `full_content`。
- 每段生成后都会尝试提炼 world_state 并追加到 `rolling_world_states`（第230-235行），但若 `extract_world_state` 抛 `deepseek_client.ApiCallError` 则静默跳过（第233-234行），不影响已生成内容。

【调用方须知】当 `sub_intents` 数量超过 `chunk_size`（默认5）时，函数会在每段正文前**自动插入"第N章"标题**（第238-241行），且这个标题是函数自己加的、不是模型生成的——如果你的下游流程（如存档、字数统计、后续续写）不期望正文里出现这些章节标题，或者你希望标题格式不同，必须在调用前自行处理；另外每段都可能被 max_tokens 截断（`finish_reason == "length"`），函数不会重试，截断的段落会原样拼进最终结果，调用方应检查 `chapter_reports` 里的 `finish_reason` 而不是假设内容完整。

*✓ 核实通过——逐条核对了候选答案引用的代码行和逻辑，所有关键行为（输入参数、输出结构、副作用、前置条件、章节标题插入、截断处理）均与源码一致。*

### [B] src\writer.py :: write_script（第114行，复杂度6）

【调用方须知】调用方最容易忽略的是：write_script 的返回值在 return_finish_reason=False（默认）时是纯字符串，但 return_finish_reason=True 时返回的是 (content, finish_reason) 元组——同一个函数两种返回类型，且当 finish_reason == "length" 时说明正文被 WRITER_MAX_TOKENS=8192 截断了，不是正常写完的，调用方必须检查这个标志，否则可能把截断的半截正文当成完整成品使用。

*✓ 核实通过——候选答案准确描述了 write_script 的返回类型切换和截断风险，与代码原文完全一致。*

### [B] src\writer.py :: write_and_save_one（第242行，复杂度6）

函数 `write_and_save_one(project_name, mode, on_chapter=None)`（src/writer.py 第242行起）的契约如下，每条均引用代码原文：

**输入**
- `project_name: str`：项目名，用于加载快照和存档。
- `mode: str`：输出模式，必须是 `"novel"` 或 `"screenplay"`（`write_script` 里 `if mode not in MODE_INSTRUCTIONS: raise ValueError`）。
- `on_chapter=None`：可选回调，每写完一段调用一次（透传给 `write_long_script`）。

**输出**
- 返回 `(filename, content)` 元组（`return filename, content`）。`filename` 是存档文件名，`content` 是生成的正文纯文本。

**副作用（外部状态/文件/全局数据）**
1. 存档：调用 `ledger.save_draft(project_name, mode, content)` 写入正文文件。
2. 更新快照元数据：`snapshot["_meta"]["generated_from"][mode] = predecessor_draft_filename`，并调用 `ledger.save_snapshot(project_name, snapshot)` 持久化——记录这一幕参考的是上一幕哪个版本。
3. 提炼并保存运行事实清单：调用 `extract_world_state(content)` 后 `ledger.save_world_state(project_name, mode, state_text)`。
4. 副作用会修改项目快照文件和草稿文件，且 `extract_world_state` 会调用外部 LLM API（`deepseek_client.call`）。

**前置条件**
- 这一幕的 snapshot 必须已存在且 `_meta` 含 `predecessor` 字段（`snapshot["_meta"].get("predecessor")`）。
- 调用方负责确认这一幕状态是 `confirmed`——函数 docstring 明确说“这里不做校验”。
- 若存在 `predecessor`，需要能通过 `ledger.latest_draft_filename` 找到上一幕草稿，且 `ledger.load_draft` 能读取；否则 `previous_excerpt` 为 `None`。
- `mode` 必须合法，否则 `write_script` 抛 `ValueError`。

**调用后保证**
- 正文已写入磁盘（`save_draft`），快照的 `generated_from` 已更新并保存，事实清单已保存（除非 `extract_world_state` 抛 `ApiCallError`，此时静默跳过，不影响生成结果）。
- 返回的 `content` 是完整正文（可能内部多段拼接，对调用方透明）。

【调用方须知】最容易忽略的是：这个函数会**静默地修改并保存项目快照的 `_meta.generated_from`**——它先 `load_snapshot` 读一次，生成完后又**重新读一次快照**再写入 `generated_from`，目的是“避免覆盖这期间的其他改动”，但如果你在调用前后自己持有旧的 snapshot 引用并保存，会覆盖掉它写入的这条记录；同时它**不校验这一幕是否 confirmed**，也不提示“重新生成会影响后续幕次”，这两件事 docstring 明确推给调用方（chat.py/server.py）负责——调用前务必自己确认状态，否则会污染后续幕次的事实链。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件、调用后保证的描述均与代码原文逐条吻合，且【调用方须知】指出的静默修改 generated_from 和 docstring 推卸校验责任均有代码依据。*

### [B] tests\conftest.py :: __call__（第38行，复杂度10）

「__call__」是 FakeDeepSeek 类的实例方法（tests/conftest.py 第38-61行），使 FakeDeepSeek 实例可被当作函数调用，用于替换 deepseek_client.call。

【输入】
- 位置参数 system_prompt（str）、user_content（任意，本实现未使用）；
- 关键字参数 temperature=0.7、json_mode=False、max_tokens=None、return_finish_reason=False（第38-39行）。

【输出】
按 system_prompt 中是否包含特定特征字符串路由到不同假响应队列（第41-60行）：
- 含"剧本写手 Agent"：返回 writer_responses 队列弹出的元素；若 return_finish_reason=True 则返回 (content, finish_reason) 元组，否则只返回 content（第41-44行）。
- 含"运行事实清单"：返回 world_state_response（字符串"占位事实清单"）（第45-47行）。
- 含"must_avoid_list"或"有没有违反"：返回 {"results": 从 avoid_responses 弹出的元素}（第48-51行）。
- 含"must_include_list"或"有没有满足"：返回 {"results": 从 include_responses 弹出的元素}（第52-55行）。
- 含"推理步数有多短"：返回从 diagnose_responses 弹出的元素（第56-58行）。
- 含"保住这条大纲原本要完成的戏剧功能"：返回从 repair_responses 弹出的元素（第59-61行）。
- 若都不匹配，抛出 AssertionError（第62-63行）。

【副作用】
每次调用都会把对应类别的标识字符串（如"writer"、"world_state"、"checker_avoid"等）append 到 self.calls 列表（第42、46、49、53、57、60行），供测试断言"确实被调用了"。

【前置条件】
- 调用前需通过 __init__ 初始化各响应队列（writer_responses、avoid_responses、include_responses、diagnose_responses、repair_responses、world_state_response）和 self.calls（第28-34行）。
- system_prompt 必须包含上述六个特征字符串之一，否则抛 AssertionError。
- 队列弹出逻辑：_pop 方法（第36-37行）——若队列长度>1则 pop(0)，否则返回 queue[0]（即弹完最后一个后重复返回最后一个，不报错）。

【调用后保证】
- 返回的假响应内容与真实 DeepSeek 无关，仅用于测试纯逻辑。
- self.calls 中记录了本次调用的类别，可被测试读取。

【调用方须知】
最容易被忽略的是：_pop 在队列只剩一个元素时不会弹出而是重复返回该元素（第37行 `return queue[0]`），因此如果测试期望某类响应被调用多次且每次返回不同内容，必须预先在对应队列里放入足够多的元素；否则后续调用会静默复用最后一个响应，不会报错，可能导致测试断言"假通过"。

*✓ 核实通过——逐条对照代码确认了候选答案对输入、输出、副作用、前置条件和 _pop 行为的描述全部属实，无虚构或遗漏。*

### [B] tests\test_goal_loop.py :: test_structural_conflict_gets_repaired_and_retry_passes（第20行，复杂度8）

函数 test_structural_conflict_gets_repaired_and_retry_passes（tests/test_goal_loop.py 第20行）是一个测试函数，它验证 goal_loop.write_with_check 在遇到 structural_conflict 型违反时的行为。它的契约如下：

**输入**：
- 通过 fixture `fake_deepseek` 注入模拟的 writer/checker/diagnose/repair 响应（见第21-35行）。
- 构造一个 snapshot：`make_snapshot(must_avoid=["反派死亡"], sub_intents=[...])`，其中 sub_intent id=1 文本为"反派当场死亡"（第21-25行）。
- 调用 `goal_loop.write_with_check(snap, "novel")`（第37行）。

**输出**：
- 返回 dict，断言 `result["status"] == "passed"`（第39行）。
- `result["attempts"]` 长度为 2（第40行），表示第一次生成违反后修复重试，第二次通过。
- `result["sub_intent_changes"]` 长度为 1（第41行），且该 change 的 `sub_intent_id` 为 1、`before` 为"反派当场死亡"、`after` 为"反派认罪伏法"（第42-44行）。

**副作用**：
- 关键副作用：**不修改调用方传入的原始 snapshot**。第46行断言 `snap["sub_intents"][0]["text"] == "反派当场死亡"`，即修复只发生在返回的 snapshot 副本上，原始 snapshot 保持不变。

**前置条件**：
- 需要 `fake_deepseek` fixture 提供：两次 writer 响应（第一版和修复后正文）、第一次 avoid 检查报告一条违反（"反派死亡" violated=True）、第二次 avoid 检查为空、一次 diagnose 响应（type=structural_conflict, conflicting_sub_intent_id=1）、一次 repair 响应（revised_text="反派认罪伏法"）。

**调用后保证**：
- 当违反是 structural_conflict 时，write_with_check 会调用 repair_sub_intent 修改对应 sub_intent 的文本，然后重试，第二次通过后返回 passed。

【调用方须知】这个测试最容易被忽略的一点是：它验证了 write_with_check 的修复**不会修改调用方传入的原始 snapshot**（第46行断言原始 snapshot 的 sub_intent 文本仍是"反派当场死亡"），修复只发生在内部拷贝上——如果调用方想持久化修复结果，必须自己把返回的 `result["snapshot"]` 存回 ledger（这正是 write_and_save_one_with_check 做的事），否则修复会丢失。

*△ 未核实完——超过核实步数上限，未能完成核实*

### [B] tests\test_goal_loop.py :: test_write_missing_acts_in_series_skips_existing_and_stops_at_unconfirmed（第194行，复杂度8）

函数 `test_write_missing_acts_in_series_skips_existing_and_stops_at_unconfirmed`（tests/test_goal_loop.py 第194-218行）是一个测试函数，它验证 `goal_loop.write_missing_acts_in_series` 的契约。

**输入（前置条件）**：
- 依赖两个 fixture：`fake_deepseek`（模拟模型响应）和 `isolated_ledger`（隔离的 ledger 存储）。
- 测试先构造一个系列链：`act1`（已有 snapshot 和正文）、`act2`（有 snapshot 且 `_meta.project_state == "confirmed"`，但无正文）、`act3`（有 snapshot，保持默认 `project_state`，即非 confirmed）。
- 设置 `fake_deepseek.writer_responses = [("act2生成的正文", "stop")]` 和 `fake_deepseek.avoid_responses = [[]]`（无违反）。

**调用**：`results = goal_loop.write_missing_acts_in_series("act3", "novel")`

**输出（返回值）**：
- 返回一个列表，包含系列链中每个幕次的结果字典，顺序为 `["act1", "act2", "act3"]`（断言 `[r["name"] for r in results] == ["act1", "act2", "act3"]`）。
- 每个结果字典有 `name` 和 `status` 字段：
  - `act1` 的 `status == "skipped_exists"`（因为已有正文，跳过）。
  - `act2` 的 `status == "written"` 且 `check_status == "passed"`（因为无正文且 confirmed，被生成并通过检查）。
  - `act3` 的 `status == "skipped_not_confirmed"`（因为未 confirmed，停止处理）。

**副作用（外部状态修改）**：
- 通过 `isolated_ledger` 持久化：`act2` 的正文被写入，断言 `isolated_ledger.latest_draft("act2", "novel") == "act2生成的正文"`。
- `act3` 的正文**没有被写入**，断言 `isolated_ledger.latest_draft("act3", "novel") is None`。
- 测试没有直接断言 snapshot 是否被修改，但 `write_missing_acts_in_series` 内部调用 `write_and_save_one_with_check`，后者会保存 snapshot（见 src/goal_loop.py 中 `write_and_save_one_with_check` 的实现）。

**调用后保证**：
- 系列链中所有幕次都会被遍历并返回结果（即使中途停止，已处理的幕次仍会出现在结果中）。
- 已有正文的幕次被跳过，不重新生成。
- 未 confirmed 的幕次及其后续幕次不会被生成，且处理在此处停止（`break`）。
- 只有 confirmed 且无正文的幕次会被生成，且生成结果通过检查（`check_status == "passed"`）。

**【调用方须知】**：`write_missing_acts_in_series` 遇到未 confirmed 的幕次时会**立即停止**（`break`），不会继续处理该幕次之后的任何幕次——即使后续幕次是 confirmed 的也不会被生成，所以调用方必须确保传入的 `leaf_project_name` 是系列中最后一个需要生成的幕次，否则会漏掉后面的幕次。

*✓ 核实通过——逐条核对了测试代码和实现代码，候选答案引用的行为、断言和副作用均真实存在，没有夸大或虚构。*

### [B] tests\test_ledger.py :: test_save_draft_versions_increment_and_dont_overwrite（第18行，复杂度7）

【函数契约】

**函数**：`test_save_draft_versions_increment_and_dont_overwrite(isolated_ledger)`（tests/test_ledger.py 第18行）

**输入**：
- 参数 `isolated_ledger`：一个 ledger 实例（fixture，提供 `save_snapshot`/`save_draft`/`load_draft`/`latest_draft_filename`/`latest_draft` 等方法）。
- 测试内部调用 `make_snapshot()` 生成快照数据（来自 conftest）。

**输出**：
- 无返回值（返回 `None`）。
- 通过断言验证行为，断言失败则测试失败。

**副作用（外部状态/文件）**：
- 在 `isolated_ledger` 指向的持久化存储中创建项目 `proj_b` 的快照（`save_snapshot`）。
- 写入两个草稿文件：`novel_v1.md`（内容“第一版内容”）和 `novel_v2.md`（内容“第二版内容”），文件位于项目的 drafts 目录（见 src/ledger.py 中 `save_draft` 的实现，第292行起）。
- 这些文件是磁盘上的真实文件，测试结束后由 fixture 清理（`isolated_ledger` 是隔离的）。

**前置条件**：
- 需要 `isolated_ledger` fixture 已初始化，且 `make_snapshot()` 可用。
- 项目 `proj_b` 在调用 `save_draft` 前必须先存在（测试先调 `save_snapshot` 创建它）。
- 项目 `proj_b` 的 drafts 目录初始为空（或至少没有 `novel_v*` 文件），否则版本号会从已有最大版本继续递增，导致断言失败。

**调用后保证**：
- 两次 `save_draft` 返回的文件名分别为 `novel_v1.md` 和 `novel_v2.md`，版本号从1开始递增，且不覆盖已有文件（见 src/ledger.py `save_draft`：`next_version = (max(versions) + 1) if versions else 1`）。
- 两个版本的内容都能通过 `load_draft` 正确读回（`load_draft` 直接读文件内容，src/ledger.py 第322行）。
- `latest_draft_filename` 返回版本号最大的文件名 `novel_v2.md`（src/ledger.py `latest_draft_filename` 用 `max(candidates, key=version_of)`）。
- `latest_draft` 返回最新版本的内容“第二版内容”（src/ledger.py `latest_draft` 调用 `load_draft`）。

【调用方须知】版本号递增依赖 drafts 目录里已有的 `<mode>_v<N>.md` 文件：如果目录里已有 `novel_v5.md`，下一次 `save_draft` 会生成 `novel_v6.md` 而不是 `novel_v1.md`——所以测试假设 `proj_b` 的 drafts 目录初始为空；若在已有版本的项目上重复运行此测试，断言 `f1 == "novel_v1.md"` 会失败。调用方若想保证从 v1 开始，必须先清空该项目的 drafts 目录。

*✓ 核实通过——逐条核对了测试函数体和 ledger.py 中 save_draft/load_draft/latest_draft_filename 的实现，候选答案的所有具体说法（文件名、版本号计算、行为）都与代码原文吻合。*

### [B] tests\test_writer_chunking.py :: test_long_snapshot_splits_into_multiple_chunks_with_headers（第26行，复杂度6）

该测试函数验证 `writer.write_long_script` 在 sub_intents 数量超过 chunk_size 时的分段行为。

**输入**（依据测试第26-29行）：
- `snap = make_snapshot(sub_intents=_sub_intents(5))`：一个含 5 条 sub_intents 的 snapshot（每条 id 为 1..5，见 `_sub_intents` 第9-14行）。
- `fake_deepseek.writer_responses = [("这一段正文", "stop")]`：假模型只返回一段正文，finish_reason 为 "stop"。
- 调用 `writer.write_long_script(snap, "novel", chunk_size=2)`：mode 为 "novel"，chunk_size=2。

**输出**（依据第31-36行断言）：
- 返回 `(content, reports)` 元组。
- `len(reports) == 3`：5 条 sub_intents 按每段 2 条拆成 3 段（2/2/1）。
- `reports[0]["sub_intent_ids"] == [1, 2]`、`reports[1]["sub_intent_ids"] == [3, 4]`、`reports[2]["sub_intent_ids"] == [5]`：每段 report 的 `sub_intent_ids` 是按原顺序切分的 id 列表。
- `content` 中同时包含 "第1章"、"第2章"、"第3章"：分段时每段正文前会加上 `第N章` 标题（对应 writer.py 第150-153行的 `f"第{i}章\n\n{c}"`）。

**副作用**：
- 测试通过 `fake_deepseek` fixture 注入假响应，不调用真实 API；`write_long_script` 内部会调用 `extract_world_state`（writer.py 第141行），但该调用也走 `fake_deepseek`，且测试未断言其副作用。
- 测试未修改任何文件/全局状态，`fake_deepseek.writer_responses` 被消费（每段一次调用，共 3 次）。

**前置条件**：
- 需要 `fake_deepseek` fixture（conftest 提供），且 `fake_deepseek.writer_responses` 至少包含 3 个响应（每段一个），否则会因响应耗尽而失败。
- `snapshot` 必须含 `sub_intents` 键，且每条有 `id` 字段（`_sub_intents` 保证）。

**调用后保证**：
- 返回的 `reports` 长度等于分段数，每段 `sub_intent_ids` 按原顺序连续切分、不重叠、不遗漏。
- 当 `len(chunks) > 1` 时，`content` 由每段正文前加 `第N章` 标题拼接而成（writer.py 第150-153行）。

【调用方须知】该函数在分段时会给每段正文前强制加上 `第N章` 标题（writer.py 第150-153行），但**只有当 sub_intents 数量 > chunk_size 时才会加标题**；若数量 ≤ chunk_size，则返回的 content 是单段原文、不含任何章节标题（见 writer.py 第154-155行及 test_short_snapshot_produces_single_chunk_no_chapter_headers 的断言）。调用方若依赖 content 是否含章节标题来判断是否分段，需注意这个边界。

*△ 未核实完——超过核实步数上限，未能完成核实*
