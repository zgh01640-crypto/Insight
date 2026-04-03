from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from schemas import ApiResponse, CollectionCreate, CollectionUpdate
from models import CollectionItem, BusinessUnit
from database import get_session

router = APIRouter()


def _enrich(item: CollectionItem, session: Session) -> dict:
    """补充业务部门名称"""
    bu = session.get(BusinessUnit, item.business_unit_id)
    return {
        "id": item.id,
        "year": item.year,
        "business_unit_id": item.business_unit_id,
        "business_unit_name": bu.name if bu else "",
        "project_name": item.project_name,
        "client_name": item.client_name,
        "amount": item.amount,
        "status": item.status,
        "notes": item.notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/dashboard", response_model=ApiResponse)
def collection_dashboard(
    year: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """催收仪表盘：全局汇总 + 按事业部分组 + Top10重点项目"""
    year = year or datetime.utcnow().year
    items = session.exec(
        select(CollectionItem).where(CollectionItem.year == year)
    ).all()
    units = {u.id: u.name for u in session.exec(select(BusinessUnit)).all()}

    collecting  = [i for i in items if i.status == "催收中"]
    recovered   = [i for i in items if i.status == "已回款"]
    written_off = [i for i in items if i.status == "已核销"]

    total_amount     = sum(i.amount for i in items)
    collecting_amt   = sum(i.amount for i in collecting)
    recovered_amt    = sum(i.amount for i in recovered)
    written_off_amt  = sum(i.amount for i in written_off)
    recovery_rate    = round(recovered_amt / total_amount * 100, 1) if total_amount else 0

    # 按事业部聚合
    by_unit_map: dict = {}
    for i in items:
        d = by_unit_map.setdefault(i.business_unit_id, {
            "business_unit_id":   i.business_unit_id,
            "business_unit_name": units.get(i.business_unit_id, ""),
            "total_amount":       0.0,
            "total_count":        0,
            "collecting_amount":  0.0,
            "collecting_count":   0,
            "recovered_amount":   0.0,
            "recovered_count":    0,
            "written_off_amount": 0.0,
            "written_off_count":  0,
        })
        d["total_amount"] += i.amount
        d["total_count"]  += 1
        if i.status == "催收中":
            d["collecting_amount"] += i.amount
            d["collecting_count"]  += 1
        elif i.status == "已回款":
            d["recovered_amount"] += i.amount
            d["recovered_count"]  += 1
        elif i.status == "已核销":
            d["written_off_amount"] += i.amount
            d["written_off_count"]  += 1

    for d in by_unit_map.values():
        d["recovery_rate"] = round(
            d["recovered_amount"] / d["total_amount"] * 100, 1
        ) if d["total_amount"] else 0

    by_unit = sorted(by_unit_map.values(), key=lambda x: x["total_amount"], reverse=True)

    # Top10 催收中项目（按金额降序）
    top_items = sorted(collecting, key=lambda x: x.amount, reverse=True)[:10]

    # 按事业部分组明细（每组按金额降序）
    items_by_unit_map: dict = {}
    for i in items:
        items_by_unit_map.setdefault(i.business_unit_id, []).append(i)

    items_by_unit = {
        units.get(uid, str(uid)): [
            {
                "project_name": i.project_name,
                "client_name":  i.client_name,
                "amount":       i.amount,
                "status":       i.status,
                "notes":        i.notes,
            }
            for i in sorted(unit_items, key=lambda x: x.amount, reverse=True)
        ]
        for uid, unit_items in items_by_unit_map.items()
    }

    return ApiResponse(data={
        "year": year,
        "summary": {
            "total_amount":       round(total_amount, 2),
            "total_count":        len(items),
            "collecting_amount":  round(collecting_amt, 2),
            "collecting_count":   len(collecting),
            "recovered_amount":   round(recovered_amt, 2),
            "recovered_count":    len(recovered),
            "written_off_amount": round(written_off_amt, 2),
            "written_off_count":  len(written_off),
            "recovery_rate":      recovery_rate,
        },
        "by_unit": by_unit,
        "top_items": [
            {
                "project_name":       i.project_name,
                "client_name":        i.client_name,
                "business_unit_name": units.get(i.business_unit_id, ""),
                "amount":             i.amount,
                "status":             i.status,
                "notes":              i.notes,
            }
            for i in top_items
        ],
        "items_by_unit": items_by_unit,
    })


@router.get("/", response_model=ApiResponse)
def list_collections(
    year: Optional[int] = None,
    business_unit_id: Optional[int] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """列表查询，支持按年份、事业部、状态筛选"""
    q = select(CollectionItem)
    if year:
        q = q.where(CollectionItem.year == year)
    if business_unit_id:
        q = q.where(CollectionItem.business_unit_id == business_unit_id)
    if status:
        q = q.where(CollectionItem.status == status)
    q = q.order_by(CollectionItem.year.desc(), CollectionItem.created_at.desc())
    items = session.exec(q).all()
    return ApiResponse(data=[_enrich(item, session) for item in items])


@router.post("/", response_model=ApiResponse)
def create_collection(
    body: CollectionCreate,
    session: Session = Depends(get_session),
):
    """创建单条催收项目"""
    item = CollectionItem(**body.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return ApiResponse(data=_enrich(item, session), message="催收项目已创建")


@router.put("/{item_id}", response_model=ApiResponse)
def update_collection(
    item_id: int,
    body: CollectionUpdate,
    session: Session = Depends(get_session),
):
    """更新催收项目"""
    item = session.get(CollectionItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="催收项目不存在")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    item.updated_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return ApiResponse(data=_enrich(item, session), message="已更新")


@router.delete("/{item_id}", response_model=ApiResponse)
def delete_collection(
    item_id: int,
    session: Session = Depends(get_session),
):
    """删除催收项目"""
    item = session.get(CollectionItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="催收项目不存在")
    session.delete(item)
    session.commit()
    return ApiResponse(message="已删除")
