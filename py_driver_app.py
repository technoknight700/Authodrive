from flask import Flask, request, jsonify, render_template
import pytesseract
from PIL import Image
import pdfplumber
import re
import os
from pdf2image import convert_from_bytes

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_text_from_file(filepath):
    text = ""
    if filepath.lower().endswith(".pdf"):
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    text += page.extract_text() + "\n"
        # fallback OCR if no text
        if not text.strip():
            images = convert_from_bytes(open(filepath, "rb").read())
            for img in images:
                text += pytesseract.image_to_string(img) + "\n"
    else:  # jpg/png/jpeg
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
    return text

def parse_license_details(text):
    details = {
        "Name": None,
        "DOB": None,
        "License No": None,
        "Address": None,
        "Validity": None
    }

    # Simple regex-based extraction (tune based on license format)
    name_match = re.search(r"Name[:\s]+([A-Za-z\s]+)", text)
    dob_match = re.search(r"(\d{2}[-/]\d{2}[-/]\d{4})", text)
    lic_match = re.search(r"[A-Z]{2}\d{2}\s?\d{11}", text)
    addr_match = re.search(r"Address[:\s]+([\w\s,.-]+)", text)
    val_match = re.search(r"Valid(?:ity)?[:\s]+([\d-/]+)", text)

    if name_match: details["Name"] = name_match.group(1).strip()
    if dob_match: details["DOB"] = dob_match.group(1).strip()
    if lic_match: details["License No"] = lic_match.group(0).strip()
    if addr_match: details["Address"] = addr_match.group(1).strip()
    if val_match: details["Validity"] = val_match.group(1).strip()

    return details

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    text = extract_text_from_file(filepath)
    details = parse_license_details(text)

    return jsonify(details)

if __name__ == "__main__":
    app.run(debug=True)

