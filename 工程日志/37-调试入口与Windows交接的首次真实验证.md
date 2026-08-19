# 调试入口与Windows交接的首次真实验证

> 2026-08-19

## 背景

工程日志36建成`dialogue.py`，但"交给Claude Code处理"这一步从没被真实跑通过——用户自己拿真实有bug的worktree（`剧本机_测试用_有bug版本`）测了两次，都在consensus判断这一步就提前结束（"没有发现需要处理的问题，到此结束"），从没走到交接这一步。诊断是行为描述噪音（工程日志33已发现的同一个问题，这是第二次独立撞见）：独立重新生成`write_and_save_one_with_check`的行为描述，每次可能强调不同的真实事实，噪音出在判断的输入材料上，不是判断本身坏了。

决定不再指望"再试一次运气好"，而是把"判断准不准"和"交接机制本身对不对"拆成两个独立问题——前者已经用consensus测量过（26%噪音，是已知的、量化过的特征），后者从没测过，值得单独隔离出来验证。

## 改动

`dialogue.py`新增`--test-handoff`调试入口：报告生成（复杂度、top_functions）照常真实跑一遍——这部分不受行为描述噪音影响，`_compare_before_after`需要一个真实的"before"基线，不能用`None`糊弄；但跳过容易受噪音影响的consensus+诊断这一步，直接把工程日志27/33已经验证过是真实、准确的诊断材料（`write_and_save_one_with_check`的cap_reached问题）喂给"要不要交给Claude Code处理"这一步。

## 真实撞见的bug：Windows下`subprocess.run(["claude", ...])`直接炸

第一次跑`--test-handoff`，走到`_invoke_claude_code`就崩了：

```
FileNotFoundError: [WinError 2] 系统找不到指定的文件。
```

原因：Windows上`claude`是npm全局安装生成的`claude.cmd`（批处理脚本包装），不是PE可执行文件。`subprocess.run`不带`shell=True`时走`CreateProcess`直接找可执行文件，根本不认`.cmd`，跟直接在终端敲`claude`（终端本身会用`cmd.exe`的PATHEXT规则去找）是两条不同的路。修复：`shell=(os.name == "nt")`，让Windows下这次调用也走cmd.exe解析PATHEXT，跟用户自己在终端敲命令行为一致。

## 交接机制本身：验证通过

修完bug再跑一次，Claude Code的会话真的接管了终端：
- 任务描述正确作为初始消息出现在Claude Code里（"读码机对这个项目做体检，发现以下确认的问题，请你处理..."）
- workspace trust确认框正常弹出，用户在Claude Code原生界面里确认

这是`dialogue.py`交接终端这条设计（工程日志36里"这一步一次都没有被真实跑过"）第一次被真实验证——机制本身是通的。

## 卡住的地方：Claude Code自己的登录，不是读码机的bug

交接之后，Claude Code报401无效令牌，反复重试。排查确认不是读码机的锅：

- `读码机/.env`只定义了`DEEPSEEK_API_KEY`，没有任何`ANTHROPIC_API_KEY`之类的键会通过`os.environ.setdefault`泄漏进`subprocess`的环境
- 当前shell里也没有游离的`ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN`

也就是说就算不经过读码机、直接在这个文件夹里手动敲`claude`，大概率会撞上同一个401——这是Claude Code客户端自己的登录凭证问题。用户尝试`/login`（会话内被打断）、`claude auth logout`+`claude auth login`（走到浏览器OAuth流程时报"OAuth error"，没有更详细的错误信息），都没修好，决定第二天再弄，暂时搁置。这条链路目前卡在：**交接机制已验证通过，但完整闭环（Claude Code真的执行修复→`_compare_before_after`看到变化）还没能跑通**，纯粹是账号登录问题挡住的，不是代码问题。

## 顺带查清楚的边界

用`claude --help`确认：`dialogue.py`的自动交接目前只能驱动终端CLI，没有暴露"唤起桌面版"或"接管已经开着的另一个窗口"的接口——`subprocess`开的是全新独立进程，绑定在`dialogue.py`所在的终端窗口本身，没有IPC通道伸进另一个已经在跑的Claude Code进程里。`-c/--continue`能接上"当前目录下最近一次对话"的磁盘记录，是最接近的现有机制，但不是真正的"复用已开着的窗口"。

## 还没做的

- 完整闭环（执行→改动前后对比）一次都没被真实验证过，等用户账号登录问题解决后补测。
- 用户提出一个有效但还没测的问题：项目没有README/文档、只有代码，`describe_project`生成的叙述质量会不会明显下降——从`sensor/agent.py`的system prompt读代码确认了"优先读README"是agent自己涌现的策略，不是硬编码进去的，理论上叙述第3条（不变量，判断真正用到的部分）受影响应该更小，但没有真实数据支撑，是下次可以直接做的一个便宜的对照测试。
