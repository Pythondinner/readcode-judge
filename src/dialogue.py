"""读码机自己的对话框——不再是被Claude Code/deepseek harness当成工具调用的
MCP server，是读码机自己主动的入口：问文件夹路径→自动分析→出报告→（有
确认发现）自动诊断→问要不要交给执行者处理→把诊断当任务描述交出去。执行
权限的确认，用的是执行者自己原生的确认机制，读码机不实现、也不该实现
一个能代替用户按"确认"的机制。这条边界是"半自动，等准确率高了就自动化"
这个想法被明确否定之后定下的：该不该自动化按这次改动的风险/可逆性判断，
不按判断层自称多有把握判断（详见标准记忆readcode-machine-automation-philosophy）。

两种执行者，走的是两条不同的交接方式，但同一条设计原则：
- Claude Code（默认）：交接终端给它的正常交互会话（不是非交互的-p模式），
  它自己原生的终端确认机制接管"要不要真的执行"。
- dsh（deepseek-harness，--executor=dsh）：它没有现成的终端交互模式，
  默认自带的profile只有web和headless；headless不交互直接执行、不符合
  "先确认再执行"的要求，所以走web这条路——起一个dsh web服务（已经在跑就
  直接复用，不重复起，省去npx冷启动的成本）、打开浏览器，由它自己网页
  界面的原生确认机制接管。dsh的web session目前没有已知的稳定对外API能
  直接把任务塞进去，诊断内容写成文件（不是打印出来靠人工复制粘贴）放进
  目标项目根目录，用户只需要告诉dsh去读这个文件——大项目的诊断本来就长，
  贴进聊天框体验差，dsh本来就有读文件的能力，直接读比人工转述更不容易
  丢信息。dsh处理完之后，如果按要求把"做了什么"写成了说明文件，会自动
  读出来展示，不用去网页里翻聊天记录。"发送任务"这一步（告诉dsh去读哪个
  文件）仍需要人工做一下，是明确的、已知的缺口，不是忘了。

执行者处理完、控制权交回来之后，自动重新体检一遍，跟改之前的报告对比，
把"这次改动前后的变化"直接展示出来——确认的对象应该是"结果"（改前改后
对比、判断变没变），不是"代码diff细节"，降低确认这道关卡需要的专业门槛。

用法：
    python dialogue.py                    # 默认交给Claude Code
    python dialogue.py --executor=dsh      # 交给dsh（web半自动衔接）
    python dialogue.py --test-handoff      # 跳过判断，用已知诊断材料测交接本身
"""
import os
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser

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


def _get_batch_diagnosis_text(root: str, batch_result: dict):
    """对分批分析的每个批次分别跑consensus+迭代信号+决策层自动诊断，汇总
    成一份诊断文本，没有任何批次有确认的发现就返回None。

    consensus按批次分别跑，不是把所有批次的judged_behaviors合并统一跑一次：
    每个批次已经有自己独立生成的项目叙述（run_batch_analysis时生成的），
    consensus要拿"同一份叙述"反复判断才有意义，批次之间叙述本来就不是
    同一份，合并统一跑需要先解决"用哪份叙述当基准"这个没有干净答案的问题。
    按批次分别跑测不到"批次划分本身带来的额外不确定性"，但这部分信号已经
    由run_batch_analysis自己的跨批关联整合覆盖，不是consensus该管的事——
    两者职责不重叠，不是漏掉了一半。"""
    batches_map, _ = batch_module.find_batches(root)
    sections = []
    for name, pr in batch_result["batches"].items():
        if "narrative" not in pr:
            continue
        batch_root = root if name == "_root" else batches_map.get(name, root)
        print(f"\n批次「{name}」正在测判断稳不稳定（跑5次consensus）...")
        judgment_consensus = consensus_module.judge_project_against_narrative_consensus(
            pr, pr["narrative"]["narrative"], runs=5, verbose=True,
        )
        signal = signal_module.build_iteration_signal(pr, judgment_consensus)
        if not signal["tier1_confirmed"]:
            continue
        print(f"批次「{name}」发现{len(signal['tier1_confirmed'])}条确认的问题，自动跑诊断...")
        results = orchestrate.decide_and_diagnose(batch_root, pr, judgment_consensus, signal, verbose=True)
        sections.append(f"## 批次「{name}」\n\n{orchestrate.format_orchestration_result(results)}")
    if not sections:
        return None
    return "\n\n".join(sections)


def _invoke_claude_code(root: str, task_description: str) -> None:
    """把诊断结果当任务描述，交接终端给Claude Code的正常交互会话（不是
    -p非交互模式）——要让Claude Code自己原生的权限确认机制接管"要不要
    真的执行"这个决定。子进程不重定向stdio，终端控制权真的交出去，用户
    能直接跟Claude Code对话，它退出后控制权自然交回这个脚本。"""
    print("\n" + "=" * 60)
    print("交给Claude Code处理——接下来是Claude Code的会话，读码机退到后台")
    print("=" * 60 + "\n")
    # Windows上claude是npm装的claude.cmd（批处理脚本包装），不是真正的PE
    # 可执行文件——不带shell=True时subprocess走CreateProcess直接找它会报
    # FileNotFoundError（真实撞见的bug）。shell=True让Windows走cmd.exe去
    # 解析PATHEXT找到.cmd并执行，跟直接在终端敲claude是一回事。
    subprocess.run(["claude", task_description], cwd=root, shell=(os.name == "nt"))
    print("\n" + "=" * 60)
    print("Claude Code会话结束，读码机接回来")
    print("=" * 60)


def _dsh_web_is_up(url: str) -> bool:
    """真的发一次HTTP请求确认dsh web服务在正常响应——之前测过裸TCP端口
    能连上不代表HTTP服务真的能处理请求（dsh内部框架可能还在初始化），
    这个坑吃过一次。不管返回码是什么，只要连上了就说明在真正服务。"""
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except urllib.error.HTTPError:
        return True
    except urllib.error.URLError:
        return False


def _invoke_deepseek_harness(root: str, task_description: str) -> None:
    """把诊断结果准备好，起一个dsh web服务（如果已经在跑就直接复用）、打开
    浏览器，让dsh自己的网页界面去跟用户交互确认要不要执行——跟
    _invoke_claude_code同一条设计原则（读码机不自己实现确认机制，交给执行者
    原生的确认界面），只是dsh现在没有现成的终端交互模式：默认自带的两个
    profile是web和headless，headless不交互、直接执行（真实测过，还撞见过
    5分钟无响应，不可靠），web模式的文档明确写着"执行需要批准的操作之前会
    先问用户"，所以走web这条路，不是终端交接。

    诊断内容写成文件（不是打印出来靠人工复制粘贴进对话框）——两个真实原因：
    一是大项目的诊断本来就长，贴进聊天框体验很差；二是dsh本来就有读文件的
    能力，直接读文件比人工转述更不容易信息丢失或者贴漏。用户发现之后要做的
    只是告诉dsh去读这个文件，不用贴整份诊断文本，这一步的人工负担比第一版
    小很多。

    dsh web是常驻服务，处理完不主动关掉——留着给下次用，省去npx重复冷启动
    的成本（第一次要下载包，实测过启动很慢，这是今天反复撞见的真实痛点）。"""
    diagnosis_path = os.path.join(root, "读码机诊断.md")
    with open(diagnosis_path, "w", encoding="utf-8") as f:
        f.write(task_description)

    url = "http://127.0.0.1:3080"
    if _dsh_web_is_up(url):
        print("\ndsh web服务已经在跑了，直接复用，不用重新起。")
    else:
        print("\n" + "=" * 60)
        print("正在启动dsh web服务（第一次运行npx要下载包，可能需要几分钟）...")
        print("=" * 60)
        # npx装的dsh在Windows上同样是.cmd包装（跟claude那次一样的坑），
        # shell=True走cmd.exe解析PATHEXT才能找到它。dsh web是常驻服务，不会
        # 自己退出，用Popen而不是run，不然会卡住整个脚本。
        proc = subprocess.Popen(
            ["npx", "--yes", "@deepseek-ai/dsh", "web"],
            cwd=root, shell=(os.name == "nt"),
        )
        ready = False
        for _ in range(180):  # 最多等3分钟
            if proc.poll() is not None:
                print(f"\ndsh进程提前退出了（返回码{proc.returncode}），没能起来服务，检查上面的输出找原因。")
                return
            if _dsh_web_is_up(url):
                ready = True
                break
            time.sleep(1)
        if not ready:
            print(f"\n等了3分钟服务还是没反应，可能是启动特别慢或者失败了——"
                  f"手动去浏览器试试{url}，如果还是打不开，看看上面npx的输出有没有报错。")
    print(f"\n正在打开浏览器：{url}")
    webbrowser.open(url)

    fix_note_path = os.path.join(root, "dsh修复说明.md")
    print("\n" + "=" * 60)
    print("接下来手动做这几步：")
    print(f"1. 网页里点「Choose workspace」，选中：{root}（选过的话可以跳过）")
    print("2. 新建/找到一个session，跟dsh说这句话（不用贴整份诊断，内容已经写成文件了）：")
    print(f'   请读取项目根目录下的「读码机诊断.md」，照着里面的建议处理，'
          f'处理完把你做了什么写进项目根目录的「dsh修复说明.md」')
    print("3. dsh执行需要批准的操作时会自己弹出确认，在网页里确认")
    print("=" * 60)
    print(f"\n诊断内容已经写进：{diagnosis_path}")
    print("=" * 60)

    input("\n处理完成后（不管有没有真的采纳修改），回来这里按回车继续...")

    if os.path.exists(fix_note_path):
        print("\n" + "=" * 60)
        print("dsh写的修复说明：")
        print("=" * 60)
        with open(fix_note_path, encoding="utf-8") as f:
            print(f.read())
    else:
        print(f"\n（没有找到{fix_note_path}，dsh可能没按要求写这份说明，或者还没处理完）")

    # dsh web是常驻服务，这里不主动关掉——留着给下次用，省去npx重复冷启动
    # 的成本，用户自己想关的话手动结束那个终端/进程就行。


def _git_changed_files(root: str) -> set:
    """用git diff（不是大模型）确定性地拿到这次改动真的碰过哪些文件——
    免费、瞬间、100%准确，用来给判断变化打标签，区分"代码真的变了"还是
    "代码没变、判断自己噪音波动"。这个区分是真实撞见过才加的：中型样本
    那次dsh只改了orders.py，但改前改后对比里inventory.py/models.py另外
    4个没被碰过的函数判断结果也变了——26%噪音率（consensus测出来的）
    第一次在改前改后对比场景里被直接看见，不标出来会被误读成"这次改动
    顺带引入了4个新问题"。不是git仓库、或者git命令失败就返回None，调用方
    据此决定要不要跳过这层标注，不强求每个目标项目都有git。"""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        return {line.strip().replace("/", os.sep) for line in out.stdout.splitlines() if line.strip()}
    except (OSError, subprocess.TimeoutExpired):
        return None


def _write_and_print(root: str, filename: str, lines: list) -> None:
    """复检结果同时打印到终端、写成md文件——终端输出容易被截断、大段内容
    滚动起来不好看，文件留个能完整回看的版本，两者内容完全一致，不是
    另外做一份摘要。"""
    text = "\n".join(lines)
    print(text)
    path = os.path.join(root, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n（这份复检结果也写进了：{path}）")


def _compare_before_after(root: str, before_result, before_is_batch: bool) -> None:
    """执行者处理完之后，自动重新分析一遍，跟执行前的结果对比——确认的
    对象是"结果"不是"代码"：这次改动前后，问题变多了还是变少了、复杂度
    涨了还是降了，这些不需要读代码就能判断。判断结果的变化额外用git diff
    （确定性、免费、不是大模型生成的文档，不会带来新的加工偏差）标注
    "文件真的被改过"还是"文件没被动过、大概率是判断噪音"，避免把噪音
    误读成真实的改动效果。结果同时写成md文件，不只是打印在终端——大段
    内容在终端里容易被截断、不好回看。"""
    print("\n正在重新体检，看看这次改动的效果...")
    after_result, after_is_batch = _run_analysis(root)

    if before_is_batch or after_is_batch:
        lines = [
            "（分批分析结果目前还没有专门的前后对比函数——已知缺口，不是忘了）",
            "",
            "=== 改动前 ===",
            _format_report(before_result, before_is_batch)[:1500],
            "",
            "=== 改动后 ===",
            _format_report(after_result, after_is_batch)[:1500],
        ]
        _write_and_print(root, "读码机复检报告.md", lines)
        return

    old_verdict = store.verdict_map(before_result)
    new_verdict = store.verdict_map(after_result)
    changes = store.diff_verdict(old_verdict, new_verdict)
    old_complexity = store.complexity_map(before_result)
    new_complexity = store.complexity_map(after_result)
    complexity_changes = store.diff_complexity(old_complexity, new_complexity)
    changed_files = _git_changed_files(root)
    verified_lookup = {
        f"{e['file']}::{e['complexity_info']['name']}": e["behavior"]["verified"]
        for e in after_result.get("judged_behaviors", [])
    }

    lines = ["=== 这次改动前后对比 ==="]
    if changed_files is None:
        lines.append("（目标项目不是git仓库，或者git diff跑失败了——没法区分真实变化和判断噪音，"
                      "下面的判断变化没有标注，看的时候自己留意）")
    if changes:
        lines.append(f"判断结果变化的函数（{len(changes)}个）：")
        for key, old_v, new_v in changes:
            file_part = key.split("::", 1)[0]
            if changed_files is None:
                tag = ""
            elif file_part in changed_files:
                verified = verified_lookup.get(key)
                verified_tag = {True: "，verifier已复核通过", False: "，verifier复核未通过", None: ""}[verified]
                tag = f"（文件真的被改过{verified_tag}）"
            else:
                tag = "（文件没被动过，大概率是判断噪音，不是真实变化）"
            marker = "  ✓ 变好了" if old_v == "undermine" and new_v == "support" else ""
            lines.append(f"  {key}: {old_v} → {new_v}{marker}{tag}")
    else:
        lines.append("判断结果没有变化。")
    if complexity_changes:
        lines.append(f"\n复杂度变化的函数（{len(complexity_changes)}个）：")
        for key, old_c, new_c, direction in complexity_changes:
            lines.append(f"  {key}: {old_c} → {new_c}（{direction}）")
    else:
        lines.append("复杂度没有变化。")

    _write_and_print(root, "读码机复检报告.md", lines)


# 已经用工程日志27/33验证过是真实、准确的诊断材料——只用来单独测试"交给
# Claude Code处理"这一步本身（终端交接对不对、任务描述带没带过去），不是
# 用来测判断层准不准（那个已经用consensus测过，26%噪音+行为描述噪音都是
# 已知、量化过的问题，这里不重复测）。--test-handoff跳过前面容易受噪音
# 影响的判断环节，直接进到"要不要交给Claude Code"这一步。
_KNOWN_GOOD_DIAGNOSIS_TEXT = (
    "# 自动诊断结果（1条tier1_confirmed发现，已自动跑完诊断，测试用固定材料）\n\n"
    "以下每一条都只是诊断+修复建议，不是已经应用的改动——要不要真的改，仍需人工确认。\n\n"
    "## src/goal_loop.py :: write_and_save_one_with_check（一致率60%，✓ 诊断已核实）\n\n"
    "结论：需要修复\n\n"
    "write_and_save_one_with_check（src/goal_loop.py 第263行）即使 write_with_check 返回"
    "status为cap_reached（重试封顶仍未通过must_avoid/must_include检查），也会无条件调用"
    "ledger.save_draft保存草稿（第283行），没有任何区分标记，导致有缺陷的正文被持久化。"
    "唯一调用方write_missing_acts_in_series没有对status做任何防护。\n\n"
    "最小化修复建议：cap_reached时额外记录一个未通过检查的标记（比如写一个.unchecked"
    "标记文件），让这个事实持久化到磁盘可查询，不是悄悄丢掉。"
)


def run(test_handoff: bool = False, executor: str = "claude") -> None:
    print("=== 读码机 ===")
    print(f"给一个项目文件夹路径，我帮你做体检、找问题，需要的话交给{'dsh' if executor == 'dsh' else 'Claude Code'}处理。\n")

    root = input("项目文件夹路径：").strip()
    # Windows"复制为路径"会自带一层引号（直引号或弯引号），os.path.isdir
    # 不会自动脱掉，原样传进去必然找不到目录——这是真实撞见的bug，不是
    # 假设性的边界情况。
    root = root.strip("\"'“”‘’")
    if not os.path.isdir(root):
        print(f"找不到目录：{root}")
        return
    root = os.path.abspath(root)

    # 报告本身（复杂度、top_functions）跟改前改后对比需要用，噪音只出在
    # 判断/诊断这一步（独立重新生成行为描述会强调不同的真实事实）——所以
    # --test-handoff只跳过判断+诊断，报告生成照常跑，改前改后对比才有真实
    # 的"before"基线可用，不是伪造一个None糊弄过去。
    result, is_batch = _run_analysis(root)
    print("\n" + "=" * 60)
    print(_format_report(result, is_batch))

    if is_batch and test_handoff:
        print("\n（--test-handoff的固定诊断材料是给单次分析场景准备的，"
              "跟分批分析用不上，这两个选项不支持组合）")
        return

    if test_handoff:
        print("\n（--test-handoff模式：跳过consensus+诊断这一步，直接用已知真实的"
              "诊断材料测'交给Claude Code处理'这个动作本身）")
        diagnosis_text = _KNOWN_GOOD_DIAGNOSIS_TEXT
    elif is_batch:
        diagnosis_text = _get_batch_diagnosis_text(root, result)
        if diagnosis_text is None:
            print("\n没有发现需要处理的问题，到此结束。")
            return
    else:
        diagnosis_text = _get_diagnosis_text(root, result)
        if diagnosis_text is None:
            print("\n没有发现需要处理的问题，到此结束。")
            return

    print("\n" + "=" * 60)
    print(diagnosis_text)

    executor_label = "dsh" if executor == "dsh" else "Claude Code"
    choice = input(f"\n要交给{executor_label}处理吗？输入 是 确认，其他任意键跳过：").strip()
    if choice != "是":
        print("好，不处理，到此结束。")
        return

    task_description = (
        "读码机对这个项目做体检，发现以下确认的问题，请你处理（是否真的执行改动，"
        "由你自己的确认流程决定，我这边不会替你确认）：\n\n" + diagnosis_text
    )
    if executor == "dsh":
        _invoke_deepseek_harness(root, task_description)
    else:
        _invoke_claude_code(root, task_description)
    _compare_before_after(root, result, is_batch)


if __name__ == "__main__":
    import sys
    executor = "dsh" if "--executor=dsh" in sys.argv else "claude"
    run(test_handoff="--test-handoff" in sys.argv, executor=executor)
