import os

from huggingface_hub import hf_hub_download


def download_kokoro():
    print("Downloading Kokoro TTS Models (This may take a minute)...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # Download the main ONNX model (~330MB)
    model_path = os.path.join(models_dir, "kokoro-v1.0.onnx")
    if not os.path.exists(model_path):
        print("Fetching kokoro-v1.0.onnx...")
        hf_hub_download(repo_id="onnx-community/Kokoro-82M-v1.0-ONNX", filename="onnx/model.onnx", local_dir=models_dir)
        # Rename to what we expect
        os.rename(os.path.join(models_dir, "onnx", "model.onnx"), model_path)
        print("ONNX model downloaded.")
    else:
        print("ONNX model already exists.")
        
    # Download the voices data
    voices_path = os.path.join(models_dir, "voices.json")
    if not os.path.exists(voices_path):
        print("Fetching voices.json...")
        hf_hub_download(repo_id="onnx-community/Kokoro-82M-v1.0-ONNX", filename="voices.json", local_dir=models_dir)
        print("Voices downloaded.")
    else:
        print("Voices already exist.")
        
    print("Kokoro setup complete.")

if __name__ == "__main__":
    download_kokoro()
