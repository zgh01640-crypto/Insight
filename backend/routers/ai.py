import os
import json
import uuid
import base64
import tempfile
import pandas as pd
from datetime import date, datetime
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from sqlmodel import Session, select
from database import get_session
from models import ImportBatch, MonthlyActual, Opportunity, CollectionItem, ConversationSession, ConversationMessage, MemoryItem
from schemas import ApiResponse
from routers.dashboard import (
    overview, division_detail, quarterly_dashboard,
    monthly_dashboard, opportunity_support,
    detect_anomalies, analyze_root_cause, trend,
)
from routers.opportunities import list_opportunities, create_opportunity as _create_opp, update_opportunity as _update_opp
from routers.collections import list_collections, collection_dashboard
from routers.targets import get_targets as _get_targets
from services.importer import import_monthly_actuals, import_opportunities, import_collection_items
from schemas import OpportunityCreate, OpportunityUpdate

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
                    "div_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务, 5=创新业务"},
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
                    "business_unit_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务, 5=创新业务"},
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
    {
        "type": "function",
        "function": {
            "name": "get_collections",
            "description": "查询年度重点催收项目明细列表，包含各事业部的欠款项目、金额、状态。当用户询问某个具体事业部的催收项目、特定状态的催收项目、催收明细时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year":             {"type": "integer", "description": "年份"},
                    "business_unit_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务, 5=创新业务"},
                    "status":           {"type": "string", "enum": ["催收中", "已回款", "已核销"], "description": "状态筛选"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_collection_dashboard",
            "description": "获取催收项目仪表盘数据，包含：全局汇总（总欠款、催收中、已回款、回款率）、各事业部聚合（金额/数量/回款率）、金额Top10重点项目、各事业部完整明细。当用户询问催收整体情况、回款率、各事业部催收汇总、催收分析时优先使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "年份，默认当前年"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "import_collections",
            "description": "将用户上传的催收项目数据文件写入数据库。只在用户确认后调用。",
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
            "name": "detect_anomalies",
            "description": "自动扫描所有事业部所有指标，检测达成率偏低、月度环比骤降、同比大幅下滑、年度节奏落后等异常，返回异常列表和严重程度。当用户询问'有没有异常'、'哪里有问题'、'帮我做个体检'时优先使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year":  {"type": "integer", "description": "检测年份，默认当前年"},
                    "month": {"type": "integer", "description": "检测截止月份（1-12），默认当前月"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_root_cause",
            "description": "针对某事业部某指标的异常，钻取根因数据：逐月完成情况、季度对比、与去年同期对比、商机管道覆盖率。通常在 detect_anomalies 发现异常后，用户要求深入分析时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_unit_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务, 5=创新业务"},
                    "metric_type":      {"type": "string", "enum": ["contract", "revenue", "payment"]},
                    "year":             {"type": "integer", "description": "年份，默认当前年"},
                    "month":            {"type": "integer", "description": "截止月份，默认当前月"},
                },
                "required": ["business_unit_id", "metric_type"],
            },
        },
    },
    # ── 新增工具 ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_targets",
            "description": "查询某年各事业部年度目标及12个月分解。当用户询问'目标是多少'、'今年计划'、'年度指标'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "查询年份，默认当前年"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend",
            "description": "获取某指标的同比趋势分析：当年与去年逐月对比、YTD对比、同比增长率。当用户询问'同比'、'趋势'、'去年相比'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_type": {"type": "string", "enum": ["contract", "revenue", "payment"], "description": "指标类型：contract合同/revenue收入/payment回款，默认contract"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_opportunity",
            "description": "新增一条商机记录。当用户说'帮我新增商机'、'录入一条商机'时使用。缺少必填字段时先向用户确认再调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":               {"type": "string", "description": "商机名称"},
                    "business_unit_id":   {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务, 5=创新业务"},
                    "metric_type":        {"type": "string", "enum": ["contract", "revenue", "payment"], "description": "指标类型"},
                    "year":               {"type": "integer", "description": "所属年度，默认当前年"},
                    "quarter":            {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"], "description": "所属季度"},
                    "estimated_amount":   {"type": "number", "description": "预计金额（万元）"},
                    "stage":              {"type": "string", "enum": ["线索", "立项", "报价", "签约跟进", "已完成"], "description": "商机阶段，默认线索"},
                    "status":             {"type": "string", "enum": ["进行中", "已赢单", "已输单", "已搁置"], "description": "商机状态，默认进行中"},
                    "estimated_date":     {"type": "string", "description": "预计达成时间，格式 YYYY-MM-DD"},
                    "notes":              {"type": "string", "description": "备注"},
                },
                "required": ["name", "business_unit_id", "metric_type", "quarter", "estimated_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_opportunity",
            "description": "更新商机信息（状态、金额、阶段等）。当用户说'把某商机改成已赢单'、'更新商机金额'时使用。需先用 get_opportunities 查到商机 ID 再调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "opp_id":           {"type": "integer", "description": "商机ID，必填"},
                    "name":             {"type": "string"},
                    "business_unit_id": {"type": "integer"},
                    "metric_type":      {"type": "string", "enum": ["contract", "revenue", "payment"]},
                    "year":             {"type": "integer"},
                    "quarter":          {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
                    "estimated_amount": {"type": "number"},
                    "stage":            {"type": "string", "enum": ["线索", "立项", "报价", "签约跟进", "已完成"]},
                    "status":           {"type": "string", "enum": ["进行中", "已赢单", "已输单", "已搁置"]},
                    "estimated_date":   {"type": "string"},
                    "notes":            {"type": "string"},
                },
                "required": ["opp_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "将重要信息保存为长期记忆条目，下次对话自动注入上下文。当用户说'记住'、'记下来'、'保存这个信息'时调用。将信息提炼成简洁条目再保存。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["偏好", "项目", "人物", "数据", "其他"],
                        "description": "记忆分类：偏好=用户习惯/喜好，项目=具体项目信息，人物=人员信息，数据=重要数字，其他=不属于以上分类"
                    },
                    "content": {
                        "type": "string",
                        "description": "提炼后的简洁记忆内容，50字以内，去除冗余"
                    }
                },
                "required": ["category", "content"]
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
            elif batch.import_type == "collection":
                rows = session.exec(
                    select(CollectionItem).where(CollectionItem.import_batch_id == batch_id)
                ).all()
                deleted = len(rows)
                for r in rows:
                    session.delete(r)
                session.commit()
                return json.dumps({"deleted": deleted}, ensure_ascii=False)
            else:
                return json.dumps({"error": f"不支持撤销此类型：{batch.import_type}"}, ensure_ascii=False)
        elif name == "get_collections":
            result = list_collections(
                year=args.get("year"),
                business_unit_id=args.get("business_unit_id"),
                status=args.get("status"),
                session=session,
            )
        elif name == "get_collection_dashboard":
            result = collection_dashboard(
                year=args.get("year"),
                session=session,
            )
        elif name == "detect_anomalies":
            year  = args.get("year")  or date.today().year
            month = args.get("month") or date.today().month
            data  = detect_anomalies(session=session, year=year, month=month)
            return json.dumps(data, ensure_ascii=False, default=str)
        elif name == "analyze_root_cause":
            year  = args.get("year")  or date.today().year
            month = args.get("month") or date.today().month
            data  = analyze_root_cause(
                session=session,
                business_unit_id=args["business_unit_id"],
                metric_type=args["metric_type"],
                year=year,
                month=month,
            )
            return json.dumps(data, ensure_ascii=False, default=str)
        elif name == "import_collections":
            pending = _pending_imports.pop(args["pending_id"], None)
            if not pending:
                return json.dumps({"error": "找不到对应的待导入数据，可能已过期"}, ensure_ascii=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                pending["df"].to_excel(tmp.name, index=False)
                path = tmp.name
            try:
                batch = import_collection_items(path, pending["filename"], session)
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
        elif name == "get_targets":
            year = args.get("year") or date.today().year
            result = _get_targets(year=year, session=session)
            return json.dumps(result.data, ensure_ascii=False, default=str)
        elif name == "get_trend":
            metric = args.get("metric_type", "contract")
            result = trend(metric=metric, session=session)
            return json.dumps(result.data, ensure_ascii=False, default=str)
        elif name == "create_opportunity":
            from schemas import OpportunityCreate
            body = OpportunityCreate(
                name=args["name"],
                business_unit_id=args["business_unit_id"],
                metric_type=args["metric_type"],
                year=args.get("year") or date.today().year,
                quarter=args["quarter"],
                estimated_amount=args["estimated_amount"],
                stage=args.get("stage", "线索"),
                status=args.get("status", "进行中"),
                estimated_date=args.get("estimated_date"),
                notes=args.get("notes"),
            )
            result = _create_opp(body=body, session=session)
            return json.dumps(result.data, ensure_ascii=False, default=str)
        elif name == "update_opportunity":
            from schemas import OpportunityUpdate
            opp_id = args.pop("opp_id")
            # 先取已有数据填充缺省字段
            from models import Opportunity as OppModel
            opp = session.get(OppModel, opp_id)
            if not opp:
                return json.dumps({"error": f"商机ID {opp_id} 不存在"}, ensure_ascii=False)
            merged = {
                "name": opp.name, "business_unit_id": opp.business_unit_id,
                "metric_type": opp.metric_type, "year": opp.year,
                "quarter": opp.quarter, "estimated_amount": opp.estimated_amount,
                "stage": opp.stage, "status": opp.status,
                "estimated_date": str(opp.estimated_date) if opp.estimated_date else None,
                "notes": opp.notes,
            }
            merged.update({k: v for k, v in args.items() if v is not None})
            body = OpportunityUpdate(**merged)
            result = _update_opp(opp_id=opp_id, body=body, session=session)
            return json.dumps(result.data, ensure_ascii=False, default=str)
        elif name == "save_memory":
            item = MemoryItem(
                category=args["category"],
                content=args["content"],
                source="user_command",
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return json.dumps({"saved": True, "id": item.id, "content": item.content, "category": item.category}, ensure_ascii=False)
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
    session_id: Optional[str] = None
    pending_ids: List[str] = []   # 待注入的文件 pending_id 列表

# ── SSE 流式聊天端点 ───────────────────────────────────
@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(get_session)):
    cur_year = req.year or date.today().year
    cur_month = date.today().month

    system_prompt = f"""你是产品中心经营分析智能体「小助」，帮助产品中心负责人快速了解业务运营情况并执行操作。

当前时间：{cur_year}年{cur_month}月
产品中心下辖5个事业部（ID对应关系）：
- 1: 智能建造事业部
- 2: 大数据事业部
- 3: 数字交易事业部
- 4: 智慧政务事业部
- 5: 创新业务事业部

核心指标：合同（contract）、收入（revenue）、回款（payment），金额单位均为万元。
催收项目状态：催收中 / 已回款 / 已核销。
商机阶段：线索 → 立项 → 报价 → 签约跟进 → 已完成。
商机状态：进行中 / 已赢单 / 已输单 / 已搁置。

行为准则：
1. 只使用工具获取真实数据，不编造或估算任何数字
2. 回答简洁有力，重点突出，用中文回答
3. 金额保留两位小数，比率保留一位小数后加%
4. 多指标对比时优先用表格或列表展示
5. 发现异常（达成率低于60%、同比下滑超20%）时主动提示
6. 用户上传文件后，展示数据摘要并主动询问是否导入，导入后汇报结果
7. 用户要新增商机时，补全缺失字段后调用 create_opportunity 工具，操作成功后告知用户
8. 用户要修改商机时，先用 get_opportunities 查询确认 ID，再调用 update_opportunity
9. 用户说「记住」时调用 save_memory 工具，将信息提炼成简洁条目保存，并告知用户已记录"""

    # 注入长期记忆
    memories = session.exec(
        select(MemoryItem).order_by(MemoryItem.created_at.desc()).limit(20)
    ).all()
    if memories:
        mem_lines = "\n".join([f"- [{m.category}] {m.content}" for m in memories])
        system_prompt += f"\n\n## 你的长期记忆（用户历史保存，每次对话自动注入）\n{mem_lines}"

    messages = [{"role": "system", "content": system_prompt}]

    # 构造对话历史，处理 pending_ids 中的文件内容
    history = [{"role": m.role, "content": m.content} for m in req.messages[-10:]]

    # 把 pending_ids 注入最后一条 user 消息
    if req.pending_ids and history:
        last_user_idx = None
        for i in range(len(history) - 1, -1, -1):
            if history[i]["role"] == "user":
                last_user_idx = i
                break
        if last_user_idx is not None:
            injections = []
            vision_parts = []
            for pid in req.pending_ids:
                pending = _pending_imports.get(pid)
                if not pending:
                    continue
                if pending["type"] == "image":
                    # 视觉内容：构造 image_url part（Claude/GPT-4V 格式）
                    vision_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{pending['mime']};base64,{pending['b64']}"}
                    })
                elif pending["type"] == "document":
                    text = pending["text"][:3000]  # 限制长度
                    injections.append(f"[附件：{pending['filename']}]\n{text}")
            if vision_parts or injections:
                orig_content = history[last_user_idx]["content"]
                if vision_parts:
                    # 视觉模型：content 改为 list 格式
                    parts = [{"type": "text", "text": orig_content}]
                    if injections:
                        parts[0]["text"] = "\n\n".join(injections) + "\n\n" + orig_content
                    parts.extend(vision_parts)
                    history[last_user_idx]["content"] = parts
                else:
                    history[last_user_idx]["content"] = "\n\n".join(injections) + "\n\n" + orig_content

    messages += history

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
                    # 推送工具调用事件给前端
                    yield f"data: {json.dumps({'tool_call': tc.function.name, 'args': args}, ensure_ascii=False)}\n\n"
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

            # 保存消息到会话（如果有 session_id）
            if req.session_id:
                try:
                    conv = session.get(ConversationSession, req.session_id)
                    if conv:
                        # 保存最后一条用户消息（如果尚未保存）
                        last_user = req.messages[-1] if req.messages else None
                        if last_user and last_user.role == "user":
                            session.add(ConversationMessage(
                                session_id=req.session_id,
                                role="user",
                                content=last_user.content,
                            ))
                        # 保存 assistant 回复
                        session.add(ConversationMessage(
                            session_id=req.session_id,
                            role="assistant",
                            content=final_content,
                        ))
                        conv.updated_at = datetime.utcnow()
                        session.commit()
                except Exception:
                    pass  # 保存失败不影响响应

            yield "data: [DONE]\n\n"
            break

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── 文件解析端点 ───────────────────────────────────────
@router.post("/parse-file")
async def ai_parse_file(file: UploadFile = File(...)):
    """Parse uploaded file (Excel/CSV/image/PDF/Word), return preview without writing to DB"""
    suffix = os.path.splitext(file.filename)[1].lower() or ".xlsx"
    raw = await file.read()

    # ── 图片类型 ───────────────────────────────────────
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    if suffix in IMAGE_EXTS:
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".webp": "image/webp", ".gif": "image/gif"}
        b64 = base64.b64encode(raw).decode("utf-8")
        pending_id = str(uuid.uuid4())[:8]
        _pending_imports[pending_id] = {
            "type": "image",
            "mime": mime_map.get(suffix, "image/png"),
            "b64": b64,
            "filename": file.filename,
        }
        size_kb = len(raw) // 1024
        return JSONResponse(content={
            "success": True, "message": "",
            "data": {
                "pending_id": pending_id,
                "file_type": "image",
                "filename": file.filename,
                "preview": f"图片已就绪（{size_kb} KB），请用支持视觉的模型（如 Claude）询问图片内容",
                "can_memorize": True,
            }
        })

    # ── PDF 类型 ───────────────────────────────────────
    if suffix == ".pdf":
        try:
            import pdfplumber
            import io
            text_parts = []
            page_count = 0
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages[:50]:   # 最多读50页
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            full_text = "\n".join(text_parts)
        except Exception as e:
            return JSONResponse(content={"success": False, "message": f"PDF 解析失败：{e}", "data": None})
        pending_id = str(uuid.uuid4())[:8]
        _pending_imports[pending_id] = {
            "type": "document",
            "text": full_text,
            "filename": file.filename,
            "page_count": page_count,
        }
        preview_text = full_text[:150].replace("\n", " ")
        return JSONResponse(content={
            "success": True, "message": "",
            "data": {
                "pending_id": pending_id,
                "file_type": "document",
                "filename": file.filename,
                "preview": f"PDF 共 {page_count} 页，提取文字 {len(full_text)} 字。前150字：{preview_text}…",
                "can_memorize": True,
            }
        })

    # ── Word 类型 ──────────────────────────────────────
    if suffix in (".docx", ".doc"):
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(raw))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n".join(paragraphs)
        except Exception as e:
            return JSONResponse(content={"success": False, "message": f"Word 解析失败：{e}", "data": None})
        pending_id = str(uuid.uuid4())[:8]
        _pending_imports[pending_id] = {
            "type": "document",
            "text": full_text,
            "filename": file.filename,
            "page_count": None,
        }
        preview_text = full_text[:150].replace("\n", " ")
        return JSONResponse(content={
            "success": True, "message": "",
            "data": {
                "pending_id": pending_id,
                "file_type": "document",
                "filename": file.filename,
                "preview": f"Word 文档，提取文字 {len(full_text)} 字。前150字：{preview_text}…",
                "can_memorize": True,
            }
        })

    # ── 表格类型（原有逻辑）────────────────────────────
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        path = tmp.name
    try:
        df = pd.read_excel(path) if suffix != ".csv" else pd.read_csv(path)
    except Exception as e:
        os.unlink(path)
        return JSONResponse(content={"success": False, "message": f"表格解析失败：{e}", "data": None})
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

    cols = set(df.columns.tolist())
    actuals_cols     = {"年份", "月份", "事业部", "指标类型", "完成值"}
    opp_cols         = {"商机名称", "所属事业部", "指标类型", "所属年度", "所属季度"}
    collection_cols  = {"项目名称", "单位名称", "欠款金额（万元）"}

    if actuals_cols.issubset(cols):
        import_type = "monthly_actuals"
        type_label  = "月度完成数据"
    elif opp_cols.issubset(cols):
        import_type = "opportunities"
        type_label  = "商机数据"
    elif collection_cols.issubset(cols):
        import_type = "collections"
        type_label  = "催收项目数据"
    else:
        return JSONResponse(content={
            "success": False,
            "message": f"无法识别文件格式，列名：{sorted(cols)}",
            "data": None,
        })

    pending_id = str(uuid.uuid4())[:8]
    _pending_imports[pending_id] = {"type": import_type, "df": df, "filename": file.filename}

    sample_df = df.head(3)
    sample = []
    for _, row in sample_df.iterrows():
        row_dict = {}
        for k, v in row.items():
            if pd.isna(v):
                row_dict[k] = None
            elif isinstance(v, (int, float, str, bool)):
                row_dict[k] = v
            else:
                row_dict[k] = str(v)
        sample.append(row_dict)

    return JSONResponse(content={
        "success": True,
        "message": "",
        "data": {
            "pending_id":  pending_id,
            "file_type":   "spreadsheet",
            "import_type": type_label,
            "filename":    file.filename,
            "preview":     f"{type_label}，共 {int(len(df))} 行",
            "row_count":   int(len(df)),
            "columns":     [str(c) for c in df.columns],
            "sample_rows": sample,
            "can_memorize": False,
        }
    })
