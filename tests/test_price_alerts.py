"""اختبارات تنبيهات السعر — offline بأسعار وهمية."""

from deals_bot import price_alerts as pa


def _prices(table):
    return lambda bases: {b: table[b] for b in bases if b in table}


def test_add_above_and_below(tmp_path):
    p = str(tmp_path / "a.json")
    px = _prices({"BTC": 90_000.0, "SOL": 150.0})
    r = pa.handle_text("تنبيه BTC 100000", px, p)
    assert "#1" in r and "يطلع" in r
    r = pa.handle_text("/alert sol 140", px, p)
    assert "#2" in r and "ينزل" in r
    a = pa.load(p)["alerts"]
    assert [x["direction"] for x in a] == ["above", "below"] and a[1]["symbol"] == "SOL"


def test_percent_k_and_names(tmp_path):
    p = str(tmp_path / "a.json")
    px = _prices({"SOL": 100.0, "ETH": 3000.0, "BTC": 90_000.0})
    pa.handle_text("تنبيه SOL +5%", px, p)
    pa.handle_text("تنبيه ETH 3.5k", px, p)
    pa.handle_text("نبهني بيتكوين 80,000", px, p)
    a = pa.load(p)["alerts"]
    assert abs(a[0]["target"] - 105.0) < 1e-9
    assert a[1]["target"] == 3500.0
    assert a[2]["symbol"] == "BTC" and a[2]["target"] == 80000.0 and a[2]["direction"] == "below"


def test_unknown_coin_rejected(tmp_path):
    p = str(tmp_path / "a.json")
    r = pa.handle_text("تنبيه NOPE 5", _prices({}), p)
    assert "مش لاقي" in r and pa.load(p)["alerts"] == []


def test_check_fires_once_and_removes(tmp_path):
    p = str(tmp_path / "a.json")
    pa.handle_text("تنبيه BTC 100000", _prices({"BTC": 90_000.0}), p)
    pa.handle_text("تنبيه BTC 85000", _prices({"BTC": 90_000.0}), p)
    assert pa.check(_prices({"BTC": 95_000.0}), p) == []          # ولا واحد وصل
    fired = pa.check(_prices({"BTC": 100_500.0}), p)
    assert len(fired) == 1 and "#1" in fired[0]
    assert [a["id"] for a in pa.load(p)["alerts"]] == [2]          # #1 اتمسح، #2 لسه
    assert pa.check(_prices({"BTC": 100_500.0}), p) == []          # ما يتبعتش تاني


def test_list_and_delete(tmp_path):
    p = str(tmp_path / "a.json")
    px = _prices({"BTC": 90_000.0, "SOL": 150.0})
    assert "مفيش تنبيهات" in pa.list_text(p, px)
    pa.handle_text("تنبيه BTC 100000", px, p)
    pa.handle_text("تنبيه SOL 200", px, p)
    assert "⚠️" in pa.handle_text("الغي 9", px, p)
    assert "#1" in pa.handle_text("الغي 1", px, p)
    assert [a["id"] for a in pa.load(p)["alerts"]] == [2]
    assert "1 تنبيه" in pa.handle_text("الغي الكل", px, p)


def test_other_messages_pass_through(tmp_path):
    p = str(tmp_path / "a.json")
    for t in ("فحص الآن", "BTC", "الحالة", "تنبيه", "/start"):
        assert pa.handle_text(t, _prices({}), p) is None


def test_tiny_prices_are_readable():
    assert pa._px(3.5319e-06) == "0.0000035319"
    assert pa._px(61613.5) == "61,613.50"


def test_watch_fires_every_step_both_ways(tmp_path):
    p = str(tmp_path / "a.json")
    r = pa.handle_text("راقب BTC 500", _prices({"BTC": 90_000.0}), p)
    assert "هراقب BTC" in r and "$500" in r
    assert pa.check(_prices({"BTC": 90_300.0}), p) == []              # لسه أقل من 500
    up = pa.check(_prices({"BTC": 90_520.0}), p)
    assert len(up) == 1 and "طلع" in up[0] and "$520" in up[0]
    assert pa.check(_prices({"BTC": 90_700.0}), p) == []              # بيعدّ من 90,520 دلوقتي
    down = pa.check(_prices({"BTC": 90_000.0}), p)
    assert len(down) == 1 and "نزل" in down[0]
    assert pa.load(p)["watches"][0]["ref"] == 90_000.0                # المراقبة مستمرة


def test_watch_small_coins_and_replace(tmp_path):
    p = str(tmp_path / "a.json")
    px = _prices({"PYTH": 0.35, "FIL": 2.5, "SOL": 150.0})
    assert "هراقب PYTH" in pa.handle_text("راقب pyth 0.01", px, p)
    assert "هراقب FIL" in pa.handle_text("تابع FIL 0.1", px, p)
    pa.handle_text("راقب SOL 5", px, p)
    pa.handle_text("راقب SOL 10", px, p)                               # بيستبدل القديم
    w = {x["symbol"]: x["step"] for x in pa.load(p)["watches"]}
    assert w == {"PYTH": 0.01, "FIL": 0.1, "SOL": 10.0}
    fired = pa.check(_prices({"PYTH": 0.362, "FIL": 2.45, "SOL": 151.0}), p)
    assert len(fired) == 1 and "PYTH" in fired[0]


def test_watch_rejects_tiny_step_and_unwatch(tmp_path):
    p = str(tmp_path / "a.json")
    px = _prices({"BTC": 90_000.0})
    assert "صغير" in pa.handle_text("راقب BTC 5", px, p)
    pa.handle_text("راقب BTC 500", px, p)
    listing = pa.list_text(p, px)
    assert "BTC" in listing and "$500" in listing
    assert "وقفت مراقبة BTC" in pa.handle_text("وقف BTC", px, p)
    assert pa.load(p)["watches"] == []
    assert "⚠️" in pa.handle_text("وقف BTC", px, p)
    pa.handle_text("راقب BTC 500", px, p)
    pa.handle_text("الغي الكل", px, p)
    assert pa.load(p)["watches"] == []
