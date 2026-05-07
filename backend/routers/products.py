import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from database import get_session
from models import Product, ProductMilestone, ProductAttachment, BusinessUnit
from schemas import ApiResponse, ProductCreate, ProductUpdate, MilestoneCreate, AttachmentRead

router = APIRouter()

ATTACH_DIR = "/app/data/attachments"


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _enrich(p: Product, session: Session, include_details: bool = False) -> dict:
    bu = session.get(BusinessUnit, p.business_unit_id)
    result = {
        "id": p.id,
        "business_unit_id": p.business_unit_id,
        "business_unit_name": bu.name if bu else "",
        "name": p.name,
        "status": p.status,
        "initiated_at": str(p.initiated_at) if p.initiated_at else None,
        "product_manager": p.product_manager,
        "tech_support": p.tech_support,
        "dev_members": p.dev_members,
        "progress": p.progress,
        "risk": p.risk,
        "notes": p.notes,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "milestones": [],
        "attachments": [],
    }
    if include_details:
        milestones = session.exec(
            select(ProductMilestone)
            .where(ProductMilestone.product_id == p.id)
            .order_by(ProductMilestone.sort_order, ProductMilestone.id)
        ).all()
        result["milestones"] = [
            {
                "id": m.id, "product_id": m.product_id, "name": m.name,
                "planned_date": str(m.planned_date) if m.planned_date else None,
                "actual_date": str(m.actual_date) if m.actual_date else None,
                "status": m.status, "sort_order": m.sort_order,
            }
            for m in milestones
        ]
        attachments = session.exec(
            select(ProductAttachment)
            .where(ProductAttachment.product_id == p.id)
            .order_by(ProductAttachment.uploaded_at)
        ).all()
        result["attachments"] = [
            {
                "id": a.id, "product_id": a.product_id,
                "filename": a.filename, "file_size": a.file_size,
                "uploaded_at": a.uploaded_at,
            }
            for a in attachments
        ]
    else:
        # 列表页只返回里程碑统计
        milestones = session.exec(
            select(ProductMilestone).where(ProductMilestone.product_id == p.id)
        ).all()
        total = len(milestones)
        done = sum(1 for m in milestones if m.status == "已完成")
        result["milestone_total"] = total
        result["milestone_done"] = done
        attach_count = len(session.exec(
            select(ProductAttachment).where(ProductAttachment.product_id == p.id)
        ).all())
        result["attachment_count"] = attach_count
    return result


# ── 产品列表 ──────────────────────────────────────────
@router.get("/", response_model=ApiResponse)
def list_products(
    business_unit_id: int = None,
    status: str = None,
    keyword: str = None,
    session: Session = Depends(get_session),
):
    q = select(Product).order_by(Product.created_at.desc())
    if business_unit_id:
        q = q.where(Product.business_unit_id == business_unit_id)
    if status:
        q = q.where(Product.status == status)
    if keyword:
        q = q.where(Product.name.contains(keyword))
    products = session.exec(q).all()
    return ApiResponse(data=[_enrich(p, session, include_details=False) for p in products])


# ── 驾驶舱聚合 ────────────────────────────────────────
@router.get("/dashboard", response_model=ApiResponse)
def product_dashboard(session: Session = Depends(get_session)):
    ALL_STATUSES = ['立项中', '开发中', '测试中', '已上线', '延迟', '已暂停', '已终止']
    MS_STATUSES  = ['未开始', '进行中', '已完成', '延期']

    products   = session.exec(select(Product)).all()
    milestones = session.exec(select(ProductMilestone)).all()
    units      = session.exec(select(BusinessUnit).order_by(BusinessUnit.sort_order)).all()
    unit_map   = {u.id: u.name for u in units}

    # ── 全局汇总 ─────────────────────────────────────
    by_status = {s: 0 for s in ALL_STATUSES}
    for p in products:
        by_status[p.status] = by_status.get(p.status, 0) + 1

    ms_total = len(milestones)
    ms_done  = sum(1 for m in milestones if m.status == '已完成')

    at_risk_ids = set()
    for p in products:
        if p.status == '延迟' or (p.risk and p.risk.strip()):
            at_risk_ids.add(p.id)

    # ── 按事业部聚合 ──────────────────────────────────
    unit_data = {}  # unit_name → {...}
    for u in units:
        unit_data[u.name] = {
            'name': u.name,
            'total': 0,
            'by_status': {s: 0 for s in ALL_STATUSES},
            'milestone_total': 0,
            'milestone_done': 0,
        }

    for p in products:
        uname = unit_map.get(p.business_unit_id, '未知')
        if uname not in unit_data:
            unit_data[uname] = {'name': uname, 'total': 0,
                                'by_status': {s: 0 for s in ALL_STATUSES},
                                'milestone_total': 0, 'milestone_done': 0}
        unit_data[uname]['total'] += 1
        unit_data[uname]['by_status'][p.status] = unit_data[uname]['by_status'].get(p.status, 0) + 1

    # 里程碑按产品关联到事业部
    pid_to_unit = {p.id: unit_map.get(p.business_unit_id, '未知') for p in products}
    ms_by_unit  = {}  # unit_name → {status: count}
    for u in units:
        ms_by_unit[u.name] = {s: 0 for s in MS_STATUSES}

    for m in milestones:
        uname = pid_to_unit.get(m.product_id, '未知')
        if uname not in ms_by_unit:
            ms_by_unit[uname] = {s: 0 for s in MS_STATUSES}
        ms_by_unit[uname][m.status] = ms_by_unit[uname].get(m.status, 0) + 1
        if uname in unit_data:
            unit_data[uname]['milestone_total'] += 1
            if m.status == '已完成':
                unit_data[uname]['milestone_done'] += 1

    by_unit = []
    for u in units:
        d = unit_data.get(u.name)
        if not d or d['total'] == 0:
            continue
        mt = d['milestone_total']
        md = d['milestone_done']
        d['milestone_rate'] = round(md / mt * 100, 1) if mt else 0
        by_unit.append(d)

    milestone_by_unit = [
        {'name': uname, **counts}
        for uname, counts in ms_by_unit.items()
        if any(counts.values())
    ]

    # ── 风险产品列表 ──────────────────────────────────
    at_risk = []
    for p in products:
        if p.id in at_risk_ids:
            at_risk.append({
                'id': p.id,
                'name': p.name,
                'business_unit_name': unit_map.get(p.business_unit_id, ''),
                'status': p.status,
                'product_manager': p.product_manager,
                'progress': p.progress,
                'risk': p.risk,
            })

    return ApiResponse(data={
        'summary': {
            'total': len(products),
            'by_status': by_status,
            'milestone_total': ms_total,
            'milestone_done': ms_done,
            'at_risk_count': len(at_risk_ids),
        },
        'by_unit': by_unit,
        'milestone_by_unit': milestone_by_unit,
        'at_risk': at_risk,
    })


# ── 产品详情 ──────────────────────────────────────────
@router.get("/{product_id}", response_model=ApiResponse)
def get_product(product_id: int, session: Session = Depends(get_session)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="产品不存在")
    return ApiResponse(data=_enrich(p, session, include_details=True))


# ── 创建产品 ──────────────────────────────────────────
@router.post("/", response_model=ApiResponse)
def create_product(body: ProductCreate, session: Session = Depends(get_session)):
    p = Product(**body.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return ApiResponse(data=_enrich(p, session, include_details=True), message="产品已创建")


# ── 更新产品 ──────────────────────────────────────────
@router.put("/{product_id}", response_model=ApiResponse)
def update_product(product_id: int, body: ProductUpdate, session: Session = Depends(get_session)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="产品不存在")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    session.add(p)
    session.commit()
    session.refresh(p)
    return ApiResponse(data=_enrich(p, session, include_details=True), message="已更新")


# ── 删除产品 ──────────────────────────────────────────
@router.delete("/{product_id}", response_model=ApiResponse)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="产品不存在")
    # 删除附件文件
    attachments = session.exec(
        select(ProductAttachment).where(ProductAttachment.product_id == product_id)
    ).all()
    for a in attachments:
        try:
            os.unlink(a.stored_path)
        except Exception:
            pass
        session.delete(a)
    # 删除里程碑
    milestones = session.exec(
        select(ProductMilestone).where(ProductMilestone.product_id == product_id)
    ).all()
    for m in milestones:
        session.delete(m)
    session.delete(p)
    session.commit()
    return ApiResponse(message="已删除")


# ── 里程碑 CRUD ───────────────────────────────────────
@router.get("/{product_id}/milestones", response_model=ApiResponse)
def get_milestones(product_id: int, session: Session = Depends(get_session)):
    ms = session.exec(
        select(ProductMilestone)
        .where(ProductMilestone.product_id == product_id)
        .order_by(ProductMilestone.sort_order, ProductMilestone.id)
    ).all()
    return ApiResponse(data=[
        {
            "id": m.id, "product_id": m.product_id, "name": m.name,
            "planned_date": str(m.planned_date) if m.planned_date else None,
            "actual_date": str(m.actual_date) if m.actual_date else None,
            "status": m.status, "sort_order": m.sort_order,
        }
        for m in ms
    ])


@router.post("/{product_id}/milestones", response_model=ApiResponse)
def create_milestone(product_id: int, body: MilestoneCreate, session: Session = Depends(get_session)):
    m = ProductMilestone(product_id=product_id, **body.model_dump())
    session.add(m)
    session.commit()
    session.refresh(m)
    return ApiResponse(data={"id": m.id, "product_id": m.product_id, "name": m.name,
                             "planned_date": str(m.planned_date) if m.planned_date else None,
                             "actual_date": str(m.actual_date) if m.actual_date else None,
                             "status": m.status, "sort_order": m.sort_order})


@router.put("/{product_id}/milestones/{mid}", response_model=ApiResponse)
def update_milestone(product_id: int, mid: int, body: MilestoneCreate, session: Session = Depends(get_session)):
    m = session.get(ProductMilestone, mid)
    if not m or m.product_id != product_id:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    session.add(m)
    session.commit()
    return ApiResponse(message="已更新")


@router.delete("/{product_id}/milestones/{mid}", response_model=ApiResponse)
def delete_milestone(product_id: int, mid: int, session: Session = Depends(get_session)):
    m = session.get(ProductMilestone, mid)
    if not m or m.product_id != product_id:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    session.delete(m)
    session.commit()
    return ApiResponse(message="已删除")


# ── 附件上传/列表/删除/下载 ────────────────────────────
@router.post("/{product_id}/attachments", response_model=ApiResponse)
async def upload_attachment(
    product_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="产品不存在")
    dir_path = os.path.join(ATTACH_DIR, str(product_id))
    _ensure_dir(dir_path)
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    stored_path = os.path.join(dir_path, safe_name)
    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)
    a = ProductAttachment(
        product_id=product_id,
        filename=file.filename,
        stored_path=stored_path,
        file_size=len(content),
    )
    session.add(a)
    session.commit()
    session.refresh(a)
    return ApiResponse(data={"id": a.id, "filename": a.filename, "file_size": a.file_size, "uploaded_at": a.uploaded_at}, message="上传成功")


@router.get("/{product_id}/attachments", response_model=ApiResponse)
def list_attachments(product_id: int, session: Session = Depends(get_session)):
    items = session.exec(
        select(ProductAttachment)
        .where(ProductAttachment.product_id == product_id)
        .order_by(ProductAttachment.uploaded_at)
    ).all()
    return ApiResponse(data=[
        {"id": a.id, "product_id": a.product_id, "filename": a.filename,
         "file_size": a.file_size, "uploaded_at": a.uploaded_at}
        for a in items
    ])


@router.delete("/{product_id}/attachments/{aid}", response_model=ApiResponse)
def delete_attachment(product_id: int, aid: int, session: Session = Depends(get_session)):
    a = session.get(ProductAttachment, aid)
    if not a or a.product_id != product_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    try:
        os.unlink(a.stored_path)
    except Exception:
        pass
    session.delete(a)
    session.commit()
    return ApiResponse(message="已删除")


@router.get("/attachments/{aid}/download")
def download_attachment(aid: int, session: Session = Depends(get_session)):
    a = session.get(ProductAttachment, aid)
    if not a:
        raise HTTPException(status_code=404, detail="附件不存在")
    if not os.path.exists(a.stored_path):
        raise HTTPException(status_code=404, detail="文件不存在于服务器")
    return FileResponse(
        path=a.stored_path,
        filename=a.filename,
        media_type="application/octet-stream",
    )
