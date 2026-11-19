"""
Streamlit UI for RM Agent.
"""
import streamlit as st
import json
from datetime import datetime
from src.database import init_db
from src.rm_agent.graph import build_rm_agent_graph, create_initial_state
from src.config import settings


def get_llm_provider_from_ui():
    """Get LLM provider based on UI selection."""
    backend = st.session_state.get("llm_backend", settings.llm_backend)
    backend = backend.lower()
    
    if backend == "gemini":
        from src.llm.gemini import GeminiProvider
        return GeminiProvider()
    elif backend == "ollama":
        from src.llm.ollama import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"Unknown LLM backend: {backend}")


def init_app():
    """Initialize the Streamlit app."""
    st.set_page_config(
        page_title="Banking CRM Agent",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database if needed
    try:
        init_db()
    except:
        pass  # DB might already exist
    
    # Initialize session state
    if "llm_backend" not in st.session_state:
        st.session_state.llm_backend = settings.llm_backend
    
    if "last_backend" not in st.session_state:
        st.session_state.last_backend = settings.llm_backend
    
    if "agent_graph" not in st.session_state:
        st.session_state.agent_graph = build_rm_agent_graph()
    
    if "execution_history" not in st.session_state:
        st.session_state.execution_history = []


def main():
    """Main app logic."""
    init_app()
    
    # Header
    st.title("🏦 Banking CRM Agent")
    st.markdown("**Agentic AI for Relationship Manager use cases**")
    
    # Sidebar with information
    with st.sidebar:
        st.header("📋 About")
        st.markdown("""
This agent helps Relationship Managers:
- Find high-value customers
- Score customer value
- Recommend products
- Draft personalized messages
- Plan outreach campaigns
        """)
        
        st.divider()
        
        st.header("🔧 Configuration")
        llm_backend = st.selectbox("LLM Backend", ["gemini", "ollama"], key="llm_backend")
        
        # Show backend status
        if llm_backend == "ollama":
            st.info("✅ Using local Ollama (unlimited, free)")
        else:
            st.warning("⚠️ Using Gemini API (may have quota limits)")
        
        #crm_backend = st.selectbox("CRM Backend", ["sqlite", "hubspot"])
        
        st.divider()
        
        st.header("📊 Stats")
        st.metric("Total Executions", len(st.session_state.execution_history))
    
    # Main chat interface
    st.header("💬 Agent Conversation")
    
    # Chat history display
    if st.session_state.execution_history:
        for execution in st.session_state.execution_history[-5:]:  # Show last 5
            with st.chat_message("user"):
                st.write(execution["query"])
            with st.chat_message("assistant"):
                st.write(execution["response"])
            if execution.get("tool_calls"):
                with st.expander("📋 Tool Calls Log"):
                    for call in execution["tool_calls"][:10]:  # Show first 10
                        st.code(f"{call['tool_name']}({call['arguments']})\n→ {call['result'][:200]}...", language="json")
    
    # Input for new query
    user_input = st.text_area("What would you like to do?", placeholder="E.g., 'Find high-value customers likely to convert for personal loan'")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        execute_button = st.button("Execute", type="primary", use_container_width=True)
    
    with col2:
        clear_button = st.button("Clear", use_container_width=True)
    
    # Execute query
    if execute_button and user_input:
        with st.spinner("🤔 Agent is thinking..."):
            try:
                # Get selected LLM backend
                selected_backend = st.session_state.get("llm_backend", "gemini")
                
                # Create LLM provider for this execution
                llm_provider = get_llm_provider_from_ui()
                
                # Create initial state with the selected backend and provider
                initial_state = create_initial_state(
                    user_input,
                    llm_backend=selected_backend,
                    llm_provider=llm_provider
                )
                
                # Run the graph
                final_state = st.session_state.agent_graph.invoke(initial_state)
                
                # Store execution
                execution_record = {
                    "query": user_input,
                    "response": final_state.get("final_answer", "No response"),
                    "tool_calls": final_state.get("tool_call_log", []),
                    "customers_found": len(final_state.get("customer_set", [])),
                    "drafts_created": len(final_state.get("drafts", [])),
                    "timestamp": datetime.now().isoformat()
                }
                
                st.session_state.execution_history.append(execution_record)
                
                # Display results
                st.success("✅ Execution Complete")
                
                # Main response
                st.subheader("📝 Response")
                st.write(final_state.get("final_answer", "No response"))
                
                # Results breakdown
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Customers Found", len(final_state.get("customer_set", [])))
                with col2:
                    st.metric("Profiles Scored", len(final_state.get("scores_cache", {})))
                with col3:
                    st.metric("Messages Drafted", len(final_state.get("drafts", [])))
                with col4:
                    st.metric("Tool Calls", len(final_state.get("tool_call_log", [])))
                
                # Customers table
                if final_state.get("customer_set"):
                    st.subheader("👥 Customers Found")
                    import pandas as pd
                    df = pd.DataFrame(final_state["customer_set"][:20])
                    st.dataframe(df, use_container_width=True)
                
                # Drafts preview
                if final_state.get("drafts"):
                    st.subheader("💌 Message Drafts")
                    for i, draft in enumerate(final_state["drafts"][:3]):
                        with st.expander(f"Draft {i+1}: {draft['customer_name']}"):
                            st.write(f"**Product:** {draft['product_id']}")
                            st.write(f"**Framework:** {draft['framework']} | **Tone:** {draft['tone']}")
                            st.code(draft['message'])
                
                # Tool calls log
                if final_state.get("tool_call_log"):
                    with st.expander("🔧 Tool Execution Log"):
                        for i, call in enumerate(final_state["tool_call_log"]):
                            st.write(f"**Call {i+1}: {call['tool_name']}**")
                            st.json({"arguments": call["arguments"]})
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc(), language="python")
    
    if clear_button:
        st.session_state.execution_history = []
        st.rerun()


if __name__ == "__main__":
    main()
