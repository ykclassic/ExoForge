import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("trading.strategy.indicators")

class TechnicalIndicators:
    """
    A robust, vectorized technical indicators library using pandas.
    Designed for speed and accuracy in live trading environments.
    """
    
    @staticmethod
    def add_ema(df: pd.DataFrame, period: int, column: str = 'close') -> pd.DataFrame:
        """Calculates the Exponential Moving Average (EMA)."""
        df[f'EMA_{period}'] = df[column].ewm(span=period, adjust=False).mean()
        return df

    @staticmethod
    def add_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.DataFrame:
        """Calculates the Relative Strength Index (RSI)."""
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Avoid division by zero
        rs = np.where(loss == 0, 100, gain / loss)
        df[f'RSI_{period}'] = np.where(loss == 0, 100, 100 - (100 / (1 + rs)))
        
        # Fallback for initial NaN values
        df[f'RSI_{period}'] = df[f'RSI_{period}'].fillna(50)
        return df

    @staticmethod
    def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = 'close') -> pd.DataFrame:
        """Calculates the Moving Average Convergence Divergence (MACD)."""
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()
        
        df['MACD_line'] = ema_fast - ema_slow
        df['MACD_signal'] = df['MACD_line'].ewm(span=signal, adjust=False).mean()
        df['MACD_hist'] = df['MACD_line'] - df['MACD_signal']
        return df

    @staticmethod
    def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = 'close') -> pd.DataFrame:
        """Calculates Bollinger Bands (SMA, Upper Band, Lower Band)."""
        sma = df[column].rolling(window=period).mean()
        rolling_std = df[column].rolling(window=period).std()
        
        df[f'BB_SMA_{period}'] = sma
        df[f'BB_Upper_{period}'] = sma + (rolling_std * std_dev)
        df[f'BB_Lower_{period}'] = sma - (rolling_std * std_dev)
        return df

    @staticmethod
    def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculates the Average True Range (ATR) for volatility measurement."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        
        df[f'ATR_{period}'] = true_range.rolling(window=period).mean()
        return df

    @classmethod
    def apply_all_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Applies the standard suite of indicators required for the confluence strategy."""
        if df.empty or len(df) < 50:
            logger.warning("Insufficient data length to calculate reliable indicators.")
            return df
            
        df = cls.add_ema(df, period=50)
        df = cls.add_ema(df, period=200)
        df = cls.add_rsi(df, period=14)
        df = cls.add_macd(df)
        df = cls.add_bollinger_bands(df, period=20)
        df = cls.add_atr(df, period=14)
        
        return df
