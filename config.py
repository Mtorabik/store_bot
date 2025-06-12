# config.py

# توکن ربات از BotFather
BOT_TOKEN = "7303920308:AAGkKWdxNsFyq6VgbuwSKihoXLCfDYdZ6yo"  # جای YOUR_BOT_TOKEN را با توکن ربات پر کنید

# مرچنت‌کد زرین‌پال
MERCHANT_ID = "c1cbc49e-23ff-454a-8e7f-d13a1b78903e"  # جای YOUR_MERCHANT_ID را با مرچنت‌کد پر کنید

# آدرس Webhook (از Render می‌گیرید)
WEBHOOK_URL = "https://store-bot-x95i.onrender.com"  # جای YOUR_RENDER_URL را بعد از استقرار پر کنید

# آدرس کال‌بک زرین‌پال
CALLBACK_URL = f"{WEBHOOK_URL}/callback"

# آیدی ادمین (آیدی تلگرامی شما)
ADMIN_ID = "7776838673"  # جای YOUR_ADMIN_ID را با آیدی خود پر کنید (از @userinfobot بگیرید)

# کلید رمزنگاری برای پایگاه داده
ENCRYPTION_KEY = "ya1j3fnm0DPnsi3uIZJP5utNC1OXNmwHmwxCoerm38o="  # یک کلید 32 بایتی تولید کنید (مثلاً با: python -c "import os; print(os.urandom(32).hex())")
