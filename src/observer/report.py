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

这是observer这条线的编排入口——本身不做判断，是把complexity/behavior/
narrative/judgment这几个各自独立验证过的部件串成一份报告。"""
import os
from concurrent.futures import ThreadPoolExecutor

from . import complexity
from . import lizard_complexity
from . import behavior
from . import narrative
from . import judgment
from sensor import deepseek_client

DEFAULT_MAX_WORKERS = 3  # 并发数——每个调用都是等网络的I/O，不是等CPU，线程池够用，
                          # 不需要重写成异步。数字选得保守，是因为不知道DeepSeek API
                          # 实际的并发限速是多少，批分析场景下这层并发还会跟批次级
                          # 并发叠加（真实测过core那次，8批次×文件级并发，叠起来的
                          # 并发请求数不小），宁可先保守，撞到限流再往上调，不要一
                          # 上来就设得很激进。

RANK_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
DESCRIBE_THRESHOLD = "B"  # 只对这个等级以上（含）的函数做行为描述，不区分来源工具

PROJECT_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".idea", ".pytest_cache", "venv", ".venv"}


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
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict:
    """把很多个文件各自的体检报告（generate_report）汇总成一份项目级视图：
    整体规模、全项目按复杂度从高到低排序的函数榜单（跨文件、跨语言放在一起
    比——两个工具的数字是同一类可信的圈复杂度计算，合并比较不是制造虚假精确感，
    见模块说明）、以及所有被行为描述覆盖的函数明细。

    file_paths不传就自动找root下所有支持的源码文件。每个文件仍然复用
    generate_report——项目级汇总不是新的分析逻辑，只是把单文件报告的结果
    收集起来重新排序、分类，本身不重新读一遍代码。

    文件之间的分析互相独立（各自的复杂度计算+行为描述），用线程池并发跑——
    每次调用都是在等网络请求，不是在等CPU，用户真实反馈"批分析顺序跑一个
    core模块要一个半小时"，这是直接原因。并发时关掉每个文件内部的verbose
    输出（多线程交替打印会乱），只在这一层打印进度。

    with_narrative=True时额外跑三段式设计的第一、三步（工程日志16/17）：
    生成项目叙述、拿每条行为描述对照叙述判断支不支撑，结果分别存进返回值的
    "narrative"、"judged_behaviors"两个键。默认False——describe_project本身
    是一次不便宜的多步agent调用（真实测过11-15步），不该在每次调用
    generate_project_report时都强制付这笔成本，只在真的需要这一层判断时
    显式开启。"""
    if file_paths is None:
        file_paths = find_source_files(root)

    if verbose:
        print(f"正在分析{len(file_paths)}个文件（并发数{max_workers}）...")

    def _analyze_one_file(rel_path):
        return generate_report(root, rel_path, verbose=False)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        file_reports = list(executor.map(_analyze_one_file, file_paths))

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
        narrative_result = narrative.describe_project(root, verbose=verbose)
        result["narrative"] = narrative_result
        if verbose:
            print("正在对照项目叙述判断每个函数的行为...")
        result["judged_behaviors"] = judgment.judge_project_against_narrative(
            result, narrative_result["narrative"], verbose=verbose, max_workers=max_workers,
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
        lines.append(judgment.format_judgment_summary(p["judged_behaviors"]))
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
