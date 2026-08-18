"""不用mcp库的客户端封装（ClientSession），直接手写JSON-RPC消息、
用最原始的subprocess管道发给mcp_server.py，把每一条真实收发的报文原样打印出来。
只是给你看MCP的"裸协议"长什么样，不是读码机正式代码的一部分。
"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "mcp_server.py")
ROOT = r"C:\Users\52396\Desktop\自动剧本生成机\src"

env = {**os.environ, "READCODE_ROOT": ROOT}
proc = subprocess.Popen(
    ["python", SERVER], env=env,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, encoding="utf-8", bufsize=1,
)


def send(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    print(f">>> 发送:\n{line}\n")
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def recv():
    line = proc.stdout.readline()
    print(f"<<< 收到:\n{line.strip()}\n")
    return json.loads(line) if line.strip() else None


# 第1条消息：initialize握手
send({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2026-07-28",
        "capabilities": {},
        "clientInfo": {"name": "手动裸协议演示", "version": "0.1"},
    },
})
recv()

# 第2条：告诉服务端"握手完成了"（这是一条notification，没有id，服务端不会回复）
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# 第3条：真正调用read_file工具
send({
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "read_file", "arguments": {"path": "goal_loop.py"}},
})
result = recv()

print("=" * 50)
print("从收到的报文里，把真正的文件内容摘出来看一眼开头100字：")
text = result["result"]["content"][0]["text"]
print(text[:100])

proc.terminate()
