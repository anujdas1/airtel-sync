"""
db.py — SQLAlchemy models and database setup for Accel SYNC.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Generator

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./accel_sync.db")

# SQLite-specific: allow cross-thread usage
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=True)
    business_name = Column(String(256), nullable=True)
    business_type = Column(String(128), nullable=True)
    segment = Column(String(64), nullable=True)   # micro / prof / multi / mfg
    city = Column(String(128), nullable=True)
    city_tier = Column(Integer, nullable=True)    # 1 or 2
    state = Column(String(128), nullable=True)
    language = Column(String(64), nullable=True)
    employee_count = Column(Integer, nullable=True)
    num_sites = Column(Integer, nullable=True)
    has_gstin = Column(Boolean, nullable=True)
    gstin = Column(String(16), nullable=True)
    has_udyam = Column(Boolean, nullable=True)
    udyam_number = Column(String(32), nullable=True)
    monthly_spend = Column(Float, nullable=True)
    products_of_interest = Column(Text, nullable=True)   # semicolon-separated product IDs
    contact_name = Column(String(256), nullable=True)
    contact_role = Column(String(128), nullable=True)
    stage_reached = Column(String(64), default="advisor")
    outcome = Column(String(64), default="In Progress")
    drop_reason = Column(Text, nullable=True)
    propensity_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    order_ref = Column(String(32), unique=True, index=True, nullable=False)
    bundle_products = Column(Text, nullable=True)        # JSON string
    monthly_total = Column(Float, nullable=True)
    setup_fee = Column(Float, nullable=True)
    contract_months = Column(Integer, nullable=True)
    status = Column(String(64), default="Order Placed")
    kyc_status = Column(String(32), default="Pending")
    scheduled_activation_date = Column(DateTime, nullable=True)
    estimated_activation_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KYCSubmission(Base):
    __tablename__ = "kyc_submissions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    gstin_extracted = Column(String(16), nullable=True)
    udyam_extracted = Column(String(32), nullable=True)
    name_extracted = Column(String(256), nullable=True)
    address_extracted = Column(Text, nullable=True)
    doc_date_extracted = Column(String(32), nullable=True)
    gstin_valid = Column(Boolean, nullable=True)
    udyam_valid = Column(Boolean, nullable=True)
    name_match = Column(Boolean, nullable=True)
    address_valid = Column(Boolean, nullable=True)
    issues = Column(Text, nullable=True)             # JSON list string
    result = Column(String(16), nullable=True)       # APPROVED / FLAGGED / REJECTED
    consent_given_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    purpose = Column(String(64), nullable=False)  # identity_verification / marketing / channel_partner
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_tables() -> None:
    """Create all tables (called at startup)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Convenience type alias for Annotated dependency injection
DbSession = Annotated[Session, None]
