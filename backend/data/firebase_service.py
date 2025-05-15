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

def get_invoice_by_number(invoice_number):
    """Retrieve a single invoice by invoice number."""
    ref = get_db_reference("invoices")
    all_invoices = ref.get() or {}

    for key, entry in all_invoices.items():
        invoice_data = entry.get("Data", {}).get("ProzessDaten", {}).get("ProzessDatenElement", {})
        if invoice_data.get("invoiceNumber") == invoice_number:
            return {key: entry}

    return {}

def get_invoices_by_customer(customer_number):
    """Retrieve all invoices for a specific customer number."""
    ref = get_db_reference("invoices")
    all_invoices = ref.get() or {}

    matched_invoices = {}

    for key, entry in all_invoices.items():
        customer_data = entry.get("Data", {}).get("ProzessDaten", {}).get("ProzessDatenElement", {}).get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})
        if customer_data.get("customerNumber") == customer_number:
            matched_invoices[key] = entry

    return matched_invoices
