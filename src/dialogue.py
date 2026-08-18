"""读码机自己的对话框——不再是被Claude Code/deepseek harness当成工具调用的
MCP server，是读码机自己主动的入口：问文件夹路径→自动分析→出报告→（有
确认发现）自动诊断→问要不要交给Claude Code处理→把诊断当任务描述，把
终端交接给Claude Code的正常交互会话（不是非交互的-p模式）——执行权限的
确认，用的是Claude Code自己原生的交互确认机制，读码机不实现、也不该
实现一个能代替用户按"确认"的机制。这条边界是"半自动，等准确率高了就
自动化"这个想法被明确否定之后定下的：该不该自动化按这次改动的风险/
可逆性判断，不按判断层自称多有把握判断（详见标准记忆
readcode-machine-automation-philosophy）。

Claude Code会话结束、控制权交回来之后，自动重新体检一遍，跟改之前的
报告对比，把"这次改动前后的变化"直接展示出来——确认的对象应该是"结果"
（改前改后对比、判断变没变），不是"代码diff细节"，降低确认这道关卡
需要的专业门槛。

用法：
    python dialogue.py
"""
import os
import subprocess

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from observer import report as report_module
from observer import batch as batch_module
from observer import consensus as consensus_module
from observer import iteration_signal as signal_module
from brain import orchestrate
from ledger import store

BATCH_THRESHOLD_FILES = 25  # 超过这个文件数就用批分析，不是单次整体分析——工程
                             # 日志31/34测出单次分析在40+文件规模下覆盖率会明显
                             # 下降；这个阈值是照那次真实数据（9-13文件的项目单次
                             # 分析没问题，49文件的core覆盖率掉到43%）定的粗略
                             # 门槛，不是精确校准过的科学数字，以后有更多样本再调。


def _run_analysis(root: str):
    """自动判断该用单次分析还是批分析，返回(结果, is_batch)。"""
    file_count = len(report_module.find_source_files(root))
    if file_count > BATCH_THRESHOLD_FILES:
        print(f"（{file_count}个文件，规模较大，用分批分析——工程日志31/34验证过这样覆盖率更高）")
        return batch_module.run_batch_analysis(root, verbose=True), True
    return report_module.generate_project_report(root, with_narrative=True, verbose=True), False


def _format_report(result, is_batch: bool) -> str:
    if is_batch:
        return batch_module.format_batch_analysis(result)
    return report_module.format_project_report(result)


def _get_diagnosis_text(root: str, pr: dict):
    """对单次分析结果跑consensus+迭代信号+决策层自动诊断，返回诊断文本，
    没有确认的发现就返回None。批分析场景目前还没跟consensus/决策层打通，
    只对单次分析场景做这一步——是明确的、还没做的缺口，不是忘了。"""
    if "narrative" not in pr:
        return None
    print("\n正在测一下这些判断稳不稳定（跑5次consensus）...")
    judgment_consensus = consensus_module.judge_project_against_narrative_consensus(
        pr, pr["narrative"]["narrative"], runs=5, verbose=True,
    )
    signal = signal_module.build_iteration_signal(pr, judgment_consensus)
    if not signal["tier1_confirmed"]:
        return None
    print(f"\n发现{len(signal['tier1_confirmed'])}条确认的问题，自动跑诊断...")
    results = orchestrate.decide_and_diagnose(root, pr, judgment_consensus, signal, verbose=True)
    return orchestrate.format_orchestration_result(results)


def _invoke_claude_code(root: str, task_description: str) -> None:
    """把诊断结果当任务描述，交接终端给Claude Code的正常交互会话（不是
    -p非交互模式）——要让Claude Code自己原生的权限确认机制接管"要不要
    真的执行"这个决定。子进程不重定向stdio，终端控制权真的交出去，用户
    能直接跟Claude Code对话，它退出后控制权自然交回这个脚本。"""
    print("\n" + "=" * 60)
    print("交给Claude Code处理——接下来是Claude Code的会话，读码机退到后台")
    print("=" * 60 + "\n")
    subprocess.run(["claude", task_description], cwd=root)
    print("\n" + "=" * 60)
    print("Claude Code会话结束，读码机接回来")
    print("=" * 60)


def _compare_before_after(root: str, before_result, before_is_batch: bool) -> None:
    """Claude Code执行完之后，自动重新分析一遍，跟执行前的结果对比——
    确认的对象是"结果"不是"代码"：这次改动前后，问题变多了还是变少了、
    复杂度涨了还是降了，这些不需要读代码就能判断。"""
    print("\n正在重新体检，看看这次改动的效果...")
    after_result, after_is_batch = _run_analysis(root)

    if before_is_batch or after_is_batch:
        print("\n（分批分析结果目前还没有专门的前后对比函数——已知缺口，不是忘了）")
        print("\n=== 改动前 ===")
        print(_format_report(before_result, before_is_batch)[:1500])
        print("\n=== 改动后 ===")
        print(_format_report(after_result, after_is_batch)[:1500])
        return

    old_verdict = store.verdict_map(before_result)
    new_verdict = store.verdict_map(after_result)
    changes = store.diff_verdict(old_verdict, new_verdict)
    old_complexity = store.complexity_map(before_result)
    new_complexity = store.complexity_map(after_result)
    complexity_changes = store.diff_complexity(old_complexity, new_complexity)

    print("\n=== 这次改动前后对比 ===")
    if changes:
        print(f"判断结果变化的函数（{len(changes)}个）：")
        for key, old_v, new_v in changes:
            marker = "  ✓ 变好了" if old_v == "undermine" and new_v == "support" else ""
            print(f"  {key}: {old_v} → {new_v}{marker}")
    else:
        print("判断结果没有变化。")
    if complexity_changes:
        print(f"\n复杂度变化的函数（{len(complexity_changes)}个）：")
        for key, old_c, new_c, direction in complexity_changes:
            print(f"  {key}: {old_c} → {new_c}（{direction}）")
    else:
        print("复杂度没有变化。")


def run() -> None:
    print("=== 读码机 ===")
    print("给一个项目文件夹路径，我帮你做体检、找问题，需要的话交给Claude Code处理。\n")

    root = input("项目文件夹路径：").strip()
    if not os.path.isdir(root):
        print(f"找不到目录：{root}")
        return
    root = os.path.abspath(root)

    result, is_batch = _run_analysis(root)
    print("\n" + "=" * 60)
    print(_format_report(result, is_batch))

    if is_batch:
        print("\n（分批分析目前还没跟自动诊断打通——确认的发现要自己看报告里的跨批整合"
              "部分，还不能自动跑diagnose，是已知的、明确的缺口）")
        return

    diagnosis_text = _get_diagnosis_text(root, result)
    if diagnosis_text is None:
        print("\n没有发现需要处理的问题，到此结束。")
        return

    print("\n" + "=" * 60)
    print(diagnosis_text)

    choice = input("\n要交给Claude Code处理吗？输入 是 确认，其他任意键跳过：").strip()
    if choice != "是":
        print("好，不处理，到此结束。")
        return

    task_description = (
        "读码机对这个项目做体检，发现以下确认的问题，请你处理（是否真的执行改动，"
        "由你自己的确认流程决定，我这边不会替你确认）：\n\n" + diagnosis_text
    )
    _invoke_claude_code(root, task_description)
    _compare_before_after(root, result, is_batch)


if __name__ == "__main__":
    run()
