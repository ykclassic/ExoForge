import logging
from decimal import Decimal, InvalidOperation
from typing import Optional
from src.models.signal import Signal

logger = logging.getLogger("trading.risk.position_sizing")

class PositionSizer:
    """
    Production-grade position sizing engine utilizing the Kelly Criterion 
    and volatility adjustments for maximum capital preservation.
    """
    
    def __init__(self, fractional_multiplier: Decimal = Decimal('0.25')):
        """
        Initializes the sizer with a fractional multiplier.
        Using a quarter-Kelly (0.25) is an institutional standard to prevent 
        over-leveraging during consecutive drawdowns.
        """
        self.fractional_multiplier = fractional_multiplier

    def calculate_kelly_size(self, win_rate: Decimal, risk_reward_ratio: Decimal) -> Decimal:
        """
        Calculates the base optimal risk percentage using the Kelly Criterion.
        Formula: Kelly % = W - [(1 - W) / R]
        Where W = Win Rate, R = Risk/Reward Ratio.
        """
        if risk_reward_ratio <= 0:
            return Decimal('0.0')

        kelly_pct = win_rate - ((Decimal('1.0') - win_rate) / risk_reward_ratio)
        
        # Apply fractional multiplier for safety, floor at 0 (no negative sizing)
        safe_kelly = max(Decimal('0.0'), kelly_pct * self.fractional_multiplier)
        
        return safe_kelly

    def calculate_volatility_adjusted_size(
        self, 
        base_risk_pct: Decimal, 
        current_atr: Decimal, 
        average_atr: Decimal
    ) -> Decimal:
        """
        Reduces position size in high volatility environments to normalize risk.
        If current ATR > average ATR, the position size is reduced proportionally.
        """
        if current_atr <= 0 or average_atr <= 0:
            return base_risk_pct

        volatility_ratio = average_atr / current_atr
        
        # Only adjust down in high volatility, never scale up beyond base risk
        if volatility_ratio < Decimal('1.0'):
            return base_risk_pct * volatility_ratio
            
        return base_risk_pct

    def determine_trade_size(
        self, 
        account_balance: Decimal, 
        signal: Signal, 
        historical_win_rate: Decimal,
        current_atr: Optional[Decimal] = None,
        average_atr: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculates the final fiat (USD) value to risk on the given signal.
        """
        try:
            rr_ratio = Decimal(str(signal.risk_reward_ratio()))
            
            # 1. Get base risk using Fractional Kelly
            base_risk_pct = self.calculate_kelly_size(historical_win_rate, rr_ratio)
            
            # 2. Adjust for volatility if ATR data is provided
            if current_atr and average_atr:
                final_risk_pct = self.calculate_volatility_adjusted_size(
                    base_risk_pct, current_atr, average_atr
                )
            else:
                final_risk_pct = base_risk_pct

            # 3. Hard cap the maximum risk per trade to 2% of the account balance
            # This is an un-overrideable circuit breaker for capital preservation.
            max_allowed_risk_pct = Decimal('0.02')
            final_risk_pct = min(final_risk_pct, max_allowed_risk_pct)

            risk_amount = account_balance * final_risk_pct
            return risk_amount.quantize(Decimal('0.01'))

        except (InvalidOperation, Exception) as e:
            logger.error(f"Error calculating position size for signal {signal.signal_id}: {str(e)}")
            # Fail-safe: Risk 0 if any mathematical error occurs
            return Decimal('0.0')
