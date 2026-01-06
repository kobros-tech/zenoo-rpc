#!/bin/bash
# Start MCP HTTP Proxy for Letta Cloud Integration
#
# This script starts the HTTP proxy server that wraps the MCP server
# with a simple REST API for Letta Cloud.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Zenoo RPC MCP HTTP Proxy${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/mcp_http_proxy.py" ]; then
    echo -e "${RED}Error: mcp_http_proxy.py not found in $PROJECT_ROOT${NC}"
    echo "Please run this script from the zenoo-rpc directory"
    exit 1
fi

# Check for virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
    if [ -d "$PROJECT_ROOT/../env" ]; then
        echo -e "${GREEN}Activating virtual environment...${NC}"
        source "$PROJECT_ROOT/../env/bin/activate"
    else
        echo -e "${RED}Error: Virtual environment not found${NC}"
        echo "Please create and activate a virtual environment first:"
        echo "  python -m venv env"
        echo "  source env/bin/activate"
        exit 1
    fi
fi

# Load environment variables from zenoo-rpc/.env
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${GREEN}Loading environment variables from $PROJECT_ROOT/.env${NC}"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found at $PROJECT_ROOT/.env${NC}"
    echo "Make sure Odoo connection variables are set:"
    echo "  ODOO_URL, ODOO_DATABASE, ODOO_USERNAME, ODOO_PASSWORD"
fi

# Set defaults after loading .env (so env vars take precedence)
DEFAULT_PORT="${MCP_PORT:-8080}"
DEFAULT_API_KEY="${MCP_API_KEYS:-}"

# Get port and API key (command-line args override everything)
PORT="${1:-$DEFAULT_PORT}"
API_KEY="${2:-$DEFAULT_API_KEY}"

echo -e "${GREEN}Configuration:${NC}"
echo "  Port: $PORT"
if [ -n "$API_KEY" ]; then
    echo "  API Key: ${API_KEY:0:10}...${API_KEY: -4}"
else
    echo "  API Key: Not set (authentication disabled)"
fi
echo "  Odoo URL: ${ODOO_URL:-http://localhost:8069}"
echo "  Odoo DB: ${ODOO_DATABASE:-not set}"
echo ""

# Check if port is available
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}Error: Port $PORT is already in use${NC}"
    echo "Stop the existing process or choose a different port:"
    echo "  $0 <port> <api-key>"
    exit 1
fi

# Check if Odoo is accessible
if [ -n "$ODOO_URL" ]; then
    echo -e "${BLUE}Checking Odoo connection...${NC}"
    if curl -s -f "$ODOO_URL/web/database/list" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Odoo is accessible${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: Cannot reach Odoo at $ODOO_URL${NC}"
        echo "The proxy will start but may fail when calling tools"
    fi
    echo ""
fi

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Starting HTTP Proxy Server${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}Access at: http://localhost:$PORT${NC}"
echo ""
echo "Endpoints:"
echo "  GET  /           - Server info"
echo "  GET  /health     - Health check"
echo "  GET  /tools      - List all tools"
echo "  POST /tools/{name} - Call a tool"
echo ""
echo "Authentication:"
echo "  Authorization: Bearer $API_KEY"
echo ""
if [ -n "$API_KEY" ]; then
    echo -e "${YELLOW}For AI Agent / Remote Integration:${NC}"
    echo "  1. Expose with ngrok (optional for remote access):"
    echo "     ngrok http $PORT"
    echo ""
    echo "  2. Configure in your application:"
    echo "     URL: http://localhost:$PORT (or ngrok URL)"
    echo "     Auth: Bearer Token"
    echo "     Token: $API_KEY"
    echo ""
else
    echo -e "${YELLOW}⚠️  Warning: No API key configured${NC}"
    echo "  Set MCP_API_KEYS in .env or pass as argument:"
    echo "    $0 <port> <api-key>"
    echo ""
fi
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}Starting server... (Press Ctrl+C to stop)${NC}"
echo ""

# Start the server
cd "$PROJECT_ROOT"
python mcp_http_proxy.py --port "$PORT" --api-key "$API_KEY"
