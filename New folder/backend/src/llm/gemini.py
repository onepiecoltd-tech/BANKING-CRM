"""
Gemini LLM Provider — uses the new google-genai SDK (v2+).
"""
import json
import time
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from src.llm.base import LLMProvider, LLMMessage
from src.config import settings


class GeminiProvider(LLMProvider):
    """Gemini LLM provider using google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment or config")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-flash-latest"

    def get_model_name(self) -> str:
        return self.model_name

    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> str:
        """Generate completion from messages with retry on quota errors."""
        # Split out system prompt and build contents list
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=msg.content)]))
            elif msg.role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part(text=msg.content)]))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        retry_count = 0
        while retry_count < max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "resource_exhausted" in err.lower():
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise RuntimeError(
                            f"Gemini API quota exceeded after {max_retries} retries. "
                            "Consider switching to Ollama by setting LLM_BACKEND=ollama in your .env"
                        )
                    wait = 2 ** retry_count
                    print(f"Quota exceeded. Retrying in {wait}s ({retry_count}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"Gemini API error: {err}")

    def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        functions_desc = json.dumps(functions, indent=2)
        system_prompt = (
            f'You must respond with a JSON object: {{"function_name": "str", "arguments": {{...}}}}\n'
            f"Available functions:\n{functions_desc}\nChoose the most appropriate function."
        )
        all_messages = [LLMMessage("system", system_prompt)] + messages
        response_text = self.complete(all_messages, temperature=temperature, max_tokens=max_tokens)

        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response_text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"function_name": "none", "arguments": {"error": "Failed to parse function call"}}
