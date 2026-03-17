import cv2
from ultralytics import YOLO
import insightface
import numpy as np
import os
import pickle
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS

# ----------------------------
# 1. Initialization
# ----------------------------
print("Initializing Flask app...")
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

print("Loading YOLOv10 model...")
# Use a lightweight model suitable for server deployment
yolo_model = YOLO("yolov10n.pt")

print("Loading InsightFace model...")
# Using CPU provider for broader compatibility on EC2 instances without a GPU
face_analyzer = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider'])
face_analyzer.prepare(ctx_id=0, det_size=(640, 640))
print("✅ Models loaded")

# Path to our 'database' file
DB_PATH = "known_faces.pkl"
known_faces = {}

# ----------------------------
# 2. Helper Functions
# ----------------------------

def load_known_faces():
    """Load the face database from a pickle file."""
    global known_faces
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'rb') as f:
            known_faces = pickle.load(f)
        print(f"✅ Loaded {len(known_faces)} known faces from {DB_PATH}")
    else:
        print("⚠️ No existing face database found. Starting fresh.")

def save_known_faces():
    """Save the current face database to a pickle file."""
    with open(DB_PATH, 'wb') as f:
        pickle.dump(known_faces, f)
    print(f"✅ Saved {len(known_faces)} faces to {DB_PATH}")

def decode_image_from_base64(base64_string):
    """Decode a base64 string to an OpenCV image."""
    # The string will be in the format 'data:image/png;base64,iVBORw0KGgo...'
    # We need to strip the header
    header, encoded = base64_string.split(",", 1)
    decoded_data = base64.b64decode(encoded)
    np_arr = np.frombuffer(decoded_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

# ----------------------------
# 3. Flask API Endpoints
# ----------------------------

@app.route('/register', methods=['POST'])
def register_face():
    """
    Registers a new face. Expects JSON payload with 'name' and 'image' (base64).
    """
    data = request.json
    name = data.get('name')
    image_data = data.get('image')

    if not name or not image_data:
        return jsonify({"status": "error", "message": "Missing name or image data"}), 400

    try:
        img = decode_image_from_base64(image_data)
        if img is None:
             return jsonify({"status": "error", "message": "Invalid image data"}), 400

        # Get face embedding
        faces = face_analyzer.get(img)

        if len(faces) == 0:
            return jsonify({"status": "error", "message": "No face detected in the image."}), 400
        if len(faces) > 1:
            return jsonify({"status": "error", "message": "Multiple faces detected. Please provide an image with only one face."}), 400

        # Store the normalized embedding
        embedding = faces[0].normed_embedding
        known_faces[name] = embedding
        save_known_faces()

        print(f"✅ Registered {name}")
        return jsonify({"status": "success", "message": f"Successfully registered {name}"})

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"status": "error", "message": f"An server error occurred: {e}"}), 500


@app.route('/recognize', methods=['POST'])
def recognize_face():
    """
    Recognizes faces in an image frame. Expects 'image' (base64).
    """
    image_data = request.json.get('image')
    if not image_data:
        return jsonify({"status": "error", "message": "Missing image data"}), 400

    try:
        frame = decode_image_from_base64(image_data)
        if frame is None:
            return jsonify({"status": "error", "message": "Invalid image data"}), 400

        recognized_people = []
        threshold = 0.45  # Recognition confidence threshold

        # Use YOLO to find potential faces (or people) first
        results = yolo_model(frame, classes=[0], verbose=False) # class 0 is 'person' in COCO

        for r in results:
            for box in r.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, box[:4])
                face_crop = frame[y1:y2, x1:x2]

                if face_crop.size == 0:
                    continue

                # Get embedding for the cropped face
                faces = face_analyzer.get(face_crop)
                if len(faces) > 0:
                    emb = faces[0].normed_embedding
                    name = "Unknown"
                    best_score = -1

                    # Compare with all known faces
                    for k, v in known_faces.items():
                        sim = np.dot(emb, v)  # Cosine similarity
                        if sim > best_score:
                            best_score, name = sim, k
                    
                    if best_score < threshold:
                        name = "Unknown"

                    recognized_people.append({
                        "box": [x1, y1, x2, y2],
                        "name": name,
                        "score": float(best_score)
                    })

        return jsonify({"status": "success", "results": recognized_people})

    except Exception as e:
        print(f"Error during recognition: {e}")
        return jsonify({"status": "error", "message": "An error occurred during recognition"}), 500


# ----------------------------
# 4. Main Execution
# ----------------------------
if __name__ == '__main__':
    load_known_faces()
    # Host on 0.0.0.0 to make it accessible on the network for deployment
    app.run(host='0.0.0.0', port=5000)