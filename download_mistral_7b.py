import requests
import os

def download_model(url, output_folder, filename=None):
    os.makedirs(output_folder, exist_ok=True)
    
    if not filename:
        filename = url.split("/")[-1]

    output_path = os.path.join(output_folder, filename)

    print(f"Downloading {filename}...")

    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(output_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

    print(f"Download completed! Model saved at {output_path}")

if __name__ == "__main__":
    model_url = "https://gpt4all.io/models/gguf/mistral-7b-instruct-v0.1.Q4_0.gguf"
    output_directory = "./models"
    
    download_model(model_url, output_directory)
