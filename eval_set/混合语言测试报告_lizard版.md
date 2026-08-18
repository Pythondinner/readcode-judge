# 项目体检报告

共2个文件（另有0个不支持的文件类型被跳过），总行数952

## 复杂度分级分布

- [A] 46个函数/类
- [B] 5个函数/类
- [C] 1个函数/类
- [D] 1个函数/类
- [E] 1个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [E] deepseek-harness\packages\core\agent-loop\src\agent.ts :: step（第332行）复杂度=40
  [D] deepseek-harness\packages\core\agent-loop\src\agent.ts :: turn（第246行）复杂度=21
  [C] deepseek-harness\packages\core\agent-loop\src\agent.ts :: get status（第99行）复杂度=12
  [B] 自动剧本生成机\src\ledger.py :: _migrate_chain_to_series（第153行）复杂度=9
  [B] 自动剧本生成机\src\ledger.py :: list_projects（第105行）复杂度=7
  [B] 自动剧本生成机\src\ledger.py :: save_draft（第292行）复杂度=7
  [B] 自动剧本生成机\src\ledger.py :: delete_draft（第347行）复杂度=6
  [B] deepseek-harness\packages\core\agent-loop\src\agent.ts :: kick（第210行）复杂度=6
  [A] 自动剧本生成机\src\ledger.py :: _resolve_existing_path（第25行）复杂度=5
  [A] 自动剧本生成机\src\ledger.py :: delete_project（第272行）复杂度=5
  [A] 自动剧本生成机\src\ledger.py :: latest_draft_filename（第323行）复杂度=5
  [A] deepseek-harness\packages\core\agent-loop\src\agent.ts :: wakeDriver（第172行）复杂度=5
  [A] 自动剧本生成机\src\ledger.py :: find_successors（第245行）复杂度=4
  [A] 自动剧本生成机\src\ledger.py :: list_drafts（第310行）复杂度=4
  [A] 自动剧本生成机\src\ledger.py :: compile_series（第377行）复杂度=4

## 行为描述明细（B级以上，共8个）

### [B] 自动剧本生成机\src\ledger.py :: _migrate_chain_to_series（第153行，复杂度9）

函数 `_migrate_chain_to_series(any_member_name: str) -> str`（src/ledger.py 第153行起）的契约如下：

**输入**：一个字符串 `any_member_name`，代表链上任意一幕的项目名（第154行 `def _migrate_chain_to_series(any_member_name: str) -> str:`）。

**输出**：返回该链的系列根名（字符串），即 `root`（第177行 `return root`）。

**副作用（修改外部状态/文件系统）**：
1. 若根节点尚未嵌套（`root_already_nested` 为 False），会把根节点从 `ledger/<root>/` 搬成 `ledger/<root>/<root>/`（第163-171行）：
   - 用临时名 `.{root}.migrating` 中转（第166行 `tmp_path = os.path.join(LEDGER_ROOT, f".{root}.migrating")`），`shutil.move(root_current_path, tmp_path)` 后 `os.makedirs(series_path)` 再 `shutil.move(tmp_path, os.path.join(series_path, root))`。
2. 把链上其余仍扁平存储的成员搬进同一个系列文件夹（第173-176行）：遍历 `list_projects()`，对 `series_root(name) == root` 且当前路径在 `LEDGER_ROOT` 下的成员执行 `shutil.move(current_path, os.path.join(series_path, name))`。

**前置条件**：
- 若根节点尚未嵌套且 `root_current_path is None`（即根节点在磁盘上不存在），会抛出 `FileNotFoundError(f"project '{root}' not found")`（第165行）。
- 依赖 `series_root` 能顺着 predecessor 链找到根（第155行 `root = series_root(any_member_name)`）。

**调用后保证**：
- 整条链的所有成员都归到同一个系列文件夹 `ledger/<root>/` 下（嵌套结构）。
- 若链已经在系列里（`root_already_nested` 为 True），则跳过根节点搬迁，只处理其余扁平成员（第158-162行判断，第173-176行仍会执行）。
- 返回的 `root` 是系列文件夹名。

【调用方须知】该函数会**实际移动磁盘上的文件夹**（`shutil.move`），且移动前会先创建临时目录 `.{root}.migrating` 再搬入——如果调用方在移动过程中崩溃或中断，可能残留临时目录或处于半迁移状态；另外，它只迁移 `series_root(name) == root` 的成员，若链上某成员因 predecessor 元数据缺失/损坏导致 `series_root` 算不出同一个 root，该成员不会被搬进系列文件夹，调用方不能假设调用后所有相关项目一定都在同一目录下。

*△ 未核实完——超过核实步数上限，未能完成核实*

### [B] 自动剧本生成机\src\ledger.py :: list_projects（第105行，复杂度7）

函数 `list_projects()` 定义在 `自动剧本生成机/src/ledger.py` 第 105-119 行。

**契约描述：**

1. **输入**：无参数。函数签名 `def list_projects() -> list:`（第 105 行），不接收任何输入。

2. **输出**：返回一个字符串列表，每个字符串是一个“幕”的名字（即项目标识符）。依据：docstring 第 106-107 行“返回所有‘幕’的名字（扁平的独立项目 + 每个系列文件夹里的每一幕）”，以及第 118 行 `return names`。

3. **副作用**：无。函数只读磁盘，不写文件、不修改全局状态。依据：函数体只调用 `os.path.isdir`、`os.listdir`、`os.path.isfile` 等只读操作，没有任何 `open(..., 'w')`、`shutil.move`、`os.makedirs` 等写操作。

4. **前置条件**：无强制前置条件。若 `LEDGER_ROOT` 目录不存在，函数直接返回空列表。依据：第 110 行 `if not os.path.isdir(LEDGER_ROOT): return []`。

5. **调用后保证**：
   - 返回的列表按名字排序（`sorted` 排序，第 111 行和第 115 行）。
   - 列表是单层的，不包含嵌套路径，只包含“幕”的名字。依据：docstring 第 107 行“对外依然是一份单层的名字列表，嵌套只是磁盘层面的事”。
   - 只包含那些目录下存在 `snapshot.json` 文件的项目。依据：第 113 行 `if os.path.isfile(os.path.join(entry_path, "snapshot.json"))` 和第 116 行 `if os.path.isfile(os.path.join(act_path, "snapshot.json"))`。
   - 对于系列文件夹（即 `ledger/<entry>/` 下没有 `snapshot.json` 但包含子目录的），会展开其子目录，把每个含 `snapshot.json` 的子目录名加入列表。依据：第 114-117 行。

**【调用方须知】**：`list_projects()` 返回的名字是“幕”的名字，而不是“系列”的名字——如果一个项目是系列的一部分（嵌套存储），它返回的是该幕自己的名字（如 `ledger/<系列根>/<幕名>/` 中的 `<幕名>`），而不是系列根的名字；同时，系列根本身（如 `ledger/<系列根>/<系列根>/` 中的那个 `<系列根>`）也会作为一个独立项目被返回，因为它的目录下也有 `snapshot.json`。因此调用方不能通过这个列表直接判断哪些项目属于同一系列，需要额外调用 `series_root()` 才能知道每个项目所属的系列根。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和调用后保证的描述均与代码原文逐条吻合，包括排序、单层列表、只含 snapshot.json 的项目、系列展开逻辑，以及 LEDGER_ROOT 不存在时返回空列表。调用方须知部分也准确指出了返回的是幕名而非系列名，且系列根也会被返回，需要额外调用 series_root 才能判断归属。*

### [B] 自动剧本生成机\src\ledger.py :: save_draft（第292行，复杂度7）

【save_draft 契约】

**输入**（见第292行定义 `def save_draft(project_name: str, mode: str, content: str) -> str:`）：
- `project_name`：项目名，用于定位项目目录（内部调用 `project_dir(project_name)`，见 `_drafts_dir`）。
- `mode`：草稿模式名，会拼进文件名。
- `content`：要写入的草稿正文。

**输出**：返回写入的文件名（不含目录），格式为 `<mode>_v<N>.md`，其中 N 是版本号（见 `return filename`）。

**副作用**：
1. 创建草稿目录：`_drafts_dir` 里 `os.makedirs(path, exist_ok=True)` 会确保 `项目目录/drafts` 存在（不存在则创建）。
2. 写文件：`with open(os.path.join(d, filename), "w", encoding="utf-8") as f: f.write(content)` 以 UTF-8 覆盖写入新文件。
3. 不修改其他文件，不删除旧文件（版本号递增，互不覆盖）。

**前置条件**：
- `project_name` 对应的项目目录必须存在（`project_dir` 会用到，若不存在可能报错）。
- 无其他显式前置条件。

**调用后保证**：
- 草稿目录里会多出一个 `<mode>_v<N>.md` 文件，N 是当前该 mode 下最大版本号 +1（若没有该 mode 的版本则从 1 开始）。
- 返回的文件名可直接用于 `load_draft` 读取。

**版本号计算依据**（第294-300行）：扫描目录中所有以 `<mode>_v` 开头、`.md` 结尾的文件，解析版本号（忽略解析失败的文件），取最大值+1。

【调用方须知】调用方最容易忽略的是：`save_draft` 只保证文件名版本号递增，但它**不会**清理或覆盖同 mode 的旧版本文件——每次调用都会新增一个文件，旧版本永远保留；如果调用方期望“保存最新草稿”会覆盖旧稿，必须自己先调用 `latest_draft_filename` 并删除旧文件，否则草稿目录会无限累积。

*△ 未核实完——超过核实步数上限，未能完成核实*

### [B] 自动剧本生成机\src\ledger.py :: delete_draft（第347行，复杂度6）

delete_draft 的契约如下（依据：自动剧本生成机/src/ledger.py 第347-360行）：

**输入**：
- `project_name: str`——项目标识符（某一幕的名字，单一字符串，不区分扁平/嵌套存储，由 `_drafts_dir` 内部解析）。
- `filename: str`——要删除的草稿文件名（不含目录，如 `novel_v3.md`）。

**输出**：
- 返回 `None`（函数签名 `-> None`，无返回值）。

**副作用（改了什么外部状态）**：
- 删除磁盘上的草稿文件：`path = os.path.join(_drafts_dir(project_name), filename); if os.path.exists(path): os.remove(path)`（第355-356行）。
- **条件性连带删除**：如果被删的正好是该 mode 的当前最新版本（`was_latest` 为真），还会删除同目录下的 `<mode>_state.md` 运行事实清单文件：`state_path = os.path.join(_drafts_dir(project_name), f"{mode}_state.md"); if os.path.exists(state_path): os.remove(state_path)`（第358-360行）。
- 不修改 snapshot.json、log.jsonl 或任何其他文件。

**前置条件**：
- 无显式前置条件；函数不抛异常。若 `filename` 不含 `_v`（`mode` 为 None），则 `was_latest` 为 False，只删文件不删 state。若文件不存在，`os.path.exists` 为 False，静默跳过删除（不报错）。

**调用后保证**：
- 指定的草稿文件被删除（若存在）。
- 若删除的是最新版本，对应的 `<mode>_state.md` 也被删除；若删除的是历史版本，state 文件保留。
- 函数不返回任何值，不抛异常，不检查文件是否属于该项目或是否合法。

【调用方须知】当 `filename` 不含 `_v` 子串（例如传入 `state.md` 或任意非 `_v` 文件名）时，`mode` 为 None，`was_latest` 恒为 False，函数只会删除该文件而**绝不会**删除任何 state 文件——但若你传入的恰好是 `<mode>_state.md` 本身，它会被当作普通草稿删除，且不会触发连带删除逻辑；更关键的是，删除最新版草稿会**静默连带删除**对应的 `<mode>_state.md`，调用方若依赖该 state 文件做后续事实核对，必须自行预判并备份，因为函数不会给出任何提示或返回值告知 state 被删了。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和调用后保证的描述均与代码逐行吻合，包括条件性连带删除 state 文件的逻辑和静默行为。*

### [E] deepseek-harness\packages\core\agent-loop\src\agent.ts :: step（第332行，复杂度40）

【step 函数契约】

**输入**：
- 参数 `assembly: PromptAssembly`（第332行），来自 `preStep` 返回的 `decision.assembly`（第296行），包含 `tools` 和用于渲染 system prompt 的内容。
- 隐式输入：`this.phase` 必须是 `{ kind: 'running', turn, step, abort: { signal } }`（第334-335行），`this.session` 的日志、`this.loopCtx` 的 LLM 流、`this.inbox` 的 next-step 队列。

**输出**：
- 返回 `Promise<StepEndReason | null>`，其中 `StepEndReason = Extract<TurnEndReason, { kind: 'completed' | 'max-tokens' }>`（第30行）。
- 具体返回：
  - `{ kind: 'max-tokens' }`：当 `finish.kind === 'max-tokens'`（第382行）。
  - `{ kind: 'completed' }`：当无 tool-call（第386行）或 `concluded === true`（第395行）。
  - `null`：当有 tool-call 但 `concluded === false`（第396行），表示需要继续循环。

**副作用**（修改外部状态）：
1. **session 日志追加**：
   - `this.session.append('assistant/chunk', { turn, step, chunk })`（第350行），每个流块都追加，并记录返回的 `seq` 到 `chunkSeqs`。
   - `this.session.append('assistant/message', { turn, step, message, ...usage }, { surfaceOp: 'append', sourceEventSeqs: chunkSeqs })`（第371-378行），追加完整助手消息，并关联源块序列。
2. **inbox 修改**：通过 `executeToolCalls` 的第三个参数回调 `context => this.inbox.splice('next-step', this.inbox.nextStep.length, 0, [context])`（第393行），将工具调用产生的上下文插入到 next-step 队列末尾。
3. **dispatch 事件**：在请求错误时触发 `'agent/request-error'` waterfall（第357-365行）。

**前置条件**：
- `this.phase.kind === 'running'`，否则抛 `Error`（第334行）。
- `signal` 未中止（`signal.throwIfAborted()` 在第335、345、352、355、366行）。
- 调用方（`turn` 方法）已先追加 `step/start` 事件并设置 `phase.step`（第302-303行）。

**调用后保证**：
- 若返回 `null`，表示有未完成的 tool-call，调用方应继续循环（`turn` 中 `while(true)` 会再次调用 `step`）。
- 若返回非 null，表示步骤结束，调用方会追加 `step/end`（第306行）。
- 若发生错误且非重试，会抛 `LlmError`（第368行），由 `turn` 的 catch 处理。

【调用方须知】
`step` 在返回 `null` 时不会结束步骤，而是继续 `while(true)` 循环，但每次循环都会重新调用 `buildRequest` 并基于 `this.session.deriveMessages()` 重新构建请求——这意味着工具调用产生的上下文（通过 `inbox.splice` 插入的）并不会自动进入下一次请求的输入，除非 `executeToolCalls` 的回调把上下文写入了 session（实际它只写入了 inbox，而 `buildRequest` 用的是 `session.deriveMessages()`），所以如果工具调用没有把结果写入 session，下一次循环的请求可能看不到工具结果，导致死循环或重复调用。调用方必须确保工具执行会通过某种机制（如 session 追加）把结果反馈给模型，否则 `step` 会无限循环。

*✓ 核实通过——候选答案对 step 函数的输入、输出、副作用和前置条件的描述均与代码原文相符，特别是【调用方须知】中关于工具结果不会自动进入 session 的警告是准确的，因为代码中 executeToolCalls 的回调只写 inbox，而 buildRequest 基于 session 派生消息。*

### [D] deepseek-harness\packages\core\agent-loop\src\agent.ts :: turn（第246行，复杂度21）

【调用方须知】turn() 是 ReactLoopAgent 的私有方法，调用方（仅限本类内部）必须保证 phase.kind === 'running'（否则第 246 行 `this.throwError(new Error(...))` 直接抛错），且调用前 phase.abort.signal 未被 abort（第 249 行 `signal.throwIfAborted()`）。它承诺：输入为无参数，输出为 boolean——true 表示本 turn 结束后 inbox 仍有待处理消息（第 330 行 `if (!this.inbox.hasPending) return false` 之后返回 true），false 表示没有待处理消息或 turn 被 blocked/completed 提前结束。副作用：1) 向 session 追加事件：`turn/start`（第 252 行）、`step/start`（第 267 行）、`user/message`（第 271 行）、`step/end`（第 276 行 finally）、`turn/end`（第 306 行 finally，reason 为 turnEnds!）；2) 修改 phase.turn（第 257 行 `phase.turn = turn`）、phase.step（第 268 行）、phase.abort（第 331 行新建 AbortController）、phase.wakeRequested（第 332 行置 false）；3) 通过 dispatch 触发 `agent/turn-stopping` 事件（第 280 行）；4) 可能调用 LLM 流式请求并追加 `assistant/chunk`/`assistant/message`（在 step() 内）。前置条件：phase 必须为 running（否则抛错）、signal 未 abort、session 可写。调用后保证：无论正常/异常/abort，都会在 finally 中追加 `turn/end`（除非追加本身抛错则 throwError）；若 signal 被 abort，turnEnds 设为 `{kind:'aborted', reason}` 并重新抛出原错误（第 289-292 行）；非 LlmError 的异常被扁平化为 `{message: errorChain(error), code:'UNKNOWN'}`（第 296-298 行）。

【调用方须知】最该警惕的是：turn() 在 signal 被 abort 时不会吞掉错误——它把 turnEnds 设为 aborted 后**重新抛出原 error**（第 292 行 `throw error`），调用方（kick）必须捕获它，否则会逃逸到 driver 边界之外；同时它还会在 finally 里追加 `turn/end`，即使 abort 也会写 session，所以调用方不能假设 abort 后 session 没有 turn/end 记录。另一个易忽略点：turn 结束时若 inbox 有 pending 消息，它会**新建 AbortController 并重置 wakeRequested=false**（第 331-332 行），使之前 latch 的 wake 失效——调用方若依赖旧 abort 信号判断状态会出错。

*✓ 核实通过——候选答案对 turn() 的契约描述与代码逐条吻合，包括前置条件、返回值、副作用、异常处理和 abort 行为，且引用的行号和代码原文准确。*

### [C] deepseek-harness\packages\core\agent-loop\src\agent.ts :: get status（第99行，复杂度12）

在 deepseek-harness/packages/core/agent-loop/src/agent.ts 中，第99行的 `get status` 是 `ReactLoopAgent` 类的一个只读 getter（第98-100行）：

```ts
get status(): AgentStatus {
  return this.phase.kind === 'idle' || this.phase.kind === 'maintenance' ? 'idle' : 'running'
}
```

**契约描述：**

1. **输入**：无参数。它只读取实例私有字段 `this.phase`（第99行 `this.phase.kind`）。

2. **输出**：返回 `AgentStatus` 类型（从 `@deepseek-ai/dsh-agent` 导入，第8行）。具体取值只有两个：当 `this.phase.kind` 为 `'idle'` 或 `'maintenance'` 时返回字符串 `'idle'`，否则（即 `'running'`）返回 `'running'`。

3. **副作用**：无。它不修改任何状态、不写文件、不触发事件、不调用外部 API。它只做一次纯布尔判断并返回。

4. **前置条件**：无显式前置条件。但注意它依赖 `this.phase` 已被构造函数初始化（第92行 `this.phase = { kind: 'idle', lastTurn }`）。在构造函数执行完之前调用会访问未初始化字段。

5. **调用后保证**：返回的值是当前 `this.phase.kind` 的派生结果，且与 `setPhase` 中发布的事件一致——`setPhase`（第102-109行）在状态变化时通过 `this.dispatch.emit('agent/status', { status })` 发布 `agent/status` 事件，其中 `status` 正是这个 getter 的返回值。因此调用方可以依赖：`status === 'idle'` 表示当前没有正在运行的 driver 活动（idle 或 maintenance），`status === 'running'` 表示有一个 driver 正在运行。

**【调用方须知】**：`status` 返回 `'idle'` 并不代表 agent 一定空闲可接受新工作——它把 `'maintenance'` 阶段也归为 `'idle'`（第99行 `this.phase.kind === 'maintenance' ? 'idle'`），但 maintenance 阶段（`runMaintenance` 设置，第137-158行）期间 `runMaintenance` 会抛错拒绝新工作（第139行 `if (this.phase.kind !== 'idle') throw new Error(...)`）。所以调用方不能仅凭 `status === 'idle'` 就认为可以安全地调用 `runMaintenance` 或 `send` 等会启动新活动的操作，必须区分 idle 与 maintenance 两种底层阶段。

*✓ 核实通过——候选答案对 getter 的输入、输出、副作用、前置条件和调用后保证的描述均与代码原文一致，且【调用方须知】准确指出了 maintenance 阶段被归为 idle 但 runMaintenance 会拒绝新工作的关键陷阱。*

### [B] deepseek-harness\packages\core\agent-loop\src\agent.ts :: kick（第210行，复杂度6）

函数 `kick` 是 `ReactLoopAgent` 类的私有方法（`private async kick(): Promise<void>`，第210行），它驱动 agent 的 turn 循环直到没有待处理工作。

**输入**：无参数。它依赖实例状态：`this.phase`（必须是 `running` 状态）、`this.inbox`、`this.session`、`this.dispatch`、`this.loopCtx`。

**输出**：`Promise<void>`，不返回任何值。

**副作用**（修改的外部状态）：
1. 修改 `this.phase`：在 `finally` 块中，如果 `this.phase.kind === 'running'`，则调用 `this.setPhase({ kind: 'idle', lastTurn: turn })`（第220行），将 phase 从 `running` 变为 `idle`，并记录 `lastTurn`。
2. 可能触发 `wakeDriver()`：如果 `wakeRequested && this.inbox.hasPending`（第221行），则调用 `this.wakeDriver()`，这会启动新的 driver 活动（改变 `activityDone`、phase 状态等）。
3. 通过 `this.turn()` 间接修改 session（追加 `turn/start`、`step/start`、`user/message`、`assistant/chunk`、`assistant/message`、`turn/end` 等事件）、inbox（claim 消息）、dispatch（发出 `agent/error`、`agent/status` 等事件）。

**前置条件**：
- 调用方（`wakeDriver` 第180行）必须已通过 `setPhase` 将 phase 设为 `running`，并设置了 `this.activityDone`。
- 调用时 phase 必须是 `running`，否则 `turn()` 会调用 `throwError` 抛出错误（第245行 `if (this.phase.kind !== 'running')`）。

**调用后保证**：
- 无论成功、失败还是取消，`finally` 块都会确保 phase 最终回到 `idle`（如果它当时是 `running`），并记录 `lastTurn`。
- 所有异常都被捕获（`catch (_error)`），不会从 `kick` 抛出——错误被“contained at the driver boundary”（第214行注释）。
- 如果 phase 在进入 `finally` 时不是 `running`（例如已被外部 `cancel` 改变），则不会修改 phase。

【调用方须知】`kick` 的 `finally` 块只在 `this.phase.kind === 'running'` 时才把 phase 重置为 `idle`——如果调用方在 `kick` 运行期间（比如通过 `cancel` 或 `runMaintenance`）已经把 phase 改成了 `maintenance` 或 `idle`，`kick` 就不会碰 phase，也不会触发 `wakeDriver`；这意味着 `kick` 并不保证“结束后一定回到 idle”，它只负责清理自己启动的那个 `running` 阶段。调用方若依赖 `kick` 结束后 phase 必为 `idle`，必须确保没有其他代码在 `kick` 执行期间抢占 phase 所有权。

*✓ 核实通过——逐条核对了候选答案中引用的行号和代码行为，所有描述与源码一致，包括 finally 的条件重置和 wakeDriver 触发条件。*
