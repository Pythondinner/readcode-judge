"""决策层——但范围刻意划得很窄，只负责"接下来该自动跑哪些只读分析"，
不负责"要不要真的改代码"。

用户自己的Ledger+Observer+Brain+Executor(+Analysis)架构范式里，Brain
是做决策的那一层；读码机的定位从头到尾都是Observer+Analysis，不打算
长出Executor。这个模块是唯一的例外，但例外的范围被严格限定：它能做的
决策只有"对迭代信号里确认的发现，自动跑诊断"这一件事——把现在人工
"挑一条Tier1发现→手动跑diagnose_and_propose_fix"这个循环自动化成批量
操作，不多做任何一步。它的输出永远停在"诊断+修复建议"，不会更进一步
去决定要不要应用这个建议——那道关卡今晚被验证过不止一次必须留给人
（`offer_to_write`那次假阳性就是靠人工复核才被撤销的，不是任何自动
机制自己发现的）。

只对tier1_confirmed自动诊断，tier1_uncertain和tier2不碰：不确定的
判断本身不该被自动放大成行动，复杂度池里的函数没有功能层面的疑虑，
自动诊断没有意义，也是浪费。"""
from analysis import diagnosis


def _find_diagnosis_inputs(project_report: dict, judgment_consensus: dict, file: str, function: str) -> dict:
    """build_iteration_signal的输出本身只有复杂度和一致率这些统计量，不含
    diagnose_and_propose_fix需要的matched_invariant/reasoning/description——
    这些要回到project_report（找行为描述）和judgment_consensus的all_runs
    （找某一次给出undermine判断时的具体理由）里找。"""
    description = None
    for entry in project_report["behavior_entries"]:
        if entry["file"] == file and entry["complexity_info"]["name"] == function:
            description = entry["behavior"]["description"]
            break

    matched_invariant, reasoning = "", ""
    for run in judgment_consensus["all_runs"]:
        for item in run:
            if item["file"] == file and item["complexity_info"]["name"] == function:
                if item["judgment"].get("verdict") == "undermine":
                    matched_invariant = item["judgment"].get("matched_invariant", "")
                    reasoning = item["judgment"].get("reasoning", "")
        if matched_invariant:
            break

    return {"description": description, "matched_invariant": matched_invariant, "reasoning": reasoning}


def decide_and_diagnose(
    root: str, project_report: dict, judgment_consensus: dict, iteration_signal: dict, verbose: bool = True,
) -> list:
    """对迭代信号里所有tier1_confirmed发现自动跑诊断，返回
    [{"finding": ..., "diagnosis": ...}, ...]。找不到足够诊断材料的
    （理论上不该发生，tier1_confirmed本来就是从至少一次undermine判断
    来的，但材料缺失时如实跳过，不硬凑）会被跳过并在verbose模式下说明。"""
    results = []
    for finding in iteration_signal["tier1_confirmed"]:
        inputs = _find_diagnosis_inputs(project_report, judgment_consensus, finding["file"], finding["function"])
        if not inputs["description"] or not inputs["matched_invariant"]:
            if verbose:
                print(f"  跳过「{finding['file']} :: {finding['function']}」——找不到足够的诊断材料")
            continue
        if verbose:
            print(f"决策：对「{finding['file']} :: {finding['function']}」自动跑诊断...")
        diag = diagnosis.diagnose_and_propose_fix(
            root, finding["file"], finding["function"],
            inputs["matched_invariant"], inputs["reasoning"], inputs["description"],
            verbose=verbose,
        )
        results.append({"finding": finding, "diagnosis": diag})
    return results


def format_orchestration_result(results: list) -> str:
    """转成人能直接读的Markdown——每条诊断都带核实标记，方便一眼看出
    哪些结论可信度更高。"""
    if not results:
        return "# 自动诊断结果\n\n没有tier1_confirmed发现需要诊断（要么项目本身没问题，要么还没跑过consensus判断）。"

    lines = [f"# 自动诊断结果（{len(results)}条tier1_confirmed发现，已自动跑完诊断）", ""]
    lines.append("以下每一条都只是诊断+修复建议，不是已经应用的改动——要不要真的改，仍需人工确认。")
    lines.append("")
    for item in results:
        f = item["finding"]
        d = item["diagnosis"]
        mark = {True: "✓ 诊断已核实", False: "✗ 诊断未通过核实，建议人工再查一遍", None: "△ 核实未在预算内查完"}[d["verified"]]
        lines.append(f"## {f['file']} :: {f['function']}（一致率{f['agreement_rate']:.0%}，{mark}）")
        lines.append("")
        lines.append(d["diagnosis"])
        lines.append("")
    return "\n".join(lines)
