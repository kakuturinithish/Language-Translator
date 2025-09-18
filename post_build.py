from transformers import pipeline
print("Downloading translation model...")
pipeline('translation', model='Helsinki-NLP/opus-mt-pt-en')
pipeline('translation', model='Helsinki-NLP/opus-mt-es-en')
pipeline('translation', model='Helsinki-NLP/opus-mt-fr-en')
pipeline('translation', model='Helsinki-NLP/opus-mt-de-en')
