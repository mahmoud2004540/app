#!/usr/bin/env bash
# تشغيل بوت تيليجرام بأمر واحد.
# Usage:
#   1) ضع التوكن في ملف .env :  TELEGRAM_TOKEN=123456:ABC...
#   2) ./run_bot.sh
set -euo pipefail
cd "$(dirname "$0")"

# أنشئ بيئة افتراضية إن لم تكن موجودة
if [ ! -d ".venv" ]; then
  echo "⏳ إنشاء بيئة بايثون..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "⏳ تثبيت المتطلبات..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "🚀 تشغيل البوت..."
exec python telegram_bot.py
