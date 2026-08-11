# الترقية الاحترافية — PHASE 1 (النواة الحرجة)

ترقية مُضافة على بوت الـPython الحالي (مش إعادة بناء) — تطبّق متطلبات الـ
Master Build بنفس الجوهر المُثبت بالأرقام (+0.38R على 1H، RR 2.0 + EMA200).

> 🔒 **قاعدة الأمان الحرجة:** لا تداول بأموال حقيقية. المسار الوحيد للتنفيذ هو
> **Paper Trading**. `LIVE_TRADING_ENABLED = False` افتراضيًا ولا يُفعَّل إلا يدويًا
> وبموافقة صريحة، وبعد اجتياز Backtesting + Walk-Forward + Paper Trading.

## الملفات المُضافة في PHASE 1

| الملف | الدور | المرحلة في المخطط |
|---|---|---|
| `deals_bot/risk_engine.py` | محرّك مخاطر **مستقل** عن الـ AI: 0.5%/صفقة، 1.5% خسارة يومية، 3 خسائر متتالية، RR≥2، حماية الوقف، حجم المركز بالرسوم/الانزلاق | Risk Engine + Position Size |
| `deals_bot/confirmation.py` | تأكيد الدخول من 15M: انغلاف + توسّع حجم + كسر بنية صغرى | Entry Confirmation |
| `deals_bot/paper_trading.py` | محرّك تنفيذ ورقي يحاكي الدخول/الخروج/الرسوم/الانزلاق ويحسب P/L والـR | Paper Trading Engine |
| `deals_bot/pipeline.py` | خط القرار الكامل الذي يمرّ بكل البوّابات ويفشل مغلقًا عند أي إخفاق | Trade Decision Pipeline |
| `tests/test_risk_engine.py` | اختبارات النواة الحرجة (0.5% / 1.5% / 3 خسائر / RR / الوقف / الاستقلال) | Testing |
| `tests/test_paper_pipeline.py` | اختبارات التنفيذ الورقي + التأكيد + خط القرار | Testing |

## المعمارية (Adapter / Clean)

```
Market Data (providers)  →  Indicators  →  Trend+Pullback (analyzer)
        ↓                                        ↓
   15M Confirmation (confirmation)  →  AI Score (0–100)
        ↓
   R:R Check ─┐
              ├─►  Risk Engine (مستقل، غير قابل للتجاوز)  →  Position Size
   Daily Safety┘
        ↓
   Trade Approval  →  Paper Trading Engine  →  Trade Journal  →  Performance
```

- **الـ AI يقيّم فقط** (0–100). محرّك المخاطر هو صاحب القرار النهائي ولا يمكن تجاوزه
  (اختبار `test_risk_engine_is_independent_of_ai` يضمن عدم استيراده للـ AI).
- بوّابات الدرجة: `≥80` موافقة، `60–79` انتظار، `<60` لا صفقة.

## أوامر التشغيل والاختبار

```bash
# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل كل الاختبارات (النواة الحرجة تعمل offline بلا شبكة)
python -m pytest -q

# فحص الأداء التاريخي (النواة المُثبتة)
python backtest.py --market crypto --timeframe 1h --strategy optimize

# الرقمنة الحيّة (Paper only) — إشعارات تيليجرام
python send_digest.py
```

## ما تحقّقنا منه فعليًا في هذه البيئة

- ✅ كل الاختبارات (87) تمرّ offline.
- ✅ خط القرار يمرّ بالسلسلة الكاملة ويفشل مغلقًا عند أي بوّابة.
- ✅ محرّك المخاطر مستقل ومختبَر (0.5% / 1.5% / 3 خسائر / RR / حماية الوقف).

## القيود (بصراحة)

- Supabase / Docker / Next.js في الـ Master Build الأصلي **ليست** جزء هذه الترقية
  لأنها stack منفصل؛ الطلب كان «إضافة على البوت القديم». الأداء والمنطق يعيشان في
  Python كما هو مُثبت.
- التداول الحقيقي غير مُنفّذ إطلاقًا — المسار الوحيد Paper Trading.

## المرحلة التالية

لا أنتقل إلى PHASE 2 إلا بأمر صريح: **«ابدأ المرحلة الثانية»**.
PHASE 2 المقترحة: ربط خط القرار + التنفيذ الورقي بحلقة البوت الحيّة وتسجيل كل
صفقة ورقية في السجل، ثم Walk-Forward Testing.
