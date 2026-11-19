"""
NVIDIA NIM LLM Provider — OpenAI-compatible endpoint.
Supports Llama 3.1, Nemotron, Mixtral and other models on NVIDIA's cloud.
"""
import json
from typing import Optional, Dict, Any, List
from openai import OpenAI
from src.llm.base import LLMProvider, LLMMessage
from src.config import settings

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Best free-tier model on NVIDIA NIM for instruction following
DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"


class NvidiaProvider(LLMProvider):
    """NVIDIA NIM provider using the OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.nvidia_api_key
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set in environment or config")

        self.model_name = model or settings.nvidia_model or DEFAULT_MODEL
        self.client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=self.api_key,
        )

        # Quick connectivity check
        try:
            self.client.models.list()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to NVIDIA NIM: {e}")

    def get_model_name(self) -> str:
        return self.model_name

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send messages to NVIDIA NIM and return reply text."""
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=chat_messages,
            temperature=min(temperature, 1.0),  # NIM caps at 1.0
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """JSON-mode function calling via system prompt (NIM compatible)."""
        functions_desc = json.dumps(functions, indent=2)
        system = (
            "You are a JSON-only assistant. Respond with a single JSON object, no markdown.\n"
            f"Available tools:\n{functions_desc}\n"
            'Output format: {"function_name": "...", "arguments": {...}}'
        )
        all_messages = [LLMMessage("system", system)] + messages
        text = self.complete(all_messages, temperature=temperature, max_tokens=max_tokens)

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"function_name": "none", "arguments": {}}
