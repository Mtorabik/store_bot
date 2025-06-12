# main.py

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ContextTypes,
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
from datetime import datetime, timedelta

# Initialize Flask for webhook and callback
flask_app = Flask(__name__)

# Initialize bot
app = Application.builder().token(BOT_TOKEN).build()

# Store user states
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.message.from_user.id
    button = KeyboardButton("ارسال شماره 📱", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True)
    await update.message.reply_text(
        "لطفاً شماره موبایل خود را ارسال کنید:",
        reply_markup=reply_markup
    )
    user_states[user_id] = {'state': 'waiting_for_contact'}

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact info."""
    user_id = update.message.from_user.id
    if update.message.contact:
        phone = update.message.contact.phone_number.replace('+98', '0')
        customer = get_customer(phone)
        if not customer:
            await update.message.reply_text(
                "مشتری با این شماره یافت نشد.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        user_states[user_id] = {
            'state': 'customer_found',
            'customer': customer
        }
        
        reply = f"""
        نام: {customer['name']}
        مبلغ قسط: {customer['amount']:,} تومان
        موعد قسط: {customer['due_date']}
        شناسه قسط: {customer['installment_id']}
        """
        buttons = [
            [InlineKeyboardButton("پرداخت قسط 💳", callback_data=f"pay_{customer['installment_id']}")],
            [InlineKeyboardButton("تاریخچه پرداخت‌ها 📜", callback_data="history")]
        ]
        if str(user_id) == ADMIN_ID:
            buttons.append([InlineKeyboardButton("گزارش کل مشتریان 📊", callback_data="report")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(reply, reply_markup=reply_markup)

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded Excel file."""
    user_id = str(update.message.from_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین می‌تواند فایل آپلود کند.")
        return
    
    if update.message.document and 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in update.message.document.mime_type:
        file = await update.message.document.get_file()
        file_path = f"tmp/{update.message.document.file_id}.xlsx"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        await file.download_to_drive(file_path)
        
        success, message = save_excel(file_path)
        os.remove(file_path)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("لطفاً یک فایل اکسل معتبر ارسال کنید.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("pay_") and user_states.get(user_id, {}).get('state') == 'customer_found':
        installment_id = data.split("_")[1]
        customer = user_states[user_id]['customer']
        if customer['installment_id'] == installment_id:
            authority, payment_url, error = create_payment(customer['amount'], customer['phone'], installment_id)
            if error:
                await query.message.reply_text(error)
                return
            user_states[user_id]['authority'] = authority
            await query.message.reply_text(
                f"برای پرداخت قسط {installment_id}، روی لینک زیر کلیک کنید:\n{payment_url}"
            )
    
    elif data == "history":
        history = get_payment_history(user_states[user_id]['customer']['phone'])
        if not history:
            await query.message.reply_text("هیچ پرداختی ثبت نشده است.")
            return
        reply = "📜 تاریخچه پرداخت‌ها:\n"
        for payment in history:
            reply += f"مبلغ: {payment['amount']:,} تومان\nشناسه قسط: {payment['installment_id']}\nوضعیت: {payment['status']}\nزمان: {payment['timestamp']}\n---\n"
        await query.message.reply_text(reply)
    
    elif data == "report" and str(user_id) == ADMIN_ID:
        customers = get_all_customers()
        if not customers:
            await query.message.reply_text("هیچ مشتری ثبت نشده است.")
            return
        reply = "📊 گزارش کل مشتریان:\n"
        for c in customers:
            reply += f"نام: {c['name']}\nشماره: {c['phone']}\nمبلغ قسط: {c['amount']:,} تومان\nموعد: {c['due_date']}\nشناسه: {c['installment_id']}\n---\n"
        await query.message.reply_text(reply)
    
    await query.answer()

@flask_app.route('/callback', methods=['GET'])
def payment_callback():
    """Handle Zarinpal callback."""
    authority = request.args.get('Authority')
    status = request.args.get('Status')
    
    if status == 'OK':
        for user_id, state in user_states.items():
            if state.get('authority') == authority:
                customer = state['customer']
                success, error = verify_payment(customer['amount'], authority)
                status_text = "موفق" if success else "ناموفق"
                save_payment(customer['phone'], customer['amount'], customer['installment_id'], status_text, authority)
                app.bot.send_message(
                    chat_id=user_id,
                    text=f"پرداخت قسط {customer['installment_id']} {status_text} بود.\n{error if error else ''}"
                )
                break
        return "پردازش شد."
    return "پرداخت ناموفق."

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook."""
    update = Update.de_json(request.get_json(force=True), app.bot)
    asyncio.run(app.process_update(update))
    return 'OK'

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Send reminders for upcoming due dates."""
    customers = get_all_customers()
    today = datetime.now().date()
    for customer in customers:
        due_date = datetime.strptime(customer['due_date'], '%Y/%m/%d').date()
        if due_date - today <= timedelta(days=3) and due_date >= today:
            try:
                user_id = [uid for uid, state in user_states.items() if state.get('customer', {}).get('phone') == customer['phone']][0]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"یادآوری: قسط {customer['installment_id']} به مبلغ {customer['amount']:,} تومان تا تاریخ {customer['due_date']} باید پرداخت شود."
                )
            except:
                pass  # User not in chat

def main():
    """Main function."""
    init_db()
    app.job_queue.run_repeating(send_reminders, interval=86400, first=10)  # Daily reminders
    app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL + "/webhook"
    )
    flask_app.run(host="0.0.0.0", port=8443)

if __name__ == '__main__':
    main()