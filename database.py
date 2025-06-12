# database.py

import sqlite3
from cryptography.fernet import Fernet
import os
from config import ENCRYPTION_KEY

# Initialize encryption
cipher = Fernet(ENCRYPTION_KEY.encode())

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            amount INTEGER,
            due_date TEXT,
            installment_id TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            amount INTEGER,
            installment_id TEXT,
            status TEXT,
            authority TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def encrypt_data(data):
    """Encrypt sensitive data."""
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(data):
    """Decrypt sensitive data."""
    return cipher.decrypt(data.encode()).decode()

def save_customer(name, phone, amount, due_date, installment_id):
    """Save or update customer data."""
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    encrypted_phone = encrypt_data(phone)
    cursor.execute('''
        INSERT OR REPLACE INTO customers (name, phone, amount, due_date, installment_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, encrypted_phone, amount, due_date, installment_id))
    conn.commit()
    conn.close()

def get_customer(phone):
    """Get customer data by phone."""
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers WHERE phone = ?', (encrypt_data(phone),))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'name': result[1],
            'phone': decrypt_data(result[2]),
            'amount': result[3],
            'due_date': result[4],
            'installment_id': result[5]
        }
    return None

def get_all_customers():
    """Get all customers for admin reports."""
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, phone, amount, due_date, installment_id FROM customers')
    results = cursor.fetchall()
    conn.close()
    return [{
        'name': r[0],
        'phone': decrypt_data(r[1]),
        'amount': r[2],
        'due_date': r[3],
        'installment_id': r[4]
    } for r in results]

def save_payment(phone, amount, installment_id, status, authority):
    """Save payment record."""
    from datetime import datetime
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (phone, amount, installment_id, status, authority, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (encrypt_data(phone), amount, installment_id, status, authority, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def get_payment_history(phone):
    """Get payment history for a customer."""
    conn = sqlite3.connect('customers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, installment_id, status, timestamp FROM payments WHERE phone = ?', (encrypt_data(phone),))
    results = cursor.fetchall()
    conn.close()
    return [{
        'amount': r[0],
        'installment_id': r[1],
        'status': r[2],
        'timestamp': r[3]
    } for r in results]