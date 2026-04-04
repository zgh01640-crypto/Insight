import os
import httpx

BASE_URL = os.environ.get("INSIGHT_BASE_URL", "http://localhost:8010")


async def call(tool_name: str, args: dict) -> dict:
    """将 MCP tool 调用路由到对应的 Insight REST 接口"""
    async with httpx.AsyncClient(timeout=30) as c:

        if tool_name == "get_overview":
            r = await c.get(f"{BASE_URL}/api/dashboard/overview", params=_pick(args, ["year"]))

        elif tool_name == "get_division":
            div_id = args.get("div_id", 1)
            r = await c.get(f"{BASE_URL}/api/dashboard/division/{div_id}", params=_pick(args, ["year"]))

        elif tool_name == "get_quarterly":
            r = await c.get(f"{BASE_URL}/api/dashboard/quarterly", params=_pick(args, ["year", "quarter"]))

        elif tool_name == "get_monthly":
            r = await c.get(f"{BASE_URL}/api/dashboard/monthly", params=_pick(args, ["year", "month"]))

        elif tool_name == "get_opp_support":
            r = await c.get(f"{BASE_URL}/api/dashboard/opportunity-support", params=_pick(args, ["year", "quarter"]))

        elif tool_name == "get_opportunities":
            r = await c.get(f"{BASE_URL}/api/opportunities/", params=_pick(args, [
                "year", "quarter", "business_unit_id", "metric_type", "stage", "status"
            ]))

        elif tool_name == "get_collections":
            r = await c.get(f"{BASE_URL}/api/collections/", params=_pick(args, [
                "year", "business_unit_id", "status"
            ]))

        elif tool_name == "get_collection_dashboard":
            r = await c.get(f"{BASE_URL}/api/collections/dashboard", params=_pick(args, ["year"]))

        else:
            return {"error": f"未知工具: {tool_name}"}

        r.raise_for_status()
        return r.json()


def _pick(d: dict, keys: list) -> dict:
    """只保留有值的参数，避免传 None 给后端"""
    return {k: v for k, v in d.items() if k in keys and v is not None}
