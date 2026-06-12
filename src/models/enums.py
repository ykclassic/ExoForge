from enum import Enum, auto

class Direction(Enum):
    LONG = auto()
    SHORT = auto()

class SignalStatus(Enum):
    ACTIVE = auto()
    WON_TP1 = auto()
    WON_TP2 = auto()
    STOPPED_OUT = auto()
    CANCELLED = auto()

class OrderStatus(Enum):
    PENDING = auto()
    FILLED = auto()
    PARTIAL = auto()
    REJECTED = auto()
    CANCELLED = auto()

class MarketRegime(Enum):
    RANGING = auto()
    TRENDING_UP = auto()
    TRENDING_DOWN = auto()
    UNKNOWN = auto()

class TradingSession(Enum):
    ASIA = auto()
    EUROPE = auto()
    US = auto()
    OFF_HOURS = auto()
