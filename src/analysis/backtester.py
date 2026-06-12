import logging
from decimal import Decimal
from typing import List, Dict
import pandas as pd
from src.models.trade import Trade
from src.models.signal import Signal
from src.models.enums import SignalStatus, Direction

logger = logging.getLogger("trading.analysis.backtester")

class Backtester:
    """
    Asynchronous historical simulation engine.
    Calculates PnL, Win-Rate, and Drawdown based on historical price series.
    """
    
    def __init__(self, initial_balance: Decimal = Decimal('10000.0'), commission_pct: Decimal = Decimal('0.001')):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_pct = commission_pct
        self.trades: List[Trade] = []
        self.equity_curve: List[Decimal] = [initial_balance]

    def run_simulation(self, df: pd.DataFrame, signals: List[Signal]) -> Dict:
        """
        Simulates trading based on a list of pre-generated signals.
        Requires a DataFrame containing price data and the list of signals.
        """
        logger.info(f"Starting backtest with {len(signals)} signals.")
        
        for signal in signals:
            # Simulate execution cost (commission)
            entry_cost = signal.position_size * signal.entry_price * self.commission_pct
            self.balance -= entry_cost
            
            # Find exit based on SL or TP (simplified simulation)
            # In a production backtest, we loop through price history after signal.timestamp
            exit_price, exit_type, pnl = self._simulate_trade_exit(df, signal)
            
            # Record trade
            trade = Trade(
                trade_id=f"BT_{signal.signal_id}",
                signal_id=signal.signal_id,
                pair=signal.pair,
                direction=signal.direction,
                entry_price=signal.entry_price,
                entry_timestamp=signal.timestamp,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
                position_size=signal.position_size,
                status=SignalStatus.WON_TP1 if pnl > 0 else SignalStatus.STOPPED_OUT,
                exit_price=exit_price,
                pnl=pnl
            )
            
            self.balance += pnl
            self.trades.append(trade)
            self.equity_curve.append(self.balance)
            
        return self._calculate_metrics()

    def _simulate_trade_exit(self, df: pd.DataFrame, signal: Signal):
        """Internal logic to simulate exit based on price movement post-entry."""
        # Logic: Slice df from signal.timestamp, find first hit of SL or TP
        # This implementation assumes TP1 is the target for simplicity in the base model
        if signal.direction == Direction.LONG:
            is_win = df.loc[df.index > signal.timestamp, 'high'].max() >= signal.take_profit_1
            exit_price = signal.take_profit_1 if is_win else signal.stop_loss
            pnl = (exit_price - signal.entry_price) * signal.position_size
        else:
            is_win = df.loc[df.index > signal.timestamp, 'low'].min() <= signal.take_profit_1
            exit_price = signal.take_profit_1 if is_win else signal.stop_loss
            pnl = (signal.entry_price - exit_price) * signal.position_size
            
        return exit
