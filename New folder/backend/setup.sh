#!/usr/bin/env python3
"""
Quick setup script for Banking CRM Agent.
"""
import os
import sys
import subprocess

def run_command(cmd, description):
    """Run a command and print status."""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Error: {description} failed")
        return False
    print(f"✅ {description} complete")
    return True

def main():
    """Run setup."""
    print("\n🏦 Banking CRM Agent - Setup\n")
    
    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # 1. Create .env if needed
    if not os.path.exists(".env"):
        print("Creating .env from .env.example...")
        with open(".env.example") as f_in:
            with open(".env", "w") as f_out:
                f_out.write(f_in.read())
        print("✅ .env created (please update with your API keys)")
    
    # 2. Install dependencies
    if not run_command("pip install -r requirements.txt", "Install dependencies"):
        return
    
    # 3. Initialize and seed database
    print("\n" + "="*60)
    print("▶ Initialize and seed database")
    print("="*60)
    os.chdir("data")
    if not run_command(f"{sys.executable} seed_db.py", "Seed database"):
        return
    os.chdir("..")
    
    # 4. Train ML model
    print("\n" + "="*60)
    print("▶ Train ML conversion model")
    print("="*60)
    if not run_command(f"{sys.executable} -c \"from src.ml.train import train_conversion_model; train_conversion_model()\"", "Train ML model"):
        print("⚠️  ML training skipped (not critical)")
    
    # Done
    print("\n" + "="*60)
    print("✅ Setup Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Update .env with your API keys (GEMINI_API_KEY, etc.)")
    print("2. Run the RM agent UI: streamlit run src/app.py")
    print("\nDocumentation: See README.md for more details")

if __name__ == "__main__":
    main()
