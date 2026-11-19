"""
Train ML models for conversion prediction and scoring.
"""
import sys
import os
import pickle
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import joblib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal, Customer, Transaction, Interaction


def prepare_training_data():
    """
    Prepare training data from synthetic interactions.
    
    Returns:
        X (features), y (labels), feature_names
    """
    session = SessionLocal()
    try:
        customers = session.query(Customer).all()
        interactions = session.query(Interaction).all()
        
        X = []
        y = []
        
        for customer in customers:
            # Get customer features
            income = customer.annual_income or 0
            balance = customer.monthly_avg_balance or 0
            age = customer.age or 30
            tenure = customer.relationship_years or 0
            credit_score = customer.credit_score or 650
            
            # Count products
            products_held = (
                customer.has_credit_card +
                customer.has_personal_loan +
                customer.has_home_loan +
                customer.has_fd
            )
            
            # Get recent spend
            recent_txns = session.query(Transaction).filter(
                Transaction.customer_id == customer.customer_id,
                Transaction.date >= datetime.utcnow() - timedelta(days=30)
            ).all()
            recent_spend = sum(t.amount for t in recent_txns) if recent_txns else 0
            
            # Get conversion history (1 if converted in past, 0 otherwise)
            customer_interactions = [i for i in interactions if i.customer_id == customer.customer_id]
            converted = 1 if any(i.converted for i in customer_interactions) else 0
            
            features = [
                income,
                balance,
                age,
                tenure,
                products_held,
                credit_score,
                recent_spend,
                1 if customer.kyc_status == "verified" else 0,
                1 if customer.segment == "premium" else 0,
                1 if customer.segment == "affluent" else 0,
            ]
            
            X.append(features)
            y.append(converted)
        
        feature_names = [
            "income", "balance", "age", "tenure", "products_held",
            "credit_score", "recent_spend", "kyc_verified", "is_premium", "is_affluent"
        ]
        
        return np.array(X), np.array(y), feature_names
    finally:
        session.close()


def train_conversion_model():
    """
    Train logistic regression model for conversion prediction.
    Saves model and scaler to disk.
    """
    print("=" * 50)
    print("Training Conversion Prediction Model")
    print("=" * 50)
    
    # Prepare training data
    print("Preparing training data...")
    X, y, feature_names = prepare_training_data()
    
    print(f"  Dataset size: {len(X)} customers")
    print(f"  Positive examples (converted): {sum(y)}")
    print(f"  Negative examples: {len(y) - sum(y)}")
    print(f"  Features: {', '.join(feature_names)}")
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train logistic regression
    print("Training logistic regression model...")
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_scaled, y)
    
    # Evaluate
    train_score = model.score(X_scaled, y)
    print(f"  Training accuracy: {train_score:.3f}")
    
    # Get feature importance (coefficients)
    coefficients = model.coef_[0]
    feature_importance = sorted(
        zip(feature_names, coefficients),
        key=lambda x: abs(x[1]),
        reverse=True
    )
    
    print("  Top contributing features:")
    for name, coef in feature_importance[:5]:
        print(f"    {name}: {coef:.4f}")
    
    # Save model and scaler
    model_path = os.path.join(
        os.path.dirname(__file__),
        "model.pkl"
    )
    scaler_path = os.path.join(
        os.path.dirname(__file__),
        "scaler.pkl"
    )
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    print(f"\nModel saved to: {model_path}")
    print(f"Scaler saved to: {scaler_path}")
    
    return model, scaler, feature_names


def load_conversion_model():
    """
    Load pre-trained model and scaler.
    
    Returns:
        (model, scaler, feature_names) or None if not found
    """
    model_path = os.path.join(
        os.path.dirname(__file__),
        "model.pkl"
    )
    scaler_path = os.path.join(
        os.path.dirname(__file__),
        "scaler.pkl"
    )
    
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        feature_names = [
            "income", "balance", "age", "tenure", "products_held",
            "credit_score", "recent_spend", "kyc_verified", "is_premium", "is_affluent"
        ]
        return model, scaler, feature_names
    
    return None


if __name__ == "__main__":
    train_conversion_model()
