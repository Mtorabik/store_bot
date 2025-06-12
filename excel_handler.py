# excel_handler.py

import pandas as pd
import os
from database import save_customer, init_db

def save_excel(file_path):
    """Save Excel data to database."""
    try:
        init_db()  # Ensure database is initialized
        df = pd.read_excel(file_path)
        required_columns = ['نام مشتری', 'شماره موبایل', 'مبلغ قسط', 'موعد قسط', 'شناسه قسط']
        if all(col in df.columns for col in required_columns):
            for _, row in df.iterrows():
                save_customer(
                    name=row['نام مشتری'],
                    phone=str(row['شماره موبایل']).replace('+98', '0'),
                    amount=int(row['مبلغ قسط']),
                    due_date=str(row['موعد قسط']),
                    installment_id=str(row['شناسه قسط'])
                )
            return True, "فایل اکسل با موفقیت پردازش و ذخیره شد."
        else:
            return False, f"فایل اکسل باید شامل ستون‌های {required_columns} باشد."
    except Exception as e:
        return False, f"خطا در پردازش فایل: {str(e)}"