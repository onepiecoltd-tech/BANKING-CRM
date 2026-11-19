"""
Ollama LLM Provider — uses the /api/chat endpoint with format:json
so structured tool-call output is reliable even on smaller models.
"""
import json
import requests
from typing import Optional, Dict, Any, List
from src.llm.base import LLMProvider, LLMMessage
from src.config import settings


class OllamaProvider(LLMProvider):
    """Ollama provider for local free inference."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code != 200:
                raise RuntimeError("Ollama server not responding")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}: {e}")

    def get_model_name(self) -> str:
        return self.model

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        force_json: bool = False,
    ) -> str:
        """Send messages to Ollama /api/chat and return the reply text."""
        chat_messages = []
        for msg in messages:
            role = "assistant" if msg.role == "assistant" else msg.role
            chat_messages.append({"role": role, "content": msg.content})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if force_json:
            payload["format"] = "json"

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=180,
            )
            if r.status_code != 200:
                raise RuntimeError(f"Ollama error {r.status_code}: {r.text[:300]}")
            data = r.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def _complete_json(self, messages: List[LLMMessage], temperature: float = 0.2, max_tokens: int = 1024) -> str:
        """Complete with format=json enforced, stripping any think-tags from reasoning models."""
        raw = self.complete(messages, temperature=temperature, max_tokens=max_tokens, force_json=True)
        # Strip <think>…</think> blocks that deepseek-r1 / qwen3 emit
        import re
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw

    def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        functions_desc = json.dumps(functions, indent=2)
        system = (
            "You are a JSON-only assistant. Respond with a single JSON object, no markdown, no explanation.\n"
            f"Available tools:\n{functions_desc}\n"
            'Output format: {"function_name": "...", "arguments": {...}}'
        )
        all_messages = [LLMMessage("system", system)] + messages
        text = self._complete_json(all_messages, temperature=temperature, max_tokens=max_tokens)

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"function_name": "none", "arguments": {}}
