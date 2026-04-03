from sqlmodel import Session, create_engine, select, SQLModel, delete
from models import BusinessUnit, AnnualTarget, MonthlyTarget, MonthlyActual, Opportunity, ImportBatch, AIReport, TargetChangeLog

import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./insight.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SEED_UNITS = [
    {"code": "JZJZ", "name": "智能建造事业部", "sort_order": 1},
    {"code": "DSJS", "name": "大数据事业部",   "sort_order": 2},
    {"code": "SZJY", "name": "数字交易事业部", "sort_order": 3},
    {"code": "ZHZW", "name": "智慧政务事业部", "sort_order": 4},
]


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # 清理不在 SEED_UNITS 中的事业部及其关联数据
        seed_codes = {u["code"] for u in SEED_UNITS}
        removed = session.exec(
            select(BusinessUnit).where(BusinessUnit.code.not_in(seed_codes))
        ).all()
        for unit in removed:
            at_ids = [
                r.id for r in session.exec(
                    select(AnnualTarget).where(AnnualTarget.business_unit_id == unit.id)
                ).all()
            ]
            if at_ids:
                session.exec(delete(MonthlyTarget).where(MonthlyTarget.annual_target_id.in_(at_ids)))
                session.exec(delete(AnnualTarget).where(AnnualTarget.business_unit_id == unit.id))
            session.exec(delete(MonthlyActual).where(MonthlyActual.business_unit_id == unit.id))
            session.exec(delete(Opportunity).where(Opportunity.business_unit_id == unit.id))
            session.delete(unit)

        # 新增种子数据（幂等）
        for u in SEED_UNITS:
            exists = session.exec(
                select(BusinessUnit).where(BusinessUnit.code == u["code"])
            ).first()
            if not exists:
                session.add(BusinessUnit(**u))
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session
