"""
RM Agent state definition.
"""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class ToolCall(TypedDict):
    """Represents a tool call in the agent's reasoning trace."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    timestamp: str


class Draft(TypedDict):
    """Represents a draft message."""
    customer_id: str
    customer_name: str
    product_id: str
    message: str
    framework: str
    tone: str


class RMAgentState(TypedDict):
    """State for the Relationship Manager agent."""
    
    # Session / Context
    role: str  # "rm"
    user_query: str
    step: int
    llm_backend: str  # "gemini" or "ollama" (default for all nodes)
    llm_provider: Optional[Any]  # LLM provider instance (default)
    planner_backend: Optional[str]   # override backend for planner node
    executor_backend: Optional[str]  # override backend for executor node
    ollama_model: Optional[str]      # specific ollama model name
    nvidia_model: Optional[str]      # specific nvidia nim model name
    
    # Task planning
    task_plan: List[str]
    current_plan_step: int
    
    # Customer data
    customer_set: List[Dict[str, Any]]  # List of customer objects
    customer_count: int
    
    # Cached analysis
    scores_cache: Dict[str, Dict[str, Any]]  # customer_id -> score
    behaviors_cache: Dict[str, Dict[str, Any]]  # customer_id -> behavior
    product_recs_cache: Dict[str, List[Dict[str, Any]]]  # customer_id -> products
    
    # Messages and drafts
    conversation_history: List[Dict[str, str]]  # [{"role": "user" | "assistant", "content": str}]
    drafts: List[Draft]
    
    # Tool execution trace
    tool_call_log: List[ToolCall]
    
    # Top-N request (extracted from query, e.g. "top 5 customers")
    requested_top_n: Optional[int]

    # Final response
    final_answer: Optional[str]
    error: Optional[str]
