# config.py

# توکن ربات از BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN"  # جای YOUR_BOT_TOKEN را با توکن ربات پر کنید

# مرچنت‌کد زرین‌پال
MERCHANT_ID = "YOUR_MERCHANT_ID"  # جای YOUR_MERCHANT_ID را با مرچنت‌کد پر کنید

# آدرس Webhook (از Render می‌گیرید)
WEBHOOK_URL = "YOUR_RENDER_URL"  # جای YOUR_RENDER_URL را بعد از استقرار پر کنید

# آدرس کال‌بک زرین‌پال
CALLBACK_URL = f"{WEBHOOK_URL}/callback"

# آیدی ادمین (آیدی تلگرامی شما)
ADMIN_ID = "YOUR_ADMIN_ID"  # جای YOUR_ADMIN_ID را با آیدی خود پر کنید (از @userinfobot بگیرید)

# کلید رمزنگاری برای پایگاه داده
ENCRYPTION_KEY = "YOUR_SECURE_KEY_32_BYTES"  # یک کلید 32 بایتی تولید کنید (مثلاً با: python -c "import os; print(os.urandom(32).hex())")