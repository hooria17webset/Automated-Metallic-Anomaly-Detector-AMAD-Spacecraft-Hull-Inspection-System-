import os
import time
import base64
import requests
from PIL import Image, ImageDraw

# 1. Setup Folders
BASE_DIR = r"D:\ISSP2026\issp proj\spacecraft_metal_data"
OUTPUT_DIR = os.path.join(BASE_DIR, "Master_Hybrid_Results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 2. Connection Config
API_KEY = "LEpZy0aSpVmakeRuofBq"
WORKSPACE = "hoorias-workspace"
WORKFLOW_ID = "spacecraft-metal-detection"

# --- CRITICAL ACCURACY TWEAK ---
# We append confidence=10 to force the serverless model to catch weak/faint defects
URL = f"https://serverless.roboflow.com/infer/workflows/{WORKSPACE}/{WORKFLOW_ID}?confidence=10"

print("--- 🚀 MAXIMUM ACCURACY ENGINE STARTED (CONFIDENCE = 10%) ---")

all_images = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(x in root for x in ["Hybrid_Scan_Results", "YOLO", "results", "Master_Hybrid_Results"]):
        continue
    for file in files:
        if file.lower().endswith((".png", ".jpg", ".jpeg")):
            all_images.append(os.path.join(root, file))

total_images_found = len(all_images)
print(f"✅ Scanner Engine Ready! Total {total_images_found} images queued.\n")

total_processed = 0

for IMAGE_PATH in all_images:
    file_name = os.path.basename(IMAGE_PATH)
    relative_folder = os.path.relpath(os.path.dirname(IMAGE_PATH), BASE_DIR)
    total_processed += 1
    
    print(f"📸 [{relative_folder}] Processing {total_processed}/{total_images_found}: {file_name}")

    try:
        with open(IMAGE_PATH, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "api_key": API_KEY,
            "workspace_name": WORKSPACE,
            "workflow_id": WORKFLOW_ID,
            "inputs": {"image": {"type": "base64", "value": image_base64}},
        }

        response = requests.post(URL, json=payload, timeout=15)
        
        if response.status_code == 200:
            res_json = response.json()
            predictions = []
            
            if "outputs" in res_json and len(res_json["outputs"]) > 0:
                predictions = res_json["outputs"][0].get("predictions", {}).get("predictions", [])

            img = Image.open(IMAGE_PATH).convert("RGB")
            draw = ImageDraw.Draw(img)
            defect_found = False

            if predictions:
                defect_found = True
                print(f"   🚨 DETECTED: {len(predictions)} defect(s) found!")
                
                for pred in predictions:
                    x, y, w, h = pred["x"], pred["y"], pred["width"], pred["height"]
                    label = pred.get("class", "defect")
                    conf = pred.get("confidence", 0.0)

                    left = x - (w / 2)
                    top = y - (h / 2)
                    right = x + (w / 2)
                    bottom = y + (h / 2)

                    draw.rectangle([left, top, right, bottom], outline="red", width=4)
                    draw.text((left, top - 12), f"{label} ({conf:.2f})", fill="red")

            if defect_found:
                img.save(os.path.join(OUTPUT_DIR, f"detected_{file_name}"))
            else:
                img.save(os.path.join(OUTPUT_DIR, f"clean_{file_name}"))
                print("   ↳ Status: ✅ SURFACE CLEAN.")
        else:
            print(f"   ❌ Server Side Error ({response.status_code})")

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        continue

    time.sleep(0.05)

print(f"\n✨ Scanning process complete! Output directory: {OUTPUT_DIR}")
