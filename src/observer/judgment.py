"""行为对照叙述判断：把一个函数已经生成、已经核实过的行为描述，对照
narrative.py产出的项目叙述，判断支不支撑项目正确运行。三段式设计
（工程日志16）的第三步：项目叙述提供标准，行为描述提供事实，这一步
做对照检查。"""
from sensor import deepseek_client

SUPPORT_JUDGMENT_SYSTEM_PROMPT = """你会收到两份材料：一份是某个项目的定位描述（包含
这个项目正确运行时该保持的关键不变量），一份是这个项目里某个具体函数的行为契约描述
（已经过独立verifier核实，事实真实可信，不用怀疑其真实性）。

你的任务：判断这个函数的行为，支不支撑项目按照定位描述里的方式正确运行——不是判断
"这段代码写得好不好"、不是重新评估复杂度，是对照定位描述里列出的具体不变量逐条检查，
这个函数的行为有没有违反、削弱、或者悄悄绕过其中任何一条。

给出三选一的判断：
- "support"：这个函数的行为没有违反任何列出的不变量，符合项目定位描述里的预期——
  到此为止，不用再深挖，不用给出理由长篇大论。
- "undermine"：这个函数的行为违反或削弱了至少一条具体的不变量——必须指出具体是
  哪一条（引用或改写定位描述里的原文），以及行为描述里的哪个具体细节构成了违反。
- "unclear"：行为描述本身没有覆盖到任何一条不变量相关的细节，材料不足以判断——
  不要在这种情况下凭空猜测项目定位描述里没写清楚的标准。

只输出一个JSON对象，不要有任何其他文字：
{"verdict": "support"|"undermine"|"unclear",
 "matched_invariant": "如果是undermine，这里写具体违反的是哪条不变量；否则留空字符串",
 "reasoning": "一到两句话说明判断依据，必须引用行为描述里的具体内容"}"""


def judge_behavior_against_narrative(narrative: str, function_info: dict, behavior_description: str, verbose: bool = True) -> dict:
    """把一个函数已经生成、已经核实过的行为描述，对照项目叙述里的不变量，判断
    支不支撑项目正确运行——不重新读代码，是对两份已有材料做判断，跟
    synthesize_project_report"二次加工、不做新代码分析"是同一个原则。

    这是三段式设计（工程日志16）的第三步：项目叙述提供标准，行为描述提供事实，
    这一步做对照检查。返回的verdict只有"support"才该被当作"到此为止，不用
    再追问"；"undermine"和"unclear"都该被report.py当作值得关注、纳入后续
    优先级判断的对象。"""
    user_content = (
        f"项目定位描述（含关键不变量）：\n{narrative}\n\n"
        f"---\n\n"
        f"函数「{function_info['name']}」（{function_info.get('rank', '?')}级，"
        f"复杂度{function_info.get('complexity', '?')}）的行为契约描述：\n{behavior_description}"
    )
    if verbose:
        print(f"  正在对照项目叙述判断 {function_info['name']} 的行为...")
    return deepseek_client.call(
        SUPPORT_JUDGMENT_SYSTEM_PROMPT, user_content, temperature=0.2, json_mode=True,
    )


def judge_project_against_narrative(project_report: dict, narrative: str, verbose: bool = True) -> list:
    """对project_report里每一条已经生成、已经核实过的行为描述，逐个对照项目
    叙述判断支不支撑项目正确运行。返回列表，每项是
    {"file", "complexity_info", "behavior", "judgment"}。"""
    results = []
    for entry in project_report["behavior_entries"]:
        f = entry["complexity_info"]
        if verbose:
            print(f"  正在对照项目叙述判断 {entry['file']} :: {f['name']}...")
        judgment = judge_behavior_against_narrative(
            narrative, f, entry["behavior"]["description"], verbose=False,
        )
        results.append({
            "file": entry["file"], "complexity_info": f,
            "behavior": entry["behavior"], "judgment": judgment,
        })
    return results


def format_judgment_summary(judged: list) -> str:
    """转成人能直接读的Markdown——三档待遇刻意不同：undermine展开证据，
    unclear单独成节并显式提醒"不代表没问题"，support只列名字不展开（"到此
    为止，不再追问"落实成报告篇幅上的差异对待，不是嘴上说说）。用##而不是#
    起标题——这份内容常常被generate_project_report(with_narrative=True)
    拼进更大的项目报告里，标题层级要能正确嵌套，不能跟外层的#标题打架。"""
    undermine = [j for j in judged if j["judgment"].get("verdict") == "undermine"]
    unclear = [j for j in judged if j["judgment"].get("verdict") == "unclear"]
    support = [j for j in judged if j["judgment"].get("verdict") == "support"]

    lines = ["## 行为 vs 项目叙述 对照结果", ""]
    lines.append(
        f"共{len(judged)}个函数：{len(undermine)}个违反不变量、"
        f"{len(unclear)}个无法判断、{len(support)}个支撑项目正确运行（不再展开）"
    )
    lines.append("")

    if undermine:
        lines.append(f"### 违反不变量（{len(undermine)}个，值得优先关注）")
        lines.append("")
        for j in undermine:
            f = j["complexity_info"]
            v = j["judgment"]
            lines.append(f"**{j['file']} :: {f['name']}**")
            lines.append(f"- 违反的不变量：{v.get('matched_invariant', '')}")
            lines.append(f"- 判断依据：{v.get('reasoning', '')}")
            lines.append("")

    if unclear:
        lines.append(f"### 无法判断（{len(unclear)}个——不代表没问题，只是材料不够判断，值得人工看一眼）")
        lines.append("")
        for j in unclear:
            f = j["complexity_info"]
            lines.append(f"- {j['file']} :: {f['name']} —— {j['judgment'].get('reasoning', '')}")
        lines.append("")

    if support:
        lines.append(f"### 支撑项目正确运行（{len(support)}个，不再展开）")
        lines.append("")
        lines.append("、".join(f"{j['file']}::{j['complexity_info']['name']}" for j in support))
        lines.append("")

    return "\n".join(lines)
