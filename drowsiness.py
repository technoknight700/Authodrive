# drowsy_pi.py
import time
import csv
import os
import argparse
from datetime import datetime
 
import cv2
import numpy as np
 
# Attempt to import GPIO (works on Raspberry Pi)
try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None
    print("Warning: RPi.GPIO not available. Running in simulation mode (no buzzer).")
 
# Attempt optional MQTT (for Admin Dashboard integration)
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except Exception:
    MQTT_AVAILABLE = False
 
# Optional: use mediapipe for face mesh
import mediapipe as mp
 
# ---------------- Configuration ----------------
BUZZER_PIN = 18           # BCM pin for buzzer
EAR_THRESHOLD = 0.25      # below this -> eye considered closed
CONSEC_FRAMES = 20        # how many consecutive frames of low EAR to trigger alarm
BUZZ_DURATION = 1.0       # buzzer on duration in seconds
LOG_CSV = "drowsy_log.csv"  # event log
HEADLESS = False          # if True, no cv2.imshow window (useful for in-car)
CAMERA_ID = 0             # default camera
MQTT_BROKER = None        # set to "ip_or_host" to enable MQTT publishing
MQTT_TOPIC = "vehicle/drowsiness"  # topic for messages if MQTT enabled
# ------------------------------------------------
 
# Face mesh eye landmark index sets for MediaPipe
LEFT_EYE_IDX  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
 
mp_face_mesh = mp.solutions.face_mesh
 
# ----------------- Helpers --------------------
def init_gpio():
    if GPIO is None:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
 
def buzz(seconds=1.0):
    if GPIO is None:
        print("[SIM] Buzz for", seconds, "s")
        return
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(seconds)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
 
def euclidean(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))
 
def eye_aspect_ratio(eye):
    # eye: 6 points p0..p5
    p0, p1, p2, p3, p4, p5 = eye
    A = euclidean(p1, p5)
    B = euclidean(p2, p4)
    C = euclidean(p0, p3)
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)
 
def log_event(timestamp, ear, status):
    header = ["timestamp", "ear", "status"]
    write_header = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow([timestamp, f"{ear:.4f}" if ear is not None else "", status])
 
def mqtt_publish(client, topic, payload):
    if not MQTT_AVAILABLE or client is None:
        return
    try:
        client.publish(topic, payload, qos=1)
    except Exception as e:
        print("MQTT publish failed:", e)
 
# Hook placeholders for integration points (you'll fill these)
def check_driver_authorization():
    """
    Placeholder - return True if driver is authorized.
    Integrate your fingerprint/face auth here.
    """
    return True
 
def check_sobriety():
    """
    Placeholder - implement sobriety check (alcohol sensor, breathalyzer)
    Return True if sober, False if not sober.
    """
    return True
 
def send_alert_to_dashboard(mqtt_client, status, extra=None):
    payload = {"ts": datetime.utcnow().isoformat(), "status": status}
    if extra:
        payload.update(extra)
    # Convert to string (or JSON if you import json)
    mqtt_publish(mqtt_client, MQTT_TOPIC, str(payload))
 
# ----------------- Main -----------------------
def main(args):
    global HEADLESS, MQTT_BROKER
    HEADLESS = args.headless
    MQTT_BROKER = args.mqtt
 
    init_gpio()
 
    # Setup MQTT client if configured
    mqtt_client = None
    if MQTT_BROKER and MQTT_AVAILABLE:
        mqtt_client = mqtt.Client()
        try:
            mqtt_client.connect(MQTT_BROKER, 1883, 60)
            mqtt_client.loop_start()
            print("Connected to MQTT broker:", MQTT_BROKER)
        except Exception as e:
            print("Could not connect to MQTT broker:", e)
            mqtt_client = None
    elif MQTT_BROKER and not MQTT_AVAILABLE:
        print("MQTT broker set but paho-mqtt not installed. Install paho-mqtt to enable.")
 
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print("ERROR: Could not open camera. If headless, ensure camera is connected and accessible.")
        return
 
    counter = 0
    alarm_last_time = 0
 
    # Check pre-conditions (authorization & sobriety) - quick example
    authorized = check_driver_authorization()
    sober = check_sobriety()
    if not authorized:
        print("Driver not authorized. Aborting detection.")
        # you could send message to dashboard here
        send_alert_to_dashboard(mqtt_client, "unauthorized_driver")
        cap.release()
        return
    if not sober:
        print("Driver failed sobriety check.")
        send_alert_to_dashboard(mqtt_client, "failed_sobriety")
        cap.release()
        return
 
    with mp_face_mesh.FaceMesh(max_num_faces=1,
                               refine_landmarks=True,
                               min_detection_confidence=0.5,
                               min_tracking_confidence=0.5) as face_mesh:
 
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera frame not received — stopping.")
                break
 
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
 
            ear_val = None
            status = "No face"
            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                pts = [(lm.x * w, lm.y * h) for lm in landmarks]
 
                try:
                    left_eye = [pts[i] for i in LEFT_EYE_IDX]
                    right_eye = [pts[i] for i in RIGHT_EYE_IDX]
                    left_ear = eye_aspect_ratio(left_eye)
                    right_ear = eye_aspect_ratio(right_eye)
                    ear_val = (left_ear + right_ear) / 2.0
 
                    # simple smoothing: optional, you can add exponential or moving average
                    if ear_val < EAR_THRESHOLD:
                        counter += 1
                    else:
                        counter = 0
 
                    if counter >= CONSEC_FRAMES:
                        status = "Drowsy"
                        now = time.time()
                        # Simple cooldown to prevent continuous buzzing
                        if now - alarm_last_time > (BUZZ_DURATION + 1.0):
                            print("Drowsiness detected -> buzzing and logging.")
                            buzz(BUZZ_DURATION)
                            alarm_last_time = now
                            ts = datetime.utcnow().isoformat()
                            log_event(ts, ear_val, status)
                            send_alert_to_dashboard(mqtt_client, status, extra={"ear": ear_val})
                    else:
                        status = "Awake"
                except Exception as e:
                    status = f"Error processing landmarks: {e}"
 
            # Logging even non-alarm frames at low frequency (every 5s)
            # (adjust or remove if too chatty)
            if int(time.time()) % 5 == 0:
                log_event(datetime.utcnow().isoformat(), ear_val if ear_val is not None else 0.0, status)
 
            # Display for debugging unless headless
            if not HEADLESS:
                disp = frame.copy()
                cv2.putText(disp, f"Status: {status}", (10,30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                            (0,0,255) if status=="Drowsy" else (0,255,0), 2)
                if ear_val is not None:
                    cv2.putText(disp, f"EAR: {ear_val:.3f}", (10,60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
                cv2.imshow("Drowsiness Monitor", disp)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # in headless mode, just print periodically
                print(f"[{datetime.utcnow().isoformat()}] Status: {status} EAR: {ear_val}")
                # tiny sleep to avoid overwhelming CPU prints
                time.sleep(0.1)
 
    cap.release()
    if not HEADLESS:
        cv2.destroyAllWindows()
    if mqtt_client:
        mqtt_client.loop_stop()
    if GPIO:
        GPIO.cleanup()
    print("Exited cleanly.")
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raspberry Pi Drowsiness Detector")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (no imshow)")
    parser.add_argument("--mqtt", type=str, default=None, help="Optional MQTT broker host to publish events")
    parser.add_argument("--camera", type=int, default=0, help="Camera ID")
    args = parser.parse_args()
    CAMERA_ID = args.camera
    main(args)
 