import qrcode
import urllib.parse
import os

def create_qr_code(base_url, customer_name, customer_number):
    # URL-encode the customer name and number
    encoded_name = urllib.parse.quote(customer_name)
    encoded_number = urllib.parse.quote(customer_number)

    # Build the full URL
    full_url = f"{base_url}?name={encoded_name}&number={encoded_number}"

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

def main():
    base_url = input("Enter the base URL (e.g., https://example.com/customer): ").strip()
    customer_name = input("Enter the customer name: ").strip()
    customer_number = input("Enter the customer number: ").strip()

    create_qr_code(base_url, customer_name, customer_number)

if __name__ == "__main__":
    main()
