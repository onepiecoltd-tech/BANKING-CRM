"""
Product recommendation tools.
"""
from typing import Dict, Any, List
from src.database import SessionLocal, Customer, Product


def recommend_products(customer_id: str) -> Dict[str, Any]:
    """
    Recommend products based on eligibility and affinity.
    
    Args:
        customer_id: Customer ID
    
    Returns:
        List of recommended products with reasons
    """
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(customer_id=customer_id).first()
        
        if not customer:
            return {"error": f"Customer {customer_id} not found"}
        
        # Get all products
        all_products = session.query(Product).all()
        
        recommendations = []
        
        for product in all_products:
            # Check eligibility
            reasons = []
            eligible = True
            
            # Income check
            if customer.annual_income < product.min_income:
                eligible = False
                reasons.append(f"Income ({customer.annual_income}) below minimum ({product.min_income})")
            else:
                reasons.append(f"Income meets minimum")
            
            # Credit score check
            if customer.credit_score and customer.credit_score < product.min_credit_score:
                eligible = False
                reasons.append(f"Credit score ({customer.credit_score}) below minimum ({product.min_credit_score})")
            else:
                reasons.append(f"Credit score eligible")
            
            # Segment check
            if customer.segment not in product.eligible_segments:
                eligible = False
                reasons.append(f"Segment '{customer.segment}' not in eligible segments")
            else:
                reasons.append(f"Segment '{customer.segment}' eligible")
            
            # Product-specific logic
            score = 0
            
            if product.product_type == "personal_loan":
                if not customer.has_personal_loan:
                    score = 5
                    reasons.append("No existing personal loan")
                if customer.monthly_avg_balance > 200000:
                    score += 3
                    reasons.append("High balance indicates repayment capacity")
            
            elif product.product_type == "credit_card":
                if not customer.has_credit_card and customer.segment in ["affluent", "premium"]:
                    score = 5
                    reasons.append("No existing credit card, affluent segment")
                if customer.credit_score and customer.credit_score >= 700:
                    score += 3
                    reasons.append("Strong credit profile")
            
            elif product.product_type == "home_loan":
                if not customer.has_home_loan and customer.segment in ["affluent", "premium"]:
                    score = 5
                    reasons.append("No existing home loan, premium segment")
                if customer.relationship_years >= 5:
                    score += 3
                    reasons.append("Long-term customer relationship")
            
            elif product.product_type == "fd":
                if customer.monthly_avg_balance > 100000:
                    score = 5
                    reasons.append("Strong savings capacity")
            
            if eligible and score > 0:
                recommendations.append({
                    "product_id": product.product_id,
                    "product_name": product.name,
                    "product_type": product.product_type,
                    "interest_rate": product.interest_rate,
                    "affinity_score": score,
                    "reasons": reasons,
                })
        
        # Sort by affinity score
        recommendations.sort(key=lambda x: x["affinity_score"], reverse=True)
        
        return {
            "customer_id": customer_id,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations[:5],  # Top 5
        }
    finally:
        session.close()


def get_product_details(product_id: str) -> Dict[str, Any]:
    """
    Get detailed product information.
    
    Args:
        product_id: Product ID
    
    Returns:
        Product details
    """
    session = SessionLocal()
    try:
        product = session.query(Product).filter_by(product_id=product_id).first()
        
        if not product:
            return {"error": f"Product {product_id} not found"}
        
        return {
            "product_id": product.product_id,
            "name": product.name,
            "type": product.product_type,
            "min_income": product.min_income,
            "min_credit_score": product.min_credit_score,
            "eligible_segments": product.eligible_segments,
            "interest_rate": product.interest_rate,
            "features": product.features or {},
        }
    finally:
        session.close()
