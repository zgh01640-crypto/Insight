from typing import Optional
from datetime import date, datetime
from sqlmodel import Field, SQLModel, JSON, Column
import sqlalchemy as sa


# ── BusinessUnit ─────────────────────────────────────
class BusinessUnit(SQLModel, table=True):
    __tablename__ = "business_unit"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    code: str = Field(max_length=10, unique=True)
    sort_order: int = Field(default=0)


# ── AnnualTarget ─────────────────────────────────────
class AnnualTarget(SQLModel, table=True):
    __tablename__ = "annual_target"
    __table_args__ = (
        sa.UniqueConstraint("year", "business_unit_id", "metric_type"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    year: int
    business_unit_id: int = Field(foreign_key="business_unit.id")
    metric_type: str  # contract / revenue / payment
    target_amount: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── MonthlyTarget ─────────────────────────────────────
class MonthlyTarget(SQLModel, table=True):
    __tablename__ = "monthly_target"
    __table_args__ = (
        sa.UniqueConstraint("annual_target_id", "month"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    annual_target_id: int = Field(foreign_key="annual_target.id")
    month: int  # 1-12
    target_amount: float = Field(default=0.0)


# ── MonthlyActual ─────────────────────────────────────
class MonthlyActual(SQLModel, table=True):
    __tablename__ = "monthly_actual"
    __table_args__ = (
        sa.UniqueConstraint("year", "month", "business_unit_id", "metric_type"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    year: int
    month: int
    business_unit_id: int = Field(foreign_key="business_unit.id")
    metric_type: str
    actual_amount: float = Field(default=0.0)
    import_batch_id: Optional[int] = Field(default=None, foreign_key="import_batch.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Opportunity ───────────────────────────────────────
class Opportunity(SQLModel, table=True):
    __tablename__ = "opportunity"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    business_unit_id: int = Field(foreign_key="business_unit.id")
    metric_type: str  # contract / revenue / payment
    year: int
    quarter: str  # Q1 / Q2 / Q3 / Q4
    estimated_amount: float = Field(default=0.0)
    estimated_date: Optional[date] = None
    stage: str = Field(default="线索")   # 线索/立项/报价/签约跟进/已完成
    status: str = Field(default="进行中") # 进行中/已赢单/已输单/已搁置
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── ImportBatch ───────────────────────────────────────
class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batch"
    id: Optional[int] = Field(default=None, primary_key=True)
    import_type: str  # annual_target / monthly_actual / opportunity
    filename: str
    total_rows: int = Field(default=0)
    success_rows: int = Field(default=0)
    fail_rows: int = Field(default=0)
    fail_detail: Optional[str] = Field(default="[]")  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── TargetChangeLog ───────────────────────────────────
class TargetChangeLog(SQLModel, table=True):
    __tablename__ = "target_change_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    annual_target_id: int = Field(foreign_key="annual_target.id")
    old_amount: float
    new_amount: float
    changed_at: datetime = Field(default_factory=datetime.utcnow)
