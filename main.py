import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from database import init_db, get_customer, get_payment_history, save_payment
from excel_handler import save_excel
from payment_handler import create_payment, verify_payment
from config import BOT_TOKEN, ADMIN_ID

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# شروع بات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! شماره موبایل خود را وارد کنید تا اطلاعات قسط شما بررسی شود."
    )

# مدیریت پیام‌ها (شماره موبایل)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    customer = get_customer(phone)
    if not customer:
        await update.message.reply_text("اطلاعاتی برای این شماره یافت نشد یا قبلاً پرداخت شده است.")
        return

    msg = (
        f"🧾 اطلاعات قسط شما:\n"
        f"👤 نام: {customer['name']}\n"
        f"📞 شماره: {customer['phone']}\n"
        f"💰 مبلغ: {customer['amount']} تومان\n"
        f"📅 موعد: {customer['due_date']}\n"
    )

    keyboard = [[
        InlineKeyboardButton("پرداخت قسط", callback_data=f"pay|{customer['phone']}|{customer['amount']}|{customer['installment_id']}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup)

# دکمه پرداخت
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("pay"):
        _, phone, amount, inst_id = query.data.split("|")
        authority, link, err = create_payment(int(amount), phone, inst_id)
        if err:
            await query.edit_message_text(f"خطا: {err}")
            return
        save_payment(phone, int(amount), inst_id, "INIT", authority)
        await query.edit_message_text(f"لینک پرداخت شما:\n{link}")

# فرمان مدیریت
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.from_user.id) != ADMIN_ID:
        await update.message.reply_text("شما اجازه دسترسی به این بخش را ندارید.")
        return
    await update.message.reply_text("لطفاً فایل اکسل را ارسال کنید.")

# هندلر فایل اکسل
async def handle_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.from_user.id) != ADMIN_ID:
        await update.message.reply_text("دسترسی ندارید.")
        return

    file = await update.message.document.get_file()
    file_path = f"temp/{file.file_id}.xlsx"
    os.makedirs("temp", exist_ok=True)
    await file.download_to_drive(file_path)
    success, msg = save_excel(file_path)
    os.remove(file_path)
    await update.message.reply_text(msg)

# نمایش تاریخچه پرداخت
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً شماره موبایل خود را وارد کنید تا سوابق پرداخت نمایش داده شود.")
    context.user_data['awaiting_history'] = True

# بررسی شماره برای تاریخچه پرداخت
async def check_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_history'):
        context.user_data['awaiting_history'] = False
        phone = update.message.text.strip()
        history = get_payment_history(phone)
        if not history:
            await update.message.reply_text("پرداختی یافت نشد.")
            return

        msg = "💳 سوابق پرداخت:\n"
        for item in history:
            msg += f"\n💰 {item['amount']} تومان - شناسه {item['installment_id']} - {item['status']} - {item['timestamp']}"
        await update.message.reply_text(msg)

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_excel))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_history))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    application.run_polling()
