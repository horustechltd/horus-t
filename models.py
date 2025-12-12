# ============================================================
# HORUS ORM MODELS (SQLAlchemy Async)
# ============================================================

from sqlalchemy import Column, String, Float, Boolean, Integer, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


# ------------------------------------------------------------
# CLIENTS TABLE
# ------------------------------------------------------------
class Client(Base):
    __tablename__ = "clients"

    client_id = Column(String, primary_key=True)
    exchange = Column(String, nullable=False)

    api_key = Column(String, nullable=True)
    api_secret = Column(String, nullable=True)
    extra_password = Column(String, nullable=True)

    balance_usdt = Column(Float, default=0)
    allocation = Column(Float, default=10)
    spread_limit = Column(Float, default=1.0)

    active = Column(Boolean, default=True)
    approved = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, server_default=func.now())


# ------------------------------------------------------------
# CAPTAIN SETTINGS
# ------------------------------------------------------------
class CaptainSettings(Base):
    __tablename__ = "captain_settings"

    captain_id = Column(String, primary_key=True)
    commission_percent = Column(Float, default=10)
    spread_limit = Column(Float, default=1.0)
    smart_entry = Column(Boolean, default=True)
    notifications = Column(Boolean, default=True)
    risky_mode = Column(Boolean, default=True)

    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


# ------------------------------------------------------------
# SIGNALS
# ------------------------------------------------------------
class Signal(Base):
    __tablename__ = "signals"

    signal_id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)
    risk_level = Column(String, default="NORMAL")

    status = Column(String, default="PENDING")
    source = Column(String)

    created_at = Column(TIMESTAMP, server_default=func.now())


# ------------------------------------------------------------
# WAVE SIGNALS (Smart Entry)
# ------------------------------------------------------------
class WaveSignal(Base):
    __tablename__ = "wave_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_signal_id = Column(String, ForeignKey("signals.signal_id"))

    wave_id = Column(String, unique=True)
    symbol = Column(String)
    action = Column(String)
    exchange = Column(String)

    wave_index = Column(Integer)
    per_client = Column(JSON)

    status = Column(String, default="READY")
    created_at = Column(TIMESTAMP, server_default=func.now())


# ------------------------------------------------------------
# EXECUTION LOGS
# ------------------------------------------------------------
class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String)
    symbol = Column(String)
    amount = Column(Float)
    price = Column(Float)
    exchange = Column(String)

    status = Column(String)
    reason = Column(String)

    time = Column(TIMESTAMP, server_default=func.now())


# ------------------------------------------------------------
# WAVE LOGS
# ------------------------------------------------------------
class WaveLog(Base):
    __tablename__ = "wave_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange = Column(String)
    symbol = Column(String)
    wave = Column(Integer)
    status = Column(String)
    details = Column(String)

    time = Column(TIMESTAMP, server_default=func.now())


# ------------------------------------------------------------
# SYSTEM LOGS
# ------------------------------------------------------------
class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String)
    level = Column(String)
    message = Column(String)

    time = Column(TIMESTAMP, server_default=func.now())
