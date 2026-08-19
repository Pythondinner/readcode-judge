# MCP工具的隐藏依赖：从没加载过.env

> 2026-08-19

## 背景

昨晚给`judge_mcp_server.py`四个工具加`root: str`参数、去掉写死的`READCODE_ROOT`环境变量之后，写了一个真实MCP client测试脚本（stdio协议）去验证，第一次跑后台执行了将近两小时都没收到完成通知——用户回来问"是不是卡住了"，查后台任务的输出文件，发现根本不是卡住，是**MCP server子进程一开始就崩了**：`SystemExit: 未找到DEEPSEEK_API_KEY，请检查.env文件`，只是这个崩溃发生在异步子进程里，父进程的`asyncio`会话没有正确收到退出信号，表现成了"挂起"。

## 真正的问题

排查发现`judge_mcp_server.py`**从建成那天起就从没自己加载过`.env`**——一直依赖外部调用方（测试脚本、Claude Code、dsh）的进程环境里已经干净地带着`DEEPSEEK_API_KEY`。这次是从一个没source过`.env`的干净bash shell里启动测试脚本，子进程继承的环境里根本没有这个key，才第一次真实暴露这个从没被测过的依赖。

这不是测试脚本本身的小问题——它意味着：**如果Claude Code或dsh从它们自己的环境启动这个MCP server，大概率也不会自带`DEEPSEEK_API_KEY`**（这是读码机项目专属的key，不是Claude Code/dsh的标准环境变量），真实调用会撞上同一个崩溃。这是一个会直接影响"读码机被外部agent真实调用"这个核心目标能不能成立的真实缺口，只是因为一直是在同一个开发者环境里手动测试（环境里凑巧已经有这个key），从来没被撞见过。

## 顺带发现的重复

排查时发现这段`.env`加载逻辑，在`dialogue.py`和`checkup_cli.py`里已经各自独立复制了一份，一字不差。这次`judge_mcp_server.py`要是照旧模式再补一份，就是第三次重复——"两次是巧合，三次是模式"，到了该去重的时候。

## 修复

把三份重复删掉，统一放进`sensor/deepseek_client.py`模块级（真正需要`DEEPSEEK_API_KEY`的唯一位置）：所有间接import这个模块的入口（`dialogue.py`、`checkup_cli.py`、`judge_mcp_server.py`，以及未来任何新入口）都会在import时自动加载，不用各自维护一份。

用一个完全干净、没有预设`DEEPSEEK_API_KEY`的环境重新验证：`env -u DEEPSEEK_API_KEY python -c "from sensor import deepseek_client; ..."`，确认key正确从`.env`加载进`os.environ`。随后重新跑MCP client测试，完整通过：`list_tools`确认`root`是四个工具的必填参数，`generate_project_report_tool`真实调用`deep_search_Git`成功返回报告（`isError=False`，18文件39函数）。

## 小结

这是这一整晚反复出现的同一个规律的又一次印证：**每接一层新的调用路径，都会暴露一个之前看不见的隐藏依赖**——上次是Windows下`subprocess`的`.cmd`问题，这次是MCP server对调用方环境的隐式假设。两次都不是"代码写错了"，是"这条路径之前从没被真实跑过，所以这个依赖从没机会暴露"。继续按同样的纪律处理：撞见了就修，不因为"看起来是小问题"就跳过验证。
