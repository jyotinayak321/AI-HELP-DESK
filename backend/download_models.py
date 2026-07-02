import os
import urllib.request
from huggingface_hub import snapshot_download

def download_whisper_ct2():
    print("Downloading faster-whisper medium model...")
    # The CTranslate2 converted whisper medium model
    repo_id = "Systran/faster-whisper-medium"
    
    # Target directory
    target_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 
        "local_models", 
        "whisper-medium-ct2"
    ))
    
    os.makedirs(target_dir, exist_ok=True)
    
    # Download from HuggingFace directly to the target directory
    snapshot_download(
        repo_id=repo_id,
        local_dir=target_dir,
        local_dir_use_symlinks=False, # Important for Windows
        ignore_patterns=["*.msgpack", "*.h5", "coreml/*"]
    )
    print(f"Model successfully downloaded to: {target_dir}")

def download_silero_vad():
    print("Downloading Silero VAD PyTorch JIT model...")
    url = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.jit"
    target_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "local_models"
    ))
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "silero_vad.jit")
    
    try:
        urllib.request.urlretrieve(url, target_path)
        print(f"Silero VAD successfully downloaded to: {target_path}")
    except Exception as e:
        print(f"Failed to download Silero VAD model: {e}")
        raise

if __name__ == "__main__":
    download_whisper_ct2()
    download_silero_vad()

