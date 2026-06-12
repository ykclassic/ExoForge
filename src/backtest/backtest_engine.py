import logging
from decimal import Decimal
from typing import List, Dict, Optional
import pandas as pd

from src.models.trade import Trade
from src.models.signal import Signal
from src.models.enums import SignalStatus, Direction

logger = logging.getLogger("trading.backtest.engine")

class BacktestEngine:
    """
    Complete backtesting system with historical data replay and chronological step-forward analysis.
    Eliminates lookahead bias by evaluating price action sequentially.
    """
    
    def __init__(self, initial_balance: Decimal = Decimal('10000.0'), commission_pct: Decimal = Decimal('0.001')):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_pct = commission_pct
        self.trades: List[Trade] = []
        self.equity_curve: List[Decimal] = [initial_balance]

    def run_simulation(self, df: pd.DataFrame, signals: List[Signal]) -> Dict:
        """
        Executes the walk-forward simulation chronologically.
        """
        logger.info(f"Initiating walk-forward backtest engine with {len(signals)} signals.")
        
        # Sort signals chronologically
        signals = sorted(signals, key=lambda x: x.timestamp)
        
        for signal in signals:
            # Filter forward price action strictly after the signal timestamp
            future_df = df.loc[df.index > signal.timestamp]
            if future_df.empty:
                continue

            # Apply execution cost (simulated slippage/commission)
            entry_cost = signal.position_size * signal.entry_price * self.commission_pct
            self.balance -= entry_cost
            
            exit_price, exit_type, pnl = self._evaluate_trade_chronologically(future_df, signal)
            
            # Record the resolved trade
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

    def _evaluate_trade_chronologically(self, future_df: pd.DataFrame, signal: Signal) -> tuple[Decimal, str, Decimal]:
        """
        Steps through the dataframe bar-by-bar to ensure SL and TP are evaluated 
        without intrabar lookahead bias.
        """
        for index, row in future_df.iterrows():
            high = Decimal(str(row['high']))
            low = Decimal(str(row['low']))

            if signal.direction == Direction.LONG:
                # Check SL first (pessimistic execution assumes SL is hit before TP in the same bar)
                if low <= signal.stop_loss:
                    pnl = (signal.stop_loss - signal.entry_price) * signal.position_size
                    return signal.stop_loss, "SL", pnl
                if high >= signal.take_profit_1:
                    pnl = (signal.take_profit_1 - signal.entry_price) * signal.position_size
                    return signal.take_profit_1, "TP1", pnl
            else:
                # SHORT evaluation
                if high >= signal.stop_loss:
                    pnl = (signal.entry_price - signal.stop_loss) * signal.position_size
                    return signal.stop_loss, "SL", pnl
                if low <= signal.take_profit_1:
                    pnl = (signal.entry_price - signal.take_profit_1) * signal.position_size
                    return signal.take_profit_1, "TP1", pnl

        # If loop exhausts without hitting SL/TP, close at final available price (Time Exit)
        final_close = Decimal(str(future_df.iloc[-1]['close']))
        if signal.direction == Direction.LONG:
            pnl = (final_close - signal.entry_price) * signal.position_size
        else:
            pnl = (signal.entry_price - final_close) * signal.position_size
            
        return final_close, "TIME_EXIT", pnl

    def _calculate_metrics(self) -> Dict:
        """Computes performance statistics."""
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.pnl > Decimal('0.0'))
        win_rate = (wins / total_trades) if total_trades > 0 else 0.0
        total_pnl = sum(t.pnl for t in self.trades)
        
        peak = self.initial_balance
        max_dd = Decimal('0.0')
        for val in self.equity_curve:
            if val > peak: 
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd: 
                max_dd = dd
                
        return {
            "total_trades": total_trades,
            "win_rate": float(win_rate),
            "total_pnl": float(total_pnl),
            "final_balance": float(self.balance),
            "max_drawdown_pct": float(max_dd * Decimal('100.0'))
        }
