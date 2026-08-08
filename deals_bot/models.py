"""
نماذج البيانات المستخدمة في البوت.

Core data models shared across the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Candle:
    """شمعة سعرية واحدة (OHLCV)."""

    ts: float          # epoch seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Series:
    """سلسلة شموع لرمز واحد، مع دوال مساعدة لاستخراج القيم."""

    symbol: str
    market: str                       # "crypto" | "stocks" | "forex"
    candles: List[Candle] = field(default_factory=list)

    def closes(self) -> List[float]:
        return [c.close for c in self.candles]

    def highs(self) -> List[float]:
        return [c.high for c in self.candles]

    def lows(self) -> List[float]:
        return [c.low for c in self.candles]

    def volumes(self) -> List[float]:
        return [c.volume for c in self.candles]

    def __len__(self) -> int:
        return len(self.candles)


@dataclass
class Deal:
    """
    صفقة مقترحة ناتجة عن التحليل.

    A scored trading opportunity. `score` is signed:
      > 0  → bullish (BUY) strength
      < 0  → bearish (SELL) strength
    `confidence` is the absolute strength on a 0..100 scale.
    """

    symbol: str
    market: str
    direction: str                    # "BUY" | "SELL" | "NEUTRAL"
    score: float                      # signed strength, roughly -100..100
    confidence: float                 # abs(score), 0..100
    price: float
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    reasons: List[str] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    error: Optional[str] = None
    # تأكيد من إطار زمني أعلى (None = لم يُفحص)
    confirmed: Optional[bool] = None
    # إدارة المخاطر (تُملأ عند توفّر رأس المال)
    qty: Optional[float] = None            # حجم الصفقة المقترح (وحدات)
    risk_amount: Optional[float] = None    # المبلغ المخاطَر به بعملتك

    def is_actionable(self) -> bool:
        return self.direction in ("BUY", "SELL") and self.error is None
