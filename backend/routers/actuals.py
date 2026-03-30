from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from database import get_session
from models import MonthlyActual, BusinessUnit
from schemas import ApiResponse

router = APIRouter()

METRIC_LABEL = {"contract": "合同", "revenue": "收入", "payment": "回款"}


@router.get("/", response_model=ApiResponse)
def list_actuals(
    year: Optional[int] = None,
    month: Optional[int] = None,
    business_unit_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    q = select(MonthlyActual, BusinessUnit).join(
        BusinessUnit, MonthlyActual.business_unit_id == BusinessUnit.id
    )
    if year:
        q = q.where(MonthlyActual.year == year)
    if month:
        q = q.where(MonthlyActual.month == month)
    if business_unit_id:
        q = q.where(MonthlyActual.business_unit_id == business_unit_id)
    q = q.order_by(MonthlyActual.year, MonthlyActual.month, BusinessUnit.sort_order)
    rows = session.exec(q).all()
    data = [
        {
            "id": ma.id,
            "year": ma.year,
            "month": ma.month,
            "business_unit_id": ma.business_unit_id,
            "business_unit_name": bu.name,
            "metric_type": ma.metric_type,
            "metric_label": METRIC_LABEL.get(ma.metric_type, ma.metric_type),
            "actual_amount": ma.actual_amount,
            "updated_at": ma.updated_at,
        }
        for ma, bu in rows
    ]
    return ApiResponse(data=data)


@router.put("/{actual_id}", response_model=ApiResponse)
def update_actual(actual_id: int, amount: float, session: Session = Depends(get_session)):
    ma = session.get(MonthlyActual, actual_id)
    if not ma:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="记录不存在")
    from datetime import datetime
    ma.actual_amount = amount
    ma.updated_at = datetime.utcnow()
    session.add(ma)
    session.commit()
    return ApiResponse(message="已更新")


@router.delete("/{actual_id}", response_model=ApiResponse)
def delete_actual(actual_id: int, session: Session = Depends(get_session)):
    ma = session.get(MonthlyActual, actual_id)
    if not ma:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="记录不存在")
    session.delete(ma)
    session.commit()
    return ApiResponse(message="已删除")
