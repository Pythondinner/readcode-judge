"""一致率测量与归纳：跨函数模式归纳（synthesize_project_report）、行为
判断的consensus测量（judge_project_against_narrative_consensus）、以及
改动前后对比（compare_judgment_consensus）——这一层测的是judge层自己的
可靠性（随机噪音有多大），不是代码本身对不对。"""
from sensor import deepseek_client
from .judgment import judge_project_against_narrative

SYNTHESIS_SYSTEM_PROMPT = """你会收到一份代码库体检报告的素材：每个函数的复杂度分级，以及
已经生成、并且经过独立verifier核实过的契约描述（含【调用方须知】）。这些材料里的事实性
描述都已经核实过了——你的任务不是重新判断代码对不对、不是重新分析代码，而是在这些
已确认的材料基础上做两件事：

1. 找出跨越多个函数的共同模式——不是简单复述每一条描述，是看这些独立的发现之间有没有
   共性（比如"多个函数都倾向于静默覆盖已有数据而不做校验/提示"这类项目级的设计倾向）。
   每个模式必须至少引用2个具体的函数（文件名+函数名）作为支撑证据，不能凭空归纳出材料
   里找不到支撑的模式。

2. 给出一份"优先处理清单"——如果只能挑几件事先做，挑哪几个、为什么。排序不能只看复杂度
   数字，要结合【调用方须知】里描述的风险严重程度一起判断（一个复杂度不算最高、但有严重
   静默副作用的函数，可能比一个复杂度最高但风险可控的函数更该优先关注）。

不要引入材料里没有的新论断，不要重新对代码下判断——你的输入本身已经是核实过的事实，你的
产出是对这些事实的归纳和排序，是二次加工，不是新的代码分析。找不到跨函数模式就如实说
"没有发现明显的跨函数模式"，不要为了凑数硬造。

只输出一个JSON对象，不要有任何其他文字，格式：
{"patterns": [{"name": "模式的简短名字", "evidence": ["file.py::func_name", ...], "summary": "归纳说明"}],
 "priority_list": [{"file": "file.py", "function": "func_name", "reason": "为什么排在这个优先级"}]}
patterns和priority_list里的顺序就是重要性顺序，最重要的排最前面。"""


def synthesize_project_report(project_report: dict, verbose: bool = True) -> dict:
    """把project_report里已经生成、已经核实过的很多条独立发现，喂给模型做一次
    归纳——找跨函数的共同模式、排出优先处理清单。不重新读代码、不重新验证，只是
    对已经确认的材料做二次加工（复杂度分析人人都测，行为描述只测复杂函数，这次
    汇总同理：不是免费的，只在已经有足够多独立发现时才值得做这一步）。

    返回结构化dict（{"patterns":[...], "priority_list":[...]}）而不是一段
    格式随意的文本——这样才能被synthesize_project_report_consensus程序化地
    比较多次独立调用的结果，不用靠人工去读文本对比。

    没有对合成结果做独立verifier核实——verifier.py核实的是"描述是否有代码原文
    支撑"，而这里的产出是对多条描述的归纳排序，不是新的代码事实断言，不是同一类
    可验证的东西；这是目前诚实的局限，不是遗漏。真正应对"这次归纳靠不靠谱"这个
    问题的机制是consensus（多次独立跑、看结论稳不稳定），不是逐条verifier式核实。"""
    p = project_report
    material_lines = [f"复杂度分级分布：{p['rank_counts']}", ""]
    material_lines.append("已核实的函数契约描述：")
    for entry in p["behavior_entries"]:
        f = entry["complexity_info"]
        b = entry["behavior"]
        material_lines.append(
            f"\n--- [{f['rank']}] {entry['file']} :: {f['name']}（复杂度{f['complexity']}，"
            f"verified={b['verified']}） ---\n{b['description']}"
        )
    if p["behavior_failures"]:
        material_lines.append(f"\n未能生成描述的函数（跳过，不构成材料）：{len(p['behavior_failures'])}个")

    if verbose:
        print(f"正在对{len(p['behavior_entries'])}条已核实的描述做跨函数归纳...")
    return deepseek_client.call(
        SYNTHESIS_SYSTEM_PROMPT, "\n".join(material_lines), temperature=0.3, json_mode=True,
    )


def format_synthesis(synthesis: dict) -> str:
    """把synthesize_project_report的结构化结果转成人能直接读的Markdown。"""
    lines = ["## 跨函数模式归纳", ""]
    for p in synthesis.get("patterns", []):
        lines.append(f"### {p['name']}")
        lines.append("")
        lines.append("**支撑证据：** " + "、".join(p.get("evidence", [])))
        lines.append("")
        lines.append(p.get("summary", ""))
        lines.append("")
    lines.append("## 优先处理清单")
    lines.append("")
    for i, item in enumerate(synthesis.get("priority_list", []), 1):
        lines.append(f"{i}. **{item['file']} :: {item['function']}** —— {item.get('reason', '')}")
    return "\n".join(lines)


def synthesize_project_report_consensus(project_report: dict, runs: int = 5, top_n: int = 5, verbose: bool = True) -> dict:
    """对同一份project_report独立跑多次synthesize_project_report，统计优先处理
    清单里每个函数的复现率——只对"优先处理清单"做程序化统计（结构是{file, function}
    这种可以直接算的东西），"跨函数模式"的措辞每次不完全一样，不好机械对比，原样
    保留每一轮的结果供人工比对，不强行合并。

    动机：项目级报告首次合成时，两次独立调用（材料略有不同）给出的优先级排序
    有明显出入，第1名两次一致、第2-5名洗牌——单次合成结果不能直接当成可信的
    完整排序，只有"多次都出现"这件事本身才是可信的信号（工程日志10）。"""
    all_syntheses = []
    tally = {}  # (file, function) -> 出现次数
    rank_sum = {}  # (file, function) -> 排名之和，用于算平均排名

    for i in range(runs):
        if verbose:
            print(f"第{i + 1}/{runs}次独立合成...")
        synthesis = synthesize_project_report(project_report, verbose=False)
        all_syntheses.append(synthesis)
        for rank, item in enumerate(synthesis.get("priority_list", [])[:top_n], 1):
            key = (item["file"], item["function"])
            tally[key] = tally.get(key, 0) + 1
            rank_sum[key] = rank_sum.get(key, 0) + rank

    consensus_ranking = [
        {
            "file": key[0], "function": key[1],
            "reproduced": count, "total_runs": runs,
            "reproduce_rate": count / runs,
            "avg_rank": rank_sum[key] / count,
        }
        for key, count in tally.items()
    ]
    consensus_ranking.sort(key=lambda x: (-x["reproduce_rate"], x["avg_rank"]))

    return {
        "runs": runs, "top_n": top_n,
        "consensus_ranking": consensus_ranking,
        "pattern_clusters": cluster_patterns_by_evidence(all_syntheses),
        "all_syntheses": all_syntheses,
    }


PATTERN_SIMILARITY_THRESHOLD = 0.4  # 启发式选的，不是从数据校准出来的——没有
                                     # "两个模式算不算同一个"的标准答案可以拿来
                                     # 校准，这是诚实的局限，不是精确值


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_patterns_by_evidence(all_syntheses: list) -> list:
    """把多次独立合成里的"跨函数模式"按证据集合（而不是措辞）聚类——模式的
    名字/归纳文字每次表达不完全一样（这是之前就观察到的问题，工程日志10），
    但如果两个模式指向同一组函数证据，说明识别到的是同一个真实模式，只是
    表达方式不同，不该因为文字对不上就被当成"没有复现"。

    用Jaccard相似度（两个证据集合的交集/并集）衡量接近程度，超过阈值就归
    为同一类——贪心单遍聚类（按运行顺序处理，遇到第一个足够相似的已有类
    就并进去，找不到就新开一类），不是全局最优聚类，处理顺序理论上会影响
    结果，这是诚实的局限，样本量小（几个模式、几次运行）时实际影响有限。"""
    clusters = []  # [{"evidence_union": set, "occurrences": [...]}]
    for run_idx, synthesis in enumerate(all_syntheses, 1):
        for pattern in synthesis.get("patterns", []):
            evidence = set(pattern.get("evidence", []))
            if not evidence:
                continue
            occurrence = {
                "run": run_idx, "name": pattern.get("name", ""),
                "summary": pattern.get("summary", ""), "evidence": sorted(evidence),
            }
            best_cluster, best_sim = None, 0.0
            for cluster in clusters:
                sim = _jaccard(evidence, cluster["evidence_union"])
                if sim > best_sim:
                    best_cluster, best_sim = cluster, sim
            if best_cluster is not None and best_sim >= PATTERN_SIMILARITY_THRESHOLD:
                best_cluster["evidence_union"] |= evidence
                best_cluster["occurrences"].append(occurrence)
            else:
                clusters.append({"evidence_union": set(evidence), "occurrences": [occurrence]})

    runs_total = len(all_syntheses)
    result = []
    for cluster in clusters:
        run_numbers = {occ["run"] for occ in cluster["occurrences"]}
        result.append({
            "evidence_union": sorted(cluster["evidence_union"]),
            "reproduced_runs": len(run_numbers),
            "total_runs": runs_total,
            "reproduce_rate": len(run_numbers) / runs_total,
            "occurrences": cluster["occurrences"],
        })
    result.sort(key=lambda c: -c["reproduce_rate"])
    return result


def format_consensus(consensus: dict) -> str:
    """把synthesize_project_report_consensus的结果转成人能直接读的Markdown。"""
    lines = [f"# 复现率统计（跑了{consensus['runs']}次独立合成）", ""]

    lines.append(f"## 优先处理清单复现率（各取前{consensus['top_n']}名）")
    lines.append("")
    for item in consensus["consensus_ranking"]:
        lines.append(
            f"- **{item['file']} :: {item['function']}** —— "
            f"{item['reproduced']}/{item['total_runs']}次进入前{consensus['top_n']}名"
            f"（复现率{item['reproduce_rate']:.0%}，平均排名第{item['avg_rank']:.1f}位）"
        )
    lines.append("")

    lines.append("## 跨函数模式复现率（按证据集合聚类，不按措辞文字）")
    lines.append("")
    for cluster in consensus["pattern_clusters"]:
        lines.append(
            f"- **{cluster['reproduced_runs']}/{cluster['total_runs']}次复现**"
            f"（{cluster['reproduce_rate']:.0%}）—— 证据集合：{'、'.join(cluster['evidence_union'])}"
        )
        for occ in cluster["occurrences"]:
            lines.append(f"  - 第{occ['run']}轮命名：「{occ['name']}」")
        lines.append("")

    lines.append("## 每一轮的原始结果（供人工核对聚类，未做机械合并）")
    lines.append("")
    for i, synthesis in enumerate(consensus["all_syntheses"], 1):
        lines.append(f"### 第{i}轮")
        lines.append("")
        lines.append(format_synthesis(synthesis))
        lines.append("")
    return "\n".join(lines)


def judge_project_against_narrative_consensus(
    project_report: dict, narrative: str, runs: int = 5, verbose: bool = True,
) -> dict:
    """对project_report里每一条行为描述，独立跑多次judge_behavior_against_narrative，
    统计verdict（support/undermine/unclear）的一致率——工程日志18意外撞见
    delete_draft两次判断给出不同结论后，这是第一次专门、系统地量化"这一层
    判断本身有多稳定"，不是碰运气撞见的。

    诚实的边界（不要被数字掩盖）：这测的是随机噪音，不是系统性偏差——如果模型
    对某类风险的判断标准本身有偏，5次都会一致地得出同一个错误结论，一致率
    照样是100%，跟"判断对了"是两回事。要排查系统性偏差，需要换一个不同的
    模型/不同的独立视角去核对，不是靠同一套机制多跑几次（这次先只测噪音这
    一层，边界写清楚，不假装解决了全部可靠性问题）。"""
    tally = {}  # (file, function) -> {"support": n, "undermine": n, "unclear": n}
    all_runs = []

    for i in range(runs):
        if verbose:
            print(f"第{i + 1}/{runs}次独立判断...")
        judged = judge_project_against_narrative(project_report, narrative, verbose=False)
        all_runs.append(judged)
        for j in judged:
            key = (j["file"], j["complexity_info"]["name"])
            verdict = j["judgment"].get("verdict", "unclear")
            counts = tally.setdefault(key, {"support": 0, "undermine": 0, "unclear": 0})
            counts[verdict] = counts.get(verdict, 0) + 1

    consensus = []
    for key, counts in tally.items():
        total = sum(counts.values())
        majority_verdict = max(counts, key=counts.get)
        consensus.append({
            "file": key[0], "function": key[1],
            "counts": counts, "total_runs": total,
            "majority_verdict": majority_verdict,
            "agreement_rate": counts[majority_verdict] / total,
        })
    consensus.sort(key=lambda x: x["agreement_rate"])  # 最不稳定的排最前面，最该关注

    return {"runs": runs, "consensus": consensus, "all_runs": all_runs}


def format_judgment_consensus(consensus: dict) -> str:
    """把judge_project_against_narrative_consensus的结果转成人能直接读的
    Markdown——按一致率从低到高排序，不稳定的判断排最前面，最该被人工复核。"""
    lines = [f"# 行为判断一致率统计（跑了{consensus['runs']}次独立判断，测的是随机噪音，不是判断对不对）", ""]
    for item in consensus["consensus"]:
        counts_str = "、".join(f"{k}={v}" for k, v in item["counts"].items() if v)
        flag = "" if item["agreement_rate"] == 1.0 else "  ⚠ 不稳定"
        lines.append(
            f"- **{item['file']} :: {item['function']}** —— 多数判断：{item['majority_verdict']}"
            f"（一致率{item['agreement_rate']:.0%}，{counts_str}）{flag}"
        )
    return "\n".join(lines)


def compare_judgment_consensus(before: dict, after: dict) -> list:
    """"动态追踪"最终被拆掉之后剩下的那一小块——不是自动化的持续追踪系统，
    是一个纯比较函数：给改动前、改动后各跑一次judge_project_against_narrative_consensus
    的结果，逐个函数对比多数判断变没变、稳定性变没变。不发起任何新的API调用，
    纯粹是对已有的两份consensus结果做数据比较。

    使用方式是工作纪律，不是自动生效的机制：必须在动手改代码之前主动跑一次
    consensus留底（"before"），改完再跑一次（"after"），两者都传进来这个
    函数才有意义——不会去翻git历史自动找"改动前"的版本，那需要对旧版本
    重新生成叙述和行为描述，成本和复杂度跳了一个量级，明确不做。

    返回列表，每项是{"file","function","before_verdict","after_verdict",
    "changed","before_agreement","after_agreement"}，只包含before/after
    都出现过的函数（改动新增或删除的函数不参与对比，没有"之前"或"之后"）。"""
    before_map = {(c["file"], c["function"]): c for c in before["consensus"]}
    after_map = {(c["file"], c["function"]): c for c in after["consensus"]}

    results = []
    for key in before_map.keys() & after_map.keys():
        b, a = before_map[key], after_map[key]
        results.append({
            "file": key[0], "function": key[1],
            "before_verdict": b["majority_verdict"], "after_verdict": a["majority_verdict"],
            "changed": b["majority_verdict"] != a["majority_verdict"],
            "before_agreement": b["agreement_rate"], "after_agreement": a["agreement_rate"],
        })
    results.sort(key=lambda x: (not x["changed"], x["file"], x["function"]))
    return results


def format_judgment_comparison(comparison: list) -> str:
    """把compare_judgment_consensus的结果转成人能直接读的Markdown，变化的
    排最前面。"""
    changed = [c for c in comparison if c["changed"]]
    unchanged = [c for c in comparison if not c["changed"]]

    lines = [f"# 改动前后的判断对比（共{len(comparison)}个函数，{len(changed)}个verdict变了）", ""]
    if changed:
        lines.append("## 判断变了")
        lines.append("")
        for c in changed:
            lines.append(
                f"- **{c['file']} :: {c['function']}** —— "
                f"{c['before_verdict']}（一致率{c['before_agreement']:.0%}） → "
                f"{c['after_verdict']}（一致率{c['after_agreement']:.0%}）"
            )
        lines.append("")
    if unchanged:
        lines.append(f"## 判断没变（{len(unchanged)}个，不展开）")
        lines.append("")
        lines.append("、".join(f"{c['file']}::{c['function']}" for c in unchanged))
        lines.append("")
    return "\n".join(lines)
