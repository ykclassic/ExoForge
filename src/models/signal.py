from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import List
from .enums import Direction, MarketRegime

@dataclass(frozen=True)
class Signal:
    signal_id: str
    timestamp: int
    pair: str
    direction: Direction
    entry_price: Decimal
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal
    confidence: float
    indicators_triggered: List[str]
    market_regime: MarketRegime
    position_size: Decimal
    risk_amount: Decimal
    notes: str

    def validate_prices(self) -> None:
        if self.direction == Direction.LONG:
            if not (self.stop_loss < self.entry_price < self.take_profit_1 < self.take_profit_2):
                raise ValueError("Invalid LONG signal prices.")
        elif self.direction == Direction.SHORT:
            if not (self.stop_loss > self.entry_price > self.take_profit_1 > self.take_profit_2):
                raise ValueError("Invalid SHORT signal prices.")

    def risk_reward_ratio(self) -> float:
        risk = abs(float(self.entry_price - self.stop_loss))
        reward = abs(float(self.take_profit_1 - self.entry_price))
        return reward / risk if risk > 0 else 0.0

    def is_profitable(self) -> bool:
        return self.risk_reward_ratio() >= 1.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data['direction'] = self.direction.name
        data['market_regime'] = self.market_regime.name
        for key in ['entry_price', 'stop_loss', 'take_profit_1', 'take_profit_2', 'position_size', 'risk_amount']:
            data[key] = str(data[key])
        return data
