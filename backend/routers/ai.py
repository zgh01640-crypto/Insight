import os
import json
import uuid
import tempfile
import pandas as pd
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from openai import OpenAI
from sqlmodel import Session, select
from database import get_session
from models import ImportBatch, MonthlyActual, Opportunity
from schemas import ApiResponse
from routers.dashboard import (
    overview, division_detail, quarterly_dashboard,
    monthly_dashboard, opportunity_support,
)
from routers.opportunities import list_opportunities
from services.importer import import_monthly_actuals, import_opportunities

router = APIRouter()

# ── 文件解析缓存 ──────────────────────────────────────
_pending_imports: dict = {}  # {pending_id: {type, df, filename}}

# ── 多模型配置 ────────────────────────────────────────
MODELS = {
    "deepseek": {
        "label": "DeepSeek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "LLM_API_KEY",
    },
    "kimi": {
        "label": "Kimi",
        "model": "kimi-k2.5",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "KIMI_API_KEY",
    },
    "glm": {
        "label": "GLM",
        "model": "glm-5",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "GLM_API_KEY",
    },
    "claude": {
        "label": "Claude Sonnet",
        "model": "anthropic/claude-sonnet-4.6",
        "base_url": "https://api.ofox.ai/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
}
DEFAULT_MODEL = os.environ.get("LLM_MODEL_ID", "deepseek")

def _llm_client(model_id: str) -> OpenAI:
    cfg = MODELS.get(model_id, MODELS[DEFAULT_MODEL])
    return OpenAI(
        api_key=os.environ.get(cfg["api_key_env"], ""),
        base_url=cfg["base_url"],
    )

# ── 模型列表端点 ──────────────────────────────────────
@router.get("/models")
def list_models():
    return [{"id": k, "label": v["label"]} for k, v in MODELS.items()]

# ── Tool 定义 ─────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_overview",
            "description": "获取产品中心所有事业部的年度仪表盘数据，包含YTD实际完成、YTD目标、达成率、年度目标、同比增长率。当用户询问整体达成情况、哪个事业部完成率高/低时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "查询年份，默认当前年"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_division",
            "description": "获取单个事业部的详细数据，包含每月实际/目标、YTD达成率、年度缺口、每月需完成额、商机覆盖率。当用户询问某个具体事业部时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "div_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务"},
                    "year": {"type": "integer", "description": "查询年份，默认当前年"},
                },
                "required": ["div_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quarterly",
            "description": "获取某个季度的仪表盘数据，包含产品中心合计和各事业部的季度目标、季度实际、达成率。当用户询问季度完成情况时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "查询年份"},
                    "quarter": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"], "description": "季度"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly",
            "description": "获取某个月的仪表盘数据，包含产品中心合计和各事业部的月度目标、月度实际、达成率。当用户询问某个月完成情况时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "查询年份"},
                    "month": {"type": "integer", "description": "月份 1-12"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_opp_support",
            "description": "获取商机分析数据，包含各事业部进行中商机金额、季度目标完成率、商机阶段漏斗分布。当用户询问商机、销售管道、商机覆盖率时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "查询年份"},
                    "quarter": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"], "description": "季度"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_opportunities",
            "description": "查询商机明细列表，支持按事业部、年份、季度、指标类型、商机阶段、状态过滤，结果按金额降序。当用户询问具体商机项目、某事业部有哪些商机、哪些项目在推进、商机明细时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year":             {"type": "integer", "description": "年份"},
                    "quarter":          {"type": "string", "enum": ["Q1","Q2","Q3","Q4"], "description": "季度"},
                    "business_unit_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务"},
                    "metric_type":      {"type": "string", "enum": ["contract","revenue","payment"], "description": "指标类型：contract合同/revenue收入/payment回款"},
                    "stage":            {"type": "string", "enum": ["线索","立项","报价","签约跟进","已完成"], "description": "商机阶段"},
                    "status":           {"type": "string", "enum": ["进行中","已赢单","已输单","已搁置"], "description": "商机状态"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "import_actuals",
            "description": "将用户上传的月度完成数据文件写入数据库。只在用户确认后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pending_id": {
                        "type": "string",
                        "description": "文件解析后返回的 pending_id"
                    }
                },
                "required": ["pending_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "import_opportunities",
            "description": "将用户上传的商机数据文件写入数据库。只在用户确认后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pending_id": {
                        "type": "string",
                        "description": "文件解析后返回的 pending_id"
                    }
                },
                "required": ["pending_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_import",
            "description": "撤销一次导入操作，删除该批次写入的数据。月度完成数据中被覆盖的旧值无法恢复。",
            "parameters": {
                "type": "object",
                "properties": {
                    "batch_id": {
                        "type": "integer",
                        "description": "导入批次ID，由 import_actuals 或 import_opportunities 工具返回"
                    }
                },
                "required": ["batch_id"]
            }
        }
    },
]

# ── Tool 执行 ─────────────────────────────────────────
def _execute_tool(name: str, args: dict, session: Session) -> str:
    try:
        if name == "get_overview":
            result = overview(year=args.get("year"), session=session)
        elif name == "get_division":
            result = division_detail(div_id=args["div_id"], year=args.get("year"), session=session)
        elif name == "get_quarterly":
            result = quarterly_dashboard(year=args.get("year"), quarter=args.get("quarter"), session=session)
        elif name == "get_monthly":
            result = monthly_dashboard(year=args.get("year"), month=args.get("month"), session=session)
        elif name == "get_opp_support":
            result = opportunity_support(year=args.get("year"), quarter=args.get("quarter"), session=session)
        elif name == "get_opportunities":
            result = list_opportunities(
                year=args.get("year"), quarter=args.get("quarter"),
                business_unit_id=args.get("business_unit_id"),
                metric_type=args.get("metric_type"),
                stage=args.get("stage"), status=args.get("status"),
                session=session,
            )
        elif name == "import_actuals":
            pending = _pending_imports.pop(args["pending_id"], None)
            if not pending:
                return json.dumps({"error": "找不到对应的待导入数据，可能已过期"}, ensure_ascii=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                pending["df"].to_excel(tmp.name, index=False)
                path = tmp.name
            try:
                batch = import_monthly_actuals(path, pending["filename"], session)
            finally:
                os.unlink(path)
            failures = json.loads(batch.fail_detail) if batch.fail_detail else []
            return json.dumps({
                "batch_id": batch.id,
                "total": batch.total_rows,
                "success": batch.success_rows,
                "fail": batch.fail_rows,
                "failures": failures[:10],
                "overwrite": getattr(batch, '_overwrite_count', 0),
            }, ensure_ascii=False)
        elif name == "import_opportunities":
            pending = _pending_imports.pop(args["pending_id"], None)
            if not pending:
                return json.dumps({"error": "找不到对应的待导入数据，可能已过期"}, ensure_ascii=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                pending["df"].to_excel(tmp.name, index=False)
                path = tmp.name
            try:
                batch = import_opportunities(path, pending["filename"], session)
            finally:
                os.unlink(path)
            failures = json.loads(batch.fail_detail) if batch.fail_detail else []
            return json.dumps({
                "batch_id": batch.id,
                "total": batch.total_rows,
                "success": batch.success_rows,
                "fail": batch.fail_rows,
                "failures": failures[:10],
            }, ensure_ascii=False)
        elif name == "rollback_import":
            batch_id = args["batch_id"]
            batch = session.get(ImportBatch, batch_id)
            if not batch:
                return json.dumps({"error": f"找不到批次 {batch_id}"}, ensure_ascii=False)
            if batch.import_type == "monthly_actual":
                rows = session.exec(
                    select(MonthlyActual).where(MonthlyActual.import_batch_id == batch_id)
                ).all()
                deleted = len(rows)
                for r in rows:
                    session.delete(r)
                session.commit()
                return json.dumps({
                    "deleted": deleted,
                    "warning": "仅删除本批次新增的记录，被覆盖的旧数据无法恢复"
                }, ensure_ascii=False)
            elif batch.import_type == "opportunity":
                rows = session.exec(
                    select(Opportunity).where(Opportunity.import_batch_id == batch_id)
                ).all()
                deleted = len(rows)
                for r in rows:
                    session.delete(r)
                session.commit()
                return json.dumps({"deleted": deleted}, ensure_ascii=False)
            else:
                return json.dumps({"error": f"不支持撤销此类型：{batch.import_type}"}, ensure_ascii=False)
        else:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        return json.dumps(result.data, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# ── 请求/响应模型 ─────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    year: int = None
    model_id: str = DEFAULT_MODEL

# ── SSE 流式聊天端点 ───────────────────────────────────
@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(get_session)):
    cur_year = req.year or date.today().year
    cur_month = date.today().month

    system_prompt = f"""你是产品中心经营分析智能体，帮助产品中心负责人快速了解业务运营情况。

当前时间：{cur_year}年{cur_month}月
产品中心下辖4个事业部（ID对应关系）：
- 1: 智能建造事业部
- 2: 大数据事业部
- 3: 数字交易事业部
- 4: 智慧政务事业部

核心指标：合同（contract）、收入（revenue）、回款（payment），金额单位均为万元。

行为准则：
1. 只使用工具获取真实数据，不编造或估算任何数字
2. 回答简洁有力，重点突出，用中文回答
3. 金额保留两位小数，比率保留一位小数后加%
4. 多指标对比时优先用表格或列表展示
5. 发现异常（达成率低于60%、同比下滑超20%）时主动提示"""

    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages[-10:]]

    client = _llm_client(req.model_id)
    model_name = MODELS.get(req.model_id, MODELS[DEFAULT_MODEL])["model"]

    def generate():
        nonlocal messages
        # agentic loop：循环直到无 tool_use
        while True:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                stream=False,
            )
            msg = response.choices[0].message

            # 有工具调用，执行后继续循环
            if msg.tool_calls:
                messages.append(msg.model_dump(exclude_unset=False))
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = _execute_tool(tc.function.name, args, session)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            # 无工具调用，流式输出最终回答
            final_content = msg.content or ""
            # 分块推送（模拟流式，DeepSeek 工具调用后需二次请求才能流式）
            chunk_size = 8
            for i in range(0, len(final_content), chunk_size):
                chunk = final_content[i:i + chunk_size]
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            break

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── 文件解析端点 ───────────────────────────────────────
@router.post("/parse-file")
async def ai_parse_file(file: UploadFile = File(...)):
    """解析上传的 Excel/CSV 文件，自动识别类型（月度实绩/商机），返回摘要不写库"""
    suffix = os.path.splitext(file.filename)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        df = pd.read_excel(path) if suffix != ".csv" else pd.read_csv(path)
    finally:
        os.unlink(path)

    cols = set(df.columns.tolist())
    actuals_cols = {"年份", "月份", "事业部", "指标类型", "完成值"}
    opp_cols     = {"商机名称", "所属事业部", "指标类型", "所属年度", "所属季度"}

    if actuals_cols.issubset(cols):
        import_type = "monthly_actuals"
        type_label  = "月度完成数据"
    elif opp_cols.issubset(cols):
        import_type = "opportunities"
        type_label  = "商机数据"
    else:
        return {
            "success": False,
            "message": f"无法识别文件格式，列名：{sorted(cols)}",
            "data": None,
        }

    pending_id = str(uuid.uuid4())[:8]
    _pending_imports[pending_id] = {"type": import_type, "df": df, "filename": file.filename}

    # 转换示例行，确保所有值都是 JSON 可序列化的
    sample_df = df.head(3)
    sample = []
    for _, row in sample_df.iterrows():
        sample.append({k: (v if pd.notna(v) else None) for k, v in row.items()})

    return {
        "success": True,
        "message": "",
        "data": {
            "pending_id":  pending_id,
            "import_type": type_label,
            "filename":    file.filename,
            "row_count":   len(df),
            "columns":     df.columns.tolist(),
            "sample_rows": sample,
        }
    }
