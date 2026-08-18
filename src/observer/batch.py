"""大项目分批分析：工程日志31撞见的真实问题——单次叙述生成天然只能覆盖
一部分文件，覆盖的文件数不会随项目变大等比例增长，导致"无法判断"比例
随规模暴涨。参考用户另一个项目"刑事阅卷Agent_Git"的设计（按内容量分批+
专门做一步跨批关联整合，不是简单分批就完事），把这个思路落到读码机上。

分批粒度：按root下的一级子目录分——每个含支持源码文件的子目录是一批，
根目录下直接躺着的文件（不在任何子目录里）单独归为一批。每批独立当成
一个"小项目"跑generate_project_report(with_narrative=True)，范围小，
单次探索预算的覆盖率天然更高（工程日志31的教训：core模块49个文件覆盖
不全，但它自己的每个子包只有几个到十几个文件，单独分析时的覆盖率应该
接近今晚测过的小项目水平）。

批次结果存进ledger（scope="batch:批次名"），再单独跑一次跨批关联整合——
这一步是关键，不是可选的锦上添花：单纯分批会把批次之间的关联切断
（比如子模块A的不变量实际上依赖子模块B保证的东西，各自的叙述都不知道
对方的存在），这是刑事阅卷Agent的设计里真正解决问题的那一步，不是"分批"
这两个字本身。"""
import os

from . import report as report_module
from . import lizard_complexity
from sensor import deepseek_client
from ledger import store


def find_batches(root: str) -> dict:
    """把root下的一级子目录当成批次边界，返回{批次名: 对应目录路径}。
    根目录下直接躺着的支持文件（不在任何子目录里）单独归为一批，
    批次名固定叫"_root"。子目录本身可能有更深的嵌套，但批次粒度就停在
    一级，不递归再拆——今晚测试用的deepseek-harness/packages/core正好是
    这个粒度（7个子包），进一步细分留到真的需要时再看，不是现在就要
    解决的问题。"""
    batches = {}
    direct_files = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if entry in report_module.PROJECT_SKIP_DIRS:
            continue
        if os.path.isdir(full):
            sub_files = report_module.find_source_files(full)
            if sub_files:
                batches[entry] = full
        elif entry.endswith(".py") or entry.endswith(lizard_complexity.LIZARD_EXTENSIONS):
            direct_files.append(entry)
    if direct_files:
        batches["_root"] = root
    return batches, direct_files


CROSS_BATCH_SYSTEM_PROMPT = """你会收到同一个大项目按子模块分别生成的多份项目叙述——
每份叙述只覆盖了这个项目的一个子模块，生成时不知道其它子模块的存在，也不知道
其它叙述里写了什么。

你的任务不是重新读代码，是在这些已有叙述文本的基础上，找出容易被"分开看"这件事
本身漏掉的东西：

1. 跨批次关联的不变量——有没有哪条规则，实际上是靠多个子模块合作保证的（比如
   子模块A的叙述提到"某个ID必须唯一"，但保证唯一性的代码其实在子模块B里，
   子模块A自己的叙述看不到这一层），单独看任何一份叙述都发现不了，只有对照
   多份叙述才能看出这种依赖关系。
2. 潜在的责任空白——有没有哪类关注点，在所有子模块的叙述里都没有明确的归属，
   可能双方都以为对方负责、实际上没有代码真的在管这件事。

只基于给你的这些叙述文本做归纳和交叉对照，不要重新对代码下判断、不要编造
叙述文本里没有依据的具体不变量——找不到跨批关联就如实说"没有发现明显的
跨批次关联"，不要为了凑数硬造。

只输出一个JSON对象：
{"cross_batch_invariants": [{"description": "关联的不变量是什么", "involved_batches": ["批次名", ...], "evidence": "从哪几份叙述的哪些描述里看出这个关联"}],
 "responsibility_gaps": [{"concern": "什么关注点看起来没人负责", "reasoning": "为什么怀疑是空白"}]}"""


def cross_batch_integration(batch_narratives: dict, verbose: bool = True) -> dict:
    """对多个批次已经生成的项目叙述做一次跨批关联整合——二次加工，不重新
    读代码，跟synthesize_project_report"不做新代码分析"是同一个原则。"""
    material = "\n\n".join(
        f"=== 子模块「{name}」的叙述 ===\n{text}" for name, text in batch_narratives.items()
    )
    if verbose:
        print(f"正在对{len(batch_narratives)}个批次的叙述做跨批关联整合...")
    return deepseek_client.call(CROSS_BATCH_SYSTEM_PROMPT, material, temperature=0.3, json_mode=True)


def run_batch_analysis(root: str, verbose: bool = True) -> dict:
    """大项目分批分析的完整入口：分批→每批独立跑narrative+judgment→存进
    ledger→跨批关联整合。返回{"batches": {批次名: project_report}, "integration": ...}。

    每批用默认的探索/核实步数预算（不像core那次整体分析要手动调大）——
    这正是分批要解决的问题：每批范围小，默认预算应该就够，不需要像
    core那次一样把预算翻倍还只能覆盖一部分。"""
    batches, direct_files = find_batches(root)
    if not batches:
        raise ValueError(f"{root} 下没有找到任何支持的源码文件，无法分批")

    results = {}
    for name, path in batches.items():
        if verbose:
            print(f"\n=== 分析批次「{name}」（{path}）===")
        if name == "_root":
            pr = report_module.generate_project_report(
                root, file_paths=direct_files, with_narrative=True, verbose=verbose,
            )
        else:
            pr = report_module.generate_project_report(path, with_narrative=True, verbose=verbose)
        results[name] = pr
        store.save_artifact(root, f"batch:{name}", pr)
        if verbose:
            unclear = sum(1 for j in pr.get("judged_behaviors", []) if j["judgment"].get("verdict") == "unclear")
            total = len(pr.get("judged_behaviors", []))
            print(f"  批次「{name}」：{total}个函数判断，{unclear}个无法判断"
                  f"（{unclear/total:.0%}）" if total else f"  批次「{name}」：没有函数触发判断")

    batch_narratives = {
        name: pr["narrative"]["narrative"] for name, pr in results.items() if "narrative" in pr
    }
    integration = cross_batch_integration(batch_narratives, verbose=verbose)
    store.save_artifact(root, "batch_integration", integration)

    return {"batches": results, "integration": integration}


def format_batch_analysis(result: dict) -> str:
    """把run_batch_analysis的结果转成人能直接读的Markdown。"""
    lines = ["# 分批分析报告", ""]
    lines.append(f"共{len(result['batches'])}个批次")
    lines.append("")

    lines.append("## 跨批关联整合")
    lines.append("")
    integration = result["integration"]
    cross_invariants = integration.get("cross_batch_invariants", [])
    if cross_invariants:
        lines.append(f"### 跨批次关联的不变量（{len(cross_invariants)}个）")
        lines.append("")
        for item in cross_invariants:
            lines.append(f"- **{item['description']}**")
            lines.append(f"  - 涉及批次：{'、'.join(item.get('involved_batches', []))}")
            lines.append(f"  - 依据：{item.get('evidence', '')}")
        lines.append("")
    else:
        lines.append("没有发现明显的跨批次关联。")
        lines.append("")

    gaps = integration.get("responsibility_gaps", [])
    if gaps:
        lines.append(f"### 潜在的责任空白（{len(gaps)}个）")
        lines.append("")
        for item in gaps:
            lines.append(f"- **{item['concern']}** —— {item.get('reasoning', '')}")
        lines.append("")

    lines.append("## 各批次明细")
    lines.append("")
    for name, pr in result["batches"].items():
        lines.append(f"### 批次「{name}」")
        lines.append("")
        lines.append(report_module.format_project_report(pr))
        lines.append("")

    return "\n".join(lines)
