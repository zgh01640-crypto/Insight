from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from database import get_session
from models import MemoryItem
from schemas import ApiResponse

router = APIRouter()


@router.get("/", response_model=ApiResponse)
def list_memories(category: str = None, session: Session = Depends(get_session)):
    q = select(MemoryItem).order_by(MemoryItem.created_at.desc())
    if category:
        q = q.where(MemoryItem.category == category)
    items = session.exec(q).all()
    return ApiResponse(data=[
        {
            "id": m.id,
            "category": m.category,
            "content": m.content,
            "source": m.source,
            "created_at": m.created_at,
        }
        for m in items
    ])


@router.delete("/{memory_id}", response_model=ApiResponse)
def delete_memory(memory_id: int, session: Session = Depends(get_session)):
    item = session.get(MemoryItem, memory_id)
    if not item:
        return ApiResponse(success=False, message="记忆条目不存在")
    session.delete(item)
    session.commit()
    return ApiResponse(message="已删除")
