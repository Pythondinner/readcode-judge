"""第3步：在Flask源码这个更大、有子目录层级的代码库上，把step1（无MCP）和
step2（MCP）两版agent各跑一遍新考卷，分别存结果，方便对照——这次要看的不是
"分数一样不一样"（已经在自动剧本生成机那个小代码库上验证过协议本身没问题），
是"步数够不够用、有没有撞上MAX_STEPS上限"，这才是判断要不要做context管理的
真实依据。
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import agent
import agent_mcp
import deepseek_client

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRC_DIR)
TARGET_CODEBASE = r"C:\FPAN\Python312\Lib\site-packages\flask"
EVAL_SET_PATH = os.path.join(ROOT, "eval_set", "step3_flask考卷.json")


def load_env(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def run_step1(questions):
    results = []
    for q in questions:
        print(f"\n[step1/直接调用] 第{q['id']}题：{q['question']}")
        try:
            outcome = agent.answer_question(TARGET_CODEBASE, q["question"])
        except deepseek_client.ApiCallError as e:
            outcome = {"answer": f"（调用失败：{e}）", "steps": [], "hit_cap": False}
        print(f"  答：{outcome['answer']}")
        print(f"  步数：{len(outcome['steps'])}，撞上限：{outcome['hit_cap']}")
        results.append({
            "id": q["id"], "tier": q["tier"], "question": q["question"],
            "standard_answer": q["answer"], "agent_answer": outcome["answer"],
            "steps_taken": len(outcome["steps"]), "hit_cap": outcome["hit_cap"],
        })
    return results


async def run_step2(questions):
    results = []
    for q in questions:
        print(f"\n[step2/MCP] 第{q['id']}题：{q['question']}")
        try:
            outcome = await agent_mcp.answer_question(TARGET_CODEBASE, q["question"])
        except deepseek_client.ApiCallError as e:
            outcome = {"answer": f"（调用失败：{e}）", "steps": [], "hit_cap": False}
        print(f"  答：{outcome['answer']}")
        print(f"  步数：{len(outcome['steps'])}，撞上限：{outcome['hit_cap']}")
        results.append({
            "id": q["id"], "tier": q["tier"], "question": q["question"],
            "standard_answer": q["answer"], "agent_answer": outcome["answer"],
            "steps_taken": len(outcome["steps"]), "hit_cap": outcome["hit_cap"],
        })
    return results


def main():
    load_env(os.path.join(ROOT, ".env"))
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        exam = json.load(f)
    questions = exam["questions"]

    print("=" * 20, "step1（无MCP，直接函数调用）", "=" * 20)
    step1_results = run_step1(questions)
    with open(os.path.join(ROOT, "eval_set", "step3_step1_结果.json"), "w", encoding="utf-8") as f:
        json.dump(step1_results, f, ensure_ascii=False, indent=2)

    print("\n\n" + "=" * 20 + " step2（MCP） " + "=" * 20)
    step2_results = asyncio.run(run_step2(questions))
    with open(os.path.join(ROOT, "eval_set", "step3_step2_结果.json"), "w", encoding="utf-8") as f:
        json.dump(step2_results, f, ensure_ascii=False, indent=2)

    print("\n\n全部跑完，两份结果分别存到 step3_step1_结果.json / step3_step2_结果.json")


if __name__ == "__main__":
    main()
