from sqlmodel import Session, create_engine, select, SQLModel
from models import BusinessUnit

import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./insight.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SEED_UNITS = [
    {"code": "JZJZ", "name": "智能建造事业部", "sort_order": 1},
    {"code": "DSJS", "name": "大数据事业部",   "sort_order": 2},
    {"code": "SZJY", "name": "数字交易事业部", "sort_order": 3},
    {"code": "ZHZW", "name": "智慧政务事业部", "sort_order": 4},
    {"code": "CXYW", "name": "创新业务事业部", "sort_order": 5},
]


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
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
