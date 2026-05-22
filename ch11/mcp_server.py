import json
import logging
from contextvars import ContextVar
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

HEADER_PREFIX = "x-amzn-bedrock-agentcore-runtime-custom-"
SECURITY_KEYS = ["end-user-id", "end-user-email", "end-user-groups"]
_security_ctx: ContextVar[dict] = ContextVar("security_ctx", default={})

RBAC = {
    "engineering-admin": {"list_projects": True, "property_details": True, "budget_summary": True},
    "finance-viewer":    {"list_projects": True, "property_details": False, "budget_summary": True},
}
DEFAULT_ACCESS = {"list_projects": False, "property_details": False, "budget_summary": False}


def check_access(security_ctx: dict, permission: str) -> bool:
    groups = security_ctx.get("end-user-groups", "")
    group_list = [g.strip() for g in groups.split(",")] if groups else []
    for group in group_list:
        access = RBAC.get(group, DEFAULT_ACCESS)
        if access.get(permission, False):
            return True
    return False


class SecurityHeaderMiddleware:
    """Raw ASGI middleware that captures security headers and body _meta into a ContextVar."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict((k.decode(), v.decode()) for k, v in scope.get("headers", []))
            ctx = {}
            for key in SECURITY_KEYS:
                value = headers.get(f"{HEADER_PREFIX}{key}", "")
                if value:
                    ctx[key] = value
            if not ctx:
                first_msg = await receive()
                body_data = first_msg.get("body", b"")
                try:
                    parsed = json.loads(body_data)
                    meta = None
                    if isinstance(parsed, dict):
                        meta = parsed.get("params", {}).get("_meta", {}).get("security_context", {})
                    if meta:
                        ctx = meta
                        logger.info(f"Security context from body _meta: {json.dumps(ctx)}")
                except Exception:
                    pass
                replayed = False
                orig_receive = receive
                async def replay_receive():
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return first_msg
                    return await orig_receive()
                receive = replay_receive
            _security_ctx.set(ctx)
            if ctx:
                logger.info(f"Security context set: {json.dumps(ctx)}")
        await self.app(scope, receive, send)


mcp = FastMCP(host="0.0.0.0", stateless_http=True)


def get_security_context() -> dict:
    return _security_ctx.get()


@mcp.tool()
def get_property_details(property_id: str) -> str:
    """Get details for a real estate property by ID"""
    security_ctx = get_security_context()
    logger.info(f"get_property_details | caller={json.dumps(security_ctx)}")
    if not check_access(security_ctx, "property_details"):
        return json.dumps({"_security_context": security_ctx, "error": "Access denied: property details require engineering-admin group"}, indent=2)
    properties = {
        "PROP001": {"id": "PROP001", "address": "123 Main St, Austin TX", "type": "Commercial",
                    "status": "Under Construction", "completion_pct": 65, "contractor": "BuildCo Inc"},
        "PROP002": {"id": "PROP002", "address": "456 Oak Ave, Dallas TX", "type": "Residential",
                    "status": "Planning", "completion_pct": 0, "contractor": "TexasBuild LLC"},
    }
    result = properties.get(property_id, {"error": f"Property {property_id} not found"})
    return json.dumps({"_security_context": security_ctx, **result}, indent=2)


@mcp.tool()
def list_active_projects(status: str = "all") -> str:
    """List active real estate projects, optionally filtered by status"""
    security_ctx = get_security_context()
    logger.info(f"list_active_projects | caller={json.dumps(security_ctx)}")
    if not check_access(security_ctx, "list_projects"):
        return json.dumps({"_security_context": security_ctx, "error": "Access denied: no group with list_projects permission"}, indent=2)
    projects = [
        {"id": "PROJ001", "name": "Downtown Office Tower", "status": "Under Construction", "budget_usd": 5000000},
        {"id": "PROJ002", "name": "Riverside Condos", "status": "Planning", "budget_usd": 12000000},
        {"id": "PROJ003", "name": "Industrial Park Phase 2", "status": "Completed", "budget_usd": 3500000},
    ]
    filtered = projects if status == "all" else [p for p in projects if p["status"].lower() == status.lower()]
    return json.dumps({"_security_context": security_ctx, "projects": filtered}, indent=2)


@mcp.tool()
def get_project_budget_summary(project_id: str) -> str:
    """Get budget summary for a real estate project"""
    security_ctx = get_security_context()
    logger.info(f"get_project_budget_summary | caller={json.dumps(security_ctx)}")
    if not check_access(security_ctx, "budget_summary"):
        return json.dumps({"_security_context": security_ctx, "error": "Access denied: budget details require engineering-admin or finance-viewer group"}, indent=2)
    budgets = {
        "PROJ001": {"allocated": 5000000, "spent": 3250000, "remaining": 1750000, "variance_pct": -2.1},
        "PROJ002": {"allocated": 12000000, "spent": 450000, "remaining": 11550000, "variance_pct": 0.0},
        "PROJ003": {"allocated": 3500000, "spent": 3480000, "remaining": 20000, "variance_pct": -0.6},
    }
    result = budgets.get(project_id, {"error": f"Project {project_id} not found"})
    return json.dumps({"_security_context": security_ctx, **result}, indent=2)


if __name__ == "__main__":
    import uvicorn
    app = mcp.streamable_http_app()
    app = SecurityHeaderMiddleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
