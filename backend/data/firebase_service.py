import os
import firebase_admin
from firebase_admin import credentials, db
from functools import lru_cache

@lru_cache()
def get_db_reference(path="/"):
    if not firebase_admin._apps:
        cred_path = os.path.join(os.path.dirname(__file__), "klarbill_admin_key.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://klarbill-3de73-default-rtdb.europe-west1.firebasedatabase.app/'
        })
    return db.reference(path)


# Chat message utilities
from datetime import datetime
import uuid

def save_chat_message(customer_number, invoice_number, sender, message):
    """Save a single chat message to Firebase."""
    ref = get_db_reference(f"chats/{customer_number}/{invoice_number}")
    message_id = str(uuid.uuid4())
    ref.child(message_id).set({
        "sender": sender,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })

def get_chat_messages_by_invoice(customer_number, invoice_number):
    """Retrieve all chat messages for a specific invoice."""
    ref = get_db_reference(f"chats/{customer_number}/{invoice_number}")
    return ref.get() or {}

def get_chat_messages_by_customer(customer_number):
    """Retrieve all chat messages for a customer across all invoices."""
    ref = get_db_reference(f"chats/{customer_number}")
    return ref.get() or {}