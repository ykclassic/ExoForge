import uuid
import time
import logging
from decimal import Decimal
from typing import Optional, Tuple

from src.execution.exchange_client import GateIOClient
from src.models.signal import Signal
from src.models.trade import Trade
from src.models.order import Order
from src.models.enums import Direction, OrderStatus, SignalStatus

logger = logging.getLogger("trading.execution.order_manager")

class OrderManager:
    """
    Manages the translation of strategy signals into live exchange orders 
    and tracks their execution lifecycle.
    """

    def __init__(self, exchange_client: GateIOClient):
        self.api = exchange_client

    def _determine_api_side(self, direction: Direction) -> str:
        """Translates internal Direction enum to Gate.io API side string."""
        return "buy" if direction == Direction.LONG else "sell"

    async def execute_signal(self, signal: Signal) -> Tuple[Optional[Trade], Optional[Order]]:
        """
        Attempts to execute an entry order based on an approved signal.
        Returns the resulting Trade and Order objects if successful.
        """
        try:
            if signal.position_size <= Decimal('0.0'):
                logger.error(f"Cannot execute signal {signal.signal_id}: Position size is zero.")
                return None, None

            api_side = self._determine_api_side(signal.direction)
            pair_formatted = signal.pair.upper()  # Ensure format is e.g., "BTC_USDT"
            
            # Format quantity to standard exchange precision (e.g., 8 decimals)
            qty_str = str(signal.position_size.quantize(Decimal('0.00000001')))
            
            timestamp_sent = int(time.time() * 1000)
            
            # Execute Market Order via API
            response = await self.api.create_order(
                currency_pair=pair_formatted,
                side=api_side,
                amount=qty_str,
                order_type="market"
            )

            # Parse the Exchange Response
            exchange_order_id = response.get("id", str(uuid.uuid4()))
            fill_price_str = response.get("fill_price", str(signal.entry_price))
            status_str = response.get("status", "closed")
            
            fill_price = Decimal(fill_price_str)
            order_status = OrderStatus.FILLED if status_str == "closed" else OrderStatus.PARTIAL

            # Create the internal Order record
            trade_id = str(uuid.uuid4())
            new_order = Order(
                order_id=exchange_order_id,
                trade_id=trade_id,
                pair=signal.pair,
                direction=signal.direction,
                order_type="MARKET",
                quantity=signal.position_size,
                price=signal.entry_price,
                status=order_status,
                timestamp_sent=timestamp_sent,
                timestamp_filled=int(time.time() * 1000) if order_status == OrderStatus.FILLED else None,
                fill_price=fill_price,
                fill_quantity=signal.position_size,
                error_message=None
            )

            # Initialize the Trade Tracker
            slippage = abs(fill_price - signal.entry_price)
            
            new_trade = Trade(
                trade_id=trade_id,
                signal_id=signal.signal_id,
                pair=signal.pair,
                direction=signal.direction,
                entry_price=fill_price,  # Use actual fill price, not theoretical signal price
                entry_timestamp=new_order.timestamp_filled or timestamp_sent,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
                position_size=signal.position_size,
                status=SignalStatus.ACTIVE,
                slippage=slippage
            )

            logger.info(f"Successfully executed trade {trade_id} for signal {signal.signal_id}. Fill Price: {fill_price}")
            return new_trade, new_order

        except Exception as e:
            logger.error(f"Failed to execute signal {signal.signal_id}: {str(e)}")
            return None, None

    async def exit_trade(self, trade: Trade, exit_reason: str) -> Optional[Order]:
        """
        Executes a market order to close an active trade.
        """
        try:
            # To close a LONG, we SELL. To close a SHORT, we BUY.
            exit_side = "sell" if trade.direction == Direction.LONG else "buy"
            qty_str = str(trade.position_size.quantize(Decimal('0.00000001')))
            
            response = await self.api.create_order(
                currency_pair=trade.pair.upper(),
                side=exit_side,
                amount=qty_str,
                order_type="market"
            )

            exchange_order_id = response.get("id", str(uuid.uuid4()))
            fill_price_str = response.get("fill_price", "0")
            
            closing_order = Order(
                order_id=exchange_order_id,
                trade_id=trade.trade_id,
                pair=trade.pair,
                direction=Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG,
                order_type="MARKET",
                quantity=trade.position_size,
                price=Decimal(fill_price_str),
                status=OrderStatus.FILLED,
                timestamp_sent=int(time.time() * 1000),
                timestamp_filled=int(time.time() * 1000),
                fill_price=Decimal(fill_price_str),
                fill_quantity=trade.position_size
            )
            
            logger.info(f"Trade {trade.trade_id} closed via {exit_reason} at {fill_price_str}")
            return closing_order

        except Exception as e:
            logger.error(f"Critical error closing trade {trade.trade_id}: {str(e)}")
            return None
