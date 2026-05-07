import os
import secrets
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from database import init_db
from routers import targets, actuals, opportunities, dashboard, imports, ai, reports, collections, conversations, memory, products

app = FastAPI(title="Insight 经营分析智能体", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80", "http://localhost:8010", "http://frontend"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key 认证中间件 ─────────────────────────────────
_api_key_store = {"key": os.environ.get("SYSTEM_API_KEY", "")}
_BYPASS_PREFIXES = ("/docs", "/redoc", "/openapi", "/api/health", "/api/status", "/api/settings/apikey")

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        current_key = _api_key_store["key"]
        if not current_key:
            return await call_next(request)
        if request.url.path.startswith(_BYPASS_PREFIXES):
            return await call_next(request)
        origin = request.headers.get("origin", "")
        host   = request.headers.get("host", "")
        client_ip = request.client.host if request.client else ""
        if (origin.startswith("http://localhost") or
            origin.startswith("http://frontend") or
            host.startswith("localhost") or
            host.startswith("127.0.0.1") or
            host.startswith("backend") or
            client_ip.startswith("172.") or
            client_ip.startswith("10.") or
            client_ip == "127.0.0.1"):
            return await call_next(request)
        if request.headers.get("X-API-Key", "") != current_key:
            return JSONResponse(
                {"success": False, "message": "Unauthorized: Invalid or missing X-API-Key"},
                status_code=401,
            )
        return await call_next(request)

app.add_middleware(APIKeyMiddleware)

app.include_router(targets.router,       prefix="/api/targets",      tags=["年度目标"])
app.include_router(actuals.router,       prefix="/api/actuals",      tags=["月度完成"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["商机"])
app.include_router(dashboard.router,     prefix="/api/dashboard",    tags=["看板"])
app.include_router(imports.router,       prefix="/api/import",       tags=["数据导入"])
app.include_router(collections.router,   prefix="/api/collections",  tags=["催收项目"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["对话历史"])
app.include_router(ai.router,            prefix="/api/ai",           tags=["AI助手"])
app.include_router(reports.router,       prefix="/api/reports",      tags=["分析报告"])
app.include_router(memory.router,        prefix="/api/memory",       tags=["长期记忆"])
app.include_router(products.router,      prefix="/api/products",     tags=["产品管理"])


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    return {
        "online": True,
        "api_key_enabled": bool(_api_key_store["key"]),
        "version": "2.0.0",
    }


@app.get("/api/settings/apikey")
def get_apikey():
    """获取当前 API Key 状态（不返回明文 Key）"""
    key = _api_key_store["key"]
    return {
        "enabled": bool(key),
        "preview": (key[:6] + "…" + key[-4:]) if len(key) >= 10 else ("已设置" if key else ""),
    }


@app.post("/api/settings/apikey/generate")
def generate_apikey():
    """生成新的随机 API Key 并立即生效"""
    new_key = secrets.token_urlsafe(32)
    _api_key_store["key"] = new_key
    return {"key": new_key, "message": "新 API Key 已生成并生效，请妥善保存"}


@app.delete("/api/settings/apikey")
def clear_apikey():
    """清除 API Key，关闭认证"""
    _api_key_store["key"] = ""
    return {"message": "API Key 已清除，认证已关闭"}
