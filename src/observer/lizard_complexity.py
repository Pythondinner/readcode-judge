"""语言无关的复杂度工具：花括号语言（JS/TS/Java/C/C++等）用lizard做词法分析
计算圈复杂度——不是自己发明的近似指标，是跟radon同一类的真实圈复杂度计算，
只是用不同的（每种语言专属的）轻量解析器实现，不是完整AST但比正则规则精确
得多。

前身是自己写的正则+分支关键词计数（工程日志12），当时的动机是"不想为每种
新语言接一套专属工具、想要一次性投入"。后来意识到lizard本身就是"一次性
投入、覆盖十几种语言"的现成方案，而且是纯Python包（不像TS专属工具那样要
接Node.js运行时）——不该在这类"常见问题"上跳过检查现成工具就直接自己写。
用radon做真值在Python上验证：lizard算出的圈复杂度跟radon**100%完全一致**
（68/68个函数，工程日志13），不是"相关性高"，是同一个数字——这不是一个
可信度打折的替代品，弃用了自己写的regex版本。

Python继续用complexity.py/radon（已经在用、结果一致，没有理由换掉），这个
模块只覆盖radon不支持的其它语言。
"""
from radon.complexity import cc_rank
import lizard

# lizard官方支持的语言比这更全（Python/C#/Go/Rust/Kotlin/Swift/Ruby/PHP/Scala等），
# 这里先列出常见的几种；真遇到没列出但lizard支持的语言，加个扩展名进这个元组
# 就行，不用改任何其它代码——这正是换成lizard之后的好处，新语言的边际成本
# 几乎是0，不用再重新设计/验证一遍规则。
LIZARD_EXTENSIONS = (
    ".ts", ".tsx", ".js", ".jsx", ".java", ".c", ".h", ".cpp", ".cc", ".hpp",
    ".cs", ".go", ".rs", ".kt", ".swift", ".m", ".rb", ".php", ".scala",
)


def measure_file(path: str) -> dict:
    """对单个文件做圈复杂度分析（lizard自动识别语言），返回结构跟
    complexity.measure_file完全一致（{"raw":{"总行数":...},
    "functions":[{"name","type","complexity","rank","lineno"},...]}），
    可以复用同一套下游逻辑（report.py的阈值判断、排序、格式化），不需要
    像之前那样区分"精确"和"粗筛"两条路径——两者现在是同一类数字。"""
    result = lizard.analyze_file(path)
    functions = [
        {
            "name": f.name,
            "type": "Function",
            "complexity": f.cyclomatic_complexity,
            "rank": cc_rank(f.cyclomatic_complexity),
            "lineno": f.start_line,
        }
        for f in result.function_list
    ]
    functions.sort(key=lambda x: x["complexity"], reverse=True)

    with open(path, encoding="utf-8", errors="ignore") as fp:
        total_lines = sum(1 for _ in fp)

    return {"raw": {"总行数": total_lines}, "functions": functions}


def format_report(path: str, result: dict) -> str:
    """把measure_file的结果整理成人能一眼看懂的文本报告。"""
    lines = [f"=== {path} ===", f"总行数{result['raw']['总行数']}"]
    if not result["functions"]:
        lines.append("（没有检测到函数——可能是纯配置/类型声明文件，或者lizard不支持这个扩展名）")
        return "\n".join(lines)
    lines.append(f"\n共{len(result['functions'])}个函数，按复杂度从高到低：")
    for f in result["functions"]:
        lines.append(f"  [{f['rank']}] {f['name']}（第{f['lineno']}行）复杂度={f['complexity']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else __file__
    print(format_report(target, measure_file(target)))
