"""通用的分析产物存取层——按(project_root, scope)存一份数据，需要时按
scope或scope前缀取回来。今晚有两个真实场景在用同一套接口，不是替单一
场景写的：

1. checkup_cli.py 存"这个项目最新一次的整体快照"，scope="latest"。
2. 批分析（大项目按子模块分批分析时）要存"每个子模块各自的分析结果"，
   scope="batch:子模块名"，跨批整合那一步用list_artifacts(prefix="batch:")
   把同一轮的所有批次结果一次性找出来。

一个项目一份store.json，内部按scope做key——不是每个scope单独存一个
文件、靠转义文件名去对应scope（那样"batch:core/session"和
"batch_core_session"转义后可能撞成同一个文件名，没法可靠反查），简单
存一份JSON、按key取，没有这个歧义。

产物存在读码机自己的ledger_store/目录下（按目标项目名分文件夹），不写进
目标项目内部，不会污染目标仓库。"""
import json
import os
from datetime import datetime

LEDGER_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ledger_store")


def _project_dir(project_root: str) -> str:
    name = os.path.basename(os.path.normpath(project_root))
    d = os.path.join(LEDGER_ROOT, name)
    os.makedirs(d, exist_ok=True)
    return d


def _store_path(project_root: str) -> str:
    return os.path.join(_project_dir(project_root), "store.json")


def _load_store(project_root: str) -> dict:
    path = _store_path(project_root)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_artifact(project_root: str, scope: str, data: dict) -> None:
    """存一份分析产物，scope是这份产物的标识（比如"latest"整体快照，或
    "batch:core/session"某个子模块的批次结果）。同一个scope再存一次会
    覆盖，但会先把旧版本归档到_archive/下（带时间戳+scope，人工可读，
    不用于程序化查找），不会被覆盖丢失。"""
    store = _load_store(project_root)

    if scope in store:
        d = _project_dir(project_root)
        archive_dir = os.path.join(d, "_archive")
        os.makedirs(archive_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_scope = "".join(c if c.isalnum() else "_" for c in scope)
        archive_path = os.path.join(archive_dir, f"{ts}__{safe_scope}.json")
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(store[scope], f, ensure_ascii=False, indent=2)

    store[scope] = data
    with open(_store_path(project_root), "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def load_artifact(project_root: str, scope: str) -> dict | None:
    """取某个scope当前存的产物，没存过就返回None。"""
    return _load_store(project_root).get(scope)


def list_artifacts(project_root: str, prefix: str = "") -> list:
    """列出这个项目下所有scope（不含历史归档），可选按前缀过滤——批分析
    用这个把同一轮的所有"batch:xxx"结果一次性找出来。"""
    scopes = list(_load_store(project_root).keys())
    if prefix:
        return [s for s in scopes if s.startswith(prefix)]
    return scopes


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
