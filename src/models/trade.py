from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional, Tuple
from .enums import Direction, SignalStatus

@dataclass(frozen=True)
class Trade:
    trade_id: str
    signal_id: str
    pair: str
    direction: Direction
    entry_price: Decimal
    entry_timestamp: int
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal
    position_size: Decimal
    status: SignalStatus
    exit_price: Optional[Decimal] = None
    exit_timestamp: Optional[int] = None
    exit_type: Optional[str] = None
    pnl: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    slippage: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    hold_time_minutes: Optional[int] = None

    def calculate_pnl(self, current_price: Decimal) -> Tuple[Decimal, Decimal]:
        if self.direction == Direction.LONG:
            pnl = (current_price - self.entry_price) * self.position_size
            pnl_percent = ((current_price - self.entry_price) / self.entry_price) * Decimal('100')
        else:
            pnl = (self.entry_price - current_price) * self.position_size
            pnl_percent = ((self.entry_price - current_price) / self.entry_price) * Decimal('100')
        return pnl, pnl_percent

    def is_active(self) -> bool:
        return self.status == SignalStatus.ACTIVE

    def to_dict(self) -> dict:
        data = asdict(self)
        data['direction'] = self.direction.name
        data['status'] = self.status.name
        # Convert Decimals to strings for JSON serialization
        for key, value in data.items():
            if isinstance(value, Decimal):
                data[key] = str(value)
        return data
