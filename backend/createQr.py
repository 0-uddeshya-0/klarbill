import qrcode
import urllib.parse
import os

def create_qr_code(base_url, customer_name, customer_number, invoice_number):
    # URL-encode the customer name and number
    encoded_name = urllib.parse.quote(customer_name)
    encoded_customer_number = urllib.parse.quote(customer_number)
    encoded_invoice_number = urllib.parse.quote(invoice_number)

    # Build the full URL
    full_url = f"{base_url}?name={encoded_name}&customernumber={encoded_customer_number}&invoicenumber={encoded_invoice_number}"

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(full_url)
    qr.make(fit=True)

    # Create an image
    img = qr.make_image(fill="black", back_color="white")

    # Create filename based on customer name and number
    filename = f"qr_{customer_name}_{customer_number}.png"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    # Save the QR code
    img.save(filepath)

    print(f"QR code saved as: {filepath}")

