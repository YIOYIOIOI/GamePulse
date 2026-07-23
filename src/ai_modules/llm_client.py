"""
OpenAI 兼容 LLM 客户端（requests 直调，零新增依赖）

历史问题：strategy/summarizer 模块依赖 openai/anthropic SDK + 对应 key，
环境里两者都没有，导致"LLM 客户端未初始化"，AI 模块从未真正跑通。

方案：绝大多数国内外网关（OpenAI / 火山方舟 Ark / DeepSeek / 通义 等）都
提供 OpenAI 兼容的 /chat/completions 端点。直接用 requests（本项目既有依赖）
调这个端点，通过环境变量配置即可切换供应商：

    GAMEPULSE_LLM_BASE_URL   例: https://ark.cn-beijing.volces.com/api/v3
                             （默认 https://api.openai.com/v1）
    GAMEPULSE_LLM_API_KEY    兜底顺序: OPENAI_API_KEY -> ARK_API_KEY
    GAMEPULSE_LLM_MODEL      例: gpt-4o-mini / doubao-xxx（Ark 用推理接入点 ID）

另提供 MockLLMClient 供离线测试——LLM 链路必须在没有 key 的 CI 里也可验证。
"""

from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT = 60
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMClientError(RuntimeError):
    """LLM 调用失败（网络/鉴权/非法响应）。"""


class OpenAICompatibleClient:
    """极简 OpenAI 兼容 chat 客户端：一个方法、显式超时、幂等重试。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = "gpt-4o-mini",
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(
        self,
        user: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if resp.status_code in RETRYABLE_STATUS:
                    last_error = LLMClientError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                time.sleep(1.5 * (attempt + 1))
            except (KeyError, IndexError, ValueError) as e:
                raise LLMClientError(f"响应结构异常: {e}") from e

        raise LLMClientError(f"LLM 调用失败（重试 {self.max_retries} 次后）: {last_error}")


class MockLLMClient:
    """离线 mock：链路测试用，返回可断言的固定文本并记录收到的 prompt。"""

    def __init__(self, canned_response: str = "[MOCK] 策略生成链路连通。"):
        self.canned_response = canned_response
        self.calls: list[dict] = []

    def chat(self, user: str, system: str | None = None, **kwargs) -> str:
        self.calls.append({"system": system, "user": user, **kwargs})
        return self.canned_response


def from_env(config: dict | None = None) -> OpenAICompatibleClient | None:
    """
    从环境变量构建客户端；没有 key 返回 None（调用方自行降级）。

    优先级: GAMEPULSE_LLM_API_KEY > OPENAI_API_KEY > ARK_API_KEY
    """
    config = config or {}
    llm_cfg = config.get("llm", {}).get("openai_compatible", {})

    api_key = (
        os.getenv("GAMEPULSE_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ARK_API_KEY")
        or llm_cfg.get("api_key")
    )
    if not api_key:
        logger.warning(
            "未配置 LLM key（GAMEPULSE_LLM_API_KEY / OPENAI_API_KEY / ARK_API_KEY），LLM 功能降级关闭"
        )
        return None

    return OpenAICompatibleClient(
        api_key=api_key,
        base_url=os.getenv("GAMEPULSE_LLM_BASE_URL") or llm_cfg.get("base_url", DEFAULT_BASE_URL),
        model=os.getenv("GAMEPULSE_LLM_MODEL") or llm_cfg.get("model", "gpt-4o-mini"),
    )
