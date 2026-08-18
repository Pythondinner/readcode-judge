"""把judge层的能力（不是sensor层的文件访问）包成MCP工具，给外部有执行能力
的agent（Claude Code、deepseek harness）当信号源用——这是这次会话早前讨论过
的方向："判断层给出可靠信号，执行层外包给已经有agentic能力的大模型"。

跟mcp_server.py（暴露list_directory/read_file/search_code这几个sensor层
底层工具）是同一种包装方式，换成暴露judge层更高层的两个能力：

1. generate_project_report_tool：跑一遍完整体检（复杂度→行为描述→项目叙述→
   行为判断），返回排版好的Markdown——外部agent读这份报告就知道该关注哪些
   函数，不需要自己重新分析代码。
2. diagnose_and_propose_fix_tool：针对报告里标出的某条具体发现，深入去查
   实际调用方、判断真实不真实、给出最小化修复建议——外部agent确认要处理
   某条发现之后，可以再调这个工具拿到更具体的、能直接照着改的建议。

刻意只暴露这两个——不是judge层全部能力（consensus、迭代信号分层这些）都
接进来。理由：这次收敛复盘明确过"先验证一遍能跑通、别急着追求全覆盖"，
这两个工具已经能让外部agent走完"看报告→挑一个问题→拿修复建议"这条完整
路径，consensus/迭代信号留到这条路径真的被用起来之后再看要不要接。

不写文件、不改代码——跟judge层其它部分一样，只产出信号和建议，执行永远
是调用方（Claude Code/deepseek harness自己）的事，读码机不越界。

用法：跟mcp_server.py一样，通过环境变量READCODE_ROOT指定要分析的目标
代码库根目录，作为子进程用stdio协议启动。
"""
import os

from mcp.server.fastmcp import FastMCP

import report

ROOT = os.environ.get("READCODE_ROOT")
if not ROOT:
    raise SystemExit("必须设置环境变量READCODE_ROOT，指定要分析的目标代码库根目录")

server = FastMCP(
    name="读码机-judge",
    instructions=(
        "对一个指定代码库做体检：复杂度分析+行为契约核实+对照项目叙述判断"
        "支不支撑项目正确运行，产出人能直接读的报告；针对报告里某条具体发现，"
        "可以再深入诊断真实性、给出最小化修复建议。只读、只分析、不改代码。"
    ),
)


@server.tool()
def generate_project_report_tool(with_narrative: bool = True) -> str:
    """对READCODE_ROOT指定的代码库跑一遍完整体检（可能需要几分钟到二十几
    分钟，取决于代码库大小），返回排版好的Markdown报告——项目叙述+行为
    对照判断排在最前面（这才是决定"该关注什么"的部分），复杂度数字在后面
    （只是入场券，不是优先级依据）。with_narrative=False时跳过项目叙述和
    行为判断这两步，只返回复杂度+行为契约描述（更快，但看不出"支不支撑
    项目"这个判断）。"""
    project_report = report.generate_project_report(ROOT, with_narrative=with_narrative, verbose=False)
    return report.format_project_report(project_report)


@server.tool()
def diagnose_and_propose_fix_tool(
    file_path: str, function_name: str, matched_invariant: str, reasoning: str, description: str,
) -> str:
    """针对generate_project_report_tool报告里标出的一条"违反不变量"的具体
    发现，深入去查这个函数的实际调用方，判断在真实调用路径下会不会被
    触发、有没有已经被某个调用方防护住；如果确认是真实问题，给出具体、
    最小化的修复建议。参数直接对应报告里那条发现自带的字段：file_path
    （相对代码库根目录的文件路径）、function_name、matched_invariant
    （报告里写的"违反的不变量"）、reasoning（报告里写的"判断依据"）、
    description（这个函数的行为契约描述全文）。只产出诊断和建议文字，
    不写文件、不改代码。"""
    result = report.diagnose_and_propose_fix(
        ROOT, file_path, function_name, matched_invariant, reasoning, description, verbose=False,
    )
    verified_note = {
        True: "（诊断已通过独立核实：结论有代码原文支撑）",
        False: "（注意：诊断没有通过独立核实，下面的结论可能有不准确的地方，建议人工再核实一遍）",
        None: "（核实没有在预算步数内查完，不代表诊断错误，但也没有被独立确认）",
    }[result["verified"]]
    return f"{result['diagnosis']}\n\n---\n{verified_note}"


if __name__ == "__main__":
    server.run(transport="stdio")
