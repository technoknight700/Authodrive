from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import io
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
import os
import sys

# This line permanently tells the script where to find the Tesseract program
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- FIREBASE INITIALIZATION ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_key_path = os.path.join(script_dir, "serviceAccountKey.json")
    cred = credentials.Certificate(json_key_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'authodrive.firebasestorage.app'
    })
    db = firestore.client()
    bucket = storage.bucket()
    print("✅ Firebase initialized successfully.")
except Exception as e:
    print(f"❌ FAILED TO INITIALIZE. ERROR: {e}")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

@app.route('/process-license', methods=['POST'])
def process_license():
    if 'file' not in request.files or 'driverName' not in request.form:
        return jsonify({"error": "Missing file or driverName"}), 400

    file = request.files['file']
    driver_name_from_admin = request.form['driverName']
    # --- ADDED: Get the driver type from the form, default to 'Authorized' ---
    driver_type = request.form.get('driverType', 'Authorized')
    
    try:
        img_bytes = file.read()
        img = Image.open(io.BytesIO(img_bytes))
        img = img.convert('L')
        img = ImageEnhance.Contrast(img).enhance(2)
        text = pytesseract.image_to_string(img, config=r'--oem 3 --psm 6')

        def extract_field(txt, keywords):
            for line in txt.split("\n"):
                parts = [p.strip() for p in line.split(":", 1)] if ":" in line else [line.strip()]
                key = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                if any(kw in key.lower() for kw in keywords):
                    if "s/w/d" in keywords and not value:
                        potential_value = key.lower().replace("s/w/d", "").strip()
                        if potential_value: return potential_value.title()
                    return value.strip()
            return ""

        name = extract_field(text, ["name"])
        license_no = extract_field(text, ["license no", "licence no"])
        auth_to_drive = extract_field(text, ["authorisation", "authorization"])
        date_issue = extract_field(text, ["issue"])
        dob = extract_field(text, ["dob", "birth"])
        swd = extract_field(text, ["s/w/d"])
        date_expiry_str = extract_field(text, ["validity", "expiry"])
        present_address = extract_field(text, ["address"])
        
        if "LMV" not in auth_to_drive.upper():
            return jsonify({"error": "Driver not authorized for LMV. Details not stored."}), 403

        expiry_alert = date_expiry_str
        try:
            exp_date = None
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m-%Y"):
                try:
                    exp_date = datetime.strptime(date_expiry_str, fmt)
                    break
                except ValueError:
                    continue
            if exp_date:
                time_left = exp_date - datetime.today()
                if 0 < time_left.days <= 180:
                    expiry_alert = f"{date_expiry_str} (⚠️ Expires in {time_left.days} days)"
                elif time_left.days <= 0:
                    expiry_alert = f"{date_expiry_str} (❌ EXPIRED)"
        except Exception as e:
            print(f"Could not parse date: {date_expiry_str}, Error: {e}")

        if not license_no:
            return jsonify({"error": "Could not extract license number from image"}), 400

        blob = bucket.blob(f"licenses/{license_no}_{file.filename}")
        blob.upload_from_string(img_bytes, content_type=file.content_type)
        image_url = blob.public_url 

        doc_ref = db.collection('drivers').document(license_no)
        doc_ref.set({
            "Name": name or driver_name_from_admin,
            "License No": license_no,
            "Authorization": auth_to_drive,
            "Date of Issue": date_issue,
            "Date of Birth": dob,
            "S/W/D of": swd,
            "Date of Expiry": expiry_alert,
            "Present Address": present_address,
            "License Image": image_url,
            "Last Updated": firestore.SERVER_TIMESTAMP,
            "Rash Driving Incidents": 0,
            "Face Capture URL": "",
            "Status": "Active",
            "Removed Timestamp": None,
            # --- ADDED: Save the driver type to the document ---
            "Driver Type": driver_type
        })
        return jsonify({"success": True, "licenseNo": license_no}), 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)