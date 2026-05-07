from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Any = None


# ── Targets ──────────────────────────────────────────
class TargetItem(BaseModel):
    business_unit_id: int
    business_unit_name: str
    metric_type: str
    target_amount: float
    monthly_targets: List[float] = []  # index 0=Jan ... 11=Dec


class TargetUpdateItem(BaseModel):
    business_unit_id: int
    metric_type: str
    target_amount: float
    monthly_targets: Optional[List[float]] = None


class TargetBatchUpdate(BaseModel):
    year: int
    items: List[TargetUpdateItem]


# ── Actuals ──────────────────────────────────────────
class ActualItem(BaseModel):
    year: int
    month: int
    business_unit_id: int
    business_unit_name: str
    metric_type: str
    actual_amount: float
    updated_at: datetime


# ── Opportunity ──────────────────────────────────────
class OpportunityCreate(BaseModel):
    name: str
    business_unit_id: int
    metric_type: str
    year: int
    quarter: str
    estimated_amount: float
    estimated_date: Optional[date] = None
    stage: str = "线索"
    status: str = "进行中"
    notes: Optional[str] = None


class OpportunityUpdate(OpportunityCreate):
    pass


class OpportunityRead(OpportunityCreate):
    id: int
    business_unit_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Dashboard: Overview ──────────────────────────────
class DivisionMetricSummary(BaseModel):
    business_unit_id: int
    business_unit_name: str
    metric_type: str
    ytd_actual: float
    ytd_target: float
    rate: float          # ytd_actual / ytd_target * 100
    annual_target: float
    prev_ytd_actual: float
    yoy_rate: Optional[float]  # growth % vs same period last year


class OverviewResponse(BaseModel):
    year: int
    cur_month: int
    summaries: List[DivisionMetricSummary]


# ── Dashboard: Division Detail ────────────────────────
class DivisionDetailResponse(BaseModel):
    business_unit_id: int
    business_unit_name: str
    year: int
    metrics: dict  # { contract: {...}, revenue: {...}, payment: {...} }


# ── Dashboard: Opportunity Support ───────────────────
class FunnelStage(BaseModel):
    stage: str
    count: int
    total_amount: float


class OppSupportResponse(BaseModel):
    year: int
    contract_gap: float
    opp_active_total: float
    cover_rate: float
    funnel: List[FunnelStage]
    quarterly: dict   # { Q1: { div: amount, ... }, ... }


# ── Import ───────────────────────────────────────────
class ImportHistoryItem(BaseModel):
    id: int
    import_type: str
    filename: str
    total_rows: int
    success_rows: int
    fail_rows: int
    fail_detail: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Collection Item ──────────────────────────────────
class CollectionCreate(BaseModel):
    year: int
    business_unit_id: int
    project_name: str
    client_name: str
    amount: float
    status: str = "催收中"
    notes: Optional[str] = None


class CollectionUpdate(CollectionCreate):
    pass


class CollectionRead(CollectionCreate):
    id: int
    business_unit_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Product ──────────────────────────────────────────
class MilestoneCreate(BaseModel):
    name: str
    planned_date: Optional[date] = None
    actual_date: Optional[date] = None
    status: str = "未开始"
    sort_order: int = 0


class MilestoneRead(MilestoneCreate):
    id: int
    product_id: int

    class Config:
        from_attributes = True


class AttachmentRead(BaseModel):
    id: int
    product_id: int
    filename: str
    file_size: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    business_unit_id: int
    name: str
    status: str = "立项中"
    initiated_at: Optional[date] = None
    product_manager: Optional[str] = None
    tech_support: Optional[str] = None
    dev_members: Optional[str] = None
    progress: Optional[str] = None
    risk: Optional[str] = None
    notes: Optional[str] = None


class ProductUpdate(ProductCreate):
    pass


class ProductRead(ProductCreate):
    id: int
    business_unit_name: str
    milestones: List[MilestoneRead] = []
    attachments: List[AttachmentRead] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
