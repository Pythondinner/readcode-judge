# judge层接上MCP：两个工具，端到端跑通

> 2026-08-18

## 背景

之前收敛复盘定下的下一步——把judge层这批新能力（narrative判断、诊断建议）接上MCP，给外部有执行能力的agent（Claude Code、deepseek harness）当信号源用。之前只有最早的`agent.answer_question`通过`agent_mcp.py`/`mcp_server.py`挂了MCP，判断层这批新东西一直是纯Python函数调用。

## 做了什么

新建`src/judge_mcp_server.py`，跟已有的`mcp_server.py`（暴露sensor层的`list_directory`/`read_file`/`search_code`）是同一种包装方式，但暴露judge层更高层的两个工具，不是全部能力：

- `generate_project_report_tool(with_narrative=True)`：跑一遍完整体检，返回排版好的Markdown。
- `diagnose_and_propose_fix_tool(file_path, function_name, matched_invariant, reasoning, description)`：针对报告里一条具体发现，深入查调用方、给修复建议。

刻意只暴露这两个，不是consensus/迭代信号分层全部搬过来——先验证"外部agent能不能通过MCP拿到judge层的信号并用起来"这条链路能不能走通，其它能力等这条路径真的被用起来再看要不要接，不是一次性把所有东西都包一遍。

## 撞到的问题：mcp_server.py本来就是坏的

写完发现`import`报错——`from mcp.server.mcpserver import MCPServer`这个类在当前装的SDK版本（1.29.0）里根本不存在，正确的是`from mcp.server.fastmcp import FastMCP`。查了一下，**这个错误的import是从已有的`mcp_server.py`原样复制过来的**——也就是说，`mcp_server.py`这个"早就验证过"的sensor层MCP server，本身可能从来没有真的作为独立进程被成功启动过（`agent_mcp.py`把它当子进程连接，如果这个连接本身之前从没跑通过，这个"已验证"的标签就是不准确的）。两个文件的`import`都改成了正确的`FastMCP`。

测试脚本自己也踩了同一类版本不匹配的坑：`call_tool_result.is_error`在当前SDK里叫`isError`（驼峰），改了一下就好。

## 验证

写了个独立的MCP client测试脚本（不是`agent_mcp.py`那种完整agent循环，只是单纯测协议这层通不通），对自动剧本生成机跑：`generate_project_report_tool`（`with_narrative=False`，只测plumbing不重新测判断准不准，那部分今晚已经用直接Python调用测了很多次）返回42358字符的完整报告；`diagnose_and_propose_fix_tool`用`write_and_save_one_with_check`的材料测，正确返回"不需要修复（已被调用方防护）"——这是个意外的额外确认：因为喂的是这个函数当年被判定"undermine"时的原始材料，而现在代码已经修过了，诊断工具通过MCP协议独立重新查了一遍调用链，正确识别出修复已经生效，跟之前那次真实闭环的结论一致。

两个工具端到端都通过真实MCP协议调用成功。

## 结论

- judge层现在有了一条外部agent能用的MCP入口，不是只能被这个项目自己的Python代码调用。
- 顺带修好了一个此前没被发现的问题：`mcp_server.py`的import本身是坏的，这次不是新造的bug，是第一次真的用子进程方式启动它才暴露出来。
- 依然刻意保留的边界：只产出报告和建议，不写文件、不改代码——跟今晚所有其它环节一样，执行永远是外部agent自己的事。

## 还没做的

- 只测过"协议通不通"，没有真的接一个有执行能力的agent（Claude Code/deepseek harness）当MCP client去跑一遍"看报告→挑一条发现→拿建议→（人工确认后）改代码"这条完整路径。
- consensus、迭代信号分层（Tier1/Tier2）这两个能力还没接进MCP。
- 没有为`judge_mcp_server.py`写独立的README/使用说明，目前只有代码里的docstring。
