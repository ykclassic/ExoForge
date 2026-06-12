from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional
from .enums import Direction, OrderStatus

@dataclass(frozen=True)
class Order:
    order_id: str
    trade_id: str
    pair: str
    direction: Direction
    order_type: str
    quantity: Decimal
    price: Decimal
    status: OrderStatus
    timestamp_sent: int
    timestamp_filled: Optional[int] = None
    fill_price: Optional[Decimal] = None
    fill_quantity: Optional[Decimal] = None
    error_message: Optional[str] = None

    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    def time_to_fill(self) -> int:
        if self.timestamp_filled and self.timestamp_sent:
            return self.timestamp_filled - self.timestamp_sent
        return 0
