from transformers import pipeline
print("Downloading translation model...")
pipeline("translation", model="Helsinki-NLP/opus-mt-mul-en")
