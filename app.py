import os
from flask import Flask, request, jsonify, send_file
from transformers import pipeline
from werkzeug.utils import secure_filename
from docx import Document
import fitz  # PyMuPDF for PDF handling

# Initialize Flask app
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/tmp"

# Load translation pipelines
translators = {
    "es-en": pipeline("translation", model="Helsinki-NLP/opus-mt-es-en"),  # Spanish → English
    "pt-en": pipeline("translation", model="Helsinki-NLP/opus-mt-pt-en"),  # Portuguese → English
    "fr-en": pipeline("translation", model="Helsinki-NLP/opus-mt-fr-en"),  # French → English
}

@app.route("/", methods=["GET"])
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Language Translator</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 700px; margin: auto; }
        textarea, input[type=file] { width: 100%; margin-bottom: 10px; }
        textarea { height: 80px; }
        select, button { padding: 10px; margin: 10px 0; }
        .result { font-weight: bold; margin-top: 20px; white-space: pre-wrap; }
      </style>
    </head>
    <body>
      <h1>🌍 Language Translator</h1>
      
      <h3>Translate Text</h3>
      <textarea id="inputText" placeholder="Type text here..."></textarea><br>
      
      <label for="lang">Choose language:</label>
      <select id="lang">
        <option value="es-en">Spanish → English</option>
        <option value="pt-en">Portuguese → English</option>
        <option value="fr-en">French → English</option>
      </select><br>
      
      <button onclick="translateText()">Translate Text</button>
      
      <h3>Translate File (.txt, .pdf, .docx)</h3>
      <input type="file" id="fileInput" accept=".txt,.pdf,.docx"><br>
      <button onclick="translateFile()">Translate File</button>
      
      <div class="result" id="result"></div>

      <script>
        async function translateText() {
          const text = document.getElementById("inputText").value;
          const lang = document.getElementById("lang").value;
          const response = await fetch("/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, lang: lang })
          });
          const data = await response.json();
          document.getElementById("result").innerText = data.translation || data.error;
        }

        async function translateFile() {
          const file = document.getElementById("fileInput").files[0];
          const lang = document.getElementById("lang").value;
          if (!file) {
            alert("Please select a file first!");
            return;
          }
          const formData = new FormData();
          formData.append("file", file);
          formData.append("lang", lang);

          const response = await fetch("/translate-file", {
            method: "POST",
            body: formData
          });

          if (response.headers.get("Content-Type").includes("application/json")) {
            const data = await response.json();
            document.getElementById("result").innerText = data.translation || data.error;
          } else {
            // File download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = file.name.replace(/(\.\w+)$/, "_translated$1");
            document.body.appendChild(a);
            a.click();
            a.remove();
            document.getElementById("result").innerText = "✅ File translated and downloaded!";
          }
        }
      </script>
    </body>
    </html>
    """

@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.get_json()
    text = data.get("text", "")
    lang = data.get("lang", "es-en")

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if lang not in translators:
        return jsonify({"error": f"Unsupported language pair: {lang}"}), 400

    result = translators[lang](text)
    return jsonify({"input": text, "translation": result[0]["translation_text"]})

@app.route("/translate-file", methods=["POST"])
def translate_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    lang = request.form.get("lang", "es-en")
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    file.save(filepath)

    try:
        if ext == ".txt":
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            result = translators[lang](text)
            translated_text = result[0]["translation_text"]

            output_path = filepath.replace(".txt", "_translated.txt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            return send_file(output_path, as_attachment=True)

        elif ext == ".pdf":
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n"
            doc.close()
            result = translators[lang](text)
            translated_text = result[0]["translation_text"]

            output_path = filepath.replace(".pdf", "_translated.txt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            return send_file(output_path, as_attachment=True)

        elif ext == ".docx":
            document = Document(filepath)
            for para in document.paragraphs:
                if para.text.strip():
                    result = translators[lang](para.text)
                    para.text = result[0]["translation_text"]

            output_path = filepath.replace(".docx", "_translated.docx")
            document.save(output_path)
            return send_file(output_path, as_attachment=True)

        else:
            return jsonify({"error": "Unsupported file type"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
