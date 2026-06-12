from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class DBMarketRegime(enum.Enum):
    RANGING = "RANGING"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    UNKNOWN = "UNKNOWN"

class DBDirection(enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class DBSignal(Base):
    __tablename__ = 'signals'
    id = Column(String, primary_key=True)
    timestamp = Column(Integer, nullable=False)
    pair = Column(String(20), index=True, nullable=False)
    direction = Column(SQLEnum(DBDirection), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=False)
    stop_loss = Column(Numeric(18, 8), nullable=False)
    take_profit_1 = Column(Numeric(18, 8), nullable=False)
    take_profit_2 = Column(Numeric(18, 8), nullable=False)
    confidence = Column(Numeric(4, 3))
    market_regime = Column(SQLEnum(DBMarketRegime))
    position_size = Column(Numeric(18, 8))
    risk_amount = Column(Numeric(18, 2))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DBTrade(Base):
    __tablename__ = 'trades'
    id = Column(String, primary_key=True)
    signal_id = Column(String, ForeignKey('signals.id'), nullable=False)
    pair = Column(String(20), index=True, nullable=False)
    direction = Column(SQLEnum(DBDirection), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=False)
    entry_timestamp = Column(Integer, nullable=False)
    status = Column(String(20), index=True, nullable=False)
    exit_price = Column(Numeric(18, 8))
    exit_timestamp = Column(Integer)
    pnl = Column(Numeric(18, 2))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class DBOrder(Base):
    __tablename__ = 'orders'
    id = Column(String, primary_key=True)
    trade_id = Column(String, ForeignKey('trades.id'), nullable=False)
    pair = Column(String(20), nullable=False)
    order_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    price = Column(Numeric(18, 8), nullable=False)
    status = Column(String(20), nullable=False)
    timestamp_sent = Column(Integer, nullable=False)
    timestamp_filled = Column(Integer)
