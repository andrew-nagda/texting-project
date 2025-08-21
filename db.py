# db.py
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON  # falls back to JSON on SQLite
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

JsonType = JSONB if "postgresql" in DATABASE_URL else JSON

class User(Base):
    __tablename__ = "users"
    phone = Column(String, primary_key=True)
    name = Column(String, default="")
    track = Column(String, default="Consulting")
    per_day = Column(Integer, default=1)
    timezone = Column(String, default="America/New_York")
    subscribed = Column(Boolean, default=True)
    open = Column(JsonType)       # payload for current open question
    stats = Column(JsonType)      # {"asked":..,"correct":..,"streak":..}
    schedule = Column(JsonType)   # {"local_date":..,"remaining_utc":[...]}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)

def get_or_create(phone, defaults):
    with SessionLocal() as s:
        u = s.get(User, phone)
        if not u:
            u = User(phone=phone, **defaults)
            s.add(u); s.commit()
        return u

def save(user):
    with SessionLocal() as s:
        s.merge(user); s.commit()
        return user
