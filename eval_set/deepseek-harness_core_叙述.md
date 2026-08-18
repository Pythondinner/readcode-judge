该项目是 DeepSeek Harness 的 core/ 产品 API 主干（见根 README.md 的表格），由 scope、session、system-prompt、tools、agent、agent-default-model、agent-loop 七个包组成，面向需要可替换 agent 驱动、事件溯源会话日志、作用域化工具/提示注册的插件与消费者。

模块职责：
- scope/：作用域注册原语（createScope、scopeTarget、ScopedLayers），提供父子作用域链与作用域过滤事件。
- session/：事件溯源会话日志与内存存储（SessionStore、Session.append、deriveMessages、surface 投影、request-header 重建、chunk-rows 编解码）。
- system-prompt/：提示组装注册表（section/context/tools/variable/assemble、renderPrompt 严格插值）。
- tools/：工具注册表与执行管线（register、guard、execute、pre/post-execute、Code Mode、并行调度）。
- agent/：Agent 接口、注册表、进程内 initiator 作用域、agent/* 事件词汇（AgentRegistry、Inbox、agentEvents）。
- agent-default-model/：部署默认模型选择（currentSelection/saveSelection）。
- agent-loop/：默认具体驱动（ReactLoopAgent、executeToolCalls、AgentLoop 工厂与配置启动）。

关键不变量（每条注明证据范围）：

1. 会话日志是追加式、seq 严格递增、turn/step 必须闭合、同一步的 tool/call 必须配对 tool/result。证据：session/src/invariant.ts 的 validateEvent（seq 递增、turn/start 不能嵌套、turn/end 必须匹配打开 turn、step/start 必须匹配打开 turn、tool/result 必须有先前 tool/call 或合成 TOOL_NOT_STARTED）。该检查通过 ctx.invariants 注册，覆盖所有 session/event 追加路径（internal/dispatch 预验证 + session/event 提交）。

2. 循环构建的 LLM 请求必须与日志派生的消息和折叠的 request/header 完全一致，且请求对象必须冻结。证据：agent-loop/src/invariant.ts 的 install（llm/stream 监听器，prepend 全局）：检查 isAgentLoopRequest、Object.isFrozen(options)、sessionId 存在且为活会话、messages 冻结、日志有 step/start、有 request/header、JSON.stringify(options.messages) === JSON.stringify(session.deriveMessages())、model/system/temperature/maxTokens/stop/tools 与 header 匹配。覆盖 agent-loop 的 buildRequest 路径（agent-loop/src/agent.ts 的 buildRequest 中 markAgentLoopRequest + deepFreeze）。

3. agent/status 不能重复同一状态（no-op 转换）。证据：agent/src/invariant.ts 的 install（agent/status 监听器，WeakMap 记录上次状态，重复则 fail）。覆盖所有 setPhase 状态转换（agent-loop/src/agent.ts 的 setPhase）。

4. 同一 agent/session id 只能有一个活条目，且 agent.id 必须等于 session.id。证据：agent/src/index.ts 的 enter（id !== session.id 抛错；store.has(id) 抛错）与 AgentLoop.prepare 的 publish 顺序（先 sessions.enter 再 agents.enter）。覆盖 ctx.agents.create/resume/register 及配置启动路径。

5. 创建/恢复必须经过 setup（未发布）→ 双注册表 enter → announce → session-start 的顺序，且任何失败回滚不发布任一 id。证据：agent-loop/src/index.ts 的 setupAndPublish（raceAbort(setup) → commit → publish）与 prepare 的 publish（sessions.enter → agents.enter → announce → session-start，每步 assertLive）。覆盖 createAgent/resume 及配置路径（restoreOrCreateConfigured）。

6. 取消（cancel）默认清除 inbox 并中止活动；keepInbox 保留待处理项。证据：agent-loop/src/agent.ts 的 cancel（!keepInbox 时 inbox.clear()，然后 abort）。覆盖 Agent.cancel 接口（agent/src/runtime-types.ts）。

7. 工具结果必须按模型顺序提交，且 tool/result 的 sourceEventSeqs 必须引用其 tool/call 的 seq。证据：agent-loop/src/tool-calls.ts 的 commitReady（按 slots 顺序 appendToolResult，callSeqs 记录）与 appendToolResult（sourceEventSeqs: [callSeq]）。覆盖 executeToolCalls 的普通完成与中止路径（中止时 appendSkippedToolCall 也配对）。

8. 每个 agent 只能有一个作用域注册层，且作用域注册在 dispose 时全部撤销。证据：agent/src/index.ts 的 register/enter（store 唯一条目、detach 幂等）与 agent-loop/src/agent.ts 的 scope.dispose()（prepare 的 dispose 中 machine.scope.dispose()）。覆盖所有 agent 生命周期。

9. 配置的 agent 不能同时有 sessionId 和 resumeSessionId，且不能有重复的精确会话身份。证据：agent-loop/src/index.ts 的 validateConfiguredAgents（互斥检查 + 重复检查）。覆盖配置启动路径（AgentLoop 构造函数）。

10. 工具注册：同一层内不能有重复名称；非 native 模式拒绝保留的 run_code 名称；timeoutMs 必须为正有限数。证据：tools/README.md 的 register 描述（Duplicate names within one layer throw; non-native modes also reject the reserved run_code transport name; non-positive or non-finite timeoutMs fail at registration）。该规则在 tools/src/index.ts 的 register 实现中执行（未直接读取，但 README 明确声明）。

设计特点/取舍：
- 事件溯源：会话日志是唯一真相源，消息历史从日志派生（session/README.md）。
- 作用域化注册：agent.ctx 的注册仅对该 agent 可见且随 dispose 撤销，父子作用域链（scope/README.md）。
- 可替换驱动：agent 接口零循环依赖，agent-loop 是默认实现，通过 setFactory 注入（agent/README.md）。
- 严格失败：未知事件类型拒绝重建（除非 ignorable）、prompt 插值严格、请求重建不匹配即 fail（session/types.ts、system-prompt/README.md、agent-loop/invariant.ts）。
- 进程内 initiator 作用域：仅同进程因果归属，非授权边界（agent/README.md 的 Known Limitations）。
- 工具并行：仅 dispatch/body 重叠，策略/结果/上下文保持模型顺序（tools/README.md 的 Parallel execution）。

注意：不变量 1-3 通过可选 invariant 伴生插件注册（需加载 @deepseek-ai/dsh-invariants），根服务不隐式加载诊断（agent/README.md 明确说明）。不变量 4-10 是核心代码路径的固有行为，不依赖伴生插件。所有不变量均从上述具体文件/入口观察到，未覆盖未读取的入口（如 ACP 桥、其他 host 入口）——这些入口通过 ctx.agents.create/resume 走同一工厂路径，但未逐一验证。