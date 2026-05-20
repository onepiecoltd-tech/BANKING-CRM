"""
LangGraph construction for RM Agent.
"""
from langgraph.graph import StateGraph, END
from src.rm_agent.state import RMAgentState
from src.rm_agent.nodes import planner_node, executor_node, reflector_node, responder_node


def build_rm_agent_graph():
    """
    Build the LangGraph workflow for RM agent.
    
    Flow: Planner -> Executor ↔ Reflector -> Responder -> END
    """
    graph = StateGraph(RMAgentState)
    
    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("responder", responder_node)
    
    # Add edges
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reflector")
    
    # Conditional: reflector decides to repeat executor or go to responder
    def should_continue_executing(state):
        if state.get("step") == 3:
            return "responder"
        elif state.get("step") == 99:
            return "responder"  # Error handling
        else:
            return "executor"
    
    graph.add_conditional_edges(
        "reflector",
        should_continue_executing,
        {
            "executor": "executor",
            "responder": "responder"
        }
    )
    
    graph.add_edge("responder", END)
    
    # Set entry point
    graph.set_entry_point("planner")
    
    return graph.compile()


def create_initial_state(
    user_query: str,
    llm_backend: str = "ollama",
    llm_provider=None,
    planner_backend: str | None = None,
    executor_backend: str | None = None,
    ollama_model: str | None = None,
    nvidia_model: str | None = None,
) -> RMAgentState:
    """Create initial state for a new agent run."""
    return RMAgentState(
        role="rm",
        user_query=user_query,
        step=0,
        llm_backend=llm_backend,
        llm_provider=llm_provider,
        planner_backend=planner_backend,
        executor_backend=executor_backend,
        ollama_model=ollama_model,
        nvidia_model=nvidia_model,
        task_plan=[],
        current_plan_step=0,
        customer_set=[],
        customer_count=0,
        scores_cache={},
        behaviors_cache={},
        product_recs_cache={},
        conversation_history=[{"role": "user", "content": user_query}],
        drafts=[],
        tool_call_log=[],
        requested_top_n=None,
        final_answer=None,
        error=None,
    )
