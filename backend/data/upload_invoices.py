import os
import json
from data.firebase_service import get_db_reference
from createQr import create_qr_code

def upload_invoices_once():
    ref = get_db_reference('invoices')
    existing = ref.get()

    if existing:
        print("Invoices already uploaded. Skipping.")
        return

    base_url = os.getenv("QR_BASE_URL", "http://127.0.0.1:8000") #todo: change default url to what the frontend runs on

    try:
        invoices_path = os.path.join(os.path.dirname(__file__), "invoices.json")
        with open(invoices_path, "r", encoding="utf-8") as f:
            invoices = json.load(f)
            for i, invoice in enumerate(invoices):
                data = invoice.get("Data", {})
                customer = data.get("Customer", {})
                invoice = data.get("InvoiceInfo", {})
                customer_number = customer.get("customerNumber")
                customer_name = customer.get("name")
                invoice_number = invoice.get("invoiceNumber")

                sanitized_invoice = {
                    "Data": {
                        **data,
                        "Customer": {
                            "customerNumber": customer_number
                        }
                    }
                }

                ref.push(sanitized_invoice)
                print(f"Uploaded invoice {i + 1}")
                create_qr_code(base_url, customer_name, customer_number, invoice_number)
    except Exception as e:
        print(f"Error uploading invoices: {e}")