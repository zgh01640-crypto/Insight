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
    import_batch_id: Optional[int] = Field(default=None, foreign_key="import_batch.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── ConversationSession ───────────────────────────────
class ConversationSession(SQLModel, table=True):
    __tablename__ = "conversation_session"
    id: str = Field(primary_key=True)            # uuid[:8]
    title: str = Field(max_length=100)           # 取首条用户消息前20字
    model_id: str = Field(max_length=30)
    year: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── ConversationMessage ───────────────────────────────
class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_message"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="conversation_session.id")
    role: str        # user / assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


# ── AIReport ─────────────────────────────────────────
class AIReport(SQLModel, table=True):
    __tablename__ = "ai_report"
    id:         Optional[int] = Field(default=None, primary_key=True)
    year:       int
    title:      str = Field(max_length=100)
    content:    str                          # Markdown 正文
    model_id:   str = Field(max_length=30)  # deepseek/kimi/glm/claude
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TargetChangeLog(SQLModel, table=True):
    __tablename__ = "target_change_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    annual_target_id: int = Field(foreign_key="annual_target.id")
    old_amount: float
    new_amount: float
    changed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Product ───────────────────────────────────────────
class Product(SQLModel, table=True):
    __tablename__ = "product"
    id:               Optional[int] = Field(default=None, primary_key=True)
    business_unit_id: int = Field(foreign_key="business_unit.id")
    name:             str = Field(max_length=200)
    status:           str = Field(default="立项中")   # 立项中/开发中/测试中/已上线/已暂停/已终止
    initiated_at:     Optional[date] = None
    product_manager:  Optional[str] = Field(default=None, max_length=100)
    tech_support:     Optional[str] = Field(default=None, max_length=200)
    dev_members:      Optional[str] = None             # 逗号分隔文本
    progress:         Optional[str] = None             # 最新进展（覆盖式）
    risk:             Optional[str] = None             # 最新风险（覆盖式）
    notes:            Optional[str] = None
    created_at:       datetime = Field(default_factory=datetime.utcnow)
    updated_at:       datetime = Field(default_factory=datetime.utcnow)


class ProductMilestone(SQLModel, table=True):
    __tablename__ = "product_milestone"
    id:           Optional[int] = Field(default=None, primary_key=True)
    product_id:   int = Field(foreign_key="product.id")
    name:         str = Field(max_length=200)
    planned_date: Optional[date] = None
    actual_date:  Optional[date] = None
    status:       str = Field(default="未开始")   # 未开始/进行中/已完成/延期
    sort_order:   int = Field(default=0)


class ProductAttachment(SQLModel, table=True):
    __tablename__ = "product_attachment"
    id:           Optional[int] = Field(default=None, primary_key=True)
    product_id:   int = Field(foreign_key="product.id")
    filename:     str = Field(max_length=500)    # 原始文件名
    stored_path:  str                            # 服务器磁盘路径
    file_size:    int = Field(default=0)         # 字节数
    uploaded_at:  datetime = Field(default_factory=datetime.utcnow)


# ── MemoryItem ────────────────────────────────────────
class MemoryItem(SQLModel, table=True):
    __tablename__ = "memory_item"
    id:         Optional[int] = Field(default=None, primary_key=True)
    category:   str = Field(max_length=50)   # 偏好 / 项目 / 人物 / 数据 / 其他
    content:    str                          # LLM 提炼后的简洁记忆正文
    source:     str = Field(max_length=20, default="user_command")  # user_command / auto_extract
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class CollectionItem(SQLModel, table=True):
    __tablename__ = "collection_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    year: int
    business_unit_id: int = Field(foreign_key="business_unit.id")
    project_name: str = Field(max_length=200)        # 项目名称
    client_name: str = Field(max_length=200)         # 单位名称
    amount: float = Field(default=0.0)               # 欠款金额（万元）
    status: str = Field(default="催收中")             # 催收中 / 已回款 / 已核销
    notes: Optional[str] = None
    import_batch_id: Optional[int] = Field(default=None, foreign_key="import_batch.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
