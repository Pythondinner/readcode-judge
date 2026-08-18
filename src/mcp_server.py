"""读码机 step2：把 tools.py 里的两个函数包成一个真正的 MCP server。

跟 step1 的区别只在"工具怎么被调用"这一层：step1 是 agent.py 直接 import
tools.py 的函数来调用；这里改成通过 MCP 协议——工具定义、调用方式都遵循
标准协议格式，任何支持 MCP 的客户端（不只是我们自己写的 agent_mcp.py）都能
连上来用这两个工具，不是本项目专属的。

安全边界的检查逻辑直接复用 tools.py 的 _resolve，不重新写一遍——这是
安全相关的代码，只应该有一份实现，两边分别维护容易出现"改了一边忘了改
另一边"的问题。

用法：作为子进程被 agent_mcp.py 启动，通过环境变量 READCODE_ROOT 指定
要读的目标代码库根目录（不是这个MCP server自己所在的目录）。
"""
import os

from mcp.server.fastmcp import FastMCP

import tools

ROOT = os.environ.get("READCODE_ROOT")
if not ROOT:
    raise SystemExit("必须设置环境变量 READCODE_ROOT，指定要读的目标代码库根目录")

server = FastMCP(
    name="读码机-filesystem",
    instructions="提供对一个指定代码库根目录的只读访问：列目录、读文件，不能访问根目录以外的路径。",
)


@server.tool()
def list_directory(path: str = "") -> str:
    """列出 path（相对代码库根目录的路径，根目录本身用空字符串）下的文件/子目录名。"""
    return tools.list_directory(ROOT, path)


@server.tool()
def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """读 path（相对代码库根目录的文件路径）这个文件的内容。不传行号范围
    读整个文件；传了就只读这个范围（从1开始计数，闭区间）。"""
    return tools.read_file(ROOT, path, start_line, end_line)


@server.tool()
def search_code(pattern: str, path: str = "") -> str:
    """在代码库根目录（或 path 指定的子目录）内递归搜索 pattern（纯文本子串
    匹配），返回匹配到的"文件路径:行号: 内容"列表。"""
    return tools.search_code(ROOT, pattern, path)


if __name__ == "__main__":
    server.run(transport="stdio")
