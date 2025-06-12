import logging
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, ADMIN_ID
from secure_database import get_customer, get_all_customers, save_payment, get_payment_history
from payment_handler import create_payment, verify_payment
from excel_handler import save_excel
from datetime import datetime

# Initialize bot and logging
bot = telebot.TeleBot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# Keyboards for customers and admin
customer_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
customer_buttons.add(KeyboardButton('پرداخت قسط'), KeyboardButton('وضعیت پرداخت‌ها'))

admin_buttons = InlineKeyboardMarkup(row_width=2)
admin_buttons.add(
    InlineKeyboardButton('لیست مشتریان', callback_data='list_customers'),
    InlineKeyboardButton('پرداخت‌ها', callback_data='list_payments')
)
admin_buttons.add(
    InlineKeyboardButton('آپلود فایل اکسل', callback_data='upload_excel'),
    InlineKeyboardButton('بستن پنل مدیریت', callback_data='close_admin_panel')
)

# Helper Functions
def send_admin_panel(chat_id):
    """Send admin panel with buttons."""
    bot.send_message(chat_id, "پنل مدیریت:", reply_markup=admin_buttons)

def toggle_keyboard(chat_id, open: bool):
    """Toggle the visibility of the keyboard."""
    if open:
        bot.send_message(chat_id, "دکمه‌ها باز شدند", reply_markup=admin_buttons)
    else:
        bot.send_message(chat_id, "دکمه‌ها بسته شدند", reply_markup=ReplyKeyboardMarkup())

def get_user_info(chat_id):
    """Get customer data from the database."""
    customer = get_customer(chat_id)
    if customer:
        bot.send_message(chat_id, f"نام: {customer['name']}\nمبلغ قسط: {customer['amount']}\nموعد قسط: {customer['due_date']}")
    else:
        bot.send_message(chat_id, "مشتری پیدا نشد!")

def handle_payment_request(chat_id, phone, amount, installment_id):
    """Handle payment request for customers."""
    authority, payment_link, error = create_payment(amount, phone, installment_id)
    if payment_link:
        bot.send_message(chat_id, f"لینک پرداخت شما: {payment_link}")
        save_payment(phone, amount, installment_id, "pending", authority)
    else:
        bot.send_message(chat_id, f"خطا: {error}")

# Command Handlers
@bot.message_handler(commands=['start'])
def start(message):
    """Start command - show main menu."""
    if message.chat.id == ADMIN_ID:
        send_admin_panel(message.chat.id)
    else:
        bot.send_message(message.chat.id, "سلام! از دکمه‌ها برای شروع استفاده کنید.", reply_markup=customer_buttons)

@bot.message_handler(func=lambda message: message.text == "پرداخت قسط")
def handle_installment_payment(message):
    """Handle installment payment requests."""
    customer = get_customer(message.chat.id)
    if customer:
        bot.send_message(message.chat.id, "لطفاً مبلغ قسط را وارد کنید.")
        bot.register_next_step_handler(message, process_payment_amount, customer['phone'], customer['installment_id'])
    else:
        bot.send_message(message.chat.id, "مشتری پیدا نشد!")

def process_payment_amount(message, phone, installment_id):
    """Process the amount entered by the user."""
    try:
        amount = int(message.text)
        handle_payment_request(message.chat.id, phone, amount, installment_id)
    except ValueError:
        bot.send_message(message.chat.id, "مبلغ وارد شده صحیح نیست. لطفاً دوباره امتحان کنید.")
        bot.register_next_step_handler(message, process_payment_amount, phone, installment_id)

@bot.message_handler(func=lambda message: message.text == "وضعیت پرداخت‌ها")
def handle_payment_status(message):
    """Show payment status for the customer."""
    payment_history = get_payment_history(message.chat.id)
    if payment_history:
        response = "\n".join([f"شناسه قسط: {p['installment_id']}\nمبلغ: {p['amount']}\nوضعیت: {p['status']}\nتاریخ: {p['timestamp']}" for p in payment_history])
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "هیچ پرداختی پیدا نشد.")

# Admin Commands
@bot.callback_query_handler(func=lambda call: call.data == 'list_customers')
def list_customers(call):
    """Show all customers to the admin."""
    customers = get_all_customers()
    if customers:
        response = "\n".join([f"{c['name']} - {c['phone']}\nمبلغ: {c['amount']}\nموعد قسط: {c['due_date']}" for c in customers])
        bot.send_message(call.message.chat.id, response)
    else:
        bot.send_message(call.message.chat.id, "هیچ مشتریی پیدا نشد.")

@bot.callback_query_handler(func=lambda call: call.data == 'list_payments')
def list_payments(call):
    """Show all payments to the admin."""
    payments = get_all_payments()
    if payments:
        response = "\n".join([f"شناسه قسط: {p['installment_id']}\nمبلغ: {p['amount']}\nوضعیت: {p['status']}\nتاریخ: {p['timestamp']}" for p in payments])
        bot.send_message(call.message.chat.id, response)
    else:
        bot.send_message(call.message.chat.id, "هیچ پرداختی پیدا نشد.")

@bot.callback_query_handler(func=lambda call: call.data == 'upload_excel')
def upload_excel(call):
    """Handle Excel file upload for admin."""
    bot.send_message(call.message.chat.id, "لطفاً فایل اکسل را ارسال کنید.")

@bot.callback_query_handler(func=lambda call: call.data == 'close_admin_panel')
def close_admin_panel(call):
    """Close admin panel."""
    toggle_keyboard(call.message.chat.id, open=False)

# Start the bot
if __name__ == '__main__':
    bot.polling(none_stop=True)
