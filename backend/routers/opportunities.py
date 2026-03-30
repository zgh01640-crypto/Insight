from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from database import get_session
from models import Opportunity, BusinessUnit
from schemas import ApiResponse, OpportunityCreate, OpportunityUpdate

router = APIRouter()


def _enrich(opp: Opportunity, session: Session) -> dict:
    bu = session.get(BusinessUnit, opp.business_unit_id)
    return {
        "id": opp.id,
        "name": opp.name,
        "business_unit_id": opp.business_unit_id,
        "business_unit_name": bu.name if bu else "",
        "metric_type": opp.metric_type,
        "year": opp.year,
        "quarter": opp.quarter,
        "estimated_amount": opp.estimated_amount,
        "estimated_date": opp.estimated_date,
        "stage": opp.stage,
        "status": opp.status,
        "notes": opp.notes,
        "created_at": opp.created_at,
        "updated_at": opp.updated_at,
    }


@router.get("/", response_model=ApiResponse)
def list_opportunities(
    year: Optional[int] = None,
    quarter: Optional[str] = None,
    business_unit_id: Optional[int] = None,
    metric_type: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    q = select(Opportunity)
    if year: q = q.where(Opportunity.year == year)
    if quarter: q = q.where(Opportunity.quarter == quarter)
    if business_unit_id: q = q.where(Opportunity.business_unit_id == business_unit_id)
    if metric_type: q = q.where(Opportunity.metric_type == metric_type)
    if stage: q = q.where(Opportunity.stage == stage)
    if status: q = q.where(Opportunity.status == status)
    q = q.order_by(Opportunity.year, Opportunity.quarter, Opportunity.estimated_amount.desc())
    opps = session.exec(q).all()
    return ApiResponse(data=[_enrich(o, session) for o in opps])


@router.post("/", response_model=ApiResponse)
def create_opportunity(body: OpportunityCreate, session: Session = Depends(get_session)):
    opp = Opportunity(**body.model_dump())
    session.add(opp)
    session.commit()
    session.refresh(opp)
    return ApiResponse(data=_enrich(opp, session), message="商机已创建")


@router.put("/{opp_id}", response_model=ApiResponse)
def update_opportunity(opp_id: int, body: OpportunityUpdate, session: Session = Depends(get_session)):
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    for k, v in body.model_dump().items():
        setattr(opp, k, v)
    opp.updated_at = datetime.utcnow()
    session.add(opp)
    session.commit()
    return ApiResponse(data=_enrich(opp, session), message="已更新")


@router.delete("/{opp_id}", response_model=ApiResponse)
def delete_opportunity(opp_id: int, session: Session = Depends(get_session)):
    opp = session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="商机不存在")
    session.delete(opp)
    session.commit()
    return ApiResponse(message="已删除")
