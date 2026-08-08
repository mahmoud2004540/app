"""
deals_bot — محرّك تحليل يعطي أفضل صفقات التداول.

Trading deals engine: fetches market data, computes technical indicators,
scores opportunities, and returns the best deals for crypto / stocks / forex.
"""

__version__ = "1.0.0"

from .models import Candle, Deal
from .analyzer import analyze_symbol, rank_deals

__all__ = ["Candle", "Deal", "analyze_symbol", "rank_deals", "__version__"]
