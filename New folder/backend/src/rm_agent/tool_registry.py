"""
Tool registry for RM agent with full access.
"""
from typing import Dict, Any, Callable, List
import json
from src.tools import customer_tool, transaction_tool, scoring_tool, product_tool, message_tool, outreach_tool


# Define tool schemas for function calling
TOOL_SCHEMAS = {
    "query_customers": {
        "name": "query_customers",
        "description": "Search for customers matching specified filters (segment, city, income range, credit score)",
        "parameters": {
            "type": "object",
            "properties": {
                "segment": {
                    "type": "string",
                    "description": "Customer segment: mass, affluent, or premium"
                },
                "city": {
                    "type": "string",
                    "description": "City name"
                },
                "min_income": {
                    "type": "number",
                    "description": "Minimum annual income"
                },
                "max_income": {
                    "type": "number",
                    "description": "Maximum annual income"
                },
                "min_credit_score": {
                    "type": "number",
                    "description": "Minimum credit score"
                },
                "min_balance": {
                    "type": "number",
                    "description": "Minimum average balance"
                }
            }
        }
    },
    "get_customer_profile": {
        "name": "get_customer_profile",
        "description": "Get detailed profile for a specific customer",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                }
            },
            "required": ["customer_id"]
        }
    },
    "get_transaction_summary": {
        "name": "get_transaction_summary",
        "description": "Get transaction summary for a customer over a time window",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                },
                "window_days": {
                    "type": "integer",
                    "description": "Look-back window in days (default 90)"
                }
            },
            "required": ["customer_id"]
        }
    },
    "score_customer_value": {
        "name": "score_customer_value",
        "description": "Calculate customer lifetime value score",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                }
            },
            "required": ["customer_id"]
        }
    },
    "predict_conversion_probability": {
        "name": "predict_conversion_probability",
        "description": "Predict likelihood of customer converting for a product",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                },
                "product_id": {
                    "type": "string",
                    "description": "Product ID"
                }
            },
            "required": ["customer_id", "product_id"]
        }
    },
    "recommend_products": {
        "name": "recommend_products",
        "description": "Get product recommendations for a customer",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                }
            },
            "required": ["customer_id"]
        }
    },
    "draft_outreach_message": {
        "name": "draft_outreach_message",
        "description": "Create a highly personalized WhatsApp outreach message with real loan amounts, EMIs, and behavioral signals",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer CRM ID — used to load real financial data for personalization"
                },
                "customer_name": {
                    "type": "string",
                    "description": "Customer's full name"
                },
                "product_id": {
                    "type": "string",
                    "description": "Product ID (e.g. PL001, CC001, FD001, HL001)"
                },
                "framework": {
                    "type": "string",
                    "description": "Sales framework: AIDA or SPIN",
                    "enum": ["AIDA", "SPIN"]
                },
                "tone": {
                    "type": "string",
                    "description": "Message tone — auto-selected from conversion_probability when omitted",
                    "enum": ["professional", "warm", "urgent"]
                },
                "conversion_probability": {
                    "type": "number",
                    "description": "Probability 0–1 from predict_conversion_probability — used to auto-tune tone"
                },
                "transaction_context": {
                    "type": "object",
                    "description": "Output from get_transaction_summary — used for spend category personalization"
                }
            },
            "required": ["customer_id", "customer_name", "product_id"]
        }
    },
    "send_outreach_message": {
        "name": "send_outreach_message",
        "description": "Send outreach message to customer",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID"
                },
                "phone_number": {
                    "type": "string",
                    "description": "Phone number"
                },
                "message": {
                    "type": "string",
                    "description": "Message to send"
                },
                "product_id": {
                    "type": "string",
                    "description": "Product ID"
                }
            },
            "required": ["customer_id", "phone_number", "message", "product_id"]
        }
    }
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get list of tool schemas for function calling."""
    return list(TOOL_SCHEMAS.values())


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Execute a tool with given arguments, silently dropping any kwargs the
    function doesn't accept so LLM hallucinations don't crash the agent.
    """
    import inspect

    tools = {
        "query_customers": customer_tool.query_customers,
        "get_customer_profile": customer_tool.get_customer_profile,
        "get_transaction_summary": transaction_tool.get_transaction_summary,
        "score_customer_value": scoring_tool.score_customer_value,
        "predict_conversion_probability": scoring_tool.predict_conversion_probability,
        "recommend_products": product_tool.recommend_products,
        "draft_outreach_message": message_tool.draft_outreach_message,
        "send_outreach_message": outreach_tool.send_outreach_message,
    }

    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_fn = tools[tool_name]

    # Strip kwargs the function doesn't accept to survive LLM hallucinations
    sig = inspect.signature(tool_fn)
    valid_params = set(sig.parameters.keys())
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if not has_var_keyword:
        dropped = set(arguments.keys()) - valid_params
        if dropped:
            arguments = {k: v for k, v in arguments.items() if k in valid_params}

    return tool_fn(**arguments)
