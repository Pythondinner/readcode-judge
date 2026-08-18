"""项目叙述：给整个项目生成一份定位描述，作为后续判断"某个函数支不支撑
项目正确运行"的参照标准——复用sensor层的agent.answer_question读代码能力，
跟behavior.describe_function是同一条生产线，只是问题从"这一个函数的契约
是什么"换成"这整个项目的定位是什么"。"""
from sensor import agent
from sensor import verifier

PROJECT_NARRATIVE_TASK = (
    "给这个代码库写一份项目定位描述，这份描述以后会被当作参照标准，去判断"
    "'某个具体函数的行为，支不支撑这个项目正确运行'——不是写营销式的summary，"
    "要具体、要能被拿来对照检查：\n"
    "1. 这个项目是做什么的，面向什么场景/用户，解决什么问题。\n"
    "2. 主要由哪些模块/文件组成，各自的职责边界是什么。\n"
    "3. 项目正确运行时，关键的数据/状态应该保持什么样的不变量或流程——比如"
    "什么操作应该产生什么样的结果、什么状态转换是合法的、什么数据不该被覆盖或"
    "丢失。这一条是最重要的，因为后续要拿它去检查具体函数有没有违反。"
    "**每一条不变量必须写清楚证据范围**：具体是在哪个文件、哪个入口（比如某条"
    "HTTP路由、某个CLI命令分支）观察到这条规则被遵守的，不能只写\"删除操作\""
    "\"确认流程\"这种笼统说法。如果项目里同一类操作存在多个不同入口（比如同一种"
    "删除/生成动作，CLI和HTTP API各有一条独立路径），必须逐个检查每个入口是否"
    "都遵守同一条规则：都遵守就写清楚覆盖了哪几个入口；只在部分入口观察到，就"
    "必须明确指出规则只对这些入口成立、其它入口没有证据支持同一规则，不能把从"
    "一个入口归纳出的模式，不加说明地写成对全部同类入口都成立的通用规则——这是"
    "后续判断时最容易出的错，宁可把不变量的范围写窄、写具体，也不要写成看似"
    "适用全局、实际只验证过一个场景的空泛陈述。\n"
    "4. 设计上有什么突出的特点或明确的取舍。\n"
    "每一条尽量引用具体的文件/入口/关键函数作为依据，不要泛泛而谈。"
)


def describe_project(root: str, verbose: bool = True, explore_max_steps: int = None, verify_max_steps: int = 15) -> dict:
    """给整个项目生成一份定位描述——不是分析某个具体函数，是回答"这个项目
    整体是什么样子"这个问题，复用agent.py的读代码问答能力（跟describe_function
    是同一条生产线，只是问题从"这一个函数的契约是什么"换成"这整个项目的定位
    是什么"）。

    这份描述是"函数行为支不支撑项目"判断的参照标准——没有它，"支不支撑"这个
    问题问不出来，所以是新增行为评判机制的必要前置步骤，不是锦上添花。

    explore_max_steps不传就用agent.answer_question的默认预算（20，照小项目
    校准的）——项目文件数多的时候（比如几十个文件的模块）默认预算读不完，
    该由调用方显式加大，不是改agent.py的全局默认值去影响所有调用方。

    返回 {"narrative", "agent_steps", "agent_hit_cap", "verified",
    "verify_evidence", "verify_reasoning"}，跟describe_function的返回形状
    一致（只是"function"换成了整个项目本身，没有单独的function字段）。"""
    outcome = agent.answer_question(root, PROJECT_NARRATIVE_TASK, verbose=verbose, max_steps=explore_max_steps)
    # 项目叙述一次要核对十几条跨越多个文件的说法，verifier默认的4步（为单函数
    # 场景校准的）明显不够——真实测过，4步内只够读3个文件，远没读完就撞了
    # 上限。项目级叙述的核实预算要大得多，覆盖掉默认值。
    v = verifier.verify_answer(root, PROJECT_NARRATIVE_TASK, outcome["answer"], verbose=verbose, max_steps=verify_max_steps)
    return {
        "narrative": outcome["answer"],
        "agent_steps": len(outcome["steps"]),
        "agent_hit_cap": outcome["hit_cap"],
        "verified": v["verified"],
        "verify_evidence": v["evidence"],
        "verify_reasoning": v["reasoning"],
    }
