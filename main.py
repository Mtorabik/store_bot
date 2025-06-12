from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from config import BOT_TOKEN, WEBHOOK_URL, ADMIN_ID
from excel_handler import save_excel
from payment_handler import create_payment, verify_payment
from database import init_db, get_customer, get_all_customers, save_payment, get_payment_history
from flask import Flask, request
import asyncio
import os
import logging
from datetime import datetime, timedelta
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask for webhook
flask_app = Flask(__name__)

# Initialize bot
app = Application.builder().token(BOT_TOKEN).build()

# Store user states
user_states = {}

# Customer panel buttons
def get_customer_panel(customer):
    buttons = [
        [InlineKeyboardButton("قسط‌ها و موعد‌هاشون", callback_data="show_installments")],
        [InlineKeyboardButton("پرداخت قسط", callback_data="pay_installment")],
        [InlineKeyboardButton("مجموع بدهی", callback_data="total_debt")]
    ]
    return InlineKeyboardMarkup(buttons)

# Admin panel buttons
def get_admin_panel():
    buttons = [
        [InlineKeyboardButton("ارسال پیام به مشتریان", callback_data="send_message")],
        [InlineKeyboardButton("قسط‌های امروز", callback_data="due_today")],
        [InlineKeyboardButton("قسط‌های پرداخت‌شده امروز", callback_data="paid_today")],
        [InlineKeyboardButton("گزارش وصولی‌ها و پرداختی‌ها", callback_data="report")],
        [InlineKeyboardButton("پیدا کردن مشتری", callback_data="find_customer")],
        [InlineKeyboardButton("آمار کلی", callback_data="stats")],
        [InlineKeyboardButton("برنامه‌ریزی یادآوری", callback_data="schedule_reminder")]
    ]
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if str(user_id) == ADMIN_ID:
        await update.message.reply_text("پنل مدیریت:", reply_markup=get_admin_panel())
    else:
        button = KeyboardButton("ارسال شماره من", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True)
        await update.message.reply_text("لطفاً شماره خود را ارسال کنید:", reply_markup=reply_markup)
        user_states[user_id] = {'state': 'waiting_for_contact'}

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.contact:
        phone = update.message.contact.phone_number.replace('+98', '0')
        customer = get_customer(phone)
        if customer:
            user_states[user_id] = {'state': 'customer_found', 'customer': customer}
            await update.message.reply_text(f"خوش آمدید {customer['name']}!", reply_markup=get_customer_panel(customer))
        else:
            await update.message.reply_text("مشتری با این شماره یافت نشد.", reply_markup=ReplyKeyboardRemove())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if str(user_id) == ADMIN_ID:
        if data == "send_message":
            await query.message.reply_text("ارسال به همه یا بدهکاران؟", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("همه", callback_data="send_all")],
                [InlineKeyboardButton("بدهکاران", callback_data="send_debtors")]
            ]))
        elif data == "due_today":
            due_customers = [c for c in get_all_customers() if datetime.strptime(c['due_date'], '%Y/%m/%d').date() == datetime.now().date()]
            await query.message.reply_text("قسط‌های امروز:\n" + "\n".join([f"{c['name']}: {c['amount']:,} تومان" for c in due_customers]) if due_customers else "هیچ قسطی برای امروز نیست.")
        elif data == "paid_today":
            # لاجیک برای قسط‌های پرداخت‌شده امروز (نیاز به دیتابیس دارد)
            await query.message.reply_text("در حال توسعه...")
        elif data == "report":
            await query.message.reply_text("گزارش در حال آماده‌سازی...")
        elif data == "find_customer":
            await query.message.reply_text("شماره یا نام مشتری را وارد کنید.", reply_markup=ReplyKeyboardRemove())
            user_states[user_id] = {'state': 'finding_customer'}
        elif data == "stats":
            await query.message.reply_text("آمار کلی در حال محاسبه...")
        elif data == "schedule_reminder":
            await query.message.reply_text("زمان‌بندی یادآوری در حال تنظیم...")
    else:
        customer = user_states.get(user_id, {}).get('customer')
        if customer:
            if data == "show_installments":
                await query.message.reply_text(f"قسط‌ها:\n{json.dumps(customer['installments'], ensure_ascii=False, indent=2)}")
            elif data == "pay_installment":
                await query.message.reply_text("پرداخت آخرین قسط یا قسط انتخابی؟", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("آخرین قسط", callback_data="pay_last")],
                    [InlineKeyboardButton("قسط انتخابی", callback_data="pay_select")]
                ]))
            elif data == "total_debt":
                total = sum(float(i['amount']) for i in customer.get('installments', []) if not i.get('paid'))
                await query.message.reply_text(f"مجموع بدهی: {total:,.0f} تومان")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_states.get(user_id, {}).get('state') == 'finding_customer':
        query = update.message.text
        customer = get_customer(query) or next((c for c in get_all_customers() if c['name'] == query), None)
        if customer:
            await update.message.reply_text(f"یافت شد: {customer['name']}", reply_markup=get_customer_panel(customer))
        else:
            await update.message.reply_text("مشتری یافت نشد.")
        user_states[user_id] = {}

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    customers = get_all_customers()
    today = datetime.now().date()
    for customer in customers:
        due_date = datetime.strptime(customer['due_date'], '%Y/%m/%d').date()
        if due_date == today:
            user_ids = [uid for uid, state in user_states.items() if state.get('customer', {}).get('phone') == customer['phone']]
            if user_ids:
                await context.bot.send_message(
                    chat_id=user_ids[0],
                    text=f"موعد قسط شما رسید. قسط {customer['installment_id']} به مبلغ {customer['amount']:,} تومان را از طریق دکمه پرداخت با زرین‌پال پرداخت کنید.",
                    reply_markup=get_customer_panel(customer)
                )

def main():
    init_db()
    app.job_queue.run_repeating(send_reminder, interval=86400, first=10)  # Daily reminder
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL + "/webhook"
    )

if __name__ == '__main__':
    main()
