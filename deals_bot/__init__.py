"""
deals_bot — محرّك تحليل يعطي أفضل صفقات التداول.
"""

__version__ = "1.0.0"

from .models import Candle, Deal
from .analyzer import analyze_symbol, rank_deals

try:
    import config as _cfg
    from .settings_store import apply_overrides as _apply
    _apply(_cfg)
except Exception:
    pass

__all__ = ["Candle", "Deal", "analyze_symbol", "rank_deals", "__version__"]
