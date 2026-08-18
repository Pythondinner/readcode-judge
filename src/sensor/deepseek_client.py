"""
共享的 DeepSeek API 调用封装。brain.py（结构化 JSON 输出）和 writer.py
（自由文本输出）都用这一份，避免重复的 HTTP 请求/错误处理逻辑。
"""

import json
import os
import time

import requests

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

JSON_RETRY_LIMIT = 2  # json_mode下模型偶尔会输出解析不了的JSON——不是内容判断错了，
                       # 是这一次输出格式没守住，值得给几次机会自己纠正，不该直接判整次调用失败。
                       # 这是安全阀，不是无限重试；限制内还是没能解析，照样抛错，不会一直卡下去。

NETWORK_RETRY_LIMIT = 2  # 网络抖动/超时/限流——跟上面的JSON_RETRY_LIMIT是两层不同的
                          # 重试，处理的是完全不同的失败原因：这一层出问题时内容还没
                          # 生成出来，不需要任何"纠正信号"，原样重试就够（跟deep_research_agent
                          # 项目里retry.py的思路一致：网络层失败是外部的、瞬时的，不是模型
                          # 判断的问题，不用像JSON重试那样喂纠正提示）。
NETWORK_RETRY_BASE_DELAY = 1.5  # 秒，线性退避（第n次重试等 base*n 秒），不是指数级，
                                  # 网络问题通常几秒内就过去了，不需要退避得太狠


class ApiCallError(Exception):
    """模型调用失败（网络/超时/限流/返回内容不是预期格式等）。

    调用方应该捕获这个异常并提示用户重试，而不是让整个进程崩掉——
    调用失败时不会有任何副作用发生，上层的 snapshot/草稿都不会被写脏。
    """


def _extract_balanced_json(content: str):
    """从文本里找第一个花括号配平的{...}子串，找不到返回None。手动数括号
    （而不是用正则）是因为要正确跳过字符串内部的花括号和转义引号，正则处理
    这种嵌套/转义场景容易出错。"""
    start = content.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(content)):
        ch = content[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[start:i + 1]
    return None


def _try_repair_json(content: str, error: json.JSONDecodeError):
    """JSON解析失败时，先尝试本地文本修复——不发起新的网络请求，只是看
    能不能把手头这段坏文本本身修好，能修好就直接用，不消耗JSON_RETRY_LIMIT
    的重试次数（重试次数留给真的需要模型重新生成的情况）。分两层兜底，
    参考的是"刑事阅卷Agent"项目verification层的思路：

    1. "Extra data"专属修复：这类错误意味着json在error.pos处已经解析出
       一个完整合法的JSON值，只是后面还有多余内容（实测遇到的两次真实
       失败——goal_loop.py的write_with_check和chat.py的load_env——都是
       这个错误类型，很可能是模型在JSON对象后面又多输出了几个字/换行）。
       直接从这个位置截断，重新解析截断后的部分。
    2. 正则抢救式提取：截断修复不适用或没解析出来时，退一步找文本里第一个
       花括号配平的{...}子串，尝试单独解析它——用于处理"JSON前面混了别的
       文字"这类场景。

    两层都失败返回None，交给上层走原来的纠正性重试（把报错喂回去让模型
    重新生成）。"""
    if error.msg == "Extra data":
        try:
            return json.loads(content[:error.pos])
        except json.JSONDecodeError:
            pass

    candidate = _extract_balanced_json(content)
    if candidate is not None:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _post_with_retry(payload: dict, headers: dict):
    """网络传输层的重试——处理超时/限流/连接失败这类跟模型输出内容无关的
    问题，原样重试即可，不需要任何纠正信号（跟call()内部的JSON内容重试是
    两层不同机制，各自处理不同的失败原因，不要混在一起）。"""
    last_error = None
    for attempt in range(NETWORK_RETRY_LIMIT + 1):
        try:
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < NETWORK_RETRY_LIMIT:
                time.sleep(NETWORK_RETRY_BASE_DELAY * (attempt + 1))
    raise ApiCallError(
        f"请求 DeepSeek API 失败（网络层重试{NETWORK_RETRY_LIMIT}次后仍失败）：{last_error}"
    ) from last_error


def call(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = None,
    return_finish_reason: bool = False,
):
    """调用一次模型。json_mode=True 时返回已解析的 dict，否则返回原始文本。
    max_tokens 不传就用 API 默认值（之前一直是这样，长文本因此被默认值悄悄截断过）。
    return_finish_reason=True 时改为返回 (content_or_dict, finish_reason) 元组，
    finish_reason == "length" 说明是被 max_tokens 截断的，不是模型自己写完的。

    json_mode=True 时，如果模型这一次输出解析不了，不会立刻报错退出——会把
    "上一次输出+具体解析报错"当作新一轮追加进对话，明确告诉模型"格式不对，
    重新来"，再给它最多 JSON_RETRY_LIMIT 次机会自己纠正。这是同一个调用内部
    的、对调用方透明的重试（调用方拿到的要么是解析好的 dict，要么是最终的
    ApiCallError，感知不到中间发生过几轮格式纠正）——跟 goal_loop.py"诊断后
    修复"是同一个思路：给模型一个具体的改进信号，不是盲目再赌一次。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    attempt = 0
    while True:
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = _post_with_retry(
            payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            choice = resp.json()["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError) as e:
            raise ApiCallError(f"API 返回结构异常，不像预期的响应格式：{e}") from e

        if json_mode:
            try:
                content = json.loads(content)
            except json.JSONDecodeError as e:
                repaired = _try_repair_json(content, e)
                if repaired is not None:
                    content = repaired
                else:
                    attempt += 1
                    if attempt > JSON_RETRY_LIMIT:
                        raise ApiCallError(
                            f"模型返回的内容连续{JSON_RETRY_LIMIT}次重试后仍不是合法 JSON：{e}"
                        ) from e
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"你上一条回复不是合法的JSON，解析时报错：{e}。"
                                   f"请只输出一个合法的JSON对象，不要有任何其他文字。",
                    })
                    continue

        return (content, finish_reason) if return_finish_reason else content
