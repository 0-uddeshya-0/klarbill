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
