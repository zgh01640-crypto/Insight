from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from database import get_session
from models import (
    AnnualTarget, MonthlyTarget, MonthlyActual,
    Opportunity, BusinessUnit,
)
from schemas import ApiResponse

router = APIRouter()

METRICS = ["contract", "revenue", "payment"]


def _cur_month() -> int:
    return date.today().month


def _ytd_actual(session: Session, year: int, cur_month: int) -> dict:
    """Returns {(unit_id, metric): amount} for YTD actuals."""
    rows = session.exec(
        select(
            MonthlyActual.business_unit_id,
            MonthlyActual.metric_type,
            func.sum(MonthlyActual.actual_amount).label("total"),
        )
        .where(MonthlyActual.year == year, MonthlyActual.month <= cur_month)
        .group_by(MonthlyActual.business_unit_id, MonthlyActual.metric_type)
    ).all()
    return {(r.business_unit_id, r.metric_type): r.total or 0.0 for r in rows}


def _ytd_target(session: Session, year: int, cur_month: int) -> dict:
    """Returns {(unit_id, metric): amount} — sum of monthly targets up to cur_month."""
    rows = session.exec(
        select(
            AnnualTarget.business_unit_id,
            AnnualTarget.metric_type,
            func.sum(MonthlyTarget.target_amount).label("total"),
        )
        .join(MonthlyTarget, MonthlyTarget.annual_target_id == AnnualTarget.id)
        .where(AnnualTarget.year == year, MonthlyTarget.month <= cur_month)
        .group_by(AnnualTarget.business_unit_id, AnnualTarget.metric_type)
    ).all()
    result = {(r.business_unit_id, r.metric_type): r.total or 0.0 for r in rows}

    # Fallback: if no monthly breakdown, use prorated annual target
    at_rows = session.exec(
        select(AnnualTarget).where(AnnualTarget.year == year)
    ).all()
    for at in at_rows:
        key = (at.business_unit_id, at.metric_type)
        if key not in result:
            result[key] = round(at.target_amount / 12 * cur_month, 2)
    return result


def _annual_targets(session: Session, year: int) -> dict:
    rows = session.exec(select(AnnualTarget).where(AnnualTarget.year == year)).all()
    return {(r.business_unit_id, r.metric_type): r.target_amount for r in rows}


# ── Overview ─────────────────────────────────────────
@router.get("/overview", response_model=ApiResponse)
def overview(
    year: int = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    cur_month = _cur_month()
    prev_year = year - 1

    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    ytd_a  = _ytd_actual(session, year, cur_month)
    ytd_t  = _ytd_target(session, year, cur_month)
    ann_t  = _annual_targets(session, year)
    prev_a = _ytd_actual(session, prev_year, cur_month)

    summaries = []
    for unit in units:
        for metric in METRICS:
            actual   = ytd_a.get((unit.id, metric), 0.0)
            target   = ytd_t.get((unit.id, metric), 0.0)
            annual   = ann_t.get((unit.id, metric), 0.0)
            prev_act = prev_a.get((unit.id, metric), 0.0)
            rate     = round(actual / target * 100, 1) if target else 0.0
            yoy      = round((actual - prev_act) / prev_act * 100, 1) if prev_act else None
            summaries.append({
                "business_unit_id":   unit.id,
                "business_unit_name": unit.name,
                "metric_type":        metric,
                "ytd_actual":         actual,
                "ytd_target":         target,
                "rate":               rate,
                "annual_target":      annual,
                "prev_ytd_actual":    prev_act,
                "yoy_rate":           yoy,
            })

    return ApiResponse(data={
        "year": year, "cur_month": cur_month, "summaries": summaries
    })


# ── Division Detail ───────────────────────────────────
@router.get("/division/{div_id}", response_model=ApiResponse)
def division_detail(
    div_id: int,
    year: int = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    cur_month = _cur_month()
    unit = session.get(BusinessUnit, div_id)
    if not unit:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="事业部不存在")

    ann_t = _annual_targets(session, year)
    ytd_a = _ytd_actual(session, year, cur_month)
    ytd_t = _ytd_target(session, year, cur_month)
    prev_a = _ytd_actual(session, year - 1, cur_month)

    metrics_data = {}
    for metric in METRICS:
        # Monthly actuals array (12 months)
        monthly_rows = session.exec(
            select(MonthlyActual)
            .where(
                MonthlyActual.year == year,
                MonthlyActual.business_unit_id == div_id,
                MonthlyActual.metric_type == metric,
            )
            .order_by(MonthlyActual.month)
        ).all()
        monthly_actual = [0.0] * 12
        for row in monthly_rows:
            monthly_actual[row.month - 1] = row.actual_amount

        # Monthly targets array
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == div_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        monthly_target = [0.0] * 12
        if at:
            mt_rows = session.exec(
                select(MonthlyTarget)
                .where(MonthlyTarget.annual_target_id == at.id)
                .order_by(MonthlyTarget.month)
            ).all()
            if mt_rows:
                for mt in mt_rows:
                    monthly_target[mt.month - 1] = mt.target_amount
            else:
                # fallback: even distribution
                monthly_target = [round(at.target_amount / 12, 2)] * 12

        actual   = ytd_a.get((div_id, metric), 0.0)
        target   = ytd_t.get((div_id, metric), 0.0)
        annual   = ann_t.get((div_id, metric), 0.0)
        prev_act = prev_a.get((div_id, metric), 0.0)
        rate     = round(actual / target * 100, 1) if target else 0.0
        gap      = round(annual - actual, 2)
        remain   = 12 - cur_month
        per_month = round(gap / remain, 2) if remain > 0 else 0.0

        # Opp support
        opp_rows = session.exec(
            select(func.sum(Opportunity.estimated_amount))
            .where(
                Opportunity.business_unit_id == div_id,
                Opportunity.metric_type == metric,
                Opportunity.year == year,
                Opportunity.status == "进行中",
            )
        ).first()
        opp_total = opp_rows or 0.0
        opp_cover = round(opp_total / gap * 100, 1) if gap > 0 else 999.0

        metrics_data[metric] = {
            "monthly_actual": monthly_actual,
            "monthly_target": monthly_target,
            "ytd_actual": actual,
            "ytd_target": target,
            "annual_target": annual,
            "rate": rate,
            "gap": gap,
            "per_month_needed": per_month,
            "opp_support_total": opp_total,
            "opp_cover_rate": opp_cover,
            "prev_ytd_actual": prev_act,
            "yoy_rate": round((actual - prev_act) / prev_act * 100, 1) if prev_act else None,
        }

    return ApiResponse(data={
        "business_unit_id": div_id,
        "business_unit_name": unit.name,
        "year": year,
        "cur_month": cur_month,
        "metrics": metrics_data,
    })


# ── Opportunity Support ───────────────────────────────
@router.get("/opportunity-support", response_model=ApiResponse)
def opportunity_support(
    year: int = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    cur_month = _cur_month()

    ytd_a = _ytd_actual(session, year, cur_month)
    ann_t = _annual_targets(session, year)

    contract_actual  = sum(v for (_, m), v in ytd_a.items() if m == "contract")
    contract_annual  = sum(v for (_, m), v in ann_t.items() if m == "contract")
    contract_gap     = max(contract_annual - contract_actual, 0)

    # Active opps
    active_opps = session.exec(
        select(Opportunity).where(Opportunity.year == year, Opportunity.status == "进行中")
    ).all()
    opp_total = sum(o.estimated_amount for o in active_opps)
    cover_rate = round(opp_total / contract_gap * 100, 1) if contract_gap else 999.0

    # Funnel
    STAGES = ["线索", "立项", "报价", "签约跟进", "已完成"]
    all_opps = session.exec(
        select(Opportunity).where(Opportunity.year == year)
    ).all()
    funnel = []
    for stage in STAGES:
        items = [o for o in all_opps if o.stage == stage]
        funnel.append({
            "stage": stage,
            "count": len(items),
            "total_amount": sum(o.estimated_amount for o in items),
        })

    # Quarterly distribution per division
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    quarterly = {q: {} for q in ["Q1", "Q2", "Q3", "Q4"]}
    for opp in all_opps:
        unit = next((u for u in units if u.id == opp.business_unit_id), None)
        name = unit.name if unit else str(opp.business_unit_id)
        quarterly[opp.quarter][name] = quarterly[opp.quarter].get(name, 0) + opp.estimated_amount

    return ApiResponse(data={
        "year": year,
        "contract_gap": contract_gap,
        "opp_active_total": opp_total,
        "cover_rate": cover_rate,
        "funnel": funnel,
        "quarterly": quarterly,
        "total_count": len(all_opps),
    })


# ── Trend Analysis ────────────────────────────────────
@router.get("/trend", response_model=ApiResponse)
def trend(
    metric: str = Query(default="contract"),
    session: Session = Depends(get_session),
):
    cur_year = date.today().year
    years = [cur_year - 1, cur_year]
    cur_month = _cur_month()
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()

    matrix = []
    for unit in units:
        row = {"business_unit_id": unit.id, "business_unit_name": unit.name, "years": {}}
        for year in years:
            # Full year monthly actuals
            monthly_rows = session.exec(
                select(MonthlyActual)
                .where(
                    MonthlyActual.year == year,
                    MonthlyActual.business_unit_id == unit.id,
                    MonthlyActual.metric_type == metric,
                )
                .order_by(MonthlyActual.month)
            ).all()
            monthly = [0.0] * 12
            for r in monthly_rows:
                monthly[r.month - 1] = r.actual_amount
            ytd = sum(monthly[:cur_month])
            total = sum(monthly)
            row["years"][year] = {
                "monthly": monthly,
                "ytd": ytd,
                "total": total,
            }
        # YoY growth
        prev = row["years"][cur_year - 1]["ytd"]
        curr = row["years"][cur_year]["ytd"]
        row["yoy_rate"] = round((curr - prev) / prev * 100, 1) if prev else None
        matrix.append(row)

    # Center-level monthly totals (for multi-year line chart)
    center_monthly = {}
    for year in years:
        center_monthly[year] = [
            sum(
                next(
                    (
                        r.actual_amount
                        for r in session.exec(
                            select(MonthlyActual).where(
                                MonthlyActual.year == year,
                                MonthlyActual.month == m + 1,
                                MonthlyActual.business_unit_id == unit.id,
                                MonthlyActual.metric_type == metric,
                            )
                        ).all()
                    ),
                    0.0,
                )
                for unit in units
            )
            for m in range(12)
        ]

    return ApiResponse(data={
        "metric": metric,
        "years": years,
        "cur_month": cur_month,
        "matrix": matrix,
        "center_monthly": center_monthly,
    })


# ── Business Units list ───────────────────────────────
@router.get("/units", response_model=ApiResponse)
def list_units(session: Session = Depends(get_session)):
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    return ApiResponse(data=[
        {"id": u.id, "name": u.name, "code": u.code, "sort_order": u.sort_order}
        for u in units
    ])
