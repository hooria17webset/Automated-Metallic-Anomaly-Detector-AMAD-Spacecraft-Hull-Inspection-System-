import cv2
import numpy as np
import time
import os
import threading
import base64
import requests
import queue
import pandas as pd
import matplotlib
matplotlib.rcParams['toolbar'] = 'None'
import matplotlib.pyplot as plt

# Platform-safe audio setup
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    import winsound

def play_alarm_async(frequency, duration):
    if IS_WINDOWS:
        threading.Thread(target=winsound.Beep, args=(frequency, duration), daemon=True).start()

print("======================================================================")
print(" ⚡ MGR-4-M AUTOMATED HIGH-RESOLUTION ANALYTICS CORE v10.6          ")
print("======================================================================")

# -----------------------------------------------------------------
# ROBOFLOW OPTIMIZED CONFIGURATION
# -----------------------------------------------------------------
API_KEY = "LEpZy0aSpVmakeRuofBq"
WORKSPACE = "hoorias-workspace"
WORKFLOW_ID = "spacecraft-metal-detection"
URL = f"https://serverless.roboflow.com/infer/workflows/{WORKSPACE}/{WORKFLOW_ID}?confidence=40"

STRICT_METAL_LABELS = ["defect", "crack", "scratch", "hole", "pitting", "damage", "metal_defect", "rough_surface", "surface", "metal"]

# -----------------------------------------------------------------
# DIRECTORIES SETUP
# -----------------------------------------------------------------
BASE_DIR = r"D:\ISSP2026\issp proj\spacecraft_metal_data"
REPORT_DIR = os.path.join(BASE_DIR, "Inspection_Reports")
SNAPSHOT_DIR = os.path.join(BASE_DIR, "Defect_Snapshots")

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

inspection_log = []

# -----------------------------------------------------------------
# HARDWARE SUBSYSTEM INITIALIZATION (UNTOUCHED)
# -----------------------------------------------------------------
RUNNING_ON_PI = False
try:
    import RPi.GPIO as GPIO
    RUNNING_ON_PI = True
    print("[HARDWARE] Genuine Raspberry Pi GPIO subsystem detected.")
except (ImportError, RuntimeError):
    print("[SIMULATION] Running in Stable Lag-Free Emulation Mode.")

PIN_SAFE_LED = 18    
PIN_ALERT_LED = 23   
PIN_BUZZER = 24      
PIN_VACUUM_RELAY = 25  
PIN_MAGNET_MOSFET = 12 

if RUNNING_ON_PI:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [PIN_SAFE_LED, PIN_ALERT_LED, PIN_BUZZER, PIN_VACUUM_RELAY, PIN_MAGNET_MOSFET]:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(PIN_SAFE_LED, GPIO.HIGH)

# -----------------------------------------------------------------
# CAMERA ARRAY FEED & QUEUE MANAGEMENT (ZERO LAG)
# -----------------------------------------------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Error: Could not open camera array.")
    exit()

frame_queue = queue.Queue(maxsize=1)
predictions_cache = []
anomaly_detected = False
is_running = True
last_beep_time = 0
last_screenshot_time = 0
SCREENSHOT_COOLDOWN = 2.0  

def assess_severity(label, confidence):
    lbl = label.lower()
    if "crack" in lbl or "hole" in lbl or "destroyed" in lbl or confidence > 0.85:
        return "DESTROYED / DAMAGE"
    elif "defect" in lbl or "damage" in lbl or confidence > 0.65:
        return "CRITICAL"
    else:
        return "MODERATE"

# --- ASYNC HIGH-SPEED DETAILED WORKER ---
def detailed_precision_core_worker():
    global is_running, anomaly_detected, predictions_cache, last_screenshot_time
    
    while is_running:
        try:
            full_frame = frame_queue.get(timeout=0.1)
            
            _, buffer = cv2.imencode('.jpg', full_frame)
            image_base64 = base64.b64encode(buffer).decode("utf-8")

            payload = {
                "api_key": API_KEY,
                "workspace_name": WORKSPACE,
                "workflow_id": WORKFLOW_ID,
                "inputs": {"image": {"type": "base64", "value": image_base64}},
            }

            response = requests.post(URL, json=payload, timeout=3)
            if response.status_code == 200:
                res_json = response.json()
                if "outputs" in res_json and len(res_json["outputs"]) > 0:
                    raw_preds = res_json["outputs"][0].get("predictions", {}).get("predictions", [])
                    
                    valid_precision_preds = []
                    for p in raw_preds:
                        detected_class = str(p.get("class", "")).lower()
                        box_area = p["width"] * p["height"]
                        
                        if any(word in detected_class for word in STRICT_METAL_LABELS) and (100 < box_area < 55000):
                            valid_precision_preds.append(p)
                    
                    predictions_cache = valid_precision_preds
                    anomaly_detected = len(valid_precision_preds) > 0
                    
                    timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    if anomaly_detected:
                        primary_fault = valid_precision_preds[0]
                        fault_label = primary_fault.get("class", "metal_defect").upper()
                        fault_conf = float(primary_fault.get("confidence", 0.0))
                        severity_level = assess_severity(fault_label, fault_conf)
                        
                        current_time = time.time()
                        if current_time - last_screenshot_time > SCREENSHOT_COOLDOWN:
                            marked_frame = full_frame.copy()
                            for pred in valid_precision_preds:
                                x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
                                p_label = pred.get("class", "metal_defect").upper()
                                p_conf = float(pred.get("confidence", 0.0))
                                p_severity = assess_severity(p_label, p_conf)

                                left = int(x - (w / 2))
                                top = int(y - (h / 2))
                                right = int(x + (w / 2))
                                bottom = int(y + (h / 2))

                                cv2.rectangle(marked_frame, (left, top), (right, bottom), (0, 0, 255), 3)
                                cv2.putText(marked_frame, f"{p_label} ({p_conf*100:.1f}%) - {p_severity}", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            ss_filename = f"MARKED_DEFECT_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                            ss_path = os.path.join(SNAPSHOT_DIR, ss_filename)
                            cv2.imwrite(ss_path, marked_frame)
                            print(f"📸 Saved: {ss_filename} | Severity: {severity_level}")
                            last_screenshot_time = current_time
                        
                        inspection_log.append({
                            "Timestamp": timestamp_str,
                            "Status": "CRITICAL FAULT",
                            "Detected Fault Type": fault_label,
                            "Confidence Score": f"{fault_conf*100:.2f}%",
                            "Severity Level": severity_level,
                            "Total Anomalies Present": len(valid_precision_preds)
                        })
                    else:
                        inspection_log.append({
                            "Timestamp": timestamp_str,
                            "Status": "NOMINAL SURFACE",
                            "Detected Fault Type": "NONE",
                            "Confidence Score": "0.00%",
                            "Severity Level": "SAFE",
                            "Total Anomalies Present": 0
                        })
            
            frame_queue.task_done()
        except queue.Empty:
            continue
        except Exception:
            pass
        time.sleep(0.01)

threading.Thread(target=detailed_precision_core_worker, daemon=True).start()

# TELEMETRY DISPLAY MONITOR CONFIGURATION
plt.ion()
fig, ax = plt.subplots(figsize=(11.25, 5.0)) 
fig.canvas.manager.set_window_title("MGR-4-M Absolute Inspection Hardware Telemetry Dashboard")
fig.patch.set_facecolor('#100C0A')
ax.set_facecolor('#100C0A')
plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

try:
    while plt.fignum_exists(fig.number):
        start_tick = time.time()
        
        ret, frame = cap.read()
        if not ret:
            break
            
        raw_frame = cv2.resize(frame, (640, 480))
        processing_frame = raw_frame.copy()

        if frame_queue.full():
            try: frame_queue.get_nowait()
            except queue.Empty: pass
        try: frame_queue.put_nowait(raw_frame)
        except queue.Full: pass

        # ---------------- RENDERING LIVE MONITOR BOUNDS ----------------
        current_preds = predictions_cache.copy()
        if len(current_preds) > 0:
            for pred in current_preds:
                x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
                label = pred.get("class", "metal_defect").upper()
                conf = float(pred.get("confidence", 0.0))
                sev = assess_severity(label, conf)

                left = int(x - (w / 2))
                top = int(y - (h / 2))
                right = int(x + (w / 2))
                bottom = int(y + (h / 2))

                cv2.rectangle(processing_frame, (left, top), (right, bottom), (0, 0, 255), 3)
                cv2.putText(processing_frame, f"{label} ({conf*100:.1f}%) - {sev}", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        # ---------------- ORIGINAL HARDWARE LOGIC ----------------
        if anomaly_detected:
            vacuum_state = False   
            magnet_state = True    
            if RUNNING_ON_PI:
                GPIO.output(PIN_SAFE_LED, GPIO.LOW)
                GPIO.output(PIN_ALERT_LED, GPIO.HIGH)
                GPIO.output(PIN_BUZZER, GPIO.HIGH)
            else:
                if time.time() - last_beep_time > 0.12:
                    play_alarm_async(2200, 120) 
                    last_beep_time = time.time()
        else:
            vacuum_state = True    
            magnet_state = False   
            if RUNNING_ON_PI:
                GPIO.output(PIN_SAFE_LED, GPIO.HIGH)
                GPIO.output(PIN_ALERT_LED, GPIO.LOW)
                GPIO.output(PIN_BUZZER, GPIO.LOW)

        # ---------------- UNTOUCHED STABLE SIMULATION PANEL ----------------
        canvas = np.zeros((480, 720, 3), dtype=np.uint8)
        canvas[:] = [16, 12, 10] 
        for x in range(0, 720, 20): cv2.line(canvas, (x, 0), (x, 480), (24, 20, 16), 1)
        for y in range(0, 480, 20): cv2.line(canvas, (0, y), (720, y), (24, 20, 16), 1)
        cv2.rectangle(canvas, (240, 110), (540, 420), (45, 85, 20), -1)
        cv2.rectangle(canvas, (240, 110), (540, 420), (80, 140, 40), 2)
        cv2.putText(canvas, "RASPBERRY PI 4 MAINBOARD", (255, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.rectangle(canvas, (320, 160), (400, 230), (40, 38, 35), -1)
        cv2.putText(canvas, "BCM2711", (332, 198), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
        cv2.rectangle(canvas, (255, 370), (525, 405), (20, 20, 20), -1)
        cv2.rectangle(canvas, (255, 370), (525, 405), (60, 60, 60), 1)
        cv2.putText(canvas, "J8 GPIO HEADER (PIN 1-40)", (255, 362), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (140, 140, 140), 1)
        
        pin_positions = {}
        pin_index = 1
        for col_x in range(265, 520, 13):
            cv2.circle(canvas, (col_x, 378), 3, (214, 174, 94), -1)
            pin_positions[pin_index] = (col_x, 378)
            pin_index += 2
        pin_index = 2
        for col_x in range(265, 520, 13):
            cv2.circle(canvas, (col_x, 395), 3, (180, 180, 180), -1)
            pin_positions[pin_index] = (col_x, 395)
            pin_index += 2

        cv2.rectangle(canvas, (425, 275), (525, 335), (75, 40, 15), -1)
        cv2.rectangle(canvas, (425, 275), (525, 335), (130, 85, 35), 1)
        cv2.putText(canvas, "PDU REGULATOR", (430, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        pwr_txt = "5V @ 1.50A" if anomaly_detected else "5V @ 0.95A"
        cv2.putText(canvas, pwr_txt, (430, 312), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)

        buzz_ui_color = (68, 126, 219) if anomaly_detected else (40, 40, 40)
        cv2.rectangle(canvas, (20, 25), (140, 75), buzz_ui_color, -1)
        cv2.rectangle(canvas, (20, 25), (140, 75), (160, 160, 160), 1)
        cv2.putText(canvas, "BUZZER (GPIO 24)", (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)
        cv2.putText(canvas, "CRITICAL" if anomaly_detected else "SILENT", (45, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0,0,255) if anomaly_detected else (140,140,140), 1)

        led_ui_color = (0, 0, 255) if anomaly_detected else (25, 25, 55)
        cv2.circle(canvas, (80, 130), 12, led_ui_color, -1)
        cv2.putText(canvas, "ALERT LED (GPIO 23)", (22, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150, 150, 255), 1)

        vac_ui_color = (20, 55, 20) if anomaly_detected else (0, 210, 0)
        cv2.rectangle(canvas, (20, 185), (140, 235), vac_ui_color, -1)
        cv2.rectangle(canvas, (20, 185), (140, 235), (160, 160, 160), 1)
        cv2.putText(canvas, "VACUUM (GPIO 25)", (25, 202), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255,255,255) if anomaly_detected else (0,0,0), 1)
        cv2.putText(canvas, "RUNNING" if vacuum_state else "TRIPPED", (40, 222), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140,140,140) if anomaly_detected else (0,0,0), 1)

        mag_ui_color = (0, 0, 255) if magnet_state else (40, 40, 40)
        cv2.rectangle(canvas, (20, 265), (140, 315), mag_ui_color, -1)
        cv2.rectangle(canvas, (20, 265), (140, 315), (160, 160, 160), 1)
        cv2.putText(canvas, "MAGNET (GPIO 12)", (25, 282), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)
        cv2.putText(canvas, "ENGAGED" if magnet_state else "DISARMED", (35, 302), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0,255,0) if magnet_state else (140,140,140), 1)

        pin_24_xy = pin_positions[18] 
        pin_23_xy = pin_positions[16]  
        pin_25_xy = pin_positions[22]  
        pin_12_xy = pin_positions[32]  

        w1_c = (0, 180, 255) if anomaly_detected else (45, 40, 35)
        cv2.line(canvas, (140, 50), (220, 50), w1_c, 2)
        cv2.line(canvas, (220, 50), (220, 345), w1_c, 2)
        cv2.line(canvas, (220, 345), (pin_24_xy[0], 345), w1_c, 2)
        cv2.line(canvas, (pin_24_xy[0], 345), (pin_24_xy[0], pin_24_xy[1]), w1_c, 2)

        w2_c = (0, 0, 255) if anomaly_detected else (45, 35, 35)
        cv2.line(canvas, (92, 130), (210, 130), w2_c, 2)
        cv2.line(canvas, (210, 130), (210, 352), w2_c, 2)
        cv2.line(canvas, (210, 352), (pin_23_xy[0], 352), w2_c, 2)
        cv2.line(canvas, (pin_23_xy[0], 352), (pin_23_xy[0], pin_23_xy[1]), w2_c, 2)

        w3_c = (0, 120, 0) if vacuum_state else (40, 50, 40)
        cv2.line(canvas, (140, 210), (200, 210), w3_c, 2)
        cv2.line(canvas, (200, 210), (200, 358), w3_c, 2)
        cv2.line(canvas, (200, 358), (pin_25_xy[0], 358), w3_c, 2)
        cv2.line(canvas, (pin_25_xy[0], 358), (pin_25_xy[0], pin_25_xy[1]), w3_c, 2)

        w4_c = (255, 0, 255) if magnet_state else (50, 40, 50)
        cv2.line(canvas, (140, 290), (190, 290), w4_c, 2)
        cv2.line(canvas, (190, 290), (190, 364), w4_c, 2)
        cv2.line(canvas, (190, 364), (pin_12_xy[0], 364), w4_c, 2)
        cv2.line(canvas, (190, 364), (pin_12_xy[0], pin_12_xy[1]), w4_c, 2)

        # ---------------- SIDE MONITOR RENDERING PANEL ----------------
        view_upper = cv2.resize(processing_frame, (360, 240))
        if anomaly_detected: cv2.rectangle(view_upper, (5, 5), (355, 235), (0, 0, 255), 2)

        view_lower = np.zeros((240, 360, 3), dtype=np.uint8) + 20
        latency_ms = (time.time() - start_tick) * 1000 
        
        cv2.putText(view_lower, "DETAILED DIAGNOSTIC COMPILER", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 150), 1)
        cv2.putText(view_lower, f"Surface Faults: {len(current_preds)}", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,0,255) if anomaly_detected else (0,255,0), 1)
        cv2.putText(view_lower, f"Realtime Loop: {1000/latency_ms:.1f} FPS" if latency_ms > 0 else "N/A", (15, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
        cv2.putText(view_lower, "Log Status: ACTIVE DETAILED ENGINE", (15, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 165, 255), 1)
        
        right_monitoring_panel = cv2.vconcat([view_upper, view_lower])
        unified_dashboard = cv2.hconcat([canvas, right_monitoring_panel])
        rgb_dashboard = cv2.cvtColor(unified_dashboard, cv2.COLOR_BGR2RGB)
        
        ax.clear()
        ax.imshow(rgb_dashboard)
        ax.axis('off')
        fig.canvas.draw()
        fig.canvas.flush_events()
        time.sleep(0.002)

finally:
    is_running = False
    cap.release()
    
    # ADVANCED AUTO-FORMATTED DETAILED EXCEL REPORT GENERATION
    if len(inspection_log) > 0:
        df = pd.DataFrame(inspection_log)
        excel_path = os.path.join(REPORT_DIR, "Detailed_Inspection_Telemetry.xlsx")
        
        # Saving with engine openpyxl
        writer = pd.ExcelWriter(excel_path, engine='openpyxl')
        df.to_excel(writer, sheet_name='Telemetry_Log', index=False)
        
        # Auto-adjust columns layout dynamically using openpyxl properties
        workbook  = writer.book
        worksheet = writer.sheets['Telemetry_Log']
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
        writer.close()
        print(f"\n📊 [REPORT COMPLETE] Advanced Formatted Excel Saved: {excel_path}")
        
        total_records = len(df)
        critical_count = len(df[df["Severity Level"] == "CRITICAL"])
        destroyed_count = len(df[df["Severity Level"] == "DESTROYED / DAMAGE"])
        moderate_count = len(df[df["Severity Level"] == "MODERATE"])
        
        detailed_txt_path = os.path.join(REPORT_DIR, "Detailed_Summary.txt")
        with open(detailed_txt_path, "w") as f:
            f.write("===============================================\n")
            f.write("   MGR-4-M HIGH-RESOLUTION DETAILED REPORT     \n")
            f.write("===============================================\n")
            f.write(f"Timestamp            : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Evaluated Scans: {total_records}\n")
            f.write(f"Moderate Anomalies   : {moderate_count}\n")
            f.write(f"Critical Anomalies   : {critical_count}\n")
            f.write(f"Destroyed/Damaged    : {destroyed_count}\n")
            f.write("-----------------------------------------------\n")
            f.write(f"FINAL RUN STATUS     : {'CRITICAL STRUCTURAL FAULT' if (critical_count + destroyed_count) > 0 else 'NOMINAL SURFACE'}\n")
            f.write("===============================================\n")
        print(f"📝 [REPORT COMPLETE] Detailed Text Summary Saved: {detailed_txt_path}")

    if RUNNING_ON_PI:
        GPIO.cleanup()
    plt.close('all')
