import os
import json
from datetime import date
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from openai import OpenAI
from sqlmodel import Session
from database import get_session
from routers.dashboard import (
    overview, division_detail, quarterly_dashboard,
    monthly_dashboard, opportunity_support,
)

router = APIRouter()

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
        "base_url": "https://api.ofox.ai/anthropic",
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
