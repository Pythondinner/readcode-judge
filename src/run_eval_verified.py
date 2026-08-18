"""在起步考卷12题上，把 agent.answer_question 和 verifier.verify_answer
串起来跑一遍——不是只测3个手挑的案例了，是在正式的、已经有人工标准答案的
考卷规模上看这层核实真实好不好用：verifier的判断（true/false/None）
跟"这个答案实际上对不对（人工标准答案说了算）"符不符合，才是核实层
在真实场景下靠不靠谱的证据。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from sensor import agent
from sensor import deepseek_client
from sensor import verifier

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRC_DIR)
TARGET_CODEBASE = r"C:\Users\52396\Desktop\自动剧本生成机\src"
EVAL_SET_PATH = os.path.join(ROOT, "eval_set", "起步考卷.json")
RESULTS_PATH = os.path.join(ROOT, "eval_set", "step_verified_结果.json")


def load_env(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env(os.path.join(ROOT, ".env"))
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        exam = json.load(f)

    results = []
    for q in exam["questions"]:
        print(f"\n==== 第{q['id']}题（{q['tier']}）====")
        print(f"题目：{q['question']}")
        try:
            outcome = agent.answer_question(TARGET_CODEBASE, q["question"], verbose=False)
        except deepseek_client.ApiCallError as e:
            outcome = {"answer": f"（调用失败：{e}）", "steps": [], "hit_cap": False}
        print(f"agent回答：{outcome['answer']}")
        print(f"标准答案：{q['answer']}")

        try:
            v = verifier.verify_answer(TARGET_CODEBASE, q["question"], outcome["answer"], verbose=False)
        except deepseek_client.ApiCallError as e:
            v = {"verified": None, "evidence": "", "reasoning": f"核实调用失败：{e}", "steps": 0, "hit_cap": False}
        mark = {"True": "✓ 核实通过", "False": "✗ 核实不通过", "None": "△ 未核实完"}[str(v["verified"])]
        print(f"核实结果：{mark}（{v['reasoning']}）")

        results.append({
            "id": q["id"], "tier": q["tier"], "question": q["question"],
            "standard_answer": q["answer"], "agent_answer": outcome["answer"],
            "agent_steps": len(outcome["steps"]), "agent_hit_cap": outcome["hit_cap"],
            "verified": v["verified"], "verify_evidence": v["evidence"],
            "verify_reasoning": v["reasoning"], "verify_steps": v["steps"],
        })

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\n全部跑完，结果存到 {RESULTS_PATH}")


if __name__ == "__main__":
    main()
