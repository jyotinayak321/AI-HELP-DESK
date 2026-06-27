import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer

# 1. Setup the target directory for local models
save_dir = "./local_models"
os.makedirs(save_dir, exist_ok=True)

print("🚀 Starting offline model downloads...")

# 2. Download the Semantic Matcher Model (for embedder.py - R-25)
print("\n📦 Downloading multilingual-e5-base...")
e5_model = SentenceTransformer('intfloat/multilingual-e5-base')
e5_model.save(f"{save_dir}/multilingual-e5-base")

# 3. Download the Zero-Shot Classifier Model (for classifier.py - R-11, R-12)
print("\n📦 Downloading mDeBERTa-v3-base-xnli-multilingual...")
model_name = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

tokenizer.save_pretrained(f"{save_dir}/mDeBERTa-v3")
model.save_pretrained(f"{save_dir}/mDeBERTa-v3")

print("\n✅ All models successfully downloaded and saved locally for air-gapped deployment!")

