"""
LLM Provider factory and initialization.
"""
from typing import Optional
from src.config import settings
from src.llm.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    """
    Get LLM provider based on configuration.
    
    Returns:
        Configured LLM provider instance
    
    Raises:
        ValueError: If LLM_BACKEND is not recognized
    """
    backend = settings.llm_backend.lower()
    
    if backend == "gemini":
        from src.llm.gemini import GeminiProvider
        return GeminiProvider()
    
    elif backend == "ollama":
        from src.llm.ollama import OllamaProvider
        return OllamaProvider()
    
    else:
        raise ValueError(f"Unknown LLM backend: {backend}. Use 'gemini' or 'ollama'.")


# Global provider instance (lazy-loaded)
_provider: Optional[LLMProvider] = None


def provider() -> LLMProvider:
    """
    Get or initialize the global LLM provider.
    
    Returns:
        LLM provider instance
    """
    global _provider
    if _provider is None:
        _provider = get_llm_provider()
    return _provider
