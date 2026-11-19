"""
Seed the database with realistic banking customer data.
"""
import sys
import os
import argparse
from datetime import datetime, timedelta
import random
from faker import Faker

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    engine, Base, SessionLocal, Customer, Transaction, Product, Interaction,
    IdentityGraph, Consent, Suppression
)
from src.config import settings

fake = Faker('en_IN')  # India-specific faker

# Product definitions
PRODUCTS = {
    "PL001": {
        "name": "Personal Loan",
        "type": "personal_loan",
        "min_income": 300000,
        "min_credit_score": 650,
        "interest_rate": 10.5,
        "eligible_segments": ["mass", "affluent", "premium"]
    },
    "CC001": {
        "name": "Premium Credit Card",
        "type": "credit_card",
        "min_income": 600000,
        "min_credit_score": 700,
        "interest_rate": None,
        "eligible_segments": ["affluent", "premium"]
    },
    "HL001": {
        "name": "Home Loan",
        "type": "home_loan",
        "min_income": 500000,
        "min_credit_score": 700,
        "interest_rate": 7.2,
        "eligible_segments": ["affluent", "premium"]
    },
    "FD001": {
        "name": "Fixed Deposit",
        "type": "fd",
        "min_income": 0,
        "min_credit_score": 0,
        "interest_rate": 6.0,
        "eligible_segments": ["mass", "affluent", "premium"]
    }
}

SEGMENTS = ["mass", "affluent", "premium"]
CITIES = ["Mumbai", "Bangalore", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"]
CATEGORIES = ["salary", "shopping", "food", "healthcare", "utilities", "entertainment", "education"]
CHANNELS = ["ATM", "online", "mobile", "branch"]
MERCHANTS = [
    "Amazon", "Flipkart", "BigBasket", "Zomato", "Uber", "Airbnb",
    "Netflix", "Spotify", "Swiggy", "Apollo Hospitals", "Max Healthcare"
]


def seed_products(session):
    """Create base products."""
    print("Seeding products...")
    for product_id, product_data in PRODUCTS.items():
        existing = session.query(Product).filter_by(product_id=product_id).first()
        if not existing:
            product = Product(
                product_id=product_id,
                name=product_data["name"],
                product_type=product_data["type"],
                min_income=product_data["min_income"],
                min_credit_score=product_data["min_credit_score"],
                interest_rate=product_data["interest_rate"],
                eligible_segments=product_data["eligible_segments"]
            )
            session.add(product)
    session.commit()
    print(f"Created {len(PRODUCTS)} products")


def seed_customers(session, count=500):
    """Create realistic customer profiles."""
    print(f"Seeding {count} customers...")
    created = 0
    for i in range(count):
        customer_id = f"CUST{str(i+1).zfill(6)}"
        existing = session.query(Customer).filter_by(customer_id=customer_id).first()
        if not existing:
            segment = random.choice(SEGMENTS)
            segment_income_map = {
                "mass": (250000, 750000),
                "affluent": (750000, 2000000),
                "premium": (2000000, 10000000)
            }
            min_income, max_income = segment_income_map[segment]
            annual_income = random.randint(min_income, max_income)
            
            customer = Customer(
                customer_id=customer_id,
                name=fake.name(),
                age=random.randint(25, 65),
                gender=random.choice(["M", "F"]),
                city=random.choice(CITIES),
                segment=segment,
                occupation=fake.job(),
                annual_income=annual_income,
                kyc_status="verified",
                relationship_years=random.randint(0, 20),
                has_credit_card=random.choice([True, False]),
                has_personal_loan=random.choice([True, False]),
                has_home_loan=random.choice([True, False]),
                has_fd=random.choice([True, False]),
                monthly_avg_balance=random.uniform(50000, 500000),
                credit_score=random.randint(550, 850),
                last_contact_date=datetime.utcnow() - timedelta(days=random.randint(0, 90))
            )
            session.add(customer)
            created += 1
            if created % 100 == 0:
                print(f"  Created {created} customers...")
    session.commit()
    print(f"Total customers created: {created}")


def seed_transactions(session, months=12):
    """Create realistic transaction history."""
    print(f"Seeding transactions (last {months} months)...")
    customers = session.query(Customer).all()
    created = 0
    
    for customer in customers:
        num_txns = random.randint(5, 30)
        for _ in range(num_txns):
            days_ago = random.randint(0, months * 30)
            txn_date = datetime.utcnow() - timedelta(days=days_ago)
            
            transaction = Transaction(
                txn_id=fake.uuid4(),
                customer_id=customer.customer_id,
                date=txn_date,
                amount=random.uniform(100, 50000),
                category=random.choice(CATEGORIES),
                channel=random.choice(CHANNELS),
                merchant=random.choice(MERCHANTS) if random.random() > 0.3 else None
            )
            session.add(transaction)
            created += 1
        
        if created % 1000 == 0:
            print(f"  Created {created} transactions...")
    
    session.commit()
    print(f"Total transactions created: {created}")


def seed_interactions(session, months=6):
    """Create sample interaction history."""
    print(f"Seeding interactions (last {months} months)...")
    customers = session.query(Customer).all()
    products_list = list(PRODUCTS.keys())
    created = 0
    
    for customer in random.sample(customers, min(200, len(customers))):
        num_interactions = random.randint(0, 5)
        for _ in range(num_interactions):
            days_ago = random.randint(0, months * 30)
            interaction_date = datetime.utcnow() - timedelta(days=days_ago)
            
            interaction = Interaction(
                interaction_id=fake.uuid4(),
                customer_id=customer.customer_id,
                date=interaction_date,
                channel=random.choice(["whatsapp", "email", "sms", "call"]),
                product_offered=random.choice(products_list),
                message="Outreach message about product",
                response=random.choice([None, "Interested", "Not interested", "Already have"]),
                converted=random.random() > 0.9,
                pipeline_state=random.choice(["NEW", "CONTACTED", "ENGAGED", "WON", "LOST"]),
                framework_used=random.choice(["AIDA", "SPIN", None])
            )
            session.add(interaction)
            created += 1
    
    session.commit()
    print(f"Total interactions created: {created}")


def seed_identity_graph(session):
    """Create identity resolution records."""
    print("Seeding identity graph...")
    customers = session.query(Customer).all()
    created = 0
    
    for customer in customers:
        canonical_id = customer.customer_id
        
        # Add customer_id as primary identifier
        identity = IdentityGraph(
            id=fake.uuid4(),
            identifier_value=canonical_id,
            identifier_type="customer_id",
            canonical_id=canonical_id,
            confidence=1.0,
            source="primary"
        )
        session.add(identity)
        created += 1
        
        # Add mobile number identifier
        mobile = fake.phone_number()
        identity = IdentityGraph(
            id=fake.uuid4(),
            identifier_value=mobile,
            identifier_type="mobile",
            canonical_id=canonical_id,
            confidence=1.0,
            source="kyc"
        )
        session.add(identity)
        created += 1
        
        # Add email identifier
        email = fake.email()
        identity = IdentityGraph(
            id=fake.uuid4(),
            identifier_value=email,
            identifier_type="email",
            canonical_id=canonical_id,
            confidence=0.95,
            source="signup"
        )
        session.add(identity)
        created += 1
    
    session.commit()
    print(f"Total identity records created: {created}")


def seed_consents(session):
    """Create consent records."""
    print("Seeding consents...")
    customers = session.query(Customer).all()
    channels = ["whatsapp", "email", "sms", "call"]
    created = 0
    
    for customer in customers:
        for channel in channels:
            consent = Consent(
                id=fake.uuid4(),
                canonical_id=customer.customer_id,
                channel=channel,
                opted_in=random.random() > 0.1,  # 90% opted in
                dnd_window="21:00-09:00" if channel == "call" else None
            )
            session.add(consent)
            created += 1
    
    session.commit()
    print(f"Total consent records created: {created}")


def seed_suppressions(session):
    """Create some suppression records."""
    print("Seeding suppressions...")
    customers = session.query(Customer).all()
    suppression_sample = random.sample(customers, min(50, len(customers)))
    created = 0
    
    for customer in suppression_sample:
        reason = random.choice(["opted_out", "frequency_capped", "compliance"])
        suppression = Suppression(
            id=fake.uuid4(),
            canonical_id=customer.customer_id,
            reason=reason,
            expires_at=datetime.utcnow() + timedelta(days=random.randint(30, 365)) if reason == "frequency_capped" else None,
            source="system"
        )
        session.add(suppression)
        created += 1
    
    session.commit()
    print(f"Total suppression records created: {created}")


def main(count=500):
    """Run the full seed."""
    print("=" * 50)
    print("Banking CRM Database Seeding")
    print("=" * 50)
    
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        # Seed in order
        seed_products(session)
        seed_customers(session, count=count)
        seed_transactions(session, months=12)
        seed_interactions(session, months=6)
        seed_identity_graph(session)
        seed_consents(session)
        seed_suppressions(session)
        
        print("=" * 50)
        print("Seeding complete!")
        print("=" * 50)
    except Exception as e:
        print(f"Error during seeding: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Seed the Banking CRM database with sample data.")
    parser.add_argument("--count", type=int, default=500, help="Number of customers to create")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(count=args.count)

