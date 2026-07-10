import os
import shutil
from silero_vad import load_silero_vad

print("Downloading Silero VAD for offline use...")
model = load_silero_vad()
print("Silero VAD successfully downloaded to default cache.")

# In airgapped system we will need this cache. 
# Usually silero_vad caches to ~/.cache/silero_vad. Let's find it.
cache_dir = os.path.expanduser("~/.cache/silero_vad")
if os.path.exists(cache_dir):
    target = os.path.abspath("./local_models/silero_vad_cache")
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(cache_dir, target)
    print(f"Copied silero_vad cache to {target}")
else:
    print("Could not find ~/.cache/silero_vad, perhaps it's stored in torch hub cache.")
