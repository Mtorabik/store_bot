# payment_handler.py

import requests
from config import MERCHANT_ID, CALLBACK_URL

def create_payment(amount, phone, installment_id):
    """Create a payment link using Zarinpal."""
    try:
        url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"  # Use sandbox for testing
        payload = {
            "merchant_id": MERCHANT_ID,
            "amount": int(amount * 10),  # Convert to Rials
            "description": f"پرداخت قسط {installment_id} برای شماره {phone}",
            "callback_url": CALLBACK_URL,
            "metadata": {"mobile": phone}
        }
        response = requests.post(url, json=payload)
        data = response.json()
        if data['data']['code'] == 100:
            return data['data']['authority'], f"https://sandbox.zarinpal.com/pg/StartPay/{data['data']['authority']}", None
        return None, None, f"خطا در ایجاد لینک پرداخت: {data['errors']['message']}"
    except Exception as e:
        return None, None, f"خطا در ارتباط با زرین‌پال: {str(e)}"

def verify_payment(amount, authority):
    """Verify payment status."""
    try:
        url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        payload = {
            "merchant_id": MERCHANT_ID,
            "amount": int(amount * 10),  # Convert to Rials
            "authority": authority
        }
        response = requests.post(url, json=payload)
        data = response.json()
        if data['data']['code'] == 100:
            return True, None
        return False, f"خطا در تأیید پرداخت: {data['errors']['message']}"
    except Exception as e:
        return False, f"خطا در ارتباط با زرین‌پال: {str(e)}"