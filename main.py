import os
import logging
import asyncio
from datetime import datetime, timedelta

from flask import Flask, request
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

from config import BOT_TOKEN, WEBHOOK_URL, ADMIN_ID
from database import init_db, get_customer, get_all_customers, save_payment, get_payment_history
from payment_handler import create_payment, verify_payment
from excel_handler import save_excel

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhook callback
flask_app = Flask(__name__)

# Telegram bot app
app = Application.builder().token(BOT_TOKEN).build()

# Conversation states
(A_WAIT_CONTACT, A_WAIT_CUSTOMER_QUERY) = range(2)
user_states = {}

# Inline keyboards
def get_customer_panel(customer):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\ud83d\udccb مشاهده اقساط", callback_data="show_installments"),
         InlineKeyboardButton("\ud83d\udcb3 پرداخت قسط", callback_data="pay_installment")],
        [InlineKeyboardButton("\ud83d\udcca مجموع بدهی", callback_data="total_debt"),
         InlineKeyboardButton("\ud83e\uddfe سابقه پرداخت", callback_data="history")],
        [InlineKeyboardButton("\u2709\ufe0f پیام پشتیبانی", callback_data="support_msg"),
         InlineKeyboardButton("\u274c بستن منو", callback_data="close_menu")],
    ])

def get_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\ud83d\udce4 ارسال پیام \u200cبه همه", callback_data="send_all"),
         InlineKeyboardButton("\ud83d\udce4 ارسال پیام \u200cبه بدهکاران", callback_data="send_debtors")],
        [InlineKeyboardButton("\ud83d\udcc5 اقساط امروز", callback_data="due_today"),
         InlineKeyboardButton("\u2705 پرداخت‌های امروز", callback_data="paid_today")],
        [InlineKeyboardButton("\ud83d\udcc8 گزارش کامل", callback_data="report"),
         InlineKeyboardButton("\ud83d\udd0d جستجوی مشتری", callback_data="find_customer")],
        [InlineKeyboardButton("\u23f0 تنظیم یادآوری", callback_data="schedule_reminder"),
         InlineKeyboardButton("\u274c بستن منو", callback_data="close_menu")],
    ])

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if str(user_id) == ADMIN_ID:
        await update.message.reply_text("\ud83d\udd27 پنل مدیریت:", reply_markup=get_admin_panel())
    else:
        button = KeyboardButton("\ud83d\udcde ارسال شماره", request_contact=True)
        markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("لطفاً شماره تماس خود را ارسال کنید:", reply_markup=markup)
        return A_WAIT_CONTACT

# Handle contact
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    phone = update.message.contact.phone_number.replace("+98", "0")
    customer = get_customer(phone)
    if not customer:
        await update.message.reply_text("❌ مشتری با این شماره یافت نشد.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    user_states[user.id] = customer
    await update.message.reply_text(f"\ud83d\udc4b سلام {customer['name']}!", reply_markup=get_customer_panel(customer))
    return ConversationHandler.END

# Button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "close_menu":
        await query.message.edit_reply_markup(reply_markup=None)
        return

    if str(user_id) == ADMIN_ID:
        await handle_admin_buttons(query, context)
    else:
        await handle_customer_buttons(query, context)

# Admin buttons
async def handle_admin_buttons(query, context):
    data = query.data
    if data in ("send_all", "send_debtors"):
        await query.message.reply_text("\ud83d\udce4 لطفاً متن پیام را ارسال کنید:")
        user_states[int(query.from_user.id)] = {'state': data}
    elif data == "due_today":
        today = datetime.now().date()
        items = [(c['name'], c['due_date'], c['amount']) for c in get_all_customers()
                 if datetime.strptime(c['due_date'], "%Y/%m/%d").date() == today]
        text = "\n".join(f"{n}: {a:,} تومان ({d})" for n, d, a in items) or "هیچ قسطی امروز موعد ندارد."
        await query.message.reply_text("\ud83d\udcc5 اقساط امروز:\n" + text)
    elif data == "paid_today":
        await query.message.reply_text("✅ در حال حاضر گزارشی ثبت نشده است.")
    elif data == "find_customer":
        await query.message.reply_text("\ud83d\udd0d لطفاً نام یا شماره مشتری را وارد کنید:")
        user_states[int(query.from_user.id)] = {'state': "find_customer"}
    elif data == "schedule_reminder":
        await query.message.reply_text("⏰ یادآوری در ساعت مشخصی به شما اطلاع داده خواهد شد.")
    elif data == "report":
        save_excel(get_all_customers())
        await query.message.reply_text("📈 گزارش کامل خروجی گرفته شد و در فایل Excel ذخیره شد.")

# Customer buttons
async def handle_customer_buttons(query, context):
    user_id = query.from_user.id
    user = user_states.get(user_id)
    if not user:
        await query.message.reply_text("❗ لطفاً ابتدا شماره تماس خود را ارسال کنید.")
        return

    data = query.data
    phone = user['phone']

    if data == "show_installments":
        await query.message.reply_text(f"\ud83d\udd0d جزئیات قسط:\nشناسه: {user['installment_id']}\nمبلغ: {user['amount']:,} تومان\nموعد: {user['due_date']}")
    elif data == "pay_installment":
        authority, url, err = create_payment(user['amount'], phone, user['installment_id'])
        if url:
            await query.message.reply_text(f"\ud83d\udd17 برای پرداخت روی لینک زیر کلیک کنید:\n{url}")
            save_payment(phone, user['amount'], user['installment_id'], "pending", authority)
        else:
            await query.message.reply_text(f"❌ خطا در ایجاد لینک: {err}")
    elif data == "total_debt":
        await query.message.reply_text(f"\ud83d\udcb0 مجموع بدهی شما: {user['amount']:,} تومان")
    elif data == "history":
        history = get_payment_history(phone)
        if history:
            txt = "\n".join(f"{r['installment_id']}: {r['amount']:,} تومان — {r['status']} در {r['timestamp']}" for r in history)
        else:
            txt = "هیچ سابقه پرداختی یافت نشد."
        await query.message.reply_text("\ud83e\uddfe سابقه پرداخت:\n" + txt)
    elif data == "support_msg":
        await query.message.reply_text("✉️ لطفاً پیام خود را ارسال کنید:")
        user_states[user_id] = {'state': 'supporting'}

# Text handler
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {}).get('state')

    if state in ("send_all", "send_debtors"):
        text = update.message.text
        targets = get_all_customers()
        if state == "send_debtors":
            targets = [c for c in targets if not c.get('paid')]
        count = 0
        for c in targets:
            try:
                await context.bot.send_message(chat_id=int(c['phone']), text=text)
                count += 1
            except Exception as e:
                logger.error(f"خطا در ارسال به {c['phone']}: {e}")
        await update.message.reply_text(f"✅ پیام ارسال شد به {count} کاربر.")
        user_states.pop(user_id, None)

    elif state == "find_customer":
        query = update.message.text
        customer = get_customer(query) or next((c for c in get_all_customers() if c['name'] == query), None)
        if customer:
            await update.message.reply_text(f"یافت شد: {customer['name']}", reply_markup=get_customer_panel(customer))
        else:
            await update.message.reply_text("❌ مشتری یافت نشد.")
        user_states.pop(user_id, None)

    elif state == "supporting":
        await context.bot.send_message(chat_id=int(ADMIN_ID),
                                       text=f"✉️ پشتیبانی:\nاز {update.message.from_user.full_name}:\n{update.message.text}")
        await update.message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.")
        user_states.pop(user_id, None)

# Zarinpal callback (Flask)
@flask_app.route('/callback')
def callback_route():
    authority = request.args.get('Authority')
    status = request.args.get('Status')
    return "پرداخت شما با وضعیت: " + status

# Webhook main
def main():
    init_db()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={A_WAIT_CONTACT: [MessageHandler(filters.CONTACT, contact_handler)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    async def job(ctx):
        today = datetime.now().date()
        customers = get_all_customers()
        for c in customers:
            if datetime.strptime(c['due_date'], "%Y/%m/%d").date() == today:
                await app.bot.send_message(chat_id=ADMIN_ID, text=f"⏰ موعد قسط برای {c['name']} امروز است.")
    app.job_queue.run_daily(job, time=datetime.now().time())

    app.run_webhook(
        listen='0.0.0.0',
        port=int(os.getenv('PORT', 8443)),
        url_path='/webhook',
        webhook_url=WEBHOOK_URL + '/webhook'
    )
    flask_app.run(port=5000)

if __name__ == '__main__':
    main()
