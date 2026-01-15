"""
Core MCP Server implementation for Zenoo RPC.

This module provides the main MCP server that exposes Odoo operations
through the Model Context Protocol, allowing AI tools to interact with Odoo.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import Tool, Resource, Prompt, TextContent, ImageContent
    MCP_AVAILABLE = True
except ImportError:
    # Mock classes for when MCP is not available
    class FastMCP:
        def __init__(self, name: str, instructions: str = ""):
            self.name = name
            self.instructions = instructions
            self.tools = {}
            self.resources = {}
            self.prompts = {}
        
        def tool(self, name: str = None):
            def decorator(func):
                tool_name = name or func.__name__
                self.tools[tool_name] = func
                return func
            return decorator
        
        def resource(self, uri_template: str):
            def decorator(func):
                self.resources[uri_template] = func
                return func
            return decorator
        
        def prompt(self, name: str = None):
            def decorator(func):
                prompt_name = name or func.__name__
                self.prompts[prompt_name] = func
                return func
            return decorator
        
        async def run(self, transport="stdio", **kwargs):
            host = kwargs.get('host', 'localhost')
            port = kwargs.get('port', 8000)
            print(f"Mock MCP server '{self.name}' running with {transport} transport")
            if transport == "http":
                print(f"Mock HTTP server would run on {host}:{port}")
            # Mock server - just wait indefinitely
            import asyncio
            await asyncio.Event().wait()
    
    class Tool:
        def __init__(self, name: str, description: str = ""):
            self.name = name
            self.description = description
    
    class Resource:
        def __init__(self, uri: str, name: str = "", description: str = ""):
            self.uri = uri
            self.name = name
            self.description = description
    
    class Prompt:
        def __init__(self, name: str, description: str = ""):
            self.name = name
            self.description = description
    
    class TextContent:
        def __init__(self, text: str):
            self.text = text
    
    class ImageContent:
        def __init__(self, data: str, mime_type: str):
            self.data = data
            self.mime_type = mime_type
    
    MCP_AVAILABLE = False

from ..client import ZenooClient
from .config import MCPServerConfig
from .security import MCPSecurityManager
from .exceptions import (
    MCPServerError,
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPToolError,
    MCPResourceError
)

logger = logging.getLogger(__name__)


class ZenooMCPServer:
    """MCP Server that exposes Zenoo RPC/Odoo operations to AI tools.
    
    This server implements the Model Context Protocol to allow AI assistants
    and other tools to interact with Odoo through a standardized interface.
    
    Features:
    - Tools: Execute Odoo operations (CRUD, search, workflows)
    - Resources: Access Odoo data (models, records, reports)
    - Prompts: Template-based Odoo queries
    - Security: Authentication, authorization, input validation
    - Performance: Caching, connection pooling, async operations
    
    Example:
        >>> config = MCPServerConfig.from_env()
        >>> server = ZenooMCPServer(config)
        >>> await server.start()
    """
    
    def __init__(self, config: MCPServerConfig):
        """Initialize MCP server.
        
        Args:
            config: Server configuration
        """
        self.config = config
        self.zenoo_client: Optional[ZenooClient] = None
        self.security_manager = MCPSecurityManager(config)
        
        # Initialize FastMCP server
        self.mcp_server = FastMCP(
            name=config.name,
            instructions=self._get_server_instructions(),
            host=config.host,
            port=config.port
        )
        
        # Register tools, resources, and prompts
        self._register_tools()
        self._register_resources()
        self._register_prompts()
        
        logger.info(f"Initialized MCP server '{config.name}'")
    
    def _get_server_instructions(self) -> str:
        """Get server instructions for AI clients."""
        return f"""
{self.config.description}

This server provides access to Odoo ERP operations through the following capabilities:

TOOLS (Actions you can perform):
- search_records: Search for records in any Odoo model
- get_record: Get a specific record by ID
- create_record: Create a new record
- update_record: Update an existing record
- delete_record: Delete a record
- execute_workflow: Execute workflow actions
- generate_report: Generate Odoo reports

RESOURCES (Data you can access):
- odoo://models - List all available Odoo models
- odoo://model/{{model_name}} - Get model information
- odoo://record/{{model_name}}/{{record_id}} - Get specific record
- odoo://search/{{model_name}}/{{domain}} - Search results

PROMPTS (Templates you can use):
- analyze_data: Analyze Odoo data with AI
- generate_report_query: Generate report queries
- suggest_workflow: Suggest workflow improvements

Authentication: {self.config.security.auth_method.value}
Rate Limits: {self.config.security.rate_limit_requests} requests per {self.config.security.rate_limit_window}s
"""
    
    async def start(self) -> None:
        """Start the MCP server."""
        try:
            # Connect to Odoo
            await self._connect_to_odoo()
            
            # Start security cleanup task
            asyncio.create_task(self._security_cleanup_task())
            
            # Run MCP server
            transport = self.config.transport_type.value
            if transport == "stdio":
                await self.mcp_server.run_stdio_async()
            elif transport == "http":
                # Use streamable-http transport for HTTP
                await self.mcp_server.run_streamable_http_async()
            else:
                raise MCPServerError(f"Unsupported transport: {transport}")
                
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise MCPServerError(f"Server startup failed: {e}") from e
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        try:
            if self.zenoo_client:
                await self.zenoo_client.close()
            logger.info("MCP server stopped")
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")

    async def _connect_to_odoo(self) -> None:
        """Connect to Odoo using Zenoo RPC."""
        try:
            self.zenoo_client = ZenooClient(self.config.odoo_url)
            await self.zenoo_client.login(
                self.config.odoo_database,
                self.config.odoo_username,
                self.config.odoo_password
            )
            logger.info("Connected to Odoo successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {e}")
            raise MCPServerError(f"Odoo connection failed: {e}") from e
    
    async def _security_cleanup_task(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                self.security_manager.cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in security cleanup task: {e}")
    
    def _register_tools(self) -> None:
        """Register MCP tools."""
        if not self.config.features.enable_tools:
            return
        
        @self.mcp_server.tool()
        async def search_records(
            model: str,
            domain: List = None,
            fields: List[str] = None,
            limit: int = 100,
            offset: int = 0,
            order: str = None
        ) -> Dict[str, Any]:
            """Search for records in an Odoo model using basic domain filters.

            This is the fundamental search tool for querying Odoo records. Use this for simple
            searches with Odoo's native domain syntax. For more advanced filtering with lookup
            expressions, use the complex_search tool instead.

            Args:
                model: Odoo model name to search
                    Examples: "res.partner", "sale.order", "product.product", "account.move"

                domain: Odoo domain filter as a list of conditions (default: [] for all records)
                    Format: [["field", "operator", "value"], ...]
                    Operators: "=", "!=", ">", ">=", "<", "<=", "like", "ilike", "in", "not in"
                    Logic: Use "|" for OR, "&" for AND (AND is default)
                    Examples:
                    - [["name", "ilike", "John"]] - Name contains "John" (case-insensitive)
                    - [["active", "=", True], ["customer_rank", ">", 0]] - Active customers
                    - ["|", ["email", "!=", False], ["phone", "!=", False]] - Has email OR phone

                fields: List of field names to retrieve (default: None retrieves all fields)
                    Examples: ["id", "name", "email"], ["id", "display_name", "partner_id"]
                    Note: Specifying fewer fields improves performance for large datasets

                limit: Maximum number of records to return (default: 100)
                    Use lower limits for faster responses, higher for bulk data retrieval

                offset: Number of records to skip, useful for pagination (default: 0)
                    Example: offset=0 limit=50 (page 1), offset=50 limit=50 (page 2)

                order: Sort order specification (default: None for natural order)
                    Format: "field_name ASC" or "field_name DESC"
                    Examples: "name ASC", "create_date DESC", "partner_id, date_order DESC"

            Returns:
                Dictionary containing:
                - records: List of matching record dictionaries
                - count: Number of records returned (up to limit)
                - model: Model name that was searched
                - domain: Domain filter that was applied
                - total_count: Total matching records (if available)

            Examples:
                # Search for all active partners
                {
                    "model": "res.partner",
                    "domain": [["active", "=", True]],
                    "limit": 50
                }

                # Search for recent sales orders with specific fields
                {
                    "model": "sale.order",
                    "domain": [["date_order", ">=", "2025-01-01"], ["state", "=", "sale"]],
                    "fields": ["id", "name", "partner_id", "amount_total", "date_order"],
                    "order": "date_order DESC",
                    "limit": 25
                }

                # Pagination example - get second page of partners
                {
                    "model": "res.partner",
                    "domain": [["is_company", "=", True]],
                    "limit": 20,
                    "offset": 20
                }

            Notes:
                - For complex filtering with lookup expressions (ilike, gt, lt, etc.), use complex_search
                - Empty domain [] returns all records (subject to limit)
                - Use fields parameter to improve performance when you don't need all data
                - Combine with offset/limit for efficient pagination
            """
            return await self._execute_tool("search_records", {
                "model": model,
                "domain": domain or [],
                "fields": fields,
                "limit": limit,
                "offset": offset,
                "order": order
            })
        
        @self.mcp_server.tool()
        async def get_record(
            model: str,
            record_id: int,
            fields: List[str] = None
        ) -> Dict[str, Any]:
            """Retrieve a single specific record by its ID from an Odoo model.

            Use this tool when you know the exact record ID and want to fetch its data.
            This is faster than searching when you have the ID. Returns all fields by default,
            or specify which fields you need for better performance.

            Args:
                model: Odoo model name where the record exists
                    Examples: "res.partner", "sale.order", "product.product", "res.users"

                record_id: The unique integer ID of the record to retrieve
                    Note: This is the internal Odoo record ID (integer), not external references

                fields: Optional list of specific field names to retrieve (default: None for all fields)
                    Examples: ["id", "name", "email", "phone"], ["display_name", "partner_id"]
                    Tip: Requesting fewer fields improves performance and reduces response size

            Returns:
                Dictionary containing:
                - record: Dictionary with the record's field values
                - model: Model name
                - record_id: ID of the retrieved record

            Examples:
                # Get full partner record
                {
                    "model": "res.partner",
                    "record_id": 42
                }

                # Get specific fields from a sales order
                {
                    "model": "sale.order",
                    "record_id": 150,
                    "fields": ["id", "name", "partner_id", "amount_total", "state", "date_order"]
                }

                # Get user information
                {
                    "model": "res.users",
                    "record_id": 2,
                    "fields": ["id", "name", "login", "email", "company_id"]
                }

            Error Handling:
                - Returns error if record_id does not exist in the model
                - Returns error if specified fields don't exist in the model

            Notes:
                - Much faster than search_records when you know the exact ID
                - Use fields parameter to optimize performance for large records
                - Related fields (Many2one, One2many) may return just IDs unless explicitly requested
            """
            return await self._execute_tool("get_record", {
                "model": model,
                "record_id": record_id,
                "fields": fields
            })
        
        @self.mcp_server.tool()
        async def create_record(
            model: str,
            values: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Create a new record in an Odoo model with specified field values.

            Creates a single new record and returns its ID and data. Field values are validated
            according to the model's field definitions. Required fields must be provided unless
            they have default values in Odoo.

            Args:
                model: Odoo model name where the record will be created
                    Examples: "res.partner", "sale.order", "product.product", "crm.lead"

                values: Dictionary of field names and their values for the new record
                    Format: {"field_name": value, ...}
                    - Simple fields: Use direct values (strings, numbers, booleans)
                    - Many2one fields: Use integer ID of related record
                    - One2many/Many2many: Use special commands (see examples)
                    - Date fields: Use "YYYY-MM-DD" format
                    - Datetime fields: Use "YYYY-MM-DD HH:MM:SS" format

            Returns:
                Dictionary containing:
                - record: Created record data with all field values
                - model: Model name
                - created: True (confirmation flag)
                - id: ID of the newly created record

            Examples:
                # Create a new partner (contact/company)
                {
                    "model": "res.partner",
                    "values": {
                        "name": "Acme Corporation",
                        "email": "contact@acme.com",
                        "phone": "+1-555-0123",
                        "is_company": true,
                        "street": "123 Main St",
                        "city": "New York",
                        "country_id": 233  # USA country ID
                    }
                }

                # Create a sales order
                {
                    "model": "sale.order",
                    "values": {
                        "partner_id": 42,
                        "date_order": "2025-01-15",
                        "order_line": [
                            [0, 0, {
                                "product_id": 10,
                                "product_uom_qty": 5,
                                "price_unit": 99.99
                            }]
                        ]
                    }
                }

                # Create a product
                {
                    "model": "product.product",
                    "values": {
                        "name": "Premium Widget",
                        "type": "product",
                        "list_price": 149.99,
                        "standard_price": 75.00,
                        "categ_id": 1
                    }
                }

            One2many/Many2many Commands:
                Use these command tuples to manage related records:
                - [0, 0, {values}]: Create new related record with values
                - [4, id]: Link existing record with given ID
                - [6, 0, [ids]]: Replace all with list of IDs

            Validation:
                - Required fields must be provided (or have defaults)
                - Field types are validated (string, integer, float, boolean, etc.)
                - Foreign key references must point to existing records
                - Returns error if validation fails

            Notes:
                - For bulk creation, use batch_operation tool instead
                - Created record ID is returned in the response
                - Some computed fields may be auto-populated by Odoo
                - Odoo may apply default values for fields not specified
            """
            return await self._execute_tool("create_record", {
                "model": model,
                "values": values
            })
        
        @self.mcp_server.tool()
        async def update_record(
            model: str,
            record_id: int,
            values: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Update an existing record by modifying specific field values.

            Modifies only the fields specified in the values dictionary. All other fields
            remain unchanged. The record must exist or an error will be returned. Field
            values are validated according to model constraints.

            Args:
                model: Odoo model name containing the record to update
                    Examples: "res.partner", "sale.order", "product.product", "crm.lead"

                record_id: Integer ID of the existing record to update
                    Note: This must be a valid, existing record ID

                values: Dictionary of field names and new values to update
                    Format: {"field_name": new_value, ...}
                    - Only specify fields you want to change
                    - Omitted fields retain their current values
                    - Many2one fields: Use integer ID of related record
                    - One2many/Many2many: Use special commands (see examples below)
                    - Set field to False/null: Use False or None

            Returns:
                Dictionary containing:
                - record: Updated record data with new field values
                - model: Model name
                - updated: True (confirmation flag)

            Examples:
                # Update partner contact information
                {
                    "model": "res.partner",
                    "record_id": 42,
                    "values": {
                        "email": "newemail@acme.com",
                        "phone": "+1-555-9999",
                        "mobile": "+1-555-8888"
                    }
                }

                # Update sales order state and add notes
                {
                    "model": "sale.order",
                    "record_id": 150,
                    "values": {
                        "state": "sale",
                        "note": "Customer requested expedited shipping"
                    }
                }

                # Update product pricing
                {
                    "model": "product.product",
                    "record_id": 25,
                    "values": {
                        "list_price": 199.99,
                        "standard_price": 100.00
                    }
                }

                # Update One2many field (e.g., adding order lines)
                {
                    "model": "sale.order",
                    "record_id": 150,
                    "values": {
                        "order_line": [
                            [0, 0, {"product_id": 15, "product_uom_qty": 2, "price_unit": 50.00}],
                            [1, 123, {"product_uom_qty": 5}],
                            [2, 124]
                        ]
                    }
                }

            One2many/Many2many Update Commands:
                - [0, 0, {values}]: Create and link new related record
                - [1, id, {values}]: Update existing related record with given ID
                - [2, id]: Delete related record with given ID
                - [3, id]: Unlink (remove relation but don't delete) record with ID
                - [4, id]: Link existing record
                - [5]: Unlink all (clear all relations)
                - [6, 0, [ids]]: Replace all relations with given IDs

            Validation:
                - Record must exist (checked before update)
                - Field constraints are validated
                - Related record IDs must exist
                - Returns error if validation fails

            Error Handling:
                - Returns error if record_id doesn't exist
                - Returns error if fields don't exist in model
                - Returns error if values don't meet field constraints

            Notes:
                - For bulk updates, use batch_operation tool instead
                - Only specified fields are updated; others remain unchanged
                - Some computed fields may be automatically recalculated
                - Workflow triggers and constraints are respected
            """
            return await self._execute_tool("update_record", {
                "model": model,
                "record_id": record_id,
                "values": values
            })
        
        @self.mcp_server.tool()
        async def delete_record(
            model: str,
            record_id: int
        ) -> Dict[str, Any]:
            """Permanently delete a record from an Odoo model.

            Removes the specified record from the database. This operation is irreversible
            and will also handle related records according to the model's ondelete constraints
            (cascade, restrict, set null, etc.). Use with caution.

            Args:
                model: Odoo model name containing the record to delete
                    Examples: "res.partner", "sale.order", "product.product", "crm.lead"

                record_id: Integer ID of the record to permanently delete
                    Warning: This record will be completely removed from the database

            Returns:
                Dictionary containing:
                - id: ID of the deleted record
                - model: Model name
                - deleted: True (confirmation flag)

            Examples:
                # Delete a draft partner record
                {
                    "model": "res.partner",
                    "record_id": 999
                }

                # Delete a cancelled sales order
                {
                    "model": "sale.order",
                    "record_id": 150
                }

                # Delete a test product
                {
                    "model": "product.product",
                    "record_id": 1234
                }

            Important Warnings:
                - PERMANENT: Deleted records cannot be recovered
                - CASCADE: May delete related records if ondelete='cascade' is set
                - CONSTRAINTS: Deletion may fail if other records depend on this one
                - AUDIT: Consider using 'active=False' instead of deletion for audit trails

            Related Record Behavior (ondelete):
                - cascade: Related records are also deleted
                - restrict: Deletion fails if related records exist
                - set null: Foreign keys in related records are set to null
                - set default: Foreign keys are set to default value

            Error Handling:
                - Returns error if record_id doesn't exist
                - Returns error if deletion violates database constraints
                - Returns error if user lacks delete permissions

            Alternatives to Deletion:
                Instead of permanent deletion, consider:
                - Archive: Update 'active' field to False (if model supports it)
                - Cancel: Update 'state' field to 'cancel'
                - Mark as obsolete: Use custom status fields

            Best Practices:
                - Verify record exists before deletion (use get_record first)
                - Check for dependent records that might be affected
                - Use batch_operation for deleting multiple records
                - Prefer archiving over deletion when possible for audit trails
                - Test deletions in development environment first

            Notes:
                - For bulk deletion, use batch_operation tool instead
                - Some models may override unlink() with custom logic
                - System/admin records may have deletion restrictions
                - Deletion triggers model constraints and business logic
            """
            return await self._execute_tool("delete_record", {
                "model": model,
                "record_id": record_id
            })

        # Advanced tools leveraging Zenoo RPC features
        @self.mcp_server.tool()
        async def complex_search(
            model: str,
            filters: Dict[str, Any],
            order_by: str = None,
            limit: int = 100,
            include_relationships: bool = False
        ) -> Dict[str, Any]:
            """Advanced search using QueryBuilder with complex filters and Django-like lookup expressions.

            Supports powerful filtering with multiple operators and automatic AND combination of filters.

            Args:
                model: Odoo model name (e.g., 'res.partner', 'sale.order')
                filters: Complex filters using lookup expressions. Supports two formats:
                    1. Simple: {"name": "John", "active": true}
                    2. Complex: {"name": {"ilike": "%john%"}, "customer_rank": {"gt": 0}}

                    Available lookup expressions:
                    - ilike: Case-insensitive pattern match (e.g., {"name": {"ilike": "%company%"}})
                    - gt/gte: Greater than / greater than or equal (e.g., {"customer_rank": {"gt": 0}})
                    - lt/lte: Less than / less than or equal (e.g., {"age": {"lt": 65}})
                    - ne: Not equal (e.g., {"email": {"ne": false}})
                    - in: Value in list (e.g., {"id": {"in": [1, 2, 3]}})
                    - Direct value: Exact match (e.g., {"is_company": true})

                order_by: Sort field(s). Prefix with '-' for descending order
                    Examples: 'name', '-create_date', 'city,name'
                limit: Maximum number of records to return (default: 100)
                include_relationships: Include related record data (default: false)

            Returns:
                Dictionary with:
                - records: List of matching records
                - count: Number of records returned
                - model: Model name searched
                - filters_applied: Filters that were applied
                - order_by: Ordering used
                - includes_relationships: Whether relationships were included

            Examples:
                # Search for active companies with email
                {
                    "model": "res.partner",
                    "filters": {
                        "is_company": true,
                        "active": true,
                        "email": {"ne": false}
                    },
                    "order_by": "name",
                    "limit": 50
                }

                # Search with pattern matching and date range
                {
                    "model": "res.partner",
                    "filters": {
                        "name": {"ilike": "%tech%"},
                        "create_date": {"gte": "2025-01-01"}
                    },
                    "order_by": "-create_date",
                    "limit": 25
                }

                # Search specific IDs with relationships
                {
                    "model": "res.partner",
                    "filters": {
                        "id": {"in": [1, 2, 3, 10, 20]}
                    },
                    "include_relationships": true,
                    "limit": 10
                }
            """
            return await self._execute_tool("complex_search", {
                "model": model,
                "filters": filters,
                "order_by": order_by,
                "limit": limit,
                "include_relationships": include_relationships
            })

        @self.mcp_server.tool()
        async def batch_operation(
            operation: str,
            model: str,
            records: List[Dict[str, Any]]
        ) -> Dict[str, Any]:
            """Perform batch operations (create, update, delete) on multiple records for high performance.

            Processes multiple records in a single operation, ideal for bulk data manipulation.
            All records are processed individually but returned together for efficiency.

            Args:
                operation: Operation type - must be one of:
                    - 'create': Create multiple new records
                    - 'update': Update multiple existing records (requires 'id' in each record)
                    - 'delete': Delete multiple records (requires 'id' in each record)

                model: Odoo model name (e.g., 'res.partner', 'sale.order', 'product.product')

                records: List of record dictionaries. Structure depends on operation:
                    - For 'create': List of dicts with field values (no 'id' needed)
                    - For 'update': List of dicts with 'id' + fields to update
                    - For 'delete': List of dicts with 'id' field only

            Returns:
                Dictionary with:
                - operation: The operation that was performed
                - model: Model name
                - processed_count: Number of records processed
                - results: List of operation results for each record

            Examples:
                # Batch create multiple partners
                {
                    "operation": "create",
                    "model": "res.partner",
                    "records": [
                        {"name": "Company A", "email": "info@companya.com", "is_company": true},
                        {"name": "Company B", "email": "info@companyb.com", "is_company": true},
                        {"name": "John Doe", "email": "john@example.com", "is_company": false}
                    ]
                }

                # Batch update multiple partners
                {
                    "operation": "update",
                    "model": "res.partner",
                    "records": [
                        {"id": 10, "phone": "+1-555-0001", "active": true},
                        {"id": 20, "phone": "+1-555-0002", "city": "New York"},
                        {"id": 30, "email": "updated@example.com"}
                    ]
                }

                # Batch delete multiple partners
                {
                    "operation": "delete",
                    "model": "res.partner",
                    "records": [
                        {"id": 100},
                        {"id": 101},
                        {"id": 102}
                    ]
                }

            Notes:
                - All operations process records sequentially but return together
                - For 'update' and 'delete', the 'id' field is required in each record
                - Failed operations for individual records will be reflected in results
                - Use this for bulk operations instead of calling individual create/update/delete
            """
            return await self._execute_tool("batch_operation", {
                "operation": operation,
                "model": model,
                "records": records
            })

        @self.mcp_server.tool()
        async def analytics_query(
            model: str,
            group_by: List[str],
            aggregates: Dict[str, str],
            filters: Dict[str, Any] = None,
            date_range: Dict[str, str] = None
        ) -> Dict[str, Any]:
            """Perform analytics queries with grouping and aggregation functions for data analysis.

            Enables powerful data analytics by grouping records and applying aggregate functions
            like sum, count, avg, min, max. Ideal for reports, dashboards, and business intelligence.

            Args:
                model: Odoo model name (e.g., 'sale.order', 'account.move', 'res.partner')

                group_by: List of field names to group results by
                    Examples: ['state'], ['partner_id', 'state'], ['create_date']

                aggregates: Dictionary mapping result field names to aggregate functions
                    Supported functions: 'sum', 'count', 'avg', 'min', 'max'
                    Format: {'result_name': 'function:field_name'}
                    Examples:
                    - {'total_amount': 'sum:amount_total', 'order_count': 'count:id'}
                    - {'average_price': 'avg:price_unit', 'max_qty': 'max:product_qty'}

                filters: Optional filters to apply before aggregation (same format as complex_search)
                    Examples: {'state': 'sale'}, {'partner_id': {'ne': false}}

                date_range: Optional date range filter for time-based analysis
                    Format: {'field': 'date_field_name', 'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
                    Example: {'field': 'date_order', 'start': '2025-01-01', 'end': '2025-12-31'}

            Returns:
                Dictionary with:
                - model: Model name analyzed
                - groups: List of grouped results with aggregate values
                - group_by: Fields used for grouping
                - aggregates: Aggregations applied
                - total_groups: Number of groups returned

            Examples:
                # Sales by partner
                {
                    "model": "sale.order",
                    "group_by": ["partner_id"],
                    "aggregates": {
                        "total_sales": "sum:amount_total",
                        "order_count": "count:id"
                    },
                    "filters": {"state": "sale"}
                }

                # Monthly sales revenue with date range
                {
                    "model": "sale.order",
                    "group_by": ["create_date"],
                    "aggregates": {
                        "revenue": "sum:amount_total",
                        "avg_order": "avg:amount_total",
                        "orders": "count:id"
                    },
                    "filters": {"state": "sale"},
                    "date_range": {
                        "field": "date_order",
                        "start": "2025-01-01",
                        "end": "2025-12-31"
                    }
                }

                # Product inventory analysis
                {
                    "model": "product.product",
                    "group_by": ["categ_id"],
                    "aggregates": {
                        "total_qty": "sum:qty_available",
                        "product_count": "count:id",
                        "avg_price": "avg:list_price"
                    },
                    "filters": {"active": true}
                }

            Notes:
                - Results are automatically grouped by the specified fields
                - Aggregate functions operate on all records within each group
                - Use filters to narrow down the dataset before aggregation
                - Date range provides convenient time-based filtering
                - Useful for dashboards, reports, and business metrics
            """
            return await self._execute_tool("analytics_query", {
                "model": model,
                "group_by": group_by,
                "aggregates": aggregates,
                "filters": filters or {},
                "date_range": date_range
            })

        @self.mcp_server.tool()
        async def execute_method(
            model: str,
            method: str,
            args: List[Any] = None,
            kwargs: Dict[str, Any] = None
        ) -> Dict[str, Any]:
            """Execute any method on an Odoo model - the universal method caller.

            This is the most flexible tool that allows calling ANY method available on an Odoo model.
            Use this for workflow actions, business logic methods, computed operations, and any
            custom methods defined in Odoo modules.

            Args:
                model: Odoo model name (e.g., 'sale.order', 'res.partner', 'account.move')

                method: Method name to execute on the model. Common methods include:
                    Workflow/Actions:
                    - 'action_confirm': Confirm orders/invoices
                    - 'action_cancel': Cancel documents
                    - 'action_done': Mark as done
                    - 'action_draft': Reset to draft
                    - 'action_post': Post journal entries
                    - 'button_validate': Validate transfers

                    Data Operations:
                    - 'copy': Duplicate a record (pass record ID in args)
                    - 'default_get': Get default values for fields
                    - 'fields_get': Get field definitions
                    - 'name_search': Search by name
                    - 'name_get': Get display names for IDs

                    Computations:
                    - 'get_views': Get view definitions
                    - 'check_access_rights': Check user permissions
                    - Any custom method defined in the model

                args: Positional arguments for the method (default: [])
                    Format: List of values passed to the method
                    Examples:
                    - For methods on specific records: [[record_id]] or [[id1, id2, ...]]
                    - For copy: [record_id]
                    - For name_search: ['search_term']
                    - For fields_get: [] or [['field1', 'field2']]

                kwargs: Keyword arguments for the method (default: {})
                    Format: Dictionary of named parameters
                    Examples:
                    - {'context': {'lang': 'en_US'}}
                    - {'limit': 10, 'operator': 'ilike'}

            Returns:
                Dictionary with:
                - model: Model name
                - method: Method that was executed
                - result: Return value from the method (varies by method)
                - success: True if execution completed

            Examples:
                # Confirm a sales order
                {
                    "model": "sale.order",
                    "method": "action_confirm",
                    "args": [[42]]
                }

                # Post an invoice
                {
                    "model": "account.move",
                    "method": "action_post",
                    "args": [[150]]
                }

                # Duplicate a partner record
                {
                    "model": "res.partner",
                    "method": "copy",
                    "args": [25],
                    "kwargs": {"default": {"name": "Copy of Partner"}}
                }

                # Get default values for new sale order
                {
                    "model": "sale.order",
                    "method": "default_get",
                    "args": [["partner_id", "date_order", "pricelist_id"]]
                }

                # Search partners by name
                {
                    "model": "res.partner",
                    "method": "name_search",
                    "args": ["Acme"],
                    "kwargs": {"limit": 10, "operator": "ilike"}
                }

                # Get field definitions for a model
                {
                    "model": "res.partner",
                    "method": "fields_get",
                    "args": [["name", "email", "phone"]],
                    "kwargs": {"attributes": ["string", "type", "required"]}
                }

                # Check access rights
                {
                    "model": "sale.order",
                    "method": "check_access_rights",
                    "args": ["write"],
                    "kwargs": {"raise_exception": false}
                }

                # Cancel multiple orders
                {
                    "model": "sale.order",
                    "method": "action_cancel",
                    "args": [[10, 11, 12]]
                }

                # Validate a stock picking
                {
                    "model": "stock.picking",
                    "method": "button_validate",
                    "args": [[75]]
                }

            Notes:
                - Methods that operate on records typically expect record IDs in a list: [[id1, id2]]
                - Some methods return True/False, others return data structures
                - Check Odoo model documentation for available methods
                - Custom module methods are also accessible
                - Use this for any operation not covered by basic CRUD tools
            """
            return await self._execute_tool("execute_method", {
                "model": model,
                "method": method,
                "args": args or [],
                "kwargs": kwargs or {}
            })

    def _register_resources(self) -> None:
        """Register MCP resources."""
        if not self.config.features.enable_resources:
            return
        
        @self.mcp_server.resource("odoo://models")
        async def list_models() -> str:
            """List all available Odoo models."""
            return await self._execute_resource("list_models", {})
        
        @self.mcp_server.resource("odoo://model/{model_name}")
        async def get_model_info(model_name: str) -> str:
            """Get information about a specific model."""
            return await self._execute_resource("get_model_info", {
                "model_name": model_name
            })
        
        @self.mcp_server.resource("odoo://record/{model_name}/{record_id}")
        async def get_record_resource(model_name: str, record_id: int) -> str:
            """Get a specific record as a resource."""
            return await self._execute_resource("get_record_resource", {
                "model_name": model_name,
                "record_id": record_id
            })
    
    def _register_prompts(self) -> None:
        """Register MCP prompts."""
        if not self.config.features.enable_prompts:
            return
        
        @self.mcp_server.prompt()
        async def analyze_data(
            model: str = "res.partner",
            analysis_type: str = "summary"
        ) -> str:
            """Generate a prompt for analyzing Odoo data."""
            return await self._execute_prompt("analyze_data", {
                "model": model,
                "analysis_type": analysis_type
            })
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with security and validation."""
        try:
            # Security validation would go here
            # For now, simplified implementation
            
            if not self.zenoo_client:
                raise MCPToolError("Not connected to Odoo")
            
            if tool_name == "search_records":
                return await self._handle_search_records(arguments)
            elif tool_name == "get_record":
                return await self._handle_get_record(arguments)
            elif tool_name == "create_record":
                return await self._handle_create_record(arguments)
            elif tool_name == "update_record":
                return await self._handle_update_record(arguments)
            elif tool_name == "delete_record":
                return await self._handle_delete_record(arguments)
            elif tool_name == "complex_search":
                return await self._handle_complex_search(arguments)
            elif tool_name == "batch_operation":
                return await self._handle_batch_operation(arguments)
            elif tool_name == "analytics_query":
                return await self._handle_analytics_query(arguments)
            elif tool_name == "execute_method":
                return await self._handle_execute_method(arguments)
            else:
                raise MCPToolError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            raise MCPToolError(f"Tool '{tool_name}' failed: {e}") from e
    
    async def _handle_search_records(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search_records tool using Zenoo RPC search_read."""
        try:
            model_name = args["model"]
            domain = args.get("domain", [])
            fields = args.get("fields")
            limit = args.get("limit", 100)
            offset = args.get("offset", 0)
            order = args.get("order")

            # Use search_read for direct Odoo access
            records = await self.zenoo_client.search_read(
                model=model_name,
                domain=domain,
                fields=fields,
                limit=limit,
                offset=offset,
                order=order
            )

            return {
                "records": records,
                "count": len(records),
                "model": model_name,
                "has_more": len(records) == limit,
                "domain": domain,
                "fields": fields or "all"
            }

        except Exception as e:
            logger.error(f"Search records failed: {e}")
            raise MCPToolError(f"Search failed for model {args.get('model')}: {e}")

    def _apply_domain_to_query(self, query, domain: List) -> Any:
        """Convert Odoo domain to QueryBuilder filters."""
        from ..query import Q

        # This is a simplified domain converter
        # In a full implementation, we'd need to handle complex domain logic
        for item in domain:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, operator, value = item

                if operator == "=":
                    query = query.filter(**{field: value})
                elif operator == "!=":
                    query = query.exclude(**{field: value})
                elif operator == "like" or operator == "ilike":
                    query = query.filter(**{f"{field}__ilike": value})
                elif operator == "in":
                    query = query.filter(**{f"{field}__in": value})
                elif operator == ">":
                    query = query.filter(**{f"{field}__gt": value})
                elif operator == ">=":
                    query = query.filter(**{f"{field}__gte": value})
                elif operator == "<":
                    query = query.filter(**{f"{field}__lt": value})
                elif operator == "<=":
                    query = query.filter(**{f"{field}__lte": value})

        return query
    
    async def _handle_get_record(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_record tool using Zenoo RPC OdooModel."""
        try:
            model_name = args["model"]
            record_id = args["record_id"]
            fields = args.get("fields")

            # Use read() for direct Odoo access - most reliable method
            records = await self.zenoo_client.read(
                model=model_name,
                ids=[record_id],
                fields=fields
            )

            if not records:
                raise MCPToolError(f"Record {record_id} not found in model {model_name}")

            record_data = records[0]

            return {
                "record": record_data,
                "model": model_name,
                "id": record_id
            }

        except Exception as e:
            logger.error(f"Get record failed: {e}")
            raise MCPToolError(f"Failed to get record {args.get('record_id')} from {args.get('model')}: {e}")
    
    async def _handle_create_record(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_record tool using Zenoo RPC."""
        try:
            model_name = args["model"]
            values = args["values"]

            # Use direct create() method for reliability
            # (transactions require setup_transaction_manager() to be called first)
            record_id = await self.zenoo_client.create(model_name, values)

            # Build record data with ID and values
            record_data = {"id": record_id, **values}

            return {
                "record": record_data,
                "model": model_name,
                "created": True,
                "id": record_id
            }

        except Exception as e:
            logger.error(f"Create record failed: {e}")
            raise MCPToolError(f"Failed to create record in {args.get('model')}: {e}")
    
    async def _handle_update_record(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_record tool using Zenoo RPC."""
        try:
            model_name = args["model"]
            record_id = args["record_id"]
            values = args["values"]

            # Use direct write() method for reliability
            # (transactions require setup_transaction_manager() to be called first)
            success = await self.zenoo_client.write(model_name, [record_id], values)
            if not success:
                raise MCPToolError(f"Failed to update record {record_id} in model {model_name}")

            # Return updated record data
            record_data = {"id": record_id, **values}

            return {
                "record": record_data,
                "model": model_name,
                "updated": True,
            }

        except Exception as e:
            logger.error(f"Update record failed: {e}")
            raise MCPToolError(f"Failed to update record {args.get('record_id')} in {args.get('model')}: {e}")
    
    async def _handle_delete_record(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_record tool using Zenoo RPC."""
        try:
            model_name = args["model"]
            record_id = args["record_id"]

            # Use direct unlink() method for reliability
            # (transactions require setup_transaction_manager() to be called first)
            success = await self.zenoo_client.unlink(model_name, [record_id])
            if not success:
                raise MCPToolError(f"Failed to delete record {record_id} from model {model_name}")

            return {
                "id": record_id,
                "model": model_name,
                "deleted": True,
            }

        except Exception as e:
            logger.error(f"Delete record failed: {e}")
            raise MCPToolError(f"Failed to delete record {args.get('record_id')} from {args.get('model')}: {e}")
    
    async def _execute_resource(self, resource_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a resource request."""
        try:
            if resource_name == "list_models":
                return await self._handle_list_models_resource()
            elif resource_name == "get_model_info":
                return await self._handle_model_info_resource(arguments)
            elif resource_name == "get_record_resource":
                return await self._handle_record_resource(arguments)
            else:
                return json.dumps({
                    "error": f"Unknown resource: {resource_name}",
                    "available_resources": ["list_models", "get_model_info", "get_record_resource"]
                })
        except Exception as e:
            logger.error(f"Resource execution failed: {e}")
            return json.dumps({
                "error": f"Resource execution failed: {e}",
                "resource": resource_name,
                "arguments": arguments
            })
    
    async def _handle_list_models_resource(self) -> str:
        """Handle list_models resource - get all available Odoo models."""
        try:
            # Get list of models from Odoo
            models = await self.zenoo_client.execute_kw(
                'ir.model', 'search_read',
                [[]],
                {'fields': ['model', 'name', 'info']}
            )

            return json.dumps({
                "resource": "list_models",
                "count": len(models),
                "models": models[:50]  # Limit to first 50 for readability
            })
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return json.dumps({"error": f"Failed to list models: {e}"})

    async def _handle_model_info_resource(self, arguments: Dict[str, Any]) -> str:
        """Handle get_model_info resource - get info about specific model."""
        try:
            model_name = arguments.get("model_name")
            if not model_name:
                return json.dumps({"error": "model_name is required"})

            # Get model information
            model_info = await self.zenoo_client.execute_kw(
                'ir.model', 'search_read',
                [[['model', '=', model_name]]],
                {'fields': ['model', 'name', 'info']}
            )

            # Get model fields
            fields = await self.zenoo_client.execute_kw(
                'ir.model.fields', 'search_read',
                [[['model', '=', model_name]]],
                {'fields': ['name', 'field_description', 'ttype', 'required']}
            )

            return json.dumps({
                "resource": "get_model_info",
                "model_name": model_name,
                "model_info": model_info[0] if model_info else None,
                "fields": fields[:20]  # Limit fields for readability
            })
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return json.dumps({"error": f"Failed to get model info: {e}"})

    async def _handle_record_resource(self, arguments: Dict[str, Any]) -> str:
        """Handle get_record_resource - get specific record data."""
        try:
            model_name = arguments.get("model_name")
            record_id = arguments.get("record_id")

            if not model_name or not record_id:
                return json.dumps({"error": "model_name and record_id are required"})

            # Get record data
            records = await self.zenoo_client.search_read(
                model_name,
                [['id', '=', int(record_id)]],
                limit=1
            )

            return json.dumps({
                "resource": "get_record_resource",
                "model_name": model_name,
                "record_id": record_id,
                "record": records[0] if records else None
            })
        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return json.dumps({"error": f"Failed to get record: {e}"})

    async def _execute_prompt(self, prompt_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a prompt request."""
        # Mock implementation
        return f"Mock prompt for {prompt_name} with args: {arguments}"

    # Advanced tool handlers leveraging Zenoo RPC features
    async def _handle_complex_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle complex search using QueryBuilder with advanced features."""
        try:
            from ..models.registry import get_model_class
            from ..query import Q, Field

            model_name = args["model"]
            filters = args.get("filters", {})
            order_by = args.get("order_by")
            limit = args.get("limit", 100)
            include_relationships = args.get("include_relationships", False)

            # Try to get registered model class for type safety
            try:
                model_class = get_model_class(model_name)
                query = self.zenoo_client.model(model_class)
            except (KeyError, ImportError):
                # Fallback to dynamic model access
                query = self.zenoo_client.model(model_name)

            # Apply complex filters using Q objects
            if filters:
                q_filters = []
                for field, value in filters.items():
                    if isinstance(value, dict):
                        # Handle complex filters like {'name__ilike': 'test', 'age__gt': 18}
                        for lookup, val in value.items():
                            q_filters.append(Q(**{f"{field}__{lookup}": val}))
                    else:
                        q_filters.append(Q(**{field: value}))

                # Combine filters with AND
                if q_filters:
                    combined_filter = q_filters[0]
                    for q_filter in q_filters[1:]:
                        combined_filter = combined_filter & q_filter
                    query = query.filter(combined_filter)

            # Apply ordering
            if order_by:
                query = query.order_by(order_by)

            # Apply limit
            query = query.limit(limit)

            # Execute query
            records = await query.all()

            # Include relationships if requested
            result_data = []
            for record in records:
                if hasattr(record, 'to_dict'):
                    record_dict = record.to_dict()

                    # Include relationship data
                    if include_relationships and hasattr(record, '_get_relationships'):
                        relationships = await record._get_relationships()
                        record_dict["_relationships"] = relationships

                    result_data.append(record_dict)
                else:
                    result_data.append(dict(record))

            return {
                "records": result_data,
                "count": len(result_data),
                "model": model_name,
                "filters_applied": filters,
                "order_by": order_by,
                "includes_relationships": include_relationships
            }

        except Exception as e:
            logger.error(f"Complex search failed: {e}")
            raise MCPToolError(f"Complex search failed for model {args.get('model')}: {e}")

    async def _handle_batch_operation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch operations for high performance."""
        try:
            operation = args["operation"]
            model_name = args["model"]
            records = args["records"]

            # Use direct methods for reliability
            # (transactions require setup_transaction_manager() to be called first)
            results = []

            if operation == "create":
                # Batch create - handle multiple records
                for record_data in records:
                    record_id = await self.zenoo_client.create(model_name, record_data)
                    results.append({"id": record_id, **record_data})

            elif operation == "update":
                # Batch update
                for record_data in records:
                    record_id = record_data.pop("id")
                    success = await self.zenoo_client.write(model_name, [record_id], record_data)
                    results.append({"id": record_id, "updated": success, **record_data})

            elif operation == "delete":
                # Batch delete
                record_ids = [r["id"] for r in records]
                success = await self.zenoo_client.unlink(model_name, record_ids)
                results = [{"id": rid, "deleted": success} for rid in record_ids]

            else:
                raise MCPToolError(f"Unknown batch operation: {operation}")

            return {
                "operation": operation,
                "model": model_name,
                "processed_count": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Batch operation failed: {e}")
            raise MCPToolError(f"Batch {args.get('operation')} failed for model {args.get('model')}: {e}")

    async def _handle_analytics_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analytics queries with aggregation using Odoo's read_group."""
        try:
            model_name = args["model"]
            group_by = args["group_by"]
            aggregates = args["aggregates"]
            filters = args.get("filters", {})
            date_range = args.get("date_range")

            # Build domain (Odoo filter format)
            domain = []

            # Apply basic filters
            if filters:
                for field, value in filters.items():
                    if isinstance(value, dict):
                        # Handle complex filters
                        for operator, val in value.items():
                            if operator == "ne":
                                domain.append([field, "!=", val])
                            elif operator == "gt":
                                domain.append([field, ">", val])
                            elif operator == "gte":
                                domain.append([field, ">=", val])
                            elif operator == "lt":
                                domain.append([field, "<", val])
                            elif operator == "lte":
                                domain.append([field, "<=", val])
                            elif operator == "in":
                                domain.append([field, "in", val])
                            elif operator == "ilike":
                                domain.append([field, "ilike", val])
                            else:
                                domain.append([field, "=", val])
                    else:
                        domain.append([field, "=", value])

            # Apply date range filter
            if date_range:
                start_date = date_range.get("start")
                end_date = date_range.get("end")
                date_field = date_range.get("field", "create_date")

                if start_date:
                    domain.append([date_field, ">=", start_date])
                if end_date:
                    domain.append([date_field, "<=", end_date])

            # Build fields list for aggregation
            # Odoo's read_group requires "field:agg" format
            fields_to_aggregate = []
            for alias, agg_spec in aggregates.items():
                # Parse "function:field" format
                if ":" in agg_spec:
                    func, field = agg_spec.split(":", 1)
                    fields_to_aggregate.append(f"{field}:{func}")
                else:
                    # Assume it's just a field name, default to sum
                    fields_to_aggregate.append(f"{agg_spec}:sum")

            # Execute read_group using Odoo RPC
            results = await self.zenoo_client.execute_kw(
                model_name,
                'read_group',
                [domain],  # domain
                {
                    'fields': list(set(fields_to_aggregate + group_by)),  # fields to aggregate + group fields
                    'groupby': group_by,  # group by fields
                    'lazy': False  # get all groups at once
                }
            )

            return {
                "model": model_name,
                "groups": results,
                "group_by": group_by,
                "aggregates": aggregates,
                "filters_applied": filters,
                "date_range": date_range,
                "total_groups": len(results)
            }

        except Exception as e:
            logger.error(f"Analytics query failed: {e}")
            raise MCPToolError(f"Analytics query failed for model {args.get('model')}: {e}")

    async def _handle_execute_method(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle execute_method tool - execute any method on an Odoo model."""
        try:
            model_name = args["model"]
            method_name = args["method"]
            method_args = args.get("args", [])
            method_kwargs = args.get("kwargs", {})

            # Execute the method using execute_kw
            result = await self.zenoo_client.execute_kw(
                model_name,
                method_name,
                method_args,
                method_kwargs
            )

            return {
                "model": model_name,
                "method": method_name,
                "result": result,
                "success": True
            }

        except Exception as e:
            logger.error(f"Execute method failed: {e}")
            raise MCPToolError(f"Failed to execute {args.get('method')} on {args.get('model')}: {e}")
