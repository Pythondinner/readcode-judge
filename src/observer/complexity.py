"""复杂度工具：用 radon 做 AST 层面的圈复杂度分析，完全不经过大模型，
是"确定性工具测复杂度，LLM 判断行为"这条分工原则的具体落地
（docs/03 第三节"可靠性分工原则"、工程日志01 的讨论结论）。

完全独立于 agent.py 的读文件循环——直接对文件内容跑 AST 分析，不进
transcript，不受"会不会撑爆上下文"的限制，可以直接对着任意大小的
代码库跑，不需要等 sensor 先做搜索/压缩扩容。
"""
import radon.complexity as cc
import radon.raw as raw


def _flatten_with_closures(results, prefix=""):
    """radon的cc_visit只返回顶层函数/类，嵌套函数（.closures属性）不在返回值里——
    装饰器的wrapper几乎全部是这种写法，等于所有装饰器内部的复杂度对整个judge层
    从一开始就是盲区，直到真实测试（checkup_cli.py对比测试撞见retry.py::wrapper
    复杂度变化没被抓到）才暴露。这里递归展开，嵌套函数用点号路径命名
    （比如"with_retry.decorator.wrapper"）避免同名嵌套函数互相覆盖。"""
    flat = []
    for r in results:
        full_name = f"{prefix}{r.name}"
        flat.append(r)
        r._flat_name = full_name
        closures = getattr(r, "closures", None) or []
        flat.extend(_flatten_with_closures(closures, prefix=f"{full_name}."))
    return flat


def measure_file(path: str) -> dict:
    """对单个 .py 文件做复杂度分析，返回
    {"raw": {行数等整体指标}, "functions": [{name, complexity, rank, lineno}, ...]}。
    functions 按复杂度从高到低排序——最该关注的排在最前面，不用调用方自己再排一遍。
    嵌套函数（闭包/装饰器wrapper）也会被展开进来，不只是顶层函数。"""
    with open(path, encoding="utf-8") as f:
        source = f.read()

    raw_metrics = raw.analyze(source)
    top_level = cc.cc_visit(source)
    cc_results = _flatten_with_closures(top_level)

    functions = [
        {
            "name": getattr(r, "_flat_name", r.name),
            "type": type(r).__name__,  # "Function" 或 "Class"（方法算在类下面的子项）
            "complexity": r.complexity,
            "rank": cc.cc_rank(r.complexity),  # A(最简单)到F(最复杂)的字母评级，radon内置标准
            "lineno": r.lineno,
        }
        for r in cc_results
    ]
    functions.sort(key=lambda x: x["complexity"], reverse=True)

    return {
        "raw": {
            "总行数": raw_metrics.loc,
            "代码行数": raw_metrics.sloc,  # 不含空行/纯注释行
            "注释行数": raw_metrics.comments,
            "空行数": raw_metrics.blank,
        },
        "functions": functions,
    }


def format_report(path: str, result: dict) -> str:
    """把measure_file的结果整理成人能一眼看懂的文本报告。"""
    lines = [f"=== {path} ===", f"总行数{result['raw']['总行数']}，代码行数{result['raw']['代码行数']}"]
    if not result["functions"]:
        lines.append("（没有检测到函数/类，可能是纯脚本或者空文件）")
        return "\n".join(lines)

    lines.append(f"\n共{len(result['functions'])}个函数/类，按复杂度从高到低：")
    for f in result["functions"]:
        lines.append(f"  [{f['rank']}] {f['name']}（第{f['lineno']}行）复杂度={f['complexity']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else __file__
    print(format_report(target, measure_file(target)))
