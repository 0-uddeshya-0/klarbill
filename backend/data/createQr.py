
def create_qr_code(base_url, customer_name, customer_number, invoice_number):
    import qrcode
    import urllib.parse
    import os

    # Encode components
    encoded_customer_name = urllib.parse.quote(customer_name)
    encoded_customer_number = urllib.parse.quote(customer_number)
    encoded_invoice_number = urllib.parse.quote(invoice_number)

    # Generate URLs
    invoice_url = f"{base_url}?invoicenumber={encoded_invoice_number}"
    customer_url = f"{base_url}?customernumber={encoded_customer_number}"

    # Generate and save QR code for invoice URL
    qr_invoice = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr_invoice.add_data(invoice_url)
    qr_invoice.make(fit=True)
    img_invoice = qr_invoice.make_image(fill="black", back_color="white")
    filename_invoice = f"qr_invoice_{customer_name}_{invoice_number}.png"
    filepath_invoice = os.path.join(os.path.dirname(__file__), filename_invoice)
    img_invoice.save(filepath_invoice)
    print(f"Invoice QR code saved as: {filepath_invoice}")

    # Generate and save QR code for customer URL
    qr_customer = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr_customer.add_data(customer_url)
    qr_customer.make(fit=True)
    img_customer = qr_customer.make_image(fill="black", back_color="white")
    filename_customer = f"qr_customer_{customer_name}_{customer_number}.png"
    filepath_customer = os.path.join(os.path.dirname(__file__), filename_customer)
    img_customer.save(filepath_customer)
    print(f"Customer QR code saved as: {filepath_customer}")

