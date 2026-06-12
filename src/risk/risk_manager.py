import logging
from decimal import Decimal
from typing import List, Tuple
from src.config import BotConfig
from src.models.trade import Trade
from src.models.signal import Signal
from src.models.enums import SignalStatus

logger = logging.getLogger("trading.risk.risk_manager")

class PortfolioRiskManager:
    """
    Master risk orchestrator. Acts as a circuit breaker for the bot,
    enforcing daily loss limits, drawdown maximums, and exposure caps.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.max_open_positions = config.trading.max_open_positions
        self.daily_loss_limit = Decimal(str(config.trading.daily_loss_limit_usd))
        self.max_drawdown_pct = Decimal(str(config.trading.max_drawdown_pct))

    def check_max_positions(self, active_trades: List[Trade]) -> bool:
        """Ensures the bot does not exceed the maximum allowed concurrent positions."""
        open_count = sum(1 for t in active_trades if t.status == SignalStatus.ACTIVE)
        if open_count >= self.max_open_positions:
            logger.warning(f"Risk Block: Max open positions ({self.max_open_positions}) reached.")
            return False
        return True

    def check_daily_loss_limit(self, realized_pnl_today: Decimal) -> bool:
        """
        Circuit breaker: Halts trading if daily realized losses exceed the configured limit.
        realized_pnl_today should be a negative number if in a loss.
        """
        if realized_pnl_today < Decimal('0.0') and abs(realized_pnl_today) >= self.daily_loss_limit:
            logger.critical(f"CIRCUIT BREAKER: Daily loss limit (${self.daily_loss_limit}) exceeded. Trading halted.")
            return False
        return True

    def check_drawdown_limit(self, peak_equity: Decimal, current_equity: Decimal) -> bool:
        """
        Circuit breaker: Halts trading if the portfolio experiences a severe drawdown.
        """
        if peak_equity <= Decimal('0.0'):
            return True

        current_drawdown_pct = ((peak_equity - current_equity) / peak_equity) * Decimal('100.0')
        
        if current_drawdown_pct >= self.max_drawdown_pct:
            logger.critical(f"CIRCUIT BREAKER: Max drawdown ({self.max_drawdown_pct}%) exceeded. Trading halted.")
            return False
        return True

    def validate_trade_proposal(
        self, 
        signal: Signal, 
        active_trades: List[Trade], 
        realized_pnl_today: Decimal,
        peak_equity: Decimal,
        current_equity: Decimal
    ) -> Tuple[bool, str]:
        """
        Orchestrates all risk checks. Returns (is_approved, reason).
        """
        # 1. Check Drawdown
        if not self.check_drawdown_limit(peak_equity, current_equity):
            return False, "Max Drawdown Limit Reached"

        # 2. Check Daily Loss
        if not self.check_daily_loss_limit(realized_pnl_today):
            return False, "Daily Loss Limit Reached"

        # 3. Check Max Positions
        if not self.check_max_positions(active_trades):
            return False, "Max Open Positions Reached"

        # 4. Check Pair Correlation / Duplication Exposure
        # Do not allow multiple entries into the exact same asset simultaneously
        for trade in active_trades:
            if trade.pair == signal.pair and trade.status == SignalStatus.ACTIVE:
                logger.warning(f"Risk Block: Active position already exists for {signal.pair}.")
                return False, f"Duplicate Exposure on {signal.pair}"

        # 5. Validate Signal Profitability
        if not signal.is_profitable():
            return False, "Risk/Reward Ratio below 1.0"

        return True, "Approved"
