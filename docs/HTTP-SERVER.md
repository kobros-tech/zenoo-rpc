# Zenoo RPC HTTP Server Guide

Complete guide for running Zenoo RPC as an HTTP REST API server. Provides 8 powerful tools for Odoo operations accessible via standard HTTP/JSON. Works with any HTTP client: AI agents, custom applications, curl, Postman, or any programming language.

## Quick Start

### 1. Configure Environment

Edit `.env` file in the `zenoo-rpc` directory:

```bash
# MCP Server Configuration
MCP_API_KEYS=your-secret-key-here
MCP_PORT=8080
MCP_HOST=0.0.0.0

# Odoo Connection
ODOO_URL=http://localhost:8069
ODOO_DATABASE=your_database
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password
```

### 2. Start the Server

```bash
# From zenoo-rpc directory
bash scripts/start_http_proxy.sh

# Or with custom port/key
bash scripts/start_http_proxy.sh 9000 custom-api-key
```

### 3. Test the Server

```bash
# List available tools
curl http://localhost:8080/tools \
  -H "Authorization: Bearer your-secret-key-here"

# Search for partners
curl -X POST http://localhost:8080/tools/search_records \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"model": "res.partner", "limit": 5}}'
```

## Architecture

```
Any HTTP Client ──HTTPS──> HTTP Server ──stdio──> MCP Server ──> Odoo
(AI Agents,              (REST API)     (Python)   (FastMCP)     (JSON-RPC)
 Apps, curl, etc)
```

**Why This Design?**
- **Standard REST API**: Simple HTTP/JSON interface, no special protocols
- **Universal Compatibility**: Works with any HTTP client in any language
- **Easy Authentication**: Standard Bearer token authentication
- **No Complex Setup**: Just HTTP POST with JSON - that's it

## Available Tools

### Basic CRUD Operations

1. **`search_records`** - Search with Odoo domain filters
2. **`get_record`** - Get single record by ID
3. **`create_record`** - Create new record
4. **`update_record`** - Update existing record
5. **`delete_record`** - Delete record

### Advanced Operations

6. **`complex_search`** - Advanced search with Django-like lookups (ilike, gt, lt, in, etc.)
7. **`batch_operation`** - Bulk create/update/delete operations
8. **`analytics_query`** - Data aggregation with grouping (sum, count, avg, min, max)

## API Endpoints

### GET /tools
List all available tools with their descriptions.

```bash
curl http://localhost:8080/tools \
  -H "Authorization: Bearer your-api-key"
```

### POST /tools/{tool_name}
Execute a specific tool.

```bash
curl -X POST http://localhost:8080/tools/search_records \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "model": "res.partner",
      "domain": [["is_company", "=", true]],
      "limit": 10
    }
  }'
```

### GET /health
Health check endpoint.

```bash
curl http://localhost:8080/health
```

## Usage Examples

### Search Records

```bash
curl -X POST http://localhost:8080/tools/search_records \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "model": "sale.order",
      "domain": [["state", "=", "sale"], ["date_order", ">=", "2025-01-01"]],
      "fields": ["id", "name", "partner_id", "amount_total"],
      "order": "date_order DESC",
      "limit": 25
    }
  }'
```

### Complex Search

```bash
curl -X POST http://localhost:8080/tools/complex_search \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "model": "res.partner",
      "filters": {
        "name": {"ilike": "%tech%"},
        "customer_rank": {"gt": 0},
        "active": true
      },
      "order_by": "-create_date",
      "limit": 20
    }
  }'
```

### Create Record

```bash
curl -X POST http://localhost:8080/tools/create_record \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "model": "res.partner",
      "values": {
        "name": "Acme Corporation",
        "email": "contact@acme.com",
        "phone": "+1-555-0123",
        "is_company": true
      }
    }
  }'
```

### Batch Operation

```bash
curl -X POST http://localhost:8080/tools/batch_operation \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "operation": "update",
      "model": "res.partner",
      "records": [
        {"id": 10, "phone": "+1-555-0001"},
        {"id": 20, "phone": "+1-555-0002"},
        {"id": 30, "email": "updated@example.com"}
      ]
    }
  }'
```

### Analytics Query

```bash
curl -X POST http://localhost:8080/tools/analytics_query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "model": "sale.order",
      "group_by": ["state"],
      "aggregates": {
        "total_sales": "sum:amount_total",
        "order_count": "count:id"
      },
      "filters": {"date_order": {"gte": "2025-01-01"}}
    }
  }'
```

## AI Agent Integration

The HTTP server works with any AI agent platform that supports custom tools/APIs:

### Claude Code Integration

To connect Claude Code (Anthropic's CLI) to the Zenoo RPC HTTP server, create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "zenoo-rpc": {
      "type": "http",
      "url": "http://your-server-url:8080/mcp",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      }
    }
  }
}
```

Or add to your global Claude settings at `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "zenoo-rpc": {
      "type": "http",
      "url": "https://your-public-url.com/mcp",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      }
    }
  }
}
```

After configuration, restart Claude Code. The Odoo tools will be available natively.

**Note:** The `/mcp` endpoint implements the MCP Streamable HTTP protocol for Claude Code. For Letta and other platforms, use the root `/` endpoint with JSON-RPC format.

### Letta Integration

For Letta AI agents, use the JSON-RPC endpoint at `/`:

```json
{
  "url": "https://your-server-url.com/",
  "auth_type": "bearer_token",
  "token": "your-api-key-here"
}
```

### Expose Server Publicly (Optional)

For cloud-based AI agents, expose your local server:

```bash
# Terminal 1: Start HTTP server
bash scripts/start_http_proxy.sh

# Terminal 2: Expose with ngrok
ngrok http 8080
```

### Configure in Other AI Platforms

Most AI platforms (LangChain, AutoGPT, etc.) need:
- **URL/Endpoint**: Your server URL (e.g., `https://abc123.ngrok.io` or `http://localhost:8080`)
- **Authentication**: Bearer Token
- **Token**: Value from `MCP_API_KEYS` in `.env`
- **Available Tools**: Call `GET /tools` to see all available operations

### Example AI Agent Usage

Your AI agent can now:
- "Search for all active partners in Odoo"
- "Create a new partner named 'Test Company'"
- "Show me sales analytics grouped by state"
- "Update partner ID 42 with new email address"
- "Get the details of sales order 150"

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MCP_PORT` | HTTP server port | 8080 | No |
| `MCP_HOST` | Bind address | 0.0.0.0 | No |
| `MCP_API_KEYS` | Bearer token for auth | - | Yes |
| `ODOO_URL` | Odoo server URL | - | Yes |
| `ODOO_DATABASE` | Database name | - | Yes |
| `ODOO_USERNAME` | Odoo username | - | Yes |
| `ODOO_PASSWORD` | Odoo password | - | Yes |

### Script Options

```bash
# Use defaults from .env
bash scripts/start_http_proxy.sh

# Custom port
bash scripts/start_http_proxy.sh 9000

# Custom port and API key
bash scripts/start_http_proxy.sh 9000 my-custom-key
```

## Security

### Authentication

All requests require Bearer token authentication:

```bash
Authorization: Bearer your-secret-key-here
```

### Best Practices

1. **Use strong API keys** - Generate random, long keys
2. **Use HTTPS in production** - Never expose HTTP to the internet
3. **Rotate credentials regularly** - Change API keys periodically
4. **Use ngrok for testing only** - Production needs proper HTTPS setup
5. **Limit network access** - Use firewall rules to restrict access
6. **Monitor logs** - Watch for suspicious activity

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
bash scripts/start_http_proxy.sh 9000
```

### Connection to Odoo Failed

1. Verify Odoo is running: `curl http://localhost:8069`
2. Check credentials in `.env`
3. Verify database exists
4. Check Odoo logs for errors

### Authentication Errors

1. Verify `MCP_API_KEYS` is set in `.env`
2. Check Bearer token in request header
3. Ensure no extra spaces in token

### Tool Execution Errors

1. Check Odoo model exists: `curl POST /tools/search_records`
2. Verify field names are correct
3. Check Odoo user permissions
4. Review server logs for details

## Development

### Run in Debug Mode

```bash
# Set log level to DEBUG in code or via environment
LOG_LEVEL=DEBUG bash scripts/start_http_proxy.sh
```

### Test with Python

```python
import httpx
import asyncio

async def test_search():
    url = "http://localhost:8080/tools/search_records"
    headers = {
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json"
    }
    payload = {
        "arguments": {
            "model": "res.partner",
            "limit": 5
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        print(response.json())

asyncio.run(test_search())
```

## Performance Tips

1. **Use specific fields** - Request only needed fields to reduce payload size
2. **Set appropriate limits** - Don't fetch more records than needed
3. **Use batch operations** - Bulk operations are much faster than individual calls
4. **Enable caching** - Configure Redis for better performance
5. **Use complex_search** - More efficient than multiple search_records calls
6. **Connection pooling** - HTTP/2 connection reuse is automatic

## Support

- **Documentation**: See [CLAUDE.md](../CLAUDE.md) for development guide
- **Issues**: Report bugs at [GitHub Issues](https://github.com/tuanle96/zenoo-rpc/issues)
- **Tool Descriptions**: All tools have comprehensive docstrings - call `/tools` endpoint to see them
