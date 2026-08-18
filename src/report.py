"""模块体检报告：把复杂度工具（Python走complexity.py/radon，其它语言走
lizard_complexity.py/lizard——两者验证过在Python上给出100%完全一致的数字，
工程日志13，是同一类可信的圈复杂度计算，不是"精确vs粗糙"两个不同量级的东西，
不需要分开处理）和behavior.py（LLM行为描述+证据核实）拼成一份完整报告——
不是发明新机制，是把已经分别验证过的工具接起来，一次调用产出一份人能直接看
的报告。

只对复杂度工具标出的"值得关注"的函数才跑行为描述——行为描述要调模型、还要
接一次verifier独立核实，比纯复杂度分析贵得多，不该对每一个琐碎函数都跑一遍，
那是浪费，也是"围栏只建在错误代价高的地方"这条原则（docs/03）的直接应用：
复杂度分析人人都测，行为描述只对真正复杂的部分测。
"""
import os

import complexity
import lizard_complexity
import behavior
import deepseek_client
import agent
import verifier

RANK_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
DESCRIBE_THRESHOLD = "B"  # 只对这个等级以上（含）的函数做行为描述，不区分来源工具

PROJECT_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".idea", ".pytest_cache", "venv", ".venv"}

PROJECT_NARRATIVE_TASK = (
    "给这个代码库写一份项目定位描述，这份描述以后会被当作参照标准，去判断"
    "'某个具体函数的行为，支不支撑这个项目正确运行'——不是写营销式的summary，"
    "要具体、要能被拿来对照检查：\n"
    "1. 这个项目是做什么的，面向什么场景/用户，解决什么问题。\n"
    "2. 主要由哪些模块/文件组成，各自的职责边界是什么。\n"
    "3. 项目正确运行时，关键的数据/状态应该保持什么样的不变量或流程——比如"
    "什么操作应该产生什么样的结果、什么状态转换是合法的、什么数据不该被覆盖或"
    "丢失。这一条是最重要的，因为后续要拿它去检查具体函数有没有违反。"
    "**每一条不变量必须写清楚证据范围**：具体是在哪个文件、哪个入口（比如某条"
    "HTTP路由、某个CLI命令分支）观察到这条规则被遵守的，不能只写\"删除操作\""
    "\"确认流程\"这种笼统说法。如果项目里同一类操作存在多个不同入口（比如同一种"
    "删除/生成动作，CLI和HTTP API各有一条独立路径），必须逐个检查每个入口是否"
    "都遵守同一条规则：都遵守就写清楚覆盖了哪几个入口；只在部分入口观察到，就"
    "必须明确指出规则只对这些入口成立、其它入口没有证据支持同一规则，不能把从"
    "一个入口归纳出的模式，不加说明地写成对全部同类入口都成立的通用规则——这是"
    "后续判断时最容易出的错，宁可把不变量的范围写窄、写具体，也不要写成看似"
    "适用全局、实际只验证过一个场景的空泛陈述。\n"
    "4. 设计上有什么突出的特点或明确的取舍。\n"
    "每一条尽量引用具体的文件/入口/关键函数作为依据，不要泛泛而谈。"
)


def describe_project(root: str, verbose: bool = True, explore_max_steps: int = None, verify_max_steps: int = 15) -> dict:
    """给整个项目生成一份定位描述——不是分析某个具体函数，是回答"这个项目
    整体是什么样子"这个问题，复用agent.py的读代码问答能力（跟describe_function
    是同一条生产线，只是问题从"这一个函数的契约是什么"换成"这整个项目的定位
    是什么"）。

    这份描述是"函数行为支不支撑项目"判断的参照标准——没有它，"支不支撑"这个
    问题问不出来，所以是新增行为评判机制的必要前置步骤，不是锦上添花。

    explore_max_steps不传就用agent.answer_question的默认预算（20，照小项目
    校准的）——项目文件数多的时候（比如几十个文件的模块）默认预算读不完，
    该由调用方显式加大，不是改agent.py的全局默认值去影响所有调用方。

    返回 {"narrative", "agent_steps", "agent_hit_cap", "verified",
    "verify_evidence", "verify_reasoning"}，跟describe_function的返回形状
    一致（只是"function"换成了整个项目本身，没有单独的function字段）。"""
    outcome = agent.answer_question(root, PROJECT_NARRATIVE_TASK, verbose=verbose, max_steps=explore_max_steps)
    # 项目叙述一次要核对十几条跨越多个文件的说法，verifier默认的4步（为单函数
    # 场景校准的）明显不够——真实测过，4步内只够读3个文件，远没读完就撞了
    # 上限。项目级叙述的核实预算要大得多，覆盖掉默认值。
    v = verifier.verify_answer(root, PROJECT_NARRATIVE_TASK, outcome["answer"], verbose=verbose, max_steps=verify_max_steps)
    return {
        "narrative": outcome["answer"],
        "agent_steps": len(outcome["steps"]),
        "agent_hit_cap": outcome["hit_cap"],
        "verified": v["verified"],
        "verify_evidence": v["evidence"],
        "verify_reasoning": v["reasoning"],
    }


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


def _measure_file(full_path: str, file_path: str):
    """按扩展名把文件分派给对应的复杂度工具。返回(raw, functions, tool)，
    tool是"radon"或"lizard"（哪个工具测的，只是溯源标记，不代表可信度差异）
    或None（不支持的扩展名）。两个工具返回的functions字段形状完全一致
    （{"name","type","complexity","rank","lineno"}），可以直接合并使用。"""
    if file_path.endswith(".py"):
        result = complexity.measure_file(full_path)
        return result["raw"], result["functions"], "radon"
    if file_path.endswith(lizard_complexity.LIZARD_EXTENSIONS):
        result = lizard_complexity.measure_file(full_path)
        return result["raw"], result["functions"], "lizard"
    return None, None, None


def generate_report(root: str, file_path: str, verbose: bool = True) -> dict:
    """对root下的file_path这一个文件生成完整体检报告。
    返回 {"file", "raw", "tool", "entries": [{"complexity_info", "behavior"}, ...]}，
    entries按复杂度从高到低排。扩展名不受支持时tool为None、entries为空——
    不报错，如实说明"这个文件类型不支持"。"""
    full_path = os.path.join(root, file_path)
    raw, functions, tool = _measure_file(full_path, file_path)
    if tool is None:
        return {"file": file_path, "raw": {}, "tool": None, "entries": []}

    threshold = RANK_ORDER[DESCRIBE_THRESHOLD]
    entries = []
    for f in functions:
        entry = {"complexity_info": f, "tool": tool, "behavior": None, "behavior_error": None}
        if RANK_ORDER.get(f["rank"], 0) >= threshold:
            if verbose:
                print(f"  正在描述 {f['name']}（复杂度{f['complexity']}，{f['rank']}级）...")
            try:
                entry["behavior"] = behavior.describe_function(root, file_path, f, verbose=False)
            except deepseek_client.ApiCallError as e:
                # 单个函数的行为描述失败（比如JSON重试耗尽，技术文档08 Bug#4，
                # 概率不是0），不该让批量报告（尤其是project_report要连续跑
                # 几十个函数）因为一次失败就整体崩掉、前面跑完的全部作废——
                # 记下失败原因，跳过这一个，继续处理剩下的函数。
                if verbose:
                    print(f"  {f['name']} 行为描述失败，跳过：{e}")
                entry["behavior_error"] = str(e)
        entries.append(entry)

    return {"file": file_path, "raw": raw, "tool": tool, "entries": entries}


def format_report(report: dict) -> str:
    """转成人能直接读的Markdown格式。"""
    lines = [f"# 模块体检报告：{report['file']}", ""]
    if report["tool"] is None:
        lines.append("（不支持的文件类型，跳过——只支持.py以及lizard覆盖的语言，见lizard_complexity.LIZARD_EXTENSIONS）")
        return "\n".join(lines)
    raw_desc = f"总行数{report['raw']['总行数']}"
    if "代码行数" in report["raw"]:
        raw_desc += f"，代码行数{report['raw']['代码行数']}"
    lines.append(raw_desc)
    lines.append("")

    if not report["entries"]:
        lines.append("（没有检测到函数/类）")
        return "\n".join(lines)

    for entry in report["entries"]:
        f = entry["complexity_info"]
        lines.append(f"## [{f['rank']}] {f['name']}（第{f['lineno']}行，复杂度{f['complexity']}）")
        lines.append("")
        if entry["behavior"] is None and entry.get("behavior_error") is not None:
            lines.append(f"（行为描述失败，跳过：{entry['behavior_error']}）")
        elif entry["behavior"] is None:
            lines.append(f"（复杂度低于{DESCRIBE_THRESHOLD}级，未生成行为描述）")
        else:
            b = entry["behavior"]
            lines.append(b["description"])
            lines.append("")
            mark = {"True": "✓ 核实通过", "False": "✗ 核实不通过", "None": "△ 未核实完"}[str(b["verified"])]
            lines.append(f"*{mark}——{b['verify_reasoning']}*")
        lines.append("")

    return "\n".join(lines)


def find_source_files(root: str) -> list:
    """递归找root下所有支持的源码文件（.py走complexity.py，lizard覆盖的其它
    语言走lizard_complexity.py），跳过常见的非源码目录，返回相对路径列表，
    按路径排序。"""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PROJECT_SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(".py") or filename.endswith(lizard_complexity.LIZARD_EXTENSIONS):
                full = os.path.join(dirpath, filename)
                results.append(os.path.relpath(full, root))
    return sorted(results)


def generate_project_report(
    root: str, file_paths: list = None, verbose: bool = True, with_narrative: bool = False,
) -> dict:
    """把很多个文件各自的体检报告（generate_report）汇总成一份项目级视图：
    整体规模、全项目按复杂度从高到低排序的函数榜单（跨文件、跨语言放在一起
    比——两个工具的数字是同一类可信的圈复杂度计算，合并比较不是制造虚假精确感，
    见模块说明）、以及所有被行为描述覆盖的函数明细。

    file_paths不传就自动找root下所有支持的源码文件。每个文件仍然复用
    generate_report——项目级汇总不是新的分析逻辑，只是把单文件报告的结果
    收集起来重新排序、分类，本身不重新读一遍代码。

    with_narrative=True时额外跑三段式设计的第一、三步（工程日志16/17）：
    生成项目叙述、拿每条行为描述对照叙述判断支不支撑，结果分别存进返回值的
    "narrative"、"judged_behaviors"两个键。默认False——describe_project本身
    是一次不便宜的多步agent调用（真实测过11-15步），不该在每次调用
    generate_project_report时都强制付这笔成本，只在真的需要这一层判断时
    显式开启。"""
    if file_paths is None:
        file_paths = find_source_files(root)

    file_reports = []
    for rel_path in file_paths:
        if verbose:
            print(f"正在分析 {rel_path} ...")
        file_reports.append(generate_report(root, rel_path, verbose=verbose))

    total_loc = 0
    rank_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    all_functions = []
    unsupported_files = []
    behavior_entries = []
    behavior_failures = []
    for r in file_reports:
        if r["tool"] is None:
            unsupported_files.append(r["file"])
            continue
        total_loc += r["raw"]["总行数"]
        for entry in r["entries"]:
            f = entry["complexity_info"]
            rank_counts[f["rank"]] = rank_counts.get(f["rank"], 0) + 1
            all_functions.append({"file": r["file"], "tool": r["tool"], **f})
            if entry["behavior"] is not None:
                behavior_entries.append({
                    "file": r["file"], "complexity_info": f, "behavior": entry["behavior"],
                })
            elif entry.get("behavior_error") is not None:
                behavior_failures.append({
                    "file": r["file"], "complexity_info": f, "error": entry["behavior_error"],
                })
    all_functions.sort(key=lambda x: x["complexity"], reverse=True)

    result = {
        "files": [r["file"] for r in file_reports if r["tool"] is not None],
        "unsupported_files": unsupported_files,
        "total_loc": total_loc,
        "rank_counts": rank_counts,
        "top_functions": all_functions,
        "behavior_entries": behavior_entries,
        "behavior_failures": behavior_failures,
        "file_reports": file_reports,
    }

    if with_narrative:
        if verbose:
            print("正在生成项目叙述...")
        narrative_result = describe_project(root, verbose=verbose)
        result["narrative"] = narrative_result
        if verbose:
            print("正在对照项目叙述判断每个函数的行为...")
        result["judged_behaviors"] = judge_project_against_narrative(
            result, narrative_result["narrative"], verbose=verbose,
        )

    return result


def format_project_report(project_report: dict, top_n: int = 15) -> str:
    """转成人能直接读的Markdown格式的项目级报告。

    有意把"项目叙述"和"行为vs叙述对照"放在复杂度数字前面——复杂度只是决定
    要不要花钱跑行为描述的入场券，不是报告里最该被优先看到的东西；真正
    该优先关注的是"哪些函数的行为违反了项目本该有的样子"，这一层判断该排
    在最前面，复杂度榜单降级成支撑细节（工程日志15的教训：复杂度排名对
    "这条建议该不该改"的预测力很弱，reachability/narrative对照才是）。"""
    p = project_report
    lines = ["# 项目体检报告", ""]
    lines.append(f"共{len(p['files'])}个文件（另有{len(p['unsupported_files'])}个不支持的文件类型被跳过），总行数{p['total_loc']}")
    lines.append("")

    if "narrative" in p:
        n = p["narrative"]
        mark = {"True": "✓ 核实通过", "False": "✗ 核实不通过", "None": "△ 未核实完"}[str(n["verified"])]
        lines.append(f"## 项目叙述（{mark}）")
        lines.append("")
        lines.append(n["narrative"])
        lines.append("")

    if "judged_behaviors" in p:
        lines.append(format_judgment_summary(p["judged_behaviors"]))
        lines.append("")

    lines.append("## 复杂度分级分布")
    lines.append("")
    for rank in ["A", "B", "C", "D", "E", "F"]:
        count = p["rank_counts"].get(rank, 0)
        if count:
            lines.append(f"- [{rank}] {count}个函数/类")
    lines.append("")

    lines.append(f"## 全项目复杂度榜单（前{top_n}，跨文件跨语言排序）")
    lines.append("")
    for f in p["top_functions"][:top_n]:
        lines.append(f"  [{f['rank']}] {f['file']} :: {f['name']}（第{f['lineno']}行）复杂度={f['complexity']}")
    lines.append("")

    lines.append(f"## 行为描述明细（{DESCRIBE_THRESHOLD}级以上，共{len(p['behavior_entries'])}个）")
    lines.append("")
    for entry in p["behavior_entries"]:
        f = entry["complexity_info"]
        b = entry["behavior"]
        lines.append(f"### [{f['rank']}] {entry['file']} :: {f['name']}（第{f['lineno']}行，复杂度{f['complexity']}）")
        lines.append("")
        lines.append(b["description"])
        lines.append("")
        mark = {"True": "✓ 核实通过", "False": "✗ 核实不通过", "None": "△ 未核实完"}[str(b["verified"])]
        lines.append(f"*{mark}——{b['verify_reasoning']}*")
        lines.append("")

    if p["behavior_failures"]:
        lines.append(f"## 行为描述失败（{len(p['behavior_failures'])}个，跳过未纳入上面明细）")
        lines.append("")
        for fail in p["behavior_failures"]:
            f = fail["complexity_info"]
            lines.append(f"- [{f['rank']}] {fail['file']} :: {f['name']}（第{f['lineno']}行）——{fail['error']}")
        lines.append("")

    return "\n".join(lines)


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


DIAGNOSIS_TASK_TEMPLATE = (
    "读码机的judge层判断，函数「{function_name}」（{file_path}）的行为违反了这个项目的"
    "一条不变量：\n{matched_invariant}\n\n"
    "判断依据：{reasoning}\n\n"
    "已核实的行为契约描述：\n{description}\n\n"
    "你的任务分三步：\n"
    "1. 用search_code找到这个函数的实际调用方，逐个读一遍确认——这个问题在正常调用路径下"
    "会不会真的被触发？有没有某个调用方已经做了防护（比如提前检查了某个状态、某个条件），"
    "让这个问题实际上不构成风险？这一步是judge层原来的分析完全没做过的——原来的行为描述"
    "只看这个函数自己，不看谁在调用它。\n"
    "2. 如果确认是真实、会被触发的问题，提出一个具体、最小化的修复方案——只针对这条具体"
    "违反给出改动建议，不要重新设计整个函数，尽量保留函数原有的设计意图（读一下函数的"
    "注释/docstring，如果某个行为是刻意的设计取舍，修复不该把它一起改掉，只该处理没被"
    "覆盖到的那部分）。\n"
    "3. 如果发现这个问题实际上不会被真实调用路径触发（比如所有调用方都已经做了防护），"
    "明确说明具体是哪个调用方、怎么防护的，不要为了给出结论就编一个不存在的修复。\n\n"
    "最后单独一行给结论：'结论：需要修复' 或 '结论：不需要修复（已被调用方防护）' 或"
    "'结论：有条件需要修复（说明具体条件）'。需要修复的话，给出具体怎么改，可以带示例"
    "代码片段——这只是给人看的建议，不会被自动应用，你没有写文件的能力。"
)


def diagnose_and_propose_fix(
    root: str, file_path: str, function_name: str, matched_invariant: str,
    reasoning: str, description: str, verbose: bool = True,
) -> dict:
    """给Tier1里一条"违反不变量"的发现做诊断——这是今晚两次真实闭环（工程日志22/23）
    里唯一没有被read码机自己的机制覆盖、完全靠人现读代码做的一步：判断这个问题在
    真实调用路径下会不会被触发、该怎么修。两次真实诊断都发现，关键信息是函数的
    "实际调用方"，而judge层现有的所有环节（复杂度、行为描述、叙述、判断）都只看
    被标记的这一个函数本身，从不看调用它的地方——这不是疏忽，是judge_behavior_
    against_narrative这类"喂现成文字进去、一次性推理"的机制形状决定的，调用方是谁
    要现查，不是提前能喂进prompt的静态材料。

    所以这个函数复用的不是判断层的机制，是agent.answer_question——跟"读代码回答
    问题"是同一条生产线，只是这次的问题是"这个已知的违反，在真实调用路径下成不成立、
    该怎么修"，不是从零探索一个开放问题。

    诊断本身也用verifier独立核实——它对调用方行为做了新的断言，这些断言没有被
    最初生成behavior_description时的核实覆盖过（那次核实只查了被标记的函数自己）。

    返回{"diagnosis","agent_steps","agent_hit_cap","verified","verify_evidence",
    "verify_reasoning"}。只产出诊断和建议——不写文件、不改代码，执行永远走人工
    审批下的协作，这条边界今晚两次真实闭环里都没有破例，这里也不例外。"""
    question = DIAGNOSIS_TASK_TEMPLATE.format(
        function_name=function_name, file_path=file_path,
        matched_invariant=matched_invariant, reasoning=reasoning, description=description,
    )
    outcome = agent.answer_question(root, question, verbose=verbose)
    v = verifier.verify_answer(root, question, outcome["answer"], verbose=verbose, max_steps=10)
    return {
        "diagnosis": outcome["answer"],
        "agent_steps": len(outcome["steps"]),
        "agent_hit_cap": outcome["hit_cap"],
        "verified": v["verified"],
        "verify_evidence": v["evidence"],
        "verify_reasoning": v["reasoning"],
    }
