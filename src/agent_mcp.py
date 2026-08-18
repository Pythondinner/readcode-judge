"""读码机 step2：跟 agent.py（step1）几乎一样的循环逻辑，唯一的区别是
"读文件/列目录"这两个动作不再是直接调用 tools.py 的函数，而是通过 MCP
协议连到 mcp_server.py（作为子进程启动）去调用。

刻意保持"要不要继续读、什么时候给答案"这部分逻辑跟 step1 完全一致（连
SYSTEM_PROMPT、MAX_STEPS、transcript 拼接方式都没有变）——这样如果这一版
的分数跟 step1 不一样，就能确定差异来自"换了协议"本身，不是因为顺便改动
了别的东西，对照实验要一次只变一个变量。

MCP client 的调用是异步的（async/await），所以这一版的核心函数是 async def，
跟 step1 的同步版本比多了这一层，是接入协议本身带来的复杂度，不是我们自己
加的。deepseek_client.call 本身还是同步调用，直接在 async 函数里调用，
不会出错，只是不是"真正并发"的写法——对这个项目的规模来说足够用，不需要
为了这一点复杂度去重写 deepseek_client.py。
"""
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import deepseek_client
from agent import MAX_STEPS, SYSTEM_PROMPT, repeat_notice  # 复用step1的常量和逻辑，确保是同一份


def _extract_text(call_tool_result) -> str:
    """MCP工具调用的返回结构里，正文在content列表的TextContent.text里。"""
    if call_tool_result.is_error:
        parts = [c.text for c in call_tool_result.content if hasattr(c, "text")]
        return "（工具调用出错：" + "; ".join(parts) + "）"
    parts = [c.text for c in call_tool_result.content if hasattr(c, "text")]
    return "\n".join(parts)


async def answer_question(root: str, question: str, verbose: bool = True) -> dict:
    """跟 agent.answer_question 签名/返回值格式完全一致，方便run_eval_mcp.py
    跟run_eval.py共用同样的结果记录格式。"""
    server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env={**os.environ, "READCODE_ROOT": root},
    )

    transcript = f"<question>{question}</question>\n\n（还没有做任何操作。）"
    steps = []
    last_action_key = None
    repeat_count = 0

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for step_num in range(1, MAX_STEPS + 1):
                result = deepseek_client.call(
                    SYSTEM_PROMPT, transcript, temperature=0.2, json_mode=True,
                )
                action = result.get("action")

                if action == "final_answer":
                    answer = result.get("answer", "")
                    steps.append({"step": step_num, "action": "final_answer", "answer": answer})
                    if verbose:
                        print(f"    [第{step_num}步] final_answer")
                    return {"answer": answer, "steps": steps, "hit_cap": False}

                path = result.get("path", "")
                pattern = result.get("pattern", "")
                start_line = result.get("start_line")
                end_line = result.get("end_line")
                action_key = (action, path, pattern, start_line, end_line)
                repeat_count = repeat_count + 1 if action_key == last_action_key else 0
                last_action_key = action_key
                if action == "search_code":
                    detail = f"{path} pattern={pattern!r}"
                elif action == "read_file" and (start_line or end_line):
                    detail = f"{path}[{start_line}:{end_line}]"
                else:
                    detail = path

                if action == "list_directory":
                    tool_result = await session.call_tool(action, {"path": path})
                    observation = _extract_text(tool_result)
                elif action == "read_file":
                    args = {"path": path}
                    if start_line is not None:
                        args["start_line"] = start_line
                    if end_line is not None:
                        args["end_line"] = end_line
                    tool_result = await session.call_tool(action, args)
                    observation = _extract_text(tool_result)
                elif action == "search_code":
                    tool_result = await session.call_tool(action, {"pattern": pattern, "path": path})
                    observation = _extract_text(tool_result)
                else:
                    observation = f"（未识别的action：{action!r}，请重新按格式输出）"

                if repeat_count >= 1:
                    observation += repeat_notice(action, detail, repeat_count)

                steps.append({"step": step_num, "action": action, "path": path, "pattern": pattern, "repeat_count": repeat_count})
                if verbose:
                    flag = f"（重复第{repeat_count + 1}次）" if repeat_count >= 1 else ""
                    print(f"    [第{step_num}步，经MCP] {action} {detail} {flag}")

                transcript += (
                    f"\n\n=== 第{step_num}步 ===\n"
                    f"你的动作：{json.dumps(result, ensure_ascii=False)}\n"
                    f"观察结果：{observation}"
                )

    return {"answer": "（超过最大步数，未能得出答案）", "steps": steps, "hit_cap": True}
