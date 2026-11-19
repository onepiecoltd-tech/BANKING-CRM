"""
LLM Provider abstraction for pluggable LLM backends.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class LLMMessage:
    """Represents a message in LLM conversation."""
    
    def __init__(self, role: str, content: str):
        """
        Args:
            role: "system", "user", or "assistant"
            content: Message content
        """
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name being used."""
        pass
    
    @abstractmethod
    def complete(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate completion from messages.
        
        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature (0-1)
            max_tokens: Max response length
        
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        Generate function call from messages.
        
        Args:
            messages: List of LLMMessage objects
            functions: List of function definitions (OpenAI format)
            temperature: Sampling temperature
            max_tokens: Max response length
        
        Returns:
            Function call result {function_name, arguments}
        """
        pass


# Implementations will be in separate files
