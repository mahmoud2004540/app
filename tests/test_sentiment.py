"""اختبارات مزوّد المشاعر (CryptoPanic) — parser offline بلا شبكة."""

from deals_bot.providers import _base_asset, _parse_sentiment, fetch_sentiment


def test_base_asset_mapping():
    assert _base_asset("BTC-USD") == "BTC"
    assert _base_asset("ETHUSDT") == "ETH"
    assert _base_asset("EURUSD=X") == "EUR"
    assert _base_asset("SOL") == "SOL"


def test_parse_sentiment_bullish():
    raw = {"results": [
        {"votes": {"positive": 3, "negative": 1}},
        {"votes": {"positive": 2, "negative": 0}},
    ]}
    s = _parse_sentiment(raw, "BTC")
    assert s["positive"] == 5 and s["negative"] == 1
    assert s["score"] == 4 and s["posts"] == 2
    assert "إيجابي" in s["label"]


def test_parse_sentiment_bearish_and_neutral():
    bear = _parse_sentiment({"results": [{"votes": {"positive": 0, "negative": 4}}]}, "X")
    assert bear["score"] == -4 and "سلبي" in bear["label"]
    neu = _parse_sentiment({"results": [{"votes": {"positive": 1, "negative": 1}}]}, "X")
    assert neu["score"] == 0 and "محايد" in neu["label"]


def test_parse_sentiment_empty():
    s = _parse_sentiment({"results": []}, "X")
    assert s["posts"] == 0 and s["score"] == 0


def test_fetch_sentiment_none_without_token(monkeypatch):
    monkeypatch.delenv("CRYPTOPANIC_TOKEN", raising=False)
    assert fetch_sentiment("BTC-USD") is None
