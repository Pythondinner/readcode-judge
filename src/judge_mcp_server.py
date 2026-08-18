"""把judge层的能力（不是sensor层的文件访问）包成MCP工具，给外部有执行能力
的agent（Claude Code、deepseek harness）当信号源用——这是这次会话早前讨论过
的方向："判断层给出可靠信号，执行层外包给已经有agentic能力的大模型"。

跟mcp_server.py（暴露list_directory/read_file/search_code这几个sensor层
底层工具）是同一种包装方式，换成暴露judge层更高层的能力：

1. generate_project_report_tool：跑一遍完整体检（复杂度→行为描述→项目叙述→
   行为判断），返回排版好的Markdown——外部agent读这份报告就知道该关注哪些
   函数，不需要自己重新分析代码。
2. diagnose_and_propose_fix_tool：针对报告里标出的某条具体发现，深入去查
   实际调用方、判断真实不真实、给出最小化修复建议——外部agent确认要处理
   某条发现之后，可以再调这个工具拿到更具体的、能直接照着改的建议。
3. run_batch_analysis_tool：给大项目（单次叙述覆盖不全的规模，工程日志31/34
   验证过）用的——按子模块分批分析+跨批关联整合，覆盖率比单次整体分析高
   得多。
4. auto_diagnose_confirmed_findings_tool：完整跑一遍判断→consensus→迭代
   信号→对所有confirmed发现自动诊断，一次调用拿到"确认的问题+诊断建议"
   汇总，不用外部agent自己维护中间状态、分好几次调用传JSON。

每个工具都是自包含的完整流程（不需要外部agent在多次调用之间传递复杂的
中间数据结构），跟generate_project_report_tool已有的设计是同一个思路。

不写文件、不改代码——跟judge层其它部分一样，只产出信号和建议，执行永远
是调用方（Claude Code/deepseek harness自己）的事，读码机不越界。决策层
（brain.orchestrate）能做的也只是"自动决定诊断哪些发现"，不能决定"要不要
应用修复"，这条线没有因为接上MCP就松动。

用法：跟mcp_server.py一样，通过环境变量READCODE_ROOT指定要分析的目标
代码库根目录，作为子进程用stdio协议启动。
"""
import os

from mcp.server.fastmcp import FastMCP

from observer import report
from observer import batch as batch_module
from observer import consensus as consensus_module
from observer import iteration_signal as signal_module
from analysis import diagnosis
from brain import orchestrate

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
    result = diagnosis.diagnose_and_propose_fix(
        ROOT, file_path, function_name, matched_invariant, reasoning, description, verbose=False,
    )
    verified_note = {
        True: "（诊断已通过独立核实：结论有代码原文支撑）",
        False: "（注意：诊断没有通过独立核实，下面的结论可能有不准确的地方，建议人工再核实一遍）",
        None: "（核实没有在预算步数内查完，不代表诊断错误，但也没有被独立确认）",
    }[result["verified"]]
    return f"{result['diagnosis']}\n\n---\n{verified_note}"


@server.tool()
def run_batch_analysis_tool() -> str:
    """给大项目用的体检——READCODE_ROOT指定的代码库按一级子目录分批，
    每批独立跑复杂度+行为描述+项目叙述+行为判断（范围小，覆盖率天然更高，
    工程日志31/34真实验证过：单次整体分析对49文件86函数的项目只能覆盖
    43%，分批后覆盖率提到81%），再跑一步跨批关联整合，找批次之间容易被
    分开分析漏掉的关联（比如某条规则由A子模块强制、但实际实现路径在B
    子模块）。可能需要十几分钟到更久，取决于代码库大小和批次数量——比
    generate_project_report_tool更贵，只在代码库大到"无法判断"比例明显
    偏高时才该用这个，不是默认选项。"""
    result = batch_module.run_batch_analysis(ROOT, verbose=False)
    return batch_module.format_batch_analysis(result)


@server.tool()
def auto_diagnose_confirmed_findings_tool(consensus_runs: int = 5) -> str:
    """完整跑一遍judge层的判断链路：生成项目叙述→对每个函数的行为判断跑
    consensus（默认5次独立判断，测一致率）→构建迭代信号→对一致率达标、
    确认违反不变量的发现（tier1_confirmed）自动逐个跑诊断，一次调用直接
    拿到"确认的问题+每条的诊断和修复建议"汇总，不需要你自己维护判断结果、
    consensus数据这些中间状态、分好几次调用来回传。

    这是决策层（brain.orchestrate）能做的全部——只自动决定"诊断哪些发现"，
    不会、也不能决定"要不要应用某条修复"，那始终是你自己的决定；这个工具
    只产出诊断建议文字，不写文件、不改代码。consensus_runs调小能省时间但
    一致率的参考价值会降低（默认5次是今晚测出来的、既能反映真实噪音水平
    又不会跑太久的折中）。"""
    project_report = report.generate_project_report(ROOT, with_narrative=True, verbose=False)
    judgment_consensus = consensus_module.judge_project_against_narrative_consensus(
        project_report, project_report["narrative"]["narrative"], runs=consensus_runs, verbose=False,
    )
    signal = signal_module.build_iteration_signal(project_report, judgment_consensus)
    results = orchestrate.decide_and_diagnose(ROOT, project_report, judgment_consensus, signal, verbose=False)
    return orchestrate.format_orchestration_result(results)


if __name__ == "__main__":
    server.run(transport="stdio")
