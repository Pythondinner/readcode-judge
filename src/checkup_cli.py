"""把"加完功能后，跑一次体检、跟上次比一下"这个动作，从手写脚本变成一条
随手能敲的命令——不是新机制，是把observer层已经验证过的部件
（generate_project_report、judge_project_against_narrative_consensus、
compare_judgment_consensus）串起来，加一层ledger.snapshots的存取逻辑。

刻意不做的事：不watch文件系统、不常驻后台、不自己决定什么时候该跑——
必须由人主动执行这个命令，这条边界是今晚已经定下来的（工程日志20），
这里不是偷偷加回去。

用法：
    python checkup_cli.py <目标项目根目录>              # 单次判断，快
    python checkup_cli.py <目标项目根目录> --consensus   # 加5次consensus，慢但更可信
"""
import argparse
import os
from datetime import datetime

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from observer import report
from observer import consensus as consensus_module
from ledger import snapshots


def run(target_root: str, use_consensus: bool) -> None:
    snapshot_dir = snapshots.snapshot_dir(target_root)
    previous = snapshots.load_previous(snapshot_dir)

    print(f"=== 对 {target_root} 做一次体检 ===")
    project_report = report.generate_project_report(target_root, with_narrative=True, verbose=True)

    consensus = None
    if use_consensus:
        print("\n=== 跑5次consensus（比单次判断更可信，但慢） ===")
        consensus = consensus_module.judge_project_against_narrative_consensus(
            project_report, project_report["narrative"]["narrative"], runs=5, verbose=True,
        )

    print("\n" + "=" * 60)
    print("体检结果")
    print("=" * 60)
    print(report.format_project_report(project_report))

    print("\n" + "=" * 60)
    print("跟上一次快照对比")
    print("=" * 60)
    if previous is None:
        print("没有找到上一次的快照——这是第一次对这个项目做体检，本次结果会被存为基线，"
              "下次再跑就能看到变化了。")
    else:
        old_complexity = snapshots.complexity_map(previous["project_report"])
        new_complexity = snapshots.complexity_map(project_report)
        complexity_changes = snapshots.diff_complexity(old_complexity, new_complexity)
        if complexity_changes:
            print(f"\n复杂度有变化的函数（{len(complexity_changes)}个）：")
            for key, old_c, new_c, direction in complexity_changes:
                print(f"  {key}: {old_c} → {new_c}（{direction}）")
        else:
            print("\n复杂度没有变化。")

        old_verdict = snapshots.verdict_map(previous["project_report"])
        new_verdict = snapshots.verdict_map(project_report)
        verdict_changes = snapshots.diff_verdict(old_verdict, new_verdict)
        if verdict_changes:
            print(f"\n单次判断结果有变化的函数（{len(verdict_changes)}个，"
                  "注意单次判断有噪音，变化不一定是真的，想确认就加--consensus）：")
            for key, old_v, new_v in verdict_changes:
                marker = " ⚠" if new_v == "undermine" else ""
                print(f"  {key}: {old_v} → {new_v}{marker}")
        else:
            print("\n单次判断结果没有变化。")

        if consensus and previous.get("consensus"):
            print("\nconsensus对比（更可信）：")
            comparison = consensus_module.compare_judgment_consensus(previous["consensus"], consensus)
            print(consensus_module.format_judgment_comparison(comparison))
        elif use_consensus and not previous.get("consensus"):
            print("\n（上一次快照没有consensus数据，这次的consensus结果会被存下来，"
                  "下次能做consensus级别的对比）")

    snapshots.save_snapshot(snapshot_dir, {
        "target_root": target_root,
        "timestamp": datetime.now().isoformat(),
        "project_report": project_report,
        "consensus": consensus,
    })
    print(f"\n本次快照已保存到 {snapshot_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="对一个项目做一次体检，跟上次比对")
    parser.add_argument("target_root", help="要体检的项目根目录")
    parser.add_argument("--consensus", action="store_true", help="加跑5次consensus，更可信但更慢")
    args = parser.parse_args()
    run(os.path.abspath(args.target_root), args.consensus)
