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

# 季度分配比例 2:3:3:2，月度 = 季度/3
# Q1=20%, Q2=30%, Q3=30%, Q4=20%
_Q_WEIGHTS = [0.2/3] * 3 + [0.3/3] * 3 + [0.3/3] * 3 + [0.2/3] * 3  # 12个月


def _monthly_targets(annual: float) -> list:
    """按 2:3:3:2 季度比例分解年度目标到12个月。"""
    return [round(annual * w, 2) for w in _Q_WEIGHTS]


def _ytd_weight(cur_month: int) -> float:
    """1~cur_month 的累计权重（cur_month 为1-12）。"""
    return sum(_Q_WEIGHTS[:cur_month])


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

    # Fallback: if no monthly breakdown, use 2:3:3:2 quarterly distribution
    at_rows = session.exec(
        select(AnnualTarget).where(AnnualTarget.year == year)
    ).all()
    for at in at_rows:
        key = (at.business_unit_id, at.metric_type)
        # 月度分解为空或全为0时，用 2:3:3:2 fallback
        if not result.get(key):
            result[key] = round(at.target_amount * _ytd_weight(cur_month), 2)
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
            actual      = ytd_a.get((unit.id, metric), 0.0)
            target      = ytd_t.get((unit.id, metric), 0.0)
            annual      = ann_t.get((unit.id, metric), 0.0)
            prev_act    = prev_a.get((unit.id, metric), 0.0)
            rate        = round(actual / target * 100, 1) if target else 0.0
            annual_rate = round(actual / annual * 100, 1) if annual else 0.0
            yoy         = round((actual - prev_act) / prev_act * 100, 1) if prev_act else None
            summaries.append({
                "business_unit_id":   unit.id,
                "business_unit_name": unit.name,
                "metric_type":        metric,
                "ytd_actual":         actual,
                "ytd_target":         target,
                "rate":               rate,
                "annual_rate":        annual_rate,
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
            if mt_rows and any(mt.target_amount > 0 for mt in mt_rows):
                for mt in mt_rows:
                    monthly_target[mt.month - 1] = mt.target_amount
            else:
                # fallback: 2:3:3:2 quarterly distribution（月度分解为空或全0时）
                monthly_target = _monthly_targets(at.target_amount)

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
    quarter: str = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    # 默认当前季度
    if quarter is None:
        m = date.today().month
        quarter = "Q1" if m <= 3 else "Q2" if m <= 6 else "Q3" if m <= 9 else "Q4"
    quarter = quarter.upper()

    q_months = _QUARTER_MONTHS.get(quarter, [1, 2, 3])
    cur_month = _cur_month()
    ann_t = _annual_targets(session, year)

    # 季度实际完成（该季度已过月份之和）
    q_rows = session.exec(
        select(
            MonthlyActual.business_unit_id,
            MonthlyActual.metric_type,
            func.sum(MonthlyActual.actual_amount).label("total"),
        )
        .where(
            MonthlyActual.year == year,
            MonthlyActual.month.in_(q_months),
            MonthlyActual.month <= cur_month,
        )
        .group_by(MonthlyActual.business_unit_id, MonthlyActual.metric_type)
    ).all()
    q_actual_map = {(r.business_unit_id, r.metric_type): r.total or 0.0 for r in q_rows}

    # 该季度商机
    q_opps = session.exec(
        select(Opportunity).where(
            Opportunity.year == year,
            Opportunity.quarter == quarter,
        )
    ).all()
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    STAGES = ["线索", "立项", "报价", "签约跟进", "已完成"]

    def _div_q_target(unit_id, metric):
        """单个事业部某指标的季度目标。"""
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == unit_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        if at:
            mt_rows = session.exec(
                select(MonthlyTarget).where(
                    MonthlyTarget.annual_target_id == at.id,
                    MonthlyTarget.month.in_(q_months),
                )
            ).all()
            if mt_rows and any(mt.target_amount > 0 for mt in mt_rows):
                return sum(mt.target_amount for mt in mt_rows)
        annual = ann_t.get((unit_id, metric), 0.0)
        return round(annual * _QUARTER_WEIGHT[quarter], 2)

    metrics_data = {}
    for metric in METRICS:
        q_actual_sum = sum(v for (_, m), v in q_actual_map.items() if m == metric)
        q_tgt = sum(_div_q_target(u.id, metric) for u in units)
        gap = max(q_tgt - q_actual_sum, 0)

        active = [o for o in q_opps if o.metric_type == metric and o.status == "进行中"]
        opp_total = sum(o.estimated_amount for o in active)
        cover_rate = round(opp_total / q_tgt * 100, 1) if q_tgt else 0.0

        metric_opps = [o for o in q_opps if o.metric_type == metric]
        funnel = []
        for stage in STAGES:
            items = [o for o in metric_opps if o.stage == stage]
            funnel.append({
                "stage": stage,
                "count": len(items),
                "total_amount": sum(o.estimated_amount for o in items),
            })

        # 按事业部统计覆盖率（进行中商机 / 季度目标）
        div_coverage = []
        for u in units:
            u_tgt = _div_q_target(u.id, metric)
            u_active = [o for o in active if o.business_unit_id == u.id]
            u_opp = sum(o.estimated_amount for o in u_active)
            u_rate = round(u_opp / u_tgt * 100, 1) if u_tgt else 0.0
            div_coverage.append({
                "name": u.name,
                "opp_total": u_opp,
                "quarter_target": u_tgt,
                "cover_rate": u_rate,
            })

        metrics_data[metric] = {
            "quarter_actual": q_actual_sum,
            "quarter_target": q_tgt,
            "gap": gap,
            "opp_active_total": opp_total,
            "cover_rate": cover_rate,
            "funnel": funnel,
            "div_coverage": div_coverage,
            "count": len(metric_opps),
        }

    return ApiResponse(data={
        "year": year,
        "quarter": quarter,
        "cur_month": cur_month,
        "metrics": metrics_data,
        "total_count": len(q_opps),
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


# ── Monthly Dashboard ─────────────────────────────────
@router.get("/monthly", response_model=ApiResponse)
def monthly_dashboard(
    year: int = Query(default=None),
    month: int = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month

    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    ann_t = _annual_targets(session, year)

    # 月度实际（本年）
    rows = session.exec(
        select(
            MonthlyActual.business_unit_id,
            MonthlyActual.metric_type,
            MonthlyActual.actual_amount,
        )
        .where(MonthlyActual.year == year, MonthlyActual.month == month)
    ).all()
    m_actual = {(r.business_unit_id, r.metric_type): r.actual_amount for r in rows}

    # 月度实际（去年同期）
    prev_rows = session.exec(
        select(
            MonthlyActual.business_unit_id,
            MonthlyActual.metric_type,
            MonthlyActual.actual_amount,
        )
        .where(MonthlyActual.year == year - 1, MonthlyActual.month == month)
    ).all()
    m_prev = {(r.business_unit_id, r.metric_type): r.actual_amount for r in prev_rows}

    def _m_target(unit_id, metric):
        """月度目标：优先用月度分解，否则用 2:3:3:2 fallback。"""
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == unit_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        if at:
            mt = session.exec(
                select(MonthlyTarget).where(
                    MonthlyTarget.annual_target_id == at.id,
                    MonthlyTarget.month == month,
                )
            ).first()
            if mt and mt.target_amount > 0:
                return mt.target_amount
        annual = ann_t.get((unit_id, metric), 0.0)
        return round(annual * _Q_WEIGHTS[month - 1], 2)

    # 产品中心合计
    center = []
    for metric in METRICS:
        tgt  = sum(_m_target(u.id, metric) for u in units)
        act  = sum(m_actual.get((u.id, metric), 0.0) for u in units)
        prev = sum(m_prev.get((u.id, metric), 0.0) for u in units)
        ann  = sum(ann_t.get((u.id, metric), 0.0) for u in units)
        center.append({
            "metric_type":    metric,
            "month_target":   tgt,
            "month_actual":   act,
            "annual_target":  ann,
            "rate": round(act / tgt * 100, 1) if tgt else 0.0,
            "prev_month_actual": prev,
            "yoy_rate": round((act - prev) / prev * 100, 1) if prev else None,
        })

    # 各事业部明细
    divisions = []
    for unit in units:
        metrics_data = {}
        for metric in METRICS:
            tgt  = _m_target(unit.id, metric)
            act  = m_actual.get((unit.id, metric), 0.0)
            prev = m_prev.get((unit.id, metric), 0.0)
            ann  = ann_t.get((unit.id, metric), 0.0)
            metrics_data[metric] = {
                "month_target":  tgt,
                "month_actual":  act,
                "annual_target": ann,
                "rate": round(act / tgt * 100, 1) if tgt else 0.0,
                "prev_month_actual": prev,
                "yoy_rate": round((act - prev) / prev * 100, 1) if prev else None,
            }
        divisions.append({
            "business_unit_id":   unit.id,
            "business_unit_name": unit.name,
            "metrics": metrics_data,
        })

    return ApiResponse(data={
        "year": year, "month": month,
        "center": center, "divisions": divisions,
    })


# ── Quarterly Dashboard ───────────────────────────────
_QUARTER_MONTHS = { "Q1": [1,2,3], "Q2": [4,5,6], "Q3": [7,8,9], "Q4": [10,11,12] }
_QUARTER_WEIGHT = { "Q1": 0.2, "Q2": 0.3, "Q3": 0.3, "Q4": 0.2 }


def _cur_quarter() -> str:
    m = date.today().month
    return "Q1" if m <= 3 else "Q2" if m <= 6 else "Q3" if m <= 9 else "Q4"


@router.get("/quarterly", response_model=ApiResponse)
def quarterly_dashboard(
    year: int = Query(default=None),
    quarter: str = Query(default=None),
    session: Session = Depends(get_session),
):
    if year is None:
        year = date.today().year
    if quarter is None:
        quarter = _cur_quarter()
    quarter = quarter.upper()

    months = _QUARTER_MONTHS.get(quarter, [1,2,3])
    cur_month = date.today().month

    units    = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    ann_t    = _annual_targets(session, year)

    # 季度实际完成：该季度已过月份的合计（未到的月份不计）
    rows = session.exec(
        select(
            MonthlyActual.business_unit_id,
            MonthlyActual.metric_type,
            func.sum(MonthlyActual.actual_amount).label("total"),
        )
        .where(
            MonthlyActual.year == year,
            MonthlyActual.month.in_(months),
            MonthlyActual.month <= cur_month,
        )
        .group_by(MonthlyActual.business_unit_id, MonthlyActual.metric_type)
    ).all()
    q_actual = {(r.business_unit_id, r.metric_type): r.total or 0.0 for r in rows}

    def _q_target(unit_id, metric):
        annual = ann_t.get((unit_id, metric), 0.0)
        # 优先用月度分解之和
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == unit_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        if at:
            mt_rows = session.exec(
                select(MonthlyTarget)
                .where(
                    MonthlyTarget.annual_target_id == at.id,
                    MonthlyTarget.month.in_(months),
                )
            ).all()
            if mt_rows and any(mt.target_amount > 0 for mt in mt_rows):
                return sum(mt.target_amount for mt in mt_rows)
        # fallback: 2:3:3:2
        return round(annual * _QUARTER_WEIGHT[quarter], 2)

    # 产品中心合计
    center = []
    for metric in METRICS:
        q_tgt  = sum(_q_target(u.id, metric) for u in units)
        q_act  = sum(q_actual.get((u.id, metric), 0.0) for u in units)
        ann    = sum(ann_t.get((u.id, metric), 0.0) for u in units)
        rate   = round(q_act / q_tgt * 100, 1) if q_tgt else 0.0
        center.append({
            "metric_type": metric,
            "quarter_target": q_tgt,
            "quarter_actual": q_act,
            "annual_target": ann,
            "rate": rate,
        })

    # 各事业部明细
    divisions = []
    for unit in units:
        metrics_data = {}
        for metric in METRICS:
            q_tgt = _q_target(unit.id, metric)
            q_act = q_actual.get((unit.id, metric), 0.0)
            ann   = ann_t.get((unit.id, metric), 0.0)
            rate  = round(q_act / q_tgt * 100, 1) if q_tgt else 0.0
            metrics_data[metric] = {
                "quarter_target": q_tgt,
                "quarter_actual": q_act,
                "annual_target":  ann,
                "rate": rate,
            }
        divisions.append({
            "business_unit_id":   unit.id,
            "business_unit_name": unit.name,
            "metrics": metrics_data,
        })

    # 当季已过月份数
    elapsed = sum(1 for m in months if m <= cur_month)

    return ApiResponse(data={
        "year": year,
        "quarter": quarter,
        "cur_month": cur_month,
        "elapsed_months": elapsed,
        "center": center,
        "divisions": divisions,
    })


# ── Business Units list ───────────────────────────────
@router.get("/units", response_model=ApiResponse)
def list_units(session: Session = Depends(get_session)):
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    return ApiResponse(data=[
        {"id": u.id, "name": u.name, "code": u.code, "sort_order": u.sort_order}
        for u in units
    ])
