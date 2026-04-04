import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from models import ConversationSession, ConversationMessage
from schemas import ApiResponse
from database import get_session

router = APIRouter()


class SessionCreate(BaseModel):
    model_id: str = "deepseek"
    year: Optional[int] = None
    title: str = ""


@router.post("/", response_model=ApiResponse)
def create_session(
    body: SessionCreate,
    session: Session = Depends(get_session),
):
    """创建新会话"""
    sid = str(uuid.uuid4())[:8]
    year = body.year or datetime.utcnow().year
    title = body.title.strip() or "新对话"
    conv = ConversationSession(id=sid, title=title, model_id=body.model_id, year=year)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return ApiResponse(data={"id": conv.id, "title": conv.title})


@router.get("/", response_model=ApiResponse)
def list_sessions(session: Session = Depends(get_session)):
    """列出历史会话（按时间倒序，最近20条）"""
    sessions = session.exec(
        select(ConversationSession)
        .order_by(ConversationSession.updated_at.desc())
        .limit(20)
    ).all()
    return ApiResponse(data=[
        {"id": s.id, "title": s.title, "model_id": s.model_id,
         "year": s.year, "updated_at": s.updated_at}
        for s in sessions
    ])


@router.get("/{session_id}/messages", response_model=ApiResponse)
def get_messages(session_id: str, session: Session = Depends(get_session)):
    """拉取某会话的全量消息"""
    conv = session.get(ConversationSession, session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at)
    ).all()
    return ApiResponse(data=[
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in msgs
    ])


@router.delete("/{session_id}", response_model=ApiResponse)
def delete_session(session_id: str, session: Session = Depends(get_session)):
    """删除会话及其所有消息"""
    conv = session.get(ConversationSession, session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = session.exec(
        select(ConversationMessage).where(ConversationMessage.session_id == session_id)
    ).all()
    for m in msgs:
        session.delete(m)
    session.delete(conv)
    session.commit()
    return ApiResponse(message="已删除")
