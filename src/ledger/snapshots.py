"""存快照、跟上次比——读码机自己的记忆层雏形，目前只服务checkup_cli.py
这一个场景（不是完整的③记忆层设计，只是把"跟上次比"这个动作需要的存取
逻辑单独放一处，别的调用方需要时也能直接复用，不用重新写一遍）。

快照存在读码机自己的snapshots/目录下（按目标项目名分文件夹），不写进
目标项目内部，不会污染目标仓库。"""
import json
import os
from datetime import datetime

SNAPSHOT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "snapshots")


def snapshot_dir(target_root: str) -> str:
    name = os.path.basename(os.path.normpath(target_root))
    d = os.path.join(SNAPSHOT_ROOT, name)
    os.makedirs(d, exist_ok=True)
    return d


def load_previous(snapshot_dir_path: str) -> dict | None:
    path = os.path.join(snapshot_dir_path, "latest.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(snapshot_dir_path: str, data: dict) -> None:
    path = os.path.join(snapshot_dir_path, "latest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 归档一份带时间戳的，latest.json只留最近一次，历史版本不会被覆盖丢失
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(snapshot_dir_path, f"{ts}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def complexity_map(project_report: dict) -> dict:
    return {
        f"{f['file']}::{f['name']}": f["complexity"]
        for f in project_report["top_functions"]
    }


def verdict_map(project_report: dict) -> dict:
    jb = project_report.get("judged_behaviors") or []
    return {
        f"{e['file']}::{e['behavior']['function']}": e["judgment"]["verdict"]
        for e in jb
    }


def diff_complexity(old_map: dict, new_map: dict) -> list:
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


def diff_verdict(old_map: dict, new_map: dict) -> list:
    changes = []
    for key, new_v in new_map.items():
        old_v = old_map.get(key)
        if old_v is not None and old_v != new_v:
            changes.append((key, old_v, new_v))
    return changes
