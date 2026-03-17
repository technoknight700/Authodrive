from flask import Flask, jsonify, request
# You will need to install Flask on your Raspberry Pi: pip install Flask
# You will also need to install the pyfingerprint library: pip install pyfingerprint
# Note: You will need to replace the database logic with your actual Firebase setup.
from pyfingerprint.pyfingerprint import PyFingerprint
import time

app = Flask(__name__)

# Initialize the fingerprint sensor.
# The device path might be different depending on your setup.
# You may need to use /dev/ttyS0 or /dev/ttyUSB0.
try:
    f = PyFingerprint('/dev/ttyUSB0', 57600)
    if not f.verifyPassword():
        raise ValueError('Sensor not found or password incorrect.')
    print('Fingerprint sensor initialized.')
except Exception as e:
    print(f"Error initializing sensor: {e}")
    f = None

@app.route('/api/fingerprint/enroll/<int:id>', methods=['GET'])
def enroll(id):
    """Enrolls a new fingerprint with the given ID."""
    if not f:
        return jsonify({"success": False, "error": "Fingerprint sensor not initialized."})
    try:
        print(f'Waiting for finger to enroll with ID {id}...')
        
        # Step 1: Wait for a finger to be placed on the sensor
        while f.get_fpdata(timeout=1) == -1:
            pass
        
        # Step 2: Capture the first image
        print('Finger detected. Place the same finger again to confirm.')
        if not f.capture_finger(1):
            return jsonify({"success": False, "error": "Failed to capture first image."})
        
        # Step 3: Wait for the same finger to be placed again
        while f.get_fpdata(timeout=1) == -1:
            pass
            
        # Step 4: Capture the second image and enroll the fingerprint
        if not f.capture_finger(2):
            return jsonify({"success": False, "error": "Failed to capture second image."})
            
        enrollment_status = f.enroll_finger(id)
        
        if enrollment_status == f.ACK_SUCCESS:
            # Here you would connect to your Firebase to store the enrollment ID.
            return jsonify({"success": True, "message": f"Fingerprint enrolled successfully with ID: {id}"})
        else:
            return jsonify({"success": False, "error": f"Enrollment failed with status code: {enrollment_status}"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/fingerprint/verify', methods=['GET'])
def verify():
    """Verifies a fingerprint and returns the matching ID."""
    if not f:
        return jsonify({"success": False, "error": "Fingerprint sensor not initialized."})
    try:
        print('Waiting for finger to verify...')
        
        # Wait for a finger to be placed on the sensor
        while f.get_fpdata(timeout=1) == -1:
            pass
            
        # Identify the fingerprint
        fid = f.identify_finger()
        
        if fid > -1:
            # Here you would connect to your Firebase to verify the user with the ID.
            return jsonify({"success": True, "message": f"Fingerprint verified. ID: {fid}"})
        else:
            return jsonify({"success": False, "error": "No match found."})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
