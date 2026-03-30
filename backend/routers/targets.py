from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models import AnnualTarget, MonthlyTarget, BusinessUnit, TargetChangeLog
from schemas import ApiResponse, TargetBatchUpdate

router = APIRouter()


@router.get("/{year}", response_model=ApiResponse)
def get_targets(year: int, session: Session = Depends(get_session)):
    units = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    result = []
    for unit in units:
        for metric in ["contract", "revenue", "payment"]:
            at = session.exec(
                select(AnnualTarget).where(
                    AnnualTarget.year == year,
                    AnnualTarget.business_unit_id == unit.id,
                    AnnualTarget.metric_type == metric,
                )
            ).first()
            monthly = []
            if at:
                mts = session.exec(
                    select(MonthlyTarget)
                    .where(MonthlyTarget.annual_target_id == at.id)
                    .order_by(MonthlyTarget.month)
                ).all()
                monthly = [mt.target_amount for mt in mts]
                if len(monthly) < 12:
                    monthly += [0.0] * (12 - len(monthly))
            result.append({
                "business_unit_id": unit.id,
                "business_unit_name": unit.name,
                "metric_type": metric,
                "target_amount": at.target_amount if at else 0.0,
                "monthly_targets": monthly,
            })
    return ApiResponse(data={"year": year, "items": result})


@router.put("/{year}", response_model=ApiResponse)
def update_targets(year: int, body: TargetBatchUpdate, session: Session = Depends(get_session)):
    for item in body.items:
        at = session.exec(
            select(AnnualTarget).where(
                AnnualTarget.year == year,
                AnnualTarget.business_unit_id == item.business_unit_id,
                AnnualTarget.metric_type == item.metric_type,
            )
        ).first()
        if at:
            if at.target_amount != item.target_amount:
                session.add(TargetChangeLog(
                    annual_target_id=at.id,
                    old_amount=at.target_amount,
                    new_amount=item.target_amount,
                ))
            at.target_amount = item.target_amount
            at.updated_at = datetime.utcnow()
        else:
            at = AnnualTarget(
                year=year,
                business_unit_id=item.business_unit_id,
                metric_type=item.metric_type,
                target_amount=item.target_amount,
            )
            session.add(at)
            session.flush()

        if item.monthly_targets:
            # delete existing monthly targets
            existing = session.exec(
                select(MonthlyTarget).where(MonthlyTarget.annual_target_id == at.id)
            ).all()
            for mt in existing:
                session.delete(mt)
            for i, amt in enumerate(item.monthly_targets[:12], start=1):
                session.add(MonthlyTarget(
                    annual_target_id=at.id,
                    month=i,
                    target_amount=amt,
                ))
    session.commit()
    return ApiResponse(message="目标已保存")


@router.get("/{year}/changelog", response_model=ApiResponse)
def get_changelog(year: int, session: Session = Depends(get_session)):
    rows = session.exec(
        select(TargetChangeLog, AnnualTarget, BusinessUnit)
        .join(AnnualTarget, TargetChangeLog.annual_target_id == AnnualTarget.id)
        .join(BusinessUnit, AnnualTarget.business_unit_id == BusinessUnit.id)
        .where(AnnualTarget.year == year)
        .order_by(TargetChangeLog.changed_at.desc())
    ).all()
    data = [
        {
            "changed_at": log.changed_at,
            "business_unit": bu.name,
            "metric_type": at.metric_type,
            "old_amount": log.old_amount,
            "new_amount": log.new_amount,
        }
        for log, at, bu in rows
    ]
    return ApiResponse(data=data)
