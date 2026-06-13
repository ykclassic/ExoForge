import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from src.config import EnvironmentConfig
from src.data.schema import Base, DBSignal, DBTrade, DBOrder
from src.models.signal import Signal
from src.models.trade import Trade
from src.models.order import Order

logger = logging.getLogger("trading.data.database")

class DatabaseClient:
    """
    Production-grade asynchronous PostgreSQL interface for Supabase.
    Configured for compatibility with PgBouncer (Transaction Pooler).
    """

    def __init__(self, config: EnvironmentConfig):
        db_url = config.SUPABASE_DB_URL
        # Ensure connection string is formatted for asyncpg
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # CRITICAL FIX: statement_cache_size=0 for PgBouncer compatibility
        self.engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_recycle=300,
            pool_pre_ping=True,
            connect_args={"statement_cache_size": 0} 
        )
        self.AsyncSessionLocal = async_sessionmaker(
            bind=self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def initialize_schema(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized successfully.")
        except SQLAlchemyError as e:
            logger.critical(f"Failed to initialize database schema: {str(e)}")
            raise

    async def save_signal(self, signal: Signal) -> bool:
        async with self.AsyncSessionLocal() as session:
            try:
                db_signal = DBSignal(
                    id=signal.signal_id,
                    timestamp=signal.timestamp,
                    pair=signal.pair,
                    direction=signal.direction.name,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit_1=signal.take_profit_1,
                    take_profit_2=signal.take_profit_2,
                    confidence=signal.confidence,
                    market_regime=signal.market_regime.name,
                    position_size=signal.position_size,
                    risk_amount=signal.risk_amount,
                    notes=signal.notes
                )
                session.add(db_signal)
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to save signal {signal.signal_id}: {str(e)}")
                return False

    async def save_trade(self, trade: Trade) -> bool:
        async with self.AsyncSessionLocal() as session:
            try:
                db_trade = DBTrade(
                    id=trade.trade_id,
                    signal_id=trade.signal_id,
                    pair=trade.pair,
                    direction=trade.direction.name,
                    entry_price=trade.entry_price,
                    entry_timestamp=trade.entry_timestamp,
                    status=trade.status.name
                )
                session.add(db_trade)
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to save trade {trade.trade_id}: {str(e)}")
                return False

    async def update_trade(self, trade: Trade) -> bool:
        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(select(DBTrade).where(DBTrade.id == trade.trade_id))
                db_trade = result.scalar_one_or_none()
                if db_trade:
                    db_trade.status = trade.status.name
                    db_trade.exit_price = trade.exit_price
                    db_trade.exit_timestamp = trade.exit_timestamp
                    db_trade.pnl = trade.pnl
                    await session.commit()
                    return True
                return False
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to update trade {trade.trade_id}: {str(e)}")
                return False

    async def save_order(self, order: Order) -> bool:
        async with self.AsyncSessionLocal() as session:
            try:
                db_order = DBOrder(
                    id=order.order_id,
                    trade_id=order.trade_id,
                    pair=order.pair,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price,
                    status=order.status.name,
                    timestamp_sent=order.timestamp_sent,
                    timestamp_filled=order.timestamp_filled
                )
                session.add(db_order)
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Failed to save order {order.order_id}: {str(e)}")
                return False

    async def close(self):
        await self.engine.dispose()
