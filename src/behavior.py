"""行为描述：给一个已经被复杂度工具（complexity.py）标出来的函数，生成一份
带证据的契约描述——它对调用方承诺了什么，不是"这段代码在干什么"这种开放式
总结（那种范围太软，没法验证对不对）。

不是新发明一套机制——复用 agent.py（读代码+回答问题）和 verifier.py（独立
核实回答有没有真实证据支撑），只是把任务从"回答一个开放问题"换成"描述这一个
具体函数的契约"，跟其余问答场景走的是同一条生产线。
"""
import agent
import verifier

DESCRIBE_TASK_TEMPLATE = (
    "描述{file_path}里的函数/类「{function_name}」（{complexity_note}，"
    "在第{lineno}行）的契约：它对调用方承诺了什么——输入是什么、输出是什么、"
    "有没有副作用（改了什么外部状态/文件/全局数据）、调用前需要满足什么前置条件、"
    "调用后保证什么。每一条描述都要引用具体的代码原文作为依据，不要泛泛而谈、"
    "不要只复述函数名和docstring的字面意思。"
    "\n\n最后单独用一行、以'【调用方须知】'开头，明确指出一件调用方最容易忽略、"
    "或者最该警惕的具体事情——比如一个不明显的副作用、一个函数名字面意思看不出来的"
    "行为、一个容易被漏掉的边界情况。这一句要具体、可操作，不要写成泛泛的总结。"
)


def _complexity_note(function_info: dict) -> str:
    """function_info可能来自complexity.py（radon，只测Python）或
    lizard_complexity.py（lizard，测其它语言），两者返回同样的字段形状
    （"complexity"+"rank"）——工程日志13验证过lizard和radon在Python上的数字
    100%一致，是同一类可信的圈复杂度计算，不需要在措辞上区分"精确"和"粗糙"，
    只是不点名具体哪个工具测的（字段里本来也不带来源信息）。"""
    if "complexity" in function_info and "rank" in function_info:
        return f"圈复杂度{function_info['complexity']}（{function_info['rank']}级）"
    return "复杂度信息未知"


def describe_function(root: str, file_path: str, function_info: dict, verbose: bool = True) -> dict:
    """function_info 是 complexity.measure_file() 或 lizard_complexity.measure_file()
    结果里 functions 列表的一项，两者字段形状一致（{"name","type","complexity",
    "rank","lineno"}），见_complexity_note。

    返回 {"function", "description", "agent_steps", "agent_hit_cap",
    "verified", "verify_evidence", "verify_reasoning"}——先用 agent 生成契约
    描述，再用 verifier 独立核实这份描述里的说法有没有被代码本身支撑，
    两步都复用已经验证过的机制，不重新发明。"""
    question = DESCRIBE_TASK_TEMPLATE.format(
        file_path=file_path, function_name=function_info["name"],
        complexity_note=_complexity_note(function_info), lineno=function_info["lineno"],
    )
    outcome = agent.answer_question(root, question, verbose=verbose)
    v = verifier.verify_answer(root, question, outcome["answer"], verbose=verbose)
    return {
        "function": function_info["name"],
        "description": outcome["answer"],
        "agent_steps": len(outcome["steps"]),
        "agent_hit_cap": outcome["hit_cap"],
        "verified": v["verified"],
        "verify_evidence": v["evidence"],
        "verify_reasoning": v["reasoning"],
    }
