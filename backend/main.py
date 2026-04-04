import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from database import init_db
from routers import targets, actuals, opportunities, dashboard, imports, ai, reports, collections, conversations

app = FastAPI(title="Insight 经营分析智能体", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80", "http://localhost:8010", "http://frontend"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key 认证中间件 ─────────────────────────────────
SYSTEM_API_KEY = os.environ.get("SYSTEM_API_KEY", "")
_BYPASS_PREFIXES = ("/docs", "/redoc", "/openapi", "/api/health", "/api/status")

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 未配置 API Key 时全部放行
        if not SYSTEM_API_KEY:
            return await call_next(request)
        # 豁免路径
        if request.url.path.startswith(_BYPASS_PREFIXES):
            return await call_next(request)
        # 内部来源（前端容器、localhost）免认证
        origin = request.headers.get("origin", "")
        host   = request.headers.get("host", "")
        if (origin.startswith("http://localhost") or
            origin.startswith("http://frontend") or
            host.startswith("localhost") or
            host.startswith("127.0.0.1")):
            return await call_next(request)
        # 外部请求验证 API Key
        if request.headers.get("X-API-Key", "") != SYSTEM_API_KEY:
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
        "api_key_enabled": bool(SYSTEM_API_KEY),
        "version": "2.0.0",
    }
