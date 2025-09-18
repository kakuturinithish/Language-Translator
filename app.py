import os
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from transformers import pipeline
import docx
from PyPDF2 import PdfReader

# Flask setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"txt", "docx", "pdf"}

# Cache models
MODEL_CACHE = {}

# Language → Model mapping
LANG_TO_MODEL = {
    "pt": "Helsinki-NLP/opus-mt-pt-en",  # Portuguese
    "es": "Helsinki-NLP/opus-mt-es-en",  # Spanish
    "fr": "Helsinki-NLP/opus-mt-fr-en",  # French
    "de": "Helsinki-NLP/opus-mt-de-en",  # German
    "it": "Helsinki-NLP/opus-mt-it-en",  # Italian
    "default": "Helsinki-NLP/opus-mt-mul-en",  # fallback multilingual
}


# ---------------------- Helpers ----------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def read_file_content(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()
    if ext == "txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == "docx":
        doc = docx.Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == "pdf":
        pdf = PdfReader(filepath)
        return "\n".join([page.extract_text() or "" for page in pdf.pages])
    return ""


def get_translator(src_lang):
    model_name = LANG_TO_MODEL.get(src_lang, LANG_TO_MODEL["default"])
    if model_name not in MODEL_CACHE:
        MODEL_CACHE[model_name] = pipeline("translation", model=model_name)
    return MODEL_CACHE[model_name]


def translate_text_preserve_format(text, src_lang, tgt_lang="en"):
    translator = get_translator(src_lang)

    chunks = [text[i:i + 300] for i in range(0, len(text), 300)]
    translations = []
    for chunk in chunks:
        out = translator(chunk, max_length=512)
        translations.append(out[0]["translation_text"])
    return " ".join(translations)


# Dummy language detector (replace with Groq later)
def detect_language_with_groq(text):
    # very naive check for demo
    if "que" in text or "hola" in text:
        return "es"
    if "olá" in text or "obrigado" in text:
        return "pt"
    if "bonjour" in text:
        return "fr"
    if "danke" in text:
        return "de"
    return "en"


# ---------------------- HTML ----------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Translator</title>
</head>
<body>
    <h2>AI Translator (Multi-Language + Dialects)</h2>
    <form method="POST" enctype="multipart/form-data">
        <p>Upload File (.txt, .docx, .pdf):</p>
        <input type="hidden" name="input_type" value="file">
        <input type="file" name="file">
        <button type="submit">Translate</button>
    </form>
    {% if translated_text %}
        <h3>Detected: {{ detected_lang.upper() }}</h3>
        <p><b>Processing:</b> {{ processing_info }}</p>
        <pre>{{ translated_text }}</pre>
        <a href="{{ download_url }}">Download File</a>
    {% endif %}
</body>
</html>
"""


# ---------------------- Routes ----------------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        input_type = request.form.get("input_type")
        tgt_lang = "en"

        if input_type == "file":
            if "file" not in request.files:
                flash("No file uploaded.", "error")
                return redirect(url_for("home"))

            file = request.files["file"]
            if file.filename == "":
                flash("No file selected.", "error")
                return redirect(url_for("home"))

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                try:
                    start_time = datetime.now()
                    content = read_file_content(filepath)

                    if not content.strip():
                        flash("The uploaded file appears empty.", "error")
                        os.remove(filepath)
                        return redirect(url_for("home"))

                    # Detect language
                    src_lang = detect_language_with_groq(content)

                    # Translate
                    if src_lang == tgt_lang:
                        translated_content = content
                        flash("File already in English.", "success")
                    else:
                        translated_content = translate_text_preserve_format(content, src_lang, tgt_lang)

                    end_time = datetime.now()
                    processing_time = (end_time - start_time).total_seconds()

                    # Save translated file
                    output_filename = f"translated_{filename.rsplit('.',1)[0]}.txt"
                    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(translated_content)

                    os.remove(filepath)  # cleanup

                    return render_template_string(
                        HTML_TEMPLATE,
                        translated_text=translated_content[:2000] + "..." if len(translated_content) > 2000 else translated_content,
                        download_url=url_for("download_file", filename=output_filename),
                        detected_lang=src_lang,
                        processing_info=f"{processing_time:.2f} sec"
                    )

                except Exception as e:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    flash(f"Error processing file: {str(e)}", "error")
                    return redirect(url_for("home"))

    return render_template_string(HTML_TEMPLATE)


@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


# ---------------------- Run ----------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
