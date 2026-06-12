import uuid
import time
import logging
from decimal import Decimal
import pandas as pd
from typing import Optional

from src.models.signal import Signal
from src.models.enums import Direction, MarketRegime
from src.strategy.indicators import TechnicalIndicators

logger = logging.getLogger("trading.strategy.generator")

class SignalGenerator:
    """
    Multi-timeframe confluence engine.
    Requires alignment across 4H, 1H, and 15M charts before generating a valid signal.
    """

    def __init__(self):
        self.indicators = TechnicalIndicators()

    def _determine_market_regime(self, df_4h: pd.DataFrame) -> MarketRegime:
        """Determines the macro market regime using the 4H timeframe."""
        latest = df_4h.iloc[-1]
        
        # Trend detection via EMA 50/200 cross and MACD position
        if latest['EMA_50'] > latest['EMA_200'] and latest['MACD_line'] > 0:
            return MarketRegime.TRENDING_UP
        elif latest['EMA_50'] < latest['EMA_200'] and latest['MACD_line'] < 0:
            return MarketRegime.TRENDING_DOWN
        else:
            return MarketRegime.RANGING

    def analyze_confluence(
        self, 
        pair: str, 
        df_4h: pd.DataFrame, 
        df_1h: pd.DataFrame, 
        df_15m: pd.DataFrame
    ) -> Optional[Signal]:
        """
        Evaluates indicator confluence across three timeframes.
        Returns a populated Signal dataclass if entry criteria are met.
        """
        try:
            # 1. Apply indicators to all dataframes
            df_4h = self.indicators.apply_all_indicators(df_4h)
            df_1h = self.indicators.apply_all_indicators(df_1h)
            df_15m = self.indicators.apply_all_indicators(df_15m)

            # Get the most recently closed candles
            curr_4h = df_4h.iloc[-1]
            curr_1h = df_1h.iloc[-1]
            curr_15m = df_15m.iloc[-1]

            regime = self._determine_market_regime(df_4h)
            atr_15m = curr_15m['ATR_14']
            current_price = curr_15m['close']

            if pd.isna(atr_15m) or atr_15m <= 0:
                logger.warning(f"Invalid ATR calculation for {pair}. Aborting signal generation.")
                return None

            direction = None
            triggered_indicators = []
            confidence = 0.0

            # -------------------------------------------------------------
            # LONG CONFLUENCE LOGIC
            # 4H: Trending Up
            # 1H: MACD Bullish Crossover & RSI > 50 (Momentum shift)
            # 15M: Price touching/crossing lower Bollinger Band (Value entry)
            # -------------------------------------------------------------
            if regime == MarketRegime.TRENDING_UP:
                if curr_1h['MACD_line'] > curr_1h['MACD_signal'] and curr_1h['RSI_14'] > 50:
                    if current_price <= curr_15m['BB_Lower_20'] or curr_15m['low'] <= curr_15m['BB_Lower_20']:
                        direction = Direction.LONG
                        triggered_indicators = ["4H_EMA_BULL", "1H_MACD_BULL", "15M_BB_LOWER_TOUCH"]
                        confidence = 0.85

            # -------------------------------------------------------------
            # SHORT CONFLUENCE LOGIC
            # 4H: Trending Down
            # 1H: MACD Bearish Crossover & RSI < 50
            # 15M: Price touching/crossing upper Bollinger Band (Overbought entry)
            # -------------------------------------------------------------
            elif regime == MarketRegime.TRENDING_DOWN:
                if curr_1h['MACD_line'] < curr_1h['MACD_signal'] and curr_1h['RSI_14'] < 50:
                    if current_price >= curr_15m['BB_Upper_20'] or curr_15m['high'] >= curr_15m['BB_Upper_20']:
                        direction = Direction.SHORT
                        triggered_indicators = ["4H_EMA_BEAR", "1H_MACD_BEAR", "15M_BB_UPPER_TOUCH"]
                        confidence = 0.85

            # Generate Signal if logic matched
            if direction:
                return self._build_signal(
                    pair=pair,
                    direction=direction,
                    current_price=current_price,
                    atr=atr_15m,
                    regime=regime,
                    confidence=confidence,
                    triggered_indicators=triggered_indicators
                )

            return None

        except Exception as e:
            logger.error(f"Error during confluence analysis for {pair}: {str(e)}")
            return None

    def _build_signal(
        self, 
        pair: str, 
        direction: Direction, 
        current_price: float, 
        atr: float, 
        regime: MarketRegime,
        confidence: float,
        triggered_indicators: list[str]
    ) -> Signal:
        """
        Constructs the Signal object with dynamic, ATR-based risk management levels.
        SL is placed 1.5 ATR away, TP1 is 2.0 ATR, TP2 is 3.5 ATR.
        """
        entry_price_dec = Decimal(str(current_price))
        atr_dec = Decimal(str(atr))

        # Dynamic Risk/Reward Calculation
        sl_distance = atr_dec * Decimal('1.5')
        tp1_distance = atr_dec * Decimal('2.0')
        tp2_distance = atr_dec * Decimal('3.5')

        if direction == Direction.LONG:
            stop_loss = entry_price_dec - sl_distance
            take_profit_1 = entry_price_dec + tp1_distance
            take_profit_2 = entry_price_dec + tp2_distance
        else:
            stop_loss = entry_price_dec + sl_distance
            take_profit_1 = entry_price_dec - tp1_distance
            take_profit_2 = entry_price_dec - tp2_distance

        # Note: position_size and risk_amount are set to 0.0 initially. 
        # The PositionSizer (Phase 2) will calculate and populate these downstream.
        new_signal = Signal(
            signal_id=str(uuid.uuid4()),
            timestamp=int(time.time() * 1000),
            pair=pair,
            direction=direction,
            entry_price=entry_price_dec.quantize(Decimal('0.00000001')),
            stop_loss=stop_loss.quantize(Decimal('0.00000001')),
            take_profit_1=take_profit_1.quantize(Decimal('0.00000001')),
            take_profit_2=take_profit_2.quantize(Decimal('0.00000001')),
            confidence=confidence,
            indicators_triggered=triggered_indicators,
            market_regime=regime,
            position_size=Decimal('0.0'),
            risk_amount=Decimal('0.0'),
            notes="Generated via 4H/1H/15M Confluence Model"
        )
        
        # Validate price hierarchy before returning
        new_signal.validate_prices()
        logger.info(f"Generated new {direction.name} signal for {pair} at {entry_price_dec}")
        return new_signal
