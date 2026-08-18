"""读码机的最小工具集：列目录、读文件、搜索关键词，都限定在目标代码库根目录内，
不允许访问根目录以外的任何路径——防止 agent"读跑偏"到不相关的地方，
也是一种最基础的安全边界，不需要框架，几行代码就能做到。

search_code 是 sensor 扩容的第一块——纯文本关键词匹配，不是语义搜索、
不接任何外部服务，本质上就是 grep 的最小实现，跟 deep_research 类系统
（多来源网络检索+综合）不是一回事：这里要解决的问题窄得多，只是"在一个
已经有完整读取权限的本地代码库里，找关键词出现在哪"，不需要那么重的机制。"""
import os

SEARCH_MAX_RESULTS = 50  # 结果条数上限——本身就是"压缩"要解决的问题的一个
                          # 预防版本，避免一次搜索的结果把transcript撑爆
SEARCH_FILE_EXTENSIONS = (".py", ".md", ".txt", ".json", ".js", ".ts")
SEARCH_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".idea", ".pytest_cache"}


def _resolve(root: str, rel_path: str) -> str:
    rel_path = (rel_path or "").strip().lstrip("/\\")
    full = os.path.normpath(os.path.join(root, rel_path))
    root_abs = os.path.normpath(root)
    if not (full == root_abs or full.startswith(root_abs + os.sep)):
        raise ValueError(f"路径 {rel_path!r} 超出了代码库根目录范围，拒绝访问")
    return full


def list_directory(root: str, rel_path: str = "") -> str:
    """列出 rel_path（相对代码库根目录）下的文件/子目录名，用于先摸清结构。"""
    try:
        full = _resolve(root, rel_path)
    except ValueError as e:
        return str(e)
    if not os.path.isdir(full):
        return f"（{rel_path or '.'} 不是一个目录，或者不存在）"
    entries = sorted(os.listdir(full))
    return "\n".join(entries) if entries else "（空目录）"


def read_file(root: str, rel_path: str, start_line: int = None, end_line: int = None) -> str:
    """读 rel_path（相对代码库根目录）这个文件的内容。
    不传 start_line/end_line 时读整个文件（原有行为不变，向后兼容）；
    传了就只读这个行号范围（从1开始计数，闭区间），前后带一句"第几行到
    第几行、全文共几行"的说明，让 agent 清楚自己看到的是节选还是全部——
    避免它把局部内容误当成整个文件的样子去下结论。"""
    try:
        full = _resolve(root, rel_path)
    except ValueError as e:
        return str(e)
    if not os.path.isfile(full):
        return f"（{rel_path} 不是一个文件，或者不存在）"
    try:
        with open(full, encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return f"（{rel_path} 不是文本文件，无法读取）"

    total = len(lines)
    if start_line is None and end_line is None:
        return "".join(lines)

    start = max(1, start_line or 1)
    if start > total:
        return f"（{rel_path} 总共只有{total}行，第{start}行不存在）"
    end = min(total, end_line or total)
    snippet = "".join(lines[start - 1:end])
    return f"（{rel_path} 第{start}-{end}行，全文共{total}行，这是节选不是全文）\n{snippet}"


def search_code(root: str, pattern: str, rel_path: str = "") -> str:
    """在 root（或 root 下 rel_path 子目录）内递归搜索 pattern（纯文本子串匹配，
    不支持正则——保持最简单，够用就行，不是先穷举一套正则语法）。
    返回"文件路径:行号: 该行内容"的列表，最多 SEARCH_MAX_RESULTS 条。"""
    try:
        full = _resolve(root, rel_path)
    except ValueError as e:
        return str(e)
    if not os.path.isdir(full):
        return f"（{rel_path or '.'} 不是一个目录，或者不存在）"
    if not pattern:
        return "（搜索关键词不能为空）"

    matches = []
    for dirpath, dirnames, filenames in os.walk(full):
        dirnames[:] = [d for d in dirnames if d not in SEARCH_SKIP_DIRS]
        for filename in filenames:
            if len(matches) >= SEARCH_MAX_RESULTS:
                break
            if not filename.endswith(SEARCH_FILE_EXTENSIONS):
                continue
            file_full = os.path.join(dirpath, filename)
            try:
                with open(file_full, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, start=1):
                        if pattern in line:
                            rel = os.path.relpath(file_full, root)
                            matches.append(f"{rel}:{lineno}: {line.strip()}")
                            if len(matches) >= SEARCH_MAX_RESULTS:
                                break
            except (UnicodeDecodeError, OSError):
                continue
        if len(matches) >= SEARCH_MAX_RESULTS:
            break

    if not matches:
        return f"（没有找到包含 {pattern!r} 的内容）"
    result = "\n".join(matches)
    if len(matches) >= SEARCH_MAX_RESULTS:
        result += f"\n（结果超过{SEARCH_MAX_RESULTS}条，只显示前{SEARCH_MAX_RESULTS}条，考虑用更具体的关键词缩小范围）"
    return result
