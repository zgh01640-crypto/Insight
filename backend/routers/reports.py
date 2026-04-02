from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session, select
from database import get_session
from models import AIReport
from schemas import ApiResponse

router = APIRouter()


class ReportCreate(BaseModel):
    year:     int
    title:    str
    content:  str
    model_id: str


@router.get("/", response_model=ApiResponse)
def list_reports(session: Session = Depends(get_session)):
    rows = session.exec(
        select(AIReport).order_by(AIReport.created_at.desc())
    ).all()
    return ApiResponse(data=[
        {
            "id": r.id, "year": r.year, "title": r.title,
            "model_id": r.model_id,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in rows
    ])


@router.post("/", response_model=ApiResponse)
def save_report(body: ReportCreate, session: Session = Depends(get_session)):
    report = AIReport(**body.model_dump())
    session.add(report)
    session.commit()
    session.refresh(report)
    return ApiResponse(data={"id": report.id}, message="报告已保存")


@router.get("/{report_id}", response_model=ApiResponse)
def get_report(report_id: int, session: Session = Depends(get_session)):
    report = session.get(AIReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return ApiResponse(data={
        "id": report.id, "year": report.year, "title": report.title,
        "content": report.content, "model_id": report.model_id,
        "created_at": report.created_at.strftime("%Y-%m-%d %H:%M"),
    })


@router.delete("/{report_id}", response_model=ApiResponse)
def delete_report(report_id: int, session: Session = Depends(get_session)):
    report = session.get(AIReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    session.delete(report)
    session.commit()
    return ApiResponse(message="已删除")
