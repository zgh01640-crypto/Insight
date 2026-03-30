import os
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File
from sqlmodel import Session, select
from database import get_session
from models import ImportBatch
from schemas import ApiResponse
from services.importer import import_annual_targets, import_monthly_actuals, import_opportunities

router = APIRouter()


async def _save_temp(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(await file.read())
    tmp.flush()
    return tmp.name


@router.post("/targets", response_model=ApiResponse)
async def import_targets_file(file: UploadFile = File(...), session: Session = Depends(get_session)):
    path = await _save_temp(file)
    try:
        batch = import_annual_targets(path, file.filename, session)
    finally:
        os.unlink(path)
    return ApiResponse(
        data={"batch_id": batch.id, "success": batch.success_rows, "fail": batch.fail_rows},
        message=f"导入完成：{batch.success_rows}条成功，{batch.fail_rows}条失败",
    )


@router.post("/actuals", response_model=ApiResponse)
async def import_actuals_file(file: UploadFile = File(...), session: Session = Depends(get_session)):
    path = await _save_temp(file)
    try:
        batch = import_monthly_actuals(path, file.filename, session)
    finally:
        os.unlink(path)
    return ApiResponse(
        data={"batch_id": batch.id, "success": batch.success_rows, "fail": batch.fail_rows},
        message=f"导入完成：{batch.success_rows}条成功，{batch.fail_rows}条失败",
    )


@router.post("/opportunities", response_model=ApiResponse)
async def import_opportunities_file(file: UploadFile = File(...), session: Session = Depends(get_session)):
    path = await _save_temp(file)
    try:
        batch = import_opportunities(path, file.filename, session)
    finally:
        os.unlink(path)
    return ApiResponse(
        data={"batch_id": batch.id, "success": batch.success_rows, "fail": batch.fail_rows},
        message=f"导入完成：{batch.success_rows}条成功，{batch.fail_rows}条失败",
    )


@router.get("/history", response_model=ApiResponse)
def get_import_history(session: Session = Depends(get_session)):
    batches = session.exec(
        select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(100)
    ).all()
    return ApiResponse(data=[
        {
            "id": b.id, "import_type": b.import_type, "filename": b.filename,
            "total_rows": b.total_rows, "success_rows": b.success_rows,
            "fail_rows": b.fail_rows, "fail_detail": b.fail_detail,
            "created_at": b.created_at,
        }
        for b in batches
    ])


@router.get("/history/{batch_id}/failures", response_model=ApiResponse)
def get_batch_failures(batch_id: int, session: Session = Depends(get_session)):
    batch = session.get(ImportBatch, batch_id)
    if not batch:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="批次不存在")
    import json
    return ApiResponse(data=json.loads(batch.fail_detail or "[]"))
