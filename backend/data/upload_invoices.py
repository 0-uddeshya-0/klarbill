import os
import json
from data.firebase_service import get_db_reference
from .createQr import create_qr_code

def upload_invoices_once():
    ref = get_db_reference('invoices')
    existing = ref.get() or {}

    base_url = os.getenv("QR_BASE_URL", "http://127.0.0.1:8000") #todo: change default url to what the frontend runs on

    import glob

    invoice_dir = os.path.dirname(__file__)
    invoice_files = glob.glob(os.path.join(invoice_dir, "invoice*.json"))

    for file_path in invoice_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                invoice = json.load(f)
                data = invoice.get("Data", {})
                pro_daten = data.get("ProzessDaten", {})
                prozess_element = pro_daten.get("ProzessDatenElement", {})

                # If it's a list, take the first element
                if isinstance(prozess_element, list):
                    process_data = prozess_element[0] if prozess_element else {}
                else:
                    process_data = prozess_element
                business_partner = process_data.get("Geschaeftspartner", {}).get("GeschaeftspartnerElement", {})

                customer_number = business_partner.get("customerNumber")
                customer_name = business_partner.get("name")
                salutation = business_partner.get("salutation")
                invoice_number = process_data.get("invoiceNumber")

                # Check if the invoice is already in Firebase (based on invoice number)
                already_uploaded = any(
                    inv.get("Data", {}).get("ProzessDaten", {}).get("ProzessDatenElement", {}).get("invoiceNumber") == invoice_number
                    for inv in existing.values()
                )

                if not already_uploaded:
                    ref.push(invoice)
                    print(f"Uploaded invoice file: {os.path.basename(file_path)}")
                else:
                    print(f"Invoice {invoice_number} already uploaded. Skipping upload.")

                full_name = f"{salutation} {customer_name}".strip()
                if full_name and customer_number and invoice_number:
                    create_qr_code(base_url, full_name, str(customer_number), str(invoice_number))
                else:
                    print(f"Skipping QR code generation due to missing data. Name: {full_name}, Number: {customer_number}, Invoice: {invoice_number}")
        except Exception as e:
            print(f"Error processing invoice from {file_path}: {e}")