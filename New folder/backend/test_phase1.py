"""
Manual test to verify Phase 1 setup works.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import SessionLocal, Customer, init_db
from src.tools import customer_tool, scoring_tool, product_tool, message_tool
from src.ml.train import load_conversion_model

def test_database():
    """Test database connection."""
    print("\n✓ Testing Database...")
    try:
        init_db()
        session = SessionLocal()
        count = session.query(Customer).count()
        session.close()
        print(f"  ✅ Database OK - {count} customers found")
        return True
    except Exception as e:
        print(f"  ❌ Database error: {str(e)}")
        return False

def test_tools():
    """Test Phase 1 tools."""
    print("\n✓ Testing Tools...")
    try:
        # Get first customer
        session = SessionLocal()
        customer = session.query(Customer).first()
        session.close()
        
        if not customer:
            print("  ⚠️  No customers found - run seed_db.py first")
            return False
        
        customer_id = customer.customer_id
        
        # Test query_customers
        results = customer_tool.query_customers({"segment": "mass"}, limit=3)
        print(f"  ✅ query_customers: {len(results)} results")
        
        # Test get_customer_profile
        profile = customer_tool.get_customer_profile(customer_id)
        print(f"  ✅ get_customer_profile: {profile['name']}")
        
        # Test scoring
        score = scoring_tool.score_customer_value(customer_id)
        print(f"  ✅ score_customer_value: {score['score']}")
        
        # Test recommendations
        recs = product_tool.recommend_products(customer_id)
        print(f"  ✅ recommend_products: {len(recs['recommendations'])} products")
        
        # Test message drafting
        msg = message_tool.draft_outreach_message(
            customer_name=profile['name'],
            product_id="PL001",
            framework="AIDA",
            tone="warm"
        )
        print(f"  ✅ draft_outreach_message: {msg['primary_message'][:50]}...")
        
        return True
    except Exception as e:
        print(f"  ❌ Tool error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_ml_model():
    """Test ML model."""
    print("\n✓ Testing ML Model...")
    try:
        model_info = load_conversion_model()
        if model_info:
            print(f"  ✅ ML model loaded successfully")
            return True
        else:
            print(f"  ⚠️  ML model not found - run training script first")
            return False
    except Exception as e:
        print(f"  ❌ ML model error: {str(e)}")
        return False

def test_llm_provider():
    """Test LLM provider."""
    print("\n✓ Testing LLM Provider...")
    try:
        from src.llm import get_llm_provider
        provider = get_llm_provider()
        model_name = provider.get_model_name()
        print(f"  ✅ LLM provider initialized: {model_name}")
        return True
    except Exception as e:
        print(f"  ⚠️  LLM provider warning: {str(e)} (set API keys in .env)")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("🏦 Banking CRM Agent - Phase 1 Manual Test")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Database", test_database()))
    results.append(("Tools", test_tools()))
    results.append(("ML Model", test_ml_model()))
    results.append(("LLM Provider", test_llm_provider()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! Ready to run the app.")
        print("\nNext steps:")
        print("1. Update .env with your API keys")
        print("2. Run: streamlit run src/app.py")
    else:
        print("⚠️  Some tests failed. See above for details.")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
