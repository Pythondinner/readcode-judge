# 分批分析报告

共8个批次

## 跨批关联整合

### 跨批次关联的不变量（7个）

- **Agent id 必须等于其 session id，且同一 id 只能有一个存活 Agent。该不变量由 agent 注册表（agent 子模块）强制，但实际创建/恢复的发布路径在 agent-loop 子模块中实现，两者共同保证。**
  - 涉及批次：agent、agent-loop
  - 依据：agent 子模块叙述 3.1/3.2 提到注册表 enter() 强制 id 唯一且等于 session id；agent-loop 子模块叙述 3.9 提到 prepare() 中 publish() 调用 sessions.enter 和 agents.enter，且并发操作由最终 enter() 仲裁。
- **agent/inbox/* 事件在修改 live 投影前发出，且 MessageId 在 pending 列表中唯一。该不变量由 agent 子模块的 Inbox 类实现，但 agent-loop 子模块的 send() 是唯一修改入口，两者共同保证。**
  - 涉及批次：agent、agent-loop
  - 依据：agent 子模块叙述 3.8/3.9 描述 Inbox 的 mutate() 先 append 事件再 splice，且 validate() 检查 MessageId 唯一；agent-loop 子模块叙述 3.6 提到 send() 是唯一 inbox 修改入口，且回调在 splice 前注册。
- **工具调用结果按模型序提交，且每个 tool/result 引用其 tool/call 的 seq。该不变量由 agent-loop 子模块的 tool-calls.ts 实现，但依赖 session 子模块的 append 事件和 seq 连续性。**
  - 涉及批次：agent-loop、session
  - 依据：agent-loop 子模块叙述 3.4 描述 commitReady() 按模型序提交并引用 callSeqs；session 子模块叙述 3.1 强制事件 seq 连续递增，且 append 时校验 expectedSeq。
- **每个成功完成的 provider 调用恰好追加一个 assistant/message 完成锚点。该不变量由 agent-loop 子模块的 step() 实现，但依赖 session 子模块的 surface 规则（assistant/message 必须带 surfaceOp）。**
  - 涉及批次：agent-loop、session
  - 依据：agent-loop 子模块叙述 3.1 描述 step() 中 append assistant/message；session 子模块叙述 3.3 要求消息事件必须带 surfaceOp，否则抛错。
- **Code Mode 下模型只能直接调用 run_code，其他工具解析为 UNKNOWN_TOOL。该不变量由 tools 子模块的 collapses() 实现，但由 agent-tool-presentation 子模块的 presentAs('code') 触发。**
  - 涉及批次：agent-tool-presentation、tools
  - 依据：agent-tool-presentation 子模块叙述不变量 B 提到 UNKNOWN_TOOL 解析在 dsh-tools 中，本包只是通过 presentAs('code') 触发；tools 子模块叙述 3.9 描述 collapses() 在策略流水线之前拒绝非 run_code 工具。
- **作用域注册的可见性与所有权必须来自同一个上下文。该不变量由 scope 子模块的 ScopedLayers.effect 实现，但被 system-prompt 子模块的 scoped 层和 tools 子模块的 scoped shadowing 依赖。**
  - 涉及批次：scope、system-prompt、tools
  - 依据：scope 子模块叙述不变量 1 描述 effect 用 scopeOf(ctx) 决定层、ctx.effect 决定 disposer；system-prompt 子模块叙述 I10 提到 scoped 层 shadow 全局且随 scope 销毁清理；tools 子模块叙述 3.18 提到 restrict 只过滤继承的全局工具，且 view() 是唯一解析器。
- **事件准入沿父链向上、绝不向下。该不变量由 scope 子模块的 scopeTarget 实现，但被 system-prompt 子模块的 scoped 监听器（agent.ctx assemble 只影响自身 scope）依赖。**
  - 涉及批次：scope、system-prompt
  - 依据：scope 子模块叙述不变量 4 描述 filter 循环只向上走；system-prompt 子模块叙述 I9 提到 scoped 监听器只影响自身 scope 的 assemblies。

### 潜在的责任空白（4个）

- **agent/request 瀑布流中 provider/model 缺失时的补全责任。** —— agent-loop 子模块叙述 3.14 提到 buildRequest() 中 provider/model 缺失时抛错，但 README 提到 agent/request 可能补全缺失对；agent-default-model 子模块叙述提到服务不校验 catalog 成员资格，可用性诊断由实际消费者负责。没有明确哪个模块负责在 agent/request 中补全缺失的 provider/model。
- **第二次声明 tool-presentation 的拒绝逻辑。** —— agent-tool-presentation 子模块叙述不变量 G 只在 README 中声称第二次声明会被拒绝，但 src/index.ts 和测试中都没有实现或验证该逻辑。没有明确哪个模块负责实现这一拒绝。
- **context 注册时 system-prompt/change 监听器抛错回滚的测试缺失。** —— system-prompt 子模块叙述 I3 提到 section/tool/variable 有回滚测试，但 context 注册时监听器抛错回滚没有专门测试。虽然代码可能实现了回滚，但测试覆盖存在空白，可能双方都以为对方覆盖了。
- **session 子模块的 turn/step 嵌套和工具配对不变量只在可选插件中强制。** —— session 子模块叙述 3.6/3.7 明确这些不变量只在 session-invariant 伴生插件加载时生效，Session.append 本身不强制。如果插件未加载，这些关系可能无人负责检查，存在责任空白。

## 各批次明细

### 批次「agent」

# 项目体检报告

共15个文件（另有0个不支持的文件类型被跳过），总行数3191

## 项目叙述（✓ 核实通过）

项目定位描述（依据：src/ 下各文件与 README.md）

## 1. 项目是什么
`@deepseek-ai/dsh-agent` 是 dsh 生态中**Agent 的接口层与运行时注册表**：它定义 Agent 的公开句柄（`Agent`）、进程内 initiator 作用域、`agent/*` 事件词汇，以及一个跟踪存活 Agent 的注册表服务（`ctx.agents`）。它**不实现具体循环**（loop 由 `@deepseek-ai/dsh-agent-loop` 提供，通过 `setFactory` 注入），因此 UI、hooks、orchestrators 等插件只依赖本包接口，loop 可替换。

面向场景：需要创建/恢复/跟踪 Agent、向 Agent 投递消息（followup/steer/inject）、监听 Agent 生命周期与 inbox 事件的插件与桥接层（如 ACP bridge）。解决的问题：把 Agent 的“接口/注册/事件”与“具体驱动实现”解耦，让消费者不依赖具体 loop 包。

## 2. 模块与职责
- `src/index.ts`：`AgentRegistry` 服务（ctx key `agents`）——注册/查询/列出 Agent、`create`/`resume` 委托给工厂、进程内 initiator 作用域（`withInitiator`/`withoutInitiator`/`currentInitiator`/`requireInitiator`）、`setFactory` 注册创建工厂。
- `src/runtime-types.ts`：公开类型与 `agent/*` 事件声明（`Agent` 接口、`AgentStatus`、`PreStepDecision`、`CancelOptions`、`agent/created`/`agent/disposed`/`agent/status`/`agent/inbox/*`/`agent/pre-step`/`agent/request`/`agent/request-error`/`agent/turn-stopping`/`agent/error` 等）。
- `src/inbox.ts`：`Inbox` 类——对持久化 `agent/inbox/spliced` 事件的增量投影，提供 `append/prepend/replace/remove/clear/splice/claim`，并发布 `inserted/discarded/claimed` 通知。
- `src/dispatch.ts`：`agentEvents`/`agentCarrier`/`assembleContextFor`/`emitAgentEvent`——把 agent 主体与其 scope carrier 耦合的 fused 分发器。
- `src/consumed-work.ts`：`foldConsumedWork`——从日志折叠出“被消费的工作”的账目（哪个 turn 结束、是否有未运行就被取消的工作）。
- `src/model-selection.ts`：`installModelSelection`——把可变 provider/model/effort 选择耦合到 prompt 组装与请求路由。
- `src/invariant.ts`：可选 companion 插件，注册 `agent/status` 无重复转换的不变量检查。
- `src/types.ts`：声明 `agent/inbox/spliced` 会话事件。

## 3. 关键不变量（含证据范围）

### 3.1 注册表唯一性：同一 id 只能有一个存活 Agent
- 证据：`src/index.ts` 的 `enter()`——`if (this.store.has(id)) throw new Error(...)`；`register()` 通过 `enter()` 记录。
- 范围：`enter()` 是 `register()` 与工厂 `create/resume` 的最终发布路径，覆盖这两个入口。

### 3.2 Agent id 必须等于其 session id
- 证据：`src/index.ts` 的 `enter()`——`if (id !== agent.session.id) throw new Error(...)`。
- 范围：`enter()` 覆盖 `register()` 与工厂发布路径。

### 3.3 创建/恢复的发布顺序：先 setup（未发布）→ 提交 commit → 插入 session/agent → 按序 announce → 启动 loop；任何失败回滚且不发布任一 id
- 证据：`src/index.ts` 的 `AgentFactory.createAgent`/`resume` 文档注释（“awaits unpublished setup, invokes its optional synchronous commit, inserts both session and agent, emits their creation notifications in order, emits agent/session-start, and only then starts the loop. The sequence is rollback-covered”）；`CreateAgentOptions.setup` 文档（“Setup may return an AgentSetupCommit; the factory invokes its synchronous commit() after every setup await settles and immediately before registry publication… A setup throw/rejection, commit throw, or owner disposal rolls the scope back without publishing either id”）。
- 范围：`create` 与 `resume` 两个入口（`AgentRegistry.create`/`resume` 都委托给工厂的 `createAgent`/`resume`）。

### 3.4 `agent/created` 恰好发出一次，且 detach 在 dispatch 展开后才执行；stale capability 不能删除后来的同 id 替换
- 证据：`src/index.ts` 的 `announce()`——`if (entry.announced || entry.announcing) throw new Error(...)`；`enter()` 返回的 detach 在 `entry.announcing` 时设置 `detachRequested`，`announce()` 的 finally 中才调用 `detachEntered`；`detachEntered` 检查 `this.store.get(entry.id) !== entry` 后返回。
- 范围：`announce()`/`enter()` 覆盖 `register()` 与工厂发布路径。

### 3.5 `agent/disposed` 只对已 announce 的条目发出；未 announce 的插入回滚不发出 disposed
- 证据：`src/index.ts` 的 `detachEntered()`——`if (!entry.announced) return` 后才 `emitDisposed`。
- 范围：`detachEntered` 是 `enter()` 返回的 detach 与 `announce()` 的 finally 共同调用的路径。

### 3.6 通知类事件（emit）不否决生命周期：每个 listener 的同步 throw 与返回 Promise 的 rejection 被独立捕获并记录
- 证据：`src/dispatch.ts` 的 `agentEvents().emit`——`try { ... } catch { ctx.logger.warn(...) }` 且 `void Promise.resolve(returned).catch(...)`；`src/index.ts` 的 `emitDisposed`/`announce` 同样逐 listener 捕获。
- 范围：`agentEvents().emit`（覆盖所有 emit 模式事件）与 `emitDisposed`/`announce`。

### 3.7 `agent/created` 的同步 listener 失败否决发布（回滚），而返回 Promise 的 rejection 只被报告
- 证据：`src/index.ts` 的 `announce()`——同步 throw 会传播出 `announce()`（“A synchronous creation failure vetoes publication and rolls back”），而 `void Promise.resolve(returned).catch(...)` 只记录。
- 范围：`announce()` 覆盖 `register()` 与工厂发布路径。

### 3.8 inbox 的持久化 splice 先于 live 投影变更提交，同步 observer 能看到 pre-splice 状态
- 证据：`src/inbox.ts` 的 `mutate()`——`const event = this.session.append('agent/inbox/spliced', splice)` 之后才 `inbox.splice(...)`；`types.ts` 注释“Live dispatch precedes projection mutation, so synchronous observers may read the pre-splice inbox”。
- 范围：`Inbox` 的所有变更方法（`append/prepend/replace/remove/clear/splice/claim`）都经 `mutate()`。

### 3.9 inbox 中 pending 消息的 `MessageId` 必须唯一（跨两个列表）
- 证据：`src/inbox.ts` 的 `validate()`——对 `next-turn` 与 `next-step` 合并检查重复 id，重复则 throw。
- 范围：`mutate()`（所有变更）与 `apply()`（重放持久化事件）都调用 `validate()`。

### 3.10 `claim` 是纯删除 splice（不标记 canceled），且只从 next-step 取全部、从 next-turn 取一个；`clear`/`remove` 是 durable 取消（outcome: 'canceled'）
- 证据：`src/inbox.ts` 的 `claim()`——`this.mutate('next-step', 0, this.nextStep.length, [], false)` 与 `this.mutate('next-turn', 0, 1, [], false)`（`discardRemoved=false`）；`clear()`/`remove()` 走 `splice()`（`discardRemoved=true`），`mutate()` 中 `outcome = discardRemoved && actualDeleteCount > 0 ? 'canceled' : undefined`。
- 范围：`claim` 与 `clear`/`remove`/`replace`（replace 的删除也带 canceled，但插入新消息）。

### 3.11 `foldConsumedWork` 的账目规则：只有 `completed` 结束不记账（空 claim 被重写掉）；`blocked`/`aborted`/`interrupted`/`error` 结束对已 claim 输入记账；`canceled` 且无插入的 splice 记为 droppedUnrun
- 证据：`src/consumed-work.ts` 的 `accountsForClaim()` 与 `foldConsumedWork()`。
- 范围：`foldConsumedWork` 是唯一入口（`src/consumed-work.ts`）。

### 3.12 模型选择：prompt 组装快照 `selection.current` 到 `selection.assembled`，请求路由使用 `assembled`，避免并发切换分裂两个表面；absent effort 清除继承的 effort
- 证据：`src/model-selection.ts` 的 `installModelSelection()`——`system-prompt/assemble` 监听器先 `const selected = selection.current`，`await next()` 后 `selection.assembled = selected`；`agent/request` 监听器用 `selection.assembled`。
- 范围：`installModelSelection` 是唯一入口。

### 3.13 initiator 作用域：`withInitiator` 保留 operation 的精确同步值或 Promise；teardown 时拒绝新边界、排空返回 Promise 的边界、然后 disable AsyncLocalStorage
- 证据：`src/index.ts` 的 `runWithInitiator()`（`isPromise(result)` 分支挂 then 释放 run）、`disposeInitiators()`（`this.initiators.disable()`）、`closeInitiators()`（状态转 `closing` 后 `runWithInitiator` 抛 `DISPOSED_INITIATOR_MESSAGE`）。
- 范围：`withInitiator`/`withoutInitiator` 都经 `runWithInitiator`。

### 3.14 `agent/status` 不能重复（no-op 转换）
- 证据：`src/invariant.ts` 的 `install`——`if (previous === status) fail(...)`。
- 范围：仅当加载 `@deepseek-ai/dsh-agent/invariant` companion 插件时生效（README 明确“The root agent service does not load diagnostics implicitly”）。

## 4. 设计特点与取舍
- **接口/实现解耦**：`Agent` 接口与 `agent/*` 事件在 `dsh-agent` 声明，loop 通过 `setFactory` 注入，消费者不依赖具体 loop 包（README、`src/index.ts` 的 `AgentFactory` 注释）。
- **进程内 initiator 作用域**：用 `AsyncLocalStorage` 传递因果 initiator，但明确“ambient presence is neither liveness proof nor authorization”，跨进程/worker/HTTP 边界必须显式传递身份（README Known Limitations）。
- **disposer 是 capability**：`AgentHandle.dispose()` 只有持有者能调用；`ctx.agents.get(id)` 只返回裸 `Agent`（`src/index.ts` 的 `AgentHandle` 注释）。
- **持久化事件为唯一事实源**：turn/step/模型 token 流是 `session/event`，不镜像为 `agent/*` 通知；inbox 只发 per-message 的最小通知（README）。
- **通知不否决、waterfall 可否决**：emit 模式逐 listener 捕获失败；`agent/pre-step`/`agent/request`/`agent/request-error` 是 waterfall，可拒绝/替换/重试（`src/runtime-types.ts` 事件注释）。
- **明确取舍**：`cancel()` 默认清空 inbox（`keepInbox` 可保留）；`agent/session-start` 不能 gate 启动（同步、无否决）；每个 `UserMessage` 只带一个 `MessageSource`；`SessionStartSource` 的 `'clear'`/`'compact'` 尚无 emitter（README Known Limitations）。

## 行为 vs 项目叙述 对照结果

共5个函数：0个违反不变量、0个无法判断、5个支撑项目正确运行（不再展开）

### 支撑项目正确运行（5个，不再展开）

src\consumed-work.ts::accountsForClaim、src\dispatch.ts::(anonymous)、src\inbox.ts::locate、src\inbox.ts::constructor、src\index.ts::return


## 复杂度分级分布

- [A] 261个函数/类
- [B] 3个函数/类
- [C] 1个函数/类
- [D] 1个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [D] src\inbox.ts :: locate（第149行）复杂度=26
  [C] src\consumed-work.ts :: accountsForClaim（第42行）复杂度=19
  [B] src\dispatch.ts :: (anonymous)（第18行）复杂度=6
  [B] src\inbox.ts :: constructor（第28行）复杂度=6
  [B] src\index.ts :: return（第626行）复杂度=6
  [A] src\dispatch.ts :: emit（第120行）复杂度=4
  [A] src\index.ts :: (anonymous)（第373行）复杂度=4
  [A] tests\agent.spec.ts :: calls（第415行）复杂度=4
  [A] src\inbox.ts :: claim（第71行）复杂度=3
  [A] src\index.ts :: (anonymous)（第289行）复杂度=3
  [A] src\index.ts :: detach（第494行）复杂度=3
  [A] src\index.ts :: (anonymous)（第474行）复杂度=3
  [A] src\model-selection.ts :: (anonymous)（第56行）复杂度=3
  [A] tests\agent.spec.ts :: (anonymous)（第377行）复杂度=3
  [A] src\dispatch.ts :: (anonymous)（第29行）复杂度=2

## 行为描述明细（B级以上，共5个）

### [C] src\consumed-work.ts :: accountsForClaim（第42行，复杂度19）

函数 `accountsForClaim` 是 `src/consumed-work.ts` 里的一个私有辅助函数（非导出），其契约如下：

**输入**：一个 `TurnEndReason` 对象（`reason`），即 `turn/end` 事件的 `data.reason`。

**输出**：一个布尔值——`true` 表示该结束方式“为输入负责”（即该 turn 消费了输入但未进入 step，其结束方式仍算作对输入负责）；`false` 表示不负责。

**行为/副作用**：无副作用。纯函数，不修改任何外部状态、文件或全局数据，只根据 `reason.kind` 做分支判断。

**前置条件**：调用方必须保证传入的 `reason` 是 `turn/end` 事件里真实的 `reason`（即 `reason.kind` 是 `TurnEndReasonMap` 中已命名的 kind 之一，或至少是合法的 `TurnEndReason`）。代码注释明确说明：`max-tokens` 这个唯一未命名的内置 kind 需要 step，其 turn 会在调用本函数之前就短路为 stepped，因此不会走到这里；而 `TurnEndReasonMap` 是可合并扩展的，后端可能新增变体，所以 `default` 分支对未命名/未知的 kind 返回 `true`。

**调用后保证**：
- 当 `reason.kind === 'completed'` 时返回 `false`（注释：completed 的 turn 在 claim 被重写掉之后没有剩余可运行内容，因此不负责）。
- 当 `reason.kind` 为 `'blocked'`、`'aborted'`、`'interrupted'`、`'error'` 时返回 `true`（注释：blocked 是 pre-step 拒绝，丢弃了 claimed 消息，所以它取走的工作永远不会运行，因此负责）。
- 对任何其他（未知/未命名）kind，`default` 分支返回 `true`（注释：一个无法命名的、消费了输入的结束方式绝不能读作成功）。

**调用位置**：在 `foldConsumedWork` 的 `turn/end` 分支中调用：`if (stepped.delete(turn) || (claimed.delete(turn) && accountsForClaim(reason)))`。即仅当该 turn 未进入 step（不在 `stepped` 中）且确实 claim 过输入（在 `claimed` 中）时，才用 `accountsForClaim` 判断该结束方式是否算作对输入负责；若负责，则把该 `turn/end` 事件记为 `end` 并重置 `droppedUnrun`。

【调用方须知】最容易忽略的是：`accountsForClaim` 对**未知/未命名的 `reason.kind` 一律返回 `true`**（`default` 分支），而不是报错或返回 `false`——这意味着如果后端新增了一个未在 `TurnEndReasonMap` 中列出的结束 kind，且该 turn 消费了输入但未进入 step，`foldConsumedWork` 会把它当作“对输入负责”的结束，从而把该 `turn/end` 记为 `end` 并清除 `droppedUnrun`。调用方若依赖 `droppedUnrun` 来判定“是否有工作被未运行地丢弃”，必须意识到：任何未知结束方式都会被当作负责处理，不会留下 `droppedUnrun` 标记。

*✓ 核实通过——候选答案对函数契约的描述与代码原文完全吻合，包括输入输出、无副作用、前置条件（reason为turn/end的reason）以及default分支对未知kind返回true的行为，调用方须知也准确指出了这一易忽略点。*

### [B] src\dispatch.ts :: (anonymous)（第18行，复杂度6）

第18行的「(anonymous)」是 `agentEvents` 函数内部定义的 `fused` 箭头函数（`const fused = <K extends AgentSubjectEvent>(payload: PayloadRest<K>): PayloadOf<K> => ...`），它被 `emit`/`serial`/`waterfall` 三个方法共用。

**契约（依据代码原文）**：
1. **输入**：一个 `PayloadRest<K>` 类型的 payload 对象（即事件 payload 去掉 `agent` 字段后的剩余字段）。原文：`const fused = <K extends AgentSubjectEvent>(payload: PayloadRest<K>): PayloadOf<K> =>`。
2. **输出**：一个 `PayloadOf<K>` 类型的完整 payload 对象——即把 `agent` 注入进去后的完整 payload。原文：`({ ...payload, agent } as PayloadOf<K>)`。
3. **副作用**：无外部副作用。它只构造并返回一个新对象，不修改传入的 `payload`（用展开运算符 `...payload` 复制），不写文件、不改全局、不触发事件。它只是纯函数式地把 `agent` 字段合并进 payload。
4. **前置条件**：调用方（即 `emit`/`serial`/`waterfall` 内部）必须已经持有 `agent` 变量（来自 `agentEvents` 的参数），且 `payload` 是合法的 `PayloadRest<K>`。
5. **调用后保证**：返回的对象中 `agent` 字段一定等于 `agentEvents` 传入的 `agent`，且该字段在展开之后注入，所以即使调用方传入的 payload 里意外带了 `agent` 字段，也无法覆盖注入的 subject。原文注释明确说明：`The spread comes first, so a structurally acceptable payload that happens to carry an agent field can never override the injected subject.`

【调用方须知】这个 `fused` 函数是 `agentEvents` 内部闭包，调用方无法直接调用它；但它的行为决定了 `emit`/`serial`/`waterfall` 的 payload 处理——最该警惕的是：**调用方传给这三个方法的 payload 里如果带了 `agent` 字段，会被静默丢弃/覆盖，注入的是 `agentEvents` 构造时传入的 `agent`**。也就是说，你无法通过 payload 指定一个不同的 agent 来“冒充”另一个 subject——scope key 和 payload 的 `agent` 永远绑定为构造时的那个 agent，这是设计上防止 subject 与 scope 不一致的机制，不是 bug。如果你试图传一个不同的 `agent` 字段，它会被忽略，事件仍以构造时的 agent 为 subject 派发。

*✓ 核实通过——逐条核对了代码原文，候选答案对函数签名、行为、副作用和前置条件的描述均与源码相符，且调用方须知准确指出了 payload 中 agent 字段会被静默覆盖的关键行为。*

### [D] src\inbox.ts :: locate（第149行，复杂度26）

【locate 契约】

**定义位置**：`src/inbox.ts` 第 149-155 行，是 `Inbox` 类的私有方法。

**输入**：
- 参数 `messageId: MessageId`（第 149 行）——一个消息身份标识。

**输出**：
- 返回 `{ target: InboxTarget; index: number } | undefined`（第 149 行）。
- 若在 `next-turn` 或 `next-step` 两个列表中找到了 `message.id === messageId` 的消息，返回该消息所在列表（`target`）及其下标（`index`）；否则返回 `undefined`。

**副作用**：
- **无副作用**。`locate` 只读 `this.state`（第 151 行 `this.state[target].findIndex(...)`），不修改任何状态、不 append 事件、不发布通知。它是纯查询函数。

**前置条件**：
- 调用方必须是 `Inbox` 类内部（它是 `private`，第 149 行），外部无法直接调用。
- 无其他前置条件；`this.state` 已由构造函数初始化（第 18 行）。

**调用后保证**：
- 若返回对象，则 `this.state[target][index].id === messageId` 成立（由 `findIndex` 的谓词保证，第 151 行）。
- 若返回 `undefined`，则两个列表中都不存在该 `messageId`。
- 不改变任何状态，调用前后 `this.state` 完全一致。

**调用方（类内方法）**：`replace`（第 128 行）和 `remove`（第 139 行）都先调用 `locate`，若返回 `undefined` 则直接返回 `false`，否则用返回的 `target`/`index` 调用 `splice`。

【调用方须知】`locate` 只按 `message.id` 精确匹配（第 151 行 `message.id === messageId`），它**不**做任何归一化或模糊匹配——如果调用方传入的 `messageId` 与待查消息的 `id` 在格式/大小写/类型上不完全一致（例如数字与字符串、或带/不带前缀的 ID），即使语义上指向同一条消息，`locate` 也会返回 `undefined`，导致 `replace`/`remove` 静默返回 `false` 而不做任何修改。调用方必须保证传入的 `messageId` 与消息的 `id` 严格相等，否则会误判为“消息不存在”。

*✓ 核实通过——候选答案对locate的输入、输出、无副作用、前置条件（private）及调用方（replace/remove）的描述均与代码原文一致，且调用方须知关于严格相等匹配的警告准确。*

### [B] src\inbox.ts :: constructor（第28行，复杂度6）

【constructor 契约】

**输入**（第28-30行）：
```ts
constructor(
  private readonly session: Session,
  private readonly notifications: InboxNotifications,
)
```
- 必须传入一个 `Session` 对象（`session`）和一个 `InboxNotifications` 对象（`notifications`）。

**行为/副作用**（第31-39行）：
```ts
for (const event of session.events.slice(session.header.seedLength ?? 0)) {
  if (event.type !== 'agent/inbox/spliced') continue
  try {
    this.apply(event.data)
  } catch (error: unknown) {
    throw new Error(`invalid persisted inbox splice at session seq ${event.seq}`, { cause: error })
  }
}
```
- 构造时**立即重放** session 中从 `seedLength`（若未定义则从 0）开始的所有历史事件，只处理 `agent/inbox/spliced` 类型的事件，把每个事件的数据通过 `this.apply(event.data)` 应用到内部 `state`（`next-turn`/`next-step` 两个数组）。
- 副作用：**修改了实例自身的私有状态** `this.state`（第13行 `private readonly state: InboxState = { 'next-turn': [], 'next-step': [] }`），把持久化的 inbox splice 事件投影到内存中的待处理消息列表。
- 若某个 splice 事件数据非法（`apply` 内部调用 `validate` 抛错），构造函数会**抛出** `Error('invalid persisted inbox splice at session seq ...')`，并带上原始错误作为 `cause`。

**前置条件**：
- 传入的 `session` 必须已经具备 `events` 数组和 `header.seedLength` 字段（`session.events.slice(...)` 和 `session.header.seedLength` 可访问）。
- 传入的 `session` 中已有的 `agent/inbox/spliced` 事件数据必须符合 `validate` 的约束（start 为非负安全整数、removedCount 非负、start+removedCount ≤ 列表长度、且插入后不产生重复 message id），否则构造会抛错。

**输出/调用后保证**：
- 构造完成后，`this.state['next-turn']` 和 `this.state['next-step']` 已按持久化事件顺序重建，可通过 `nextTurn`/`nextStep` getter（第42-51行）读取。
- 构造函数本身**不发布任何通知**（不调用 `notifications` 的任何方法），也不修改 session（只读 `session.events`）。

【调用方须知】构造函数会**同步重放并校验 session 中所有历史 `agent/inbox/spliced` 事件**——如果 session 里存在任何一条非法 splice（坐标越界或消息 id 重复），构造会直接抛错，导致整个 Inbox 实例无法创建；调用方在构造前应确保 session 的 inbox 事件数据是干净合法的，否则会得到一个构造即失败的实例。

*✓ 核实通过——逐行核对代码，候选答案对输入、重放行为、副作用、前置条件和错误抛出的描述均与源码一致，且引用的行号和代码片段准确。*

### [B] src\index.ts :: return（第626行，复杂度6）

在 src/index.ts 中，第626行的函数是 `roots()`（位于 `AgentRegistry` 类内，第626-632行）。它的契约如下：

**输入**：无参数。

**输出**：返回一个 `Agent[]` 数组，包含所有“顶层”实时 agent（即 `owner === undefined` 的 agent），按注册顺序排列。返回的是新数组（`[...this.store.values()]` 创建新数组），修改它不影响注册表。

**副作用**：无。它只读取 `this.store`，不修改任何外部状态、文件或全局数据。

**前置条件**：无显式前置条件。它不检查 `initiatorState`，也不依赖工厂注册。它只要求 `this.store` 存在（即 `AgentRegistry` 实例已构造）。

**调用后保证**：返回的数组是快照，修改它不会影响注册表；数组中的 agent 对象是实时引用（不是副本），因此通过返回的 agent 修改其状态会影响注册表中的 agent。

**代码依据**：
- 函数体：`return [...this.store.values()].filter(entry => entry.owner === undefined).map(entry => entry.agent)`（第627-631行）
- docstring："All live top-level agents in registration order. A top-level agent was created without an owning agent context; durable session lineage does not affect this runtime relation, so a resumed fork may still be a root."（第620-624行）
- docstring："@returns a fresh array; mutating it does not affect the registry."（第625行）

【调用方须知】最容易被忽略的是：`roots()` 返回的数组是新的，但数组中的 `Agent` 对象是注册表中的实时引用——调用方如果修改返回的 agent 对象（例如调用其方法改变其状态），会直接影响注册表中的 agent，尽管修改数组本身（如 push/pop）不会影响注册表。

*✓ 核实通过——候选答案准确描述了 `roots()` 的输入（无参数）、输出（返回新数组，包含 `owner === undefined` 的 agent，按注册顺序）、副作用（无，只读 `this.store`）、前置条件（无显式条件，仅需实例已构造）以及调用后保证（数组是快照，但 agent 对象是实时引用）。所有描述均与代码原文和 docstring 一致。*


### 批次「agent-default-model」

# 项目体检报告

共4个文件（另有0个不支持的文件类型被跳过），总行数260

## 项目叙述（✓ 核实通过）

这个代码库是 @deepseek-ai/dsh-agent-default-model，一个 Cordis 插件包，为 Agent 提供默认模型选择。它解决的问题是：当入口点（如 CLI 的 `dsh --profile headless` 或 Host 的 ApiProxy）创建 Agent 且没有会话级模型选择时，需要一个统一的部署默认值，避免各入口各自维护 provider/model 默认值。

模块组成：
- src/index.ts：核心服务 `AgentDefaultModelConfig`，注册为 `ctx.agentDefaultModel`。职责：持有默认选择（composition entry 或 settings 层的用户选择），提供 `currentSelection()` 读取、`saveSelection()` 保存。
- src/invariant.ts：空的 invariant 安装器，明确声明本包不拥有独立的不变量关系（settings 校验已覆盖所有可变值）。

关键不变量（含证据范围）：
1. 默认选择必须始终有 provider 和 model（必填）。证据：src/index.ts 中 `AgentDefaultModelConfig.Config` 和 `AGENT_DEFAULT_MODEL_SETTINGS_SCHEMA` 都用 `z.string().required()` 强制 provider/model 必填；`selection()` 函数总是返回 provider/model。
2. `currentSelection()` 返回的是分离（detached）的选择，且每次读取都从当前 source 实时解析，不缓存。证据：src/index.ts 中 `currentSelection()` 调用 `selection(this.source())`，`source` 是函数；`onChange` 为空，注释明确“Every consumer reads through currentSelection()”。
3. `saveSelection()` 在无 settings provider 时是 no-op，composition entry 保持有效。证据：src/index.ts 中 `saveSelection()` 用 `this.ctx.get('settings')?.replace(...)`，可选链保证无 provider 时不写入；README.md 明确“Without a settings provider it is a no-op and the composition entry remains current”。
4. `reasoningEffort` 只属于 Settings 层，不属于 plugin config。证据：src/index.ts 中 `Config` 只有 provider/model，而 `AgentDefaultModelSettings` 有可选 reasoningEffort；README.md 说明这是刻意取舍（composition 值会被继承，无法清除）。
5. 服务不校验 catalog 成员资格，provider 路由可能服务未广告的模型，可用性诊断由实际打开模型请求的消费者负责。证据：README.md 明确“The service does not validate catalog membership”。
6. 修改默认只影响后续从它解析的 Agent，已有会话保留其请求日志中已命名的选择，不失效既有前缀。证据：README.md 的 KV Cache effect 段落。

注意：以上不变量均来自单一入口（`currentSelection()`/`saveSelection()` 两个方法），没有多个同类入口需要逐一核对。invariant.ts 明确声明本包不注册任何运行时不变量，因此不变量检查应聚焦于 settings 校验和上述方法行为。

设计特点/取舍：
- 服务独立于任何 Host 或 transport，composition entry 在无 settings provider 时仍可用。
- 读取实时（live）而非缓存，settings 文档变化立即反映到下次读取。
- 刻意将 reasoningEffort 排除在 plugin config 之外，以支持“清除 effort”的场景。
- 不校验模型目录成员资格，把可用性诊断下放给实际消费者。
- 进程级单一默认，per-session 选择由入口点负责（README 的 Known Limitations）。

## 行为 vs 项目叙述 对照结果

共0个函数：0个违反不变量、0个无法判断、0个支撑项目正确运行（不再展开）


## 复杂度分级分布

- [A] 19个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [A] src\index.ts :: saveSelection（第98行）复杂度=3
  [A] src\index.ts :: selection（第49行）复杂度=2
  [A] src\index.ts :: source（第70行）复杂度=1
  [A] src\index.ts :: this.source（第75行）复杂度=1
  [A] src\index.ts :: setSource（第77行）复杂度=1
  [A] src\index.ts :: onChange（第80行）复杂度=1
  [A] src\index.ts :: constructor（第72行）复杂度=1
  [A] src\index.ts :: currentSelection（第88行）复杂度=1
  [A] src\invariant.ts :: install（第22行）复杂度=1
  [A] src\invariant.ts :: apply（第29行）复杂度=1
  [A] tests\agent-default-model.spec.ts :: load（第18行）复杂度=1
  [A] tests\agent-default-model.spec.ts :: persist（第22行）复杂度=1
  [A] tests\agent-default-model.spec.ts :: boot（第28行）复杂度=1
  [A] tests\agent-default-model.spec.ts :: (anonymous)（第44行）复杂度=1
  [A] tests\agent-default-model.spec.ts :: (anonymous)（第59行）复杂度=1

## 行为描述明细（B级以上，共0个）


### 批次「agent-loop」

# 项目体检报告

共27个文件（另有0个不支持的文件类型被跳过），总行数12211

## 项目叙述（✓ 核实通过）

项目定位描述（依据：src/agent.ts、src/index.ts、src/tool-calls.ts、src/runtime-context.ts、src/invariant.ts、README.md）

## 1. 项目是什么
`dsh-agent-loop` 是 DeepSeek 智能体框架（harness）中唯一包含具体循环逻辑的包：它实现 `Agent` 接口，驱动 session/turn/step 生命周期，是“调用模型→运行工具→重复”这一核心循环的具体驱动。面向的是框架内的智能体运行场景，解决“如何把一次会话拆成多个 turn、每个 turn 拆成多个 step、每个 step 调用一次 LLM 并执行工具调用”的问题。其余包都是抽象服务或插件扩展点，新行为应进插件，不进本包。

## 2. 模块组成与职责边界
- **src/index.ts**（`AgentLoop` 服务，实现 `AgentFactory`）：创建/恢复 agent 的入口。负责：配置校验（`validateConfiguredAgents`、`resolveMaxParallelToolCalls`、`assertAgentOptions`）、会话准备（`SessionPreparation`）、`prepare()` 构造驱动+scope+反向 teardown、`publish()` 进入注册表并广播事件、`create`/`createAgent`/`resume`/`resumeWith` 各入口、工厂级所有权（`FactoryOwnership`）与 teardown 收敛。
- **src/agent.ts**（`ReactLoopAgent`）：具体驱动。负责 turn/step 边界、inbox 的 send/followup/steer/inject、cancel、`preStep` 的 claim 与 `agent/pre-step` waterfall、`step()` 的 LLM 流式调用与工具执行、`buildRequest()` 的请求组装与 request/header 记录。
- **src/tool-calls.ts**（`executeToolCalls`）：调度一个 step 的工具调用。负责独占调用形成 barrier、并行调用用有界滚动池、模型序提交结果、abort 时给未派发调用补合成错误结果。
- **src/runtime-context.ts**（`RuntimeContextProjection`）：动态运行时上下文的持久投影状态，跟踪最后保留的 runtime-context 快照。
- **src/invariant.ts**：可选的 invariant 伴生插件，注册请求重建检查（`llm/stream` 监听，校验请求冻结、session 存活、消息与 header 与日志重建一致）。
- **src/constants.ts**：`DEFAULT_MAX_PARALLEL_TOOL_CALLS = 10`。

## 3. 关键不变量（每条附证据范围）

### 3.1 每个成功完成的 provider 调用恰好追加一个 `assistant/message` 完成锚点
- 证据：`src/agent.ts` `step()` 中，流结束后 `this.session.append('assistant/message', {...}, { surfaceOp: 'append', sourceEventSeqs: chunkSeqs })`，且 `finish.kind === 'max-tokens'` 时也走同一 append（`if (finish.kind === 'max-tokens') return { kind: 'max-tokens' }` 在 append 之后）。README 明确“Every provider call that reaches a successful finish appends exactly one assistant/message completion anchor, including content-less calls and max-tokens finishes”。
- 覆盖入口：`step()` 是唯一执行 LLM 流的地方（`buildRequest` 只组装请求，不 append 完成锚点）。

### 3.2 每个 step 的 `user/message` 追加发生在 `step/start` 之后、`step/end` 之前，且 `step/end` 一定在 `step/start` 之后
- 证据：`src/agent.ts` `turn()` 中 `this.session.append('step/start', { turn, step })` → `for (message of decision.messages) this.session.append('user/message', ...)` → `await this.step(...)` → `finally { this.session.append('step/end', { turn, step }) }`。
- 覆盖入口：`turn()` 是唯一打开 step 的地方。

### 3.3 每个 turn 一定有 `turn/start` 和 `turn/end`，且 `turn/end` 的 reason 在正常/错误/取消/处置下分别记录
- 证据：`src/agent.ts` `turn()` 开头 `this.session.append('turn/start', { turn })`，`finally` 块 `this.session.append('turn/end', { turn, reason: turnEnds! })`。reason 取值：正常完成 `{kind:'completed'}`、max-tokens `{kind:'max-tokens'}`、拒绝 `{kind:'blocked'}`、abort `{kind:'aborted', reason}`、错误 `{kind:'error', error}`。README 补充：`user`/`parent` 取消记录 `aborted`，处置记录 `disposed`。
- 覆盖入口：`turn()` 是唯一打开/关闭 turn 的地方。

### 3.4 工具调用结果按模型序提交，且每个 `tool/result` 引用其 `tool/call` 的 seq
- 证据：`src/tool-calls.ts` `commitReady()` 中 `appendToolResult(session, turn, step, call.block, result, callSeqs[committed]!)`，`callSeqs` 在 `startCall()` 里由 `appendToolCall` 返回的 seq 填充；`commitReady` 只推进连续模型序槽位（`while (committed < group.length)` 且 `slots[committed] === undefined` 时 break）。README 明确“Policy, durable results, and result context remain model-ordered”。
- 覆盖入口：`executeToolCalls`/`runGroup` 是唯一提交工具结果的地方。

### 3.5 取消（abort）时，未派发的工具调用获得合成错误结果 `ABORTED_BEFORE_DISPATCH`，且已派发调用的结果仍被提交
- 证据：`src/tool-calls.ts` `runGroup()` 中 `if (aborted) { for (const call of group.slice(started)) appendSkippedToolCall(...); return { consumed: group.length, aborted: true, concluded } }`；`appendSkippedToolCall` 写入 `tool/call` + `tool/result`（error code `TOOL_ABORTED_BEFORE_DISPATCH`，文本 `Error: tool call aborted before dispatch`）。README 的“Undispatched calls after cancellation”一节确认。
- 覆盖入口：`executeToolCalls`/`runGroup` 是唯一处理工具取消的地方。

### 3.6 每个 `agent/inbox/*` 事件在修改 live 投影前发出，且 `MessageId` 在 pending 列表中唯一
- 证据：`src/agent.ts` 构造函数中 `new Inbox(session, { inserted/discarded/claimed 回调 })`，回调在 `this.inbox.splice(...)` 之前注册；README 明确“Every inbox mutation publishes one normalized agent/inbox/spliced event before changing the live projection”和“MessageId stays unique across both pending lists”。
- 覆盖入口：`send()`（followup/steer/inject 都走它）是唯一 inbox 修改入口。

### 3.7 请求 header 只在首次或变化时记录，且 `request/header` 与 `request/context` 的追加条件明确
- 证据：`src/agent.ts` `buildRequest()` 中 `if (!this.requestHeaderLogged) { append('request/header', { reason: 'initial'|'resume' }) } else if (baseline === undefined || !headerEquals(baseline, header)) { append('request/header', { reason: 'change' }) }`；`request/context` 仅在 provider/model/contextWindow 变化时追加。
- 覆盖入口：`buildRequest()` 是唯一记录 header/context 的地方。

### 3.8 每个成功 step 的请求是冻结的，且携带 session id
- 证据：`src/agent.ts` `buildRequest()` 中 `markAgentLoopRequest(deepFreeze({...}))`；`src/invariant.ts` 检查 `Object.isFrozen(options)`、`options.sessionId !== undefined`、`Object.isFrozen(options.messages)`。
- 覆盖入口：`buildRequest()` 是唯一构造请求的地方；invariant 检查覆盖所有 `llm/stream` 监听（`global: true, prepend: true`）。

### 3.9 同一 session id 的并发操作：最终 `enter()` 仲裁发布，失败者回滚私有资源
- 证据：`src/index.ts` `prepare()` 中 `publish()` 调用 `agent.ctx.sessions.enter(session)` 和 `loopCtx.agents.enter(agent, ownerCtx.agent)`；README 明确“Two concurrent operations with the same id may both prepare, but the final enter() calls arbitrate publication and every loser rolls its private resources back”。
- 覆盖入口：`create`/`createAgent`/`resume`/`resumeWith` 都经 `prepare()`。

### 3.10 配置校验：`sessionId` 与 `resumeSessionId` 互斥，重复精确身份被拒绝
- 证据：`src/index.ts` `validateConfiguredAgents()` 中 `if (sessionId !== undefined && hasResumeId) throw ...` 和 `if (firstId !== undefined) throw ... duplicate exact session identity`。
- 覆盖入口：`AgentLoop` 构造函数调用 `validateConfiguredAgents(this.config.agents)`，覆盖所有配置驱动的 agent 启动。

### 3.11 `maxParallelToolCalls` 必须是正整数，非法值在写入时被拒绝
- 证据：`src/index.ts` `resolveMaxParallelToolCalls()` 中 `if (!Number.isInteger(maxParallelToolCalls) || maxParallelToolCalls < 1) throw`；settings 的 `validate` 回调也调用它。README 明确“a value that is not a positive integer is refused at the write rather than at that group”。
- 覆盖入口：构造函数和 settings 写入两个入口都校验。

### 3.12 每个 agent 的 teardown 顺序固定：stop+drain → unwind scope → detach agent → detach session
- 证据：`src/index.ts` `prepare()` 的 `dispose()` 中 `machine.cancel({kind:'disposed'})` → `await machine.whenIdle()` → `await machine.scope.dispose()` → `detachAgent?.()` → `detachSession?.()`。README 明确“Teardown runs stop and drain → unwind scope → detach agent → detach session”。
- 覆盖入口：`dispose()` 是唯一 teardown 路径，被 `create`/`createAgent`/`resume`/`resumeWith` 和工厂 dispose 共享。

### 3.13 运行时上下文快照只在变化时生成，且被替换时清除
- 证据：`src/runtime-context.ts` `project()` 中 `if (this.retained?.text === snapshot) return`；`session/event` 监听中 `isReplacementSurfaceEvent(event) && event.sourceEventSeqs?.includes(this.retained.seq)` 时 `this.retained = null`。
- 覆盖入口：`RuntimeContextProjection` 是唯一管理该投影的地方。

### 3.14 未覆盖/需注意的范围限制
- **`agent/request` 的 provider/model 缺失时抛错**：`buildRequest()` 中 `if (!proposedConfig.provider || !proposedConfig.model) throw`。这是 `buildRequest()` 内部规则，但 README 提到 `agent/request` 可能补全缺失对，所以此规则只在 `agent/request` waterfall 未补全时成立。
- **`resume` 需要 persistence 后端**：`src/index.ts` `resume()` 中 `if (persistence === undefined) throw new Error('cannot resume: session persistence is not configured')`。这是 `resume()` 入口的规则，`create`/`createAgent` 不要求。
- **`sessionId` 与 `resumeSessionId` 互斥**：只在配置校验（`validateConfiguredAgents`）中观察到；程序化 `createAgent`/`resume` 的 `CreateAgentOptions`/`ResumeAgentOptions` 类型层面未在源码中看到同样的显式校验（`createAgent` 只传 `options.sessionId`，`resume` 只传 `options.resumeSessionId`，二者天然分离）。

## 4. 设计特点与取舍
- **单一具体驱动，其余皆插件**：README 明确“This is the only package in the harness that contains concrete loop logic”，新行为进插件，本包只保留核心循环。
- **所有权融合**：`prepare()` 把 caller 取消、owner fiber 卸载、工厂 teardown 三个 owner 融合到一个 memoized `dispose()`，保证“无 continuation 在依赖消失后发布”。
- **模型序 vs 派发重叠**：工具调用只允许 dispatch/body 重叠，policy/结果/上下文保持模型序（`tool-calls.ts` 注释）。
- **取消语义**：取消改变报告方式，不改变已取消结果上下文的处理；未派发调用补合成错误结果以保持 replay 有效。
- **max-tokens 粘性**：一旦某 step 达 max-tokens，后续正常完成的 step 不得降级 turn 结果（`turn()` 中 `if (turnEnds === null || turnEnds.kind !== 'max-tokens') turnEnds = stepEnd`）。
- **配置标签默认新建**：省略 `sessionId` 每次启动新建 `${id}-session-<uuid>`；精确 resume-or-create 需显式 `sessionId`，`resumeSessionId` 需已有持久化历史。
- **无内置 turn 预算**：README 明确“No built-in turn budget”，需从 `agent/turn-stopping` 等扩展点自行取消。
- **分类是单目**：依赖比较兄弟/资源的调用必须保持独占（README“Classification is unary”）。

## 行为 vs 项目叙述 对照结果

共22个函数：0个违反不变量、2个无法判断、20个支撑项目正确运行（不再展开）

### 无法判断（2个——不代表没问题，只是材料不够判断，值得人工看一眼）

- tests\loop.spec.ts :: (anonymous) —— 行为契约描述为空，未提供任何函数行为细节，无法对照项目定位描述中的不变量进行判断。
- tests\request-reconstruction.spec.ts :: (anonymous) —— 行为描述是测试用例，未涉及项目定位描述中列出的任何关键不变量（如3.1-3.13），且测试副作用未覆盖这些不变量的具体细节，材料不足以判断。

### 支撑项目正确运行（20个，不再展开）

src\agent.ts::step、src\agent.ts::turn、src\agent.ts::get status、src\agent.ts::kick、src\index.ts::constructor、src\index.ts::validateConfiguredAgents、src\invariant.ts::(anonymous)、src\runtime-context.ts::(anonymous)、src\runtime-context.ts::constructor、src\runtime-context.ts::project、src\tool-calls.ts::commitReady、src\tool-calls.ts::fillPool、src\tool-calls.ts::startCall、tests\cancel.spec.ts::(anonymous)、tests\interception.spec.ts::(anonymous)、tests\loop.spec.ts::(anonymous)、tests\loop.spec.ts::(anonymous)、tests\loop.spec.ts::(anonymous)、tests\request-reconstruction.spec.ts::(anonymous)、tests\tool-calls.spec.ts::(anonymous)


## 复杂度分级分布

- [A] 1582个函数/类
- [B] 17个函数/类
- [C] 3个函数/类
- [D] 1个函数/类
- [E] 1个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [E] src\agent.ts :: step（第332行）复杂度=40
  [D] src\agent.ts :: turn（第246行）复杂度=21
  [C] src\invariant.ts :: (anonymous)（第21行）复杂度=19
  [C] tests\cancel.spec.ts :: (anonymous)（第774行）复杂度=14
  [C] src\agent.ts :: get status（第99行）复杂度=12
  [B] src\index.ts :: constructor（第319行）复杂度=10
  [B] tests\interception.spec.ts :: (anonymous)（第257行）复杂度=10
  [B] tests\loop.spec.ts :: (anonymous)（第413行）复杂度=9
  [B] src\index.ts :: validateConfiguredAgents（第278行）复杂度=8
  [B] src\tool-calls.ts :: commitReady（第146行）复杂度=8
  [B] src\tool-calls.ts :: fillPool（第198行）复杂度=8
  [B] src\runtime-context.ts :: (anonymous)（第46行）复杂度=7
  [B] src\runtime-context.ts :: constructor（第34行）复杂度=7
  [B] tests\request-reconstruction.spec.ts :: (anonymous)（第590行）复杂度=7
  [B] src\agent.ts :: kick（第210行）复杂度=6

## 行为描述明细（B级以上，共22个）

### [E] src\agent.ts :: step（第332行，复杂度40）

【调用方须知】step() 是 ReactLoopAgent 的私有方法，只被 turn() 调用，调用前必须满足 this.phase.kind === 'running'（第333行显式断言，否则抛错 `agent "${this.id}": step outside running phase`），且 phase 里必须有 turn、step、abort.signal 三个字段（第334行解构）。

输入：一个 PromptAssembly 对象（assembly），内部通过 this.buildRequest(turn, step, assembly.tools, system, this.session.deriveMessages(), signal) 构造请求（第338行），其中 system = renderPrompt(assembly)（第336行）。

输出：Promise<StepEndReason | null>，StepEndReason 是 {kind:'completed'|'max-tokens'} 的联合（第37行）。返回 null 表示本 step 内执行了工具调用但未得出结论（第414行 `return concluded ? { kind: 'completed' } : null`），需要继续循环；返回 {kind:'completed'} 表示没有工具调用（第410行）或工具调用已得出结论；返回 {kind:'max-tokens'} 表示达到 max-tokens 上限（第407行）。

副作用（改外部状态）：
1. 通过 this.session.append 写入会话日志：每个 chunk 追加 'assistant/chunk' 事件（第346行），最终追加 'assistant/message' 事件（第389-396行），并带 surfaceOp:'append' 和 sourceEventSeqs: chunkSeqs。
2. 通过 executeToolCalls 执行工具调用，并把产生的上下文通过回调 `context => this.inbox.splice('next-step', this.inbox.nextStep.length, 0, [context])` 插入到 inbox 的 next-step 队列（第412-413行）。
3. 可能触发 dispatch.waterfall('agent/request-error', ...) 事件（第352-360行），当流 finish 是 error/aborted 时。

前置条件：
1. this.phase.kind === 'running'（第333行）。
2. signal 未中止（第335行 signal.throwIfAborted()，以及循环内多处 throwIfAborted）。
3. 调用方（turn()）已先 append 'step/start' 事件并设置 phase.step（见 turn() 中第229-231行）。

调用后保证：
1. 若正常返回，会话中已追加了 assistant/chunk 和 assistant/message 事件；若返回 null，则 inbox 的 next-step 队列中已插入了工具调用产生的上下文。
2. 若流出错且非 retry，会 throw LlmError（第366行），不会返回。
3. 若 signal 中止，会在循环内 throw（signal.throwIfAborted()），不会返回。

【调用方须知】step() 内部是一个 while(true) 循环，一次调用可能执行多轮『请求→流式接收→工具调用』，直到没有工具调用、达到 max-tokens、或工具调用得出结论才返回；因此一次 step() 调用可能多次调用 buildRequest 并多次 append assistant/chunk 和 assistant/message 事件，且每次工具调用产生的上下文都会被 splice 进 inbox 的 next-step 队列——调用方（turn()）在 step() 返回 null 后必须继续循环（turn() 中第236行 `const stepEnd = await this.step(...)` 后继续 while），否则这些已插入的 next-step 上下文会被遗漏。另外注意：step() 返回 null 时并不代表 turn 结束，只有返回非 null（completed/max-tokens）才表示本 step 结束，且 max-tokens 是粘性的（turn() 中第234-235行注释说明）。

*✓ 核实通过——逐条核对了候选答案引用的代码行和逻辑，所有关于前置条件、输入、输出、副作用和返回语义的描述都与源码一致，包括 while(true) 循环、多次 buildRequest/append、next-step 插入和 max-tokens 粘性等细节。*

### [D] src\agent.ts :: turn（第246行，复杂度21）

【turn 的契约】

**输入**：无显式参数。它依赖 `this.phase` 必须处于 `kind === 'running'` 状态（第247行 `if (this.phase.kind !== 'running')`），并读取 `phase.abort.signal`、`phase.turn`、`phase.step`、`this.inbox`、`this.session`、`this.dispatch`、`this.loopCtx`。

**输出**：`Promise<boolean>`。返回 `true` 表示本 turn 结束后 inbox 仍有待处理消息（第292行 `if (!this.inbox.hasPending) return false` 之后返回 `true`），调用方（`kick` 的 `while (await this.turn()) {}`）会继续下一轮 turn；返回 `false` 表示 turn 结束且无待处理消息（第259行 `return false`、第265行 `return false`、第291行 `return false`）。

**副作用（外部状态修改）**：
1. 修改 `this.phase`：`phase.turn = turn`（第255行）、`phase.step = step`（第270行）、`phase.abort = new AbortController()`（第293行）、`phase.wakeRequested = false`（第294行）、`phase.step = 0`（第295行）。
2. 追加 session 事件：`turn/start`（第252行）、`step/start`（第269行）、`user/message`（第273行）、`step/end`（第280行）、`turn/end`（第287行）。
3. 通过 `this.dispatch.serial('agent/turn-stopping', ...)` 触发事件（第283行）。
4. 通过 `this.step()` 内部会追加 `assistant/chunk`、`assistant/message`、`request/header`、`request/context` 等 session 事件，并可能执行工具调用（`executeToolCalls` 会向 inbox 的 `next-step` 插入上下文，见第330行 `context => this.inbox.splice('next-step', ...)`）。

**前置条件**：
1. `this.phase.kind === 'running'`（第247行，否则抛错）。
2. `phase.abort.signal` 未中止（第250行 `signal.throwIfAborted()`，以及循环内多处）。
3. 调用方（`kick`）已通过 `wakeDriver` 建立 running phase 并持有 driver 保留权（错误信息 'turn without driver reservation' 表明这一点）。

**调用后保证**：
1. 无论正常结束还是异常，都会在 `finally` 中追加 `turn/end` 事件，携带 `reason`（第287行）。
2. 若发生错误，会通过 `throwError` 发出 `agent/error` 事件并抛出（第258、265、289行）。
3. 若正常结束且 inbox 无待处理消息，返回 `false`；否则重置 abort controller 和 step 计数并返回 `true`。
4. 若被 abort，会抛出原错误（第286行 `throw error`），且 `turnEnds` 记为 `aborted`。

【调用方须知】turn 在正常结束（非 abort、非 error）时会把 `phase.abort` 替换成一个全新的 `AbortController`（第293行 `phase.abort = new AbortController()`），同时把 `phase.wakeRequested` 重置为 `false`、`phase.step` 重置为 `0`——这意味着任何在 turn 执行期间通过 `cancel()` 或 `send(wakeup=true)` 设置的 abort 信号或 wake 闩锁，在 turn 返回 `true` 后都会失效：旧 controller 的 abort 不再影响后续 step，而 wake 请求会被丢弃（除非 inbox 里还有 pending 消息，此时返回 `true` 让 `kick` 继续下一轮）。所以调用方不能依赖在 turn 运行中调用的 `cancel()` 来中止整个 driver 循环——它只中止当前 turn 内的 step，turn 结束后 driver 会带着新 controller 继续跑。若想彻底停止，必须在 turn 返回后（或通过 `disposed` 原因）另行处理。

*✓ 核实通过——候选答案逐条引用了代码原文，且所有关键行为（输入依赖、输出布尔值、副作用、前置条件、调用后保证）均与源码一致，特别是第293-295行的重置逻辑和返回true的条件。调用方须知也准确指出了abort controller被替换和wakeRequested重置的陷阱。*

### [C] src\agent.ts :: get status（第99行，复杂度12）

【get status 契约】

**输入**：无参数。

**输出**：返回 `AgentStatus` 类型值，具体为字符串 `'idle'` 或 `'running'`。

**副作用**：无。该 getter 只读取 `this.phase.kind`，不修改任何状态、不触发事件、不写文件。

**前置条件**：`this.phase` 必须已初始化（在构造函数中赋值）。

**调用后保证**：返回值为 `'idle'` 当且仅当 `this.phase.kind` 为 `'idle'` 或 `'maintenance'`；否则返回 `'running'`。

**代码原文依据**（src/agent.ts 第99-101行）：
```ts
get status(): AgentStatus {
  return this.phase.kind === 'idle' || this.phase.kind === 'maintenance' ? 'idle' : 'running'
}
```

【调用方须知】`status` 为 `'idle'` 并不代表 agent 完全空闲——`maintenance` 阶段（如正在处理唤醒请求）也会被归为 `'idle'`，因此调用方不能仅凭 `status === 'idle'` 就断定没有正在进行的活动，需另行检查 `phase.kind` 是否为 `'maintenance'`。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和返回逻辑的描述与代码原文完全一致，且调用方须知准确指出了 maintenance 阶段被归为 idle 这一易忽略行为。*

### [B] src\agent.ts :: kick（第210行，复杂度6）

【kick 契约】

**位置与签名**：`src/agent.ts` 第210-226行，`private async kick(): Promise<void>`，是 `ReactLoopAgent` 类的私有方法。

**输入**：无显式参数。它依赖实例状态：`this.phase`（必须为 `kind: 'running'` 的 phase）、`this.turn()`、`this.inbox`、`this.dispatch`、`this.setPhase`、`this.wakeDriver`。

**输出**：`Promise<void>`，不向调用方返回任何值。

**行为（依据代码原文）**：
- 循环调用 `while (await this.turn()) {}`（第212行），`turn()` 返回 `boolean`，为 `true` 时继续下一轮，直到返回 `false` 或抛错。
- `try/catch`：捕获所有错误并吞掉——注释明确写「Reported failures and cancellation are contained at the driver boundary.」（第214行），即错误不向外传播。
- `finally` 块（第216-224行）：
  - 若 `this.phase.kind === 'running'`，则 `const { turn, wakeRequested } = this.phase`，调用 `this.setPhase({ kind: 'idle', lastTurn: turn })`（第219-220行）——把 phase 从 running 切回 idle，并记录 `lastTurn`。
  - 若 `wakeRequested && this.inbox.hasPending`，则调用 `this.wakeDriver()`（第221-222行）——唤醒下一个 driver。

**副作用（外部状态变更）**：
1. **修改 phase 状态**：通过 `setPhase` 把 `this.phase` 从 `running` 改为 `idle`（第220行），`setPhase` 会发布 `agent/status` 事件（第73-79行）。
2. **可能触发 `wakeDriver()`**：当 `wakeRequested` 为真且 inbox 有 pending 消息时（第221-222行），`wakeDriver` 会启动新的 driver 循环（见第150-180行 `wakeDriver` 定义）。
3. **通过 `turn()` 间接产生大量副作用**：`turn()` 内部会 append session 事件（`turn/start`、`step/start`、`user/message`、`step/end`、`turn/end`）、调用 LLM、执行工具调用、emit 各种 dispatch 事件（`agent/pre-step`、`agent/request`、`agent/turn-stopping` 等）。这些都在 kick 的循环内发生。
4. **不直接修改文件或全局数据**，但会修改 session 日志（通过 `this.session.append`）和 inbox 状态（通过 `this.inbox.claim`、`splice`）。

**前置条件**：
- 调用方（`wakeDriver` 第180行 `this.loopCtx.agents.withInitiator(this, () => this.kick())`）必须先通过 `setPhase` 把 phase 设为 `running`（见第169-176行 `wakeDriver` 中 `this.setPhase({ kind: 'running', ... })`）。
- 调用前 `this.phase.kind` 必须是 `'running'`，否则 `turn()` 会抛错（第236-238行 `if (this.phase.kind !== 'running') this.throwError(...)`）。
- 调用前 `this.activityDone` 已被设置为一个 promise（第170行 `this.activityDone = driver.promise`），供 `whenIdle()` 等待。

**调用后保证**：
- 无论成功、失败还是取消，`finally` 保证 phase 最终回到 `idle`（第220行），除非 phase 在 kick 期间被外部改成非 running（但 `finally` 只检查 `kind === 'running'`，若已被改成其他状态则不重置）。
- 若 `wakeRequested` 且 inbox 有 pending，会触发 `wakeDriver()` 启动下一轮（第221-222行）。
- 错误被吞掉，不向调用方抛出（第213-215行 catch 空块）。

【调用方须知】kick 的 `finally` 块只在 `this.phase.kind === 'running'` 时才把 phase 重置为 idle 并检查 `wakeRequested`；如果 kick 执行期间外部代码（如 `cancel()` 或 `runMaintenance()`）已经把 phase 改成了非 running 状态，那么 kick 的 `finally` 不会做任何清理——它不会把 phase 改回 idle，也不会触发 `wakeDriver()`。因此调用方（`wakeDriver`）在 kick 返回后不能假设 phase 一定是 idle，必须自行检查 phase 状态；尤其当 kick 因取消而退出时，若 phase 已被外部改为 `maintenance`，kick 的清理逻辑会被完全跳过，`wakeRequested` 的 latch 也不会被处理。

*✓ 核实通过——候选答案对 kick 的输入、输出、副作用、前置条件和后置保证的描述均与代码原文逐条吻合，包括 finally 只在 running 时清理、错误被吞掉、wakeDriver 触发条件等，且调用方须知指出的边界情况（外部改 phase 导致 finally 跳过）在代码中确实存在。*

### [B] src\index.ts :: constructor（第319行，复杂度10）

【constructor 契约】（src/index.ts 第319-390行）

**输入**：
- `ctx: Context`：Cordis 上下文，必须已注入 `agents`、`sessions`、`llm`、`tools`、`systemPrompt` 服务（见 `static inject`，第300行）。
- `config: Config`：插件配置，含 `maxParallelToolCalls?` 和 `agents` 数组。

**输出**：无返回值（`void`）。构造完成后 `this` 是一个已注册的 `AgentLoop` 服务实例，且已通过 `ctx.agents.setFactory(this)` 注册为 agent 工厂（第350行）。

**副作用（外部状态变更）**：
1. 调用 `super(ctx, 'agentLoop')` 注册服务（第320行）。
2. `installSettingsSection(...)` 注册设置段，并设置 `setSource` 回调，使 `this.config.maxParallelToolCalls` 的 getter 在每次读取时动态返回最新值（第329-341行）。
3. `ctx.effect(() => () => this.ownership.dispose(), ...)` 注册 teardown 钩子（第349行）。
4. `ctx.effect(() => ctx.agents.setFactory(this), ...)` 把自身注册为 agent 工厂（第350行）。
5. 注册三个 systemPrompt 变量 `provider`、`model`、`cwd`（第351-353行）。
6. 对每个配置的 agent：若 `resumeSessionId` 为空，则创建新 session（`this.create`）或恢复/创建（`restoreOrCreateConfigured`）；否则注册 `ctx.effect` 在注入 `sessionPersistence` 后恢复会话（第355-390行）。
7. 可能触发 `agent-loop/config-start-failed` 事件（第370-388行）。

**前置条件**：
- `ctx` 必须已注入 `agents`、`sessions`、`llm`、`tools`、`systemPrompt`（`static inject`）。
- `config.maxParallelToolCalls` 若提供必须是正整数（`resolveMaxParallelToolCalls` 会抛错，第129-136行）。
- `config.agents` 中每个条目：`sessionId` 与 `resumeSessionId` 不能同时存在；重复的精确 session 身份会抛错（`validateConfiguredAgents`，第279-296行）。
- 若使用 `sessionId`（非 `resumeSessionId`），`ctx` 需已提供 `sessionPersistence` 服务（第360行检查 `ctx.get('sessionPersistence')`）。

**调用后保证**：
- 所有配置的 agent 要么已创建/恢复（异步，可能尚未完成），要么已注册恢复 effect。
- 工厂 teardown 时会等待所有 live agent 和 startup 任务完成（`FactoryOwnership.dispose`）。

【调用方须知】最易忽略的是：`this.config.maxParallelToolCalls` 是一个 getter，每次读取都会动态返回当前设置值（可能被 `installSettingsSection` 的 `setSource` 在运行时修改），而不是构造时固定的快照——因此不要在构造后缓存该值，否则会读到过期配置。

*✓ 核实通过——候选答案的每一条具体描述都能在代码原文中找到对应实现，包括副作用、前置条件和动态getter行为，没有发现与代码不符之处。*

### [B] src\index.ts :: validateConfiguredAgents（第278行，复杂度8）

【契约描述】

**输入**：`agents: Config['agents']` —— 即 `Config` 接口中 `agents` 字段的类型，是 `(AgentOptions & { id: string; sessionId?: SessionId; cwd?: string; resumeSessionId?: SessionId })[]` 的数组（见第 240-260 行 `Config` 接口定义）。

**输出**：`void`（无返回值）。

**副作用**：无。函数内部只创建了一个局部 `Map`（`exactIdentities`），不修改任何外部状态、文件或全局数据。

**前置条件**：
- 调用方需传入一个 `Config['agents']` 类型的数组（即 `agents` 字段）。
- 数组中的每个元素需符合 `Config['agents']` 的结构，即至少包含 `id` 字段（`id: string`），`sessionId` 和 `resumeSessionId` 为可选字段。

**调用后保证**：
- 若所有 agent 的 `sessionId` 与 `resumeSessionId` 互斥（即不同时存在），且所有非空 `sessionId`/`resumeSessionId` 值互不重复，则函数正常返回，不抛异常。
- 若存在冲突，则抛出 `Error`，具体规则如下（依据代码原文）：
  1. 若某个 agent 同时定义了 `sessionId` 和 `resumeSessionId`（且 `resumeSessionId` 非空字符串），则抛出 `Error`，消息为 `agent "${id}": sessionId and resumeSessionId are mutually exclusive`（第 285-287 行）。
  2. 若两个 agent 使用了相同的非空 `sessionId` 或 `resumeSessionId`（即“精确会话身份”重复），则抛出 `Error`，消息为 `agents "${firstId}" and "${id}" use duplicate exact session identity "${exactIdentity}"`（第 292-294 行）。
- 注意：`resumeSessionId` 为空字符串（`''`）时被视为未定义（`hasResumeId` 为 `false`），因此空字符串不会触发互斥或重复检查（第 284 行）。

【调用方须知】
调用方最容易忽略的是：`resumeSessionId` 为空字符串 `''` 时会被当作“未设置”处理（`hasResumeId` 为 `false`），因此一个 agent 可以同时设置 `sessionId` 和 `resumeSessionId: ''` 而不触发互斥错误，但此时实际生效的身份是 `sessionId`（因为 `exactIdentity` 取 `sessionId`），这可能导致你误以为 `resumeSessionId` 被忽略而实际身份被 `sessionId` 覆盖——如果业务上需要区分“显式未设置”和“空字符串”，请务必在传入前将空字符串归一化为 `undefined`。

*✓ 核实通过——逐条核对了候选答案的输入、输出、副作用、前置条件和错误消息，均与代码原文一致，特别是空字符串处理逻辑。*

### [C] src\invariant.ts :: (anonymous)（第21行，复杂度19）

【调用方须知】该函数（第21行的`install`）本身不直接对外暴露，而是作为`apply`注册的invariant安装器，在每次`llm/stream`事件触发时执行。它对调用方（即构造loop-built请求的代码）的契约如下：

**输入**：`ctx`（Cordis上下文，需已注入`sessions`服务）和`fail`（InvariantFailure回调）。实际校验发生在`ctx.on('llm/stream', ...)`监听器中，输入是`GenerateOptions`对象（`options`）和`next`回调。

**输出**：无返回值（`void`）。行为是：若校验通过则调用`next()`继续事件链；若校验失败则调用`fail(...)`并（在部分分支）`return`，不调用`next()`。

**副作用**：注册了一个全局、前置的`llm/stream`事件监听器（`{ global: true, prepend: true }`），该监听器在插件生命周期内持续存在，影响所有`llm/stream`事件。它不修改`options`、不写文件、不改全局数据，但会通过`fail`回调报告违规。

**前置条件**：
1. `ctx`必须已注入`invariants`服务（`inject: ['invariants']`）和`sessions`服务（`inject: ['sessions']`）。
2. 调用方构造的请求必须满足`isAgentLoopRequest(options)`为真，否则监听器直接`return next()`不校验。
3. 请求必须满足以下条件，否则触发`fail`：
   - `options`必须被冻结（`Object.isFrozen(options)`为真）——原文：`if (!Object.isFrozen(options)) fail('a loop-built request must be frozen')`
   - `options.sessionId`必须已定义且对应一个存在的session——原文：`if (options.sessionId === undefined) fail(...)`、`if (!session) fail(...)`
   - `options.messages`必须被冻结——原文：`if (!Object.isFrozen(options.messages)) fail(...)`
   - session日志中必须有`step/start`事件——原文：`if (!events.some(event => event.type === 'step/start')) return fail(...)`
   - `foldRequestHeader(events)`必须返回非`undefined`（即必须有request/header事件）——原文：`if (header === undefined) return fail(...)`
   - `options.messages`必须与`session.deriveMessages()`的JSON序列化结果完全一致——原文：`if (JSON.stringify(options.messages) !== JSON.stringify(expected)) fail(...)`
   - `options.model`、`options.system`、`options.temperature`、`options.maxTokens`、`options.stop`、`options.tools`必须与折叠的request header匹配——原文：`const headerMatches = ...`

**调用后保证**：若所有校验通过，监听器调用`next()`，事件链继续，请求被放行；若任一校验失败，调用`fail`报告具体原因，且不调用`next()`（在`step/start`和`header`缺失分支明确`return fail(...)`，其余分支`fail(...)`后继续执行到`return next()`——注意：非`return`的`fail`分支在`fail`之后仍会执行`return next()`，即`fail`回调本身可能不中断事件链，但`fail`的实现（由invariant框架提供）负责处理违规）。

【调用方须知】最容易忽略的是：`options.messages`必须与`session.deriveMessages()`的JSON序列化结果**逐字节一致**（`JSON.stringify`比较），且`options`和`options.messages`都必须是**冻结的**（`Object.isFrozen`）。这意味着调用方不能直接复用session的原始消息数组，而必须构造一个内容相同但已冻结的副本；任何微小的差异（如对象属性顺序、多余字段）都会导致`fail`，即使逻辑上等价。此外，`options.tools`和`options.stop`的比较也使用`JSON.stringify`，所以数组元素顺序必须完全一致。

*✓ 核实通过——候选答案对函数契约的描述与代码原文完全一致，包括输入输出、副作用、前置条件和调用后行为，且引用的代码片段准确无误。*

### [B] src\runtime-context.ts :: (anonymous)（第46行，复杂度7）

问题中提到的「(anonymous)」函数（圈复杂度7，第46行）实际是 `RuntimeContextProjection` 类的构造函数（`constructor(ctx: Context, session: Session)`，第46行起）。它的契约如下：

**输入**：
- `ctx: Context` —— agent 作用域的事件上下文（第47行 `constructor(ctx: Context, session: Session)`）。
- `session: Session` —— 接收投影消息的会话（第47行）。

**输出**：无返回值（构造函数）。

**副作用（外部状态修改）**：
1. 修改实例自身状态 `this.retained`（第40-41行 `this.retained = { seq: event.seq, text: textOf(event.data) }`；第52行 `this.retained = { seq: event.seq, text: textOf(event.data) }`；第56行 `this.retained = null`）。
2. 通过 `ctx.on('session/event', ...)` 注册一个持久的事件监听器（第44行），该监听器在会话生命周期内持续存在，会持续修改 `this.retained`。

**前置条件**：
- `session.surface.nodes` 必须可迭代（第39行 `const surface = new Set(session.surface.nodes)`）。
- `session.events` 必须可索引且元素可能为 `undefined`（第40-41行 `const event = session.events[index]`，第42行 `if (event?.type !== 'user/message' ...)`）。
- `session.events` 中的 `user/message` 事件数据必须具有 `source.kind === 'plugin'` 且 `source.plugin === SOURCE`（第42行 `isOwned(event.data)`，第31-33行 `isOwned` 定义）。
- 事件数据必须符合 `UserMessage` 结构，`content` 为数组，元素可能有 `type` 和 `text` 字段（第35-37行 `textOf`）。

**调用后保证**：
- 构造完成后，`this.retained` 被初始化为：若会话历史中存在属于本插件的 `user/message` 事件且其 `seq` 在 `session.surface.nodes` 中，则 `retained` 为 `{ seq, text }`（第40-43行）；若存在本插件事件但都不在 surface 中，则 `retained` 为 `null`（第42行 `this.retained ??= null`）；若不存在任何本插件事件，则 `retained` 保持 `undefined`（第42行 `??=` 不触发）。
- 之后每当会话产生新事件，监听器会更新 `retained`：本插件的 `user/message` 事件会覆盖为最新快照（第51-53行）；若事件是替换 surface 事件且其 `sourceEventSeqs` 包含当前 `retained.seq`，则 `retained` 置为 `null`（第54-56行）。

【调用方须知】构造函数会通过 `ctx.on('session/event', ...)` 注册一个**永不注销的持久事件监听器**（第44行），它会在整个会话生命周期内持续修改 `this.retained` 状态——即使调用方已经不再使用该投影实例，监听器依然存活并占用资源、持续响应事件。调用方若在短生命周期场景（如临时投影）使用它，必须自行确保 `ctx` 作用域能随实例一起销毁，否则会造成监听器泄漏和意外的状态更新。

*✓ 核实通过——候选答案对构造函数的输入、副作用、前置条件和调用后保证的描述均与代码原文一致，且正确指出了监听器永不注销的隐患。*

### [B] src\runtime-context.ts :: constructor（第34行，复杂度7）

【constructor 契约】

**输入**：
- `ctx: Context` —— agent 作用域的事件上下文（用于注册事件监听）。
- `session: Session` —— 接收投影消息的会话。

**输出**：无返回值（`void`）。

**副作用（外部状态变更）**：
1. 修改实例私有字段 `this.retained`（初始为 `undefined`，表示从未有过快照）。
2. 通过 `ctx.on('session/event', ...)` 注册一个持久的事件监听器，该监听器在会话后续事件发生时持续修改 `this.retained`。这是构造器最重要的持久副作用。

**前置条件**：
- `session.surface.nodes` 与 `session.events` 必须已可用（构造器直接读取它们）。
- `session.events` 中事件的 `seq` 字段与 `session.surface.nodes` 中的节点 `seq` 对应（用于判断事件是否在 surface 上）。

**调用后保证**：
1. 构造完成后，`this.retained` 被初始化为：
   - 若会话历史中存在由本插件（`SOURCE = '@deepseek-ai/dsh-system-prompt'`）发出的、且其 `seq` 在 `session.surface.nodes` 中的最近一条 `user/message` 事件，则 `retained = { seq, text }`（`text` 为该消息的纯文本内容，若消息不是单文本块则为 `undefined`）。
   - 若存在本插件消息但都不在 surface 上，则 `retained = null`（表示无保留快照）。
   - 若从未存在本插件消息，则 `retained` 保持 `undefined`。
2. 注册的事件监听器保证：
   - 当 `session` 收到新的本插件 `user/message` 事件时，`retained` 更新为该事件（`{ seq, text }`）。
   - 当 `retained` 非空且收到一个“替换 surface 事件”（`isReplacementSurfaceEvent(event)` 为真）且该事件的 `sourceEventSeqs` 包含 `retained.seq` 时，`retained` 被置为 `null`。

**代码依据**：
- 输入/输出：`constructor(ctx: Context, session: Session)` 无返回类型。
- 初始化逻辑：`for (let index = session.events.length - 1; index >= 0; index -= 1) { ... if (surface.has(event.seq)) { this.retained = { seq: event.seq, text: textOf(event.data) }; break } }` 及 `this.retained ??= null`。
- 事件监听副作用：`ctx.on('session/event', (subject, event) => { if (subject !== session) return; ... })`。
- 判定本插件消息：`isOwned` 检查 `message.source.kind === 'plugin' && message.source.plugin === SOURCE`。
- 文本提取：`textOf` 仅当消息恰有一个 text 块时返回文本，否则 `undefined`。

【调用方须知】构造器会注册一个**持久的事件监听器**（`ctx.on('session/event', ...)`），它会在整个会话生命周期内持续修改 `this.retained`——调用方若在构造后自行读取或依赖 `retained` 的初始值，必须意识到该值会随后续会话事件（新本插件消息、surface 替换事件）被异步更新；尤其当 `retained` 初始为 `undefined`（从未有快照）时，一旦后续出现本插件消息，它会变成对象，而出现替换事件时又可能变成 `null`，三种状态（`undefined`/`null`/对象）语义不同，调用方需区分处理。

*✓ 核实通过——候选答案对构造函数的输入、输出、副作用、前置条件和保证的描述均与代码原文一致，且引用的代码片段准确。特别地，持久事件监听器的副作用和 `retained` 的三种状态（undefined/null/对象）在代码中均有明确体现。*

### [B] src\runtime-context.ts :: project（第64行，复杂度6）

函数 `project`（src/runtime-context.ts 第64-76行）的契约如下：

**输入**：
- `current: string` —— 完全渲染后的动态上下文文本（第64行）。
- `sections: readonly ContextSnapshotSection[]` —— 构成当前快照的命名贡献列表（第64行）。

**输出**：
- 返回 `UserMessage | undefined`（第64行）。当需要更新时返回一个未提交的候选用户消息；当不需要更新时返回 `undefined`。

**行为/副作用**：
- 不修改任何外部状态、文件或全局数据。它只读取 `this.retained`，并返回一个新构造的 `UserMessage`（通过 `createUserMessage` 创建，第70-75行）。它不提交该消息，也不改变 `this.retained`（`retained` 只在构造函数的事件监听器中更新）。

**前置条件**：
- 调用前 `this.retained` 必须已被构造函数初始化（构造函数会扫描历史事件并设置 `retained`，见第30-47行）。若从未调用构造函数，`retained` 为 `undefined`，此时若 `current` 为空字符串则直接返回 `undefined`（第65行）。

**调用后保证**：
- 若 `retained` 为 `undefined` 且 `current` 为空，返回 `undefined`（第65行）。
- 若 `current` 为空，`snapshot` 被设为常量 `CLEARED`（'Current runtime context: none. Earlier runtime-context snapshots no longer apply.'，第66行）。
- 若 `retained.text` 与 `snapshot` 相同，返回 `undefined`（第67行），避免重复快照。
- 否则返回一个 `UserMessage`，其文本为 `snapshot`，`source` 为 plugin 类型，plugin 为 `SOURCE`；当 `sections` 非空时附带 `form: 'snapshot'` 和 `sections`（第70-75行）。

【调用方须知】当 `current` 为空字符串时，函数返回的消息文本不是空字符串，而是固定的 `CLEARED` 常量（'Current runtime context: none. Earlier runtime-context snapshots no longer apply.'），且此时 `sections` 必须为空（否则 `source` 会带上 `form: 'snapshot'` 和 sections，但注释明确说 cleared marker 没有可归属的贡献，调用方若传入非空 sections 会产生语义不一致的消息）。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和调用后保证的描述均与代码原文一致，且【调用方须知】准确指出了 current 为空时返回 CLEARED 常量以及 sections 非空时的语义问题。*

### [B] src\tool-calls.ts :: commitReady（第146行，复杂度8）

【函数契约：commitReady（src/tool-calls.ts 第146-161行）】

**输入**：无参数（`const commitReady = async (): Promise<void> =>`）。它不接收任何显式参数，完全依赖闭包捕获的外部状态：`committed`（已提交计数）、`slots`（已settled的槽位数组）、`group`（本组的计划调用）、`session`/`turn`/`step`（来自外层`runGroup`）、`callSeqs`（每个调用对应的`tool/call`事件seq）、`ctx.tools[TOOL_RUNTIME_SCHEDULER]`（运行时调度器）、`concluded`（是否结束回合的标志）。

**输出**：`Promise<void>`，不返回任何值。

**副作用（外部状态修改）**：
1. **修改session事件流**：对每个已settled的槽位调用`appendToolResult(session, turn, step, call!.block, result, callSeqs[committed]!)`（第154行），向session追加`tool/result`事件（见`appendToolResult`第280-289行，会`session.append('tool/result', ...)`）。
2. **接受上下文**：对结果的`additionalContexts`逐个调用`acceptContext(context)`（第155行），把结果上下文交给调用方提供的acceptor（用于下一步边界）。
3. **修改`concluded`标志**：`concluded ||= result.concludesTurn === true`（第156行），若任一结果`concludesTurn`为true则置位。
4. **修改`committed`计数**：每次循环末尾`committed++`（第157行），推进已提交的槽位索引。

**前置条件**：
1. 调用前`slots[committed]`必须已settled（即该槽位已通过`startCall`的dispatch/post-result/final-result填充），否则循环直接`break`（第149-150行）。
2. 外层`runGroup`保证`commitReady`只在`startCall`之后或`Promise.race`settled之后调用（见第194、214行），确保槽位已就绪。
3. 依赖`ctx.tools[TOOL_RUNTIME_SCHEDULER]`存在且提供`finalize`/`finish`方法。

**调用后保证**：
1. 所有从`committed`到`group.length`之间连续已settled的槽位（`slots[committed] !== undefined`）都会被提交：结果写入session、上下文被接受、`concluded`被合并。
2. `committed`推进到第一个未settled槽位或`group.length`（循环条件`committed < group.length`，第148行）。
3. 若某槽位`needsPost`为true，会调用`finalize`（异步等待）；否则调用`finish`（同步）（第151-153行）。
4. 不修改`slots`数组内容，不改变`started`/`nextToStart`/`aborted`等其它状态。

【调用方须知】`commitReady`只提交**从`committed`开始的连续已settled槽位**——一旦遇到`slots[committed] === undefined`就立即`break`，即使后面还有已settled的槽位也不会提交；因此调用方必须在每次`startCall`或dispatch settle之后**立即**调用`commitReady`（如`fillPool`第194行、`Promise.race`第214行所示），否则后续已settled的结果会一直滞留不写入session，直到下一次调用才被提交。若调用方漏掉某次调用，会导致结果提交顺序错乱或延迟。

*✓ 核实通过——逐条对照代码原文，候选答案对输入、输出、副作用、前置条件和保证的描述均准确，无虚构或夸大。*

### [B] src\tool-calls.ts :: fillPool（第198行，复杂度8）

fillPool 是 src/tool-calls.ts 中 runGroup 内部的一个局部 async 函数（第198-214行），不是导出函数。它的契约如下：

**输入（隐式闭包捕获，无显式参数）**：
- `aborted`（boolean，runGroup 局部变量，初始为 `signal.aborted`）
- `nextToStart`（number，下一个待启动的调用下标）
- `group`（PlannedCall[]，当前组的调用列表）
- `inFlight`（Map<number, Promise<number>>，在途 dispatch 的 promise 集合）
- `maxParallelToolCalls`（来自 `ctx.agentLoop.config`）
- `mode`（'parallel' | 'exclusive'）
- `ctx`、`signal` 等

**输出**：`Promise<void>`，不返回任何值。

**副作用（对外部状态/会话的修改）**：
1. 调用 `startCall(nextToStart)`（第207行），而 `startCall` 内部会 `appendToolCall(session, turn, step, call.block)`（第151行）——即向 session 追加 `tool/call` 事件，并递增 `started`。
2. 调用 `commitReady()`（第209行），它会 `appendToolResult(...)`（第130行）向 session 追加 `tool/result` 事件，并调用 `acceptContext(context)`（第131行）把结果上下文交给调用方提供的 acceptor。
3. 修改闭包变量：`nextToStart++`（第208行）、`aborted = true`（第213行，当 `signal.aborted` 为真时）。
4. 通过 `startCall` 内部 `inFlight.set(index, promise)`（第163行）向 `inFlight` 添加在途 promise。

**前置条件**：
- `!aborted`（第199行）——abort 信号未触发。
- `nextToStart < group.length`（第199行）——还有未启动的调用。
- `inFlight.size < maxParallelToolCalls`（第199行）——在途并发数未达上限。
- 当 `mode === 'parallel'` 且 `nextToStart > 0` 时，`ctx.tools.executionMode(nextCall.exec).kind` 必须仍为 `'parallel'`，否则提前 break（第203-204行）。

**调用后保证**：
- 循环退出时，要么 `aborted` 为真、要么 `nextToStart === group.length`、要么 `inFlight.size === maxParallelToolCalls`。
- 每次迭代至少启动一个调用（`startCall` 被调用），且 `nextToStart` 递增。
- 若 `startCall` 或 `commitReady` 期间发生 scheduler failure，`throwSchedulerFailure()`（第208、210行）会抛出异常，终止 fillPool。
- 不保证所有调用都完成——它只负责“填满池子”，后续由外层 while 循环继续调度。

【调用方须知】fillPool 每次迭代都会调用 `commitReady()`，而 `commitReady` 会同步调用 `acceptContext(context)`（第131行）——即它会在启动新调用的同时，把已就绪结果的上文立即交给调用方注入到下一步的 inbox 中；如果调用方在 `acceptContext` 里做了重操作或依赖尚未全部结果就绪的状态，可能在这个看似只“填池”的函数里被意外触发。另外注意：fillPool 内部在 `startCall` 之后才检查 `signal.aborted` 并设置 `aborted = true`（第213行），所以 abort 信号可能在 pre-execute await 期间到达，但本轮循环仍会继续启动下一个调用（因为 `aborted` 还没被置位），直到下一次循环条件判断才停止——这意味着 abort 后可能仍会多启动一个调用。

*✓ 核实通过——候选答案对 fillPool 的契约描述与代码原文逐条吻合，包括输入捕获、输出、副作用、前置条件和调用后保证，且引用的行号和函数行为均准确。特别指出的 abort 后可能多启动一个调用（第213行在 startCall 之后才检查）也正确。*

### [B] src\tool-calls.ts :: startCall（第164行，复杂度6）

【startCall 契约】

**输入**：`index: number`，是 `group`（`PlannedCall[]`，即本组待调度的工具调用，按模型顺序排列）中的下标。函数通过 `group[index]!` 取出对应的 `PlannedCall`（含 `block: ToolCallBlock` 和 `exec: ToolExecutionInput`）。

**输出**：`Promise<void>`，无返回值。

**副作用**（对调用方可见的外部状态变更）：
1. **追加 `tool/call` 事件**：`callSeqs[index] = appendToolCall(session, turn, step, call.block)` —— 在 session 上追加一个 `tool/call` 事件，并把返回的 `seq` 记录到 `callSeqs[index]`，供后续结果引用。
2. **递增 `started` 计数**：`started++`，表示已启动的调用数。
3. **写入 `slots[index]`**：根据 `prepare` 的结果，把 `{ exec, result, needsPost }` 存入 `slots[index]`（dispatch 分支在 promise resolve 后写入；post-result / final-result 分支同步写入）。
4. **维护 `inFlight` Map**：dispatch 分支把 `dispatch(...)` 的 promise 存入 `inFlight.set(index, promise)`。
5. **可能设置 `schedulerFailure`**：dispatch 的 promise reject 时 `schedulerFailure ??= { error }`，或 `prepare` 抛错时由 `throwSchedulerFailure()` 抛出。

**前置条件**：
- `group[index]` 必须存在（`group[index]!` 断言非空）。
- `ctx.tools[TOOL_RUNTIME_SCHEDULER]` 必须存在且提供 `prepare`、`dispatch` 方法。
- 调用方（`fillPool`）需保证 `inFlight.size < maxParallelToolCalls` 且 `!aborted` 且 `nextToStart < group.length`。
- 调用前 `schedulerFailure` 应为 undefined（否则 `prepare` 后 `throwSchedulerFailure()` 会抛错）。

**调用后保证**：
- 若 `prepare` 返回 `dispatch`：`slots[index]` 会在 dispatch 的 promise resolve 后被填充（`needsPost` 取决于 outcome.kind），并注册到 `inFlight`；若 reject，则设置 `schedulerFailure` 但 `slots[index]` 保持 undefined。
- 若返回 `post-result` / `final-result`：`slots[index]` 同步填充，`needsPost` 分别为 true / false。
- 函数本身不抛错（除非 `prepare` 抛错且 `throwSchedulerFailure()` 抛出），错误通过 `schedulerFailure` 传递。

【调用方须知】startCall 在 dispatch 分支中，`slots[index]` 的填充是**异步**的（在 dispatch promise resolve 之后），而 `started` 计数和 `tool/call` 事件是**同步**完成的——因此调用方不能假设 `startCall` 返回后 `slots[index]` 一定已就绪；必须通过 `inFlight` 的 promise 等待 dispatch 完成，且 `commitReady` 只有在 `slots[committed]` 已填充时才会推进 `committed`。若 dispatch reject，`slots[index]` 永远保持 undefined，`commitReady` 会卡住，必须依赖 `schedulerFailure` 被抛出才能让外层循环退出。

*✓ 核实通过——逐条核对了候选答案中的每个具体说法（函数名、变量名、行为描述）与代码原文，全部吻合，没有发现不实之处。*

### [C] tests\cancel.spec.ts :: (anonymous)（第774行，复杂度14）

在 tests/cancel.spec.ts 中，第774行附近的「(anonymous)」是 `it.each([...])('lets a cooperative %s boundary settle from the explicit turn signal', async (stage) => {...})` 这个参数化测试用例的匿名回调函数（第774行是 `it.each([...])(...)` 的起始行，回调从第775行开始）。它的契约如下：

**输入**：
- 参数 `stage`，取值来自 `it.each` 数组：`'pre-step'`、`'system-prompt'`、`'request'`、`'stopping'`、`'tool'`（第774行）。
- 通过闭包捕获 `adapter`、`ctx`、`agent`（由 `ctx.agentLoop.create` 创建，第776行）。

**输出**：
- 无返回值（async 函数，返回 Promise<void>）。
- 断言（`expect`）验证：`turnEnd.data.reason` 等于 `{ kind: 'aborted', reason: { kind: 'user' } }`（第836-837行）。

**副作用**：
- 修改了 `agent.session.events`：追加了 `turn/end` 事件（通过 `agent.cancel` 触发，第834行）。
- 修改了 `adapter.requests`：发送了 `'go'` 消息（第833行 `send(agent, 'go')`），并可能触发一次模型请求。
- 修改了 `ctx` 的事件监听器：根据 `stage` 注册了 `agent/pre-step`、`system-prompt/assemble`、`agent/request`、`agent/turn-stopping` 或工具 `blocked`（第785-824行）。
- 调用了 `ctx.fiber.dispose()`（第838行），销毁了上下文 fiber。

**前置条件**：
- 必须已经通过 `harness(adapter)` 创建了 `ctx`，并且 `ctx.agentLoop.create` 成功创建了 `agent`（第776行）。
- `adapter` 必须能响应 `'go'` 消息（对 `'tool'` 阶段需要返回 `toolCallResponse('blocked-tool', 'blocked', {})`，其他阶段返回 `textResponse('done')`，第775行）。
- 对于 `'tool'` 阶段，`ctx.tools.register` 必须能注册名为 `'blocked'` 的工具（第810-823行）。
- 测试运行环境必须支持 `Promise.withResolvers`（第778行）。

**调用后保证**：
- `agent.cancel({ kind: 'user' })` 后，`agent.whenIdle()` 会 resolve（第834-835行），即 agent 会进入 idle 状态。
- 最终 `turn/end` 事件的 reason 一定是 `{ kind: 'aborted', reason: { kind: 'user' } }`（第836-837行），表示该 turn 被用户取消。
- 对于 `'tool'` 阶段，工具 `blocked` 的 `execute` 会等待 abort 信号，然后返回 `[{ type: 'text', text: 'cancelled' }]`（第818-822行），但该结果不会真正执行（因为 turn 已取消）。

【调用方须知】这个测试用例的 `stage` 参数决定了它注册哪个事件监听器来阻塞 turn 的执行，但无论哪个阶段，`agent.cancel({ kind: 'user' })` 都会让 `whenIdle()` 在 abort 信号触发后 resolve，并且最终 `turn/end` 的 reason 一定是 `{ kind: 'aborted', reason: { kind: 'user' } }`——但注意，对于 `'tool'` 阶段，工具 `blocked` 的 `execute` 返回的 `'cancelled'` 文本并不会被写入 `agent.session.events`（因为 turn 已取消），所以不要期望在事件日志里看到这个工具结果。最容易被忽略的是：这个测试在 `await idle` 之后才调用 `ctx.fiber.dispose()`，如果 `whenIdle()` 因为某种原因没有 resolve（比如 abort 信号没触发），测试会挂起，但这里用 `agent.cancel` 显式触发 abort，所以必须确保 `agent.cancel` 在 `whenIdle()` 注册之后调用，否则 `whenIdle()` 可能永远不 resolve。

*✓ 核实通过——I read the entire tests/cancel.spec.ts file and verified each claim in the candidate answer against the actual code, including the specific lines and behaviors mentioned.*

### [B] tests\interception.spec.ts :: (anonymous)（第257行，复杂度10）

问题中的「(anonymous)」指的是 tests/interception.spec.ts 第257行所在的 `it('stages inject and steer during pre-step for the entered turn', async () => { ... })` 测试用例（vitest 的 `it` 回调是匿名函数，圈复杂度10）。该用例的契约如下：

**输入**：
- 一个 `MockAdapter`（`new MockAdapter([textResponse('ok')])`，第258行）。
- 通过 `harness(adapter)` 构建的 `ctx`（第259行）。
- 一个 agent：`ctx.agentLoop.create(SessionId('pre-step-outbox'), { provider: 'mock', model: 'mock' })`（第260行）。
- 一个 `agent/pre-step` 监听器（第262-269行），它第一次调用时把 `messages` 存到 `claimed` 并 `entered.resolve(undefined)`，然后返回 `decision.promise`（一个未决的 `PreStepDecision`）；后续调用直接 `return { kind: 'enter', messages }`。
- 通过 `send(agent, 'entered prompt')` 发送一条用户消息（第271行）。

**输出/行为**：
- 该用例验证：在 pre-step 监听器未决期间，`agent.status` 为 `'running'`（第273行），且已发出 `turn/start` 事件（第274行）。
- 在监听器未决期间调用 `agent.inject(...)` 和 `agent.steer(...)`（第276-280行），此时**不会**产生 `user/message` 事件（第281行），这些消息进入 `agent.inbox.nextStep`（第282-287行）。
- 当 `decision.resolve({ kind: 'enter', messages: claimed })` 后（第289行），agent 进入 idle，`agent.inbox.hasPending` 为 false（第291行）。
- 事件日志顺序为：`turn/start`、`user/message`（entered prompt）、`user/message`（attached context）、`user/message`（pre-step steering）（第293-306行）。
- 第一次模型请求只包含 `entered prompt`，**不包含** `attached context` 和 `pre-step steering`（第307-310行）；第二次请求才包含后两者（第311-313行）。

**副作用**：
- 修改了 `agent.inbox` 的内部状态（`nextStep`、`hasPending`）。
- 向 `agent.session` 写入 `user/message` 事件（通过 `events(agent)` 可见）。
- 向 `adapter.requests` 追加模型请求（通过 `JSON.stringify(adapter.requests[0]...)` 断言）。
- 改变了 `agent.status`（从 `running` 到 `idle`）。

**前置条件**：
- 必须先 `await entered.promise`，确保 pre-step 监听器已捕获 `claimed` 并处于未决状态（第272行）。
- 必须先 `await waitForIdle(ctx, agent)`（第271行）建立 idle 等待，否则无法同步。
- 监听器第一次调用必须返回 `decision.promise`（未决），否则后续 `inject`/`steer` 的时序断言不成立。

**调用后保证**：
- 所有 staged 的消息（inject 和 steer）最终都会进入事件日志，且顺序为：entered prompt → attached context → pre-step steering（第293-306行）。
- 第一次请求只含 entered prompt，第二次请求才含 staged 内容（第307-313行）——即 staged 内容不会混入当前正在处理的 step，而是进入下一个 step。

【调用方须知】在 pre-step 监听器未决期间调用 `agent.inject`/`agent.steer` 的消息**不会**出现在当前 step 的模型请求里，而是被缓冲到 `inbox.nextStep`，只有等到监听器 resolve 之后的下一个 step 才会发给模型——所以如果你期望 staged 内容立即影响当前请求，会得到错误结果；必须等 pre-step 返回 `enter` 之后的下一次模型调用才会带上这些内容。

（依据：tests/interception.spec.ts 第257-313行，特别是第276-313行的断言。）

*✓ 核实通过——候选答案对函数契约的描述与代码原文完全一致，所有引用的行号和断言都准确，没有发现任何不实之处。*

### [B] tests\loop.spec.ts :: (anonymous)（第413行，复杂度9）

（超过最大步数，未能得出答案）

*✗ 核实不通过——The candidate answer is a placeholder indicating failure to produce an answer, so it cannot be verified as accurate. Additionally, the file is a test file with no such function at line 413.*

### [B] tests\loop.spec.ts :: (anonymous)（第275行，复杂度6）

第275行的「(anonymous)」是 `it('contains a strict-variable render failure: the turn errors, the loop keeps serving turns', async () => { ... })` 这个测试用例的回调函数（匿名 async 函数）。它的契约如下：

**输入**：无显式参数（闭包捕获 `adapter`、`ctx`、`errors`、`agent` 等局部变量）。

**输出**：无返回值（async 函数，返回 Promise<void>）。

**副作用（外部状态改动）**：
- 通过 `ctx.on('agent/error', ...)` 注册了一个错误监听器，把错误 push 进 `errors` 数组（第280-282行）。
- 通过 `ctx.on('system-prompt/assemble', async (assembly, _context, next) => { assembly.variables['cwd'] = '/rescued'; return next() })` 注册了一个 waterfall 监听器，**修改了 assembly.variables['cwd'] 的值**（第298-301行）。
- 通过 `ctx.agentLoop.create(...)` 创建了一个 agent（第283行），并通过 `send(agent, 'hi')` / `send(agent, 'again')` 向它发送消息（第285、302行），这会驱动 agent loop 执行、产生 session 事件、向 `adapter` 发请求。

**前置条件**：
- 需要 `harness(adapter, 'In {{cwd}}.')` 已创建好 `ctx`（第278行），且 `adapter` 是 `MockAdapter`。
- 需要 `ctx.on('agent/error')` 先注册好监听器（第280行），才能收集到错误。
- 需要 `ctx.agentLoop.create(SessionId('a1'), { provider: 'mock', model: 'mock' })` 成功创建 agent（第283行）。
- 需要 `waitForIdle(ctx, agent)` 能等到 loop 空闲（第286、303行）。

**调用后保证**：
- 第一次 `send(agent, 'hi')` 后，`adapter.requests` 长度为 0（请求从未发出，第288行），`errors` 里有一条消息为 `'prompt variable "{{cwd}}" has no value for this assembly (section "deployment:persona")'`（第289-291行），且 session 里出现一个 `turn/end` 事件，其 `reason.kind` 为 `'error'`、错误消息包含 `'no value for this assembly'`（第292-296行）。
- 注册 `system-prompt/assemble` 监听器并 `send(agent, 'again')` 后，`adapter.requests` 长度为 1，其 `system` 为 `'You are an AI agent powered by DeepSeek Harness.\n\nIn /rescued.'`（第304-306行），session 里出现两个 `turn/end` 事件，第二个的 `reason.kind` 为 `'completed'`（第307-309行）。

【调用方须知】这个测试用例通过 `ctx.on('system-prompt/assemble', ...)` 注册的 waterfall 监听器**直接修改了 `assembly.variables['cwd']` 并调用 `next()`**——这是该测试能“救活”第二次 turn 的关键副作用；如果调用方漏掉这个监听器（或忘记在 `next()` 前给 `assembly.variables['cwd']` 赋值），第二次 `send(agent, 'again')` 会像第一次一样失败（`adapter.requests` 仍为 0、`turn/end` 的 reason 仍是 `error`），而不会得到 `completed` 的结果。也就是说，这个测试的“成功”完全依赖这个瀑布监听器对 `cwd` 变量的注入，而不是 agent loop 本身的自愈能力。

*✓ 核实通过——I read the entire tests/loop.spec.ts file and verified each specific claim in the candidate answer against the actual code, including the exact error message, the system prompt string, the number of requests, and the turn/end reasons. The candidate answer is accurate and well-supported.*

### [B] tests\loop.spec.ts :: (anonymous)（第357行，复杂度6）

第357行的「(anonymous)」是 `it('materializes changed runtime context at the history tail without rewriting the system header', async () => {...})` 这个测试用例的匿名回调函数（即整个测试体）。它的契约如下：

**输入**：无显式参数。它通过闭包使用 `adapter`（`new MockAdapter([textResponse('one'), ..., textResponse('five')])`，第358-363行）、`ctx`（`await harness(adapter)`，第365行）、`mode` 变量（初始 `'read-only'`，第366行）、`dispose`（`ctx.systemPrompt.context({ name: 'policy', order: 0, text: () => \`Mode: ${mode}.\` })`，第367行）、`agent`（`ctx.agentLoop.create(SessionId('a-runtime-context'), { provider: 'mock', model: 'mock' })`，第368行）。

**输出**：无返回值（`async` 函数，正常结束即通过断言）。它通过 `expect(...)` 断言验证行为，不返回数据。

**副作用**：
1. 修改了 `mode` 变量（第366行初始化为 `'read-only'`，第382行改为 `'danger-full-access'`），该变量被 `ctx.systemPrompt.context` 的 `text` 回调闭包捕获，从而改变后续请求的运行时上下文内容。
2. 通过 `send(agent, ...)` 向 agent 发送了 5 条用户消息（`'first'`、`'unchanged'`、`'changed'`、`'cleared'`、`'still clear'`，第374、377、383、390、394行），驱动 agent 产生请求，写入 `adapter.requests`。
3. 调用了 `dispose()`（第389行），移除之前注册的 `ctx.systemPrompt.context` 回调，使运行时上下文变为“none”。
4. 修改了 `agent.session.events`（通过发送消息和 agent 内部处理），并断言 `request/header` 事件只有 1 个（第399行）。

**前置条件**：
1. `harness(adapter)` 必须成功返回一个可用的 `ctx`（第365行）。
2. `ctx.systemPrompt.context` 必须可用且能注册回调（第367行）。
3. `ctx.agentLoop.create` 必须能创建 agent（第368行）。
4. `send` 和 `waitForIdle` 辅助函数必须可用（第374、375行等）。
5. `MockAdapter` 必须按顺序提供 5 个响应（第358-363行），因为测试发送了 5 条消息。

**调用后保证**：
1. 发送 `'first'` 后，`contextEvents()` 长度为 1，且内容为 `[{ type: 'text', text: 'Current runtime context. This snapshot supersedes earlier runtime-context snapshots.\n\nMode: read-only.' }]`（第375-378行）。
2. 发送 `'unchanged'`（内容未变）后，`contextEvents()` 仍为 1（第380-381行），即不重复发出相同上下文。
3. 修改 `mode` 后发送 `'changed'`，`contextEvents()` 变为 2，且新块文本包含 `'danger-full-access'`（第382-387行）。
4. `dispose()` 后发送 `'cleared'`，`contextEvents()` 变为 3，内容为 `[{ type: 'text', text: 'Current runtime context: none. Earlier runtime-context snapshots no longer apply.' }]`（第390-393行）。
5. 发送 `'still clear'` 后，`contextEvents()` 仍为 3（第395-396行），即不再发出上下文。
6. 所有 5 个请求的 `system` 字段完全相同（`adapter.requests.map(request => request.system)).toEqual(Array(5).fill(adapter.requests[0]?.system)`，第398行），且 `request/header` 事件只有 1 个（第399行），证明系统头（system header）没有被重写，运行时上下文只在历史尾部物化。

【调用方须知】这个测试的核心断言是：即使运行时上下文内容变化（`mode` 从 `'read-only'` 变为 `'danger-full-access'`），所有 5 个请求的 `system` 字段仍然完全相同（第398行），且 `request/header` 事件只有 1 个（第399行）——即系统头在首次请求后就被固定，后续运行时上下文变化**不会**重写系统头，而是作为新的历史尾部消息追加。调用方最容易忽略的是：`dispose()` 之后发送消息，运行时上下文会变成“none”并**再次**发出一个快照（第390-393行），但之后（`'still clear'`）就不再重复发出——即“none”状态只物化一次，且系统头依然不变。

*✓ 核实通过——I read the entire tests/loop.spec.ts file and verified each claim in the candidate answer against the actual code, including the specific line numbers and the exact assertions made in the test.*

### [B] tests\loop.spec.ts :: (anonymous)（第448行，复杂度6）

第448行的「(anonymous)」是测试用例 `it('clears compacted runtime context after the active set becomes empty', ...)` 的匿名回调函数（即该测试的主体）。它的契约如下：

**输入**：无显式参数（测试回调不接收参数）。它依赖外部闭包中的 `MockAdapter`、`harness`、`SessionId`、`send`、`waitForIdle`、`createUserMessage` 等测试工具，以及 `ctx.systemPrompt.context`、`agent.session.append` 等被测对象的方法。

**输出**：无返回值（`async` 函数，返回 Promise<void>）。它通过 `expect(...)` 断言来验证行为，不产生返回值。

**副作用**：
- 创建了一个新的 agent 会话：`ctx.agentLoop.create(SessionId('a-runtime-context-compacted-clear'), { provider: 'mock', model: 'mock' })`（第451行）。
- 通过 `ctx.systemPrompt.context({ name: 'policy', order: 0, text: 'Mode: read-only.' })` 注册了一个系统提示上下文，并保存了 `dispose` 函数（第450行）。
- 通过 `agent.session.append('user/message', ...)` 向会话追加了用户消息，其中一条是 `source.plugin === 'test-compaction'` 的压缩摘要消息，并带 `surfaceOp: { op: 'replace', start: contextEvent.seq, end: contextEvent.seq }`（第458-463行）。
- 调用了 `dispose()` 来移除之前注册的上下文（第464行）。
- 通过 `send(agent, 'after compaction')` 触发 agent 处理，产生对 adapter 的请求（第466行）。
- 断言 `adapter.requests[1]?.messages` 中存在一条来自 `@deepseek-ai/dsh-system-prompt` 插件的消息，且其 `content` 精确等于 `[{ type: 'text', text: 'Current runtime context: none. Earlier runtime-context snapshots no longer apply.' }]`（第468-472行）。

**前置条件**：
- 需要 `harness(adapter)` 已初始化好测试环境（第449行）。
- 需要 `MockAdapter` 提供至少两个响应（`textResponse('one')` 和 `textResponse('two')`，第448行），因为测试会发送两次消息（'first' 和 'after compaction'）。
- 需要 `send(agent, 'first')` 后，会话中确实存在一条来自 `@deepseek-ai/dsh-system-prompt` 插件的 `user/message` 事件（第454-457行），否则会抛出 `throw new Error('first turn did not materialize runtime context')`。

**调用后保证**：
- 在 `dispose()` 之后、压缩摘要被追加之后，再次发送消息时，adapter 的第二个请求（`adapter.requests[1]`）中必须包含一条来自 `@deepseek-ai/dsh-system-prompt` 插件的消息，其内容为“Current runtime context: none. Earlier runtime-context snapshots no longer apply.”，表示运行时上下文已被清除。

【调用方须知】最容易忽略的是：这个测试在 `dispose()` 之后，`adapter.requests[1]` 中仍然会有一条来自 `@deepseek-ai/dsh-system-prompt` 插件的消息（内容是“none”的清除消息），而不是完全没有该插件的消息——即“清除”是通过发送一条显式的“无上下文”消息实现的，而不是删除该插件消息；如果调用方误以为 dispose 后该插件消息会消失，就会出错。

*✓ 核实通过——I read the entire tests/loop.spec.ts file and verified each claim in the candidate answer against the actual code. The candidate answer accurately describes the test's contract, including the specific side effects, preconditions, and postconditions, and the final warning is a correct and important observation.*

### [B] tests\request-reconstruction.spec.ts :: (anonymous)（第590行，复杂度7）

第590行的「(anonymous)」是 `adapter.requests.forEach((request, index) => { ... })` 这个回调函数（圈复杂度7，B级）。它的契约如下：

**输入**：
- `request`：`adapter.requests` 数组中的元素，即 AgentLoop 实际发送给 adapter 的请求对象（含 `messages`、`model`、`reasoningEffort`、`system`、`tools`、`temperature`、`maxTokens`、`stop` 等字段）。
- `index`：请求在 `adapter.requests` 中的下标（0、1、2）。

**输出**：无返回值（`void`）。它只做断言（`expect`），不返回任何值。

**副作用**：无。它不修改任何外部状态、文件或全局数据，只读取 `agent.session.events`、`adapter.requests` 和 `foldRequestHeader` 的结果，并做断言。

**前置条件**（调用前必须满足）：
1. `adapter.requests` 长度必须为 3（第583行 `expect(adapter.requests).toHaveLength(3)`）。
2. `agent.session.events` 中必须恰好有 3 个 `step/start` 事件（第584-585行 `const stepStarts = events.filter(e => e.type === 'step/start'); expect(stepStarts).toHaveLength(3)`）。
3. 对每个 `index`，必须存在一个 `assistant/chunk` 事件，其 `data.turn` 和 `data.step` 与 `stepStarts[index]` 的 `data.turn`/`data.step` 匹配（第587-591行 `events.find(...)` 且用 `!` 断言非空）。
4. `foldRequestHeader(events.slice(0, firstChunk.seq))` 必须返回非空（第602行 `!` 断言）。

**调用后保证**（断言成立时）：
1. 对每个请求，`request.messages` 与用 `events.slice(0, firstChunk.seq)` 重建的全新 Session 的 `deriveMessages()` 完全相等（第596-597行 `expect(structuredClone(request.messages)).toEqual(rebuilt.deriveMessages())`）。
2. `request.model`、`request.reasoningEffort`、`request.system`、`request.tools`、`request.temperature`、`request.maxTokens`、`request.stop` 分别等于 `foldRequestHeader` 返回的 header 的 `config.model`、`config.reasoningEffort`、`system`、`tools`、`config.temperature`、`config.maxTokens`、`config.stop`（第603-609行）。

【调用方须知】这个回调依赖一个关键时序假设：`assistant/chunk` 事件必须严格位于对应的 `step/start` 事件之后、且 `request/header` 快照事件位于 `step/start` 与第一个 chunk 之间（见第598-601行注释）。如果事件日志中 chunk 与 step/start 的对应关系不成立（例如同一 turn 内出现多个 step 或 chunk 顺序被打乱），`events.find` 会返回 `undefined` 并因 `!` 断言直接抛错，整个测试会失败——调用方若修改事件日志的写入顺序或 step 编号规则，必须保证这个「step/start 在 chunk 之前、header 在两者之间」的时序，否则该回调无法通过。

*✓ 核实通过——候选答案准确描述了该回调的输入、输出、副作用、前置条件和保证，且引用的代码行号和内容均与文件实际相符，包括关键时序假设（step/start 在 chunk 之前、header 在两者之间）也正确。*

### [B] tests\request-reconstruction.spec.ts :: (anonymous)（第114行，复杂度6）

第114行的「(anonymous)」是 `it('logs adapter defaults, supports per-turn effort changes, and restores the effective value', async () => {` 这个测试用例的匿名回调函数（vitest 的 it 回调）。它的契约如下：

**输入**：无显式参数（回调不接收参数）。它依赖闭包捕获的外部状态：`MockAdapter`、`harness`、`send`、`waitForIdle`、`ReasoningEffortId`、`SessionId`、`structuredClone` 等。

**输出**：返回一个 Promise（async 函数），测试通过时 resolve，断言失败时 reject。

**副作用**：
1. 创建了一个 `MockAdapter` 实例（第115行 `const adapter = new MockAdapter([textResponse('one'), textResponse('two')], reasoning)`），并注册到 `ctx` 的 LLM 适配器中（通过 `harness` 内部 `ctx.llm.registerAdapter`）。
2. 创建了一个 agent 会话（第118行 `ctx.agentLoop.create(SessionId('effort'), ...)`），并调用 `send(agent, 'first')` 和 `send(agent, 'second')`（第126-129行），这会向 agent 的 session 写入用户消息，并触发 agent 循环产生请求。
3. 注册了一个 `ctx.on('agent/request', ...)` 事件监听器（第119-122行），该监听器在 turn === 2 时修改请求配置的 `reasoningEffort` 为 `max`。
4. 在测试后半段（第140行起），通过 `resumedCtx.agents.create({ sessionId, seed: structuredClone(agent.session.events), ... })` 创建了新的 agent 会话，并传入 `seed` 事件日志，这会修改新会话的状态。
5. 测试结束时没有显式清理这些 agent/事件监听器，但测试框架会处理。

**前置条件**：
1. 需要 `MockAdapter`、`harness`、`send`、`waitForIdle` 等辅助函数可用（它们定义在文件顶部）。
2. 需要 `ReasoningEffortId`、`SessionId` 等类型/函数可用（从 `@deepseek-ai/dsh-llm` 和 `@deepseek-ai/dsh-session` 导入）。
3. 需要 `ctx.on('agent/request', ...)` 事件机制可用（由 AgentLoop 插件提供）。
4. 需要 `structuredClone` 可用（Node.js 全局）。

**调用后保证**：
1. `adapter.requests` 数组包含两个请求，且它们的 `reasoningEffort` 分别为 `high` 和 `max`（第131-135行断言）。
2. `agent.session.events` 中 `request/header` 事件的数量为 2，且它们的 `data.header.config.reasoningEffort` 分别为 `high` 和 `max`（第136-139行断言）。
3. 第一个 header 事件的 `adapterDefaults` 为 `{ reasoningEffort: true }`，第二个为 `undefined`（第140-143行断言）。
4. 两个 header 事件的 `reason` 分别为 `'initial'` 和 `'change'`（第144行断言）。
5. 测试结束时，`agent.session.events` 被用于 `structuredClone` 作为新会话的 seed，因此该事件日志是完整且可复制的。

【调用方须知】最容易被忽略的是：这个测试在 `ctx.on('agent/request', ...)` 中注册的监听器会**永久修改后续所有请求的配置**——它根据 `turn` 参数（第120行 `({ turn }, next) => ...`）在 turn === 2 时把 `reasoningEffort` 改成 `max`，但测试结束后这个监听器仍然挂在 `ctx` 上，如果同一个 `ctx` 被复用（比如在同一个测试文件中后续测试继续用这个 `ctx`），后续请求的 `reasoningEffort` 会被意外改成 `max`，导致其他测试失败。因此调用方必须确保每个测试使用独立的 `ctx`（通过 `harness` 新建），或者显式移除该监听器。

*✗ 核实不通过——候选答案对代码的引用和描述存在多处不准确，尤其是对第114行匿名函数的定位和副作用描述与代码原文不符，因此不能采信。*

### [B] tests\tool-calls.spec.ts :: (anonymous)（第459行，复杂度6）

第459行的「(anonymous)」是 `describe('tool-call scheduler: abort handling', () => {` 这个测试套件的回调函数（第459行 `describe('tool-call scheduler: abort handling', () => {`）。它不是一个独立的可调用函数，而是 vitest 的 `describe` 块，用于组织两个 `it` 测试用例。

**契约（对调用方/测试运行器的承诺）：**

1. **输入**：无显式参数。作为 `describe` 的回调，它不接收任何参数（第459行 `() => {`）。它依赖闭包中导入的 `describe`、`it`、`expect` 等 vitest 全局，以及文件顶部导入的 `MockAdapter`、`multiCall`、`textResponse`、`harness`、`gatedParallelTool`、`CallId`、`TOOL_ABORTED_BEFORE_DISPATCH` 等（第1-30行导入）。

2. **输出**：无返回值（`describe` 回调不要求返回）。它的作用是注册两个 `it` 测试用例，供 vitest 执行。

3. **副作用**：
   - 注册测试用例到 vitest 测试套件（这是 `describe` 的固有行为）。
   - 每个 `it` 内部会创建 `Context`、注册插件、创建 agent、监听事件、调用 `agent.followup` 并 `await waitForIdle`，这些会修改内存中的 `ctx`、`agent`、`gated` 等局部状态，但不会修改文件或全局数据（测试结束后这些局部对象被丢弃）。
   - 测试中通过 `ctx.on('session/event', ...)` 注册的事件监听器会在测试期间触发 `agent.cancel({ kind: 'user' })`（第470行附近），这会改变 agent 的运行状态。

4. **前置条件**：
   - 测试运行器（vitest）已初始化，`describe`/`it`/`expect` 可用。
   - 文件顶部所有依赖包（`@deepseek-ai/cordis`、`dsh-llm`、`dsh-session`、`dsh-tools`、`dsh-agent-loop` 等）已正确安装并导出所需符号（第1-30行）。
   - `MockAdapter`、`multiCall`、`textResponse`、`harness`、`gatedParallelTool` 等辅助函数在测试文件内已定义或导入（第1-30行及文件其他部分）。

5. **调用后保证**：
   - 两个 `it` 测试用例会被注册并执行：
     - 第一个 `it('starts no calls when the signal is already aborted before a parallel group', ...)`（第462行起）：验证当信号在并行组前已中止时，不会启动任何工具调用（`expect(gated.started).toEqual([])`），但会发出 `tool/call` 事件（`c1`、`c2`），且每个调用产生 `AbortError` 结果（`isError: true`，`error.code === TOOL_ABORTED_BEFORE_DISPATCH`）。
     - 第二个 `it('skips dispatch and stops starting siblings when abort fires during ordered pre-execute', ...)`（第477行起）：验证在有序 pre-execute 期间触发 abort 时，跳过 dispatch 并停止启动兄弟调用（`gated.started` 为空，`tool/call` 事件为 `c1`、`c2`，结果均为 `AbortError`）。
   - 测试执行后，`gated.started`、`events(agent)` 等断言会验证调度器行为符合预期。

【调用方须知】这个 `describe` 块本身没有可调用的行为，但它的两个测试用例都依赖 `agent.cancel({ kind: 'user' })` 在 `session/event` 监听器或 `tools/pre-execute` 监听器中触发——如果测试运行器或 mock 适配器没有正确模拟 `agent.cancel` 的异步行为（例如 cancel 是同步返回而测试期望异步等待），或者 `waitForIdle` 没有等待所有 abort 处理完成，测试会因 `gated.started` 或 `tool/result` 事件数量不符而失败。最容易被忽略的是：这两个测试都断言 `tool/call` 事件仍然会发出（即使调用被中止），且 `tool/result` 的 `error.code` 必须是 `TOOL_ABORTED_BEFORE_DISPATCH`——如果调度器在 abort 时完全跳过发出 `tool/call` 或错误码不同，测试会失败，这要求调度器在 abort 时仍要发出 `tool/call` 事件并附带特定错误码。

*✓ 核实通过——我逐行核对了第459行起的 describe 块及其两个 it 测试用例，候选答案对输入、输出、副作用、前置条件和调用后保证的描述均与代码实际内容相符，没有发现不实之处。*


### 批次「agent-tool-presentation」

# 项目体检报告

共3个文件（另有0个不支持的文件类型被跳过），总行数233

## 项目叙述（✓ 核实通过）

项目定位描述如下（依据：README.md / README.zh.md、src/index.ts、src/invariant.ts、tests/agent-tool-presentation.spec.ts）：

## 1. 项目是什么
`dsh-agent-tool-presentation` 是一个 Cordis 插件（agent preset 的一行），用来声明「模型看到的工具是哪种形态」：`native`（全部工具 schema）、`code`（只有 `run_code` 加一份生成的 TypeScript SDK）、`both`（两者都要）。它解决的是：工具注册表本身留在宿主平面（agent loop 的调度器、apiproxy 的 presenter、各工具插件都是它的消费者，无法下沉进 preset），而 preset 能拥有的是这份注册表的**呈现方式**——`ctx.tools.presentAs()` 只为正在挂载的那个 agent 声明，从而让一个 Code Mode 会话与多个 native 会话同进程并存，各自看到各自的清单。

## 2. 模块/文件职责
- `src/index.ts`：插件主体。导出 `name='tool-presentation'`、`inject=['tools']`（注意 `codeRuntime` 不在静态 inject 里，因为 native 行必须在无 runtime 的部署上也能挂载）、`Config`（`mode` 必填，`z.union(['native','code','both']).required()`）、`apply(ctx, config)`——native 立即 `presentAs('native')`；code/both 则 `ctx.inject(['codeRuntime'], ...)` 等待宿主平面的 code runtime 到达后再 `presentAs(config.mode)`。
- `src/invariant.ts`：不变式伴生插件（`tool-presentation-invariant`），注册到 `dsh-invariants`，但 `install` 是空实现——本包没有自己的运行时不变式，它建立的「哪个 agent 用哪种呈现」关系由 `dsh-tools` 持有。
- `tests/agent-tool-presentation.spec.ts`：行为测试，覆盖了下面所有不变量。

## 3. 关键不变量（含证据范围）

**不变量 A：声明只作用于挂载它的那个 agent，不影响其它 agent。**
证据：`tests/agent-tool-presentation.spec.ts` 的 `'gives its own agent Code Mode and leaves the rest native'`——同一 host 上挂 `code` 的 `coded` 和 `native` 的 `plain`，分别 assemble 后 `codedAssembly.tools` 只有 `[RUN_CODE_NAME]`，`plainAssembly.tools` 是 `['echo']`。入口是 `ctx.systemPrompt.assemble({ scope })`。

**不变量 B：`code` 模式下，通告面与可调用面一致——模型只能直接调用 `run_code`，其它工具解析为 `UNKNOWN_TOOL`。**
证据：README.md / README.zh.md 的「Model Experience」段，引用 `dsh-tools` 的投影规则和 executor-collapse note（`../../../.agents/notes/implemented/bug-fix/2026-08-07-code-mode-executor-collapse.md`）。注意：这条规则的实际执行在 `dsh-tools` 里，本包只是通过 `presentAs('code')` 触发它；本包自身代码（src/index.ts）没有直接实现 `UNKNOWN_TOOL` 解析。

**不变量 C：`both` 模式同时呈现两种形态。**
证据：`'presents both forms when asked for both'`——assemble 后 tools 为 `['echo', RUN_CODE_NAME]`。

**不变量 D：声明随 agent 卸载而撤销，恢复部署默认值，不残留。**
证据：`'restores the deployment default when the agent unloads'`——`row.dispose()` 后 assemble 回落到 `['echo']` 且无 `tools:sdk` section。这是 HMR 安全要求。

**不变量 E：code 模式在未组装 runtime 的部署上必须停在 pending，而不是乐观应用。**
证据：`'waits for a code runtime the deployment does not compose'`——`host({runtime:false})` 下挂 `code`，`row.ctx.get('codeRuntime')` 为 undefined，assemble 仍回落到 `['echo']`；`'applies once the runtime arrives'`——之后 `ctx.plugin(StubRuntime)` 再 assemble 就变成 `[RUN_CODE_NAME]`。README 说明这样做的理由：乐观应用会把失败推迟到会话第一次请求，那时操作者既改不了 preset 也改不了组装；停在 pending 则让 `dsh-agent-presets` 在挂载时指名此 id 拒绝，失败发生在激活审计里。

**不变量 F：`mode` 必填，省略即报错。**
证据：`'requires a mode rather than defaulting one'`——`Config({} as never)` 抛错。README 解释：不带这一行的 preset 本来就会拿到部署默认值，省略等于白组装。

**不变量 G：同一组装里第二次声明被拒绝而不是合并。**
证据：README.md / README.zh.md 的「一个 agent 只声明一次呈现方式……第二次声明会被拒绝而不是合并」——但**注意**：这条只在 README 文字里声明，`src/index.ts` 和测试里都没有直接实现/验证「拒绝第二次声明」的代码路径。所以这条不变量目前只有文档证据，没有代码/测试证据，范围要写窄：仅 README 声称，未在代码中观察到实现。

**不变量 H：`inject` 只声明 `['tools']`，不把 `codeRuntime` 放进静态 inject。**
证据：`'declares the services it uses without holding a code runtime hostage'`——`expect(inject).toEqual(['tools'])`；src/index.ts 注释也明确说明 `codeRuntime` 不列在 inject 里，等待是 `apply` 内部条件性的。这是 native 行能在无 runtime 部署上挂载的前提。

**不变量 I：本包没有自己的运行时不变式（invariant 为空实现）。**
证据：src/invariant.ts 的 `install = () => {}`，注释说明它只注册包名、不持有事件或快照，关系由 `dsh-tools` 观察。

**入口覆盖说明**：本包只有一个入口——`apply(ctx, config)`（由 preset 组装时调用），没有 CLI 或 HTTP 入口。上述不变量 A–F、H 都在 `tests/agent-tool-presentation.spec.ts` 中通过 `mount()`（内部用 `createScope` 模拟 preset 子树挂载）验证，入口是 `ctx.plugin({name, inject, Config, apply}, config)`。不变量 G 只有 README 文档证据，无代码/测试证据。

## 4. 设计特点/取舍
- **注册表留在宿主平面，preset 只拥有呈现**：这是核心取舍——不把注册表搬进 preset，因为它的消费者全在宿主平面；preset 通过 `presentAs()` 声明呈现，实现「一个进程里 Code Mode 与 native 并存」。
- **等待而非乐观应用**：code 模式对 runtime 采用「等待到达」而非「先应用再失败」，把失败从会话第一次请求提前到挂载时，让操作者能在激活审计里看到并处理。
- **`mode` 必填而非默认**：避免「省略 = 白组装」的歧义。
- **声明随 agent 卸载而撤销**：保证 HMR 安全，呈现不残留。
- **无自身不变式**：本包刻意不持有状态，把「哪个 agent 用哪种呈现」的关系交给 `dsh-tools` 持有，自己只做一次 scoped 调用。
- **已知限制**：运行时仍在宿主平面——preset 能选 Code Mode 但带不来 TypeScript 运行时，未组装 runtime 的部署无法组装任何 code 模式 preset（README「Known Limitations」）。

## 行为 vs 项目叙述 对照结果

共0个函数：0个违反不变量、0个无法判断、0个支撑项目正确运行（不再展开）


## 复杂度分级分布

- [A] 27个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [A] src\index.ts :: apply（第59行）复杂度=2
  [A] tests\agent-tool-presentation.spec.ts :: host（第31行）复杂度=2
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第66行）复杂度=2
  [A] src\index.ts :: (anonymous)（第69行）复杂度=1
  [A] src\invariant.ts :: install（第23行）复杂度=1
  [A] src\invariant.ts :: apply（第30行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: run（第25行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: render（第40行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: execute（第41行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第50行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: mount（第47行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第60行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第74行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第75行）复杂度=1
  [A] tests\agent-tool-presentation.spec.ts :: (anonymous)（第76行）复杂度=1

## 行为描述明细（B级以上，共0个）


### 批次「scope」

# 项目体检报告

共8个文件（另有0个不支持的文件类型被跳过），总行数1207

## 项目叙述（✓ 核实通过）

这个项目是 `@deepseek-ai/dsh-scope`，一个 Cordis 的“作用域注册原语”库。它解决的是：在同一个 Cordis 进程里，多个 agent（或其它实体）共享同一套服务/事件总线时，如何把“注册的可见性”和“注册的生命周期/所有权”绑定到同一个作用域身份上，避免一个注册在 A 作用域可见、却在 B 作用域被销毁，以及如何让事件只路由给同一作用域（或祖先作用域）的监听器。它面向的是 Cordis 插件体系下的多 agent 运行时（agent loop 为每个 live agent 建一个 scope，agent preset 的 standing mount 作为其父 scope），但机制本身与 agent 无关，低层包可独立使用。

## 模块组成与职责边界
- `src/index.ts`：核心原语。`createScope(ctx, key, options)` 铸造一个带标签的 Cordis 上下文（`Scope.ctx`），其 backing fiber 拥有所有经它注册的东西；`scopeOf(ctx)` 读最近标签；`scopeTarget(base, key)` 构造只含路由状态的事件 carrier（`Scoped<T>` 是编译期不透明品牌，事件参数携带真实 subject）；`bindScopeParent`/`scopeParentOf`/`scopeChainOf` 维护 key 级父链（注册视图向下继承、事件准入向上扩展）。
- `src/store.ts`：共享存储。`NamedEntries`（按名、插入序、调用方自持重复诊断、精确幂等 undo）、`AnonymousEntries`（匿名、等值独立注册、同样迭代边界）、`ScopedLayers`（一个 registry 的全局层 + 惰性精确作用域层，`peek` 不创建且链盲、`chainLayers` 祖先优先、`merge` 最近者胜、`effect` 从同一上下文同时推导可见性与所有权并返回精确 Cordis disposer）。
- `src/invariant.ts`：可选 companion 插件（`@deepseek-ai/dsh-scope/invariant`），在 `internal/dispatch` 上断言每个声明为 scope-filtered 的事件必须带 carrier，且当 payload 暴露路由 subject 时 carrier key 必须与 subject 同一对象。
- `src/scoped-events.generated.ts`：由 Program 生成的 subject 解析器映射（`agent/*`、`approval/request`、`goal/changed`、`system-prompt/assemble`、`tools/*` 等），供 invariant 使用；`null` 表示仅查 carrier 存在性。
- `tests/`：`scope.spec.ts`、`store.spec.ts`、`invariant.spec.ts` 覆盖上述行为。

## 关键不变量（含证据范围）
1. **注册的可见性与所有权必须来自同一个上下文**（`ScopedLayers.effect` 用 `scopeOf(ctx)` 决定层、用 `ctx.effect` 决定 disposer）。证据：`src/store.ts` 的 `ScopedLayers.effect`（`const scope = scopeOf(ctx)` 后 `ctx.effect(...)`），以及 `tests/store.spec.ts` 的“uses the same scoped context for lazy visibility and ownership”用例。
2. **`peek` 永不创建层、且链盲**（一个 scope 自己的贡献不得静默吸收祖先的）。证据：`src/store.ts` `peek` 只 `this.scoped.get(scope)` 不 set；`tests/store.spec.ts` 的“constructs global state eagerly while reads stay non-creating”用例（`peek(key)` 后 `created` 仍为 `[undefined]`）。
3. **作用域层只在完整聚合为空时才回收**（`isEmpty()` 控制）。证据：`src/store.ts` `effect` 的 yield 清理分支 `if (scope !== undefined && layer.isEmpty()) this.scoped.delete(scope)`；`tests/store.spec.ts` 的“uses the same scoped context...”用例（删掉 named 和 tail 后 `peek` 仍存在，删掉 anonymous 后才 `undefined`）。
4. **事件准入沿父链向上、绝不向下**：带祖先 tag 的监听器接收后代 key 的事件，带后代 tag 的监听器不接收祖先 key 的事件。证据：`src/index.ts` `scopeTarget` 的 filter 循环 `for (let cursor = key; cursor !== undefined; cursor = scopeParents.get(cursor))`（只向上走）；`tests/scope.spec.ts` 的“admits an ancestor-tagged listener for a descendant dispatch, never the reverse”用例（agent 分发时 preset+agent+untagged 都收到；preset 分发时 agent 不收到）。
5. **父链绑定一次、重链只能通过原 binder 持有的 binding、且任何 bind/rebind 都拒绝成环**。证据：`src/index.ts` `bindScopeParent`（`scopeParents.has(key)` 抛错、`linkScopeParent` 循环检测）、`ScopeParentBinding.rebind`；`tests/scope.spec.ts` 的“links at mint...rejects cycles”和“re-links only through the binding held by the original binder”用例。
6. **`Scope.dispose()` 幂等、共享同一 quiescence 边界，且 `rawDispose` 是精确的 Cordis disposer**（可嵌套进有序复合 effect）。证据：`src/index.ts` `createScope` 返回 `dispose: () => (disposing ??= quiesceFiber(fiber))`、`rawDispose: fiber.dispose`；`tests/scope.spec.ts` 的“shares quiescence across repeat and raw-disposer-first calls”和“exposes the exact raw disposer for ordered composite teardown”用例。
7. **`{ global: true }` 监听器保留 Cordis 全局语义**（绕过 scope 过滤）。证据：`src/index.ts` `scopeTarget` 只组合 `Context.filter`，不触碰 global 监听器路径；`tests/scope.spec.ts` 的“`{ global: true }` listeners retain Cordis global-listener semantics”用例。
8. **每个 scope-filtered 事件必须带 carrier，且 carrier key 必须与 payload 的 subject 同一对象**（仅对 `scoped-events.generated.ts` 中列出的 25 个事件成立；`null` 解析器只查 carrier 存在性）。证据：`src/invariant.ts` 的 `internal/dispatch` 处理器；`src/scoped-events.generated.ts` 的映射；`tests/invariant.spec.ts` 的“checks every generated subject resolver against the carrier key”和“requires carriers for generated presence-only scoped events”用例。注意：这条不变量只覆盖生成器列出的那些事件，其它事件不在断言范围内。
9. **`NamedEntries`/`AnonymousEntries` 的迭代器在表被清空后与后续插入分离**（drained-generation 边界），且 undo 精确幂等。证据：`src/store.ts` 两个类的 `insert`/`append`（清空时 `this.data = new Map()`）与 undo 的 `active` 标志；`tests/store.spec.ts` 的“starts a fresh iterator generation after the table drains”两个用例。
10. **`effect` 的 action 在通知前执行、undo 在通知后执行、失败时回滚且不丢弃已存在的层**。证据：`src/store.ts` `effect` 的 try/catch 与 yield 顺序；`tests/store.spec.ts` 的“runs action, notification, undo, and disposal notification in order”和“cleans up failed factories and empty failed actions without discarding an existing layer”和“rolls back a scoped insertion when notification throws”用例。

## 设计特点与取舍
- **可见性与所有权同源**：注册上下文同时决定“谁能看到”和“谁负责销毁”，这是核心设计契约（README “Design contract”）。
- **作用域不是沙箱/权限边界**：README 明确“Scopes route trusted same-process plugins; they are not sandboxes or authority boundaries”，并引用 agent-scope Agent Note 的 security non-goals。
- **key 级父链而非上下文标签级**：一个上下文只携带一个最近 scope key，层级关系存在 key 的 parent 关系里；多成员策略集不支持（README “Known Limitations”）。
- **carrier 是纯路由状态、不透明品牌**：`Scoped<T>` 不暴露 subject 属性，真实 subject 只经事件参数传递；`isScopeCarrier`/`carrierKeyOf` 用 WeakMap 记录 key。
- **服务可达性来自 scope 铸造者**：`Scope.ctx` 同时暴露铸造插件的依赖 API，更宽的 minter 无法被 holder 收窄（README “Known Limitations”）。
- **只有 scope-aware API 才隔离状态**：任意 Cordis 服务经 scoped context 调用仍是全局的，除非 registry 用 `scopeOf` 归档、事件用 `scopeTarget` 分发（README “Known Limitations”）。
- **共享存储不定义 registry 特定过滤/迭代策略**：`EntryValues` 保持内部，存储类从包根导入而非 `/store` 子路径（README “Design contract”）。
- **`effect` 返回精确的 Cordis disposer**（保持 effect 身份，供嵌套/去重），而非包装器（`src/store.ts` 的 `return dispose` 及 oxlint 注释）。

## 行为 vs 项目叙述 对照结果

共1个函数：0个违反不变量、0个无法判断、1个支撑项目正确运行（不再展开）

### 支撑项目正确运行（1个，不再展开）

src\index.ts::cordisContext.filter


## 复杂度分级分布

- [A] 136个函数/类
- [B] 1个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [B] src\index.ts :: cordisContext.filter（第173行）复杂度=6
  [A] src\invariant.ts :: (anonymous)（第17行）复杂度=5
  [A] src\store.ts :: (anonymous)（第249行）复杂度=5
  [A] src\store.ts :: (anonymous)（第48行）复杂度=4
  [A] src\store.ts :: (anonymous)（第127行）复杂度=4
  [A] src\store.ts :: (anonymous)（第257行）复杂度=4
  [A] src\store.ts :: (anonymous)（第233行）复杂度=4
  [A] src\index.ts :: linkScopeParent（第54行）复杂度=3
  [A] src\index.ts :: dispose（第145行）复杂度=3
  [A] src\index.ts :: isScopeCarrier（第192行）复杂度=3
  [A] src\store.ts :: (anonymous)（第230行）复杂度=3
  [A] tests\store.spec.ts :: (anonymous)（第222行）复杂度=3
  [A] src\index.ts :: bindScopeParent（第72行）复杂度=2
  [A] src\index.ts :: scopeChainOf（第98行）复杂度=2
  [A] src\index.ts :: quiesceFiber（第115行）复杂度=2

## 行为描述明细（B级以上，共1个）

### [B] src\index.ts :: cordisContext.filter（第173行，复杂度6）

函数「cordisContext.filter」位于 src/index.ts 第173行，是 scopeTarget 内部创建的 carrier 对象上的一个方法（`[CordisContext.filter](ctx: Context): boolean`）。

**契约描述**

1. **输入**：一个 `Context` 对象 `ctx`（第173行 `(ctx: Context)`）。
2. **输出**：一个布尔值，表示该 context 是否被此 carrier 接受（第173行 `: boolean`）。
3. **副作用**：无直接副作用。它不修改任何外部状态、文件或全局数据。它只读取闭包变量 `baseFilter`、`key`、`scopeParents` 和 `scopeOf` 的结果。唯一的外部写入发生在 scopeTarget 创建 carrier 之后（第199行 `carrierKeys.set(carrier, key)`），但这不是 filter 函数本身的行为。
4. **前置条件**：
   - 调用前，`baseFilter` 已从 `base` 的 `[CordisContext.filter]` 属性读取（第171行），如果 `base` 没有该属性则为 `undefined`。
   - `key` 是 scopeTarget 的第二个参数，可为 `undefined`。
   - `scopeParents` 是模块级 WeakMap，需已通过 `bindScopeParent` 建立父子关系（第61-63行）。
   - `ctx` 上可能带有 `kScope` 符号标记（由 `createScope` 写入，第127行 `fiber.ctx.extend({ [kScope]: key })`）。
5. **调用后保证**：
   - 如果 `baseFilter` 存在且对 `ctx` 返回 `false`，则 filter 返回 `false`（第174行 `if (baseFilter !== undefined && !baseFilter.call(base, ctx)) return false`）。
   - 如果 `ctx` 没有 scope 标记（`scopeOf(ctx)` 返回 `undefined`），则返回 `true`（第176行 `if (tag === undefined) return true`）——即无标记的 context 被无条件接受。
   - 如果 `ctx` 有标记 `tag`，则遍历从 `key` 开始的父链（`scopeParents`），若链上某个键等于 `tag` 则返回 `true`（第177-179行）；否则返回 `false`（第180行）。
   - 因此，接受条件为：`baseFilter` 通过（或不存在）且（`ctx` 无标记 或 `ctx` 的标记是 `key` 或其祖先）。

**【调用方须知】**：最容易被忽略的是——这个 filter 对**无 scope 标记的 context 无条件放行**（第176行 `if (tag === undefined) return true`），这意味着任何未通过 `createScope` 打上 `kScope` 标记的 context（例如直接由 Cordis 根 context 派生的普通 context）都会被此 carrier 接受，即使它们不属于 `key` 的 scope 链。如果你期望 carrier 只接受特定 scope 链上的事件，必须确保所有相关 context 都经过 `createScope` 打标，否则未打标的 context 会绕过 scope 路由逻辑。

*✓ 核实通过——候选答案逐条对应代码：输入、输出、副作用（filter 本身无写入，仅闭包读取）、前置条件（baseFilter 读取、scopeParents 建立、kScope 标记）、调用后保证（baseFilter 短路、无标记放行、父链匹配）均与源码一致，且【调用方须知】准确指出无标记 context 被无条件接受这一关键行为。*


### 批次「session」

# 项目体检报告

共24个文件（另有0个不支持的文件类型被跳过），总行数8377

## 项目叙述（✓ 核实通过）

项目定位描述（基于对 src/ 下各文件的直接阅读）：

## 1. 项目是什么
`@deepseek-ai/dsh-session` 是一个**事件溯源（event-sourced）的会话日志与内存存储**包，面向 agent 运行框架（如 `dsh-agent-loop`）。核心思想：`Session` 是 agent 全部交互历史的**只追加（append-only）事实源**，LLM 消息历史是从它**派生**出来的，而不是独立存储。持久化不是本包职责，由插件订阅 `session/event`、在 `session/flush` 时落盘。

## 2. 模块/文件职责
- **src/index.ts**：`Session` 类（append-only 日志、`deriveMessages` 派生消息、`requestHeader`/`requestContext` 折叠、`events` 冻结快照）与 `SessionStore` 服务（`ctx.sessions`，负责 create/prepare/enter/announce/flush/fork/get/list）。
- **src/surface.ts**：有序 surface 层——`SurfaceManager` 增量维护模型可见消息序列，`foldSurface` 全量重放，`deriveEventMessage` 单事件投影规则，`isSurfaceEvent`/`isAppendSurfaceEvent`/`isReplacementSurfaceEvent` 类型守卫。
- **src/types.ts**：事件词汇表 `SessionEventMap`、`SessionHeader`、`SurfaceOp`、`TurnEndReasonMap`、`SESSION_FORMAT_VERSION`。
- **src/json.ts**：无损 JSON 校验与快照（`isJsonValue`/`snapshotJsonValue`），迭代式遍历，拒绝循环/稀疏/负零/非有限数/异类原型。
- **src/repair.ts**：崩溃恢复——`interruptedTurnClosers` 为未闭合的尾部 turn 生成合成 `tool/result`/`step/end`/`turn/end`。
- **src/request-header.ts**：`request/header` 事件折叠（`foldRequestHeader`）、规范化（`canonicalHeader`）、相等比较（`headerEquals`）。
- **src/chunk-rows.ts**：存储编解码——把连续同块 delta chunk 事件打包成一行（`packChunkRuns`），解码还原（`decodeStorageRecord`），未知/畸形行原样保留或报错。
- **src/invariant.ts**：可选关系不变量伴生插件（`session-invariant`），校验 seq 单调、turn/step 嵌套、同 step 工具调用/结果配对。
- **src/preparation.ts**：未发布 Session 的所有权包装（`SessionPreparation`，Disposable）。
- **src/known-event-types.ts**：本仓库已知事件类型集合（生成文件）。

## 3. 关键不变量（含证据范围）

### 3.1 事件 seq 必须从 0 连续递增，且 `seq = log.length`
- **证据**：`src/index.ts` 构造函数对 seed 逐条断言 `snapshot.seq !== index` 抛错（`seed must be contiguous from 0`）；`Session.seq` getter 直接返回 `this.log.length`；`src/surface.ts` `planSurfaceEvent` 断言 `event.seq !== expectedSeq` 抛错。
- **覆盖入口**：`Session.create`（seed 路径）、`Session.fromRestore`（restore 路径）、`Session.append`（通过 `surfaceManager.validateNext` 的 expectedSeq）、`foldSurface`（全量重放）。所有入口一致。

### 3.2 事件数据必须无损 JSON 可序列化，且 append 时快照（读一次、验证一次、拷贝一次）
- **证据**：`src/index.ts` `append` 先 `snapshotJsonValue(data)`，undefined 即抛错；`src/json.ts` 文档明确“one read per property, so a stateful getter cannot change between validation and copying”。
- **覆盖入口**：`Session.append`（唯一写入口）、`Session.create`/`fromRestore` 的 seed 校验（`snapshotJsonValue(source)`）。

### 3.3 消息事件（user/message、assistant/message、tool/result）必须带 `surfaceOp`；非 surface 事件禁止带 `surfaceOp`/`sourceEventSeqs`
- **证据**：`src/surface.ts` `surfaceOpOf`：surface-eligible 类型缺 marker 抛错，非 surface 类型带 marker 抛错。
- **覆盖入口**：`Session.append`（经 `validateNext`）、`foldSurface`、`Session.create`/`fromRestore` seed 校验（`surfaceManager.validateNext`）。

### 3.4 surface 替换（`replace`）必须：start/end 都是当前 surface 节点、start ≤ end、`sourceEventSeqs` 覆盖所有被遮蔽节点；tool/result 替换只能改 content
- **证据**：`src/surface.ts` `replacementRange`（找不到 start/end 或 start>end 抛错）、`assertProvenance`（缺失遮蔽节点抛错）、`assertToolResultRewrite`（除 content 外任何差异抛错）。
- **覆盖入口**：`Session.append`（经 `validateNext`）、`foldSurface`、seed 校验。

### 3.5 已接受事件及其嵌套数据被深度冻结，日志只追加不可变
- **证据**：`src/index.ts` `append` 用 `deepFreeze` 构造事件；`events` getter 返回 `Object.freeze([...this.log])` 快照；`adoptSessionEvent`/`snapshotSessionEvent` 深度冻结消息。
- **覆盖入口**：`Session.append`、`Session.create`/`fromRestore`（seed 冻结）。

### 3.6 turn/step 嵌套：turn/start 必须递增且无嵌套，turn/end 必须匹配打开 turn 且 step 已关，step/start 必须匹配打开 turn 且 step 递增，step 内事件必须命名当前 turn/step
- **证据**：`src/invariant.ts` `validateEvent` 的 turn/start、turn/end、step/start、step/end、assistant/chunk、assistant/message、tool/call、tool/result 分支。
- **覆盖入口**：仅 `session-invariant` 伴生插件（`internal/dispatch` 预校验 + `session/event` 提交）。**注意**：这是可选插件，未加载时这些关系不变量不生效；`Session.append` 本身不校验 turn/step 嵌套（只校验 surface 元数据）。

### 3.7 同 step 工具调用/结果配对：append 的 tool/result 必须有先前 tool/call（除非是合成 TOOL_NOT_STARTED）
- **证据**：`src/invariant.ts` `tool/result` 分支：`!trace.pendingCalls.has(callId) && !syntheticNotStarted` 抛错。
- **覆盖入口**：仅 `session-invariant` 插件。同样非核心 append 路径强制。

### 3.8 派生消息只来自 surface 节点，非 surface 事件（chunk/边界/usage）不产生消息；空内容 assistant/message 不产生消息
- **证据**：`src/surface.ts` `deriveEventMessage`：非 surface 类型返回 null，空 content assistant/message 返回 null；`src/index.ts` `deriveMessages` 遍历 `surface.nodes`。
- **覆盖入口**：`Session.deriveMessages`、`Session.deriveEventMessage`、外部 `foldSurface` + `deriveEventMessage` 组合。

### 3.9 派生消息缓存按 surface 节点增量投影，surface 重写（replace）时重建缓存
- **证据**：`src/index.ts` `deriveMessages`：`generation !== this.derivedGeneration` 时清空缓存重建；`src/surface.ts` `SurfaceManager.replaceGeneration` 每次 replace 递增。
- **覆盖入口**：`Session.deriveMessages`。

### 3.10 request/header 折叠取最新快照；legacy delta 格式和 `fallback` reason 被拒绝
- **证据**：`src/request-header.ts` `foldRequestHeader` 只取最后一个 `request/header`；`src/index.ts` `assertSupportedRequestHeader` 对 `request/header-delta` 和 `reason === 'fallback'` 抛错。
- **覆盖入口**：`Session.append`（append 时拒绝）、`Session.create`/`fromRestore` seed 校验（`assertSupportedRequestHeader`）。

### 3.11 fork 边界必须存在、连续，且前缀不能结束在打开 turn 内；child id 不能已存在
- **证据**：`src/index.ts` `_forkSeed`：边界非安全整数/越界/不匹配抛 `INVALID_BOUNDARY`，前缀最后 turn 边界是 `turn/start` 抛 `OPEN_TURN`；`fork` 对已存在 child id 抛 `SESSION_ALREADY_EXISTS`。
- **覆盖入口**：`SessionStore.fork`（唯一入口）。

### 3.12 崩溃恢复：未闭合尾部 turn 生成确定性合成事件（先 tool/result，再 step/end，再 turn/end），时间戳复用最后真实事件
- **证据**：`src/repair.ts` `interruptedTurnClosers`：`seq = last.seq + 1`、`time = last.time`，按 pendingCalls → openStep → turn/end 顺序生成。
- **覆盖入口**：`interruptedTurnClosers`（导出函数，由持久化/恢复路径调用）。

### 3.13 存储编解码：未知行原样保留，畸形 chunk 行抛错；打包只针对白名单形状
- **证据**：`src/chunk-rows.ts` `decodeStorageRecord`（非 row 标签原样返回，row 标签经 `validateRow` 抛错）、`classify`（白名单外返回 undefined 原样存储）。
- **覆盖入口**：`packChunkRuns`/`decodeStorageRecord`（导出函数）。

## 4. 设计特点与取舍
- **事件溯源 + 派生历史**：日志是唯一事实源，消息历史是投影，`replace` 只遮蔽 surface 节点而不删除原始日志（`src/surface.ts`、`src/index.ts` `deriveMessages` 注释）。
- **持久化刻意不在本包**：通过 `session/event`/`session/flush` 事件让插件落盘（`src/index.ts` 顶部注释、`SessionStore` 注释）。
- **无损 JSON 单遍快照**：`src/json.ts` 迭代式遍历，避免调用栈深度限制，且一次读取防止 getter 不一致。
- **浏览器安全**：`src/surface.ts` 顶部注释明确避免 `node:` 导入（供 web 客户端消费）。
- **版本固定为 0**：`src/types.ts` `SESSION_FORMAT_VERSION = 0`，不承诺兼容，未知必需事件拒绝重建（`ignorable` 标记例外）。
- **合并可扩展**：`SessionEventMap`/`TurnEndReasonMap` 支持插件声明合并（`src/types.ts`），插件拥有自己合并事件的关系不变量（`src/invariant.ts` 默认分支交给插件）。
- **有序生命周期原语**：`prepare`/`enter`/`announce` 拆分，供 `dsh-agent-loop` 把会话拆除与 loop 最终 flush 按序折叠（`src/index.ts` `create`/`enter`/`announce` 注释）。
- **chunk 行打包**：`src/chunk-rows.ts` 把连续 delta chunk 压缩成一行（约 56× 压缩），但未知/畸形行宁可保留原样或报错也不丢数据。

**范围限制说明**：turn/step 嵌套与工具配对不变量（3.6、3.7）只在 `session-invariant` 伴生插件加载时生效，`Session.append` 本身不强制；其余不变量（seq 连续、JSON 无损、surface 元数据、冻结、header 折叠、fork 边界、崩溃恢复、编解码）在核心 `Session`/`SessionStore` 路径上强制。

## 行为 vs 项目叙述 对照结果

共29个函数：0个违反不变量、9个无法判断、20个支撑项目正确运行（不再展开）

### 无法判断（9个——不代表没问题，只是材料不够判断，值得人工看一眼）

- src\chunk-rows.ts :: validateRow —— 行为描述仅涉及私有校验函数 validateRow 的结构校验细节，未提及任何项目定位描述中列出的不变量（如 seq 连续、JSON 无损、surface 元数据等），且该函数属于存储编解码内部实现，材料不足以判断其是否违反或支持这些不变量。
- src\chunk-rows.ts :: validateRunData —— 行为描述仅涉及存储行内部字段类型校验，未提及任何项目定位描述中的不变量（如 seq 连续、JSON 无损、surface 元数据等），且函数为私有辅助函数，无法判断其是否支撑或违反核心不变量。
- src\index.ts :: validateSessionHeader —— 行为描述仅涉及 header 对象的原地冻结，未提及任何与 seq 连续、JSON 无损、surface 元数据、冻结、header 折叠等不变量相关的具体细节，材料不足以判断是否违反不变量。
- src\index.ts :: assertAdapterDefaults —— 行为描述仅涉及 adapterDefaults 中 reasoningEffort 与 maxTokens 的校验逻辑，未提及项目定位描述中任何具体不变量（如 seq 连续、JSON 无损、surface 元数据等），材料不足以判断是否违反。
- src\index.ts :: hasProviderModel —— 行为描述仅涉及对 provider/model 字段的非空字符串检查，未提及任何项目定位描述中列出的不变量（如 seq 连续、JSON 无损、surface 元数据等），因此无法判断其是否支撑或违反这些不变量。
- src\request-header.ts :: headerEquals —— 行为描述未提及任何与项目定位描述中列出的不变量（如seq连续、JSON无损、surface元数据、冻结等）相关的细节，仅涉及header字段比较逻辑，无法判断其是否支撑或违反这些不变量。
- src\request-header.ts :: canonicalHeader —— 行为描述仅涉及 canonicalHeader 的字段规范化规则，未提及任何与项目定位描述中列出的不变量（如 seq 连续、JSON 无损、surface 元数据、冻结等）相关的细节，材料不足以判断其是否违反或支持这些不变量。
- src\surface.ts :: isDeepEqualJson —— 行为描述未涉及任何列出的不变量（如seq连续、JSON无损、surface元数据、冻结等），仅描述通用深度相等函数，无法判断其是否支撑项目定位。
- tests\properties.spec.ts :: (anonymous) —— 行为描述聚焦于测试回调的交错逻辑与派生历史相等性断言，未涉及项目定位描述中列出的具体不变量（如seq连续、JSON无损、surface元数据、冻结等）的细节，材料不足以判断是否违反任何不变量。

### 支撑项目正确运行（20个，不再展开）

src\chunk-rows.ts::continues、src\chunk-rows.ts::expandRow、src\chunk-rows.ts::packChunkRuns、src\index.ts::assertMessageEventShape、src\index.ts::assertSessionEventEnvelope、src\index.ts::assertCurrentLlmShape、src\index.ts::append、src\index.ts::prepare、src\index.ts::validateRestoredSessionHeader、src\index.ts::assertSupportedRequestHeader、src\index.ts::announce、src\index.ts::validateRestoredSessionHeader、src\invariant.ts::validateEvent、src\repair.ts::interruptedTurnClosers、src\surface.ts::assertProvenance、src\surface.ts::surfaceOpOf、src\surface.ts::isReplaceOp、src\surface.ts::assertToolResultRewrite、src\surface.ts::_processDelta、tests\session.spec.ts::(anonymous)


## 复杂度分级分布

- [A] 670个函数/类
- [B] 18个函数/类
- [C] 8个函数/类
- [D] 2个函数/类
- [E] 1个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [E] src\index.ts :: assertMessageEventShape（第301行）复杂度=31
  [D] src\index.ts :: validateSessionHeader（第96行）复杂度=26
  [D] src\index.ts :: assertSessionEventEnvelope（第213行）复杂度=23
  [C] src\repair.ts :: interruptedTurnClosers（第27行）复杂度=19
  [C] src\chunk-rows.ts :: validateRow（第248行）复杂度=15
  [C] src\index.ts :: assertCurrentLlmShape（第253行）复杂度=14
  [C] src\index.ts :: append（第604行）复杂度=14
  [C] src\index.ts :: prepare（第863行）复杂度=12
  [C] src\surface.ts :: assertProvenance（第211行）复杂度=12
  [C] src\surface.ts :: isDeepEqualJson（第273行）复杂度=12
  [C] src\index.ts :: assertAdapterDefaults（第282行）复杂度=11
  [B] src\chunk-rows.ts :: validateRunData（第229行）复杂度=10
  [B] src\request-header.ts :: headerEquals（第44行）复杂度=10
  [B] src\surface.ts :: surfaceOpOf（第185行）复杂度=10
  [B] src\chunk-rows.ts :: continues（第136行）复杂度=9

## 行为描述明细（B级以上，共29个）

### [C] src\chunk-rows.ts :: validateRow（第248行，复杂度15）

`validateRow` 是 `src/chunk-rows.ts` 第 248 行定义的一个**私有（未导出）函数**，契约如下（依据均为该文件代码原文）：

**输入**：
- `value: Record<string, unknown>` —— 一个已解析的 JSONL 行值（`JSON.parse` 的结果），必须是一个对象（调用方 `decodeStorageRecord` 已用 `isRecord` 保证 `value` 是对象，见第 341 行 `if (!isRecord(value)) return [value as SessionEvent]`）。
- `tag: ChunkRow['type']` —— 必须是三个行标签之一：`'text-chunks'`、`'reasoning-chunks'`、`'tool-call-chunks'`（调用方第 343-344 行已过滤，非这三个标签直接透传）。

**输出**：
- 成功时返回 `ChunkRow`（第 283 行 `return value as unknown as ChunkRow`），即一个通过全部校验的行对象。
- 失败时**抛出异常**（`malformed` 函数，第 220 行 `throw new Error(...)`），不会返回部分结果。

**副作用**：
- **无副作用**。函数是纯校验函数：不写文件、不改全局状态、不改 `value` 本身（只读 `value` 的字段，最后 `return value as unknown as ChunkRow` 只是类型断言，不修改对象）。

**前置条件**：
1. `value` 必须是对象（`isRecord` 已由调用方保证）。
2. `tag` 必须是三个行标签之一（调用方已保证）。
3. 调用方应只在 `value.type` 命中这三个标签时调用（`decodeStorageRecord` 第 343-344 行保证）。

**调用后保证**（校验通过时）：
1. `value` 的 envelope 恰好是 `{type, seq0, time0, data}` 四个键（第 250 行 `hasExactKeys(value, ['type', 'seq0', 'time0', 'data'])`）。
2. `seq0` 是非负安全整数（第 252-254 行），`time0` 是安全整数（第 255-257 行）。
3. `data` 是对象，且对 `tool-call-chunks` 恰好是 `{turn, step, index, id, name?, dt, args}`（`name` 可选但若存在必须是字符串），对 text/reasoning 恰好是 `{turn, step, index, dt, texts}`（第 264-276 行）。
4. `turn`/`step`/`index` 都是数字（`validateRunData` 第 225 行）。
5. payload（`texts` 或 `args`）是非空字符串数组（第 227-229 行）。
6. `dt` 是安全整数数组，且长度恰好等于成员数减一（第 231-236 行）。
7. 所有成员的 seq 和 time 在重建过程中始终保持安全整数（第 278-282 行）——即 `seq0 + payload.length - 1` 是安全整数，且 `time0` 逐项累加 `dt` 后每一步都是安全整数。

**【调用方须知】**：`validateRow` 的校验是**结构精确匹配**（`hasExactKeys` 要求键集合完全一致、不多不少），任何多余字段（例如未来新增的元数据键）都会导致 `malformed` 抛异常——也就是说，一个在编码端被 `classify` 判定为“未知字段、原样存储”的值，如果其 `type` 恰好是 `text-chunks`/`reasoning-chunks`/`tool-call-chunks` 之一，解码端会直接抛错而不是透传；调用方若想对这类带额外字段的行做容错，必须在调用 `validateRow` 之前自行判断，否则会因一个多余键而让整条日志行解码失败。

*✓ 核实通过——我逐行阅读了 `src/chunk-rows.ts` 的 `validateRow` 及其调用的 `validateRunData`、`malformed`、`hasExactKeys`，并核对了 `decodeStorageRecord` 的调用上下文，候选答案对输入、输出、副作用、前置条件和保证的描述均与代码原文一致，且调用方须知准确反映了 `hasExactKeys` 的严格性。*

### [B] src\chunk-rows.ts :: validateRunData（第229行，复杂度10）

validateRunData 是模块私有函数（无 export），契约如下：

**输入**：
- `tag: string` —— 行类型标签，仅用于错误消息（如 'tool-call-chunks'）。
- `data: Record<string, unknown>` —— 行 data 对象，需含 turn/step/index/dt 及 payloadKey 字段。
- `payloadKey: 'texts' | 'args'` —— 指定 payload 字段名。

**输出**：返回 `string[]`，即 `data[payloadKey]` 的强转结果（`return payload as string[]`）。

**副作用**：无外部状态修改。唯一副作用是校验失败时抛出异常（`malformed` 抛 `Error`），不写文件、不改全局。

**前置条件**（调用方需保证）：
- `data` 是对象（调用方 `validateRow` 已用 `isRecord` 检查）。
- `data` 已通过 `hasExactKeys` 精确键检查（tool-call 分支检查了 id/name 类型后才调用）。

**调用后保证**（校验通过时）：
- `data.turn`、`data.step`、`data.index` 均为 number（`typeof data.turn !== 'number'` 等检查）。
- `data[payloadKey]` 是非空字符串数组（`Array.isArray(payload) && payload.length === 0 && payload.some(entry => typeof entry !== 'string')` 均不成立）。
- `data.dt` 是安全整数数组（`dt.some(gap => !Number.isSafeInteger(gap))` 不成立）。
- `dt.length === payload.length - 1`（否则抛错）。
- 返回的数组与 `data[payloadKey]` 是同一引用（`as string[]` 强转，非拷贝）。

**失败行为**：任一条件不满足即抛 `Error`（`malformed` 抛 `malformed ${tag} storage row: ...`），不返回。

【调用方须知】该函数返回的是 `data[payloadKey]` 的**原引用**（`return payload as string[]`），不是拷贝——调用方若修改返回数组会直接改动传入的 `data` 对象；且它只校验 `dt` 是安全整数数组，**不校验 `dt` 长度与 payload 的对应关系之外**的语义（如 dt 是否非负、是否与 seq 相关），这些由调用方 `validateRow` 后续的重建边界检查负责，调用方不能依赖本函数保证 dt 的数值合理性。

*✓ 核实通过——逐条对照代码确认了函数签名、所有校验分支、返回语句和调用上下文，候选答案的每一条描述都有代码原文支撑，没有发现不实之处。*

### [B] src\chunk-rows.ts :: continues（第136行，复杂度9）

函数 `continues(prev, next, kind)` 定义在 src/chunk-rows.ts 第136行，是一个纯函数（无副作用），用于判断两个相邻的 delta 事件 `next` 是否延续以 `prev` 结尾的同一 run。

**输入**：
- `prev: DeltaEvent`、`next: DeltaEvent`：两个 `assistant/chunk` 会话事件（`DeltaEvent = SessionEvent<'assistant/chunk'>`，见第28行）。
- `kind: DeltaKind`：调用方已确定的 delta 类型（`'text-delta' | 'reasoning-delta' | 'tool-call-delta'`，见第25行）。

**输出**：`boolean`——`true` 表示 `next` 延续 `prev` 所在的 run，`false` 表示不延续。

**前置条件**（由调用方保证，函数内不检查）：
- 调用方已确认 `prev` 和 `next` 的 `kind` 相同（docstring 第135行明确写 "same kind already checked by the caller"）。
- 输入事件必须已经通过 `classify` 白名单校验（`DeltaEvent` 类型本身即代表已白名单化，见第28行注释）。

**判定逻辑（全部为纯比较，无副作用）**：
1. `if (next.seq !== prev.seq + 1) return false`——`next` 的 seq 必须是 `prev` 的 seq 加 1（连续序号）。
2. `if (!Number.isSafeInteger(next.time - prev.time)) return false`——时间差必须是安全整数（注释说明：两个安全整数时间差可能超出双精度精确范围，如 2^53-1 与其相反数差约 2^54，此时差值会舍入成非安全整数，故用 `Number.isSafeInteger` 精确检查双向）。
3. `if (next.data.turn !== prev.data.turn || next.data.step !== prev.data.step) return false`——turn 和 step 必须相同。
4. `if (indexOf(next) !== indexOf(prev)) return false`——块索引必须相同（`indexOf` 取 `event.data.chunk.index`，见第128-130行）。
5. 若 `kind !== 'tool-call-delta'`，直接返回 `true`（text/reasoning 只需上述条件）。
6. 对 `tool-call-delta`：取 `toolCallOf(prev)` 和 `toolCallOf(next)`（返回 `{ id, name? }`，见第123-126行），要求：`a.id === b.id` 且 `Object.hasOwn(a, 'name') === Object.hasOwn(b, 'name')` 且 `a.name === b.name`——即 id 相同，且 name 字段的**存在性**和**值**都必须一致（注释第151行："`name` must match in presence AND value — a mixed run is not representable"）。

**副作用**：无。函数只做局部比较，不修改任何外部状态、文件或全局数据。

**调用后保证**：返回 `true` 时，`next` 可安全加入以 `prev` 结尾的 run（run 成员满足 `seq` 连续、时间差为安全整数、turn/step/index 相同，tool-call 时 id 和 name 完全一致），从而可被 `buildRow` 打包成单行（见第155行起）。

【调用方须知】最容易忽略的是第2条时间检查：它不只是检查时间差是否为整数，而是用 `Number.isSafeInteger` 检查差值是否在安全整数范围内——当两个时间戳本身是安全整数但差值超出 2^53 时（例如 `prev.time` 为 2^53-1、`next.time` 为其相反数），减法会舍入成非安全整数而返回 `false`，即使 seq 连续也会拒绝延续；反之，若差值恰好在安全范围内则通过。调用方若依赖时间差做其他计算，需注意这个边界，不要假设只要 seq 连续就必然延续。

*✓ 核实通过——候选答案逐条核对了函数签名、docstring 和函数体，所有引用的代码原文（seq 连续、Number.isSafeInteger 时间差、turn/step/index 相同、tool-call 的 id/name 存在性和值一致）均与源码一致，且确认无副作用，结论准确。*

### [B] src\chunk-rows.ts :: expandRow（第293行，复杂度8）

expandRow 是 src/chunk-rows.ts 第293-330行的一个私有（未导出）函数，契约如下：

**输入**：一个已经通过 validateRow 校验的 ChunkRow（第294行 `function expandRow(row: ChunkRow): SessionEvent[]`）。它假定 row 是三种合法类型之一（text-chunks / reasoning-chunks / tool-call-chunks），且其 data 字段已满足 validateRow 的全部约束（seq0 非负安全整数、time0 安全整数、dt 为安全整数数组且长度 = 成员数-1、payload 为非空字符串数组、重建后的 seq/time 都在安全整数范围内）。

**输出**：一个 SessionEvent[]，按顺序还原出原始事件。每个成员 k 生成一个 `assistant/chunk` 事件（第319-326行）：`seq: row.seq0 + k`，`time` 从 `row.time0` 开始、每步累加 `row.data.dt[k-1]`（第297、300行），`data: { turn: row.data.turn, step: row.data.step, chunk }`（第325行）。chunk 内容按类型还原：text/reasoning 为 `{type:'text-delta'|'reasoning-delta', index, text}`（第302-305行），tool-call 为 `{type:'tool-call-delta', index, id, name?(仅当 row.data 有 name 字段), argumentsDelta}`（第306-313行）。

**副作用**：无。函数是纯函数——不修改 row、不写文件、不改任何全局/外部状态，只构造并返回新数组。

**前置条件**：
1. row 必须是已通过 validateRow 校验的合法 ChunkRow（调用方 decodeStorageRecord 第344行先调 validateRow 再调 expandRow）。
2. row.type 必须是三种合法 tag 之一；default 分支（第315-317行）调用 assertNever 抛错，但注释说明 validateRow 只会返回这三种 tag，所以正常路径不会触发。
3. 对 tool-call-chunks，row.data 的 name 字段存在性决定还原出的 chunk 是否带 name（第311行 `...Object.hasOwn(row.data, 'name') ? { name: row.data.name as string } : {}`）。

**调用后保证**：返回的 events 数组长度等于成员数（members.length），每个事件的 seq 连续递增（seq0, seq0+1, ...），time 按 dt 间隙精确还原（在安全整数范围内无舍入误差），且与 packChunkRuns 打包前的原始事件完全一致（无损往返）。

【调用方须知】expandRow 假定输入已经过 validateRow 校验，它自己不做任何校验——如果直接传入未校验的 row（例如 dt 长度与成员数不匹配、或 seq0/time0 不是安全整数），函数不会报错，而是会静默地通过 `row.data.dt[k-1]` 越界访问（当 k 超过 dt 长度时读到 undefined，`time += undefined` 得到 NaN）或产生错误的 seq/time，导致还原出损坏的事件序列；因此调用方绝不能绕过 validateRow 直接调用 expandRow，必须保证 row 已通过校验。

*✓ 核实通过——候选答案对函数行为、输入输出、副作用、前置条件和保证的描述均与代码原文一致，且引用的行号和代码片段准确。特别是指出的越界风险（dt 长度不匹配时 `row.data.dt[k-1]` 为 undefined 导致 NaN）在代码中确实存在，因为 expandRow 自身不做校验。*

### [B] src\chunk-rows.ts :: packChunkRuns（第192行，复杂度6）

packChunkRuns 的契约（依据 src/chunk-rows.ts 第192-226行函数体及第1-179行辅助函数）：

**输入**：`events: readonly SessionEvent[]`——一个按日志顺序排列的事件批次（第193行）。

**输出**：`StorageRecord[]`——要写入存储的记录，每条对应一行 JSONL（第194行返回类型及docstring）。

**行为/副作用**：纯函数、无状态（docstring 第186行明确说 'Pure and stateless'）。不修改输入数组、不写文件、不改任何全局数据。

**前置条件**：
1. 输入事件需按日志顺序排列（docstring 第187行 'in log order'）。
2. 事件类型需是 `SessionEvent`（含 `assistant/chunk` 等），但函数对任何事件都安全——不认识的形状原样透传（第202-204行 `classify` 返回 undefined 时 flush 后直接 push 原事件）。
3. 无其他前置条件——docstring 第186-187行明确说 'safe over any array, including a batch whose runs were split by flush boundaries'。

**调用后保证**：
1. 每个至少 `MIN_RUN`（=3，第91行）个连续的、被白名单识别的、同 kind、同 block 的 delta chunk 事件会被打包成一个 `ChunkRow`（第197-200行 `flush` 中 `run.length >= MIN_RUN` 才 `buildRow`，否则原样展开）。
2. 其余事件（不满足打包条件的）原样、按顺序透传（第202-204行、第209-210行）。
3. 输出顺序与输入顺序一致（docstring 第187行 'in order'）。
4. 打包的 run 成员满足 `continues` 条件：seq 连续递增（第139行 `next.seq !== prev.seq + 1`）、时间差为安全整数（第143行）、turn/step 相同（第144行）、block index 相同（第145行）、tool-call 还需 id 相同且 name 存在性及值一致（第147-150行）。
5. 打包后行内 `dt` 为成员间时间差（第157行 `event.time - run[i].time`），`seq0`/`time0` 锚定第一个成员（第158行）。
6. 返回的数组是新建的（第195行 `const out: StorageRecord[] = []`），不共享内部引用。

【调用方须知】最容易被忽略的是：**打包是逐批次（per batch）进行的，不跨批次合并 run**——docstring 第186-187行明确说 'including a batch whose runs were split by flush boundaries (the split runs simply pack per batch)'。也就是说，如果同一段连续 delta 流被 flush 边界切成两个批次，每个批次各自独立判断是否达到 MIN_RUN=3 才打包；一个批次里不足 3 个的 run 会原样展开成单事件行，即使与下一个批次的同类事件合起来超过 3 个也不会合并打包。调用方若期望跨批次压缩，必须自行保证把连续 run 放在同一批次传入。

*✓ 核实通过——逐条核对了候选答案引用的代码行号和具体行为，全部与源码相符，包括 docstring 中关于跨批次不合并的说明。候选答案准确描述了函数的契约。*

### [E] src\index.ts :: assertMessageEventShape（第301行，复杂度31）

函数 `assertMessageEventShape(event: Record<string, unknown>, subject: string): void`（src/index.ts 第301行起）的契约如下：

**输入**：
- `event`：一个 `Record<string, unknown>`，表示待校验的事件对象。
- `subject`：一个字符串，用于在错误消息中标识该事件（例如来源描述）。

**输出**：
- 无返回值（`void`）。

**副作用**：
- 无。函数不修改任何外部状态、文件或全局数据，只做校验并可能抛出异常。

**前置条件**：
- 无显式前置条件。函数对任意 `event` 和 `subject` 均可调用。

**调用后保证**：
- 若 `event['type']` 不是 `'user/message'`、`'assistant/message'` 或 `'tool/result'` 三者之一，函数直接返回，不做任何校验（第304行：`if (type !== 'user/message' && type !== 'assistant/message' && type !== 'tool/result') return`）。
- 若 `type` 是上述三种之一，则校验事件结构，不满足时抛出 `Error`，错误消息以 `${subject}` 开头。具体校验点：
  1. 必须存在一个非空字符串的 `message.id`（第309-313行：`typeof (message as Record<string, unknown>)['id'] !== 'string' || (message as Record<string, unknown>)['id'] === ''` 时抛错）。
  2. `message.role` 必须匹配：`assistant/message` 要求 `'assistant'`，其余（`user/message` 和 `tool/result`）要求 `'user'`（第315-318行）。
  3. `message.source` 必须是对象且 `source.kind` 为非空字符串（第320-324行）。
  4. `message.content` 必须是数组（第326-328行）。
  5. 若 `type === 'assistant/message'`：`source.kind` 必须为 `'model'` 且 `source` 必须携带非空的 `provider` 和 `model` 字符串（第330-334行，调用 `hasProviderModel`）。
  6. 若 `type === 'tool/result'`：`source.kind` 必须为 `'tool'`，`source.callId` 必须为非空字符串（第337-341行）；`message.content` 必须恰好包含一个元素，该元素是 `type === 'tool-result'` 的对象且其 `content` 是数组（第343-348行）；且该块的 `toolCallId` 必须等于 `source.callId`（第350-352行）。
- 校验通过时函数正常返回，不产生任何输出或状态变化。

**【调用方须知】**：最容易被忽略的是：当 `event['type']` 为 `'user/message'` 时，函数取 `message = record`（即 `event['data']` 本身），而 `'assistant/message'` 和 `'tool/result'` 取 `message = record?.['message']`（即 `event['data']['message']`）——也就是说 `user/message` 的 `data` 结构与其他两种类型不同，`data` 直接就是消息对象，没有嵌套的 `message` 字段；如果调用方按统一结构构造 `user/message` 事件（把消息放在 `data.message` 下），该校验会因 `message` 为 `undefined` 而抛出“lacks an identified message”错误。

*✓ 核实通过——候选答案对函数契约的描述与 src/index.ts 中 assertMessageEventShape 的实际实现完全吻合，包括输入输出、无副作用、前置条件和各分支校验逻辑，且【调用方须知】准确指出了 user/message 与其他类型在 data 结构上的关键差异。*

### [D] src\index.ts :: validateSessionHeader（第96行，复杂度26）

【调用方须知】调用方最容易忽略的是：该函数会**原地修改传入对象**——它把传入的 header 对象（或从 JSON 快照还原的对象）直接 `deepFreeze` 掉，返回的是同一个对象引用，而不是拷贝。调用方若在调用后仍想修改该 header 的任何字段（哪怕是新增属性），都会在严格模式下抛错或静默失败；而且由于是原地冻结，调用方持有的原引用也会被冻结，无法再改。因此调用方必须确保传入的 header 对象在调用后不再被修改，否则应自行先拷贝一份再传入。

（依据：`src/index.ts` 第96行 `function validateSessionHeader(id: SessionId, input: unknown): SessionHeader`，函数体最后一行 `return deepFreeze(record as unknown as SessionHeader)`，其中 `record` 就是 `input` 强转后的同一个对象，`deepFreeze` 是原地冻结，返回同一引用。）

*✓ 核实通过——候选答案准确描述了函数原地冻结传入对象并返回同一引用的行为，依据代码原文确认。*

### [D] src\index.ts :: assertSessionEventEnvelope（第213行，复杂度23）

函数 `assertSessionEventEnvelope` 位于 src/index.ts 第213行，是一个私有函数（未导出），签名：`function assertSessionEventEnvelope(value: Record<string, unknown>, index: number): asserts value is SessionEvent`。

**契约描述（依据代码原文）：**

1. **输入**：`value` 是一个 `Record<string, unknown>`（一个已通过 JSON 物化的普通对象），`index` 是数字（种子事件在种子数组中的索引，用于错误消息定位）。

2. **输出**：无返回值。它是一个类型守卫（`asserts value is SessionEvent`），调用成功后 TypeScript 将 `value` 收窄为 `SessionEvent` 类型。

3. **副作用**：无。函数只做校验并抛错，不修改 `value`、不写文件、不改全局状态。

4. **前置条件**：调用方需保证 `value` 是已通过 JSON 物化的普通对象（函数注释写明 "after one-pass JSON materialization"），且调用方拥有该对象的所有权（可被收窄为 `SessionEvent`）。

5. **调用后保证**：
   - 若校验通过，`value` 被类型收窄为 `SessionEvent`，且满足以下不变量（代码原文）：
     - `type` 必须是字符串（`typeof type !== 'string'` 则抛错）；
     - `seq` 必须是非负安全整数（`typeof seq !== 'number' || !Number.isSafeInteger(seq) || seq < 0` 则抛错）；
     - `time` 必须是安全整数（`typeof time !== 'number' || !Number.isSafeInteger(time)` 则抛错）；
     - `data` 必须存在（`event['data'] === undefined` 则抛错）；
     - `ignorable` 若存在必须严格等于 `true`（`event['ignorable'] !== undefined && event['ignorable'] !== true` 则抛错）；
     - 事件键只允许 `type`、`seq`、`time`、`data`、`surfaceOp`、`sourceEventSeqs`、`ignorable` 之一，出现其他键抛错（`default: throw new Error(...)`）；
     - 若 `type` 为 `request/header`、`user/message`、`assistant/message`、`tool/result` 之一，还会调用 `assertCurrentLlmShape(event, index)` 做更深层校验（如 `request/header` 必须有 provider/model、`reasoningEffort` 非空字符串等）。
   - 若校验失败，抛出带 `seed event at index ${index}` 前缀的 `Error`。

**调用方须知**：这个函数的名字只暗示“校验事件信封”，但它实际上还会拒绝 `type === 'request/header-delta'` 的旧格式事件（代码原文：`if (event['type'] === 'request/header-delta') { throw new Error(...) }`），并且对 `request/header`、`user/message`、`assistant/message`、`tool/result` 这四种类型会额外调用 `assertCurrentLlmShape` 做深层校验（如 `request/header` 必须含 provider/model、`assistant/message` 的 source.kind 必须为 'model' 且含 provider/model、`tool/result` 的 source.kind 必须为 'tool' 且 callId 非空）——调用方若只按“信封字段”准备数据，很容易因这些深层约束而抛错，务必先满足 `assertCurrentLlmShape` 的全部要求。

*✓ 核实通过——候选答案对函数签名、输入输出、副作用、前置条件、调用后保证的描述均与代码原文一致，且正确指出了对 request/header-delta 的拒绝和深层校验行为。*

### [C] src\index.ts :: assertCurrentLlmShape（第253行，复杂度14）

函数 `assertCurrentLlmShape(event: Record<string, unknown>, index: number): void`（src/index.ts 第253行）的契约如下：

**输入**：
- `event`：一个 `Record<string, unknown>`，即已通过 `assertSessionEventEnvelope` 校验过的种子事件对象（调用方保证其 `type` 字段是字符串、`data` 字段存在）。
- `index`：该事件在种子序列中的索引（number），仅用于构造错误消息。

**输出**：
- 无返回值（`void`）。

**副作用**：
- 无副作用。函数只读 `event`，不修改任何外部状态、不写文件、不改变全局数据。它唯一的“行为”是：当校验失败时抛出 `Error`。

**前置条件**：
- 调用方必须先调用 `assertSessionEventEnvelope`（第207行）确保事件信封合法（`type`/`seq`/`time`/`data` 等字段类型正确）。
- 调用方只在 `type` 为 `'request/header'`、`'user/message'`、`'assistant/message'`、`'tool/result'` 时调用本函数（见第246-250行的 switch 分支）。

**调用后保证**：
- 若函数正常返回，则事件满足以下全部条件：
  1. 对 `request/header`：`data.header.config` 必须存在且包含 `provider` 和 `model`（`hasProviderModel(config)` 为真，第263行）；若 `config.reasoningEffort` 存在，则必须是**非空字符串**（第264-267行）；`adapterDefaults` 若存在，必须通过 `assertAdapterDefaults` 校验（第269行）。
  2. 对 `user/message`、`assistant/message`、`tool/result`：必须通过 `assertMessageEventShape` 校验（第278行），即 `data` 是对象、消息有非空 `id`、`role` 正确（assistant 消息 role 必须是 `'assistant'`，其余为 `'user'`）、`source` 是含非空 `kind` 的对象、`content` 是数组；assistant 消息的 source.kind 必须是 `'model'` 且含 provider/model；tool/result 的 source.kind 必须是 `'tool'` 且 `callId` 是非空字符串。
- 若任一条件不满足，函数抛出带 `index` 的错误，调用方应中止加载。

**【调用方须知】**：最容易忽略的是：本函数对 `request/header` 的校验**只检查 `config` 里的 `reasoningEffort` 和 `adapterDefaults`，但完全不检查 `config` 里是否还有其他非法键**——`assertAdapterDefaults` 只校验 `adapterDefaults` 的键白名单（`reasoningEffort`、`maxTokens`），而 `config` 本身允许任意额外字段；同时，对 `user/message` 和 `tool/result`，本函数**不校验 `role` 是否为 `'user'` 之外的值**（`expectedRole` 对非 assistant 消息固定为 `'user'`，但 `tool/result` 的 role 实际应为 `'user'` 却未强制），且 `tool/result` 的 `content` 只要求是数组、不校验元素结构。若你的调用方依赖这些未校验的字段，需自行额外验证。

*✗ 核实不通过——候选答案对 assertCurrentLlmShape 的契约描述有多处与代码不符，特别是对 tool/result 的校验描述错误，因此整体不准确。*

### [C] src\index.ts :: append（第604行，复杂度14）

【调用方须知】调用方最容易忽略的是：`append` 返回的 `event.data` 是**深拷贝快照**（`snapshotJsonValue(data)` 的结果），不是调用方传入的 `data` 对象本身——调用方在 append 之后修改自己原来的 `data` 对象，**不会**影响已记录的事件；但反过来，调用方也**不能**通过修改返回的 `event.data` 来改变日志内容（它被 `deepFreeze` 冻结了）。

---

**契约描述（依据 src/index.ts 第604-660行 `append` 方法及第560-604行 docstring）**

**输入**
- `type: T`（事件类型，`SessionEventType` 的子类型）
- `data: SessionEventMap[T]`（事件载荷，必须 JSON 可序列化）
- `...opts`：仅当 `T extends SurfaceEventType` 时，才接受一个 `SurfaceIntent` 参数（含 `surfaceOp` 和 `sourceEventSeqs`）；对非 surface 类型（如 `turn/start`、`assistant/chunk`），编译器会拒绝传入该参数（docstring："REQUIRED for SurfaceEventType events... rejected by the compiler for non-surface types"）。

**输出**
- 返回 `SessionEvent<T>`，即已记录的事件对象，包含：`type`、`seq`（= `this.log.length`，即追加前的日志长度）、`time`（`Date.now()`）、`data`（**深拷贝快照**，见第616行 `const dataSnapshot = snapshotJsonValue(data)`）、以及 surface 元数据（`surfaceOp`/`sourceEventSeqs`，若提供）。
- 返回的 `event.data` 是快照，"so reading `event.data` back sees the logged value, never the caller's still-mutable input"（docstring）。

**副作用（外部状态变更）**
1. **修改日志**：`this.log.push(event)`（第640行）——事件被追加到 append-only 日志，`seq` 递增。
2. **失效缓存**：`this.eventsSnapshot = undefined`（第641行），使 `events` getter 下次重新生成快照。
3. **同步通知观察者**：通过 `invokeContainedSessionObservers(entry.emitCtx, 'session/event', ...)`（第644行）触发 `session/event` 事件；观察者失败被记录并隔离，不影响返回值或后续观察者（docstring："observer failures are logged and contained per listener"）。
4. **更新 surface 状态**：`this.surfaceManager.validateNext(event)`（第632行）在追加前验证 surface 契约，并可能影响 surface 投影（如 `replace` 会删除被遮蔽节点）。
5. **不阻塞 I/O**：持久化是插件异步缓冲的（docstring："persistence plugins buffer asynchronously"），append 本身不写磁盘。

**前置条件**
1. `data` 必须**无损 JSON 可序列化**——不能含 BigInt、函数、symbol、undefined、负零、非有限数、循环引用、稀疏数组、或 Map/Set/Date/类实例等（docstring 的 @throws 列表）。否则抛错（第617-619行）。
2. 对 `request/header` 类型，不能使用 legacy 的 `reason` 为 `'fallback'`（`assertSupportedRequestHeader`，第620行）。
3. surface 元数据（`surfaceOp`/`sourceEventSeqs`）也必须 JSON 可序列化（第621-624行）。
4. 事件必须满足 canonical surface 契约：marker 形状与资格、唯一的 earlier source-event 引用、位置替换有效性、完整的被遮蔽节点覆盖（docstring @throws）。
5. **不能重入**：若另一个 append 正在发布中（`entry.appending` 为 true），会抛错（第626-628行）。
6. 对 `request/header-delta` 类型，直接拒绝（legacy 格式，`assertSupportedRequestHeader`）。

**调用后保证**
1. 事件已提交到日志，`seq` 连续（`seq = log.length` 契约）。
2. 返回的事件及其嵌套数据被 `deepFreeze` 冻结（第629行 `const event = deepFreeze({...})`），不可变。
3. 观察者已同步收到通知（若 store 已 attach）。
4. 若验证失败，日志**不变**——失败发生在 `this.log.push` 之前（docstring："a bad event fails at the append site rather than later"）。
5. 即使观察者抛错，append 仍成功返回（观察者错误被隔离，不影响返回值）。
6. 在 `finally` 块中重置 `entry.appending = false`，并处理延迟的 detach（第650-653行）。

**依据代码原文**：
- 输入/输出签名：第604-611行 `append<T extends SessionEventType>(type: T, data: SessionEventMap[T], ...opts: T extends SurfaceEventType ? [opts: SurfaceIntent] : []): SessionEvent<T>`
- 深拷贝快照：第616行 `const dataSnapshot = snapshotJsonValue(data)`
- 冻结：第629行 `const event = deepFreeze({...})`
- 日志 push：第640行 `this.log.push(event as SessionEvent)`
- 缓存失效：第641行 `this.eventsSnapshot = undefined`
- 观察者通知：第644行 `invokeContainedSessionObservers(...)`
- 重入检查：第626-628行 `if (entry?.appending) { throw ... }`
- 失败不改日志：docstring "a bad event fails at the append site rather than later during a backend flush"

*✓ 核实通过——候选答案的每一条契约描述都能在代码原文中找到直接依据，且没有发现与实现矛盾之处，因此判定为真实准确。*

### [C] src\index.ts :: prepare（第863行，复杂度12）

【prepare 的契约】

**输入**（src/index.ts 第863-864行）：
- `id?: SessionId`：可选会话id。省略时自动生成（第866-868行 `do sessionId = SessionId(\`session-${++this.counter}\`) while (this.store.has(sessionId))`，用递增计数器生成并跳过已存在的id）。
- `options?: PrepareSessionOptions`：可选，含 `seed`（种子事件）、`meta`（创建元数据）、`seedSource`（若为 `'persistence'` 走恢复路径）。

**输出**（第880行 `return Session.create(sessionId, seed, header)`；第875行 `return Session.fromRestore(...)`）：返回一个**已构造但尚未进入store**的 `Session` 对象（docstring 第856行明确 "NOT yet in the store"）。

**副作用**：
- **修改了 `this.counter`**（第867行 `++this.counter`）——当 `id` 省略时，计数器自增，这是对实例状态的持久副作用。
- **不写入store、不安装发布钩子、不发出任何事件**——docstring 第856行 "Build a session WITHOUT entering it into the store"，第857行 "construct the Session"。
- 当 `seedSource === 'persistence'` 时（第874-875行），调用 `Session.fromRestore`，docstring 第858-860行说明：元数据和事件必须是"fresh detached graphs whose ownership transfers to this call"，会被验证并"frozen in place"，因此调用方不得保留可变别名（所有权转移副作用）。

**前置条件**：
- 若 `id` 已存在于store中，抛错（第871行 `if (this.store.has(sessionId)) throw new Error(...)`）。
- 若 `meta` 不是纯无损JSON记录、含非法标量字段、或 `meta.cwd` 非绝对路径，抛错（docstring 第861-862行）。
- 若 `seedSource === 'persistence'`，调用方必须放弃对传入 seed/meta 的所有可变引用（docstring 第858-860行）。

**调用后保证**：
- 返回的 session 具有不可变的 `SessionHeader`，其中 `version` 固定为 `SESSION_FORMAT_VERSION`、`id` 为传入/生成的id、`createdAt` 为 `meta?.createdAt ?? Date.now()`（第877-879行），其余字段（cwd/parentSession/seedLength/origin/delegationDepth/agentPreset）仅在 `meta` 提供时存在（第880-886行）。
- 该 session **尚未**进入store，调用方必须随后调用 `enter` + `announce` 才能使其生效（docstring 第856-857行）。

【调用方须知】当 `seedSource === 'persistence'` 时，`prepare` 会通过 `Session.fromRestore` **接管并冻结（frozen in place）你传入的 seed/meta 对象的所有权**——调用后你不能再持有或修改这些对象的任何可变别名，否则会破坏已恢复的会话数据；这是函数名"prepare"字面看不出来的所有权转移副作用，务必在调用前确保这些图是"fresh detached"且不再被外部引用。

*✓ 核实通过——候选答案的每一条具体说法都能在 prepare 的实现和 docstring 中找到对应代码原文，没有发现与代码不符之处。*

### [C] src\index.ts :: assertAdapterDefaults（第282行，复杂度11）

【调用方须知】调用方最容易忽略的是：当 adapterDefaults 里同时出现 reasoningEffort 和 maxTokens 两个键时，只要其中一个键对应的 config 值缺失（undefined），整个校验就会抛错——即使另一个键的 config 值存在。也就是说，这两个键的校验是“或”关系（用 || 连接），不是“且”关系，任何一个键的 config 缺失都会导致整个 adapterDefaults 被判定为无效，而不是只针对缺失的那个键报错。

*✓ 核实通过——候选答案准确描述了该函数的校验逻辑：两个键的校验是“或”关系，任一键的 config 缺失都会导致抛错。*

### [B] src\index.ts :: validateRestoredSessionHeader（第506行，复杂度8）

【validateRestoredSessionHeader 契约】

**位置**：src/index.ts 第139行定义，第506行在 Session 私有构造函数中被调用（仅当 mode === 'restore' 时）。

**输入**：
- `id: SessionId` —— 会话身份标识。
- `input: unknown` —— 待恢复的会话头对象（来自 `Session.fromRestore` 传入的 `header`）。

**输出**：
- 返回 `SessionHeader`（一个被 `deepFreeze` 冻结的普通 JSON 记录）。

**前置条件**（调用方必须满足）：
1. `input` 必须是一个普通 JSON 对象（非 null、非数组、非原始类型），且其原型必须是 `Object.prototype` 或 `null`（第141-146行：`if (input !== null && typeof input === 'object' && !Array.isArray(input))`，然后检查 `Reflect.getPrototypeOf(input)` 是否为 `Object.prototype` 或 `null`，否则抛错 `'session header is not a plain JSON record'`）。
2. `input` 必须通过 `validateSessionHeader` 的全部字段校验（第147行调用 `validateSessionHeader(id, input)`），包括：
   - `version` 必须等于 `SESSION_FORMAT_VERSION`（第101-103行）。
   - `id` 必须与传入的 `id` 完全一致（第104-106行：`record.id !== id` 则抛错）。
   - `createdAt` 必须是非负安全整数（第107-111行）。
   - `cwd`（若存在）必须是字符串且为绝对路径（第112-118行）。
   - `parentSession`（若存在）必须是字符串（第119-121行）。
   - `seedLength`（若存在）必须是非负安全整数（第122-126行）。
   - `origin`（若存在）必须严格等于 `'subagent'`（第127-129行）。
   - `delegationDepth`（若存在）必须是非负安全整数（第130-134行）。
   - `agentPreset`（若存在）必须是字符串（第135-137行）。

**副作用**：
- **就地冻结**：该函数直接对传入的 `input` 对象调用 `deepFreeze`（第139行 `return deepFreeze(record as unknown as SessionHeader)`），即**修改了调用方传入的对象本身**，将其所有属性递归冻结为只读。调用方传入的 `header` 对象在调用后不可再被修改。
- 不修改任何文件、全局数据或外部状态；只冻结传入对象并返回它。

**调用后保证**：
- 返回的 `SessionHeader` 是深度冻结的、字段全部合法的普通 JSON 记录。
- 若任何校验失败，会抛出 `Error`（不会返回）。

**调用上下文**：仅在 `Session` 私有构造函数中、当 `mode === 'restore'` 时被调用（第505-507行），用于 `Session.fromRestore` 恢复路径。

【调用方须知】该函数会**就地冻结你传入的 `header` 对象本身**（`deepFreeze(record)`），而不是拷贝后再冻结——调用后你持有的原 `header` 对象的所有属性都变成只读，任何后续尝试修改它（包括修改嵌套对象）都会在严格模式下抛错或静默失败；若你还需要继续使用该对象，请先自行 `structuredClone` 一份再传入。

*✓ 核实通过——候选答案对函数位置、输入输出、校验逻辑、副作用（deepFreeze 就地冻结）的描述均与源码相符，且调用上下文正确。唯一小偏差是函数定义行号（候选答案称第 139 行，实际为第 139-146 行），但整体契约描述准确。*

### [B] src\index.ts :: assertSupportedRequestHeader（第363行，复杂度7）

函数 `assertSupportedRequestHeader(type: string, data: unknown, location: string): void` 定义在 src/index.ts 第363行，是一个纯校验函数，无副作用（不修改任何外部状态、文件或全局数据），只可能抛异常。

**输入契约**：
- `type`：字符串，事件类型名。
- `data`：任意值，通常是事件负载的 JSON 快照（调用方传入的是 `snapshotJsonValue` 的结果，见第618行 `assertSupportedRequestHeader(type, dataSnapshot, ...)` 和第524行 `assertSupportedRequestHeader(snapshot.type, snapshot.data, ...)`）。
- `location`：字符串，用于错误消息中标识事件来源（如 `session event "${type}"` 或 `seed event at index ${index}`）。

**输出契约**：
- 返回 `void`（无返回值）。
- 若输入不满足条件，抛出 `Error`；否则正常返回。

**副作用**：无。函数体只做条件判断和抛错，不修改任何外部状态、文件或全局数据。

**前置条件**：
- 无显式前置条件。但调用方（第618行 append、第524行 seed 校验）已先通过 `snapshotJsonValue` 确保 `data` 是 JSON 快照（非 undefined），且 `type` 是字符串。函数本身不校验这些，若 `type` 非字符串或 `data` 为 undefined，函数可能不抛错（因为条件不匹配）而静默通过。

**调用后保证**：
- 若函数未抛异常，则说明该事件类型不是 `request/header-delta`，且（若是 `request/header`）其 `data` 不是带 `reason === 'fallback'` 的对象。即：该事件不会携带被移除的 legacy 请求头词汇。

**具体依据**（第363-374行）：
```ts
function assertSupportedRequestHeader(type: string, data: unknown, location: string): void {
  if (type === 'request/header-delta') {
    throw new Error(`${location} uses unsupported legacy request/header-delta format`)
  }
  if (type === 'request/header'
    && data !== null && typeof data === 'object' && !Array.isArray(data)
    && (data as Record<string, unknown>)['reason'] === 'fallback') {
    throw new Error(`${location} uses unsupported legacy request/header reason "fallback"`)
  }
}
```

【调用方须知】最容易被忽略的是：该函数只拦截 `request/header-delta` 类型和 `request/header` 且 `data.reason === 'fallback'` 的情况，但**不拦截** `request/header` 的其他 `reason` 值（如 `'retry'`、`'refresh'` 等），也不校验 `data` 是否为合法对象——若 `data` 是 `null`、数组、或非对象，函数会静默通过，调用方不能依赖它来保证 `request/header` 事件的 `data` 一定是合法对象；它只负责拒绝那两种特定的 legacy 格式，其他合法性需由调用方另行校验。

*✓ 核实通过——逐条核对了候选答案引用的函数签名、调用点、函数体逻辑和副作用描述，均与源码相符，且【调用方须知】指出的不拦截其他 reason 值、不校验 data 合法性的行为也正确。*

### [B] src\index.ts :: announce（第968行，复杂度7）

「announce」是 SessionStore 类的一个公开方法（src/index.ts 第968行），其契约如下：

**输入**：一个 `Session` 参数（`announce(session: Session): void`）。

**前置条件**：
1. 该 session 必须已通过 `enter()` 进入 store（`const entry = this.liveEntryFor(session)` 会查找 live entry，若不存在会抛错）。
2. 该 session 尚未被 announce 过：`if (entry.announced || entry.announcing) { throw new Error(...) }` —— 重复 announce 或重入（从创建监听器里再次调用）都会抛 `session "..." was already announced`。

**行为/副作用**：
1. 在 emit 之前先置 `entry.announced = true`（注释明确说明：Cordis emit 可能先投递给前面的监听器再抛错，rollback 必须把部分创建与 disposal 配对，且监听器不能递归创建第二个生命周期边）。
2. 置 `entry.announcing = true`，然后通过 `collectSessionCallbacks(this.ctx, [entry.carrier, 'session/created', session])` 收集监听器并逐个同步调用（`callback(...callbackArgs)`）。
3. 同步抛错会传播并否决发布（veto publication），随后调用方持有的 detach 会发出配对的 disposal 边。
4. 异步监听器返回的 promise 被 `Promise.resolve(returned).catch(...)` 捕获，rejection 只记日志（`this.ctx.logger.warn(...)`），不能回滚。
5. `finally` 中置 `entry.announcing = false`，若 `entry.detachRequested && !entry.appending` 则调用 `entry.detach()`（即 detach 被延迟到 announce 展开后执行）。

**输出**：无返回值（`void`）。副作用是向 `session/created` 事件的所有监听器派发 `session` 参数。

**调用后保证**：
- 该 session 的 `announced` 标志被置为 true，之后不能再被 announce。
- 若监听器同步抛错，announce 抛错且该 session 会被 detach（发出 `session/disposed`）。
- 若监听器异步 reject，只记日志，session 保持已发布状态。

【调用方须知】announce 必须在 `enter()` 返回的 detach disposer 已产出之后调用（且要在同一同步效果内），因为 announce 内部依赖 `entry.detachRequested` 机制：若在 announce 派发期间（`announcing` 为 true）调用 detach，detach 会被延迟到 announce 的 finally 块里执行；若在 announce 之前或之后调用 detach，行为不同——最容易被忽略的是：**announce 会同步抛错（veto 发布）并触发配对的 disposal，但异步监听器的 rejection 只记日志、不会回滚，调用方不能依赖异步监听器失败来撤销发布**。

*✓ 核实通过——我通读了 src/index.ts 中 announce 的完整实现及其调用上下文（create/enter/detachEntered），候选答案对函数签名、前置条件、副作用、输出和调用方须知的描述均与代码原文一致，没有发现不实之处。*

### [B] src\index.ts :: validateRestoredSessionHeader（第139行，复杂度6）

【函数契约】validateRestoredSessionHeader(id: SessionId, input: unknown): SessionHeader（src/index.ts 第139-147行）

**输入**：
- `id: SessionId`：会话ID，用于校验header中的id字段。
- `input: unknown`：待校验的会话头对象，预期是JSON可序列化的普通对象。

**输出**：
- 返回类型为 `SessionHeader`。实际返回的是 `validateSessionHeader(id, input)` 的结果，即经过校验并深度冻结（deepFreeze）的header对象（见第147行 `return validateSessionHeader(id, input)`，以及 `validateSessionHeader` 末尾的 `return deepFreeze(record as unknown as SessionHeader)`）。

**副作用**：
- **深度冻结输入对象**：通过 `validateSessionHeader` 内部的 `deepFreeze` 将传入的header对象及其嵌套属性全部冻结（变为只读），这是对调用方传入对象的外部状态修改（使其不可变）。
- 不修改文件、全局数据或其他外部状态。

**前置条件**：
- `input` 必须是普通JSON对象（原型为 `Object.prototype` 或 `null`），否则抛错（第140-144行）。
- `input` 必须满足 `validateSessionHeader` 的所有校验规则：
  - 非null、非数组、是对象（第100行）。
  - `version` 必须等于 `SESSION_FORMAT_VERSION`（第102-104行）。
  - `id` 必须等于传入的 `id` 参数（第105-107行）。
  - `createdAt` 必须是非负安全整数（第108-112行）。
  - 可选字段 `cwd`（若存在）必须是字符串且为绝对路径（第113-119行）。
  - 可选字段 `parentSession`（若存在）必须是字符串（第120-122行）。
  - 可选字段 `seedLength`（若存在）必须是非负安全整数（第123-126行）。
  - 可选字段 `origin`（若存在）必须等于 `'subagent'`（第127-129行）。
  - 可选字段 `delegationDepth`（若存在）必须是非负安全整数（第130-133行）。
  - 可选字段 `agentPreset`（若存在）必须是字符串（第134-136行）。

**调用后保证**：
- 若校验通过，返回一个深度冻结的、满足上述所有约束的 `SessionHeader` 对象。
- 若校验失败，抛出 `Error`，不返回任何值，且不修改传入对象（校验在冻结前进行）。

【调用方须知】该函数会**原地深度冻结传入的 `input` 对象**（通过 `validateSessionHeader` 末尾的 `deepFreeze`），即使调用方后续仍持有该对象的引用，也无法再修改它——如果调用方在调用后还需要修改这个header对象，必须先自行拷贝一份再传入，否则会因冻结而抛错或静默失败。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和调用后保证的描述与代码原文完全一致，包括深度冻结的副作用和所有校验规则。*

### [B] src\index.ts :: hasProviderModel（第355行，复杂度6）

函数 `hasProviderModel`（src/index.ts 第355-360行）的契约如下：

**输入**：一个 `unknown` 类型的值 `value`。

**输出**：返回一个 `boolean`。

**行为/副作用**：无副作用。函数是纯函数，不修改任何外部状态、文件或全局数据，只读取传入参数。

**前置条件**：无。函数对任意输入都安全，不会抛异常。

**保证**：
- 若 `value` 不是对象或为 `null`，返回 `false`（第356行：`if (typeof value !== 'object' || value === null) return false`）。
- 若 `value` 是对象，则检查其 `provider` 和 `model` 属性：只有当两者都是非空字符串（`typeof === 'string'` 且 `length > 0`）时才返回 `true`，否则返回 `false`（第358-360行）。

**【调用方须知】**：该函数只检查 `provider` 和 `model` 是否为非空字符串，并不验证它们是否真的是当前支持的 provider/model 组合——函数名里的“current”具有误导性，它并不检查值是否与当前会话的 provider/model 一致，只检查字段存在且非空。调用方若期望它验证“当前”配对，会得到错误结论。

*✓ 核实通过——我逐行核对了函数实现，确认候选答案对输入、输出、副作用、前置条件和保证的描述均与代码原文相符，且对函数名误导性的提醒有代码依据。*

### [B] src\invariant.ts :: validateEvent（第55行，复杂度7）

validateEvent 是 src/invariant.ts 中一个纯函数（第55行起），契约如下：

**输入**：
- `trace: SessionTrace`：当前会话的已提交追踪状态（含 lastSeq、openTurn、openStep、nextTurn、nextStep、pendingCalls）。
- `event: SessionEvent`：待校验的候选事件。
- `fail: InvariantFailure`：校验失败时的回调。

**输出**：返回一个 `SessionTraceTransition` 对象，包含 `scalars`（新的 lastSeq/openTurn/openStep/nextTurn/nextStep）和 `pendingCalls`（'none' | 'add' | 'delete' | 'clear'）。

**副作用**：无。函数不修改传入的 `trace`，只基于其副本计算新状态。依据：函数开头 `let openTurn = trace.openTurn` 等局部变量复制，且注释明确写 'Validate one candidate event without mutating the committed trace'。真正的状态变更由调用方在事件提交后调用 `applyTransition` 完成。

**前置条件**：
- `event.seq` 必须严格大于 `trace.lastSeq`，否则 `fail`（第57-59行）。
- 对 turn/step 相关事件，要求当前 open 状态匹配（如 turn/start 要求 openTurn 为 null 且 turn 等于 nextTurn，第66-72行）。
- tool/result 若 surfaceOp 不是 'append'，要求 openTurn 非 null（第111-116行）。

**后置保证**：
- 若校验通过，返回的 transition 描述了事件提交后应如何更新 trace（scalars 和 pendingCalls）。
- 校验失败时调用 `fail`，不返回有效 transition。

**【调用方须知】**：validateEvent 本身不修改 trace，但调用方必须在事件真正提交后调用 `applyTransition` 应用返回的 transition；若事件被后续监听器否决（veto），该 transition 会被丢弃（见 internal/dispatch 中 'A later dispatch listener may veto. Validation is pure, so abandoning this weakly keyed transition does not advance or retain the session'），此时 trace 不会前进——调用方切勿在事件未提交时提前应用 transition，否则会造成状态与事件日志不一致。

*✓ 核实通过——逐条核对代码原文，候选答案对输入、输出、副作用、前置条件、后置保证及调用方须知的描述均与源码一致。*

### [C] src\repair.ts :: interruptedTurnClosers（第27行，复杂度19）

函数 `interruptedTurnClosers`（src/repair.ts 第27行起）的契约如下，每条均引用代码原文：

**输入**：`events: readonly SessionEvent[]`——一个已加载的持久化日志（docstring："the loaded durable log to scan (a valid committed prefix, possibly with a crash tail)"）。函数只读该数组，不修改它。

**输出**：`SessionEvent[]`——按顺序追加到 `events` 之后的合成收尾事件。docstring："returns the synthetic closer events to append after `events`, in order; empty when the log is already balanced."

**副作用**：无外部副作用。函数是纯函数：不写文件、不改全局数据、不改传入的 `events`（只读遍历，`pendingCalls` 是局部 Map）。唯一"外部"影响是返回的数组本身，调用方需自行决定是否持久化。

**前置条件**：
1. `events` 必须是"有效的已提交前缀"（docstring："a valid committed prefix"），即日志结构合法。
2. 若日志末尾存在未闭合的 turn（`openTurn !== null`），则 `events` 非空（代码注释："An open turn implies `events` is non-empty (its turn/start was logged), so `last` exists."），因此 `last = events.at(-1)` 不会为 undefined。
3. 无其他前置条件；空数组或完全平衡的日志直接返回 `[]`（`if (openTurn === null || last === undefined) return []`）。

**调用后保证**：
1. 若日志已平衡（无未闭合 turn）或为空，返回空数组，不产生任何事件。
2. 若存在未闭合 turn，则返回的事件序列保证：
   - 每个未匹配的 tool-call（在 `pendingCalls` 中）先收到一个 `tool/result` 错误事件（代码："Close calls before their step"），错误码为 `TOOL_OUTCOME_UNKNOWN`（若该 call 有 `tool/call` 记录，`started=true`）或 `TOOL_NOT_STARTED`（若没有，`started=false`）。
   - 若存在未闭合 step（`openStep !== null`），则在其后追加一个 `step/end`（代码："Close an open step next"）。
   - 最后追加一个 `turn/end`，`reason: { kind: 'interrupted' }`。
   - 所有合成事件的 `seq` 从 `last.seq + 1` 递增，`time` 复用 `last.time`（代码注释："reusing the last timestamp keeps them deterministic and never invents a 'future' time"）。
   - 合成 `tool/result` 的 `data.turn` 为 `openTurn`，`data.step` 为该 call 注册时的 step；若该 call 有 `tool/call` 事件，则 `sourceEventSeqs: [callSeq]` 被设置（`...started ? { sourceEventSeqs: [callSeq] } : {}`）。
   - 返回顺序固定：先所有 tool/result（按 Map 插入序），再 step/end（若有），最后 turn/end。
3. 合成 `tool/result` 的 message 是 `freezeMessage` 冻结的 `ToolResultMessage`，`role: 'user'`，`isError: true`，错误文本根据 `started` 区分（"The tool call was interrupted after it was recorded..." vs "The tool call was interrupted before the Harness recorded it as started..."）。

【调用方须知】最该警惕的是：函数**不会**为"已闭合的 turn 内部"的未匹配 call 生成任何收尾——`pendingCalls` 在每个 `turn/end`、`step/end`、`turn/start` 处被清空（`pendingCalls.clear()`），因此只有**日志末尾那个未闭合 turn 内**的未匹配 call 才会被补 `tool/result`；若一个 turn 已正常 `turn/end` 但其中某个 call 从未收到 `tool/result`，该 call 会被静默丢弃，函数返回空数组，调用方若期望"任何未闭合 call 都要补错误结果"就会漏掉这种情况。

*✓ 核实通过——候选答案的每一条描述都与代码原文逐行吻合，包括边界行为（已闭合 turn 内的未匹配 call 被静默丢弃）和具体错误文本，无虚构或夸大。*

### [B] src\request-header.ts :: headerEquals（第44行，复杂度10）

在 src/request-header.ts 中，`headerEquals`（第44行）的契约如下：

**输入**：两个 `EpochHeader` 类型的参数 `a` 和 `b`（第44行 `export function headerEquals(a: EpochHeader, b: EpochHeader): boolean`）。

**输出**：返回一个布尔值，表示两个 canonical header 是否字段级相等（第45行 `): boolean {`）。

**副作用**：无。函数是纯函数，不修改任何外部状态、文件或全局数据。它只读取参数，不调用任何有副作用的函数（`callConfigEquals` 和 `sameSchema` 都是纯比较函数）。

**前置条件**：
1. 两个参数应当是 canonical header（即经过 `canonicalHeader` 规范化后的形式）。函数内部直接比较 `a.system !== b.system`（第49行），如果 system 字段未规范化（例如空字符串 vs undefined），比较结果可能不符合预期。
2. `a.config` 和 `b.config` 必须能被 `callConfigEquals` 正确比较（第46行）。
3. `a.tools` 和 `b.tools` 中的 ToolSchema 对象必须能通过 `JSON.stringify` 比较（第53行 `sameSchema`），因此要求对象属性顺序一致，否则即使语义相同也会返回 false。

**调用后保证**：
- 当且仅当以下条件全部满足时返回 true：
  - `callConfigEquals(a.config, b.config)` 为 true（第46行）
  - `a.adapterDefaults?.reasoningEffort === b.adapterDefaults?.reasoningEffort`（第47行）
  - `a.adapterDefaults?.maxTokens === b.adapterDefaults?.maxTokens`（第48行）
  - `a.system === b.system`（第49行）
  - `a.tools` 和 `b.tools` 长度相同，且按顺序每个工具 schema 通过 `sameSchema` 比较（第51-53行）
- 若任一条件不满足，返回 false。
- 注意：`adapterDefaults` 的其余字段（如 `reasoningEffort` 和 `maxTokens` 之外的其他属性）**不参与比较**，即使它们不同，只要上述字段相同就返回 true。

【调用方须知】最容易被忽略的是：`headerEquals` 只比较 `adapterDefaults` 中的 `reasoningEffort` 和 `maxTokens` 两个字段（第47-48行），`adapterDefaults` 对象上的其他任何属性（例如未来新增的配置项）都不会被比较——如果调用方期望两个 header 的 `adapterDefaults` 完全一致，这个函数会静默地认为它们相等，导致漏判。此外，`tools` 的比较依赖 `JSON.stringify`（第53行），因此两个语义相同但属性顺序不同的 ToolSchema 会被判定为不相等，调用方需确保传入的 tools 是规范化且属性顺序一致的。

*✓ 核实通过——候选答案逐条对照代码原文核实，所有引用的行号和逻辑均准确，包括 adapterDefaults 只比较两个字段、tools 用 JSON.stringify 按顺序比较等细节，结论正确。*

### [B] src\request-header.ts :: canonicalHeader（第21行，复杂度7）

canonicalHeader 的契约（依据 src/request-header.ts 第 21-30 行）：

**输入**：一个 EpochHeader 类型的对象 header（第 22 行 `export function canonicalHeader(header: EpochHeader): EpochHeader`）。docstring 明确说明“not mutated”（第 20 行）。

**输出**：返回一个新的 EpochHeader 对象，是输入的规范化（canonical）形式。具体规则（第 23-29 行）：
- 始终保留 `config` 字段（第 24 行 `config: header.config`）。
- `adapterDefaults` 仅在 `adapterDefaults?.reasoningEffort === true || adapterDefaults?.maxTokens === true` 时保留（第 25-26 行），否则该字段被省略（absent）。
- `system` 仅在 `header.system !== undefined && header.system.length > 0` 时保留（第 27 行），否则省略。
- `tools` 仅在 `header.tools !== undefined && header.tools.length > 0` 时保留（第 28 行），否则省略。

**副作用**：无。函数是纯函数，不修改输入对象（docstring 第 20 行“not mutated”），不写文件、不改全局状态。

**前置条件**：无特殊前置条件，任何 EpochHeader 均可传入。

**调用后保证**：返回的 header 是规范化的——空 system、空 tools、以及非 true 的 adapterDefaults 字段会被移除，使“空字段变为缺失字段”，与请求构建方式一致（docstring 第 18-19 行）。

【调用方须知】该函数返回的是**新对象**，且会**丢弃**输入中 `adapterDefaults` 里 `reasoningEffort` 和 `maxTokens` 之外的任何其他属性（第 25-26 行只保留整个 adapterDefaults 对象，但只有当这两个布尔之一为 true 时才保留；若两者都非 true，整个 adapterDefaults 被省略）——如果调用方依赖 adapterDefaults 中的其他字段（如 temperature、topP 等），这些字段在规范化后可能丢失，且 headerEquals（第 36-44 行）也只比较 reasoningEffort 和 maxTokens，不会发现这种丢失。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和保证的描述均与代码原文一致，且调用方须知指出的adapterDefaults其他字段丢失问题准确，因为代码只保留整个adapterDefaults对象但条件仅基于这两个布尔值。*

### [C] src\surface.ts :: assertProvenance（第211行，复杂度12）

函数 `assertProvenance` 位于 `src/surface.ts` 第211行，签名：`function assertProvenance(event: SessionEvent, shadowedSeqs: readonly number[]): void`。

**契约描述（依据代码原文）：**

1. **输入**：
   - `event: SessionEvent` —— 一个会话事件，函数会读取其 `seq` 字段和可选的 `sourceEventSeqs` 字段（通过 `(event as SessionEvent & { sourceEventSeqs?: unknown }).sourceEventSeqs` 提取）。
   - `shadowedSeqs: readonly number[]` —— 被替换操作实际移除的表面节点序列号列表（由调用方传入，通常是 `replacementRange` 计算出的 `shadowedSeqs`）。

2. **输出**：
   - 返回 `void`（无返回值）。

3. **副作用**：
   - **无副作用**。函数只做校验，不修改任何外部状态、文件或全局数据。它只读取 `event` 和 `shadowedSeqs`，不改变它们，也不改变任何模块级变量。

4. **前置条件**：
   - 调用方应已确定该事件是 surface-eligible 且携带 `surfaceOp`（通常由 `surfaceOpOf` 校验过），但 `assertProvenance` 本身不检查这一点，它只关注 `sourceEventSeqs` 字段。
   - 调用方应已计算出 `shadowedSeqs`（被替换的表面节点序列），通常来自 `replacementRange`。

5. **调用后保证（校验规则，违反即抛错）**：
   - 若 `sourceEventSeqs` 存在，则必须是数组，否则抛 `Error('sourceEventSeqs on event at seq ${event.seq} must be an array when present')`。
   - 若 `sourceEventSeqs` 非空数组，则事件类型必须是 `'assistant/message'`，否则抛 `Error('sourceEventSeqs must not be empty except on assistant/message')`。
   - 数组中的每个元素必须是合法的非负安全整数（`isEventSeq`），否则抛 `Error('session event "${event.type}" sourceEventSeqs must densely contain non-negative safe integers')`。
   - 数组不能包含重复元素，否则抛 `Error('sourceEventSeqs must not contain duplicates')`。
   - 数组中的每个元素必须严格小于 `event.seq`（即必须引用更早的事件），否则抛 `Error('sourceEventSeqs must reference earlier events: ${nonEarlierSource} >= current seq ${event.seq}')`。
   - 最后，`shadowedSeqs` 中的每个序列号必须出现在 `sourceEventSeqs` 中（即 `sourceEventSeqs` 必须覆盖所有被替换的表面节点），否则抛 `Error('surface replace: sourceEventSeqs must include every shadowed surface node; missing ${missing.join(', ')}')`。
   - 若所有校验通过，函数正常返回（无返回值），表示该事件的 provenance 声明合法。

【调用方须知】最容易被忽略的是：当 `sourceEventSeqs` 存在且为空数组（`raw.length === 0`）时，函数只允许事件类型为 `'assistant/message'`，其他类型（如 `user/message`、`tool/result`）即使 `sourceEventSeqs` 为空数组也会抛错——这意味着一个空数组的 `sourceEventSeqs` 并不是“无来源”的通用表示，而是被严格限定为仅 assistant/message 事件可用，调用方在构造或校验事件时若想表达“无来源”，必须确保事件类型是 `assistant/message`，否则会意外抛错。

*✓ 核实通过——逐条核对了候选答案中引用的所有错误消息和逻辑，与代码原文完全一致，且函数确实无副作用。候选答案准确描述了契约。*

### [C] src\surface.ts :: isDeepEqualJson（第273行，复杂度12）

基于对 src/surface.ts 的阅读，函数 isDeepEqualJson 位于第 273 行（实际代码在第 273-281 行），其契约如下：

**输入**：两个参数 `a: unknown` 和 `b: unknown`，即任意 JavaScript 值（第 273 行 `function isDeepEqualJson(a: unknown, b: unknown): boolean`）。

**输出**：返回 `boolean`，表示两个值是否“深度结构相等”（第 273 行返回类型 `boolean`）。

**副作用**：无。函数是纯函数，不修改任何外部状态、文件或全局数据。它只读取参数并返回布尔值，内部没有赋值给外部变量、没有调用任何修改性 API。

**前置条件**：无特殊前置条件。函数接受任意值，不要求参数是特定类型。但根据 docstring（第 270-272 行）和实现，它只对“session-event JSON 值域”（null/boolean/number/string、数组、普通对象）有定义；对函数、Symbol、Date、Map 等非 JSON 值，行为未定义（会走 `typeof a !== 'object'` 分支返回 false，或对函数对象比较时可能因 `Object.keys` 返回空数组而误判相等）。

**调用后保证**：
1. 若 `a === b`（严格相等，含同一引用），直接返回 `true`（第 274 行 `if (a === b) return true`）。
2. 若任一参数是数组，则要求两者都是数组且长度相等，然后递归比较每个元素（第 275-277 行）。
3. 若任一参数是对象（非 null），则要求两者都是非 null 对象，且键的数量相等，且每个键在对方中存在且递归相等（第 278-281 行）。
4. 若类型不匹配（一个数组一个非数组、一个对象一个非对象、或任一为 null），返回 `false`（第 275、278 行）。
5. 对普通对象，比较的是“自有可枚举键”（`Object.keys`），且用 `Object.hasOwn` 检查键存在性（第 280-281 行），不比较原型链、不比较不可枚举属性、不比较符号键。

**【调用方须知】**：该函数对“普通对象”的相等判断只比较自有可枚举键（`Object.keys`），因此两个对象若键相同但值不同会返回 false，但若两个对象键相同且值相同，即使原型不同（如一个是 `Object.create(null)` 一个是普通对象）也会返回 true；反之，若对象有不可枚举属性或 Symbol 键，这些属性会被完全忽略——例如 `{a:1}` 与 `{a:1, [Symbol()]: 2}` 会被判为相等，因为 `Object.keys` 不包含 Symbol 键。若你的调用方依赖这些属性参与比较，会得到意外结果。此外，函数对 `Date`、`Map`、`Set`、`RegExp` 等非 JSON 对象会退化为“键比较”，例如两个 `new Date(0)` 和 `new Date(1)` 因 `Object.keys` 都为空数组而返回 `true`，这通常不是期望的深度相等语义。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件和行为描述均与代码逐行吻合，包括对非JSON值（如Date、Symbol）的退化行为，以及只比较自有可枚举键的细节，均准确无误。*

### [B] src\surface.ts :: surfaceOpOf（第185行，复杂度10）

函数 `surfaceOpOf`（src/surface.ts 第185-207行）的契约如下：

**输入**：一个 `SessionEvent` 类型的参数 `event`（第185行 `function surfaceOpOf(event: SessionEvent)`）。

**输出**：返回 `SurfaceOp | undefined`（第185行）。具体为：
- 当事件类型是 surface-eligible（即 `user/message`、`assistant/message`、`tool/result` 之一，见第20-22行 `SURFACE_EVENT_TYPES`）且 `surfaceOp` 为字符串 `'append'` 时，直接返回 `'append'`（第198行 `if (op === 'append') return op`）。
- 当事件类型 surface-eligible 且 `surfaceOp` 是合法的 replace 形状对象时，返回该对象（第206行 `return op`）。
- 当事件类型不是 surface-eligible 时返回 `undefined`（第195行 `return`）。

**副作用**：无。该函数是纯校验/提取函数，不修改任何外部状态、文件或全局数据。它只读取 `event` 上的 `surfaceOp` 和 `sourceEventSeqs` 字段（第186行 `const raw = event as SessionEvent & { surfaceOp?: unknown; sourceEventSeqs?: unknown }`），不改变 `event` 本身，也不触碰 `SurfaceFoldState` 等可变状态。

**前置条件**：
1. 事件类型必须是 surface-eligible（`user/message`、`assistant/message`、`tool/result`），否则函数会抛错（见下）。
2. 若事件类型是 surface-eligible，则 `surfaceOp` 字段必须存在（不能是 `undefined`），否则抛错（第196-197行 `if (op === undefined) { throw new Error(...) }`）。
3. 若 `surfaceOp` 不是 `'append'`，则它必须是合法的 replace 形状：一个非 null、非数组的普通对象，且恰好有 `op`、`start`、`end` 三个键，`op === 'replace'`，`start` 和 `end` 都是非负安全整数（第199-205行，以及第170-183行 `isReplaceOp` 的定义）。

**调用后保证**：
- 若返回 `undefined`，则事件类型不是 surface-eligible，且该事件上既没有 `surfaceOp` 也没有 `sourceEventSeqs` 字段（否则会抛错，见第188-194行）。
- 若返回 `'append'`，则事件类型 surface-eligible 且 `surfaceOp === 'append'`。
- 若返回 replace 对象，则它满足 `isReplaceOp` 的全部约束（三个键、`op==='replace'`、`start`/`end` 为非负安全整数）。
- 函数不抛错时，返回值的类型是可信的（`SurfaceOp` 联合类型）。

**抛错情况**（违反前置条件时）：
- 非 surface-eligible 事件却携带 `surfaceOp`：抛 `session event "${event.type}" is not surface-eligible and cannot carry surfaceOp`（第189-191行）。
- 非 surface-eligible 事件却携带 `sourceEventSeqs`：抛 `session event "${event.type}" is not surface-eligible and cannot carry sourceEventSeqs`（第192-194行）。
- surface-eligible 事件缺少 `surfaceOp`：抛 `session event "${event.type}" is surface-eligible and requires a surfaceOp marker`（第196-197行）。
- `surfaceOp` 是 null、非对象、或数组：抛 `session event "${event.type}" carries an invalid surfaceOp`（第199-200行）。
- `surfaceOp` 不是合法 replace 形状：抛 `session event "${event.type}" carries an invalid replace surfaceOp`（第203-204行）。

【调用方须知】最容易忽略的是：这个函数对**非 surface-eligible 事件**（如 `chunk`、`boundary`、`log-only` 等）会**静默返回 `undefined`**，但前提是该事件上**不能带 `surfaceOp` 或 `sourceEventSeqs` 字段**——一旦带了，函数会直接抛错而不是忽略。也就是说，调用方不能想当然地认为“非 surface 事件就安全返回 undefined”，如果这类事件上残留了 `surfaceOp`/`sourceEventSeqs` 元数据（例如从别处复制来的事件对象），`surfaceOpOf` 会抛异常，调用方必须确保非 surface-eligible 事件上这两个字段严格为 `undefined` 才能安全调用。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件、抛错情况的描述均与代码原文一致，且引用的行号和代码片段准确无误。特别地，关于非surface-eligible事件携带`surfaceOp`或`sourceEventSeqs`会抛错的行为，以及`isReplaceOp`的约束，均已在代码中逐条核实。*

### [B] src\surface.ts :: isReplaceOp（第173行，复杂度7）

【调用方须知】isReplaceOp 是一个纯类型守卫（type guard），它只做运行时形状校验，不读取、不修改任何外部状态、文件或全局数据，也没有任何副作用——它甚至不检查 start/end 的语义关系（比如 start <= end），只检查它们各自是非负安全整数。调用方最容易忽略的是：它要求对象恰好有 3 个自有属性（op、start、end），多一个或少一个属性都会返回 false，即使这些属性名和值都合法；另外它只校验 start/end 是安全非负整数，不校验 start <= end，也不校验 start/end 是否落在实际 surface 范围内——这些语义校验由调用方（如 assertProvenance）另行负责。

契约细节（依据 src/surface.ts 第173-181行）：

1. **输入**：一个 `object` 类型的运行时值（`value: object`）。
2. **输出**：一个类型谓词——返回 `value is Extract<SurfaceOp, { op: 'replace' }>`，即当返回 true 时，TypeScript 会把 value 收窄为 replace 类型的 SurfaceOp；返回 false 时不做任何收窄。
3. **判定条件（全部满足才返回 true）**：
   - `Object.keys(op).length === 3`：对象恰好有 3 个自有可枚举属性。
   - `Object.hasOwn(op, 'op')`、`Object.hasOwn(op, 'start')`、`Object.hasOwn(op, 'end')`：三个属性都存在。
   - `op['op'] === 'replace'`：op 字段的值严格等于字符串 'replace'。
   - `isEventSeq(op['start'])` 且 `isEventSeq(op['end'])`：start 和 end 都是非负安全整数（`typeof === 'number' && Number.isSafeInteger && >= 0`，见第166-169行）。
4. **副作用**：无。函数体只做类型断言和属性检查，不修改任何外部状态、不写文件、不改变全局数据。
5. **前置条件**：调用方需保证传入的是 `object` 类型（非 null、非数组、非原始值）。函数内部用 `value as Record<string, unknown>` 做断言，如果传入 null 或原始值，`Object.keys` 会抛 TypeError——但函数签名已限定 `value: object`，所以类型层面已排除这些情况。
6. **调用后保证**：返回 true 时，value 可安全地当作 `{ op: 'replace', start: number, end: number }` 使用（start/end 均为非负安全整数）；返回 false 时，value 不是合法的 replace 操作，调用方应拒绝该事件（如 surfaceOpOf 在第199-201行抛错）。

注意：该函数不校验 start <= end，也不校验 start/end 是否在 surface 范围内——这些由调用方（如 assertProvenance）另行处理。

*✓ 核实通过——候选答案逐条核对了函数签名、判定条件（恰好3个自有属性、op/start/end存在、op==='replace'、start/end为非负安全整数）、无副作用、前置条件（value: object）以及不校验start<=end等语义，均与代码原文一致。*

### [B] src\surface.ts :: assertToolResultRewrite（第287行，复杂度6）

函数 `assertToolResultRewrite`（src/surface.ts 第287行）的契约如下：

**输入**：
- `event: SessionEvent` — 待校验的替换事件（其 `type` 应为 `'tool/result'`，否则函数直接返回，不校验）。
- `shadowedSeqs: readonly number[]` — 被替换（遮蔽）的当前 surface 节点序列号数组。
- `events: readonly SessionEvent[]` — 完整事件日志（用于按 seq 索引查找被替换的原始事件）。
- `baseSeq: number` — 日志的起始 seq，用于将 seq 转换为数组下标（`events[originalSeq - baseSeq]`）。

**输出**：无返回值（`void`）。

**副作用**：无。函数只做校验，不修改任何外部状态、文件或全局数据；它构造的 `originalRest`/`replacementRest` 等对象都是局部变量，且通过展开运算符复制，不修改传入的 `event` 或 `events` 中的对象。

**前置条件**：
1. 调用方应已通过 `replacementRange` 等逻辑确认 `shadowedSeqs` 是被替换的当前 surface 节点（函数内部会校验其长度必须为 1）。
2. `events` 数组的索引 `originalSeq - baseSeq` 必须有效（即 `originalSeq` 在 `[baseSeq, baseSeq + events.length)` 范围内），否则 `events[originalSeq - baseSeq]` 为 `undefined`，会触发第二个错误分支。
3. `event.data.message.content` 和 `original.data.message.content` 必须是非空数组（代码直接取 `[0]`，若为空会抛 TypeError，但这不是函数显式契约）。

**调用后保证**：
- 若 `event.type !== 'tool/result'`，函数静默返回，不做任何校验。
- 若 `shadowedSeqs.length !== 1`，抛出 `Error('tool/result surface replacement must rewrite exactly one current node')`。
- 若被替换的原始事件不是 `'tool/result'` 类型，抛出 `Error('tool/result surface replacement must target a current tool/result')`。
- 若替换事件与被替换事件在“除 `message.content[0].content` 之外的所有字段”上不深度相等（通过 `isDeepEqualJson` 比较），抛出 `Error('tool/result surface replacement may change only content')`。
- 若所有校验通过，函数正常返回，表示该替换合法——即替换只允许修改单个 tool/result 的 `message.content[0].content` 字段，其余字段必须与被替换的原始事件完全一致。

**关键实现细节**（依据代码原文）：
- 比较时，代码将 `original.data.message.content[0]` 和 `event.data.message.content[0]` 的 `content` 字段显式置为 `null`（`content: null`），再比较其余部分，从而“豁免” `content` 字段的差异。
- 比较的是 `original.data` 与 `event.data` 的完整结构（包括 `message` 及其 `content` 数组），但 `content` 数组只比较第一个元素（`content[0]`），且该元素的 `content` 字段被置空后参与比较。

【调用方须知】函数名 `assertToolResultRewrite` 字面意思是“断言工具结果重写”，但它的校验范围远不止“重写”本身：它要求替换事件与被替换事件在**除 `message.content[0].content` 之外的所有字段**（包括 `message` 的其他字段、`content` 数组的长度、`content[0]` 的其他字段如 `type`/`id` 等）都深度相等——也就是说，一次替换**只能改 `content[0].content` 这一个字段**，任何其他字段（哪怕只是 `content` 数组多一个元素、或 `content[0]` 的 `type` 变了）都会抛错。调用方最容易忽略的是：`content` 数组**长度必须为 1**（代码只取 `[0]`），且 `content[0]` 的 `content` 字段被置空比较，意味着如果原始 `content[0]` 本身没有 `content` 字段（或为 `undefined`），替换后也必须保持同样缺失，否则 `isDeepEqualJson` 会因键集合不同而判定不等并抛错。

*✓ 核实通过——逐行核对代码，候选答案对输入参数、输出、副作用、前置条件、错误分支和比较逻辑的描述均与源码一致，且引用的代码原文准确。特别确认了 `content` 数组只取 `[0]`、`content` 字段置空比较、以及 `isDeepEqualJson` 的深度比较行为，候选答案的【调用方须知】也准确指出了这些关键点。*

### [B] src\surface.ts :: _processDelta（第444行，复杂度6）

基于对 src/surface.ts 全文（第1-460行）的阅读，`_processDelta`（第444行，`SurfaceManager` 的私有方法）的契约如下：

**输入**：无显式参数。它读取实例私有字段 `this._lastProcessedSeq`、`this.log`、`this.baseSeq`、`this._pendingPlan` 和 `this._state`。

**输出**：无返回值（`void`）。

**副作用（改了什么外部状态）**：
- 修改 `this._state`（`SurfaceFoldState`）：通过 `applySurfacePlan` 或 `applySurfaceEvent` 改变 `state.nodes`（追加或替换节点）和 `state.replaceGeneration`（替换时 +1）。
- 修改 `this._lastProcessedSeq`：循环末尾 `this._lastProcessedSeq = seq`，推进已处理游标。
- 修改 `this._pendingPlan`：当 `pending.expectedSeq <= seq` 时置为 `undefined`（第458行）。
- 注意：它不直接改 `this.log`（log 是只读的），也不改任何文件/全局数据。

**前置条件**：
- 调用方（`validateNext`、`replaceGeneration` getter、`nodes` getter）在调用前都检查 `this._lastProcessedSeq < this.baseSeq + this.log.length - 1`，即存在尚未折叠的日志事件。
- `this.log` 必须是连续完整日志或已加载事件窗口，且 `this.baseSeq` 是窗口首事件的绝对序号（构造函数注释）。
- 循环内 `this.log[index]!` 的非空断言依赖循环边界 `seq <= tailSeq` 保证 index 在数组范围内。

**调用后保证**：
- 所有从 `_lastProcessedSeq+1` 到 `tailSeq` 的事件都被折叠进 `_state`，`_lastProcessedSeq` 更新为 `tailSeq`。
- 若 `_pendingPlan` 存在且其 `expectedSeq` 与当前 seq 匹配且 `pending.event === event`（即该事件正是 `validateNext` 验证过的候选），则直接应用已验证的 `pending.plan`（第452-454行），否则重新走 `applySurfaceEvent` 完整校验（第455-456行）。
- 折叠后 `_state.nodes` 反映模型可见顺序，`_state.replaceGeneration` 反映替换次数。

**【调用方须知】**：`_processDelta` 在折叠时若 `_pendingPlan` 存在且其 `expectedSeq <= seq`，会在处理完该 seq 后立即把 `_pendingPlan` 置为 `undefined`（第458行），这意味着 `validateNext` 的预验证结果只对“下一个恰好进入日志的事件”生效——如果调用方在 `validateNext` 之后、该候选事件真正进入日志之前，又调用了 `nodes`/`replaceGeneration` 触发了 `_processDelta`，且此时日志尾部事件与候选事件不是同一个对象（`pending.event === event` 用引用相等比较），那么候选的预验证计划会被丢弃，后续该事件进入日志时会走完整的 `applySurfaceEvent` 重新校验（可能抛错），调用方不能依赖 `validateNext` 的“无异常”结果来保证后续折叠不抛错——必须确保候选事件对象与最终写入日志的对象是同一个引用，否则预验证形同虚设。

*✓ 核实通过——候选答案对 _processDelta 的契约描述（输入、输出、副作用、前置条件、调用后保证）逐条与代码原文吻合，且【调用方须知】中关于 _pendingPlan 在 expectedSeq <= seq 时被置 undefined、以及 pending.event === event 引用相等比较的警告，均准确反映了代码第458行和第452行的实际行为。*

### [B] tests\properties.spec.ts :: (anonymous)（第138行，复杂度6）

在 tests/properties.spec.ts 第138行的「(anonymous)」是第137-151行 `it('non-message events never affect derived history (any interleaving)', ...)` 测试用例中 `fc.property` 的回调函数（第138行 `(messages, noise, pick) => {`）。它的契约如下：

**输入**：
- `messages: Appendable[]`（由 `fc.array(messageEventArb, { maxLength: 12 })` 生成，第133行），是消息类事件数组，每个元素都带 `intent: { surfaceOp: 'append' }`（见第30-31行注释和 `messageEventArb` 定义）。
- `noise: Appendable[]`（由 `fc.array(nonMessageEventArb, { maxLength: 12 })` 生成，第134行），是非消息事件数组（如 turn/start、assistant/chunk 等，见第62-70行）。
- `pick: fc.infiniteStream(fc.boolean())`（第135行），一个无限布尔流，用于决定交错时优先取哪个流。

**输出**：无返回值（`void`），它只做断言（`expect`）。

**副作用**：
- 调用 `build(messages)` 和 `build(interleaved)`（第139、150行），而 `build` 内部调用 `Session.create(SessionId(`prop-${counter++}`))`（第84行），会递增模块级变量 `counter`（第82行 `let counter = 0`），即每次调用都会改变 `counter` 这个全局状态。
- 调用 `deriveMessages()` 本身不修改 `session.events`（测试最后 `expect(session.events).toEqual(before)` 验证了这一点，见第170行）。

**前置条件**：
- `messages` 和 `noise` 的元素必须符合 `Appendable` 类型（第20-23行），且 `messages` 中的元素必须带 `intent`（否则 `build` 会走 `session.append(e.type, e.data)` 分支，见第87-88行，但测试的 `messageEventArb` 都带 intent）。
- `pick` 必须是一个可迭代的无限布尔流（`pick[Symbol.iterator]()` 在第142行被调用）。

**调用后保证**：
- 断言 `withNoise.deriveMessages()` 与 `clean.deriveMessages()` 深度相等（第151行 `expect(withNoise).toEqual(clean)`），即非消息事件无论怎么交错插入，都不影响派生历史。
- 交错算法保证两个流各自的相对顺序不变（第143-149行的 while 循环，`takeNoise` 逻辑确保只在 noise 可用且（messages 耗尽或 picker 为 true）时取 noise）。

【调用方须知】这个回调函数会通过 `build` 递增模块级变量 `counter`（第82、84行），每次调用都会改变这个全局计数器；如果测试框架并行运行多个 property 测试，这个共享的可变状态可能导致 `SessionId` 冲突或测试间相互干扰，务必注意 `counter` 不是线程/测试隔离的。

*✓ 核实通过——逐条核对了候选答案引用的行号和代码原文，所有描述（输入、输出、副作用、前置条件、保证）均与文件实际内容一致，特别是 `counter` 副作用和交错逻辑。候选答案准确反映了代码行为。*

### [B] tests\session.spec.ts :: (anonymous)（第927行，复杂度6）

第927行的「(anonymous)」是测试用例 `it('iteratively freezes deeply nested restored event data', () => { ... })` 的回调函数（匿名箭头函数），它本身没有对外部调用方的契约——它是测试框架（Jest）调用的一个测试体，不是被业务代码调用的函数。它的“输入”是测试框架注入的（无参数），输出是断言结果（通过/失败），副作用是执行了 `Session.fromRestore` 并验证其行为。

依据代码原文：
- 输入：无参数（`() => {`），内部构造了深度为 20_000 的嵌套对象 `data`（第929-934行：`const depth = 20_000; const data = {}; let tail = data; for (...) { tail['child'] = child; tail = child; }`），并构造了一个 `event`（第936-940行：`{ type: 'test/deep-restore', seq: 0, time: 1, data }`）。
- 输出：无返回值，通过 `expect(...).not.toThrow()`（第942-947行）和 `expect(frozenNodes).toBe(depth + 2)`（第958行）断言。
- 副作用：调用了 `Session.fromRestore(SessionId('deep-restore'), [event], {...})`（第942-947行），这会创建/恢复一个 Session 对象（可能写入内存中的 session 存储），并深度冻结 `event` 及其嵌套数据（第950-957行遍历验证 `Object.isFrozen`）。
- 前置条件：`Session.fromRestore` 可被调用且不抛异常；`SessionEvent`、`SessionId`、`SESSION_FORMAT_VERSION` 等类型/常量在测试作用域内可用。
- 调用后保证：`Session.fromRestore` 对深度 20_000 的嵌套数据不抛错，且返回的 event 数据被深度冻结（`frozenNodes` 等于 `depth + 2`，即 event 本身 + data 链上每个节点 + 最内层 child）。

【调用方须知】这个测试用例验证的是 `Session.fromRestore` 对**极深嵌套（20_000 层）**数据能迭代式冻结而不爆栈——如果调用方自己实现类似深度冻结逻辑，必须用迭代而非递归，否则在深层数据上会栈溢出；同时它断言冻结节点数恰好是 `depth + 2`，意味着 event 对象本身和 data 链上每一层（包括最内层 child）都必须被冻结，漏掉任何一层都会让 `frozenNodes` 计数中断。

*✓ 核实通过——The candidate answer accurately describes the anonymous function's contract based on the actual code in the test file, including the specific depth, event structure, Session.fromRestore call, and the frozen node count assertion.*


### 批次「system-prompt」

# 项目体检报告

共6个文件（另有0个不支持的文件类型被跳过），总行数1576

## 项目叙述（✓ 核实通过）

项目定位描述（依据：README.md、src/index.ts、src/invariant.ts、tests/*.spec.ts）

## 1. 项目是什么
`@deepseek-ai/dsh-system-prompt` 是一个 Cordis 插件/服务，负责在 DeepSeek Harness 智能体循环中，**按步骤组装发给模型的完整 system prompt**。它把 system prompt 拆成可注册的“片段（section）”、动态上下文（context）、工具 schema 和命名变量（variable），每次模型请求前组装一次并渲染成最终提示词。

面向场景/用户：DeepSeek Harness 的插件生态——各插件（工具包、agent 循环等）通过它贡献自己拥有的提示词片段；部署方通过配置提供全局 persona；agent 可通过 scoped 层覆盖全局。解决的问题：把“模型被告知它是什么、能做什么、当前环境是什么”组织成一个有序、可扩展、可被瀑布流拦截的单一装配流程。

## 2. 模块组成与职责
- **src/index.ts**：核心服务 `SystemPrompt`。职责：
  - 注册/管理 section、context、tool provider、variable（按 scope 分层，`ScopedLayers`）；
  - `assemble()` 合并全局与 scope 层、解析 provider、排序、跑 `system-prompt/assemble` 瀑布流、恢复 complete section；
  - `renderPrompt`/`renderContextSnapshot`/`renderContextSections`/`joinContextSections` 做严格变量插值与渲染；
  - 工具排序（`orderTools`/`validateToolOrder`）与 `TOOL_ORDER_REST` 保留名。
- **src/invariant.ts**：companion 插件 `system-prompt-invariant`，在 `system-prompt/assemble` 瀑布流结果上做校验（section/context/tool 名字非空且不重复、text 为字符串、变量名合法且值为 string|undefined）。
- **tests/**：system-prompt.spec.ts（核心机制）、tool-order.spec.ts（工具排序）、scoped.spec.ts（scope 分层）、invariant.spec.ts（不变量校验）。

## 3. 关键不变量（含证据范围）
以下每条都注明观察到的入口（测试文件 + 具体用例），未覆盖的入口明确说明。

### I1. 内置 section 恒定存在且名字保留
- 默认装配始终包含 `harness:identity`（order -100，文本 `You are an AI agent powered by DeepSeek Harness.`）和 `deployment:persona`（order 0，来自 config.persona）。
- 证据：`src/index.ts` 构造函数（`this.section({name:'harness:identity', order:-100, ...})`、`this.section({name:PERSONA_SECTION, order:PERSONA_ORDER, ...})`）；`tests/system-prompt.spec.ts` 的 `built-in sections` describe 块（`registers the harness identity...`、`renders no persona section...`、`can omit the harness identity...`）。
- 例外（有明确证据）：`includeHarnessIdentity:false` 时省略 identity（同 describe 的 `can omit...` 用例）；`persona` 为空时 persona section 在渲染时被丢弃（`renders no persona section...` 用例）。
- 范围：这两个内置 section 的注册发生在 `SystemPrompt` 构造函数，对所有 `assemble()` 生效；测试覆盖了 `ctx.plugin(SystemPrompt, config)` 入口。

### I2. 同一层内 section/context/variable 名字唯一，重复注册抛错且不泄漏
- 证据：`src/index.ts` 中 `PromptLayer` 构造函数用 `NamedEntries` 生成“already registered”错误；`tests/system-prompt.spec.ts` 的 `rejects a duplicate section name...`、`rejects duplicate and non-finite context registrations...`、`rejects a duplicate variable name...`；`tests/scoped.spec.ts` 的 `duplicate names throw per layer...`、`same-layer duplicates throw...`。
- 范围：覆盖 `ctx.systemPrompt.section/context/variable` 三个注册入口（全局与 scoped 层）。

### I3. 注册/注销触发 `system-prompt/change`，且监听器抛错时注册回滚（不泄漏）
- 证据：`src/index.ts` 中 `layers` 的 `() => this.ctx.emit('system-prompt/change')`；`tests/system-prompt.spec.ts` 的 `rolls back a section when a system-prompt/change listener throws (P1-1)`、`rolls back a tool provider...`、`rolls back a variable...`、`emits system-prompt/change when a tool provider is registered and disposed`、`emits system-prompt/change when a context is registered and disposed`。
- 范围：覆盖 section、tool provider、variable 三个注册入口；context 的注册/注销触发 change 有测试（`emits...context...`），但 context 注册时监听器抛错回滚**没有**专门测试用例（只有 section/tool/variable 有 P1-1 回滚测试）。

### I4. 装配结果是一次性快照，调用方修改不泄漏到后续装配
- 证据：`tests/system-prompt.spec.ts` 的 `assembles snapshots so one-step mutations do not leak into future assemblies`（修改 sections/contexts/tools/parameters 后再次 assemble 得到干净结果）。
- 范围：覆盖 `ctx.systemPrompt.assemble()` 入口；工具参数通过 `structuredClone` 深拷贝（`src/index.ts` assemble 内 `parameters: structuredClone(parameters)`）。

### I5. 变量插值严格：未知/未赋值/畸形引用抛错，`{{` 无 `}}` 时按字面保留，替换值不再扫描
- 证据：`src/index.ts` 的 `interpolate` 函数；`tests/system-prompt.spec.ts` 的 `prompt variables` describe 块（`throws on a reference to an unregistered variable...`、`throws when a referenced variable has no value...`、`throws on a malformed complete reference...`、`leaves a lone {{ verbatim only when NO }} follows...`、`rejects {{constructor}} as UNKNOWN...`、`never re-scans substituted values...`）。
- 范围：覆盖 `renderPrompt` 和 `renderContextSnapshot` 两个渲染入口（`interpolate` 同时服务 section 与 context）。

### I6. 工具排序：无 toolOrder 时按字典序；有 toolOrder 时列出的工具占位、未列出的在 rest 入口按字典序；配置错误在加载或装配时抛错
- 证据：`src/index.ts` 的 `validateToolOrder`/`orderTools`；`tests/tool-order.spec.ts` 全部用例（`assembles tools in lexicographic...`、`applies a configured toolOrder...`、`rejects the assembly when toolOrder names a tool that is not registered...`、`rejects a provider tool named like the reserved rest entry...`、`rejects ... at load` 等）。
- 范围：覆盖 `assemble()` 入口（装配时校验未知工具名、保留名）和 `ctx.plugin(SystemPrompt, {toolOrder})` 加载入口（缺 rest 入口/重复抛错）。

### I7. 工具排序在瀑布流之前完成；瀑布流监听器追加的工具不再排序
- 证据：`tests/tool-order.spec.ts` 的 `canonicalizes BEFORE the assemble waterfall...`（监听器看到已排序列表，追加的 `aardvark` 不被重排）。
- 范围：覆盖 `assemble()` 入口。

### I8. 多个 complete section 使装配失败；单个 complete section 在瀑布流后恢复为唯一 section
- 证据：`src/index.ts` assemble 中 `completeSections.length > 1` 抛错、`completeSection` 恢复逻辑；`tests/system-prompt.spec.ts` 的 `restores one complete section after the assembly waterfall`、`rejects multiple effective complete sections`。
- 范围：覆盖 `assemble()` 入口。

### I9. 瀑布流监听器按注册顺序执行，可短路（不调 next）；scope 过滤
- 证据：`tests/system-prompt.spec.ts` 的 `composes multiple system-prompt/assemble waterfall listeners in order...`、`lets a waterfall listener short-circuit by not calling next()`；`tests/scoped.spec.ts` 的 `an agent.ctx assemble listener shapes only its own scope's assemblies`。
- 范围：覆盖 `assemble()` 入口（全局与 scoped 监听器）。

### I10. scoped 层 shadow 全局同名 section/context/variable，且只对该 scope 生效；scope 销毁后清理
- 证据：`tests/scoped.spec.ts` 的 `a scoped persona shadows deployment:persona...`、`scoped-only sections join that scope alone...`、`a scoped variable shadows its global name-twin...`、`shadows a global context for one scope...`、`scoped providers are consulted only for their scope`。
- 范围：覆盖 `assemble({scope})` 入口（section/context/variable/tool provider 四类）。

### I11. `includeRuntimeContext:false` 或 scoped suppressor 使装配的 contexts 为空，且不评估 context provider、不接受瀑布流追加的 context
- 证据：`tests/system-prompt.spec.ts` 的 `can suppress runtime context without evaluating providers or accepting waterfall additions`；`tests/scoped.spec.ts` 的 `suppresses all context for one scope and restores it when disposed`。
- 范围：覆盖 `assemble()` 入口（全局配置与 scoped suppressor 两条路径）。

### I12. 装配结果（瀑布流权威值）满足结构不变量：section/context/tool 名字非空且不重复、text 为字符串、变量名合法且值为 string|undefined
- 证据：`src/invariant.ts` 的 `validateAssembly`；`tests/invariant.spec.ts` 全部用例（`accepts a well-formed authoritative assembly`、`rejects malformed authoritative assembly` 的 9 个失败分支）。
- 范围：覆盖 `system-prompt/assemble` 瀑布流结果（通过 `ctx.waterfall` 入口，companion 插件 `system-prompt-invariant` 安装后生效）。

### I13. 注册的 section/context 的 order 必须为有限数，否则抛错
- 证据：`src/index.ts` 的 `section`/`context` 方法中 `Number.isFinite` 检查；`tests/system-prompt.spec.ts` 的 `rejects a non-finite section order`、`rejects duplicate and non-finite context registrations...`。
- 范围：覆盖 `ctx.systemPrompt.section`/`context` 两个注册入口。

### I14. 变量名必须匹配 `[a-z][a-z0-9_]*`，否则注册抛错
- 证据：`src/index.ts` 的 `variable` 方法中 `VARIABLE_NAME.test`；`tests/system-prompt.spec.ts` 的 `rejects a duplicate variable name and an unreferenceable name`（`Not Valid` 用例）。
- 范围：覆盖 `ctx.systemPrompt.variable` 注册入口。

## 4. 设计特点与取舍
- **严格失败优先（fail loud）**：未知变量、畸形引用、重复名字、配置错误的 toolOrder、多个 complete section 都直接抛错，而不是静默产出坏提示词（README 明确“fail loud beats shipping a malformed prompt”）。
- **装配与渲染分离**：`assemble()` 产出未插值的 sections/contexts + 已排序 tools + 已解析 variables；`renderPrompt` 才做插值。瀑布流在装配阶段拦截，complete section 在瀑布流后强制恢复。
- **scope 分层**：全局与 agent 级 scoped 层，scoped 覆盖全局同名项，支持按 agent 定制 persona/变量/上下文/工具，且随 scope 生命周期清理。
- **工具顺序显式化**：用中心化 `toolOrder` 配置（而非 per-plugin 权重）保证模型看到的工具顺序确定，且与注册顺序解耦（README 引用设计笔记）。
- **无字面 `{{}}` 转义**：所有完整 `{{...}}` 组都按变量插值，转义语法被推迟（README Known Limitations）。
- **无最终用户提示词编辑 API**：部署方只能通过配置/插件贡献，没有运行时编辑入口（README Known Limitations）。
- **快照隔离**：每次装配产出独立对象，防止调用方/监听器的一次性修改污染后续请求（I4）。

## 5. 范围限制说明
- 上述不变量大多在 `assemble()` 与各注册入口（`section`/`context`/`variable`/`tools`/`suppressRuntimeContext`）上观察到；`renderPrompt`/`renderContextSnapshot` 的插值规则（I5）在渲染入口验证。
- **未覆盖的入口**：没有针对 `ctx.systemPrompt.tools()` 注册时监听器抛错回滚的专门测试（I3 只覆盖了 section/tool/variable 的 P1-1 回滚，tool 的 P1-1 有测试，但 context 的 P1-1 回滚无测试）；`renderPrompt` 对 `{{` 无 `}}` 的字面保留规则只在 section 上测试，context 上未单独测试（但 `interpolate` 共用同一逻辑）。
- 所有不变量均基于本仓库的 `src/` 与 `tests/` 观察，未涉及外部 `dsh-scope`/`dsh-llm`/`dsh-invariants` 包内部实现。

## 行为 vs 项目叙述 对照结果

共2个函数：0个违反不变量、0个无法判断、2个支撑项目正确运行（不再展开）

### 支撑项目正确运行（2个，不再展开）

src\index.ts::orderTools、src\invariant.ts::validateAssembly


## 复杂度分级分布

- [A] 213个函数/类
- [C] 2个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [C] src\invariant.ts :: validateAssembly（第16行）复杂度=15
  [C] src\index.ts :: orderTools（第164行）复杂度=11
  [A] src\index.ts :: validateToolOrder（第146行）复杂度=5
  [A] src\index.ts :: (anonymous)（第170行）复杂度=2
  [A] tests\scoped.spec.ts :: (anonymous)（第66行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第182行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第200行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第216行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第235行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第291行）复杂度=2
  [A] tests\system-prompt.spec.ts :: (anonymous)（第453行）复杂度=2
  [A] tests\tool-order.spec.ts :: (anonymous)（第67行）复杂度=2
  [A] src\index.ts :: (anonymous)（第165行）复杂度=1
  [A] src\invariant.ts :: (anonymous)（第47行）复杂度=1
  [A] src\invariant.ts :: install（第46行）复杂度=1

## 行为描述明细（B级以上，共2个）

### [C] src\index.ts :: orderTools（第164行，复杂度11）

orderTools 是 src/index.ts 第164行定义的一个模块私有函数（未 export），契约如下：

**输入**（三个参数，见第164行签名）：
- `tools: ToolSchema[]`：本次 assembly 收集到的工具 schema 数组（来自所有 tool provider，见 assemble 中 `collected`）。
- `toolOrder: string[] | undefined`：配置的 `Config.toolOrder`（已在构造函数中经 `validateToolOrder` 校验，见第130行 `this.toolOrder = validateToolOrder(config.toolOrder)`）。
- `knownNames: ReadonlySet<string>`：预限制前的工具名全集（来自各 provider 的 `knownNames ?? schemas` 名，见 assemble 中 `acceptedKnownNames`）。

**输出**：`ToolSchema[]`，即按配置顺序排列的工具数组。

**副作用**：
- 当 `toolOrder === undefined` 时，直接对传入的 `tools` 数组调用 `tools.sort(compareToolNames)`（第173行），**原地修改了调用方传入的数组**（sort 是 in-place），并按字典序（code-unit 比较，见 compareToolNames 第190-192行）排序。
- 当 `toolOrder` 存在时，不修改 `tools`，而是通过 `flatMap` 构造新数组返回（第181行）。

**前置条件**：
- `toolOrder` 若存在，必须已通过 `validateToolOrder` 校验（含唯一性和必须含 `TOOL_ORDER_REST` 标记），否则构造函数已抛错。
- `tools` 中不得含有名为 `TOOL_ORDER_REST`（`'<unlisted-tools>'`）的工具，否则抛错（第166-168行）。
- `toolOrder` 中除 `TOOL_ORDER_REST` 外的每个名字必须存在于 `knownNames` 中，否则抛错（第170-172行）。

**后置保证**：
- 返回数组中，`toolOrder` 中列出的工具按配置顺序出现；未列出的工具（不在 `toolOrder` 中）被收集到 `rest`，按字典序排序后插入到 `TOOL_ORDER_REST` 标记的位置（第179-181行）。
- 若 `toolOrder` 为 undefined，返回按字典序排序的数组。
- 函数不抛错时，返回的数组包含 `tools` 中所有工具（无遗漏、无重复）。

【调用方须知】当 `toolOrder` 为 undefined 时，orderTools 会**原地排序**调用方传入的 `tools` 数组（`tools.sort(compareToolNames)`，第173行），这会修改调用方持有的数组引用；如果调用方后续还依赖该数组的原始顺序，会得到被排序后的结果——在 assemble 中该数组是刚构造的 `collected`，无此问题，但若复用同一数组多次调用需注意。

*✓ 核实通过——候选答案对函数签名、参数来源、副作用（原地sort）、前置条件（保留名和未知名检查）及后置行为（flatMap构造新数组）的描述均与代码原文一致，且调用方须知准确指出了undefined时原地排序的副作用。*

### [C] src\invariant.ts :: validateAssembly（第16行，复杂度15）

函数 `validateAssembly`（第16行）是 `src/invariant.ts` 内的私有函数，不导出，仅被同文件 `install` 中的 `ctx.on('system-prompt/assemble', ...)` 回调调用。其契约如下：

**输入**：
- `assembly: PromptAssembly`（第17行）——由 `next()` 返回的权威组装结果，包含 `sections`、`contexts`、`tools`、`variables` 四个字段。
- `fail: InvariantFailure`（第17行）——一个回调，用于报告不变量失败。

**输出**：无返回值（`void`，第17行）。

**副作用**：
- 不修改 `assembly` 对象本身（只读遍历）。
- 唯一的副作用是调用 `fail(...)` 回调（第19、21、24、27、29、32、35、38、41、44行），该回调由 `install` 传入，用于向不变量系统报告失败。

**前置条件**：
- `assembly` 必须是一个对象，且其 `sections`、`contexts`、`tools` 为可迭代数组，`variables` 为可枚举对象（第18、26、33、37行）。
- `fail` 必须是一个可调用函数。

**后置保证**（对每个字段）：
- `sections`：每个 `section.name` 非空（第19行），名称不重复（第21行），`section.text` 必须是字符串（第24行）。
- `contexts`：每个 `context.name` 非空（第29行），名称不重复（第32行），`context.text` 必须是字符串（第35行）。
- `tools`：每个 `tool.name` 非空（第38行）。
- `variables`：每个键名必须匹配 `/^[a-z][a-z0-9_]*$/`（第40行，即小写字母开头、仅含小写字母/数字/下划线），值必须是字符串或 `undefined`（第41-44行）。

**调用方须知**：调用方最容易忽略的是 `variables` 的键名校验（第40行）——它要求变量名必须以小写字母开头且只能包含小写字母、数字和下划线，因此任何以大写字母、数字或下划线开头的变量名（如 `Foo`、`1x`、`_x`）都会触发 `fail`，即使该变量值合法（字符串或 `undefined`）也会被拒绝；同时 `variables` 中值为 `undefined` 的键是允许的（第41行），但键名仍必须通过正则校验。

*✓ 核实通过——候选答案逐条对应代码原文，所有引用的行号和逻辑均与文件内容一致，且调用方须知准确指出了变量名正则校验的严格性。*


### 批次「tools」

# 项目体检报告

共22个文件（另有0个不支持的文件类型被跳过），总行数13796

## 项目叙述（✓ 核实通过）

项目定位描述（依据：src/index.ts、src/code-mode.ts、src/schema.ts、src/json-schema.ts、src/ts-types.ts、src/py-types.ts、src/invariant.ts、README.md）

## 1. 项目是什么

`@deepseek-ai/dsh-tools` 是一个**工具注册表与执行流水线**（tool registry and execution pipeline）。它面向 agent 循环（agent loop）与工具插件作者：工具插件通过 `ctx.tools.register()` 注册自己的 schema 和执行函数；agent 循环通过 `ctx.tools.execute()` 执行每一次工具调用。它解决的核心问题是：把“工具如何被模型看到（presentation）”“工具调用如何被策略门控（pre-execute/guard）”“工具结果如何被规范化、渲染、观察（post-execute/finalize/result）”统一成一条确定性的流水线，并支持原生函数调用（native）与 Code Mode（`run_code` 传输 + 生成的 SDK）两种模型呈现方式。

## 2. 主要模块与职责边界

- **src/index.ts** — 核心：`ToolRuntime` 服务。负责注册（`register`）、作用域遮蔽（scoped shadowing）、限制（`restrict`）、守卫（`guard`）、执行流水线（`execute` → pre-execute → guard → execute → post-execute → finalizeContent → result）、呈现模式（`mode`/`presentAs`）、Code Mode 的 `run_code` 传输装配与 collapse 判定。
- **src/code-mode.ts** — `run_code` 传输本身：`createRunCodeTool` 构造该工具定义，实现 SDK 子调度的调度器（并发池、exclusive 屏障、settlement 纪律）、`ToolCallError` 契约、`CodeRunFailedError`、`tools/code-dispatch`/`tools/code-dispatch-start` 事件、`tools/code-dispatch-log` 瀑布。
- **src/schema.ts** — 统一 schema DSL：`defineTool`、`validateArgs`、`valueSchemaSpecToJsonSchema`、`parameterSchemaSpecToJsonSchema`、`InferValue`/`InferArgs` 类型推断。
- **src/json-schema.ts** — 强制 JSON Schema 子集：`assertSupportedJsonSchema`、`assertObjectJsonSchema`、`validateJsonSchemaValue`。
- **src/ts-types.ts** — TypeScript SDK 代码生成：`jsonSchemaToTs`、`renderToolsSdk`。
- **src/py-types.ts** — Python SDK 代码生成：`jsonSchemaToPy`、`renderToolsSdkPy`。
- **src/presentation.ts** — 工具自有的 UI 呈现意图类型（`ToolCallView`/`ToolResultView` 的 card 词汇）。
- **src/testing.ts** — 测试夹具 `defineContentToolFixture`。
- **src/invariant.ts** — 流水线不变量检查插件（`tools-invariant`）。

## 3. 关键不变量（每条附证据范围）

### 3.1 工具注册必须声明合法的 `output`，且 `timeoutMs` 必须为正有限数
- 证据：`src/index.ts` 的 `register()`（约第 570 行起）——`output` 缺失或 `render` 非函数、`presentationMeta` 非函数时抛 `TypeError`；`timeoutMs` 非正有限数时抛 `TypeError`。`defineTool`（`src/schema.ts`）同样在构造时校验 `timeoutMs`。
- 范围：所有通过 `register()` 或 `defineTool()` 注册的入口都遵守（`defineTool` 内部也调用 `parameterSchemaSpecToJsonSchema`/`valueSchemaSpecToJsonSchema`，最终走 `assertSupportedJsonSchema`）。

### 3.2 注册名 `run_code` 被保留，任何层都不能注册或遮蔽
- 证据：`src/index.ts` 的 `register()`——`if (name === RUN_CODE_NAME) throw new Error(...)`。`restrict()` 也拒绝命名 `RUN_CODE_NAME`。
- 范围：`register()` 与 `restrict()` 两个入口都遵守。

### 3.3 每个工具调用必须经过完整流水线，且 `tools/result` 观察到的执行对象与结果对象必须被冻结
- 证据：`src/index.ts` 的 `finishScheduledExecution()`——在 `notifyResult()` 前调用 `materializeFinalResult()`（`deepFreeze`），`notifyResult()` 中 `Object.freeze(exec)`。`src/invariant.ts` 的 `validateResult()` 检查 `Object.isFrozen(exec)`、`Object.isFrozen(result)`、`Object.isFrozen(result.content)`。
- 范围：所有通过 `execute()` 进入的调用（包括 Code Mode 子调度，因为子调度也走 `scheduler.finalize/finish`）。

### 3.4 流水线阶段顺序：pre-execute → guard → execute → post-execute → finalizeContent → result，且 guard 是单调的（不能把已拒绝的调用改回允许）
- 证据：`src/index.ts` 的 `prepareExecution()`（pre-execute 瀑布 → `guardReason` → dispatch）、`dispatchScheduledExecution()`（execute 瀑布 → body）、`finalizeScheduledExecution()`（post-execute 瀑布 → `finishScheduledExecution` 应用 `finalizeContent` → `notifyResult`）。`src/invariant.ts` 的 `internal/dispatch` 监听器检查 `tools/execute` 必须跟在 `tools/pre-execute` 之后、`tools/post-execute` 必须跟在 pre 或 execute 之后。
- 范围：所有 `execute()` 调用（含 Code Mode 子调度，因为子调度复用同一 scheduler）。

### 3.5 工具 body 返回的 canonical value 必须通过 `output.schema` 校验，且必须是 lossless JSON
- 证据：`src/index.ts` 的 `createSuccessResult()`——`snapshotToolValue`（lossless JSON 检查）→ `validateJsonSchemaValue(tool.output.schema, detached, 'value')` → 违规抛 `ToolOutputError`。`defineTool` 的 `execute` 包装器先 `validate(args)` 再调用用户 body。
- 范围：所有成功结果（包括 post-execute 替换 value 时，`postExecute()` 中 `createSuccessResult` 重新校验）。

### 3.6 参数在进入策略前必须被 lossless 快照并冻结
- 证据：`src/index.ts` 的 `createExecution()`——`snapshotJsonValue(exec.arguments)`，失败抛 `TypeError`；`deepFreeze(detached)` 后存入 execution。
- 范围：所有 `execute()` 调用（含 Code Mode 子调度，因为子调度也走 `createExecution`）。

### 3.7 取消是协作式的：body 启动前取消 → `ABORTED_BEFORE_DISPATCH`；body 启动后取消只能把成功结果替换为 `ABORTED`，且已启动的 promise 必须被 drain
- 证据：`src/index.ts` 的 `cancellationResult()`（按 `bodyInvoked` 区分）、`dispatchToolBody()`（`state.bodyInvoked = true` 后调用 body，`isAborted(signal)` 时 `toolAbortedResult`）、`toolAbortedBeforeDispatchResult()`/`toolAbortedResult()` 的 `code` 常量。
- 范围：所有 `execute()` 调用（含 Code Mode 子调度，因为子调度也走同一 pipeline）。

### 3.8 `finalizeContent` 在每次规范化结果（包括绕过 post-execute 的失败）上恰好执行一次，且只能替换 `content`
- 证据：`src/index.ts` 的 `createExecution()` 在参数物化前捕获 `finalizeContent`（`capturedFinalizer`），`finishScheduledExecution()` 中 `applyFinalContent()` 只替换 `content`。
- 范围：所有 `execute()` 调用（含 Code Mode 子调度）。

### 3.9 Code Mode 下，模型直接调用非 `run_code` 工具必须被拒绝为 `UNKNOWN_TOOL`，且发生在策略流水线之前
- 证据：`src/index.ts` 的 `collapses()`（`!nested && modeFor(scope) === 'code' && name !== RUN_CODE_NAME`）与 `createExecution()` 中 `collapsed` 分支——在 pre-execute/approval/guard 之前返回 `ToolNotFoundError`。`resolveExecution()` 也调用 `collapses`。
- 范围：`execute()` 入口（`createExecution`）与 `executionMode()` 入口都遵守。

### 3.10 Code Mode 子调度必须携带外层执行的 `parent` token，且 `tools/code-dispatch`/`tools/code-dispatch-start` 事件必须携带非空 `rootCallId`/`parentCallId`/`subCallId`，且必须落在打开的 turn 内
- 证据：`src/code-mode.ts` 的 `binding()`——`input.parent = exec.token`，`subCallId = CallId(exec.callId + ':code:' + n)`，事件 append 到 `agent.session`。`src/invariant.ts` 的 `validateDispatch()`/`seed()` 检查非空 id、root 一致性、`openTurn` 非 null。
- 范围：Code Mode 子调度（`run_code` 的 execute 内）。

### 3.11 Code Mode 子调度结果必须按提交顺序提交，且 settle 事件必须在 run 结束前全部落地
- 证据：`src/code-mode.ts` 的 `drive()`（head-of-line commit cursor）、`drainDispatches()`（`while (logWork.size > 0) await Promise.allSettled([...logWork])`）、`commit()` 中 `while (logWork.size > maxParallel) await Promise.race(logWork)`。
- 范围：`run_code` 的 execute 内。

### 3.12 `run_code` 的 SDK 语言必须与加载的 runtime 语言一致，且无 renderer 的语言必须在 prompt 装配时失败
- 证据：`src/index.ts` 的 `requireCodeRuntime()`（`Object.hasOwn(SDK_RENDERERS, runtime.language)` 否则抛错）、`sdkSection()` 的 `text` 回调。`src/code-mode.ts` 的 `resolveFlavor()`（`RUN_CODE_FLAVORS` 查表，未知语言抛错）。
- 范围：prompt 装配路径（`wireSchemas`/`sdkSection`）与 `run_code` 执行路径都遵守。

### 3.13 SDK 生成必须确定性（lexicographic 工具顺序，字节一致）且永不抛错
- 证据：`src/ts-types.ts` 的 `renderToolsSdk()`（`[...schemas].sort(...)`）、`jsonSchemaToTs()`（`try { ... } catch { return 'unknown' }`）。`src/py-types.ts` 的 `renderToolsSdkPy()`（同样 sort）、`jsonSchemaToPy()`（`try { ... } catch { return 'Any' }`）。
- 范围：两个 codegen 入口（`jsonSchemaToTs`/`jsonSchemaToPy`）与两个 SDK 渲染入口（`renderToolsSdk`/`renderToolsSdkPy`）。

### 3.14 工具参数/输出 schema 必须属于强制 JSON Schema 子集，且 `oneOf` 必须至少两个分支、`additionalProperties` 必须显式布尔（DSL 对象）
- 证据：`src/json-schema.ts` 的 `assertSupportedJsonSchema()`（`checkSchemaNode` 检查 `oneOf.length < 2`、`additionalProperties` 非布尔等）。`src/schema.ts` 的 `runSchemaCompiler()`（`additionalProperties` 必须显式 true/false）。
- 范围：`register()`（`assertSupportedJsonSchema(output.schema)`）、`defineTool()`（编译时 `assertSupportedJsonSchema`）、`valueSchemaSpecToJsonSchema`/`parameterSchemaSpecToJsonSchema`。

### 3.15 工具参数在进入 body 前必须被校验，非法参数走 `ToolArgsError`（`INVALID_ARGS`）错误结果路径
- 证据：`src/schema.ts` 的 `defineTool` 的 `execute` 包装器——`validate(args)` 违规抛 `ToolArgsError`。
- 范围：所有 `defineTool` 定义的工具（`run_code` 也通过 `defineTool` 定义，因此也遵守）。

### 3.16 呈现回调（`presentCall`/`presentResult`）必须纯且永不抛错（replay 时软校验并回退）
- 证据：`src/schema.ts` 的 `defineTool`——`presentCall`/`presentResult` 包装器 `if (validate(args).length > 0) return undefined`。
- 范围：所有 `defineTool` 定义的工具。

### 3.17 并发分类：只有 `isConcurrencySafe` 精确返回 `true` 才并行，否则排他
- 证据：`src/index.ts` 的 `executionMode()`——`concurrencySafe === true ? 'parallel' : 'exclusive'`，异常/未声明/非法输入都排他。
- 范围：`executionMode()` 入口（native loop 与 Code Mode 桥都调用它）。

### 3.18 作用域限制（`restrict`）只过滤继承的全局工具，不作用于 scope 自身注册的工具，也不作用于保留的 `run_code` 传输
- 证据：`src/index.ts` 的 `view()`——`inherited` 应用 `layers.every(layer => layer.admits(name))`，`own.tools` 直接加入 `visible`，`run_code` 在 `modeFor(scope) !== 'native'` 时追加。
- 范围：`view()` 是 `get`/`schemas`/`wireSchemas`/`sdkSchemas` 的唯一解析器，因此所有读取入口都遵守。

### 3.19 `tools/result` 是 observe-only 事件，监听器失败被包含（不失败调用）
- 证据：`src/index.ts` 的 `notifyResult()`——`reportFailure` 捕获监听器异常，`void Promise.resolve(returned).catch(reportFailure)`。
- 范围：`tools/result` 事件。

### 3.20 `tools/code-dispatch-log` 监听器失败被包含（回退到原始 content）
- 证据：`src/index.ts` 的 `shapeDispatchLog()`——`catch` 中 `logger.warn` 并返回 `dispatch.content`。
- 范围：`run_code` 桥的日志路径。

## 4. 设计特点与取舍

- **单一可见性解析器**：`view()` 是 `get`/`schemas`/`wireSchemas`/`sdkSchemas` 的唯一事实来源，保证呈现、查找、调度看到同一工具集（`src/index.ts` 注释明确说明）。
- **Code Mode 的 executor collapse**：`mode: 'code'` 下模型只能直接调用 `run_code`，其他工具必须从程序内调用；拒绝发生在策略流水线之前，且拒绝消息指明路由（`src/index.ts` 的 `collapses`/`createExecution`）。
- **协作式取消而非硬杀**：注册表保留 caller 信号，body 启动后不 abandon promise，只把成功结果替换为 `ABORTED`（`src/index.ts` 的 `dispatchToolBody`/`fuseToolSignals`）。
- **lossless JSON 边界**：参数、canonical value、呈现投影都在进入策略/离开 body 时快照并冻结，拒绝 `undefined`/`BigInt`/循环/稀疏数组/`-0`（`src/index.ts` 的 `snapshotToolValue`/`snapshotProjection`、`src/code-mode.ts` 的 `jsonNormalizeArgs`）。
- **显式工作栈而非递归**：schema 编译、校验、TS/Python 渲染都用显式栈，保证深 schema 处理内存有界（`src/schema.ts` 的 `runSchemaCompiler`、`src/json-schema.ts` 的 `checkSchemaNode`/`checkValue`、`src/ts-types.ts` 的 `renderSupportedSchema`、`src/py-types.ts` 的 `renderType`）。
- **确定性 SDK 生成**：lexicographic 工具顺序、字节一致文本，利于 prefix cache（`src/ts-types.ts`/`src/py-types.ts`）。
- **Python SDK 的语法有效性保障**：`py-types.ts` 处理 Python 关键字、NFKC 稳定性、不可打印字符、孤立代理、`MAX_LIST_NESTING` 等，保证生成的 SDK 块是合法 Python（`mode: 'code'` 下这是模型唯一的工具声明）。
- **`finalizeContent` 快照时机**：在参数物化前捕获回调，避免参数 getter 替换/清除回调导致的不一致（`src/index.ts` 的 `createExecution` 注释）。
- **`tools/pre-execute` 故意不支持参数重写**：避免日志/渲染参数与实际运行参数脱节（README 的 Known Limitations）。
- **`timeoutMs` 是声明性的**：注册表本身不强制 deadline，需要 `@deepseek-ai/dsh-tool-call-timeout-policy` 包装器（README 的 Known Limitations）。
- **Code Mode 中间值执行局部且无字节上限**：只有外层 `run_code` 输出有 worker 的 `maxOutputBytes` 硬上限（README 的 Known Limitations）。

## 行为 vs 项目叙述 对照结果

共29个函数：0个违反不变量、6个无法判断、23个支撑项目正确运行（不再展开）

### 无法判断（6个——不代表没问题，只是材料不够判断，值得人工看一眼）

- src\index.ts :: (anonymous) —— 行为描述为空，未提供任何函数行为细节，无法对照项目定位描述中的不变量进行判断。
- src\json-schema.ts :: isPlainJsonArray —— 行为描述仅涉及数组结构检查，未提及任何不变量相关的注册、执行流水线、Code Mode 或 schema 校验细节，无法判断其是否支撑项目定位。
- src\schema.ts :: runSchemaCompiler —— 行为描述未涉及任何不变量相关的具体细节，如注册校验、流水线顺序、冻结、取消等，仅描述内部编译过程，无法判断是否违反不变量。
- tests\code-mode.spec.ts :: (anonymous) —— 行为描述为空，未提供任何函数行为细节，无法对照项目定位描述中的不变量进行判断。
- tests\invariant.spec.ts :: execution —— 行为描述仅涉及测试辅助工厂构造ToolExecution的默认字段，未提及任何不变量相关的具体执行路径或流水线行为，无法判断是否违反列出的不变量。
- tests\properties.spec.ts :: checkLevel —— 行为描述仅涉及测试辅助函数对 required 集合的断言，未覆盖项目定位描述中任何具体不变量（如注册校验、流水线顺序、冻结、Code Mode 调度等）的细节，材料不足以判断支撑或削弱。

### 支撑项目正确运行（23个，不再展开）

src\code-mode.ts::driverRun、src\code-mode.ts::renderJsonValue、src\code-mode.ts::commit、src\index.ts::errorInfo、src\index.ts::register、src\index.ts::errorMessage、src\index.ts::admits、src\invariant.ts::(anonymous)、src\invariant.ts::validateDispatch、src\invariant.ts::seed、src\json-schema.ts::checkValue、src\json-schema.ts::checkSchemaNode、src\json-schema.ts::checkObjectSchemaTail、src\json-schema.ts::isPlainJsonRecord、src\json-schema.ts::scalarMatches、src\json-schema.ts::assertObjectJsonSchema、src\json-schema.ts::checkScalarValue、src\py-types.ts::renderToolsSdkPy、src\py-types.ts::pyScalar、src\ts-types.ts::docLines、tests\code-mode.spec.ts::setup、tests\code-mode.spec.ts::(anonymous)、tests\properties.spec.ts::valueForProp


## 复杂度分级分布

- [A] 1181个函数/类
- [B] 18个函数/类
- [C] 3个函数/类
- [D] 3个函数/类
- [E] 2个函数/类
- [F] 4个函数/类

## 全项目复杂度榜单（前15，跨文件跨语言排序）

  [F] src\json-schema.ts :: checkValue（第487行）复杂度=56
  [F] src\index.ts :: errorInfo（第642行）复杂度=51
  [F] src\py-types.ts :: result（第513行）复杂度=44
  [F] src\json-schema.ts :: checkSchemaNode（第227行）复杂度=41
  [E] src\schema.ts :: runSchemaCompiler（第275行）复杂度=37
  [E] src\index.ts :: (anonymous)（第1071行）复杂度=33
  [D] src\ts-types.ts :: docLines（第32行）复杂度=29
  [D] src\code-mode.ts :: driverRun（第398行）复杂度=22
  [D] src\code-mode.ts :: renderJsonValue（第187行）复杂度=21
  [C] src\index.ts :: register（第1037行）复杂度=14
  [C] tests\properties.spec.ts :: valueForProp（第73行）复杂度=14
  [C] src\invariant.ts :: (anonymous)（第84行）复杂度=13
  [B] src\code-mode.ts :: commit（第558行）复杂度=10
  [B] src\invariant.ts :: validateDispatch（第37行）复杂度=10
  [B] src\json-schema.ts :: checkObjectSchemaTail（第203行）复杂度=10

## 行为描述明细（B级以上，共29个）

### [D] src\code-mode.ts :: driverRun（第398行，复杂度22）

【driverRun 契约】

**输入**：无显式参数。它是 `drive()` 内部创建的异步 IIFE 的 Promise，`drive()` 无参数，`driverRun` 只是该 Promise 的引用。

**输出**：`Promise<void>`。当且仅当 `pendingQueue`、`commitQueue`、`inFlight` 三者同时为空时 resolve（第 421 行 `if (pendingQueue.length === 0 && commitQueue.length === 0 && inFlight.size === 0) return`）。

**副作用（外部状态变更）**：
1. 修改闭包内 `driving` 标志：进入时置 `true`（第 386 行），`finally` 中置回 `false`（第 431 行 `driving = false`）。
2. 修改 `wake` 闭包变量：每次循环创建新的 wakeup promise 时覆盖 `wake`（第 393 行 `wake = resolve`），`finally` 中置 `undefined`（第 432 行）。
3. 修改 `commitQueue`：shift 掉已 settled 的队首（第 396 行 `commitQueue.shift()`）。
4. 修改 `pendingQueue`：shift 掉已启动/已放弃的队首（第 405、413 行）。
5. 修改 `inFlight`：`inFlight.add(flight)`（第 418 行），flight 的 finally 中 `inFlight.delete(flight)`（第 416 行）。
6. 修改 `exclusiveActive`：exclusive 启动时置 `true`（第 411 行），其 commit 完成后置 `false`（第 400 行）。
7. 调用 `head.abandon()`（第 406 行）、`head.start()`（第 414 行）、`head.commit()`（第 397 行）——这些会触发 dispatch 的 reject/append/append 等副作用。

**前置条件**：
- 调用方（`binding` 内）必须先 `pendingQueue.push(...)` 再 `wakeup()` 再 `void drive()`（第 566-568 行），否则 driver 可能因队列为空直接返回。
- `driving` 为 false 时才能启动新 run；若已 driving，`drive()` 直接返回现有 `driverRun`（第 385 行 `if (driving) return driverRun`）。
- 依赖 `runController.signal` 的 abort 状态（第 404 行检查）。

**调用后保证**：
- 返回的 Promise 在队列和 inFlight 全空时 resolve，即所有 dispatch 已 settle 且已 commit。
- `finally` 保证 `driving` 复位为 false、`wake` 清空，即使异常也如此。
- 若 abort 已触发，driver 会放弃所有未启动的 pending 条目（`head.abandon()`），但已启动的 flight 会继续等待其 settle。

【调用方须知】`drive()` 是幂等入口：若 `driving` 已为 true，再次调用 `drive()` 不会启动新 run，而是直接返回同一个 `driverRun` Promise——因此 `binding` 里每次 push 后都调 `void drive()` 是安全的（不会重复启动），但如果你在 `driving` 为 true 时依赖 `drive()` 返回的 Promise 来等待“本次 push 的条目被处理”，它不会等待新条目，只会等待当前 run 结束。真正要等待所有条目处理完，必须等 `driverRun` 本身 resolve（即队列全空），而不是等某次 `drive()` 调用。

*✓ 核实通过——候选答案对driverRun的输入、输出、副作用、前置条件和调用后保证的描述均与代码原文逐条吻合，且【调用方须知】中关于drive()幂等性和返回Promise语义的警示准确反映了代码行为。*

### [D] src\code-mode.ts :: renderJsonValue（第187行，复杂度21）

函数 `renderJsonValue`（src/code-mode.ts 第187行起）的契约如下：

**输入**：
- 参数 `value` 的类型是 `Exclude<JsonValue, string>`（第187行），即**非字符串**的 JSON 值：`null`、`boolean`、`number`、数组、对象。字符串被排除在外（由调用方 `renderValue` 单独处理，见第260行 `typeof value === 'string' ? value : renderJsonValue(value)`）。
- 前置条件：输入必须是**规范化的 JsonValue**——数组是稠密的（无空洞）、对象属性值不能是 `undefined`。代码在遇到 `item === undefined`（第211行）和 `key === undefined`（第225行）、`item === undefined`（第227行）时直接 `throw new Error`，注释明确写“canonical JsonValue arrays are dense”（第210行）、“canonical JsonValue records contain no undefined properties”（第226行）。

**输出**：
- 返回一个 `string`，是输入 JSON 的**两空格缩进**格式化文本（`JSON_INDENT = '  '`，第158行），且**不使用递归**（用显式任务栈 `tasks` 迭代遍历，第189-190行），因此不会因深层嵌套导致栈溢出。
- 缩进有上限：当 `(task.depth + 1) * JSON_INDENT.length > MAX_JSON_INDENT_CHARS`（`MAX_JSON_INDENT_CHARS = 10`，第166行）时，后续子树切换为 `compact` 模式（第199行），不再换行缩进，保证输出大小与规范 JSON 大小线性（第162-165行注释）。
- 字符串值用 `JSON.stringify` 转义（第197行），对象键也用 `JSON.stringify` 转义（第231、234行）。

**副作用**：
- **无副作用**。函数是纯函数：只向局部 `chunks` 数组和 `tasks` 栈写入，不修改任何外部状态、文件或全局数据。

**调用后保证**：
- 返回的字符串是输入值的合法 JSON 文本表示（两空格缩进，深层紧凑）。
- 对合法输入**不会抛异常**；只有违反前置条件（稀疏数组、undefined 属性）才抛 `Error`。

**调用方须知**：调用方最容易忽略的是——该函数**只接受非字符串的 JsonValue**，字符串输入会走 `renderValue` 的另一个分支（第260行直接原样返回，不做 JSON 转义）；如果直接对字符串调用 `renderJsonValue`，TypeScript 类型上就不允许（`Exclude<JsonValue, string>`），但若绕过类型检查传入字符串，函数会把它当作对象处理（`typeof current === 'string'` 分支在第196行存在，会返回 `JSON.stringify(current)`），行为与 `renderValue` 的“字符串原样返回”不一致——所以调用方必须通过 `renderValue` 入口，而不是直接调 `renderJsonValue`，否则字符串会被加上引号。

*✓ 核实通过——逐条对照代码原文核实了候选答案的每个具体断言（参数类型、缩进常量、非递归、稀疏数组/undefined 抛错、无副作用、字符串分支），全部与源码一致。*

### [B] src\code-mode.ts :: commit（第558行，复杂度10）

【commit 的契约】

**输入**：无参数（`async commit(): Promise<void>`，第558行）。它不接收任何输入，而是读取闭包状态 `parked`（第559行 `if (parked === undefined) return`）。

**前置条件**：
1. `parked` 必须已被赋值——即 `start()` 已执行完毕（第559行注释 `commit() runs only after `settled` flipped, which set parked`）。`parked` 在 `start()` 中被设置为 `{ kind, exec, result }`（第536-538行）。
2. 调用方（driver 循环）保证只在 `settled === true` 时才调用 commit（第403行 `if (commitHead !== undefined && commitHead.settled)`）。

**输出**：`Promise<void>`，不向调用方返回任何值。

**副作用**（按代码原文）：
1. **调用调度器终结**：`const result = parked.kind === 'post-result' ? await scheduler.finalize(parked.exec, parked.result) : scheduler.finish(parked.exec, parked.result)`（第560-561行）——对嵌套结果执行 finalize 或 finish。
2. **图片结果转为用户消息**：`if (!result.isError && result.content.some(block => block.type === 'image')) { exec.deferContext(createUserMessage({ content: result.content, source: { kind: 'plugin', plugin: 'tools-code-mode' } })) }`（第562-566行）——把图片内容作为用户消息推迟到上下文中。
3. **转发 additionalContexts**：`for (const context of result.additionalContexts ?? []) { exec.deferContext(context) }`（第567-569行）。
4. **终结回合**：`if (result.concludesTurn) exec.concludeTurn()`（第573行）。
5. **settle(result)**（第574行）——resolve 掉外层 Promise，把结果交给程序（`settle` 定义在第487-517行，resolve 后还追加日志事件）。
6. **背压等待**：`while (logWork.size > maxParallel) await Promise.race(logWork)`（第577-578行）——等待日志任务池降到上限以下。

**调用后保证**：
- 程序已拿到结果值（`settle` 里 resolve 了 `{ isError, value }`，第489-491行）。
- 所有日志事件（`tool/code-dispatch`）已追加到 session（`settle` 内部，第497-515行）。
- 若结果含图片，图片已作为用户消息进入上下文；若 `concludesTurn`，回合已终结。

【调用方须知】commit 会**同步阻塞等待日志任务池收缩**（`while (logWork.size > maxParallel) await Promise.race(logWork)`，第577-578行），且它内部会调用 `settle(result)` 去 resolve 外层 Promise 并追加日志——这意味着 commit 不是纯终结动作，它可能因慢速日志后端而长时间挂起，调用方（driver）在 commit 期间不能推进后续条目，必须意识到这个背压等待可能拖慢整个有序提交队列。

*✓ 核实通过——我逐行核对了 src/code-mode.ts 中 commit 的实现，候选答案引用的每一处代码原文（行号、函数调用、条件判断）都与实际代码完全匹配，没有发现任何虚构或错误描述。*

### [F] src\index.ts :: errorInfo（第642行，复杂度51）

函数 `errorInfo`（src/index.ts 第642-648行）的契约如下：

**输入**：一个 `unknown` 类型的值 `error`（任意被抛出的值）。

**输出**：
- 若 `error` 是 `HarnessError` 的实例（`error instanceof HarnessError` 为真），返回 `{ name: error.name, code: error.code }`，即一个 `ToolErrorInfo` 对象（`ToolErrorInfo` 接口定义在第475-478行：`{ name: string; code: string }`）。
- 否则返回 `undefined`（第644行 `: undefined`）。
- 若 `instanceof` 检查本身抛异常（例如敌意的 `Symbol.hasInstance` 陷阱），catch 块捕获后返回 `undefined`（第646-647行）。

**副作用**：无。函数体只做类型检查和属性读取，不修改任何外部状态、文件或全局数据。

**前置条件**：无。函数对任意输入都是全函数（total），即使 `error` 是 `null`、`undefined`、原始值或带陷阱的对象，也只会返回 `undefined` 或捕获异常后返回 `undefined`，不会抛出。

**后置保证**：
- 返回值要么是 `undefined`，要么是一个 `{ name, code }` 对象，其中 `name` 和 `code` 直接取自 `HarnessError` 实例的对应属性（第644行）。
- 该函数绝不抛出异常（try/catch 保证）。

**调用方须知**：这个函数只识别 `HarnessError` 实例——如果调用方传入的是 `ToolNotFoundError`（它继承自 `HarnessError`，见第490-492行），会正常返回 `{ name, code }`；但任何其他错误类型（包括普通 `Error`、`ToolNotFoundError` 之外的错误）都会返回 `undefined`，所以调用方不能依赖它来区分所有错误，只能用它判断“是否是一个 HarnessError 及其 name/code”。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和后置保证的描述与代码原文完全一致，且引用的行号和接口定义准确无误。*

### [E] src\index.ts :: (anonymous)（第1071行，复杂度33）

（超过最大步数，未能得出答案）

*✗ 核实不通过——The candidate answer explicitly says it failed to produce an answer, so it cannot be considered accurate or verified.*

### [C] src\index.ts :: register（第1037行，复杂度14）

【register 契约】

**输入**：一个 `ToolDefinition` 对象（`definition`），其中必须包含：
- `name`（字符串，`const name = definition.name`）
- `output`：必须是对象，且 `output.render` 必须是函数；若 `output.presentationMeta` 存在则也必须是函数（否则抛 `TypeError`）
- `output.schema`：必须通过 `assertSupportedJsonSchema(output.schema)` 校验
- `timeoutMs`（可选）：若提供，必须是正有限数（`Number.isFinite(timeoutMs) && timeoutMs > 0`），否则抛 `TypeError`

**输出**：返回一个函数 `() => void`，即“精确的注销器”（disposer），调用它可注销该工具。

**副作用**：调用 `this.layers.effect(this.ctx, layer => layer.tools.insert(name, definition), { label: 'tools.register()' })`——即把工具插入到当前上下文的工具层（`layer.tools`），修改了 `this.ctx` 所代表的工具注册表状态（全局或调用方 agent 作用域）。

**前置条件**：
- `definition.name` 不能等于保留名 `RUN_CODE_NAME`（否则抛 `Error`，注释说明该名被 Code Mode 传输保留，不可注册或遮蔽）
- `output` 结构必须合法（见上）
- `output.schema` 必须通过 `assertSupportedJsonSchema`
- `timeoutMs` 若提供必须为正有限数

**调用后保证**：
- 工具已注册到当前作用域（`layer.tools.insert`），可被后续使用
- 返回的 disposer 可精确撤销本次注册（docstring：`returns the exact disposer that unregisters the tool`）

【调用方须知】最容易被忽略的是：`register` 的副作用是**修改了 `this.ctx` 对应的工具层状态**（`layer.tools.insert`），且**返回的 disposer 必须被保存并在需要时调用**——如果调用方丢弃返回值，工具将永久留在注册表中，无法撤销；同时 `name` 为 `RUN_CODE_NAME` 时会在注册前直接抛错，调用方若想注册名为 `run_code` 的工具会失败，这是函数名/文档看不出、但代码明确强制保留的边界。

*✓ 核实通过——候选答案对 register 的输入校验、输出、副作用、前置条件和返回 disposer 的描述均与代码原文逐条吻合，包括对 RUN_CODE_NAME 的保留检查和 timeoutMs 的正有限数校验，因此判定为真实准确。*

### [B] src\index.ts :: errorMessage（第608行，复杂度7）

函数 `errorMessage`（src/index.ts 第608行）的契约如下：

**输入**：一个 `unknown` 类型的值 `error`，即任意可能被抛出的值（包括 `Error` 实例、普通对象、原始值、甚至可能抛出异常的值）。

**输出**：一个 `string`，即人类可读的错误消息。

**行为/副作用**：无副作用。函数不修改任何外部状态、文件或全局数据，只读取传入值并返回字符串。

**前置条件**：无。函数对任意输入都保证返回字符串，不会抛出异常（内部有 try/catch 兜底）。

**后置保证**：
- 若 `error instanceof Error`，返回 `error.message`（第610行）。
- 若 `error` 是对象且非 null、有字符串类型的 `message` 属性（如 `throw { message: 'denied' }`），返回该 `message`（第611-613行）。
- 否则返回 `String(error)`（第614行）。
- 若上述任何操作（`instanceof`、属性访问、字符串转换）抛出异常（例如恶意抛出的值），返回固定字符串 `'<unprintable thrown value>'`（第618-620行）。

**【调用方须知】**：该函数是“错误规范化”的最外层安全边界，它保证**绝不抛出异常**——即使传入一个会令 `instanceof`、属性访问或 `String()` 抛错的值（如 `Symbol`、带 getter 的对象），它也会返回 `'<unprintable thrown value>'` 而不是把异常传播给调用方。因此调用方可以放心用它处理任何未知的 thrown 值，无需再包 try/catch。

*✓ 核实通过——逐行核对代码后，候选答案的每一条契约描述（包括catch兜底和'<unprintable thrown value>'）都与实际实现吻合，且调用方须知准确指出了该函数绝不抛异常的安全边界。*

### [B] src\index.ts :: admits（第738行，复杂度6）

函数 `admits(name: string): boolean`（src/index.ts 第738行）是 `ToolLayer` 类的一个方法，其契约如下：

**输入**：一个字符串 `name`，代表一个全局工具名（如 `run_code`）。

**输出**：布尔值。返回 `true` 表示该层所有已编译的 restriction 都允许这个工具名；返回 `false` 表示至少有一个 restriction 拒绝它。

**副作用**：无。它只读取 `this.restrictions`（一个 `AnonymousEntries<CompiledToolRestriction>`），不修改任何状态、不写文件、不触发外部调用。

**前置条件**：`this.restrictions` 已初始化（构造时默认创建）。`name` 应为非空字符串，但函数本身不校验，空字符串也会正常参与判断。

**调用后保证**：
- 返回 `false` 当且仅当存在某个 restriction `filter` 满足：`filter.allow !== undefined && !filter.allow.has(name)`（即 allow 列表存在且不含该名字）**或** `filter.deny !== undefined && filter.deny.has(name)`（即 deny 列表存在且包含该名字）。
- 返回 `true` 当且仅当所有 restriction 都不满足上述条件（即所有 allow 列表都含该名字或未定义，且所有 deny 列表都不含该名字或未定义）。
- 该判断是纯函数式的，不依赖调用顺序，多次调用结果一致。

**调用方上下文**：在 `view()` 方法（第1174行）中，`layers.every(layer => layer.admits(name))` 用于判断一个继承的工具名是否在整条作用域链上可见——只有当链上每一层都 `admits` 该名字时，该工具才会被放入 `visible` 集合。

【调用方须知】最容易忽略的是：`admits` 只检查 `restrictions`（allow/deny 过滤），**完全不检查 `guards`（ToolGuard 守卫）**。一个工具名即使 `admits` 返回 `true`（即通过所有 restriction），仍可能在执行时被某个 guard 拒绝（`guardReason` 返回非 undefined）。因此 `admits` 的 `true` 只代表“静态可见性”，不代表“运行时一定可调用”——调用方若用 `admits` 判断工具是否可用，必须另行检查 guard 逻辑，否则会误判工具实际可执行性。

*✓ 核实通过——I read the actual source code and confirmed the exact implementation, behavior, and usage of `admits` as described in the candidate answer, including the lack of guard checks.*

### [C] src\invariant.ts :: (anonymous)（第84行，复杂度13）

第84行的「(anonymous)」是 `ctx.on('internal/dispatch', ...)` 注册的全局事件监听回调（第84-127行）。其契约如下：

**输入**：三个参数——`_mode`（忽略）、`eventName`（字符串，如 `'session/event'`、`'tools/pre-execute'`、`'tools/execute'`、`'tools/post-execute'`、`'tools/result'`）、`args`（事件参数数组，按事件类型解构为 `[Session, SessionEvent]` 或 `[ToolExecution]` 或 `[ToolExecution, ToolExecutionResult]`）。

**输出**：无返回值（`void`）。

**副作用**（修改外部状态）：
1. 修改模块级 `WeakMap`：`stages`（第88、91、94、97、101行 `stages.set(exec, ...)` / `stages.delete(exec)`）、`openTurns`（第110、112行 `openTurns.set(session, ...)`）。
2. 调用 `fail(...)` 触发不变量失败（第87、90、93、96、100、105、108行），这是对外部 invariant 服务的副作用。
3. 调用 `validateDispatch` / `commitDispatch`（第85、86行），后者修改 `dispatchRoots` WeakMap（第53行 `roots.set(...)`）。

**前置条件**：
- 事件 `'tools/pre-execute'`、`'tools/execute'`、`'tools/post-execute'`、`'tools/result'` 必须按顺序到达（第88-101行检查 `stages` 状态机）。
- `'tools/result'` 的 `exec` 和 `result` 必须已冻结（`Object.isFrozen`，第22-24行 `validateResult`）。
- `'session/event'` 事件中若为 `tool/code-dispatch-start` 或 `tool/code-dispatch`，要求 `rootCallId`、`parentCallId`、`subCallId` 非空（第37-40行），且 `parentCallId` 必须属于 `rootCallId`（第44-46行），且必须处于打开的 turn 中（第105-108行）。

**调用后保证**：
- 若违反上述不变量，会调用 `fail` 抛出失败；否则事件被正常处理，`stages` 状态机推进，`dispatchRoots` 记录子调用到根调用的映射。

【调用方须知】该回调会**修改模块级 `WeakMap`（`stages`、`openTurns`、`dispatchRoots`）并调用 `fail` 触发不变量失败**，这些副作用在函数名 `(anonymous)` 中完全看不出来；尤其注意 `'tools/result'` 事件会**删除 `stages` 中的记录**（第101行 `stages.delete(exec)`），如果调用方在 `'tools/result'` 之后再次对同一 `exec` 触发 `'tools/pre-execute'`，会因 `stages.has(exec)` 为 false 而通过检查，但状态机已被重置——这是最容易忽略的边界情况。

*✓ 核实通过——逐条对照代码原文，候选答案对回调的输入、输出、副作用、前置条件和边界情况的描述均与源码一致，无虚构或夸大。*

### [B] src\invariant.ts :: validateDispatch（第37行，复杂度10）

「validateDispatch」是 src/invariant.ts 中 install 闭包内定义的一个局部函数（第 37 行起），不是导出成员。它的契约如下：

**输入**：两个参数 `session: Session` 和 `event: SessionEvent`（第 37 行 `const validateDispatch = (session: Session, event: SessionEvent): void => {`）。

**输出**：无返回值（`void`）。

**副作用**：不直接修改任何外部状态，但会调用闭包捕获的 `fail: InvariantFailure` 回调（第 43、47、49 行 `fail(...)`），即当校验失败时触发不变量失败上报。它本身不写 `dispatchRoots` 等 WeakMap——写入由 `commitDispatch` 负责（第 52-57 行），`validateDispatch` 只读 `dispatchRoots`（第 45 行 `const roots = dispatchRoots.get(session)`）。

**前置条件**：
1. `event` 必须是 `SessionEvent` 类型，且其 `data` 上存在 `rootCallId`、`parentCallId`、`subCallId` 字段（第 39-41 行读取这些字段）。
2. 若 `event.type` 不是 `'tool/code-dispatch-start'` 或 `'tool/code-dispatch'`，函数直接返回、不做任何校验（第 38 行 `if (event.type !== 'tool/code-dispatch-start' && event.type !== 'tool/code-dispatch') return`）。
3. 调用前 `dispatchRoots` 中应已为 `session` 建立映射（由 `seed` 第 62 行 `dispatchRoots.set(session, new Map())` 保证），否则 `roots` 为 `undefined`，此时只校验非空和 parent 归属（第 45-49 行对 `undefined` 做了安全处理）。

**调用后保证**：
1. 若三个 id 任一为空字符串，调用 `fail` 并返回（第 42-44 行）。
2. 若 `subCallId` 已记录过且其 root 与本次不同，调用 `fail`（第 46 行 `if (known !== undefined && known !== root) fail(...)`）。
3. 若 `parentCallId` 不等于 `rootCallId` 且 `parentCallId` 未记录为属于该 root，调用 `fail`（第 48-50 行）。
4. 校验通过时不调用 `fail`，函数正常返回，不改变任何状态。

【调用方须知】这个函数的名字叫 validateDispatch，但它只对 `tool/code-dispatch-start` 和 `tool/code-dispatch` 两类事件做校验，对其他任何事件类型（包括 `tool/code-dispatch-end` 等）都会直接静默返回、不做任何检查——所以不要以为它对所有 dispatch 事件都校验；而且它只读不写，真正的状态登记（把 subCallId→rootCallId 写入 `dispatchRoots`）是在 `commitDispatch` 里做的，调用方若只调用 validateDispatch 而不调用 commitDispatch，后续对同一 subCallId 的重复校验会因 `known === undefined` 而漏掉 root 变更检测。

*✓ 核实通过——候选答案对函数签名、行为、副作用、前置条件和调用后保证的描述均与代码原文一致，且调用方须知准确指出了只校验两类事件和只读不写的特性。*

### [B] src\invariant.ts :: seed（第58行，复杂度7）

seed 是 src/invariant.ts 第58行定义的一个内部函数（非导出），签名 `const seed = (session: Session): number | null`。

【输入】一个 Session 对象（`session: Session`）。
【输出】`number | null`——返回该 session 当前“打开的 turn 编号”（`openTurn`），若没有打开的 turn 则返回 `null`。

【副作用】
1. 修改外部状态：`dispatchRoots.set(session, new Map())`——为这个 session 重置/初始化一个空的 dispatch 根映射（WeakMap<Session, Map<string,string>>）。
2. 修改外部状态：`openTurns.set(session, openTurn)`——把计算出的 openTurn 写入 `openTurns`（WeakMap<Session, number|null>）。
3. 调用 `fail(...)` 触发不变量失败回调（副作用是可能中断/报告错误）。

【前置条件】
- `session.events` 必须可迭代（`for (const event of session.events)`）。
- 对每个 event，`event.type`、`event.data` 需可访问；对 `tool/code-dispatch-start` 和 `tool/code-dispatch` 事件，`event.data.rootCallId`、`parentCallId`、`subCallId` 必须存在（否则 `String(undefined)` 得到空串，会触发 fail）。
- 对 `turn/start` 事件，`event.data.turn` 必须存在。

【调用后保证】
- 该 session 的 dispatch 根映射被重置为空 Map，且所有历史事件被重新校验（validateDispatch）并提交（commitDispatch）。
- `openTurns` 中该 session 的值被更新为“最后一个 turn/start 之后、turn/end 之前”的 turn 编号；若事件流以 turn/end 结尾或没有 turn/start，则为 null。
- 返回值等于刚写入 `openTurns` 的值。

【调用方须知】seed 会**重置**该 session 的 `dispatchRoots` 映射（`dispatchRoots.set(session, new Map())`），并**重新遍历全部历史事件**重新校验和提交——如果调用方在 session 已有事件之后再次调用 seed，会清空之前积累的 dispatch 根记录并重新建立，可能改变后续 `validateDispatch` 对 rootCallId 归属的判断；同时它把 openTurn 状态写入 `openTurns`，若调用方在事件流中途调用 seed，会把 openTurn 重置为当前事件流末尾的状态，可能覆盖掉调用方已维护的 turn 状态。

*✓ 核实通过——逐行核对代码，候选答案对 seed 的输入输出、副作用、前置条件和保证的描述均准确，且调用方须知指出的重置 dispatchRoots 和重新遍历事件的行为在代码中有明确依据。*

### [F] src\json-schema.ts :: checkValue（第487行，复杂度56）

checkValue 是内部函数（非导出），由导出函数 validateJsonSchemaValue 在 src/json-schema.ts 第656行调用（`return checkValue(schema, value, path)`）。

**输入**：
- `schema: JsonSchemaNode` —— 一个已通过 `assertSupportedJsonSchema` 校验的 schema（见第650行 docstring `a schema accepted by assertSupportedJsonSchema`）。
- `value: unknown` —— 任意候选 JSON 值（docstring 第650行 `total for arbitrary values`）。
- `path: string` —— 用于诊断信息的根标签（docstring 第652行 `root label used in diagnostics`）。

**输出**：
- `string[]` —— 所有违规信息，按遍历顺序排列；空数组表示有效（docstring 第653行 `All violations in walk order; empty means valid`）。

**副作用**：
- 无外部副作用。函数是纯函数：不修改传入的 schema 或 value（只读访问，如 `Object.hasOwn(frame.node, ...)`、`frame.value[key]`），不写文件、不碰全局状态。所有状态都在局部 `frames` 栈和 `rootResult` 中。

**前置条件**：
- `schema` 必须是 `assertSupportedJsonSchema` 接受的 schema（docstring 第650行）。
- 无其他前置条件；对任意 `value` 都是全函数（docstring 第650行 `total for arbitrary values`）。

**调用后保证**：
- 返回的数组要么为空（值有效），要么包含至少一条违规消息，每条消息都带路径前缀（如 `"${diagnosticPath(frame.path)}" must be an object`，第535行）。
- 对 `oneOf` 分支，保证恰好匹配一个分支才通过（第512行 `frame.matches === 1 ? [] : ...`）。
- 对 `object` 类型，保证检查 required 属性（第541-544行）、additionalProperties:false（第551-555行）。
- 对 `number`/`integer`，保证是有限 JSON 数字（第574-580行 `isJsonNumber`）。
- 对未知 `type` 值，`frame.catches` 设为 false（第526行），异常会向上抛出（第599-601行），最终返回 `losslessValueViolation(path)`（第606行）。

**【调用方须知】**：最容易被忽略的是：`checkValue` 对 `oneOf` 的处理是“恰好匹配一个分支”，但 `receive` 只在子结果为空（`result.length === 0`）时才递增 `matches`（第499行 `if (result.length === 0) parent.matches++`），这意味着如果某个分支匹配但产生了非空违规（比如类型对但标量约束失败），该分支不会被计入匹配数——因此一个值可能因为“匹配了0个分支”或“匹配了2个分支”都报错，但“匹配了1个分支且该分支有违规”也会报错（因为 matches 仍为0），调用方不要以为“恰好匹配一个分支”就代表值有效，必须同时检查返回数组是否为空。

*✓ 核实通过——我逐条核对了候选答案中引用的代码行号和具体行为，所有描述均与源码相符，包括 oneOf 匹配计数的细节，因此结论为真实准确。*

### [F] src\json-schema.ts :: checkSchemaNode（第227行，复杂度41）

【checkSchemaNode 契约】

**输入**（第227行签名）：`checkSchemaNode(root: unknown, rootPath: string, violations: string[], seen: Set<object>): void`
- `root`：待校验的原始 schema 节点（任意值，不要求是对象）。
- `rootPath`：诊断路径前缀，用于生成违规消息（如 `'schema'`）。
- `violations`：调用方提供的字符串数组，函数把发现的违规消息 push 进去（副作用载体）。
- `seen`：调用方提供的 `Set<object>`，用于检测循环引用（副作用载体）。

**输出**：无返回值（`void`）。所有结果通过 `violations` 数组传出。

**副作用**：
1. 修改 `violations` 数组——push 违规消息（第231、236、239、243、247、253、257、262、266、270、274、278、282、286、290、294、298、302、306、310、314、318、322、326、330、334、338、342、346、350、354、358、362、366、370、374、378、382、386、390、394 行等多处）。
2. 修改 `seen` 集合——进入节点时 `seen.add(node)`（第249行），离开时 `seen.delete(node)`（第232行）。
3. 不修改任何文件、全局数据或外部状态；不抛出异常（所有错误都转为 violations 条目）。

**前置条件**：
- `violations` 必须是非空数组（函数直接 push，若为 null/undefined 会抛 TypeError）。
- `seen` 必须是 `Set<object>`（函数调用 `seen.has`/`add`/`delete`）。
- `rootPath` 应为字符串（用于拼接消息）。
- 无其他前置条件；`root` 可以是任意值（函数内部用 `isJsonSchemaRecord` 等守卫）。

**调用后保证**：
- 若 schema 合法，`violations` 长度不变；若非法，`violations` 会追加所有违规路径（不提前停止，遍历完整棵树）。
- `seen` 在函数返回时恢复为空（每个 `add` 都有对应的 `delete`，见第249行 add 与第232行 delete 配对）。
- 不抛出异常（除非前置条件被破坏）。

**行为细节（依据代码）**：
- 使用显式任务栈（`tasks`）而非递归，避免 JS 调用栈溢出（第228-229行）。
- 对非 schema 对象：`violations.push(`${path} must be a schema object`)`（第243行）。
- 循环引用：`seen.has(node)` 时 push `${path} is circular`（第247行）。
- 未知关键字：push `${path}.${key} is not a supported keyword...`（第257行）。
- 注解关键字（description/title/default/examples）必须是无损 JSON 数据（第253-255行）。
- `type` 与 `oneOf` 互斥（第266行）；两者都缺时，`oneOf` 兄弟关键字（properties/required/additionalProperties/items/enum/const）报错（第270-274行）。
- `oneOf` 必须是至少两个 schema 的数组（第278行）。
- `type` 必须是单一字符串且属于 `SCHEMA_TYPES`（第286-290行）。
- 按类型校验：object 的 properties/required/additionalProperties（第320-338行）、array 的 items（第340-342行）、标量类型的 enum/const（第344-366行）。

【调用方须知】`checkSchemaNode` 本身不抛异常、不返回结果，所有违规都 push 进你传入的 `violations` 数组——调用方必须在调用后检查 `violations.length` 并自行决定是否抛错（如 `assertSupportedJsonSchema` 第397-399行所做）；同时它会在 `seen` 集合中临时记录节点，返回时清空，因此调用方不能复用同一个 `seen` 集合去并发/嵌套调用本函数，否则循环检测会误报。

*✓ 核实通过——逐条核对了候选答案中的行号和代码行为，与源码完全一致，包括副作用、前置条件、行为细节和调用方须知。所有引用均准确无误。*

### [B] src\json-schema.ts :: checkObjectSchemaTail（第203行，复杂度10）

函数 `checkObjectSchemaTail` 的契约如下（依据 src/json-schema.ts 第203-226行）：

**输入**：
- `node: Record<string, unknown>`：一个待校验的 schema 对象（必须是普通 JSON 记录，由调用方保证）。
- `path: string`：该节点在 schema 树中的路径（用于错误消息前缀）。
- `properties: unknown`：该节点的 `properties` 字段值（可能不是对象）。
- `violations: string[]`：一个数组，用于收集错误消息。

**输出**：无返回值（`void`）。所有校验结果通过向 `violations` 数组 push 错误字符串来报告。

**副作用**：
- 唯一的外部状态修改是向传入的 `violations` 数组追加字符串（第211、214、217、222行）。不修改 `node`、`properties` 或任何全局/文件状态。

**前置条件**：
- `node` 必须是普通 JSON 记录（调用方 `checkSchemaNode` 在调用前已通过 `isJsonSchemaRecord` 检查，见第244行）。
- `violations` 必须是一个可变的数组（调用方传入）。
- `properties` 可以是任意值（函数内部用 `isJsonSchemaRecord` 判断是否可用）。

**调用后保证**：
- 如果 `node.required` 存在且不是普通 JSON 数组或包含非字符串元素，则 push `"${path}.required must be an array of strings"`（第211行）。
- 如果 `required` 是字符串数组，则检查其中每个键是否在 `properties` 中（若 `properties` 是普通 JSON 记录则用其键，否则视为空对象）；缺失的键 push `"${path}.required names \"${key}\" which is not in properties"`（第214-217行）。
- 如果 `node.additionalProperties` 存在且不是布尔值，则 push `"${path}.additionalProperties must be a boolean"`（第222行）。
- 函数不会抛出异常，不会修改 `node` 或 `properties`。

【调用方须知】该函数只校验 `required` 和 `additionalProperties` 两个字段，但**不会校验 `properties` 本身是否为合法 schema 对象**——它只是把 `properties` 当作键集合来检查 `required` 引用，如果 `properties` 不是普通 JSON 记录（例如是数组或字符串），函数会静默地将其视为空对象（第213行 `isJsonSchemaRecord(properties) ? properties : {}`），导致 `required` 中所有键都被报告为“不在 properties 中”，即使这些键实际上存在于一个非普通记录里。调用方若传入非普通记录的 `properties`，会得到误导性的错误消息，需自行确保 `properties` 是普通 JSON 记录。

*✓ 核实通过——我逐行阅读了 src/json-schema.ts 中 checkObjectSchemaTail 的完整实现（第203-226行），并核对了调用方 checkSchemaNode 中传入 properties 的方式（第244行附近），确认候选答案对输入、输出、副作用、前置条件、调用后保证以及【调用方须知】的描述均与代码原文一致。*

### [B] src\json-schema.ts :: isPlainJsonRecord（第115行，复杂度7）

函数 `isPlainJsonRecord`（src/json-schema.ts 第115-124行）的契约如下：

**输入**：一个 `unknown` 类型的值 `value`（第116行 `export function isPlainJsonRecord(value: unknown)`）。

**输出**：一个类型谓词 `value is Record<string, unknown>`（第116行），即返回 `true` 时 TypeScript 将 `value` 收窄为 `Record<string, unknown>`；返回 `false` 时不做收窄。

**行为/判定逻辑**（第117-123行）：
- 第117行：若 `typeof value !== 'object'`（非对象）、`value === null`（null）、或 `Array.isArray(value)`（数组），直接返回 `false`。
- 第118-122行：在 `try` 块内取 `Object.getPrototypeOf(value)` 得到原型，返回 `true` 当且仅当：原型为 `null`（第120行），或原型是对象且 `isIntrinsicObjectPrototype(prototype)` 为真（第121行）。`isIntrinsicObjectPrototype`（第104-107行）要求原型自身原型为 `null` 且 `hasIntrinsicConstructor(prototype, 'Object')` 为真，即原型是某个 realm 的原生 `Object.prototype`。
- 第123行：`catch` 块捕获任何异常（如 `Object.getPrototypeOf` 对某些 exotic 对象抛错）并返回 `false`。

**副作用**：无。函数是纯函数，不修改任何外部状态、文件或全局数据；只读取 `value` 的原型链和构造器描述符（`hasIntrinsicConstructor` 内部调用 `Object.getOwnPropertyDescriptor` 和 `Function.prototype.toString`，均为只读操作）。

**前置条件**：无。函数接受任意 `unknown` 值，包括跨 realm 的对象、代理、冻结对象等，均不会抛出异常（异常被 `catch` 吞掉返回 `false`）。

**调用后保证**：
- 返回 `true` 时，`value` 是普通对象（原型为 `null` 或原生 `Object.prototype`），且不是数组、不是 null、不是原始值。
- 返回 `false` 时，`value` 可能是数组、null、原始值、或原型链非普通（如类实例、`Object.create({})` 创建的对象、代理等）。
- 注意：该函数**不检查**键的可枚举性、键是否为字符串、或键是否可 JSON 序列化——这些由 `isJsonSchemaRecord`（第148-151行）额外通过 `hasOnlyEnumerableStringKeys` 补充。

【调用方须知】该函数返回 `true` 只保证原型链是普通对象，**不保证**对象的键都是字符串或可枚举——例如 `Object.create(null)` 且带 Symbol 键或不可枚举键的对象也会返回 `true`，若你需要“键能无损 JSON 投影”的普通记录，必须改用 `isJsonSchemaRecord`（它额外调用 `hasOnlyEnumerableStringKeys`），不要仅凭 `isPlainJsonRecord` 的 `true` 就当作可 JSON 序列化的普通记录使用。

*✓ 核实通过——候选答案对函数行为、副作用、前置条件的描述与代码逐条吻合，且正确指出该函数不检查键的可枚举性或字符串性，与`isJsonSchemaRecord`的差异也准确。*

### [B] src\json-schema.ts :: isPlainJsonArray（第161行，复杂度7）

函数 `isPlainJsonArray`（src/json-schema.ts 第161-172行）的契约如下：

**输入**：一个任意 JavaScript 值 `value: unknown`，可来自任何 realm（跨 realm 候选数组）。

**输出**：一个类型谓词 `value is unknown[]`——若返回 `true`，则 TypeScript 将 `value` 收窄为 `unknown[]`；返回 `false` 则不是。

**判定逻辑（依据代码原文）**：
1. `if (!Array.isArray(value)) return false` —— 非数组直接返回 `false`。
2. `if (!hasPlainArrayPrototype(value) || Reflect.ownKeys(value).length !== value.length + 1) return false` —— 要求数组的原型链是某个 realm 的固有 `Array.prototype`（`hasPlainArrayPrototype` 检查 `Object.getPrototypeOf(value)` 是数组、其 `constructor` 是原生 `Array` 且 `Function.prototype.toString` 为 `function Array() { [native code] }`），且 `Reflect.ownKeys` 的键数量恰好等于 `length + 1`（即只有 `length` 和所有索引键，没有额外装饰键）。
3. `for (let index = 0; index < value.length; index++) { if (!Object.hasOwn(value, index)) return false }` —— 要求每个索引 `0..length-1` 都是自有属性（稠密数组，无空洞）。
4. 整个逻辑包在 `try { ... } catch { return false }` 中——任何异常（如代理抛错）都返回 `false`。

**副作用**：无。函数是纯函数，不修改任何外部状态、文件或全局数据；只读取 `value` 的原型、自有键和索引属性。

**前置条件**：无。可对任意值调用，包括 `null`、`undefined`、原始值、代理对象等；异常路径已被 `catch` 兜底。

**调用后保证**：若返回 `true`，保证 `value` 是一个稠密（无空洞）、无额外自有装饰键（除 `length` 和索引外）、原型为固有 `Array.prototype` 的数组；若返回 `false`，则 `value` 不满足上述任一条件（或抛异常）。

【调用方须知】该函数会拒绝任何带有额外自有属性（如 `value.foo = 1`）或稀疏（有空洞）的数组——即使这些数组在 JSON.stringify 下看起来正常，也会返回 `false`；调用方若期望接受“可 JSON 序列化”的数组，需注意此函数比 JSON 序列化更严格，它要求数组在结构上完全“纯净”。

*✓ 核实通过——逐条核对了候选答案引用的代码逻辑，包括`Array.isArray`、`hasPlainArrayPrototype`、`Reflect.ownKeys`长度检查、`Object.hasOwn`循环和`try/catch`，所有描述均准确无误。*

### [B] src\json-schema.ts :: scalarMatches（第180行，复杂度7）

函数 `scalarMatches` 定义在 src/json-schema.ts 第180-187行，是一个模块私有（未导出）的类型守卫函数。

**契约描述（依据代码原文）：**

1. **输入**：两个参数——`type: JsonSchemaScalarType`（即 `'string' | 'number' | 'integer' | 'boolean' | 'null'`，见第27行 `type JsonSchemaScalarType = Exclude<JsonSchemaType, 'object' | 'array'>`）和 `value: unknown`。

2. **输出**：返回一个布尔值，且该函数是类型守卫（`value is JsonSchemaScalar`，其中 `JsonSchemaScalar = string | number | boolean | null`，见第20行）。当返回 `true` 时，TypeScript 会把 `value` 收窄为 `JsonSchemaScalar` 类型。

3. **行为逻辑**（第181-186行 switch 语句）：
   - `case 'string': return typeof value === 'string'`
   - `case 'number': return isJsonNumber(value)`——注意这里不是简单的 `typeof value === 'number'`，而是调用 `isJsonNumber`（第172-174行）：要求 `typeof value === 'number' && Number.isFinite(value) && !Object.is(value, -0)`。即：必须是有限数，且**排除负零（-0）**。
   - `case 'integer': return isJsonNumber(value) && Number.isInteger(value)`——在 `isJsonNumber` 基础上再要求是整数。
   - `case 'boolean': return typeof value === 'boolean'`
   - `case 'null': return value === null`
   - `default: return assertNever(type, 'JsonSchemaType')`——对不可能到达的 `type` 调用 `assertNever`（来自 `@deepseek-ai/dsh-llm`），用于编译期穷尽性检查；注释 `/* v8 ignore next -- JsonSchemaScalarType is closed; this retains compile-time exhaustiveness. */` 说明这是为保持编译期穷尽性而设，运行时不会走到。

4. **副作用**：无。函数体只做纯类型判断和返回值，不修改任何外部状态、不读写文件、不改变全局数据、不抛出异常（`assertNever` 分支在正常调用下不可达）。

5. **前置条件**：
   - `type` 必须是 `JsonSchemaScalarType` 的合法值（'string'/'number'/'integer'/'boolean'/'null'）。若传入 'object' 或 'array'，TypeScript 编译期会报错（类型不匹配），运行时若强行传入则会落入 `default` 分支调用 `assertNever`。
   - 无其他前置条件；`value` 可以是任意值（包括 `undefined`、对象、数组等），函数会安全地返回 `false`。

6. **调用后保证**：
   - 返回 `true` 时，`value` 保证是 `JsonSchemaScalar`（string/number/boolean/null 之一），且对 'number'/'integer' 类型还额外保证是有限数、非负零（number 类型）或整数（integer 类型）。
   - 返回 `false` 时，`value` 不满足对应类型的 JSON 标量约束。
   - 函数不改变任何状态，可安全重复调用。

【调用方须知】最容易被忽略的是：`scalarMatches('number', value)` 和 `scalarMatches('integer', value)` 并不接受所有 `typeof value === 'number'` 的值——它们通过 `isJsonNumber` 排除了 `NaN`、`Infinity`、`-Infinity` 以及**负零 `-0`**（`Object.is(value, -0)` 为真时返回 false）。因此调用方若用 `typeof value === 'number'` 的直觉判断，会把 `-0`、`NaN` 等误判为合法 JSON 数字；在需要严格 JSON 数字语义（如校验 `enum`/`const` 字面量）时必须依赖此函数而非 `typeof` 检查。

*✓ 核实通过——逐行核对代码原文，候选答案对输入、输出、逻辑、副作用、前置条件和调用方须知的描述均与源码一致，特别是对 -0 和 NaN 的排除准确无误。*

### [B] src\json-schema.ts :: assertObjectJsonSchema（第397行，复杂度6）

## assertObjectJsonSchema 的契约（src/json-schema.ts 第397-406行）

```ts
export function assertObjectJsonSchema(schema: unknown): asserts schema is ObjectJsonSchema {
  const violations: string[] = []
  checkSchemaNode(schema, 'schema', violations, new Set())
  if (violations.length === 0
    && (!isJsonSchemaRecord(schema) || !Object.hasOwn(schema, 'type') || schema.type !== 'object')) {
    violations.push('schema.type must be "object" (structured output is object-rooted)')
  }
  if (violations.length > 0) throw new JsonSchemaError(violations)
}
```

### 输入
- 参数 `schema: unknown`——一个不受信任的原始 JSON Schema（docstring 明确写 `untrusted caller-supplied schema`，第393行）。
- 它可以是任意值（`unknown`），包括非对象、数组、原始值等。

### 输出
- 若断言成功：无返回值，但通过 TypeScript 类型守卫 `asserts schema is ObjectJsonSchema` 将 `schema` 收窄为 `ObjectJsonSchema`（即 `JsonSchemaNode & { type: 'object' }`，第91行）。
- 若断言失败：抛出 `JsonSchemaError`（第405行），其 `violations` 数组列出所有违规路径（`JsonSchemaError` 构造器第96-103行，`super(..., 'UNSUPPORTED_SCHEMA')`）。

### 副作用
- **无外部副作用**。函数只做纯校验：不修改 `schema` 对象、不写文件、不改全局状态。它只构造局部 `violations` 数组和局部 `Set`（第398行），并可能抛异常。

### 前置条件
- 无。调用方不需要预先做任何事，任何值都可以传入。

### 调用后保证
1. **若未抛异常**：`schema` 满足受支持的子集（`checkSchemaNode` 通过，第399行），**且** 它是一个对象根 schema——即 `isJsonSchemaRecord(schema)` 为真、`schema` 自身拥有 `type` 属性、且 `schema.type === 'object'`（第400-402行）。
2. **若抛异常**：`schema` 不在受支持子集内，或不是对象根。异常携带 `violations` 数组，列出每个违规路径（第404-405行）。

### 与 assertSupportedJsonSchema 的区别
`assertSupportedJsonSchema`（第383-387行）只校验子集，接受 annotation-only（无 `type`）的 schema 作为无约束 JSON；而 `assertObjectJsonSchema` 额外强制根必须是 `type: 'object'`（第400-402行），这是 subagent 和 workflow 结构化输出保留的约束（docstring 第391-392行）。

### 校验细节（依据 checkSchemaNode 第218-374行）
- 每个节点必须是 `isJsonSchemaRecord`（普通对象、仅自有可枚举字符串键，第154-158行），否则报 `must be a schema object`（第229行）。
- 循环引用被检测并报 `is circular`（第231-232行）。
- 只允许 `CONSTRAINT_KEYWORDS`（type/oneOf/properties/required/additionalProperties/items/enum/const）和 `ANNOTATION_KEYWORDS`（description/title/default/examples），其他键报 `is not a supported keyword`（第235-244行）。
- `type` 和 `oneOf` 不能同时声明（第255-257行）；无 `type` 也无 `oneOf` 时，约束关键字报 `requires type or oneOf`（第258-262行）。
- `oneOf` 必须是至少两个 schema 的数组（第264-267行），且不能与 properties/required/additionalProperties/items/enum/const 共存（第219-224行）。
- 标量类型（string/number/integer/boolean/null）的 `enum` 必须是非空且元素类型匹配的数组，`const` 必须类型匹配，且 `const` 在同时声明 `enum` 时必须是 `enum` 之一（第344-365行）。
- 注解（description/title/default/examples）必须是 lossless JSON 数据（第236-243行），description/title 还必须是字符串（第245-249行）。

【调用方须知】这个函数的名字只强调“对象根”，但它的校验远不止检查 `type === 'object'`：它会对整棵 schema 树做完整的子集校验（包括 `oneOf` 至少两个分支、`required` 里的每个名字必须出现在 `properties` 中、`enum`/`const` 的类型匹配、循环引用检测、以及任何不在白名单里的关键字都会导致抛错），所以一个“看起来只是对象根”的 schema 可能因为某个深层子节点用了不支持的写法（比如 `type: ['string','number']` 数组、或 `oneOf` 只有一个分支）而抛 `JsonSchemaError`——调用方不能只检查根节点的 `type` 就跳过这个断言。

*✓ 核实通过——逐条核对了候选答案引用的函数体、错误类型、校验逻辑和边界情况，所有具体说法都与源码一致，没有发现虚构或错误内容。*

### [B] src\json-schema.ts :: checkScalarValue（第475行，复杂度6）

函数 `checkScalarValue(node: JsonSchemaNode, value: unknown, path: string): string[]`（src/json-schema.ts 第475-481行）的契约如下：

**输入**：
- `node`：一个 `JsonSchemaNode`，代表一个已通过基本类型检查的标量 schema 节点（注释 `Validate one scalar node after its primitive type check`，第474行）。
- `value`：待校验的标量值（`unknown` 类型）。
- `path`：用于生成诊断消息的路径字符串。

**输出**：
- 返回 `string[]`，即违规诊断消息数组。
- 若 `node` 有 `enum` 属性且 `value` 不在 `allowed` 数组中，返回 `["${diagnosticPath(path)}" must be one of ${JSON.stringify(allowed)}]`（第477-479行）。
- 若 `node` 有 `const` 属性且 `value !== node.const`，返回 `["${diagnosticPath(path)}" must be ${JSON.stringify(node.const)}]`（第480-481行）。
- 否则返回空数组 `[]`（第482行）。

**副作用**：
- 无。函数是纯函数，不修改任何外部状态、文件或全局数据；只读取 `node`、`value`、`path` 并返回新数组。

**前置条件**：
- 调用方必须保证 `node` 是标量 schema 节点（即已通过基本类型检查，如 `string`/`number`/`boolean`/`null` 等），因为函数只处理 `enum`/`const` 约束，不处理类型本身。
- `node` 必须是一个对象，且 `Object.hasOwn` 可用（ES2022+）。
- `value` 应是一个标量值（`JsonSchemaScalar`），因为 `allowed.includes(value as JsonSchemaScalar)` 做了类型断言（第478行）。

**后置条件**：
- 返回的数组要么为空（校验通过），要么包含恰好一条诊断消息（校验失败）。
- 诊断消息的格式固定为 `"${diagnosticPath(path)}" must be ...`。

**调用方须知**：调用方最该警惕的是：该函数只检查 `enum` 和 `const` 两个关键字，**不会**检查 `type`、`minimum`、`maxLength`、`pattern` 等其他约束——它假定调用方已经先完成了基本类型检查（见注释 `after its primitive type check`，第474行），如果直接对未做类型检查的任意值调用它，`enum`/`const` 之外的约束会被静默忽略，导致校验不完整。

*✓ 核实通过——候选答案对函数输入、输出、副作用、前置条件和后置条件的描述均与代码原文相符，且调用方须知准确指出了函数只处理 enum/const 而不做类型检查的事实。*

### [B] src\py-types.ts :: renderToolsSdkPy（第763行，复杂度9）

函数 `renderToolsSdkPy`（src/py-types.ts 第763行起）的契约如下，每条均引用代码原文：

**输入**
- 参数 `schemas: ToolSdkSchema[]`——工具 schema 加 canonical 输出 schema 的数组。docstring 明确："the tool schemas plus canonical output schemas to declare (the caller excludes `run_code` itself)"。
- 前置条件：输入中不得有重名工具。docstring 说："The sort is not a total order on byte-equal names, so two schemas sharing a name would render in argument order; the caller's visible-capability map is keyed by name, so the input never carries a duplicate."——即调用方必须保证 `schemas` 里没有重名项，否则输出顺序不确定。

**输出**
- 返回一个字符串：完整的 `tools:sdk` prompt 段落。docstring："Render the full `tools:sdk` prompt section under `runtime.language === 'python'`"，"@returns the complete section text."。
- 输出是确定性的：docstring 说 "Deterministic — tools are emitted in lexicographic name order... so an unchanged tool set produces byte-identical text across assemblies"。代码里 `const sorted = [...schemas].sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0)` 按名字字典序排序。
- 输出结构：`SDK_INSTRUCTIONS` 固定说明 + 一个 ```python 代码块，内含 `from typing import ...`、`class ToolCallError`、若干 `TypedDict` 类、`class Tools(Protocol)`、`tools: Tools`。代码：`return `${SDK_INSTRUCTIONS}\n\n\`\`\`python\n${declaration}\n\`\`\``。

**副作用**
- 无外部副作用：函数是纯函数，不写文件、不改全局状态。它只构造并返回字符串。内部 `state` 是局部变量（`const state: RenderState = {...}`），只用于收集渲染过程中的类声明和 typing 符号，不逃逸。
- 唯一"状态"是 `state.classes`、`state.typing` 等局部收集器，全部在函数内消费，不修改任何传入对象（`[...schemas]` 是拷贝，不修改原数组）。

**调用后保证**
- 返回的文本是语法上有效的 Python 代码块（在 ```python 围栏内），可被模型程序使用。
- 每个工具要么渲染为 `async def name(self, args: X) -> Y:` 方法（当 `isBareIdentifier(schema.name) && !RESERVED.has(schema.name) && !schema.name.startsWith('_')`），要么渲染为 `# tools["name"](args: X) -> Y` 注释（下标访问路径）。代码：`if (isBareIdentifier(schema.name) && !RESERVED.has(schema.name) && !schema.name.startsWith('_')) { ... } else { members.push(`${pad(1)}# tools[${JSON.stringify(schema.name)}](args: ${argType}) -> ${outputType}`) }`。
- 若所有工具都走下标路径（没有方法被发出），类体会插入 `pass` 以保证语法有效："Subscript entries are COMMENTS, not statements: a class body of only comments fails to parse, so `pass` is required whenever no method was emitted"，代码 `const bodyLines = statements > 0 ? members : [`${pad(1)}pass`, ...members]`。
- `typing` import 行只列出实际用到的符号：`const imports = TYPING_ORDER.filter(symbol => state.typing.has(symbol))`，且 `TYPING_ORDER` 顺序固定（`['Any', 'Literal', 'NotRequired', 'Protocol', 'TypedDict']`），保证确定性。
- 每个对象的参数/输出都渲染为命名 `TypedDict`（`${camelCase(schema.name)}Args` / `${camelCase(schema.name)}Output`），嵌套对象也各自命名，类声明先于引用它们的父类（docstring："class declarations precede the protocol in that same order (nested classes before the parent that references them)"）。

【调用方须知】最容易忽略的是：返回的 SDK 文本里 `TypedDict` 类只是静态桩，运行时并不存在——`SDK_INSTRUCTIONS` 明确写着 "the `TypedDict` classes do NOT exist at run time, so build arguments as plain `dict`/`list` JSON values: `await tools.name({"field": 1})`, never `FooArgs(field=1)`, which raises `NameError`"——所以调用方（或下游模型）绝不能把生成的 `TypedDict` 类当作可实例化的运行时类型，必须用普通 dict 传参；同时，名字不是合法裸标识符（含 `-`、是 Python 关键字、或以下划线开头）的工具会被渲染成 `# tools["name"](...)` 注释而非方法，调用方必须通过 `tools["name"]` 下标访问，不能写成 `tools.name`。

*✓ 核实通过——逐条核对了候选答案引用的代码原文和 docstring，所有具体说法（输入输出、确定性、副作用、方法/注释分支、pass 插入、import 过滤、TypedDict 运行时不存在）均与源码一致。*

### [B] src\py-types.ts :: pyScalar（第436行，复杂度7）

函数 `pyScalar`（src/py-types.ts 第436行）的契约如下：

**输入**：一个 `JsonSchemaScalar` 类型的值（即 JSON Schema 标量：`true`/`false`/字符串/数字）。

**输出**：一个字符串，表示该值在 Python 类型表达式（`Literal[...]`）中的字面量写法。

**行为与副作用**：纯函数，无副作用——不修改任何外部状态、文件或全局数据。它只读取输入并返回字符串。

**前置条件**：调用方传入的值必须是 `JsonSchemaScalar` 类型（即 `boolean | string | number`）。函数内部对 `number` 的处理依赖 `Number.isInteger` 和 `Number.isSafeInteger`，因此传入的值必须是合法的 JS 数字（不能是 `NaN`、`Infinity` 等，但这类值本就不属于 `JsonSchemaScalar`）。

**保证**：
1. 对 `true`/`false` 返回 `'True'`/`'False'`（Python 布尔字面量）。
2. 对字符串返回 `JSON.stringify(value)` 的结果——即带双引号的 JSON 字符串，其中所有需要转义的字符（`"`、`\\`、`\b`、`\f`、`\n`、`\r`、`\t`、`\uXXXX`）都被转义，且这些转义恰好也是 Python 的转义，因此输出既能被 Python 解析，又能解码回原值（见第400-420行注释）。
3. 对整数但超出安全范围的数字（`Number.isInteger(value) && !Number.isSafeInteger(value)`），返回 `BigInt(value).toString()`——即该整数的十进制数字字符串（如 `2**60` 返回 `'1152921504606846976'`），而不是可能被 JS 舍入的浮点表示。
4. 对其他数字（包括非整数、安全范围内的整数），返回 `String(value)`——即 JS 默认的数字转字符串。

**调用方须知**：最容易被忽略的是：对超出安全范围的整数（如 `2**53` 以上的整数），函数返回的是 `BigInt` 的十进制字符串（如 `'1152921504606846976'`），而不是 `JSON.stringify` 可能产生的舍入后的浮点字符串（如 `1.152921504606847e+18`）。这意味着调用方如果期望输出是 `JSON.stringify` 的结果，会得到不同的、更精确的表示——这是有意为之（见第400-420行注释），但若调用方依赖 `JSON.stringify` 的舍入行为，就会出错。另外，对非整数数字（如 `1.5`），返回的是 `String(value)`（如 `'1.5'`），这会导致 `Literal[1.5]` 在严格 PEP 586 检查器下被拒绝（见 `renderConstrainedScalar` 的注释），但函数本身不负责处理这种偏差。

*✓ 核实通过——我逐行核对了 `pyScalar` 的实现及其上下文注释，候选答案的每一条契约描述（输入、输出、副作用、前置条件、保证）都能在代码中找到直接对应，且没有夸大或遗漏。调用方须知指出的 `BigInt` 行为是代码中明确设计且注释强调的，是调用方容易忽略的关键点。*

### [E] src\schema.ts :: runSchemaCompiler（第275行，复杂度37）

`runSchemaCompiler`（src/schema.ts 第275行）是一个**私有**函数，签名 `function runSchemaCompiler(initial: CompileTask): void`，返回 `void`。它不直接暴露给调用方，而是被 `compilePropertyMap` 和 `compileValueSchema` 调用（第449、459行），这两个函数又分别被 `parameterSchemaSpecToJsonSchema` 和 `valueSchemaSpecToJsonSchema` 使用。

**输入**：一个 `CompileTask`（`initial`），即一个描述待编译节点/属性映射及其安装位置的判别联合（第275行）。

**输出**：无返回值（`void`）。编译结果通过 `NodeDestination`/`PropertyMapDestination` 写入调用方提供的 holder 或目标对象（`assignCompiledNode`、`assignCompiledPropertyMap`，第214-244行）。

**副作用**：
1. **修改传入的 destination 对象**：通过 `assignCompiledNode` 写入 `holder.value`、`target[key]`、`target.items`、`target[index]`（第214-232行）；通过 `assignCompiledPropertyMap` 写入 `holder.value` 或 `target.properties`（第236-244行）。
2. **修改编译产物节点**：设置 `node.type`、`node.additionalProperties`、`node.enum`、`node.const`、`node.oneOf`、`node.items`、`node.properties`、`node.required` 等（第330-420行）。
3. **修改局部 `required` 数组**：在 `property` 任务中 `task.required.push(task.key)`（第300行），并在 `property-map-tail` 中写入 `compiled.required` 和 `target.required`（第283-287行）。
4. **不修改任何全局/文件/外部状态**：所有写入都限于传入的 destination 和局部变量。

**前置条件**：
1. `initial` 必须是合法的 `CompileTask`（`value`/`property-map`/`property`/`property-map-tail`/`leave` 之一，第275行）。
2. 输入对象必须是 JSON 记录（`isJsonSchemaRecord` 检查，第296、318行），否则抛 `JsonSchemaError`。
3. 输入不能是循环引用（`seen` 集合检测，第319、321行），否则抛 `JsonSchemaError`。
4. 对 `object` 节点，`additionalProperties` 必须显式为布尔值（第337-339行）。
5. 对 `oneOf`，不能同时声明 `type`，且 `oneOf` 必须是至少两个分支的数组（第326-329行）。
6. 对 `property` 任务，`required` 若存在必须为 `true`（第297-299行）。
7. 对 `value` 任务，`type` 必须是合法值（string/number/integer/boolean/null/array/object/json），否则抛错（第420-421行）。

**调用后保证**：
1. 若编译成功，destination 指向的节点/属性映射已被完整填充，且符合原始 JSON Schema 子集（`assertSupportedJsonSchema` 在调用方 `valueSchemaSpecToJsonSchema`/`parameterSchemaSpecToJsonSchema` 中执行，第470、485行）。
2. 若编译失败，抛出 `JsonSchemaError`（`authorError`，第160-162行），且不会返回。
3. 编译是**栈安全**的：使用显式任务栈 `tasks` 而非递归（第277-278行），避免深层嵌套导致栈溢出。
4. 循环引用会被检测并拒绝（第319、321行）。

【调用方须知】`runSchemaCompiler` 是**迭代式**的，它通过 `seen` 集合检测循环引用，但 `seen` 只在 `leave` 任务时删除（第280-282行）——这意味着**同一个对象在编译过程中被引用两次（非循环，而是 DAG 共享）也会被误判为循环**并抛错。例如，同一个 schema 对象同时作为两个属性的 `items` 或 `oneOf` 分支，第二次遇到时 `seen.has(input)` 为真，会抛 `... is circular`。调用方若想复用同一 schema 对象，必须复制对象或使用不同的对象实例，否则会得到错误的循环错误。

*✗ 核实不通过——候选答案对函数签名、调用关系、副作用等描述基本准确，但关于 seen 集合导致 DAG 共享误判的结论与代码实际执行顺序不符，因为 leave 任务在子任务完成后立即执行，不会导致同一对象在编译期间被重复标记。*

### [D] src\ts-types.ts :: docLines（第32行，复杂度29）

函数 `docLines` 定义在 `src/ts-types.ts` 第 32-39 行，是一个内部（非导出）辅助函数，其契约如下：

**输入**：
- `description: unknown` —— 任意类型的值，通常来自 JSON-Schema 节点的 `description` 字段（调用方在 `renderToolsSdk` 第 264 行 `docLines(schema.description, 1)` 和 `renderSupportedSchema` 第 166 行 `docLines(prop.description, frame.indent + 1)` 传入）。
- `indent: number` —— 缩进层级数，用于生成行首空格。

**输出**：
- 返回 `string[]`（字符串数组）。
- 当 `description` 不是字符串或为空字符串时，返回空数组 `[]`（第 33 行：`if (typeof description !== 'string' || description.length === 0) return []`）。
- 否则返回恰好一个元素的数组，元素为一行 JSDoc 注释：`/** <collapsed> */`，其中 `<collapsed>` 是把 description 中所有连续空白（含换行）折叠成单个空格并 trim 后的结果（第 35 行：`description.replace(/\s+/g, ' ').trim()`），且所有 `*/` 被转义为 `*\/`（第 36 行：`collapsed.replaceAll('*/', String.raw`*\/`)`）。行首有 `pad(indent)` 生成的 `'  '.repeat(indent)` 缩进（第 36 行）。

**副作用**：
- 无。函数是纯函数，不修改任何外部状态、文件或全局数据；只读取 `description` 和 `indent` 并返回新数组。

**前置条件**：
- 无特殊前置条件。`indent` 应为非负整数（`pad` 用 `'  '.repeat(indent)`，负数会抛 RangeError，但调用方总是传非负值，如 0、1、`frame.indent + 1`）。`description` 可为任意值，函数对非字符串安全降级。

**调用后保证**：
- 返回的数组要么为空，要么恰好含一个元素；该元素总是以 `/** ` 开头、以 ` */` 结尾，且内部不会包含 `*/`（已转义），因此不会意外终止生成的 JSDoc 块（第 34 行注释明确说明此意图）。
- 返回的字符串不含换行（空白已折叠），保证是单行注释。

【调用方须知】最该警惕的是：`docLines` 返回的数组元素是**单行** JSDoc，且把 description 中所有换行/多段空白折叠成单个空格——如果 description 本身是带格式的多行文本（比如含列表、代码块或有意保留的换行），这些格式会被完全抹平，生成注释变成一长串挤在一行；同时它只转义 `*/`，不转义 `/*` 或 `*`，所以 description 里若含 `/*` 不会破坏注释，但含 `*/` 会被转义成 `*\/`（字面量反斜杠加星号斜杠），渲染出的注释文本与原始 description 并不逐字一致——依赖 description 原文的调用方（如测试断言）会踩坑。另外注意它返回的是数组，调用方必须用 `for...of` 或展开（如 `renderToolsSdk` 第 264 行 `argsMembers.push(...docLines(...))`）来消费，不能直接当字符串用。

*✓ 核实通过——候选答案对输入、输出、副作用、前置条件、调用后保证的描述均与代码原文逐条吻合，且【调用方须知】指出的单行折叠、仅转义 `*/`、返回数组需展开消费等行为均有代码依据。*

### [B] tests\code-mode.spec.ts :: setup（第50行，复杂度8）

函数 `setup`（tests/code-mode.spec.ts 第50行）是一个测试夹具（fixture），用于搭建一个完整的 Code Mode 测试环境。

**输入（参数）**：`options: SetupOptions = {}`（第50行），可选字段：
- `mode?: Config['mode']`（第42行）——传给 ToolRuntime 的 mode，默认 `'code'`（第53行 `options.mode ?? 'code'`）
- `maxParallelSubCalls?: number`（第43行）——仅在明确提供时传给 ToolRuntime（第53行 `...options.maxParallelSubCalls !== undefined ? { maxParallelSubCalls: options.maxParallelSubCalls } : {}`）
- `runtime?: false | { language?: string }`（第44行）——`false` 表示不安装 FakeRuntime；否则安装，`{ language }` 作为其配置（第55-58行）
- `toolOrder?: string[]`（第45行）——仅在提供时传给 SystemPrompt（第52行 `...options.toolOrder ? { toolOrder: options.toolOrder } : {}`）

**输出（返回值）**：一个对象（第59行 `return { ctx, tools: ctx.tools, systemPrompt: ctx.systemPrompt, runtime: runtime! }`），包含：
- `ctx`：新建的 `Context` 实例（第51行 `const ctx = new Context()`）
- `tools`：`ctx.tools`
- `systemPrompt`：`ctx.systemPrompt`
- `runtime`：`FakeRuntime` 实例（若 `options.runtime !== false`），否则为 `undefined`（第58行 `runtime!` 非空断言）

**副作用（外部状态修改）**：
- 在传入的 `ctx` 上安装插件：`SystemPrompt`（第52行）、`ToolRuntime`（第53行）、`FakeRuntime`（第56行，若启用）。这些 `ctx.plugin(...)` 调用会修改 `ctx` 内部状态（注册工具、系统提示、code runtime）。
- 若 `options.runtime !== false`，会把 `ctx.codeRuntime` 赋值给局部变量 `runtime`（第57行 `runtime = ctx.codeRuntime as FakeRuntime`），并作为返回值暴露。
- 不修改任何全局/文件状态；`FakeRuntime` 的 `run` 会记录 `lastRequest`（第31行），但那是测试内可观察的实例状态，不是外部全局。

**前置条件**：
- 无显式前置条件；`options` 可省略（默认 `{}`）。但若 `options.runtime` 为 `false`，返回值 `runtime` 会是 `undefined`（第58行 `runtime!` 非空断言在运行时不会报错，只是类型上断言非空）。
- 依赖 `Context`、`SystemPrompt`、`ToolRuntime`、`FakeRuntime` 等已导入（第2-9行）。

**调用后保证**：
- 返回的 `ctx` 已安装 SystemPrompt 和 ToolRuntime（mode 为 `options.mode ?? 'code'`），因此 `ctx.tools` 可用（第59行）。
- 若 `options.runtime !== false`，`ctx.codeRuntime` 是一个 `FakeRuntime`，其 `behavior` 默认返回 `{ logs: [] }`（第28行），测试可覆盖它。
- 返回的 `systemPrompt` 是 `ctx.systemPrompt`，其内容受 `toolOrder` 影响（若提供）。

【调用方须知】当 `options.runtime` 为 `false` 时，返回值里的 `runtime` 是 `undefined`（第58行 `runtime!` 只是类型断言，运行时就是 `undefined`），任何对 `runtime` 的访问（如 `runtime.behavior`）都会抛 TypeError；同时 `ctx.codeRuntime` 也不存在，因此不要在这种配置下调用 `runCode` 或依赖 code runtime。这是最容易忽略的边界情况——`runtime: false` 的语义是“不安装 runtime”，而不是“安装一个空 runtime”。

*✓ 核实通过——候选答案对 setup 的输入、输出、副作用、前置条件和保证的描述均与代码原文逐条吻合，包括 `runtime: false` 时返回 `undefined` 的边界情况（第58行 `runtime!` 只是类型断言）。*

### [B] tests\code-mode.spec.ts :: (anonymous)（第1435行，复杂度7）

（超过最大步数，未能得出答案）

*✗ 核实不通过——Since the candidate answer provides no content and the referenced function does not exist in the file, the answer is not accurate.*

### [B] tests\code-mode.spec.ts :: (anonymous)（第279行，复杂度6）

第279行的「(anonymous)」是 `it.each(['code', 'both'] as const)('reserves run_code against scoped shadows and explicit restrictions in mode %s', async (mode) => { ... })` 这个测试用例（vitest 的 `it.each` 会为每个 mode 生成一个匿名测试函数，圈复杂度6）。它的契约如下：

**输入**：
- 参数 `mode`，只能是 `'code'` 或 `'both'`（`it.each(['code', 'both'] as const)`）。
- 通过 `setup({ mode })` 构造 `ctx` 和 `systemPrompt`（第280行）。
- 通过 `mintAgentScope(ctx)` 得到 `scope` 和 `agent`（第281行）。
- 构造一个名为 `RUN_CODE_NAME` 的“冒名”工具 `impostor`（第282-286行）。

**输出**：
- 该函数本身不返回值（async 测试），其“输出”是断言结果：
  - `scope.ctx.tools.register(impostor)` 必须抛出 `/reserved for the Code Mode presentation transport/`（第288行）。
  - `ctx.tools.register(impostor)` 必须抛出同样的错误（第289行）。
  - `scope.ctx.tools.restrict({ allow: [RUN_CODE_NAME] })` 必须抛出 `/cannot name reserved Code Mode presentation transport/`（第290行）。
  - `scope.ctx.tools.restrict({ deny: [RUN_CODE_NAME] })` 必须抛出同样的错误（第291行）。
  - `assembly.tools` 中名为 `RUN_CODE_NAME` 的工具恰好有1个，且其 `description` 包含 `'Execute a TypeScript program'`（第300-302行）。
  - `assembly.sections` 中名为 `'scoped-note'` 的 section 文本是 `'safe note'`（第303行）。
  - `assembly.sections` 中名为 `'tools:sdk'` 的 section 文本包含 `'scoped_safe:'`（第304行）。
  - `ctx.tools.get(RUN_CODE_NAME, agent)` 与 `ctx.tools.get(RUN_CODE_NAME)` 是同一个对象（第305行）。
  - `runCode(ctx, 'return 1', { agent })` 的结果 `content` 等于 `[{ type: 'text', text: '(run_code completed with no output)' }]`（第306-307行）。

**副作用（外部状态修改）**：
- 在 `scope` 上注册了一个名为 `'scoped_safe'` 的工具（第292-296行），并添加了一个名为 `'scoped-note'` 的 system prompt section（第292行）。这些是测试内部对 `scope` 状态的修改，用于验证后续 `assemble` 的行为。
- 调用了 `systemPrompt.assemble({ scope: agent })`（第299行），这会触发 system prompt 的组装过程。
- 调用了 `runCode(ctx, 'return 1', { agent })`（第306行），这会触发一次代码运行。

**前置条件**：
- 必须通过 `setup({ mode })` 初始化，且 `mode` 为 `'code'` 或 `'both'`（第280行）。
- 必须存在 `mintAgentScope` 函数（第281行），它返回 `scope` 和 `agent`。
- 必须存在 `defineContentToolFixture`、`RUN_CODE_NAME`、`runCode` 等测试辅助（第282、306行）。
- 测试依赖 `systemPrompt.assemble` 在 `mode` 为 `'code'` 或 `'both'` 时能正常组装（第299行）。

**调用后保证**：
- 注册名为 `RUN_CODE_NAME` 的工具（无论全局还是 scope 级）必然失败，且错误信息包含 `'reserved for the Code Mode presentation transport'`。
- 对 `RUN_CODE_NAME` 做 `allow`/`deny` 限制必然失败，错误信息包含 `'cannot name reserved Code Mode presentation transport'`。
- 组装后的 `assembly.tools` 中 `RUN_CODE_NAME` 恰好出现一次，且其描述是 TypeScript 风格的 `'Execute a TypeScript program'`。
- 在 scope 上注册的其他工具（如 `scoped_safe`）和自定义 section（如 `scoped-note`）会正常出现在组装结果中。
- `ctx.tools.get(RUN_CODE_NAME, agent)` 与全局的 `ctx.tools.get(RUN_CODE_NAME)` 是同一个对象，即 `RUN_CODE_NAME` 工具在 scope 下不会被遮蔽。
- 运行 `'return 1'` 程序时，输出固定为 `'(run_code completed with no output)'`。

【调用方须知】最容易被忽略的是：这个测试断言 `ctx.tools.get(RUN_CODE_NAME, agent)` 与 `ctx.tools.get(RUN_CODE_NAME)` 是同一个对象（第305行），这意味着 `RUN_CODE_NAME` 工具在 scope 下不会被遮蔽——即使你在 scope 里注册了同名工具（会直接抛错），`run_code` 始终是全局唯一的、不可被 scope 覆盖的“保留传输通道”。调用方若试图在某个 scope 内用同名工具覆盖或限制 `run_code`，会立即抛错，而不是静默生效。

*✓ 核实通过——I read the actual test file and verified every claim in the candidate answer against the code, including the exact line numbers, function calls, assertion messages, and the final runCode output. All details match the source code.*

### [B] tests\invariant.spec.ts :: execution（第20行，复杂度7）

函数 `execution`（第20-27行）是一个测试辅助工厂，用于构造 `ToolExecution` 对象。

**输入**：一个可选的 `overrides` 参数（`Partial<ToolExecution>`，默认 `{}`），用于覆盖默认字段。

**输出**：一个 `ToolExecution` 对象，包含以下字段：
- `token`: `Symbol('tool')`（第21行）
- `callId`: `CallId('call-1')`（第22行）
- `name`: `'echo'`（第23行）
- `arguments`: `Object.freeze({ text: 'hi' })`（第24行）
- `signal`: `overrides.signal ?? testToolSignal`（第26行）
- `rootCallId`: `overrides.rootCallId ?? overrides.callId ?? CallId('call-1')`（第27行）

**副作用**：无直接副作用，但注意 `arguments` 被 `Object.freeze` 冻结（第24行），且 `overrides` 中的 `arguments` 若传入则不会被冻结（因为 `...overrides` 在冻结之后展开，第25行）。

**前置条件**：无显式前置条件，但调用方需注意 `overrides` 中的 `callId` 或 `rootCallId` 若传入，会影响 `rootCallId` 的默认值（第27行）。

**调用后保证**：返回的对象具有稳定的默认值，且 `arguments` 默认被冻结；`rootCallId` 默认等于 `callId` 或 `CallId('call-1')`。

【调用方须知】最容易被忽略的是：`overrides` 中的 `arguments` 不会被冻结（因为 `...overrides` 在 `Object.freeze` 之后展开），如果测试中需要冻结的 `arguments`，必须显式传入 `Object.freeze` 的版本，否则后续对 `arguments` 的修改可能违反 invariant 测试中对冻结的要求（如第3个测试用例 `rejects mutable or anonymous final snapshots` 所检查的）。

*✓ 核实通过——候选答案对execution的输入、输出、副作用、前置条件和保证的描述与代码逐行一致，且【调用方须知】指出的overrides.arguments不会被冻结（因展开顺序）是准确的，与第3个测试用例的检查相符。*

### [C] tests\properties.spec.ts :: valueForProp（第73行，复杂度14）

valueForProp 是 tests/properties.spec.ts 第73行定义的一个纯函数，契约如下：

**输入**：一个 ParameterPropertySpec 类型的参数 prop（第73行 `function valueForProp(prop: ParameterPropertySpec): fc.Arbitrary<unknown>`）。

**输出**：一个 fast-check 的 Arbitrary<unknown>，即一个能生成满足该 prop 约束的值的生成器（第73行返回类型 `fc.Arbitrary<unknown>`，注释“Generate a value that satisfies a prop”）。具体分支：
- 若 prop 有 `oneOf` 字段，返回 `fc.oneof(...prop.oneOf.map(valueForProp))`（第74行），即递归生成每个子 schema 的值并随机选一个。
- 若 prop 有 `const` 字段，返回 `fc.constant(prop.const)`（第75行），即固定生成该常量。
- 按 `prop.type` 分支：
  - `'string'`：有 `enum` 则 `fc.constantFrom(...prop.enum)`，否则 `fc.string()`（第77行）。
  - `'number'`：`fc.double({ noNaN: true, noDefaultInfinity: true }).filter(value => !Object.is(value, -0))`（第78行），排除 NaN、±Infinity 和 -0。
  - `'integer'`：`fc.integer()`（第79行）。
  - `'boolean'`：`fc.boolean()`（第80行）。
  - `'null'`：`fc.constant(null)`（第81行）。
  - `'object'`：有 `properties` 则 `validArgsForSpec(prop.properties)`（递归生成满足嵌套 spec 的对象），否则 `fc.constant({})`（第82行）。
  - `'array'`：有 `items` 则 `fc.array(valueForProp(prop.items), { maxLength: 3 })`（数组长度 0~3），否则 `fc.constant([])`（第83行）。
  - `'json'`：`fc.jsonValue().filter(value => isJsonValue(value))`（第84行），过滤掉非 JSON 值。

**副作用**：无。函数是纯函数，不修改任何外部状态、文件或全局数据；它只构造并返回一个 Arbitrary 对象，不执行任何生成动作（生成发生在调用方后续调用 fc.assert 时）。

**前置条件**：
- 传入的 prop 必须是一个合法的 ParameterPropertySpec，且其结构满足 valueForProp 的分支假设：若 `oneOf` 存在，则 `prop.oneOf` 必须是数组且每个元素是 ParameterPropertySpec（第74行 `prop.oneOf.map(valueForProp)`）；若 `const` 存在，则 `prop.const` 必须存在（第75行）；若 `type` 存在，则必须是 'string'|'number'|'integer'|'boolean'|'null'|'object'|'array'|'json' 之一（第77-84行的 switch，无 default 分支，若 type 为其他值会返回 undefined 导致运行时错误）。
- 对于 `'object'` 分支，若 `prop.properties` 存在，它必须是一个合法的 ParameterSchemaSpec（因为会传给 validArgsForSpec，第82行）。
- 对于 `'array'` 分支，若 `prop.items` 存在，它必须是一个 ValueSchemaSpec（因为会传给 valueForProp，第83行）。
- 对于 `'number'` 分支，`fc.double` 的选项是固定的，不依赖 prop 的其他字段。

**调用后保证**：
- 返回的 Arbitrary 生成的任何值都满足 prop 的约束（这是该函数的设计意图，被第119行 `validArgsForSpec` 使用，并最终被第150行测试“args satisfying the spec pass validateArgs”验证）。
- 对于 `'number'` 分支，保证生成的值不是 NaN、不是 ±Infinity、也不是 -0（第78行的 filter）。
- 对于 `'array'` 分支，保证数组长度 ≤ 3（第83行 `maxLength: 3`）。
- 对于 `'object'` 分支且无 properties 时，保证生成空对象 `{}`（第82行）。
- 对于 `'array'` 分支且无 items 时，保证生成空数组 `[]`（第83行）。

【调用方须知】最容易被忽略的是：valueForProp 对 `'number'` 分支显式过滤掉了 -0（`!Object.is(value, -0)`，第78行），所以它生成的数字永远不会是 -0；但调用方如果自己构造 prop 并期望生成 -0 来测试边界，会永远得不到 -0 值——这可能导致针对 -0 的测试用例永远无法触发，需要调用方自行用其他方式构造 -0 输入。

*✓ 核实通过——逐条对照代码原文，候选答案对每个分支的描述、副作用、前置条件和保证均与代码一致，且【调用方须知】指出的 -0 过滤行为准确无误。*

### [B] tests\properties.spec.ts :: checkLevel（第117行，复杂度7）

「checkLevel」是 tests/properties.spec.ts 第117-125行内嵌在第一个 it 测试里的一个递归局部函数（不是导出函数/类），其契约如下：

**输入**：
- 第一个参数 `s: ParameterSchemaSpec`（一个属性名→属性规格的映射，见第118行 `(s: ParameterSchemaSpec, json: ...)`）。
- 第二个参数 `json: { required?: string[]; properties: Record<string, unknown> }`（一个 JSON Schema 节点，含可选的 `required` 数组和必有的 `properties` 映射）。

**输出**：无返回值（`void`）。它不返回任何东西，而是通过 `expect(...)` 断言来验证。

**行为/副作用**：
- 它调用 `expect(new Set(json.required ?? [])).toEqual(new Set(requiredKeys(s)))`（第119行），断言 JSON Schema 的 `required` 集合与 `requiredKeys(s)` 返回的集合相等。`requiredKeys`（第106-108行）返回 `s` 中所有 `required === true` 的键。注意 `json.required ?? []` 表示若 `json.required` 为 `undefined` 则视为空数组。
- 然后遍历 `s` 的每个条目（第120行 `for (const [key, prop] of Object.entries(s))`），取出 `json.properties[key]`（第121行），若该属性是 `type: 'object'` 且有 `properties`（第122行 `if ('type' in prop && prop.type === 'object' && prop.properties)`），则递归调用自身 `checkLevel(prop.properties, propJson)`（第123行），对嵌套对象层做同样的断言。
- 副作用：它不修改任何外部状态、文件或全局数据；它只调用 `expect` 断言，若断言失败会抛出测试失败异常。它唯一的外部影响是：若断言不成立，测试用例失败。

**前置条件**：
- 调用方必须保证 `json` 的每个 `properties[key]` 在 `s` 有对应条目时存在且可被断言（即 `json.properties[key]` 不为 `undefined`，否则第121行 `as Record<string, unknown>` 会得到 `undefined`，第122行的 `'type' in prop` 只检查 `prop` 不检查 `propJson`，但递归时 `propJson` 若为 `undefined` 会在第119行访问 `json.required` 时抛 TypeError）。
- 调用方必须保证 `s` 中所有 `type: 'object'` 且带 `properties` 的属性，其对应的 `json.properties[key]` 也必须是带 `properties` 的对象，否则递归时 `propJson.properties` 为 `undefined` 会导致第119行 `json.required` 访问报错。
- 调用方必须保证 `s` 和 `json` 结构一致（即 `json` 是由 `parameterSchemaSpecToJsonSchema(s)` 生成的），否则断言会失败。

**调用后保证**：
- 若函数正常返回（未抛异常），则保证：对 `s` 的每一层（包括所有嵌套 object 层），JSON Schema 的 `required` 集合恰好等于该层 `required: true` 的键集合。
- 若断言不成立，函数会抛出测试失败异常（由 `expect` 触发），不会静默返回。

**【调用方须知】**：最容易被忽略的是：`checkLevel` 只对 `type: 'object'` 且带 `properties` 的属性递归，但对 `type: 'array'` 或 `type: 'object'` 但无 `properties` 的属性，它完全不检查其内部 `required`——也就是说，它只验证对象层的 `required` 一致性，不会深入数组的 `items` 或没有 `properties` 的对象，因此调用方若期望它验证所有嵌套层（包括数组元素内的 required），会漏掉这些层。另外，若 `json.properties[key]` 为 `undefined`（即 `s` 有键但 `json` 缺该属性），第121行会得到 `undefined`，但第122行只检查 `prop`，不会报错，直到递归时访问 `json.required` 才抛 TypeError——这是一个不明显的崩溃点。

*✓ 核实通过——候选答案对 checkLevel 的输入、输出、副作用、前置条件和后置条件的描述均与代码原文一致，且准确指出了只递归 object 带 properties 的属性、不检查数组 items 或没有 properties 的对象，以及 propJson 为 undefined 时的崩溃点。*

## 行为描述失败（1个，跳过未纳入上面明细）

- [F] src\py-types.ts :: result（第513行）——模型返回的内容连续2次重试后仍不是合法 JSON：Unterminated string starting at: line 1 column 54 (char 53)

