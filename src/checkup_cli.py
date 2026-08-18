"""把"加完功能后，跑一次体检、跟上次比一下"这个动作，从手写脚本变成一条
随手能敲的命令——不是新机制，是把今晚已经验证过的部件（generate_project_report、
judge_project_against_narrative_consensus、compare_judgment_consensus）串起来，
加一层"跟上次快照比"的存取逻辑。

刻意不做的事：不watch文件系统、不常驻后台、不自己决定什么时候该跑——
必须由人主动执行这个命令，这条边界是今晚已经定下来的（工程日志20），
这里不是偷偷加回去。

快照存在读码机自己的snapshots/目录下（按目标项目名分文件夹），不写进
目标项目内部，不会污染目标仓库。

用法：
    python checkup_cli.py <目标项目根目录>              # 单次判断，快
    python checkup_cli.py <目标项目根目录> --consensus   # 加5次consensus，慢但更可信
"""
import argparse
import json
import os
import sys
from datetime import datetime

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

import report

SNAPSHOT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snapshots")


def _snapshot_dir(target_root: str) -> str:
    name = os.path.basename(os.path.normpath(target_root))
    d = os.path.join(SNAPSHOT_ROOT, name)
    os.makedirs(d, exist_ok=True)
    return d


def _load_previous(snapshot_dir: str) -> dict | None:
    path = os.path.join(snapshot_dir, "latest.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_snapshot(snapshot_dir: str, data: dict) -> None:
    path = os.path.join(snapshot_dir, "latest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 归档一份带时间戳的，latest.json只留最近一次，历史版本不会被覆盖丢失
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(snapshot_dir, f"{ts}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _complexity_map(project_report: dict) -> dict:
    return {
        f"{f['file']}::{f['name']}": f["complexity"]
        for f in project_report["top_functions"]
    }


def _verdict_map(project_report: dict) -> dict:
    jb = project_report.get("judged_behaviors") or []
    return {
        f"{e['file']}::{e['behavior']['function']}": e["judgment"]["verdict"]
        for e in jb
    }


def _diff_complexity(old_map: dict, new_map: dict) -> list:
    changes = []
    for key, new_c in new_map.items():
        old_c = old_map.get(key)
        if old_c is None:
            changes.append((key, None, new_c, "新出现"))
        elif new_c != old_c:
            direction = "上升" if new_c > old_c else "下降"
            changes.append((key, old_c, new_c, direction))
    for key, old_c in old_map.items():
        if key not in new_map:
            changes.append((key, old_c, None, "消失（函数被删或改名）"))
    return changes


def _diff_verdict(old_map: dict, new_map: dict) -> list:
    changes = []
    for key, new_v in new_map.items():
        old_v = old_map.get(key)
        if old_v is not None and old_v != new_v:
            changes.append((key, old_v, new_v))
    return changes


def run(target_root: str, use_consensus: bool) -> None:
    snapshot_dir = _snapshot_dir(target_root)
    previous = _load_previous(snapshot_dir)

    print(f"=== 对 {target_root} 做一次体检 ===")
    project_report = report.generate_project_report(target_root, with_narrative=True, verbose=True)

    consensus = None
    if use_consensus:
        print("\n=== 跑5次consensus（比单次判断更可信，但慢） ===")
        consensus = report.judge_project_against_narrative_consensus(
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
        old_complexity = _complexity_map(previous["project_report"])
        new_complexity = _complexity_map(project_report)
        complexity_changes = _diff_complexity(old_complexity, new_complexity)
        if complexity_changes:
            print(f"\n复杂度有变化的函数（{len(complexity_changes)}个）：")
            for key, old_c, new_c, direction in complexity_changes:
                print(f"  {key}: {old_c} → {new_c}（{direction}）")
        else:
            print("\n复杂度没有变化。")

        old_verdict = _verdict_map(previous["project_report"])
        new_verdict = _verdict_map(project_report)
        verdict_changes = _diff_verdict(old_verdict, new_verdict)
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
            comparison = report.compare_judgment_consensus(previous["consensus"], consensus)
            print(report.format_judgment_comparison(comparison))
        elif use_consensus and not previous.get("consensus"):
            print("\n（上一次快照没有consensus数据，这次的consensus结果会被存下来，"
                  "下次能做consensus级别的对比）")

    _save_snapshot(snapshot_dir, {
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
