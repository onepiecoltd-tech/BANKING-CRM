"""
Customer query and profile tools.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import and_
from src.database import SessionLocal, Customer


def query_customers(
    segment: str = None,
    city: str = None,
    min_income: float = None,
    max_income: float = None,
    min_credit_score: int = None,
    min_balance: float = None,
    has_credit_card: bool = None,
    has_personal_loan: bool = None,
    has_home_loan: bool = None,
    has_fd: bool = None,
    min_relationship_years: int = None,
    dormant: bool = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Query customers with filters.

    Args:
        segment: Customer segment (mass, affluent, premium)
        city: City name
        min_income: Minimum annual income
        max_income: Maximum annual income
        min_credit_score: Minimum credit score
        min_balance: Minimum average balance
        has_credit_card: Filter by credit card ownership
        has_personal_loan: Filter by personal loan ownership
        has_home_loan: Filter by home loan ownership
        has_fd: Filter by fixed deposit ownership
        min_relationship_years: Minimum years as customer (loyalty)
        dormant: If True, customers not contacted in last 90 days
        limit: Max results to return

    Returns:
        List of matching customer profiles
    """
    from datetime import datetime, timedelta

    session = SessionLocal()
    try:
        query = session.query(Customer)

        if segment:
            query = query.filter(Customer.segment == segment.lower())
        if city:
            query = query.filter(Customer.city == city)
        if min_income:
            query = query.filter(Customer.annual_income >= min_income)
        if max_income:
            query = query.filter(Customer.annual_income <= max_income)
        if min_credit_score:
            query = query.filter(Customer.credit_score >= min_credit_score)
        if min_balance:
            query = query.filter(Customer.monthly_avg_balance >= min_balance)
        if has_credit_card is not None:
            query = query.filter(Customer.has_credit_card == has_credit_card)
        if has_personal_loan is not None:
            query = query.filter(Customer.has_personal_loan == has_personal_loan)
        if has_home_loan is not None:
            query = query.filter(Customer.has_home_loan == has_home_loan)
        if has_fd is not None:
            query = query.filter(Customer.has_fd == has_fd)
        if min_relationship_years:
            query = query.filter(Customer.relationship_years >= min_relationship_years)
        if dormant:
            cutoff = datetime.utcnow() - timedelta(days=90)
            query = query.filter(
                (Customer.last_contact_date == None) |  # noqa: E711
                (Customer.last_contact_date <= cutoff)
            )

        customers = query.limit(limit).all()
        
        return [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "age": c.age,
                "city": c.city,
                "segment": c.segment,
                "annual_income": c.annual_income,
                "credit_score": c.credit_score,
                "monthly_avg_balance": c.monthly_avg_balance,
                "relationship_years": c.relationship_years,
                "has_credit_card": c.has_credit_card,
                "has_personal_loan": c.has_personal_loan,
                "has_home_loan": c.has_home_loan,
                "has_fd": c.has_fd,
            }
            for c in customers
        ]
    finally:
        session.close()


def get_customer_profile(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get enriched customer profile.
    
    Args:
        customer_id: Customer ID
    
    Returns:
        Full customer profile or None if not found
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        
        if not customer:
            return None
        
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "age": customer.age,
            "gender": customer.gender,
            "city": customer.city,
            "segment": customer.segment,
            "occupation": customer.occupation,
            "annual_income": customer.annual_income,
            "kyc_status": customer.kyc_status,
            "relationship_years": customer.relationship_years,
            "credit_score": customer.credit_score,
            "monthly_avg_balance": customer.monthly_avg_balance,
            "has_credit_card": customer.has_credit_card,
            "has_personal_loan": customer.has_personal_loan,
            "has_home_loan": customer.has_home_loan,
            "has_fd": customer.has_fd,
            "last_contact_date": customer.last_contact_date.isoformat() if customer.last_contact_date else None,
            "created_at": customer.created_at.isoformat(),
        }
    finally:
        session.close()
