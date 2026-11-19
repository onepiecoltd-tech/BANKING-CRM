"""
Seed demo customers for Home Loan edge case testing.
Run: python3 -m src.knowledge_base.seed_demo_customers
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from src.database import SessionLocal, Customer, Base, engine
from datetime import datetime

# ── 1. Add new columns to existing DB if they don't exist ──────────────────
def migrate():
    with engine.connect() as conn:
        for col, defn in [
            ("employment_type",       "VARCHAR"),
            ("employment_tenure_years","FLOAT DEFAULT 0"),
            ("existing_emi",          "FLOAT DEFAULT 0"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE customers ADD COLUMN {col} {defn}"))
                conn.commit()
                print(f"  ✅ Added column: {col}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  ℹ️  Column already exists: {col}")
                else:
                    print(f"  ⚠️  {col}: {e}")

# ── 2. Demo customers — 8 edge cases ───────────────────────────────────────
DEMO_CUSTOMERS = [
    {
        # ELIGIBLE — all 6 pass
        "customer_id": "HL_DEMO_001",
        "name": "Aryan Mehta",
        "age": 35,
        "gender": "Male",
        "city": "Mumbai",
        "segment": "affluent",
        "occupation": "Software Engineer",
        "annual_income": 1_800_000,       # ₹1.8L/month → well above ₹25k ✅
        "credit_score": 780,              # ≥700 ✅
        "monthly_avg_balance": 250_000,
        "relationship_years": 6,
        "has_credit_card": True,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": True,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 5.0,   # ≥2 yrs ✅
        "existing_emi": 15_000,           # FOIR = (15k + ~70k proposed) / 150k = 57%... wait let me recalc
        # monthly = 150k, existing emi = 15k, proposed ~70k → FOIR = 85k/150k = 57% ⚠️
        # Let me set existing_emi to 5k so FOIR is clean
        # Actually let me recalculate: max emi = 150k*0.5 = 75k, existing=15k, so headroom=60k ✅
        # FOIR = (15k+proposed)/150k. If proposed = 55k → FOIR = 70k/150k = 46.7% ✅
    },
    {
        # CONDITIONALLY ELIGIBLE — CIBIL 675 (⚠️)
        "customer_id": "HL_DEMO_002",
        "name": "Priya Sharma",
        "age": 32,
        "gender": "Female",
        "city": "Delhi",
        "segment": "affluent",
        "occupation": "Doctor",
        "annual_income": 1_200_000,       # ₹1L/month ✅
        "credit_score": 675,              # 650–699 → ⚠️ CONDITIONALLY ELIGIBLE
        "monthly_avg_balance": 150_000,
        "relationship_years": 4,
        "has_credit_card": False,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": False,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 3.5,
        "existing_emi": 8_000,
    },
    {
        # NOT ELIGIBLE — CIBIL 620 (❌)
        "customer_id": "HL_DEMO_003",
        "name": "Ravi Nair",
        "age": 40,
        "gender": "Male",
        "city": "Bangalore",
        "segment": "mass",
        "occupation": "Shopkeeper",
        "annual_income": 600_000,
        "credit_score": 620,              # <650 → ❌ NOT ELIGIBLE
        "monthly_avg_balance": 45_000,
        "relationship_years": 8,
        "has_credit_card": False,
        "has_personal_loan": True,
        "has_home_loan": False,
        "has_fd": False,
        "kyc_status": "verified",
        "employment_type": "self_employed",
        "employment_tenure_years": 4.0,
        "existing_emi": 12_000,
    },
    {
        # NOT ELIGIBLE — Income too low (₹18k/month < ₹25k)
        "customer_id": "HL_DEMO_004",
        "name": "Sunita Rao",
        "age": 28,
        "gender": "Female",
        "city": "Chennai",
        "segment": "mass",
        "occupation": "Retail Staff",
        "annual_income": 216_000,         # ₹18k/month → ❌ < ₹25k
        "credit_score": 720,
        "monthly_avg_balance": 18_000,
        "relationship_years": 2,
        "has_credit_card": False,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": False,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 2.0,
        "existing_emi": 0,
    },
    {
        # CONDITIONALLY ELIGIBLE — Age 59 (⚠️: loan ends at 67 > 65)
        "customer_id": "HL_DEMO_005",
        "name": "Deepak Joshi",
        "age": 59,
        "gender": "Male",
        "city": "Pune",
        "segment": "premium",
        "occupation": "Senior Manager",
        "annual_income": 2_400_000,       # ₹2L/month ✅
        "credit_score": 760,              # ✅
        "monthly_avg_balance": 500_000,
        "relationship_years": 15,
        "has_credit_card": True,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": True,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 12.0,
        "existing_emi": 55_000,           # FOIR = (55k+proposed)/200k → ⚠️ at 52%
        # loan matures at 57+8=65 → max tenure 8 yrs → shorter loan → reduced max ⚠️
    },
    {
        # NOT ELIGIBLE — Age 64 (loan would mature at 84) ❌
        "customer_id": "HL_DEMO_006",
        "name": "Meena Pillai",
        "age": 64,
        "gender": "Female",
        "city": "Hyderabad",
        "segment": "premium",
        "occupation": "Retired Teacher",
        "annual_income": 960_000,         # pension ₹80k/month
        "credit_score": 750,
        "monthly_avg_balance": 300_000,
        "relationship_years": 20,
        "has_credit_card": True,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": True,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 0.5,   # retired, minimal tenure ⚠️
        "existing_emi": 0,
        # Age: 64 > 63 → ❌ (loan matures >65 even for 1yr tenure... actually 64+1=65 is ok)
        # Actually at 64, max tenure = 1 year. That makes loan almost non-viable.
        # Let's keep age 64 — employment ❌ (retired), age ⚠️ → NOT ELIGIBLE
    },
    {
        # CONDITIONALLY ELIGIBLE — Employment tenure only 1yr (⚠️ for salaried, need 2yr)
        "customer_id": "HL_DEMO_007",
        "name": "Kartik Singh",
        "age": 27,
        "gender": "Male",
        "city": "Kolkata",
        "segment": "mass",
        "occupation": "Junior Analyst",
        "annual_income": 480_000,         # ₹40k/month ✅
        "credit_score": 730,
        "monthly_avg_balance": 55_000,
        "relationship_years": 3,
        "has_credit_card": False,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": False,
        "kyc_status": "verified",
        "employment_type": "salaried",
        "employment_tenure_years": 1.0,   # < 2 yrs → ⚠️ Employment marginal
        "existing_emi": 5_000,
    },
    {
        # NOT ELIGIBLE — City not in approved zone list
        "customer_id": "HL_DEMO_008",
        "name": "Anjali Desai",
        "age": 38,
        "gender": "Female",
        "city": "Shimla",                 # ❌ Not in approved city list
        "segment": "affluent",
        "occupation": "Business Owner",
        "annual_income": 1_500_000,
        "credit_score": 740,
        "monthly_avg_balance": 200_000,
        "relationship_years": 5,
        "has_credit_card": True,
        "has_personal_loan": False,
        "has_home_loan": False,
        "has_fd": True,
        "kyc_status": "verified",
        "employment_type": "self_employed",
        "employment_tenure_years": 6.0,
        "existing_emi": 20_000,
    },
]

def seed():
    session = SessionLocal()
    inserted = 0
    updated = 0
    try:
        for data in DEMO_CUSTOMERS:
            existing = session.query(Customer).filter_by(customer_id=data["customer_id"]).first()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                c = Customer(**data, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
                session.add(c)
                inserted += 1
        session.commit()
        print(f"  ✅ Inserted: {inserted} | Updated: {updated} demo customers")
    finally:
        session.close()


def run_edge_case_tests():
    """Quick smoke test — print eligibility verdict for each demo customer."""
    APPROVED_CITIES = {
        "Mumbai","Delhi","Bangalore","Bengaluru","Hyderabad","Chennai",
        "Pune","Kolkata","Ahmedabad","Jaipur","Surat","Nagpur",
        "Noida","Gurgaon","Lucknow","Bhopal"
    }

    session = SessionLocal()
    demo_ids = [d["customer_id"] for d in DEMO_CUSTOMERS]
    customers = session.query(Customer).filter(Customer.customer_id.in_(demo_ids)).all()
    session.close()

    print("\n" + "="*70)
    print("HOME LOAN EDGE CASE TEST RESULTS")
    print("="*70)

    expected = {
        "HL_DEMO_001": "ELIGIBLE",
        "HL_DEMO_002": "CONDITIONALLY ELIGIBLE",
        "HL_DEMO_003": "NOT ELIGIBLE",
        "HL_DEMO_004": "NOT ELIGIBLE",
        "HL_DEMO_005": "CONDITIONALLY ELIGIBLE",
        "HL_DEMO_006": "NOT ELIGIBLE",
        "HL_DEMO_007": "CONDITIONALLY ELIGIBLE",
        "HL_DEMO_008": "NOT ELIGIBLE",
    }

    for c in sorted(customers, key=lambda x: x.customer_id):
        monthly = (c.annual_income or 0) / 12
        existing_emi = c.existing_emi or 0
        rate_monthly = 7.2 / 100 / 12
        tenure_months = min(30, 65 - (c.age or 30)) * 12
        if tenure_months <= 0:
            tenure_months = 12
        proposed_emi = 2_000_000 * rate_monthly / (1 - (1 + rate_monthly)**-tenure_months)
        foir = (existing_emi + proposed_emi) / monthly * 100 if monthly > 0 else 999

        # Score each criterion
        results = {}

        # 1. Income
        min_income = 25_000 if c.employment_type != "self_employed" else 40_000
        if monthly >= min_income:
            results["Income"] = "✅"
        elif monthly >= min_income * 0.85:
            results["Income"] = "⚠️"
        else:
            results["Income"] = "❌"

        # 2. CIBIL
        cs = c.credit_score or 0
        if cs >= 700:   results["CIBIL"] = "✅"
        elif cs >= 650: results["CIBIL"] = "⚠️"
        else:           results["CIBIL"] = "❌"

        # 3. FOIR
        if foir <= 50:   results["FOIR"] = "✅"
        elif foir <= 55: results["FOIR"] = "⚠️"
        else:            results["FOIR"] = "❌"

        # 4. Age
        age = c.age or 30
        loan_end_age = age + min(30, 65 - age)
        if age <= 58 and loan_end_age <= 65: results["Age"] = "✅"
        elif age <= 63:                      results["Age"] = "⚠️"
        else:                                results["Age"] = "❌"

        # 5. Employment
        tenure = c.employment_tenure_years or 0
        emp = c.employment_type or "unknown"
        if emp == "salaried" and tenure >= 2:        results["Employment"] = "✅"
        elif emp == "self_employed" and tenure >= 3: results["Employment"] = "✅"
        elif tenure >= 1:                            results["Employment"] = "⚠️"
        else:                                        results["Employment"] = "❌"

        # 6. Property / City
        city = (c.city or "").strip().title()
        results["Property"] = "✅" if city in APPROVED_CITIES else "❌"

        # Verdict
        fails = sum(1 for v in results.values() if v == "❌")
        passes = sum(1 for v in results.values() if v == "✅")
        income_ok  = results["Income"]   != "❌"
        cibil_ok   = results["CIBIL"]    != "❌"
        property_ok = results["Property"] != "❌"  # city must be in approved zone

        if fails == 0 and passes == 6:
            verdict = "ELIGIBLE"
        elif (not income_ok) or (not cibil_ok) or (not property_ok) or fails >= 3:
            # Hard fails: Income ❌, CIBIL ❌, Property ❌, or 3+ any fail
            verdict = "NOT ELIGIBLE"
        elif passes >= 4 and income_ok and cibil_ok and property_ok:
            verdict = "CONDITIONALLY ELIGIBLE"
        else:
            verdict = "NOT ELIGIBLE"

        exp = expected.get(c.customer_id, "?")
        match = "✅" if verdict == exp else "❌ MISMATCH"

        print(f"\n{c.customer_id} — {c.name} ({c.age}y, {c.city})")
        print(f"  Criteria: {' | '.join(f'{k}:{v}' for k,v in results.items())}")
        print(f"  FOIR: {foir:.1f}% | Monthly: ₹{monthly:,.0f} | EMI: ₹{existing_emi:,.0f}")
        print(f"  Verdict:  {verdict}")
        print(f"  Expected: {exp}  {match}")

    print("\n" + "="*70)


if __name__ == "__main__":
    print("\n[1/3] Running DB migration...")
    migrate()
    print("\n[2/3] Seeding demo customers...")
    seed()
    print("\n[3/3] Running edge case tests...")
    run_edge_case_tests()
