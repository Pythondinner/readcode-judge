"""跟 run_eval.py 完全对应，唯一区别是调用 agent_mcp（走MCP协议）而不是
agent（直接函数调用），结果存到 step2_结果.json，方便跟 step1_结果.json
逐题对照，检查换协议本身有没有引入新问题。
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from sensor import agent_mcp
from sensor import deepseek_client

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRC_DIR)
TARGET_CODEBASE = r"C:\Users\52396\Desktop\自动剧本生成机\src"
EVAL_SET_PATH = os.path.join(ROOT, "eval_set", "起步考卷.json")
RESULTS_PATH = os.path.join(ROOT, "eval_set", "step2_结果.json")


def load_env(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


async def main():
    load_env(os.path.join(ROOT, ".env"))
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        exam = json.load(f)

    results = []
    for q in exam["questions"]:
        print(f"\n==== 第{q['id']}题（{q['tier']}）====")
        print(f"题目：{q['question']}")
        try:
            outcome = await agent_mcp.answer_question(TARGET_CODEBASE, q["question"])
        except deepseek_client.ApiCallError as e:
            outcome = {"answer": f"（调用失败：{e}）", "steps": [], "hit_cap": False}
        print(f"agent回答：{outcome['answer']}")
        print(f"标准答案：{q['answer']}")
        results.append({
            "id": q["id"], "tier": q["tier"], "question": q["question"],
            "standard_answer": q["answer"], "agent_answer": outcome["answer"],
            "steps_taken": len(outcome["steps"]), "hit_cap": outcome["hit_cap"],
        })

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\n全部跑完，结果存到 {RESULTS_PATH}，对照 step1_结果.json 看协议接入有没有引入新问题。")


if __name__ == "__main__":
    asyncio.run(main())
