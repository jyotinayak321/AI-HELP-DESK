import os
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

if __name__ == "__main__":
    download_whisper_ct2()
