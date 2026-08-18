"""诊断+修复建议：Observer标出一条"违反不变量"的具体发现之后，按需启动
的深入诊断——主动去查这个函数的实际调用方，判断真实调用路径下会不会
被触发、该怎么修。跟Observer那种"材料已经齐了，一次性推理"的机制形状
不同：调用方是谁事先不知道，需要现查，所以复用的是sensor层的
agent.answer_question（从零探索），不是Observer的判断机制。"""
from sensor import agent
from sensor import verifier

DIAGNOSIS_TASK_TEMPLATE = (
    "读码机的judge层判断，函数「{function_name}」（{file_path}）的行为违反了这个项目的"
    "一条不变量：\n{matched_invariant}\n\n"
    "判断依据：{reasoning}\n\n"
    "已核实的行为契约描述：\n{description}\n\n"
    "你的任务分三步：\n"
    "1. 用search_code找到这个函数的实际调用方，逐个读一遍确认——这个问题在正常调用路径下"
    "会不会真的被触发？有没有某个调用方已经做了防护（比如提前检查了某个状态、某个条件），"
    "让这个问题实际上不构成风险？这一步是judge层原来的分析完全没做过的——原来的行为描述"
    "只看这个函数自己，不看谁在调用它。\n"
    "2. 如果确认是真实、会被触发的问题，提出一个具体、最小化的修复方案——只针对这条具体"
    "违反给出改动建议，不要重新设计整个函数，尽量保留函数原有的设计意图（读一下函数的"
    "注释/docstring，如果某个行为是刻意的设计取舍，修复不该把它一起改掉，只该处理没被"
    "覆盖到的那部分）。\n"
    "3. 如果发现这个问题实际上不会被真实调用路径触发（比如所有调用方都已经做了防护），"
    "明确说明具体是哪个调用方、怎么防护的，不要为了给出结论就编一个不存在的修复。\n\n"
    "最后单独一行给结论：'结论：需要修复' 或 '结论：不需要修复（已被调用方防护）' 或"
    "'结论：有条件需要修复（说明具体条件）'。需要修复的话，给出具体怎么改，可以带示例"
    "代码片段——这只是给人看的建议，不会被自动应用，你没有写文件的能力。"
)


def diagnose_and_propose_fix(
    root: str, file_path: str, function_name: str, matched_invariant: str,
    reasoning: str, description: str, verbose: bool = True,
) -> dict:
    """给Tier1里一条"违反不变量"的发现做诊断——这是今晚两次真实闭环（工程日志22/23）
    里唯一没有被read码机自己的机制覆盖、完全靠人现读代码做的一步：判断这个问题在
    真实调用路径下会不会被触发、该怎么修。两次真实诊断都发现，关键信息是函数的
    "实际调用方"，而judge层现有的所有环节（复杂度、行为描述、叙述、判断）都只看
    被标记的这一个函数本身，从不看调用它的地方——这不是疏忽，是judge_behavior_
    against_narrative这类"喂现成文字进去、一次性推理"的机制形状决定的，调用方是谁
    要现查，不是提前能喂进prompt的静态材料。

    所以这个函数复用的不是判断层的机制，是agent.answer_question——跟"读代码回答
    问题"是同一条生产线，只是这次的问题是"这个已知的违反，在真实调用路径下成不成立、
    该怎么修"，不是从零探索一个开放问题。

    诊断本身也用verifier独立核实——它对调用方行为做了新的断言，这些断言没有被
    最初生成behavior_description时的核实覆盖过（那次核实只查了被标记的函数自己）。

    返回{"diagnosis","agent_steps","agent_hit_cap","verified","verify_evidence",
    "verify_reasoning"}。只产出诊断和建议——不写文件、不改代码，执行永远走人工
    审批下的协作，这条边界今晚两次真实闭环里都没有破例，这里也不例外。"""
    question = DIAGNOSIS_TASK_TEMPLATE.format(
        function_name=function_name, file_path=file_path,
        matched_invariant=matched_invariant, reasoning=reasoning, description=description,
    )
    outcome = agent.answer_question(root, question, verbose=verbose)
    v = verifier.verify_answer(root, question, outcome["answer"], verbose=verbose, max_steps=10)
    return {
        "diagnosis": outcome["answer"],
        "agent_steps": len(outcome["steps"]),
        "agent_hit_cap": outcome["hit_cap"],
        "verified": v["verified"],
        "verify_evidence": v["evidence"],
        "verify_reasoning": v["reasoning"],
    }
