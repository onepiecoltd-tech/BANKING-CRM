"""
Transaction analysis tools.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func
from src.database import SessionLocal, Transaction


def get_transaction_summary(
    customer_id: str,
    window_days: int = 90
) -> Dict[str, Any]:
    """
    Get transaction summary for a customer.
    
    Args:
        customer_id: Customer ID
        window_days: Look-back window in days
    
    Returns:
        Transaction summary including spend, velocity, balance trend
    """
    session = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)
        
        transactions = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= cutoff_date
        ).all()
        
        if not transactions:
            return {
                "customer_id": customer_id,
                "window_days": window_days,
                "total_count": 0,
                "total_spend": 0.0,
                "total_inflow": 0.0,
                "total_outflow": 0.0,
                "avg_transaction": 0.0,
                "max_transaction": 0.0,
                "min_transaction": 0.0,
                "categories": {},
                "channels": {},
            }
        
        # Separate inflow (salary, transfer_in) vs outflow
        inflows = [t for t in transactions if "salary" in t.category.lower() if t.category]
        outflows = [t for t in transactions if not ("salary" in t.category.lower() if t.category else False)]
        
        total_spend = sum(t.amount for t in transactions)
        total_inflow = sum(t.amount for t in inflows)
        total_outflow = sum(t.amount for t in outflows)
        
        # Category breakdown
        categories = {}
        for txn in transactions:
            cat = txn.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + txn.amount
        
        # Channel breakdown
        channels = {}
        for txn in transactions:
            ch = txn.channel or "unknown"
            channels[ch] = channels.get(ch, 0) + txn.amount
        
        return {
            "customer_id": customer_id,
            "window_days": window_days,
            "total_count": len(transactions),
            "total_spend": round(total_spend, 2),
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2),
            "avg_transaction": round(total_spend / len(transactions), 2) if transactions else 0,
            "max_transaction": round(max(t.amount for t in transactions), 2),
            "min_transaction": round(min(t.amount for t in transactions), 2),
            "categories": {k: round(v, 2) for k, v in categories.items()},
            "channels": {k: round(v, 2) for k, v in channels.items()},
        }
    finally:
        session.close()


def analyze_spending_velocity(
    customer_id: str,
    recent_days: int = 30,
    prior_days: int = 30
) -> Dict[str, Any]:
    """
    Compare recent spending velocity to prior period.
    
    Args:
        customer_id: Customer ID
        recent_days: Recent period window
        prior_days: Prior period window
    
    Returns:
        Velocity comparison with change percentage
    """
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(days=recent_days)
        prior_start = now - timedelta(days=recent_days + prior_days)
        prior_end = recent_cutoff
        
        recent_txns = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= recent_cutoff
        ).all()
        
        prior_txns = session.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.date >= prior_start,
            Transaction.date < prior_end
        ).all()
        
        recent_spend = sum(t.amount for t in recent_txns) if recent_txns else 0
        prior_spend = sum(t.amount for t in prior_txns) if prior_txns else 0
        
        pct_change = (
            ((recent_spend - prior_spend) / prior_spend * 100)
            if prior_spend > 0 else 0
        )
        
        return {
            "customer_id": customer_id,
            "recent_period_days": recent_days,
            "recent_spend": round(recent_spend, 2),
            "prior_spend": round(prior_spend, 2),
            "pct_change": round(pct_change, 2),
            "trend": "increasing" if pct_change > 10 else "decreasing" if pct_change < -10 else "stable",
        }
    finally:
        session.close()
