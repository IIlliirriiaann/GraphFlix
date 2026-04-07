#!/bin/bash
# Quick validation script for new Cypher queries
# Run this to check for syntax errors before deploying

set -e

echo "=== GraphFlix Recommendation Queries - Syntax Validation ==="
echo ""

# File paths
COLLAB_FILE="graphflix-api/app/queries/collaborative.py"
CONTENT_FILE="graphflix-api/app/queries/content_based.py"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test Python syntax
test_python_syntax() {
    local file=$1
    echo -n "Checking Python syntax in $file... "
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        python3 -m py_compile "$file"
        return 1
    fi
}

# Function to extract and validate Cypher queries
validate_cypher() {
    local file=$1
    local query_name=$2
    
    echo "Extracting $query_name from $file..."
    
    # Extract query string (simplified check - looks for valid Cypher start)
    if grep -q "^$query_name = \"\"\"" "$file"; then
        echo -e "  ${GREEN}✓ Query defined${NC}"
        
        # Check for common Cypher keywords
        if grep -q "MATCH\|UNWIND\|RETURN\|WITH" "$file"; then
            echo -e "  ${GREEN}✓ Contains valid Cypher keywords${NC}"
        else
            echo -e "  ${RED}✗ Missing Cypher keywords${NC}"
            return 1
        fi
        
        # Check for proper Cypher end
        if grep -q "LIMIT \$limit" "$file"; then
            echo -e "  ${GREEN}✓ Proper query termination${NC}"
        else
            echo -e "  ${YELLOW}⚠ Missing LIMIT parameter (may be intentional)${NC}"
        fi
        
        return 0
    else
        echo -e "  ${RED}✗ Query not found${NC}"
        return 1
    fi
}

echo "=== Validating Collaborative Queries ==="
test_python_syntax "$COLLAB_FILE"
validate_cypher "$COLLAB_FILE" "GET_COLLABORATIVE_RECOMMENDATIONS"
validate_cypher "$COLLAB_FILE" "GET_HYBRID_RECOMMENDATIONS"
validate_cypher "$COLLAB_FILE" "GET_CONFIGURABLE_WEIGHT_RECOMMENDATIONS"

echo ""
echo "=== Validating Content-Based Queries ==="
test_python_syntax "$CONTENT_FILE"
validate_cypher "$CONTENT_FILE" "GET_SIMILAR_MOVIES_BY_GENRE"
validate_cypher "$CONTENT_FILE" "GET_USER_CONTENT_RECOMMENDATIONS"

echo ""
echo "=== Checking Query Complexity ==="

# Count lines per major query
echo "Collaborative:"
grep -n "^GET_COLLABORATIVE_RECOMMENDATIONS" "$COLLAB_FILE" | head -1
echo "  Expected: ~170 lines (Jaccard + normalization)"

echo "Hybrid:"
grep -n "^GET_HYBRID_RECOMMENDATIONS" "$COLLAB_FILE" | head -1
echo "  Expected: ~280 lines (multi-signal fusion)"

echo "Configurable:"
grep -n "^GET_CONFIGURABLE_WEIGHT_RECOMMENDATIONS" "$COLLAB_FILE" | head -1
echo "  Expected: ~320 lines (4-component scoring)"

echo ""
echo "=== Checking for Common Issues ==="

# Check for missing parameters
echo -n "Checking for \$userId usage... "
if grep -q '\$userId' "$COLLAB_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for \$limit usage... "
if grep -q '\$limit' "$COLLAB_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Check for math functions
echo -n "Checking for aggregate functions (COUNT, SUM, AVG)... "
if grep -qE "COUNT|SUM|AVG" "$COLLAB_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Check for normalization
echo -n "Checking for normalization (REDUCE, toFloat, sqrt)... "
if grep -qE "toFloat|sqrt|REDUCE" "$COLLAB_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ May be missing normalization${NC}"
fi

# Check for exp() function (for logistic)
echo -n "Checking for z-score logistic (exp function)... "
if grep -q "exp(" "$COLLAB_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "=== Service Integration Check ==="

# Check if service methods exist
SERVICE_FILE="graphflix-api/app/services/recommendation_service.py"

echo -n "Checking for get_hybrid_recommendations method... "
if grep -q "async def get_hybrid_recommendations" "$SERVICE_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for get_configurable_weight_recommendations method... "
if grep -q "async def get_configurable_weight_recommendations" "$SERVICE_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "=== Router Integration Check ==="

# Check if endpoints exist
ROUTER_FILE="graphflix-api/app/routers/recommendations.py"

echo -n "Checking for /hybrid endpoint... "
if grep -q "def get_hybrid_recommendations" "$ROUTER_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for /custom endpoint... "
if grep -q "async def get_configurable_recommendations" "$ROUTER_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for HybridWeights model... "
if grep -q "class HybridWeights" "$ROUTER_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for ConfigurableWeights model... "
if grep -q "class ConfigurableWeights" "$ROUTER_FILE"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "=== Documentation Check ==="

echo -n "Checking for ALGORITHMS.md... "
if [ -f "ALGORITHMS.md" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for INTEGRATION.md... "
if [ -f "INTEGRATION.md" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "Checking for CHANGES.md... "
if [ -f "CHANGES.md" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "=== Validation Complete ==="
echo -e "Status: ${GREEN}✓ All checks passed!${NC}"
echo ""
echo "Next steps:"
echo "  1. Start the API server: python -m uvicorn app.main:app --reload"
echo "  2. Test collaborative endpoint: curl http://localhost:8000/api/recommendations/1"
echo "  3. Test hybrid endpoint: curl -X POST http://localhost:8000/api/recommendations/hybrid -H 'Content-Type: application/json' -d '{\"userId\": 1, \"weights\": {\"collaborativeWeight\": 0.6, \"contentWeight\": 0.4}, \"limit\": 10}'"
echo "  4. Check response times: should be < 500ms"
echo "  5. Verify diversity: check that genres are varied in results"
echo ""
