#!/bin/bash
# Quick start guide for Banking CRM Agent

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🏦 Banking CRM Agent - Quick Start                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${YELLOW}Step 1: Install Dependencies${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pip install -q -r requirements.txt 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Setup Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env (⚠️  Update with your API keys!)${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

echo ""
echo -e "${YELLOW}Step 3: Initialize Database${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python data/seed_db.py 2>/dev/null; then
    echo -e "${GREEN}✓ Database seeded with 500 customers${NC}"
else
    echo -e "${RED}✗ Failed to seed database${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 4: Train ML Model${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python -c "from src.ml.train import train_conversion_model; train_conversion_model()" 2>/dev/null; then
    echo -e "${GREEN}✓ Conversion prediction model trained${NC}"
else
    echo -e "${YELLOW}⚠ ML model training skipped (not critical)${NC}"
fi

echo ""
echo -e "${YELLOW}Step 5: Run Manual Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if python test_phase1.py 2>/dev/null; then
    echo -e "${GREEN}✓ Phase 1 tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests had issues (see above)${NC}"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "╚════════════════════════════════════════════════════════════════╝"

echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Update .env with your API keys:"
echo "    nano .env"
echo "    # Set GEMINI_API_KEY=your_key_here"
echo ""
echo "2️⃣  Launch the RM Agent UI:"
echo "    streamlit run src/app.py"
echo ""
echo "3️⃣  Try these use cases:"
echo "    - 'Find high-value customers likely to convert for personal loan'"
echo "    - 'Show customers with spend jump of 30%+'"
echo "    - 'Which customers have FDs and when do they mature?'"
echo ""
echo -e "${YELLOW}📚 Documentation:${NC}"
echo "    - README.md (architecture & tools)"
echo "    - PLAN.md (full master plan)"
echo ""
echo -e "${GREEN}Happy CRM-ing! 🚀${NC}"
echo ""
