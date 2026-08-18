"""迭代信号：把复杂度+行为判断合成成"该关注什么"，用词典序分层，不是
加权分数——功能违反是离散判断，复杂度是连续量，硬凑是范畴错误，而且
两者可靠性不是一个量级（复杂度零噪音，行为判断有噪音）。"""


def build_iteration_signal(project_report: dict, judgment_consensus: dict, min_agreement: float = 0.6) -> dict:
    """把"迭代信号该怎么定"这个问题的最终结论落成一个具体函数——不是把复杂度
    和行为判断加权合并成一个梯度式的单一分数，是分层（词典序优先级）：

    第一层（tier1）：consensus核实过的功能违反（undermine），复杂度不参与
    排序，不参与过滤。今晚反复验证过复杂度对"该不该优先改"预测力很弱
    （工程日志15：write_and_save_one_with_check复杂度只有7，但比复杂度27的
    offer_to_write更该优先修），把两者加权合并是范畴错误，不是精度问题——
    功能判断是离散的约束满足问题，复杂度是连续量，硬凑成一个数字会互相
    稀释，而且两者可靠性完全不是一个量级（复杂度零噪音，行为判断有26%
    的量出来的噪音，工程日志19），混在一起会让噪音污染到本来可靠的那部分。

    tier1内部再分两档：agreement_rate>=min_agreement的是"tier1_confirmed"
    （consensus里多数判断且够稳，可以相对有把握地采信）；min_agreement是
    今晚测出write_and_save_one_with_check恰好只有60%一致率、但仍是真实bug
    这个真实案例定的，不能把它当噪音直接丢掉。凡是在5次consensus里出现过
    至少1次undermine投票、但没达到多数或者一致率不够高的，归进
    "tier1_uncertain"——不是"没问题"，是"这次判断本身靠不住，需要人工另外
    核实"，不能被复杂度池悄悄吞掉。

    第二层（tier2）：完全没有出现过undermine投票的函数，才进入复杂度排序池，
    复杂度只在这一层起作用，且起的是"该往哪投入可维护性精力"这个独立作用，
    不跟tier1的优先级混算。"""
    complexity_map = {(f["file"], f["name"]): f for f in project_report["top_functions"]}

    tier1_confirmed = []
    tier1_uncertain = []
    tier2_pool = []

    for item in judgment_consensus["consensus"]:
        key = (item["file"], item["function"])
        f = complexity_map.get(key, {})
        undermine_votes = item["counts"].get("undermine", 0)
        entry = {
            "file": item["file"], "function": item["function"],
            "complexity": f.get("complexity"), "rank": f.get("rank"),
            "majority_verdict": item["majority_verdict"],
            "agreement_rate": item["agreement_rate"],
            "undermine_votes": undermine_votes, "total_runs": item["total_runs"],
        }
        if item["majority_verdict"] == "undermine" and item["agreement_rate"] >= min_agreement:
            tier1_confirmed.append(entry)
        elif undermine_votes > 0:
            tier1_uncertain.append(entry)
        else:
            tier2_pool.append(entry)

    tier1_confirmed.sort(key=lambda x: -x["agreement_rate"])
    tier1_uncertain.sort(key=lambda x: -x["undermine_votes"])
    tier2_pool.sort(key=lambda x: -(x["complexity"] or 0))

    return {
        "min_agreement": min_agreement,
        "tier1_confirmed": tier1_confirmed,
        "tier1_uncertain": tier1_uncertain,
        "tier2_by_complexity": tier2_pool,
    }


def format_iteration_signal(signal: dict) -> str:
    """把build_iteration_signal的结果转成人能直接读的Markdown——三层分开
    展示，不合并成一个排行榜，呈现方式本身就是在落实"不该做成梯度"这条
    结论。"""
    lines = ["# 迭代信号（分层优先级，不是加权分数）", ""]

    lines.append(f"## Tier 1 · 确认的功能违反（一致率≥{signal['min_agreement']:.0%}，{len(signal['tier1_confirmed'])}个）")
    lines.append("")
    lines.append("无条件排在最前面，复杂度不参与这一层的排序或过滤。")
    lines.append("")
    for e in signal["tier1_confirmed"]:
        lines.append(
            f"- **{e['file']} :: {e['function']}**（复杂度{e['complexity']}，"
            f"仅供参考不参与排序）—— 一致率{e['agreement_rate']:.0%}"
            f"（{e['undermine_votes']}/{e['total_runs']}次判定违反）"
        )
    lines.append("")

    lines.append(f"## Tier 1' · 不确定的功能违反（曾被判定违反但不够稳，{len(signal['tier1_uncertain'])}个）")
    lines.append("")
    lines.append("不代表没问题，代表这次判断本身靠不住——需要人工核实调用路径，不能被复杂度池悄悄吞掉。")
    lines.append("")
    for e in signal["tier1_uncertain"]:
        lines.append(
            f"- **{e['file']} :: {e['function']}** —— 多数判断{e['majority_verdict']}，"
            f"但{e['undermine_votes']}/{e['total_runs']}次判定违反，一致率{e['agreement_rate']:.0%}"
        )
    lines.append("")

    lines.append(f"## Tier 2 · 复杂度排序（从没出现过违反投票的函数，{len(signal['tier2_by_complexity'])}个）")
    lines.append("")
    lines.append("功能层面没有疑虑，复杂度在这一层单独起作用，指向「可维护性该往哪投入」，不代表优先级。")
    lines.append("")
    for e in signal["tier2_by_complexity"]:
        lines.append(f"  [{e['rank']}] {e['file']} :: {e['function']}  复杂度={e['complexity']}")

    return "\n".join(lines)
