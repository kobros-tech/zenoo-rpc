# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zenoo RPC is a modern, async-first Python library for Odoo RPC operations with type safety, AI integration, and MCP (Model Context Protocol) support. It replaces the legacy `odoorpc` library with modern Python practices (async/await, Pydantic, type hints).

**Key Characteristics:**
- **Async-first**: Built on `asyncio` and `httpx` with HTTP/2 support
- **Type-safe**: Full Pydantic integration with runtime validation and IDE support
- **Clean Architecture**: Clear separation of concerns across layers
- **Python Support**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Status**: Alpha stage, actively developed

## Development Commands

### Setup
```bash
# Install for development
pip install -e ".[dev,redis]"

# Install pre-commit hooks
pre-commit install
```

### Testing
```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_client.py -v
pytest tests/test_models.py tests/test_query_builder.py -v

# Run with coverage
pytest --cov=src/zenoo_rpc --cov-report=term-missing --cov-report=html

# Using Makefile shortcuts
make test                # All tests
make test-core           # Core functionality tests
make test-cache          # Cache tests
make test-redis          # Redis tests (requires Docker)
make test-transaction    # Transaction tests
make test-coverage       # Tests with coverage report
```

### Redis Testing
```bash
# Start Redis container for testing
make setup-redis

# Check Redis status
make redis-status

# Stop Redis
make stop-redis

# Clean Redis (remove container and volumes)
make clean-redis
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/zenoo_rpc

# Using Makefile
make format              # Format code with black + isort
make lint               # Run flake8 + mypy
make type-check         # Run mypy only
```

### Cleanup
```bash
make clean              # Clean build artifacts
make clean-all          # Clean everything including Redis
```

## High-Level Architecture

### Layered Architecture

Zenoo RPC follows Clean Architecture with four distinct layers:

**1. Presentation Layer (`client.py`)**
- `ZenooClient`: Main entry point and facade
- Handles authentication, session management, URL parsing
- Provides fluent API for model access: `client.model(ResPartner)`
- Orchestrates high-level operations

**2. Application Layer (managers)**
- `TransactionManager` (`transaction/`): ACID transaction handling with rollback
- `BatchManager` (`batch/`): Bulk operation coordination with chunking
- `CacheManager` (`cache/`): Intelligent caching strategies (TTL, LRU) with Redis support
- `RetryManager` (`retry/`): Resilience with exponential backoff and circuit breaker
- These are optional components initialized via `client.setup_*()` methods

**3. Domain Layer (models and query)**
- `OdooModel` (`models/base.py`): Base Pydantic model with metaclass for relationship descriptors
- `QuerySet` (`query/builder.py`): Django-like fluent query builder with lazy evaluation
- Relationship types: Many2One, One2Many, Many2Many with lazy loading via descriptors
- Field validation and business rules

**4. Infrastructure Layer (transport)**
- `AsyncTransport` (`transport/httpx_transport.py`): HTTP/2 client with connection pooling
- `SessionManager` (`transport/session.py`): Session and authentication management
- Cache backends: Memory (default) and Redis (`cache/backends.py`)

### Key Design Patterns

**1. Relationship Management (Critical Pattern)**
- Uses Python descriptors (`Many2OneDescriptor`, `One2ManyDescriptor`, `Many2ManyDescriptor`) in `models/fields.py`
- Metaclass `OdooModelMeta` in `models/base.py` automatically sets up descriptors on class creation
- Lazy loading: Relationships return `LazyRelationship` objects that fetch data on first access
- Field metadata uses `json_schema_extra` to store Odoo-specific info (`odoo_type`, `odoo_relation`)

**2. Query Builder Pattern**
- `QuerySet` is lazy - doesn't execute until `.all()`, `.first()`, iteration, or other terminal operations
- Supports method chaining: `.filter().limit().order_by()`
- Uses `Q` objects for complex queries: `Q(name__ilike='test') | Q(email__ilike='test')`
- Filter expressions support Django-like lookups: `name__ilike`, `id__in`, etc.

**3. Context Managers**
- Client: `async with ZenooClient(...) as client:`
- Transactions: `async with client.transaction() as tx:`
- Batch operations: `async with client.batch() as batch:`

**4. MCP Integration**
- MCP Server (`mcp_server/`): Provides tools for AI assistants (Claude Desktop, Letta AI)
- HTTP Proxy (`mcp_http_proxy.py` in root): REST wrapper around MCP for Letta Cloud
- Architecture: `Letta Cloud -> HTTP Proxy (ngrok) -> MCP Server (stdio) -> Odoo`

### Important Implementation Details

**Authentication Flow:**
1. Client stores credentials via `login(database, username, password)`
2. `SessionManager` obtains session ID from Odoo's `/web/session/authenticate`
3. Session ID stored and used in subsequent RPC calls
4. Context includes `uid` (user ID) from authentication

**RPC Call Pattern:**
- All Odoo operations go through `AsyncTransport.json_rpc_call()`
- Endpoint: `/jsonrpc`
- Method format: `call` with service (e.g., 'object') and method (e.g., 'execute_kw')
- Parameters include: database, uid, password, model, method, args, kwargs

**Model Registration:**
- Models registered in `models/registry.py`
- `get_model_class()` retrieves model by Odoo name (e.g., 'res.partner')
- Common models in `models/common.py`: ResPartner, ResUsers, etc.

**Cache Key Generation:**
- Deterministic keys from model, method, and sorted parameters
- Uses MD5 hash for complex parameter sets
- Includes cache versioning for invalidation

**Transaction Implementation:**
- Uses Odoo's context `{'rollback_on_error': True}` feature
- NOT true ACID (Odoo limitation) - best effort rollback
- Tracks operations in `TransactionContext` for rollback coordination

## Important Constraints

**Type Annotations:**
- Maintain strict type hints (enforced by mypy in strict mode)
- Use `Optional[T]` for nullable fields
- Use `ClassVar` for Odoo model names: `_odoo_name: ClassVar[str]`

**Async/Await:**
- ALL I/O operations must be async
- Use `asyncio.gather()` for concurrent operations
- Proper async context manager usage

**Pydantic V2:**
- Uses Pydantic V2 API
- `model_fields` (not `__fields__`)
- `model_validate()` (not `parse_obj()`)
- `ConfigDict` (not `Config` class)

**Testing:**
- Tests use pytest-asyncio with `asyncio_mode = "auto"`
- Mock the transport layer for unit tests
- Integration tests require Odoo instance (see conftest.py)

**Common Pitfalls:**
1. Don't forget `await` on async operations - common source of bugs
2. Relationship descriptors only work on instances, not class level
3. QuerySet is lazy - clone properly when chaining to avoid mutations
4. Cache manager must be set up before using `.cache()` on queries
5. Transaction manager doesn't provide true ACID guarantees (Odoo limitation)

## File Organization

```
src/zenoo_rpc/
├── client.py              # Main ZenooClient facade
├── transport/             # HTTP layer
│   ├── httpx_transport.py # HTTP/2 transport
│   ├── session.py        # Session management
│   └── pool.py           # Connection pooling
├── models/               # Domain models
│   ├── base.py          # OdooModel base + metaclass
│   ├── fields.py        # Relationship descriptors
│   ├── relationships.py # Lazy loading logic
│   ├── registry.py      # Model registration
│   └── common.py        # Common Odoo models
├── query/               # Query builder
│   ├── builder.py       # QuerySet implementation
│   ├── filters.py       # Filter expressions, Q objects
│   ├── expressions.py   # Domain expressions
│   └── lazy.py          # Lazy collection wrappers
├── cache/               # Caching layer
│   ├── manager.py       # Cache manager
│   ├── backends.py      # Memory + Redis backends
│   ├── strategies.py    # TTL, LRU strategies
│   └── keys.py          # Cache key generation
├── transaction/         # Transaction management
│   ├── manager.py       # Transaction coordinator
│   ├── context.py       # Transaction context
│   └── exceptions.py    # Transaction errors
├── batch/               # Batch operations
│   ├── manager.py       # Batch coordinator
│   ├── executor.py      # Batch execution
│   ├── operations.py    # Operation types
│   └── context.py       # Batch context
├── retry/               # Retry mechanisms
│   ├── policies.py      # Retry policies
│   ├── strategies.py    # Backoff strategies
│   └── decorators.py    # Retry decorators
├── ai/                  # AI features (LiteLLM)
│   ├── core/           # AI client + assistant
│   ├── query/          # NL to query, optimizer
│   └── diagnostics/    # Error analyzer
├── mcp/                # MCP client integration
├── mcp_server/         # MCP server for AI assistants
└── exceptions/         # Exception hierarchy
    ├── base.py         # Base exceptions
    └── mapping.py      # Odoo error mapping
```

## Testing Patterns

**Unit Tests:**
- Mock `AsyncTransport` to avoid real Odoo calls
- Test individual components in isolation
- Located in `tests/test_*.py` matching module names

**Integration Tests:**
- Require running Odoo instance (configure in conftest.py)
- Test full request/response cycle
- Found in `tests/performance/` and integration test files

**Common Test Fixtures:**
- `client`: Mock ZenooClient with transport
- `mock_transport`: AsyncTransport mock
- `redis_cache`: Redis backend for cache tests (requires Docker)

## MCP Integration Notes

**For Letta Cloud Deployment:**
1. HTTP Proxy (`mcp_http_proxy.py`) wraps MCP server as REST API
2. Use `scripts/start_http_proxy.sh` to start proxy on port 8080
3. Expose via ngrok: `ngrok http 8080`
4. Configure in Letta Cloud with Bearer token authentication

**MCP Server Tools:**
- `search_records`: Search with filters
- `get_record`: Fetch by ID with fields
- `create_record`: Create with validation
- `update_record`: Update existing
- `delete_record`: Delete records
- `complex_search`: Advanced Q-based queries
- `batch_operation`: Bulk operations
- `analytics_query`: Aggregations

**Key Files:**
- `mcp_http_proxy.py`: HTTP proxy (root directory)
- `mcp_server/server.py`: MCP server implementation
- `mcp_server/cli.py`: CLI entry point
- `scripts/start_http_proxy.sh`: Startup script

## Common Development Workflows

**Adding a New Model:**
1. Define in `models/common.py` or create new file
2. Inherit from `OdooModel`
3. Set `_odoo_name: ClassVar[str]`
4. Add fields with proper types and `json_schema_extra` for relationships
5. Register in `models/__init__.py` if needed

**Adding a Cache Backend:**
1. Implement `CacheBackend` interface from `cache/backends.py`
2. Add async `get()`, `set()`, `delete()`, `clear()` methods
3. Handle serialization (JSON or pickle)
4. Update `CacheManager` to support new backend

**Modifying Query Builder:**
- Changes to `QuerySet` affect all queries - test thoroughly
- Maintain lazy evaluation - don't execute prematurely
- Clone state properly in chaining methods
- Update cache key generation if adding query parameters
