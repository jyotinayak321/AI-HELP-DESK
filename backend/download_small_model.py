from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Systran/faster-whisper-small",
    local_dir="local_models/whisper-small-ct2",
    local_dir_use_symlinks=False,  # ← Ye line symlink issue completely bypass karti hai
)

print("✅ Small model downloaded successfully to local_models/whisper-small-ct2")