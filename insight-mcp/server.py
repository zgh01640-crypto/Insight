"""
Insight MCP Server
将 Insight 经营分析系统的数据查询能力通过 MCP 协议对外暴露。
运行方式：python server.py（由 Claude Code 通过 stdio 启动）
"""
import asyncio
import json
import sys
import os

# 确保能 import 同目录的 client.py
sys.path.insert(0, os.path.dirname(__file__))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
import client as insight_client

app = Server("insight")

# ── 工具定义 ──────────────────────────────────────────
TOOLS = [
    types.Tool(
        name="get_overview",
        description="获取产品中心所有事业部的年度仪表盘数据，包含YTD实际完成、YTD目标、达成率、年度目标、同比增长率。当询问整体达成情况、哪个事业部完成率高/低时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "查询年份，默认当前年"},
            },
        },
    ),
    types.Tool(
        name="get_division",
        description="获取单个事业部的详细数据，包含每月实际/目标、YTD达成率、年度缺口。当询问某个具体事业部时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "div_id": {"type": "integer", "description": "事业部ID：1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务"},
                "year":   {"type": "integer", "description": "查询年份"},
            },
            "required": ["div_id"],
        },
    ),
    types.Tool(
        name="get_quarterly",
        description="获取某季度的仪表盘数据，包含产品中心合计和各事业部的季度目标、实际、达成率。",
        inputSchema={
            "type": "object",
            "properties": {
                "year":    {"type": "integer", "description": "查询年份"},
                "quarter": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
            },
        },
    ),
    types.Tool(
        name="get_monthly",
        description="获取某个月的仪表盘数据，包含产品中心合计和各事业部的月度目标、实际、达成率。",
        inputSchema={
            "type": "object",
            "properties": {
                "year":  {"type": "integer", "description": "查询年份"},
                "month": {"type": "integer", "description": "月份 1-12"},
            },
        },
    ),
    types.Tool(
        name="get_opp_support",
        description="获取商机支撑分析数据，包含各事业部进行中商机金额、季度目标完成率、商机阶段漏斗。当询问商机覆盖率、销售管道时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "year":    {"type": "integer", "description": "查询年份"},
                "quarter": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
            },
        },
    ),
    types.Tool(
        name="get_opportunities",
        description="查询商机明细列表，支持按事业部、年份、季度、指标类型、阶段、状态过滤。当询问具体商机项目时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "year":             {"type": "integer"},
                "quarter":          {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
                "business_unit_id": {"type": "integer", "description": "1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务"},
                "metric_type":      {"type": "string", "enum": ["contract", "revenue", "payment"]},
                "stage":            {"type": "string", "enum": ["线索", "立项", "报价", "签约跟进", "已完成"]},
                "status":           {"type": "string", "enum": ["进行中", "已赢单", "已输单", "已搁置"]},
            },
        },
    ),
    types.Tool(
        name="get_collections",
        description="查询年度重点催收项目明细列表。当询问某事业部具体催收项目、特定状态的催收明细时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "year":             {"type": "integer"},
                "business_unit_id": {"type": "integer", "description": "1=智能建造, 2=大数据, 3=数字交易, 4=智慧政务"},
                "status":           {"type": "string", "enum": ["催收中", "已回款", "已核销"]},
            },
        },
    ),
    types.Tool(
        name="get_collection_dashboard",
        description="获取催收仪表盘数据：全局汇总（总欠款/回款率）、各事业部聚合、Top10重点项目、各部门完整明细。当询问催收整体情况、回款率、催收分析时优先使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "查询年份，默认当前年"},
            },
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await insight_client.call(name, arguments)
        return [types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, default=str),
        )]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
