# صورة تشغيل بوت تيليجرام على أي استضافة تدعم Docker.
FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات أولًا للاستفادة من طبقات الكاش
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# التوكن يُمرّر كمتغيّر بيئة TELEGRAM_TOKEN وقت التشغيل (لا تضعه داخل الصورة)
CMD ["python", "telegram_bot.py"]
