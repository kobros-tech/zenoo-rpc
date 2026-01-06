#!/bin/bash
# Test HTTP Proxy endpoints
#
# This script tests all HTTP proxy endpoints to verify functionality

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

API_KEY="${1:-letta-secret-123}"
BASE_URL="${2:-http://localhost:8080}"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Testing MCP HTTP Proxy${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo "Base URL: $BASE_URL"
echo "API Key: ${API_KEY:0:10}...${API_KEY: -4}"
echo ""

# Test 1: Server info
echo -e "${YELLOW}Test 1: GET / (Server Info)${NC}"
curl -s "$BASE_URL/" | jq '.'
echo ""

# Test 2: Health check
echo -e "${YELLOW}Test 2: GET /health${NC}"
curl -s "$BASE_URL/health" -H "Authorization: Bearer $API_KEY" | jq '.'
echo ""

# Test 3: List tools
echo -e "${YELLOW}Test 3: GET /tools (List All Tools)${NC}"
curl -s "$BASE_URL/tools" -H "Authorization: Bearer $API_KEY" | jq '.tools[] | {name, description}'
echo ""

# Test 4: Search records
echo -e "${YELLOW}Test 4: POST /tools/search_records${NC}"
curl -s -X POST "$BASE_URL/tools/search_records" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"model": "res.partner", "limit": 3}}' | jq '.'
echo ""

# Test 5: Get specific record
echo -e "${YELLOW}Test 5: POST /tools/get_record${NC}"
curl -s -X POST "$BASE_URL/tools/get_record" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"model": "res.partner", "record_id": 1}}' | jq '.'
echo ""

echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}  All tests completed!${NC}"
echo -e "${GREEN}======================================================================${NC}"
