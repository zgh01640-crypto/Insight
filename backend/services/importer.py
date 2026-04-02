"""
Import service: validates and writes Excel/CSV data.
Supports three import types: annual_target, monthly_actual, opportunity.
"""
import json
from datetime import datetime
from typing import Tuple
import pandas as pd
from sqlmodel import Session, select
from models import (
    AnnualTarget, MonthlyTarget, MonthlyActual,
    Opportunity, ImportBatch, BusinessUnit, TargetChangeLog,
)

METRIC_MAP = {"合同": "contract", "收入": "revenue", "回款": "payment"}
STAGE_VALUES = {"线索", "立项", "报价", "签约跟进", "已完成"}
STATUS_VALUES = {"进行中", "已赢单", "已输单", "已搁置"}
QUARTER_VALUES = {"Q1", "Q2", "Q3", "Q4"}


def _get_unit_map(session: Session) -> dict:
    units = session.exec(select(BusinessUnit)).all()
    return {u.name: u.id for u in units}


def _read_file(filepath: str, filename: str) -> pd.DataFrame:
    if filename.endswith(".csv"):
        return pd.read_csv(filepath, dtype=str)
    return pd.read_excel(filepath, dtype=str)


# ── Annual Target Import ──────────────────────────────
def import_annual_targets(filepath: str, filename: str, session: Session) -> ImportBatch:
    df = _read_file(filepath, filename)
    unit_map = _get_unit_map(session)
    required = ["年份", "事业部", "指标类型", "年度目标值"]
    errors = []
    success = 0

    for idx, row in df.iterrows():
        lineno = idx + 2
        row = row.fillna("")
        missing = [c for c in required if not str(row.get(c, "")).strip()]
        if missing:
            errors.append({"row": lineno, "reason": f"缺少必填字段: {', '.join(missing)}"})
            continue
        try:
            year = int(row["年份"])
            assert 2020 <= year <= 2040
        except Exception:
            errors.append({"row": lineno, "reason": "年份格式错误（需2020-2040整数）"})
            continue
        unit_name = str(row["事业部"]).strip()
        if unit_name not in unit_map:
            errors.append({"row": lineno, "reason": f"事业部不存在: {unit_name}"})
            continue
        metric_zh = str(row["指标类型"]).strip()
        if metric_zh not in METRIC_MAP:
            errors.append({"row": lineno, "reason": f"指标类型错误: {metric_zh}"})
            continue
        try:
            amount = float(row["年度目标值"])
            assert amount >= 0
        except Exception:
            errors.append({"row": lineno, "reason": "年度目标值必须为非负数"})
            continue

        metric = METRIC_MAP[metric_zh]
        unit_id = unit_map[unit_name]
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == unit_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        if at:
            if at.target_amount != amount:
                session.add(TargetChangeLog(
                    annual_target_id=at.id, old_amount=at.target_amount, new_amount=amount
                ))
            at.target_amount = amount
            at.updated_at = datetime.utcnow()
        else:
            session.add(AnnualTarget(
                year=year, business_unit_id=unit_id,
                metric_type=metric, target_amount=amount,
            ))

        # Optional monthly breakdown columns (1月..12月)
        monthly = []
        for m in range(1, 13):
            col = f"{m}月"
            val_str = str(row.get(col, "")).strip()
            if val_str:
                try:
                    monthly.append(float(val_str))
                except Exception:
                    monthly.append(0.0)
            else:
                monthly.append(0.0)

        session.flush()
        at2 = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == unit_id,
                AnnualTarget.metric_type == metric,
            )
        ).first()
        if at2 and any(v > 0 for v in monthly):
            existing = session.exec(
                select(MonthlyTarget).where(MonthlyTarget.annual_target_id == at2.id)
            ).all()
            for mt in existing:
                session.delete(mt)
            for i, amt in enumerate(monthly, start=1):
                session.add(MonthlyTarget(annual_target_id=at2.id, month=i, target_amount=amt))

        success += 1

    session.commit()
    batch = ImportBatch(
        import_type="annual_target",
        filename=filename,
        total_rows=len(df),
        success_rows=success,
        fail_rows=len(errors),
        fail_detail=json.dumps(errors, ensure_ascii=False),
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


# ── Monthly Actual Import ─────────────────────────────
def import_monthly_actuals(filepath: str, filename: str, session: Session) -> ImportBatch:
    df = _read_file(filepath, filename)
    unit_map = _get_unit_map(session)
    required = ["年份", "月份", "事业部", "指标类型", "完成值"]
    errors = []
    success = 0
    overwrite_count = 0
    actuals_list = []  # 收集所有被处理的 MonthlyActual 对象

    for idx, row in df.iterrows():
        lineno = idx + 2
        row = row.fillna("")
        missing = [c for c in required if not str(row.get(c, "")).strip()]
        if missing:
            errors.append({"row": lineno, "reason": f"缺少必填字段: {', '.join(missing)}"})
            continue
        try:
            year = int(row["年份"])
            assert 2020 <= year <= 2040
        except Exception:
            errors.append({"row": lineno, "reason": "年份格式错误"})
            continue
        try:
            month = int(row["月份"])
            assert 1 <= month <= 12
        except Exception:
            errors.append({"row": lineno, "reason": "月份格式错误（需1-12整数）"})
            continue
        unit_name = str(row["事业部"]).strip()
        if unit_name not in unit_map:
            errors.append({"row": lineno, "reason": f"事业部不存在: {unit_name}"})
            continue
        metric_zh = str(row["指标类型"]).strip()
        if metric_zh not in METRIC_MAP:
            errors.append({"row": lineno, "reason": f"指标类型错误: {metric_zh}"})
            continue
        try:
            amount = float(row["完成值"])
            assert amount >= 0
        except Exception:
            errors.append({"row": lineno, "reason": "完成值必须为非负数"})
            continue

        metric = METRIC_MAP[metric_zh]
        unit_id = unit_map[unit_name]
        existing = session.exec(
            select(MonthlyActual).where(
                MonthlyActual.year == year,
                MonthlyActual.month == month,
                MonthlyActual.business_unit_id == unit_id,
                MonthlyActual.metric_type == metric,
            )
        ).first()
        if existing:
            existing.actual_amount = amount
            existing.updated_at = datetime.utcnow()
            overwrite_count += 1
        else:
            session.add(MonthlyActual(
                year=year, month=month,
                business_unit_id=unit_id,
                metric_type=metric,
                actual_amount=amount,
            ))
        success += 1

# ── Monthly Actual Import ─────────────────────────────
def import_monthly_actuals(filepath: str, filename: str, session: Session) -> ImportBatch:
    df = _read_file(filepath, filename)
    unit_map = _get_unit_map(session)
    required = ["年份", "月份", "事业部", "指标类型", "完成值"]
    errors = []
    success = 0
    overwrite_count = 0
    actuals_list = []  # 收集所有被处理的 MonthlyActual 对象

    for idx, row in df.iterrows():
        lineno = idx + 2
        row = row.fillna("")
        missing = [c for c in required if not str(row.get(c, "")).strip()]
        if missing:
            errors.append({"row": lineno, "reason": f"缺少必填字段: {', '.join(missing)}"})
            continue
        try:
            year = int(row["年份"])
            assert 2020 <= year <= 2040
        except Exception:
            errors.append({"row": lineno, "reason": "年份格式错误"})
            continue
        try:
            month = int(row["月份"])
            assert 1 <= month <= 12
        except Exception:
            errors.append({"row": lineno, "reason": "月份格式错误（需1-12整数）"})
            continue
        unit_name = str(row["事业部"]).strip()
        if unit_name not in unit_map:
            errors.append({"row": lineno, "reason": f"事业部不存在: {unit_name}"})
            continue
        metric_zh = str(row["指标类型"]).strip()
        if metric_zh not in METRIC_MAP:
            errors.append({"row": lineno, "reason": f"指标类型错误: {metric_zh}"})
            continue
        try:
            amount = float(row["完成值"])
            assert amount >= 0
        except Exception:
            errors.append({"row": lineno, "reason": "完成值必须为非负数"})
            continue

        metric = METRIC_MAP[metric_zh]
        unit_id = unit_map[unit_name]
        existing = session.exec(
            select(MonthlyActual).where(
                MonthlyActual.year == year,
                MonthlyActual.month == month,
                MonthlyActual.business_unit_id == unit_id,
                MonthlyActual.metric_type == metric,
            )
        ).first()
        if existing:
            existing.actual_amount = amount
            existing.updated_at = datetime.utcnow()
            overwrite_count += 1
            actuals_list.append(existing)
        else:
            ma = MonthlyActual(
                year=year, month=month,
                business_unit_id=unit_id,
                metric_type=metric,
                actual_amount=amount,
            )
            session.add(ma)
            actuals_list.append(ma)
        success += 1

    # 先创建 ImportBatch 并 flush 得到 ID
    batch = ImportBatch(
        import_type="monthly_actual",
        filename=filename,
        total_rows=len(df),
        success_rows=success,
        fail_rows=len(errors),
        fail_detail=json.dumps(errors, ensure_ascii=False),
    )
    session.add(batch)
    session.flush()  # 获得 batch.id

    # 给所有处理过的 MonthlyActual 记录赋值 import_batch_id
    for actual in actuals_list:
        actual.import_batch_id = batch.id

    session.commit()
    session.refresh(batch)
    return batch


# ── Opportunity Import ────────────────────────────────
def import_opportunities(filepath: str, filename: str, session: Session) -> ImportBatch:
    df = _read_file(filepath, filename)
    unit_map = _get_unit_map(session)
    required = ["商机名称", "所属事业部", "指标类型", "所属年度", "所属季度", "预计金额（万元）", "商机阶段", "商机状态"]
    errors = []
    success = 0
    opps_list = []  # 收集所有被创建的 Opportunity 对象

    for idx, row in df.iterrows():
        lineno = idx + 2
        row = row.fillna("")
        missing = [c for c in required if not str(row.get(c, "")).strip()]
        if missing:
            errors.append({"row": lineno, "reason": f"缺少必填字段: {', '.join(missing)}"})
            continue
        unit_name = str(row["所属事业部"]).strip()
        if unit_name not in unit_map:
            errors.append({"row": lineno, "reason": f"事业部不存在: {unit_name}"})
            continue
        metric_zh = str(row["指标类型"]).strip()
        if metric_zh not in METRIC_MAP:
            errors.append({"row": lineno, "reason": f"指标类型错误: {metric_zh}"})
            continue
        try:
            year = int(row["所属年度"])
        except Exception:
            errors.append({"row": lineno, "reason": "所属年度格式错误"})
            continue
        quarter = str(row["所属季度"]).strip().upper()
        if quarter not in QUARTER_VALUES:
            errors.append({"row": lineno, "reason": f"季度格式错误: {quarter}"})
            continue
        try:
            amount = float(row["预计金额（万元）"])
            assert amount >= 0
        except Exception:
            errors.append({"row": lineno, "reason": "预计金额必须为非负数"})
            continue
        stage = str(row["商机阶段"]).strip()
        if stage not in STAGE_VALUES:
            errors.append({"row": lineno, "reason": f"商机阶段无效: {stage}"})
            continue
        status = str(row["商机状态"]).strip()
        if status not in STATUS_VALUES:
            errors.append({"row": lineno, "reason": f"商机状态无效: {status}"})
            continue
        est_date = None
        date_str = str(row.get("预计达成时间", "")).strip()
        if date_str:
            try:
                from datetime import date as ddate
                est_date = ddate.fromisoformat(date_str)
            except Exception:
                pass  # optional field, skip if bad

        opp = Opportunity(
            name=str(row["商机名称"]).strip(),
            business_unit_id=unit_map[unit_name],
            metric_type=METRIC_MAP[metric_zh],
            year=year, quarter=quarter,
            estimated_amount=amount,
            estimated_date=est_date,
            stage=stage, status=status,
            notes=str(row.get("备注", "")).strip() or None,
        )
        session.add(opp)
        opps_list.append(opp)
        success += 1

    # 先创建 ImportBatch 并 flush 得到 ID
    batch = ImportBatch(
        import_type="opportunity",
        filename=filename,
        total_rows=len(df),
        success_rows=success,
        fail_rows=len(errors),
        fail_detail=json.dumps(errors, ensure_ascii=False),
    )
    session.add(batch)
    session.flush()  # 获得 batch.id

    # 给所有创建的 Opportunity 记录赋值 import_batch_id
    for opp in opps_list:
        opp.import_batch_id = batch.id

    session.commit()
    session.refresh(batch)
    return batch
