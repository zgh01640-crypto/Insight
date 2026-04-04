from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
