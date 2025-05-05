import json
from firebase_service import get_db_reference

# Load the JSON file
with open('./invoices.json', 'r', encoding='utf-8') as f:
    invoices = json.load(f)

# Upload each invoice to the database
ref = get_db_reference('invoices')
for i, invoice in enumerate(invoices):
    ref.push(invoice)
    print(f"Uploaded invoice {i + 1}")